import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FloatRange(BaseModel):
    """Spread of a value across the ensemble runs."""

    min: float
    median: float
    max: float


class DateRange(BaseModel):
    """Earliest, median and latest date across the ensemble runs."""

    min: datetime.date
    median: datetime.date
    max: datetime.date


class Rating(StrEnum):
    worst = "worst"
    poor = "poor"
    fair = "fair"
    good = "good"
    great = "great"


class SourceInfo(BaseModel):
    """Freshness of one data source, shown as "Updated ..." on its card."""

    updated_at: datetime.datetime
    stale: bool = Field(description="True when the data is too old to trust at as_of")


class Stage(BaseModel):
    code: str = Field(description="APSIM stage name, e.g. HeadEmergence")
    name: str = Field(description="Farmer name of the stage")
    zadoks: int = Field(
        ge=0, le=99, description="Zadoks code at the start of the stage"
    )
