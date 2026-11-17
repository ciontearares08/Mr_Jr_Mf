"""API tests for authentication routes. They need the Postgres database."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from conftest import SignUp
from fastapi.testclient import TestClient

from api.routers.auth import JWT_ALGORITHM, JWT_ISSUER, JWT_SECRET_KEY

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another long passphrase"


@pytest.fixture
def email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def register(client: TestClient, email: str) -> httpx.Response:
    return client.post("/auth/register", json={"email": email, "password": PASSWORD})


def login(client: TestClient, email: str, password: str = PASSWORD) -> httpx.Response:
    return client.post("/auth/token", data={"username": email, "password": password})


def bearer(token_response: httpx.Response) -> dict[str, str]:
    assert token_response.status_code == 200, token_response.text
    return {"Authorization": f"Bearer {token_response.json()['access_token']}"}


def forged_token(secret: str, audience: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(hours=1),
        "iss": JWT_ISSUER,
        "aud": audience,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


# REGISTER
def test_register_user(client: TestClient, email: str) -> None:
    """Registering a new user returns 201 with the email and an id, but no password."""
    response = register(client, email)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_email_fails(client: TestClient, email: str) -> None:
    """Registering the same email twice returns 400."""
    assert register(client, email).status_code == 201

    response = register(client, email)

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_duplicate_email_ignores_case(client: TestClient, email: str) -> None:
    """Emails are case-insensitive: the same address in upper case is a duplicate."""
    assert register(client, email).status_code == 201

    response = register(client, email.upper())

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


# LOGIN
def test_login_user(client: TestClient, sign_up: SignUp, email: str) -> None:
    """Logging in with the right password returns 200 and a bearer token."""
    sign_up(email, PASSWORD)

    response = login(client, email)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_ignores_email_case(
    client: TestClient, sign_up: SignUp, email: str
) -> None:
    """Logging in with the email in upper case still works."""
    sign_up(email, PASSWORD)

    assert login(client, email.upper()).status_code == 200


def test_login_wrong_password_fails(
    client: TestClient, sign_up: SignUp, email: str
) -> None:
    """Logging in with the wrong password returns 401."""
    sign_up(email, PASSWORD)

    assert login(client, email, "wrongpassword").status_code == 401


@pytest.mark.parametrize("username", ["nobody@example.com", "not-an-email"])
def test_login_unknown_or_invalid_email_fails(
    client: TestClient, username: str
) -> None:
    """Logging in as an unknown or invalid email returns 401, like a wrong password."""
    response = login(client, username)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


# ME
def test_get_current_user_me(client: TestClient, sign_up: SignUp) -> None:
    """GET /auth/me with a valid token returns 200 and the user's profile."""
    email, headers = sign_up()

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert "id" in data


def test_get_current_user_me_without_token_fails(client: TestClient) -> None:
    """GET /auth/me without a token returns 401 and asks for a bearer token."""
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        forged_token("a-wrong-secret-that-is-at-least-32-bytes", "agriculture-web"),
        forged_token(JWT_SECRET_KEY, "some-other-app"),
        forged_token(JWT_SECRET_KEY, "agriculture-web"),
    ],
    ids=["garbage", "wrong-secret", "wrong-audience", "unknown-jti"],
)
def test_get_current_user_me_with_bad_token_fails(
    client: TestClient, token: str
) -> None:
    """GET /auth/me with a malformed, forged or unknown token returns 401."""
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# LOGOUT
def test_logout_revokes_only_the_current_token(
    client: TestClient, sign_up: SignUp
) -> None:
    """POST /auth/logout revokes the token it uses, but the user's other tokens work."""
    email, headers = sign_up()
    other_headers = bearer(login(client, email))

    assert client.post("/auth/logout", headers=headers).status_code == 204

    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me", headers=other_headers).status_code == 200


def test_logout_all_revokes_every_token(client: TestClient, sign_up: SignUp) -> None:
    """POST /auth/logout-all revokes every token of the user."""
    email, headers = sign_up()
    other_headers = bearer(login(client, email))

    assert client.post("/auth/logout-all", headers=headers).status_code == 204

    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me", headers=other_headers).status_code == 401


# CHANGE PASSWORD
def test_change_password(client: TestClient, sign_up: SignUp) -> None:
    """A password change keeps the current token, revokes others, and swaps passwords."""
    email, headers = sign_up(password=PASSWORD)
    other_headers = bearer(login(client, email))

    response = client.patch(
        "/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=other_headers).status_code == 401
    assert login(client, email, PASSWORD).status_code == 401
    assert login(client, email, NEW_PASSWORD).status_code == 200


def test_change_password_wrong_current_password_fails(
    client: TestClient, sign_up: SignUp
) -> None:
    """A password change with the wrong current password returns 400."""
    email, headers = sign_up(password=PASSWORD)

    response = client.patch(
        "/auth/password",
        json={"current_password": "wrongpassword", "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 400
    assert login(client, email, PASSWORD).status_code == 200


# CHANGE EMAIL
def test_change_email(client: TestClient, sign_up: SignUp, email: str) -> None:
    """An email change returns the new email, and the user logs in with it."""
    old_email, headers = sign_up(password=PASSWORD)

    response = client.patch(
        "/auth/email",
        json={"email": email, "current_password": PASSWORD},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert login(client, email).status_code == 200
    assert login(client, old_email).status_code == 401


def test_change_email_to_taken_email_fails(client: TestClient, sign_up: SignUp) -> None:
    """An email change to another user's email returns 400 and keeps the old email."""
    taken_email, _ = sign_up()
    email, headers = sign_up(password=PASSWORD)

    response = client.patch(
        "/auth/email",
        json={"email": taken_email, "current_password": PASSWORD},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"
    assert client.get("/auth/me", headers=headers).json()["email"] == email


def test_change_email_wrong_current_password_fails(
    client: TestClient, sign_up: SignUp, email: str
) -> None:
    """An email change with the wrong current password returns 400."""
    _, headers = sign_up()

    response = client.patch(
        "/auth/email",
        json={"email": email, "current_password": "wrongpassword"},
        headers=headers,
    )

    assert response.status_code == 400
