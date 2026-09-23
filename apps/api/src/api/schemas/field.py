from pydantic import BaseModel, Field, ConfigDict


class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="The name of the field")
    area_hectares: float = Field(gt=0, description="The area of the field in hectares")

class FieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str = Field(min_length=1, max_length=50, description="The name of the field")
    area_hectares: float = Field(gt=0, description="The area of the field in hectares")
