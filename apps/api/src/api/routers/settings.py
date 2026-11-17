from datetime import date

from fastapi import APIRouter

from api.routers.auth import DbSession
from api.settings import get_demo_date

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/demo-date", response_model=date)
def read_demo_date(db: DbSession) -> date:
    return get_demo_date(db)
