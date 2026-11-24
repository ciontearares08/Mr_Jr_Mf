"""The overview and timeline of a field, from its newest finished job (S4-33).

These routes replace /stub/overview, /stub/timeline and /stub/timeline/details
and return the same models. Today is the demo date D from app_settings.

Parts that do not exist yet are empty: no ratings (S4-37), no alerts (S6-31),
no summary (S9-05) and no satellite data (S6-37).
"""

import datetime as dt

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.auth.permissions import require_role
from api.db.models.field import Field
from api.db.models.field_member import FieldRole
from api.db.models.weather_daily import WeatherDaily
from api.results import (
    UNITS,
    FinishedJob,
    StageDef,
    daily_series,
    date_range,
    farmer_stages,
    float_range,
    most_common,
    newest_finished_job,
    range_on,
    stage_dates,
    stage_on,
)
from api.routers.auth import CurrentUser, DbSession
from api.schemas.common import Stage
from api.schemas.overview import (
    Alerts,
    FieldInfo,
    Metric,
    Metrics,
    Overview,
    Sowing,
    SowingStatus,
    StageInfo,
    UpcomingStage,
    Weather,
)
from api.schemas.timeline import (
    StageBasis,
    StageStatus,
    Timeline,
    TimelineDay,
    TimelineDetails,
    TimelineStage,
)
from api.settings import get_demo_date

router = APIRouter(prefix="/fields", tags=["fields"])


def finished_job_or_409(db: DbSession, field_id: int) -> FinishedJob:
    job = newest_finished_job(db, field_id)
    if job is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This field has no finished simulation yet. Try again when its first "
            "run is done.",
        )
    return job


def is_stale(job: FinishedJob, demo_date: dt.date) -> bool:
    """A job is stale when it was run for another demo date than today's."""
    return job.demo_date is not None and job.demo_date != demo_date


def stage_model(stage: StageDef) -> Stage:
    return Stage(code=stage.code, name=stage.name, zadoks=stage.zadoks)


class StageStarts:
    """The start dates of the farmer stages over all runs of a job."""

    def __init__(self, job: FinishedJob) -> None:
        per_run = [stage_dates(job.days[run.id]) for run in job.runs]
        self.runs_total = len(per_run)
        self.stages: list[tuple[StageDef, list[dt.date]]] = []
        for stage in farmer_stages():
            dates = [dates[stage.code] for dates in per_run if stage.code in dates]
            if dates:
                self.stages.append((stage, dates))

    def current(self, demo_date: dt.date) -> tuple[StageDef, dt.date]:
        """Return the stage the crop is in on demo_date, and its median start.

        Before sowing, the crop is in no stage yet, so this returns the first
        stage (Sowing) with its date in the future.
        """
        current = self.stages[0]
        for stage, dates in self.stages:
            if date_range(dates).median <= demo_date:
                current = (stage, dates)
        stage, dates = current
        return stage, date_range(dates).median


@router.get("/{field_id}/overview", response_model=Overview)
def field_overview(field_id: int, user: CurrentUser, db: DbSession) -> Overview:
    field, _ = require_role(field_id, user, db, FieldRole.viewer)
    job = finished_job_or_409(db, field_id)
    demo_date = get_demo_date(db)
    stale = is_stale(job, demo_date)
    updated_at = job.finished_at

    starts = StageStarts(job)
    current, current_since = starts.current(demo_date)
    upcoming = [
        UpcomingStage(**stage_model(stage).model_dump(), date=date_range(dates))
        for stage, dates in starts.stages
        if date_range(dates).median > demo_date
    ]

    series = [daily_series(job.days[run.id]) for run in job.runs]

    def metric(column: str, date: dt.date | None = None) -> Metric:
        if date is None:
            # The value at harvest: the last day of each run
            values = [
                s[-1].grain_yield for s in series if s and s[-1].grain_yield is not None
            ]
            value = float_range(values) if values else None
        else:
            value = range_on(series, date, column)
        return Metric(
            updated_at=updated_at,
            stale=stale,
            # A run without any value gives 0, so the card still renders
            value=value or float_range([0.0]),
            unit=UNITS[column],
            rating=None,
        )

    return Overview(
        as_of=demo_date,
        field=FieldInfo(
            id=field.id,
            name=field.name,
            crop="wheat",
            area_ha=field.area_ha,
            cell_id=field.cell_id,
            sowing=sowing(field, job, demo_date),
        ),
        stage=StageInfo(
            updated_at=updated_at,
            stale=stale,
            current=stage_model(current),
            current_since=current_since,
            upcoming=upcoming,
        ),
        metrics=Metrics(
            lai=metric("lai", demo_date),
            paw=metric("paw", demo_date),
            predicted_yield=metric("grain_yield"),
        ),
        weather=weather_on(db, field.cell_id, demo_date),
        alerts=Alerts(updated_at=updated_at, stale=stale, items=[]),
        summary=None,
        satellite=None,
    )


