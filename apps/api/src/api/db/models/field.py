import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=True), nullable=True
    )
    area_ha: Mapped[float] = mapped_column(nullable=False)
    cell_id: Mapped[str | None] = mapped_column(String(50), index=True)
    soil_profile: Mapped[str | None] = mapped_column(String(50))
    sowing_date: Mapped[datetime.date | None] = mapped_column(Date)
    sowing_window_start: Mapped[datetime.date | None] = mapped_column(Date)
    sowing_window_end: Mapped[datetime.date | None] = mapped_column(Date)
    recommended_sowing_date: Mapped[datetime.date | None] = mapped_column(Date)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
