from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.db.settings import get_demo_date

router = APIRouter(prefix="/settings", tags=["settings"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/demo-date", response_model=date)
def read_demo_date(db: DbSession) -> date:
    return get_demo_date(db)
