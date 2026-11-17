"""Tests for the dev seed. The db fixture rolls everything back after each test."""

import pytest
from shapely.geometry import Polygon
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db import dev
from api.db.dev import NotDevelopment
from api.db.models import Field, FieldMember, FieldRole, User
from api.db.seed import DEMO_FIELD, FARMER, MEMBERS, USERS, seed
from api.routers.auth import authenticate_user
from api.weather.grid import cell_for_geometry, is_inside_dmi_grid


@pytest.fixture(autouse=True)
def development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_seed_creates_the_users_field_and_members(db: Session) -> None:
    # The dev database may already hold the seed, so we look rows up by key.
    seed(db)

    emails = set(db.scalars(select(User.email)))
    assert {seed_user.email for seed_user in USERS} <= emails
    [field] = db.scalars(select(Field).where(Field.name == DEMO_FIELD.name)).all()
    roles = dict(
        db.execute(
            select(User.email, FieldMember.role)
            .join(FieldMember, FieldMember.user_id == User.id)
            .where(FieldMember.field_id == field.id)
        ).all()
    )
    assert roles == {member.email: member.role for member in MEMBERS}
    assert roles[FARMER.email] == FieldRole.owner


def test_seeding_twice_adds_nothing(db: Session) -> None:
    seed(db)
    counts = count(db, User), count(db, Field), count(db, FieldMember)

    seed(db)

    assert (count(db, User), count(db, Field), count(db, FieldMember)) == counts


def test_seed_users_can_log_in(db: Session) -> None:
    seed(db)

    for seed_user in USERS:
        assert authenticate_user(seed_user.email, seed_user.password, db) is not None


def test_the_written_cell_matches_the_field_corners() -> None:
    polygon = Polygon(DEMO_FIELD.corners)

    assert polygon.is_valid
    assert is_inside_dmi_grid(polygon)
    assert cell_for_geometry(polygon) == DEMO_FIELD.cell_id


@pytest.mark.parametrize("app_env", [None, "production", "Development"])
def test_seed_refuses_outside_development(
    db: Session, monkeypatch: pytest.MonkeyPatch, app_env: str | None
) -> None:
    # Keep the developer's own .env file out of the test.
    monkeypatch.setattr(dev, "load_dotenv", lambda *_: None)
    if app_env is None:
        monkeypatch.delenv("APP_ENV")
    else:
        monkeypatch.setenv("APP_ENV", app_env)
    users_before = count(db, User)

    with pytest.raises(NotDevelopment):
        seed(db)

    assert count(db, User) == users_before
