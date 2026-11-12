import datetime

from sqlalchemy import Date
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    demo_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
