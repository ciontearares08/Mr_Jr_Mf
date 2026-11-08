"""Example responses for the overview and timeline pages.

The data comes from one APSIM run in zealand_cleaned.csv. The ensemble spread
is made up: runs agree up to the demo date and drift apart after it, the way
the real ensemble does. Replace these routes with /fields/{id}/overview and
/fields/{id}/timeline (S4-01, S4-02) and keep the response models.
"""

import csv
import datetime
from functools import cache
from pathlib import Path
from statistics import fmean

from fastapi import APIRouter

from api.schemas.common import DateRange, FloatRange, GeoJSONPolygon, Rating, Stage
from api.schemas.overview import (
    Alert,
    AlertRule,
    Alerts,
    AlertSeverity,
    ConsistencyStatus,
    FieldInfo,
    HealthSummary,
    Metric,
    Metrics,
    NdviLegendEntry,
    Overview,
    Satellite,
    Sowing,
    SowingStatus,
    StageInfo,
    SummarySource,
    UpcomingStage,
    WeakestArea,
    Weather,
    WeatherCondition,
)
from api.schemas.timeline import (
    StageBasis,
    StageStatus,
    Timeline,
    TimelineDay,
    TimelineDetails,
    TimelineStage,
)

router = APIRouter(prefix="/stub", tags=["stubs"])

CSV_PATH = Path(__file__).resolve().parents[1] / "stub_data" / "zealand_cleaned.csv"
DEMO_DATE = datetime.date(2025, 6, 15)
UPDATED_AT = datetime.datetime(2025, 6, 15, 6, 0, tzinfo=datetime.UTC)
FIELD_ID = 1
# FAKE: assumed ensemble size, the real N is decided in S2-06
RUNS_TOTAL = 10

# Farmer names until stages.json lands (S1-06)
STAGE_NAMES = {
    "Sowing": "Sowing",
    "Germination": "Germination",
    "Emergence": "Emergence",
    "DoubleRidge": "Double ridge",
    "MaximumSpikeletPrimordia": "Spikelets formed",
    "FlagLeafAppearance": "Flag leaf",
    "HeadEmergence": "Heading",
    "Anthesis": "Flowering",
    "MaximumGrainLength": "Grain filling",
    "EndGrainFill": "End of grain fill",
    "HarvestRipe": "Harvest ripe",
}

# FAKE: guessed units, the CSV does not say. Confirm with Rares (APSIM report)
UNITS = {"lai": "m²/m²", "biomass": "g/m²", "grain_yield": "kg/ha", "paw": "mm/mm"}


@cache
def _rows() -> list[dict]:
    with CSV_PATH.open(newline="") as f:
        return [
            {
                "date": datetime.date.fromisoformat(r["clock_today"][:10]),
                "stage": r["wheat_phenology_current_stage_name"],
                "zadoks": float(r["wheat_phenology_zadok_stage"]),
                "lai": float(r["wheat_lai"]),
                "biomass": float(r["wheat_above_ground_wt"]),
                "grain_yield": float(r["yield"]),
                # Root zone is layers 3 to 5, as in S3-05
                "paw": fmean(float(r[f"soil_soilwater_paw({i})"]) for i in (3, 4, 5)),
            }
            for r in csv.DictReader(f)
        ]


def _row_on(date: datetime.date) -> dict:
    return next(r for r in _rows() if r["date"] == date)


def _stage_starts() -> list[dict]:
    starts = []
    for r in _rows():
        if not starts or starts[-1]["stage"] != r["stage"]:
            starts.append(r)
    return starts


def _stage(row: dict) -> Stage:
    return Stage(
        code=row["stage"], name=STAGE_NAMES[row["stage"]], zadoks=int(row["zadoks"])
    )


# FAKE: the CSV is one run, so it has one date per stage. This invents the spread
# an ensemble would give: none up to D (all runs share observed weather), then
# about 12% of the days ahead, skewed late. 0.12 and 1.3 are made up.
# The real ranges come from the ensemble summary in S3-05.
def _date_range(date: datetime.date) -> DateRange:
    days_ahead = (date - DEMO_DATE).days
    if days_ahead <= 0:
        return DateRange(min=date, median=date, max=date)
    spread = max(1, round(days_ahead * 0.12))
    return DateRange(
        min=date - datetime.timedelta(days=spread),
        median=date,
        max=date + datetime.timedelta(days=round(spread * 1.3)),
    )


# FAKE: same idea as _date_range for LAI, yield and PAW. No spread up to D, then
# 2% per day ahead, capped at 40%. The real 10th/50th/90th percentiles come from S3-05.
def _value_range(value: float, date: datetime.date) -> FloatRange:
    days_ahead = max(0, (date - DEMO_DATE).days)
    f = min(0.4, days_ahead * 0.02)
    return FloatRange(min=value * (1 - f), median=value, max=value * (1 + f * 0.8))


