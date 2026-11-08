from sqlalchemy import Column, Date, DateTime, Float, String

from api.db.base import Base


class WeatherDaily(Base):
    __tablename__ = "weather_daily"

    cell_id = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    radn = Column(Float, nullable=True)
    maxt = Column(Float, nullable=True)
    mint = Column(Float, nullable=True)
    rain = Column(Float, nullable=True)
    wind = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    fetched_at = Column(DateTime, nullable=True)
