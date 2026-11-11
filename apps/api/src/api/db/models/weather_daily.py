import datetime
from datetime import date as datetimeDate

from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class WeatherDaily(Base):
    __tablename__ = "weather_daily"

    cell_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    date: Mapped[datetimeDate] = mapped_column(Date, primary_key=True)
    radn: Mapped[float | None] = mapped_column(Float, nullable=True)
    maxt: Mapped[float | None] = mapped_column(Float, nullable=True)
    mint: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    rh: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
