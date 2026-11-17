"""API tests for creating and reading fields. They need the Postgres database."""

import datetime

import pytest
from conftest import SignUp
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.models.field_member import FieldMember, FieldRole

SQUARE = [
    [10.38, 55.40],
    [10.40, 55.40],
    [10.40, 55.41],
    [10.38, 55.41],
    [10.38, 55.40],
]
NEW_FIELD = {
    "name": "North field",
    "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
    "sowing_window": {"start": "2026-09-15", "end": "2026-10-05"},
}


@pytest.fixture(autouse=True)
def no_dmi(monkeypatch: pytest.MonkeyPatch) -> None:
    # The tests block the network. The station lookup has its own tests.
    monkeypatch.setattr("api.routers.fields.wind_station_or_none", lambda _: None)


@pytest.fixture
def owner(sign_up: SignUp) -> dict[str, str]:
    _, headers = sign_up()
    return headers


@pytest.fixture
def field_id(client: TestClient, owner: dict[str, str]) -> int:
    response = client.post("/fields", json=NEW_FIELD, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_the_creator_is_the_owner(
    client: TestClient, owner: dict[str, str], field_id: int
) -> None:
    fields = client.get("/fields", headers=owner).json()

    assert [(field["id"], field["role"]) for field in fields] == [(field_id, "owner")]


def test_the_owner_reads_the_field_back(
    client: TestClient, owner: dict[str, str], field_id: int
) -> None:
    field = client.get(f"/fields/{field_id}", headers=owner).json()

    assert field["name"] == NEW_FIELD["name"]
    assert field["geometry"]["coordinates"] == [SQUARE]
    assert field["sowing_window"] == NEW_FIELD["sowing_window"]
    assert field["sowing_date"] is None
    assert field["area_ha"] > 0


def test_a_viewer_can_read_the_field(
    client: TestClient, db: Session, field_id: int, sign_up: SignUp
) -> None:
    _, viewer = sign_up()
    viewer_id = client.get("/auth/me", headers=viewer).json()["id"]
    db.add(FieldMember(field_id=field_id, user_id=viewer_id, role=FieldRole.viewer))
    db.commit()

    response = client.get(f"/fields/{field_id}", headers=viewer)

    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


def test_a_stranger_gets_404(
    client: TestClient, field_id: int, sign_up: SignUp
) -> None:
    _, stranger = sign_up()

    assert client.get(f"/fields/{field_id}", headers=stranger).status_code == 404
    assert client.get("/fields", headers=stranger).json() == []


def test_a_missing_field_looks_like_a_hidden_one(
    client: TestClient, owner: dict[str, str]
) -> None:
    response = client.get("/fields/999999", headers=owner)

    assert response.status_code == 404
    assert response.json() == {"detail": "Field not found"}


def test_fields_need_a_login(client: TestClient) -> None:
    assert client.get("/fields").status_code == 401
    assert client.post("/fields", json=NEW_FIELD).status_code == 401


def test_the_database_rejects_a_date_and_a_window(db: Session, field_id: int) -> None:
    field = db.get_one(Field, field_id)
    field.sowing_date = datetime.date(2026, 9, 20)
    with pytest.raises(IntegrityError, match="ck_fields_sowing_date_or_window"):
        db.flush()
