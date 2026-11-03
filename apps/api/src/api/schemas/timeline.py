import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from api.schemas.common import DateRange, FloatRange, SourceInfo, Stage


class StageStatus(StrEnum):
    past = "past"
    current = "current"
    upcoming = "upcoming"


class StageBasis(StrEnum):
    # Never "actual": the app has no field observations
    simulated_observed = "simulated_observed"
    predicted = "predicted"


class TimelineStage(Stage):
    note: str | None = Field(description="What matters to the farmer in this stage")
    status: StageStatus
    basis: StageBasis = Field(
        description="simulated_observed when every run reached it before as_of"
    )
    start: DateRange
    runs_reached: int
    runs_total: int


class Timeline(SourceInfo):
    as_of: datetime.date = Field(description="The demo date D")
    field_id: int
    stages: list[TimelineStage] = Field(description="All stages in season order")


class TimelineDay(BaseModel):
    date: datetime.date
    stage_code: str
    zadoks: float
    lai: FloatRange
    biomass: FloatRange
    grain_yield: FloatRange
    paw: FloatRange


class TimelineDetails(SourceInfo):
    """Daily rows for the detailed table, served separately because they are large."""

    as_of: datetime.date
    field_id: int
    units: dict[str, str] = Field(description="Unit per value column, e.g. lai: m²/m²")
    days: list[TimelineDay]
