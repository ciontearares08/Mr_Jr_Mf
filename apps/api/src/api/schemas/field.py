import datetime
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator
from shapely.validation import explain_validity

from api.db.models.field_member import FieldRole
from api.schemas.common import GeoJSONPolygon
from api.weather.grid import is_inside_dmi_grid


class SowingWindow(BaseModel):
    """Dates between which APSIM picks the sowing day."""

    start: datetime.date
    end: datetime.date

    @model_validator(mode="after")
    def must_start_before_it_ends(self) -> Self:
        if self.start > self.end:
            raise ValueError("The sowing window must start before it ends")
        return self


class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="The name of the field")
    geometry: GeoJSONPolygon = Field(
        description="Field boundary drawn on the map, in WGS84"
    )
    sowing_date: datetime.date | None = Field(
        default=None, description="The day the farmer sows. Leave out with a window"
    )
    sowing_window: SowingWindow | None = Field(
        default=None, description="Let APSIM pick the day. Leave out with a date"
    )

    @model_validator(mode="after")
    def needs_a_sowing_date_or_window(self) -> Self:
        if self.sowing_date is not None and self.sowing_window is not None:
            raise ValueError("Give a sowing date or a sowing window, not both")
        if self.sowing_date is None and self.sowing_window is None:
            raise ValueError("Give a sowing date or a sowing window")
        return self

    @field_validator("geometry")
    @classmethod
    def must_be_a_valid_polygon(cls, geometry: GeoJSONPolygon) -> GeoJSONPolygon:
        polygon = geometry.shape
        if not polygon.is_valid:
            # For example "Self-intersection[10.39 55.405]" or "Hole lies outside shell".
            raise ValueError(f"The polygon is not valid: {explain_validity(polygon)}")
        if polygon.area == 0:
            raise ValueError("The polygon has no area")
        return geometry

    @field_validator("geometry")
    @classmethod
    def must_be_inside_dmi_grid(cls, geometry: GeoJSONPolygon) -> GeoJSONPolygon:
        # Weather comes only from DMI. Outside its grid we get no weather and the
        # simulation would run on empty values without any error.
        if not is_inside_dmi_grid(geometry.shape):
            raise ValueError(
                "The field is outside Denmark. Weather data from DMI covers only Denmark"
            )
        return geometry


class FieldRead(BaseModel):
    id: int
    name: str
    geometry: GeoJSONPolygon
    area_ha: float = Field(description="The area of the field in hectares")
    sowing_date: datetime.date | None
    sowing_window: SowingWindow | None
    role: FieldRole = Field(description="What the current user may do with the field")
