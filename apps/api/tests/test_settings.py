from datetime import date
from unittest.mock import Mock

from fastapi.testclient import TestClient

from api.db.session import get_db
from api.main import app


def test_returns_demo_date() -> None:
    mock_db = Mock()
    mock_db.scalar.return_value = date(2026, 3, 15)

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = TestClient(app).get("/settings/demo-date")

        assert response.status_code == 200
        assert response.json() == "2026-03-15"
        mock_db.scalar.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_db, None)