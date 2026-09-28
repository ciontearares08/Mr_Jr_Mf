from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.session import get_db
from api.schemas.field import FieldCreate, FieldRead

router = APIRouter(prefix="/fields", tags=["fields"])

@router.post("", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def create_field(data: FieldCreate, db: Session = Depends(get_db)) -> FieldRead:
    field = Field(**data.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return FieldRead.model_validate(field)

