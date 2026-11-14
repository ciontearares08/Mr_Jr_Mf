"""API tests for signing in, refreshing and signing out. They need the database."""

import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.main import app
from api.routers import auth

PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """Like the shared client, but on https so the Secure refresh cookie is sent."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


@pytest.fixture
def email(client: TestClient) -> str:
    email = f"{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return email


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    """Sign in, which also stores the refresh cookie in the client."""
    response = client.post(
        "/auth/token", data={"username": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def use_refresh_cookie(client: TestClient, value: str) -> None:
    client.cookies.clear()
    client.cookies.set(auth.REFRESH_COOKIE_NAME, value)


def test_sign_in_sets_an_httponly_refresh_cookie(
    client: TestClient, email: str
) -> None:
    response = client.post(
        "/auth/token", data={"username": email, "password": PASSWORD}
    )

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{auth.REFRESH_COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "Path=/auth" in cookie
    assert "Secure" in cookie


def test_refresh_gives_a_working_access_token_and_a_new_cookie(
    client: TestClient, email: str
) -> None:
    sign_in(client, email)
    old_cookie = client.cookies[auth.REFRESH_COOKIE_NAME]

    response = client.post("/auth/refresh")

    assert response.status_code == 200, response.text
    assert client.cookies[auth.REFRESH_COOKIE_NAME] != old_cookie
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["email"] == email


def test_refresh_without_a_cookie_is_rejected(client: TestClient) -> None:
    assert client.post("/auth/refresh").status_code == 401
    use_refresh_cookie(client, "not-a-session.secret")
    assert client.post("/auth/refresh").status_code == 401


def test_a_reused_refresh_token_ends_the_session(
    client: TestClient, email: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth, "REFRESH_REUSE_GRACE", timedelta(0))
    headers = sign_in(client, email)
    stolen = client.cookies[auth.REFRESH_COOKIE_NAME]
    client.post("/auth/refresh")
    current = client.cookies[auth.REFRESH_COOKIE_NAME]

    use_refresh_cookie(client, stolen)
    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert 'refresh_token=""' in response.headers["set-cookie"]
    # The whole session is gone, for the thief and the real device alike
    use_refresh_cookie(client, current)
    assert client.post("/auth/refresh").status_code == 401
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_two_tabs_refreshing_at_once_stay_signed_in(
    client: TestClient, email: str
) -> None:
    sign_in(client, email)
    shared = client.cookies[auth.REFRESH_COOKIE_NAME]
    client.post("/auth/refresh")
    newest = client.cookies[auth.REFRESH_COOKIE_NAME]

    # The second tab sent the cookie from before the first tab's refresh
    use_refresh_cookie(client, shared)
    response = client.post("/auth/refresh")

    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers
    use_refresh_cookie(client, newest)
    assert client.post("/auth/refresh").status_code == 200


def test_an_expired_access_token_is_rejected(
    client: TestClient, email: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth, "ACCESS_TOKEN_LIFETIME", timedelta(seconds=-1))
    headers = sign_in(client, email)

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_logout_ends_the_session_and_clears_the_cookie(
    client: TestClient, email: str
) -> None:
    headers = sign_in(client, email)
    cookie = client.cookies[auth.REFRESH_COOKIE_NAME]

    response = client.post("/auth/logout", headers=headers)

    assert response.status_code == 204
    assert 'refresh_token=""' in response.headers["set-cookie"]
    assert client.get("/auth/me", headers=headers).status_code == 401
    use_refresh_cookie(client, cookie)
    assert client.post("/auth/refresh").status_code == 401


def test_logout_all_ends_every_session(client: TestClient, email: str) -> None:
    laptop = sign_in(client, email)
    phone = sign_in(client, email)

    assert client.post("/auth/logout-all", headers=laptop).status_code == 204

    assert client.get("/auth/me", headers=laptop).status_code == 401
    assert client.get("/auth/me", headers=phone).status_code == 401


def test_changing_the_password_signs_out_other_devices(
    client: TestClient, email: str
) -> None:
    laptop = sign_in(client, email)
    phone = sign_in(client, email)

    response = client.patch(
        "/auth/password",
        json={"current_password": PASSWORD, "new_password": "a brand new passphrase"},
        headers=laptop,
    )

    assert response.status_code == 204, response.text
    assert client.get("/auth/me", headers=laptop).status_code == 200
    assert client.get("/auth/me", headers=phone).status_code == 401


@pytest.mark.parametrize(
    ("current_password", "new_password"),
    [
        ("the wrong password", "a brand new passphrase"),
        (PASSWORD, PASSWORD),
    ],
)
def test_bad_password_changes_are_rejected_without_signing_out(
    client: TestClient, email: str, current_password: str, new_password: str
) -> None:
    headers = sign_in(client, email)

    response = client.patch(
        "/auth/password",
        json={"current_password": current_password, "new_password": new_password},
        headers=headers,
    )

    assert response.status_code == 400
    assert client.get("/auth/me", headers=headers).status_code == 200
