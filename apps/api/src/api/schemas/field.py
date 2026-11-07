from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.validation import explain_validity

from api.schemas.common import GeoJSONPolygon


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


class FieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str = Field(min_length=1, max_length=50, description="The name of the field")
    area_ha: float = Field(gt=0, description="The area of the field in hectares")
