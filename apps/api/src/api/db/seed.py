"""Fill a development database with a small, known set of data.

Everything the seed creates is written out below, so you can read this file to
know which users, fields and members exist after `make db-seed`.

    make db-seed     # add the seed data, or reset it to the values below
    make db-fresh    # drop everything, run all migrations, then seed

Running the seed twice is safe. It finds each user by email and the field by
its name and owner, and sets them back to the values in this file. It does not
delete anything else you created.

It refuses to run unless APP_ENV=development (see api.db.dev).

The seed does not download weather. To load weather for the seed field, see
api.weather.store.
"""

import datetime as dt
import sys
from dataclasses import dataclass

from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.dev import NotDevelopment, require_development
from api.db.models import Field, FieldMember, FieldRole, User
from api.db.session import session_local
from api.geometry import area_ha
from api.routers.auth import hash_password
from api.schemas.user import normalize_email


@dataclass(frozen=True)
class SeedUser:
    email: str
    password: str  # Dev only. Log in with these.


@dataclass(frozen=True)
class SeedField:
    name: str
    owner_email: str
    # (lon, lat) corners in WGS84. The first and last corner are the same.
    corners: list[tuple[float, float]]
    # The DMI grid cell and min wind station are written out here instead of
    # looked up, so seeding never calls DMI. test_seed checks the cell.
    cell_id: str
    wind_station_id: str
    sowing_window_start: dt.date
    sowing_window_end: dt.date


@dataclass(frozen=True)
class SeedMember:
    email: str
    field_name: str
    role: FieldRole


# --- Seed data --------------------------------------------------------------

FARMER = SeedUser(email="farmer@example.com", password="farmer-password")
ADVISOR = SeedUser(email="advisor@example.com", password="advisor-password")
# Has no fields, for testing the empty state of the app.
NEWCOMER = SeedUser(email="newcomer@example.com", password="newcomer-password")

USERS = [FARMER, ADVISOR, NEWCOMER]

# About 28 ha on western Amager, south of Copenhagen. It lies in DMI cell
# 10km_617_72, the same place as the sim's Copenhagen weather file.
DEMO_FIELD = SeedField(
    name="Vestamager demo field",
    owner_email=FARMER.email,
    corners=[
        (12.5550, 55.6350),
        (12.5640, 55.6350),
        (12.5640, 55.6395),
        (12.5550, 55.6395),
        (12.5550, 55.6350),
    ],
    cell_id="10km_617_72",
    wind_station_id="06180",  # Københavns Lufthavn (Kastrup)
    # The same window as the sowing rule in apps/sim/models/wheat.apsimx.
    sowing_window_start=dt.date(2025, 9, 15),
    sowing_window_end=dt.date(2025, 10, 15),
)

FIELDS = [DEMO_FIELD]

MEMBERS = [
    SeedMember(email=FARMER.email, field_name=DEMO_FIELD.name, role=FieldRole.owner),
    SeedMember(email=ADVISOR.email, field_name=DEMO_FIELD.name, role=FieldRole.viewer),
]


# --- Seeding ----------------------------------------------------------------


def seed(db: Session) -> None:
    """Create or reset the seed data and commit."""
    require_development()
    users = {seed_user.email: upsert_user(db, seed_user) for seed_user in USERS}
    fields = {
        seed_field.name: upsert_field(db, seed_field, users[seed_field.owner_email])
        for seed_field in FIELDS
    }
    for member in MEMBERS:
        upsert_member(db, fields[member.field_name], users[member.email], member.role)
    db.commit()


def upsert_user(db: Session, seed_user: SeedUser) -> User:
    email = normalize_email(seed_user.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
    user.password_hash = hash_password(seed_user.password)
    db.flush()
    return user


def upsert_field(db: Session, seed_field: SeedField, owner: User) -> Field:
    """Find the field by its name and owner, or create it."""
    field = db.scalar(
        select(Field)
        .join(FieldMember, FieldMember.field_id == Field.id)
        .where(
            Field.name == seed_field.name,
            FieldMember.user_id == owner.id,
            FieldMember.role == FieldRole.owner,
        )
    )
    if field is None:
        field = Field()
        db.add(field)
    polygon = Polygon(seed_field.corners)
    field.name = seed_field.name
    field.geom = from_shape(polygon, srid=4326)
    field.area_ha = area_ha(polygon)
    field.cell_id = seed_field.cell_id
    field.wind_station_id = seed_field.wind_station_id
    field.sowing_date = None
    field.sowing_window_start = seed_field.sowing_window_start
    field.sowing_window_end = seed_field.sowing_window_end
    db.flush()
    return field


def upsert_member(db: Session, field: Field, user: User, role: FieldRole) -> None:
    member = db.get(FieldMember, (field.id, user.id))
    if member is None:
        member = FieldMember(field_id=field.id, user_id=user.id)
        db.add(member)
    member.role = role
    db.flush()


def main() -> int:
    try:
        require_development()
    except NotDevelopment as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    with session_local() as db:
        seed(db)
    print(f"Seeded {len(USERS)} users, {len(FIELDS)} field, {len(MEMBERS)} members.")
    for seed_user in USERS:
        print(f"  {seed_user.email} / {seed_user.password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
