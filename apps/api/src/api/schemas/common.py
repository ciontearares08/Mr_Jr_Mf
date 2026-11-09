import datetime
from enum import StrEnum
from functools import cached_property
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field
from shapely.geometry import Polygon


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


# Range checks also reject inf and nan.
Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]


def keep_only_lon_lat(position: object) -> object:
    """Drop the values after lon and lat, such as altitude.

    GeoJSON allows extra values in a position, for example [lon, lat, altitude].
    """
    if isinstance(position, (list, tuple)) and len(position) > 2:
        return position[:2]
    return position


Position = Annotated[tuple[Longitude, Latitude], BeforeValidator(keep_only_lon_lat)]
# A closed ring needs at least 3 corners plus the repeated first point.
Ring = Annotated[list[Position], Field(min_length=4)]


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[Ring] = Field(
        min_length=1,
        description="Rings of [lon, lat] points. Extra values, such as altitude, are ignored",
    )

    @cached_property
    def shape(self) -> Polygon:
        """The polygon as a shapely shape, built once per instance."""
        exterior, *holes = self.coordinates
        return Polygon(exterior, holes)
