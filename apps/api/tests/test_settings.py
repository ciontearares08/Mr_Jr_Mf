from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from api.db.models.app_setting import AppSetting
from api.settings import get_demo_date


def test_returns_the_date_the_migration_seeds(client: TestClient) -> None:
    response = client.get("/settings/demo-date")

    assert response.status_code == 200
    assert response.json() == "2026-03-15"


def test_returns_the_date_after_it_moves(client: TestClient, db: Session) -> None:
    db.get(AppSetting, 1).demo_date = date(2026, 4, 1)
    db.flush()

    assert client.get("/settings/demo-date").json() == "2026-04-01"
    assert get_demo_date(db) == date(2026, 4, 1)


def test_returns_503_when_the_date_is_missing(client: TestClient, db: Session) -> None:
    db.execute(delete(AppSetting))

    response = client.get("/settings/demo-date")

    assert response.status_code == 503
    assert "Demo date is not set" in response.json()["detail"]