@router.get("/overview", response_model=Overview)
def stub_overview() -> Overview:
    today = _row_on(DEMO_DATE)
    starts = _stage_starts()
    current = next(s for s in reversed(starts) if s["date"] <= DEMO_DATE)
    upcoming = [s for s in starts if s["date"] > DEMO_DATE]
    harvest = _rows()[-1]

    return Overview(
        as_of=DEMO_DATE,
        # FAKE: example field. The sowing date is the CSV's, the rest is made up
        field=FieldInfo(
            id=FIELD_ID,
            name="North field",
            crop="wheat",
            area_ha=12.4,
            cell_id="10km_615_68",
            sowing=Sowing(
                status=SowingStatus.sown,
                date=starts[0]["date"],
                window_start=None,
                window_end=None,
            ),
        ),
        stage=StageInfo(
            updated_at=UPDATED_AT,
            stale=False,
            current=_stage(current),
            current_since=current["date"],
            upcoming=[
                UpcomingStage(**_stage(s).model_dump(), date=_date_range(s["date"]))
                for s in upcoming
            ],
        ),
        # Values come from the CSV. FAKE: ratings are hand-picked until S3-06
        metrics=Metrics(
            lai=Metric(
                updated_at=UPDATED_AT,
                stale=False,
                value=_value_range(today["lai"], DEMO_DATE),
                unit=UNITS["lai"],
                rating=Rating.poor,
            ),
            paw=Metric(
                updated_at=UPDATED_AT,
                stale=False,
                value=_value_range(today["paw"], DEMO_DATE),
                unit=UNITS["paw"],
                rating=Rating.good,
            ),
            predicted_yield=Metric(
                updated_at=UPDATED_AT,
                stale=False,
                value=_value_range(harvest["grain_yield"], harvest["date"]),
                unit=UNITS["grain_yield"],
                rating=Rating.fair,
            ),
        ),
        # FAKE: invented weather, the CSV has none. Real data from weather_daily (S2-03)
        weather=Weather(
            updated_at=UPDATED_AT,
            stale=False,
            date=DEMO_DATE,
            condition=WeatherCondition.partly_cloudy,
            temp_c=16.8,
            temp_min_c=10.2,
            temp_max_c=21.4,
            rain_mm=1.6,
            wind_ms=4.3,
            humidity_pct=72,
        ),
        # FAKE: one hand-written alert. Real alerts come from the rules in S4-04/S4-05
        alerts=Alerts(
            updated_at=UPDATED_AT,
            stale=False,
            items=[
                Alert(
                    id=1,
                    rule=AlertRule.sensitive_stage,
                    severity=AlertSeverity.warning,
                    title="Flag leaf expected within a week",
                    reason="Most runs reach flag leaf between 23 and 25 June.",
                    action="Check disease pressure and plan any fungicide now.",
                    uncertainty="Based on 10 weather years after 15 June.",
                    opened_on=DEMO_DATE,
                )
            ],
        ),
        # FAKE: hand-written text. Real text from the template (S4-09) or the LLM (S6-13)
        summary=HealthSummary(
            updated_at=UPDATED_AT,
            stale=False,
            text=(
                "The crop is behind on leaf growth but has enough soil water. "
                "Flag leaf is expected within a week."
            ),
            source=SummarySource.template,
        ),
        # FAKE: invented NDVI values, polygon and bounds, and no images yet.
        # Real data from Sentinel-2 (S5-06) and the consistency check (S5-07)
        satellite=Satellite(
            updated_at=UPDATED_AT,
            stale=False,
            observed_on=datetime.date(2025, 6, 12),
            mean_ndvi=0.62,
            consistency=ConsistencyStatus.on_track,
            weakest_area=WeakestArea(
                geometry=GeoJSONPolygon(
                    coordinates=[
                        [
                            (11.871, 55.461),
                            (11.874, 55.461),
                            (11.874, 55.463),
                            (11.871, 55.463),
                            (11.871, 55.461),
                        ]
                    ]
                ),
                mean_ndvi=0.41,
            ),
            legend=[
                NdviLegendEntry(
                    min=-1.0, max=0.2, color="#a50026", label="Bare or water"
                ),
                NdviLegendEntry(min=0.2, max=0.4, color="#f46d43", label="Sparse"),
                NdviLegendEntry(min=0.4, max=0.6, color="#fee08b", label="Moderate"),
                NdviLegendEntry(min=0.6, max=0.8, color="#a6d96a", label="Dense"),
                NdviLegendEntry(min=0.8, max=1.0, color="#1a9850", label="Very dense"),
            ],
            ndvi_image_url=None,
            true_color_image_url=None,
            image_bounds=[(55.458, 11.866), (55.466, 11.880)],
        ),
    )


@router.get("/timeline", response_model=Timeline)
def stub_timeline() -> Timeline:
    starts = _stage_starts()
    current = next(s for s in reversed(starts) if s["date"] <= DEMO_DATE)

    def status(s: dict) -> StageStatus:
        if s is current:
            return StageStatus.current
        return StageStatus.past if s["date"] < DEMO_DATE else StageStatus.upcoming

    return Timeline(
        updated_at=UPDATED_AT,
        stale=False,
        as_of=DEMO_DATE,
        field_id=FIELD_ID,
        stages=[
            TimelineStage(
                **_stage(s).model_dump(),
                note=None,  # Written in S2-15
                status=status(s),
                basis=(
                    StageBasis.simulated_observed
                    if s["date"] <= DEMO_DATE
                    else StageBasis.predicted
                ),
                start=_date_range(s["date"]),
                # FAKE: assumes every run reaches every stage
                runs_reached=RUNS_TOTAL,
                runs_total=RUNS_TOTAL,
            )
            for s in starts
        ],
    )


@router.get("/timeline/details", response_model=TimelineDetails)
def stub_timeline_details() -> TimelineDetails:
    return TimelineDetails(
        updated_at=UPDATED_AT,
        stale=False,
        as_of=DEMO_DATE,
        field_id=FIELD_ID,
        units=UNITS,
        days=[
            TimelineDay(
                date=r["date"],
                stage_code=r["stage"],
                zadoks=r["zadoks"],
                lai=_value_range(r["lai"], r["date"]),
                biomass=_value_range(r["biomass"], r["date"]),
                grain_yield=_value_range(r["grain_yield"], r["date"]),
                paw=_value_range(r["paw"], r["date"]),
            )
            for r in _rows()
        ],
    )
