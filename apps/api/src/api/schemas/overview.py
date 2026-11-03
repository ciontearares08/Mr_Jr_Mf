import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from api.schemas.common import DateRange, FloatRange, Rating, SourceInfo, Stage


class SowingStatus(StrEnum):
    sown = "sown"
    planned = "planned"


class Sowing(BaseModel):
    status: SowingStatus
    date: datetime.date | None = Field(
        description="Actual sowing date when sown, otherwise the predicted date"
    )
    window_start: datetime.date | None
    window_end: datetime.date | None


class FieldInfo(BaseModel):
    id: int
    name: str
    crop: str
    area_ha: float
    cell_id: str | None = Field(description="DMI 10 km grid cell used for weather")
    sowing: Sowing


class UpcomingStage(Stage):
    date: DateRange


class StageInfo(SourceInfo):
    current: Stage
    current_since: datetime.date
    upcoming: list[UpcomingStage] = Field(description="Next stages, soonest first")


class Metric(SourceInfo):
    value: FloatRange
    unit: str
    rating: Rating


class Metrics(BaseModel):
    lai: Metric = Field(description="Leaf area index at as_of")
    paw: Metric = Field(description="Root-zone plant available water at as_of")
    predicted_yield: Metric = Field(description="Yield at harvest")


class WeatherCondition(StrEnum):
    clear = "clear"
    partly_cloudy = "partly_cloudy"
    cloudy = "cloudy"
    rain = "rain"
    showers = "showers"
    thunder = "thunder"
    fog = "fog"
    snow = "snow"


class Weather(SourceInfo):
    date: datetime.date
    condition: WeatherCondition
    temp_c: float
    temp_min_c: float
    temp_max_c: float
    rain_mm: float
    wind_ms: float
    humidity_pct: float


class AlertRule(StrEnum):
    soil_water_low = "soil_water_low"
    waterlogging = "waterlogging"
    sensitive_stage = "sensitive_stage"


class AlertSeverity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Alert(BaseModel):
    id: int
    rule: AlertRule
    severity: AlertSeverity
    title: str
    reason: str
    action: str
    uncertainty: str
    opened_on: datetime.date


class Alerts(SourceInfo):
    items: list[Alert] = Field(description="Open alerts, most severe first")


class SummarySource(StrEnum):
    llm = "llm"
    template = "template"


class HealthSummary(SourceInfo):
    text: str
    source: SummarySource


class ConsistencyStatus(StrEnum):
    on_track = "on_track"
    behind_model = "behind_model"
    not_enough_data = "not_enough_data"


class GeoJSONPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[tuple[float, float]]] = Field(
        description="Rings of [lon, lat] points"
    )


class NdviLegendEntry(BaseModel):
    min: float
    max: float
    color: str = Field(description="Hex color, e.g. #1a9850")
    label: str


class WeakestArea(BaseModel):
    geometry: GeoJSONPolygon
    mean_ndvi: float


class Satellite(SourceInfo):
    observed_on: datetime.date | None = Field(
        description="Date of the latest clear Sentinel-2 image"
    )
    mean_ndvi: float | None
    consistency: ConsistencyStatus
    weakest_area: WeakestArea | None
    legend: list[NdviLegendEntry]
    ndvi_image_url: str | None
    true_color_image_url: str | None
    image_bounds: list[tuple[float, float]] = Field(
        description="[[south, west], [north, east]] for the image overlay"
    )


class Overview(BaseModel):
    as_of: datetime.date = Field(description="The demo date D")
    field: FieldInfo
    stage: StageInfo
    metrics: Metrics
    weather: Weather
    alerts: Alerts
    summary: HealthSummary
    satellite: Satellite
