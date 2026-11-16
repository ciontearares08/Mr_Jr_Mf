"""API tests for authentication routes (register, token, me, logout)."""

import uuid

from fastapi.testclient import TestClient


def sign_up(client: TestClient) -> tuple[str, dict[str, str]]:
    """Register a new user and return (email, auth_headers)."""
    email = f"{uuid.uuid4().hex}@example.com"
    password = "correct horse battery staple"

    register_response = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert register_response.status_code == 201, register_response.text

    token_response = client.post(
        "/auth/token", data={"username": email, "password": password}
    )
    assert token_response.status_code == 200, token_response.text

    return email, {"Authorization": f"Bearer {token_response.json()['access_token']}"}


def test_register_user(client: TestClient) -> None:
    """Registering a new user returns 201 with the email and an id."""
    user = {"email": f"{uuid.uuid4().hex}@example.com", "password": "securepassword123"}

    response = client.post("/auth/register", json=user)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == user["email"]
    assert "id" in data


def test_register_duplicate_email_fails(client: TestClient) -> None:
    """Registering the same email twice returns 400."""
    user = {"email": f"{uuid.uuid4().hex}@example.com", "password": "securepassword123"}

    first = client.post("/auth/register", json=user)
    assert first.status_code == 201

    second = client.post("/auth/register", json=user)
    assert second.status_code == 400


def test_login_user(client: TestClient) -> None:
    """Logging in with the right password returns 200 and a bearer token."""
    user = {"email": f"{uuid.uuid4().hex}@example.com", "password": "securepassword123"}
    register_response = client.post("/auth/register", json=user)
    assert register_response.status_code == 201

    response = client.post(
        "/auth/token",
        data={"username": user["email"], "password": user["password"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_fails(client: TestClient) -> None:
    """Logging in with the wrong password returns 401."""
    user = {"email": f"{uuid.uuid4().hex}@example.com", "password": "securepassword123"}
    register_response = client.post("/auth/register", json=user)
    assert register_response.status_code == 201

    response = client.post(
        "/auth/token",
        data={"username": user["email"], "password": "wrongpassword"},
    )

    assert response.status_code == 401


def test_get_current_user_me(client: TestClient) -> None:
    """GET /auth/me with a valid token returns 200 and the user's profile."""
    email, headers = sign_up(client)

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert "id" in data


def test_get_current_user_me_without_token_fails(client: TestClient) -> None:
    """GET /auth/me without a token returns 401."""
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_logout_user_revokes_token(client: TestClient) -> None:
    """POST /auth/logout returns 204 and revokes the token for subsequent /auth/me calls."""
    _, headers = sign_up(client)

    logout_response = client.post("/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    me_response = client.get("/auth/me", headers=headers)
    assert me_response.status_code == 401