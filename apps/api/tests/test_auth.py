from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test user registration endpoint."""
    response = client.post(
        "/auth/register",
        json={
            "email": "freshuser@example.com",
            "password": "securepassword123",
            "full_name": "Fresh User",
        },
    )
    assert response.status_code in [200, 201]
    data = response.json()
    assert "email" in data or "id" in data


def test_login_user(client: TestClient):
    """Test user login / token endpoint."""
    # Ensure user exists first
    client.post(
        "/auth/register",
        json={
            "email": "loginuser@example.com",
            "password": "securepassword123",
            "full_name": "Login User",
        },
    )

    # Login via /auth/token using OAuth2 form data
    response = client.post(
        "/auth/token",
        data={
            "username": "loginuser@example.com",
            "password": "securepassword123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_get_current_user_me(client: TestClient):
    """Test fetching current authenticated user profile."""
    client.post(
        "/auth/register",
        json={
            "email": "meuser@example.com",
            "password": "securepassword123",
            "full_name": "Me User",
        },
    )
    login_res = client.post(
        "/auth/token",
        data={
            "username": "meuser@example.com",
            "password": "securepassword123",
        },
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "meuser@example.com"


def test_logout_user(client: TestClient):
    """Test user logout endpoint."""
    client.post(
        "/auth/register",
        json={
            "email": "logoutuser@example.com",
            "password": "securepassword123",
            "full_name": "Logout User",
        },
    )
    login_res = client.post(
        "/auth/token",
        data={
            "username": "logoutuser@example.com",
            "password": "securepassword123",
        },
    )
    token = login_res.json()["access_token"]

    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in [200, 204]
