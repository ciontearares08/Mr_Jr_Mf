from typing import Annotated

from fastapi import APIRouter, Depends, status
from geoalchemy2.shape import from_shape
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.models.field_member import FieldMember, FieldRole
from api.db.session import get_db
from api.geometry import area_ha
from api.routers.auth import CurrentUser
from api.schemas.field import FieldCreate, FieldRead
from api.weather.grid import cell_for_geometry

router = APIRouter(prefix="/fields", tags=["fields"])


@router.post("", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def create_field(
    data: FieldCreate, user: CurrentUser, db: Annotated[Session, Depends(get_db)]
) -> FieldRead:
    polygon = data.geometry.shape
    field = Field(
        name=data.name,
        geom=from_shape(polygon, srid=4326),
        area_ha=area_ha(polygon),
        cell_id=cell_for_geometry(polygon),
    )
    db.add(field)
    db.flush()  # Assigns field.id so the member row can point to it.
    db.add(FieldMember(field_id=field.id, user_id=user.id, role=FieldRole.owner))
    db.commit()
    db.refresh(field)
    return FieldRead.model_validate(field)