def sowing(field: Field, job: FinishedJob, demo_date: dt.date) -> Sowing:
    """The sowing card: the day APSIM sowed (the median over the runs)."""
    dates = [run.sowing_date for run in job.runs if run.sowing_date is not None]
    date = date_range(dates).median if dates else field.sowing_date
    return Sowing(
        status=(
            SowingStatus.sown
            if date is not None and date <= demo_date
            else SowingStatus.planned
        ),
        date=date,
        window_start=field.sowing_window_start,
        window_end=field.sowing_window_end,
    )


def weather_on(db: DbSession, cell_id: str | None, date: dt.date) -> Weather | None:
    """The weather card: DMI's stored day for the field's cell."""
    if cell_id is None:
        return None
    row = db.scalar(
        select(WeatherDaily).where(
            WeatherDaily.cell_id == cell_id, WeatherDaily.date == date
        )
    )
    if row is None or None in (row.maxt, row.mint, row.rain):
        return None
    return Weather(
        updated_at=row.fetched_at,
        stale=False,
        date=row.date,
        condition=None,
        temp_c=round((row.maxt + row.mint) / 2, 1),
        temp_min_c=row.mint,
        temp_max_c=row.maxt,
        rain_mm=row.rain,
        wind_ms=row.wind_speed,
        humidity_pct=row.rh,
    )


@router.get("/{field_id}/timeline", response_model=Timeline)
def field_timeline(field_id: int, user: CurrentUser, db: DbSession) -> Timeline:
    require_role(field_id, user, db, FieldRole.viewer)
    job = finished_job_or_409(db, field_id)
    demo_date = get_demo_date(db)

    starts = StageStarts(job)
    current, _ = starts.current(demo_date)

    def stage_status(stage: StageDef, start: dt.date) -> StageStatus:
        if stage == current and start <= demo_date:
            return StageStatus.current
        return StageStatus.past if start <= demo_date else StageStatus.upcoming

    stages = []
    for stage, dates in starts.stages:
        start = date_range(dates)
        every_run_before_d = len(dates) == starts.runs_total and start.max <= demo_date
        stages.append(
            TimelineStage(
                **stage_model(stage).model_dump(),
                note=stage.note,
                status=stage_status(stage, start.median),
                basis=(
                    StageBasis.simulated_observed
                    if every_run_before_d
                    else StageBasis.predicted
                ),
                start=start,
                runs_reached=len(dates),
                runs_total=starts.runs_total,
            )
        )

    return Timeline(
        updated_at=job.finished_at,
        stale=is_stale(job, demo_date),
        as_of=demo_date,
        field_id=field_id,
        stages=stages,
    )


@router.get("/{field_id}/timeline/details", response_model=TimelineDetails)
def field_timeline_details(
    field_id: int, user: CurrentUser, db: DbSession
) -> TimelineDetails:
    require_role(field_id, user, db, FieldRole.viewer)
    job = finished_job_or_409(db, field_id)
    demo_date = get_demo_date(db)

    rows = [job.days[run.id] for run in job.runs]
    series = [daily_series(run_rows) for run_rows in rows]
    dates = sorted({day.date for run_series in series for day in run_series})

    days = []
    for date in dates:
        stages = [stage for r in rows if (stage := stage_on(r, date)) is not None]
        zadoks = range_on(series, date, "zadoks")
        values = {column: range_on(series, date, column) for column in UNITS}
        if not stages or zadoks is None or None in values.values():
            continue  # a day without data in any run is left out
        days.append(
            TimelineDay(
                date=date,
                stage_code=most_common(stages),
                zadoks=zadoks.median,
                **values,
            )
        )

    return TimelineDetails(
        updated_at=job.finished_at,
        stale=is_stale(job, demo_date),
        as_of=demo_date,
        field_id=field_id,
        units=UNITS,
        days=days,
    )
