import datetime

from sqlalchemy import CheckConstraint, Date
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    demo_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
