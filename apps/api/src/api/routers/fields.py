from fastapi import APIRouter, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping
from sqlalchemy import select

from api.auth.permissions import require_role
from api.db.models.field import Field
from api.db.models.field_member import FieldMember, FieldRole
from api.geometry import area_ha
from api.routers.auth import CurrentUser, DbSession
from api.schemas.common import GeoJSONPolygon
from api.schemas.field import FieldCreate, FieldRead, SowingWindow
from api.weather.grid import cell_for_geometry
from api.weather.stations import wind_station_or_none

router = APIRouter(prefix="/fields", tags=["fields"])


def to_read(field: Field, role: FieldRole) -> FieldRead:
    window = None
    # The database CHECK makes sure that both dates are set or neither is.
    if field.sowing_window_start is not None and field.sowing_window_end is not None:
        window = SowingWindow(
            start=field.sowing_window_start, end=field.sowing_window_end
        )
    return FieldRead(
        id=field.id,
        name=field.name,
        geometry=GeoJSONPolygon.model_validate(mapping(to_shape(field.geom))),
        area_ha=field.area_ha,
        sowing_date=field.sowing_date,
        sowing_window=window,
        role=role,
    )


@router.post("", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def create_field(data: FieldCreate, user: CurrentUser, db: DbSession) -> FieldRead:
    polygon = data.geometry.shape
    window = data.sowing_window
    field = Field(
        name=data.name,
        geom=from_shape(polygon, srid=4326),
        area_ha=area_ha(polygon),
        cell_id=cell_for_geometry(polygon),
        wind_station_id=wind_station_or_none(polygon),
        sowing_date=data.sowing_date,
        sowing_window_start=window.start if window else None,
        sowing_window_end=window.end if window else None,
    )
    db.add(field)
    db.flush()  # Assigns field.id so the member row can point to it.
    db.add(FieldMember(field_id=field.id, user_id=user.id, role=FieldRole.owner))
    # Build the response before commit() expires the field, so that it is not
    # loaded again from the database.
    result = to_read(field, FieldRole.owner)
    db.commit()
    return result


@router.get("", response_model=list[FieldRead])
def list_fields(user: CurrentUser, db: DbSession) -> list[FieldRead]:
    rows = db.execute(
        select(Field, FieldMember.role)
        .join(FieldMember)
        .where(FieldMember.user_id == user.id)
        .order_by(Field.id.desc())  # Newest first.
    )
    return [to_read(field, role) for field, role in rows]


@router.get("/{field_id}", response_model=FieldRead)
def read_field(field_id: int, user: CurrentUser, db: DbSession) -> FieldRead:
    field, role = require_role(field_id, user, db, FieldRole.viewer)
    return to_read(field, role)
