"""App-wide settings stored in the app_settings table.

Every feature reads today from get_demo_date, so moving D moves the whole app.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models.app_setting import AppSetting


class DemoDateMissingError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo date is not set. Run the migrations: make migrate",
        )


def get_demo_date(db: Session) -> date:
    demo_date = db.scalar(select(AppSetting.demo_date).where(AppSetting.id == 1))
    if demo_date is None:
        raise DemoDateMissingError
    return demo_date
