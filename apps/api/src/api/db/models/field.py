import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import CheckConstraint, Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Field(Base):
    __tablename__ = "fields"
    __table_args__ = (
        # A field has a sowing date or a whole sowing window, never both and never
        # none. The same rule is in FieldCreate. This catches other write paths.
        CheckConstraint(
            "(sowing_date IS NOT NULL"
            " AND sowing_window_start IS NULL AND sowing_window_end IS NULL)"
            " OR (sowing_date IS NULL"
            " AND sowing_window_start IS NOT NULL AND sowing_window_end IS NOT NULL"
            " AND sowing_window_start <= sowing_window_end)",
            name="ck_fields_sowing_date_or_window",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=True), nullable=False
    )
    area_ha: Mapped[float] = mapped_column(nullable=False)
    cell_id: Mapped[str | None] = mapped_column(String(50), index=True)
    # The DMI station for the daily min wind. None until DMI answers.
    wind_station_id: Mapped[str | None] = mapped_column(String(10))
    soil_profile: Mapped[str | None] = mapped_column(String(50))
    sowing_date: Mapped[datetime.date | None] = mapped_column(Date)
    sowing_window_start: Mapped[datetime.date | None] = mapped_column(Date)
    sowing_window_end: Mapped[datetime.date | None] = mapped_column(Date)
    recommended_sowing_date: Mapped[datetime.date | None] = mapped_column(Date)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
