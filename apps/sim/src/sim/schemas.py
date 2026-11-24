"""Request and response bodies of the simulate endpoint.

The API sends one request per ensemble: the field inputs once, and one member
per past season. Every member covers the same 2025/26 dates (observed weather
up to the demo date D, then the weather of one past season after D), so one
sowing date or sowing window works for all members.
"""

import datetime as dt
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

# REQUEST


class WeatherRow(BaseModel):
    """The weather of one day, as stored in the API's weather_daily table.
    None means the value is missing. The sim fills a single missing day from
    the day before and the day after; a longer gap fails that member.
    """

    date: dt.date
    radn: float | None = Field(description="Solar radiation, MJ/m²")
    maxt: float | None = Field(description="Maximum temperature, °C")
    mint: float | None = Field(description="Minimum temperature, °C")
    rain: float | None = Field(description="Rain, mm")


class Event(BaseModel):
    """Something the farmer did on the field, with the columns of field_events.
    Not used by APSIM yet: the model applies its own fertiliser.
    """

    type: str = Field(min_length=1, description="For example fertiliser")
    date: dt.date
    amount: float | None = None
    unit: str | None = Field(default=None, description="For example kg N/ha")


class SowingWindow(BaseModel):
    """Dates between which APSIM picks the sowing day. Same shape as in the API."""

    start: dt.date
    end: dt.date

    @model_validator(mode="after")
    def must_start_before_it_ends(self) -> Self:
        if self.start > self.end:
            raise ValueError("The sowing window must start before it ends")
        return self


class Member(BaseModel):
    """One run of the ensemble: a full weather file for one past season."""

    season: str = Field(
        min_length=1,
        description="The past season used after the demo date, for example 2018/19",
    )
    met: list[WeatherRow] = Field(
        min_length=1, description="One row per day, oldest first"
    )


class SimulateRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90, description="Written into the .met file")
    longitude: float = Field(ge=-180, le=180)
    # Not used yet: the model has one fixed soil until the default is chosen (S4-35)
    soil_profile: str | None = None
    events: list[Event] = Field(default_factory=list)
    sowing_date: dt.date | None = Field(
        default=None, description="The day to sow. Leave out with a window"
    )
    sowing_window: SowingWindow | None = Field(
        default=None, description="Let APSIM pick the day. Leave out with a date"
    )
    members: list[Member] = Field(min_length=1)

    @model_validator(mode="after")
    def needs_a_sowing_date_or_window(self) -> Self:
        if self.sowing_date is not None and self.sowing_window is not None:
            raise ValueError("Give a sowing date or a sowing window, not both")
        if self.sowing_date is None and self.sowing_window is None:
            raise ValueError("Give a sowing date or a sowing window")
        return self

    @model_validator(mode="after")
    def seasons_must_be_unique(self) -> Self:
        # The API matches each result to its member by the season label
        seasons = [member.season for member in self.members]
        repeated = sorted({season for season in seasons if seasons.count(season) > 1})
        if repeated:
            raise ValueError(f"Each season can only be sent once: {repeated}")
        return self


# RESPONSE


class MemberStatus(StrEnum):
    ok = "ok"
    failed = "failed"


class DailyRow(BaseModel):
    """One day of a run, from the sowing day to harvest ripe.
    The crop values are None when APSIM wrote no value for that day.
    """

    date: dt.date
    # APSIM names a stage only on the day it starts; on the other days it is None
    stage: str | None
    zadoks: float | None
    lai: float | None = Field(description="Leaf area index, m²/m²")
    biomass: float | None = Field(description="Above-ground dry weight, g/m²")
    biomass_n: float | None = Field(description="Nitrogen in the biomass, g/m²")
    grain_yield: float | None = Field(description="Grain yield, kg/ha")
    grain_protein: float | None = Field(description="%")
    grain_size: float | None = Field(description="g per grain")
    grain_number: float | None = Field(description="Grains per m²")
    grain_wt: float | None = Field(description="Grain dry weight, g/m²")
    grain_n: float | None = Field(description="Nitrogen in the grain, g/m²")
    # One value per soil layer, top layer first, as stored in simulation_daily
    sw: list[float] = Field(description="Soil water per layer, mm/mm")
    paw: list[float] = Field(description="Plant available water per layer, mm")


class MemberResult(BaseModel):
    """The result of one member. A failed member has an error and no rows."""

    season: str
    status: MemberStatus
    runtime_ms: int = Field(ge=0, description="How long the run took")
    error: str | None = Field(default=None, description="Why the run failed")
    sowing_date: dt.date | None = Field(
        default=None, description="The day APSIM sowed, None when the run failed"
    )
    daily: list[DailyRow] = Field(default_factory=list)


class SimulateResponse(BaseModel):
    members: list[MemberResult] = Field(description="In the same order as the request")
