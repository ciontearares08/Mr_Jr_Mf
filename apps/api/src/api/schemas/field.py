from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.validation import explain_validity

from api.schemas.common import GeoJSONPolygon
from api.weather.grid import is_inside_dmi_grid


class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="The name of the field")
    geometry: GeoJSONPolygon = Field(
        description="Field boundary drawn on the map, in WGS84"
    )

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
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str = Field(min_length=1, max_length=50, description="The name of the field")
    area_ha: float = Field(gt=0, description="The area of the field in hectares")
