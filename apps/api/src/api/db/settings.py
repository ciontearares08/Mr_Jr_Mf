from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models.app_setting import AppSetting


def get_demo_date(db: Session) -> date:
    statement = select(AppSetting.demo_date).where(AppSetting.id == 1)
    demo_date = db.scalar(statement)

    if demo_date is None:
        raise RuntimeError("Demo date configuration not found")

    return demo_date
