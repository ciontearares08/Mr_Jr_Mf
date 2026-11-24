"""Read the results of a field's newest finished job (S4-33).

The worker stores one simulation_daily row per day for each run of a job. The
overview and timeline routes read them through these functions. A job has one
run until the ensemble arrives (S5-31), and the functions already work for N
runs: every value becomes a range (min, median, max) over the runs. With one
run, min, median and max are the same.

Two functions work on one run:

- stage_dates(rows): the first day of each stage.
- daily_series(rows): LAI, biomass, yield and root zone soil water per day.
"""

import datetime as dt
import json
import statistics
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.models.simulation import RunStatus, SimulationDaily, SimulationRun
from api.schemas.common import DateRange, FloatRange

# The stage list of the sim service, with the farmer names and notes (S3-08, S3-13)
STAGES_PATH = Path(__file__).resolve().parents[3] / "sim" / "models" / "stages.json"

# The root zone for the soil water metric: layers 1 to 5, 0 to 120 cm of the
# 7 layers in apps/sim/models/README.md. Winter
# wheat roots reach about 1 to 1.5 m. Check this with the alert rules (S5-38)
# before they use it.
ROOT_ZONE_LAYERS = 5

# The stage that starts with the first tiller, found from the stem count
TILLERING = "Tillering"

UNITS = {"lai": "m²/m²", "biomass": "g/m²", "grain_yield": "kg/ha", "paw": "mm"}


@dataclass(frozen=True)
class StageDef:
    code: str
    name: str
    zadoks: int
    # The APSIM stage that starts it. None for a stage that only has a Zadoks
    # code, for example Tillering: it starts on the first day at that code.
    apsim_stage: str | None
    show_farmer: bool
    note: str | None


@cache
def stage_defs() -> tuple[StageDef, ...]:
    """Return the stages of stages.json in season order."""
    stages = json.loads(STAGES_PATH.read_text(encoding="utf-8"))
    return tuple(
        StageDef(
            code=s["stage_name"],
            name=s["farmer_name"],
            zadoks=int(s["zadoks"]),
            apsim_stage=s["apsim_stage"],
            show_farmer=s["show_farmer"],
            note=s.get("note"),
        )
        for s in stages
    )


@cache
def farmer_stages() -> tuple[StageDef, ...]:
    """Return the stages the app shows to a farmer, in season order."""
    return tuple(stage for stage in stage_defs() if stage.show_farmer)


@dataclass(frozen=True)
class DayValues:
    date: dt.date
    zadoks: float | None
    lai: float | None
    biomass: float | None
    grain_yield: float | None
    # Plant available water in the root zone, mm
    paw: float | None


@dataclass(frozen=True)
class FinishedJob:
    job_id: uuid.UUID
    runs: list[SimulationRun]
    # The daily rows of each run, by run id, oldest first
    days: dict[int, list[SimulationDaily]]
    finished_at: dt.datetime
    # The demo date the job was queued for, if its inputs have one
    demo_date: dt.date | None


def newest_finished_job(db: Session, field_id: int) -> FinishedJob | None:
    """Return the newest job of the field whose runs are all done, or None."""
    job_id = db.scalar(
        select(SimulationRun.job_id)
        .where(SimulationRun.field_id == field_id)
        .group_by(SimulationRun.job_id)
        .having(func.bool_and(SimulationRun.status == RunStatus.done))
        .order_by(func.max(SimulationRun.created_at).desc())
        .limit(1)
    )
    if job_id is None:
        return None

    runs = list(
        db.scalars(
            select(SimulationRun)
            .where(SimulationRun.job_id == job_id)
            .order_by(SimulationRun.id)
        )
    )
    days: dict[int, list[SimulationDaily]] = {run.id: [] for run in runs}
    for day in db.scalars(
        select(SimulationDaily)
        .where(SimulationDaily.run_id.in_(days))
        .order_by(SimulationDaily.run_id, SimulationDaily.date)
    ):
        days[day.run_id].append(day)

    finished = [run.finished_at or run.created_at for run in runs]
    demo_date = (runs[0].inputs or {}).get("demo_date")
    return FinishedJob(
        job_id=job_id,
        runs=runs,
        days=days,
        finished_at=max(finished),
        demo_date=dt.date.fromisoformat(demo_date) if demo_date else None,
    )


# One run


def stage_dates(rows: Sequence[SimulationDaily]) -> dict[str, dt.date]:
    """Return the first day of each stage of one run, by stage code.

    APSIM names a stage only on the day it starts. The stages that APSIM does
    not have (apsim_stage None in stages.json) start on the first day with at
    least their Zadoks code. A stage the run did not reach is left out.

    Tillering starts on the first day with more stems than on the first day.
    APSIM's Zadoks code cannot show it: until stem extension, the code is 10
    plus the main stem leaf number, so it passes 21 in April without tillering
    (see apps/sim/models/README.md). A run without stem counts has no Tillering.

    APSIM's Zadoks code can also jump over a stage: it goes from about 20.5 to
    31 in one day at stem extension. A stage whose first day already has the
    Zadoks code of the next stage is left out for that reason.
    """
    started: dict[str, dt.date] = {}
    for row in rows:
        if row.stage and row.stage not in started:
            started[row.stage] = row.date

    dates = {}
    for stage in stage_defs():
        if stage.apsim_stage is not None:
            date = started.get(stage.apsim_stage)
        elif stage.code == TILLERING:
            date = tillering_start(rows)
        else:
            first = next(
                (r for r in rows if r.zadoks is not None and r.zadoks >= stage.zadoks),
                None,
            )
            next_zadoks = next_stage_zadoks(stage)
            jumped_over = (
                first is not None
                and next_zadoks is not None
                and first.zadoks >= next_zadoks
            )
            date = None if first is None or jumped_over else first.date
        if date is not None:
            dates[stage.code] = date
    return dates


def daily_series(rows: Sequence[SimulationDaily]) -> list[DayValues]:
    """Return the values the pages show for each day of one run."""
    return [
        DayValues(
            date=row.date,
            zadoks=row.zadoks,
            lai=row.lai,
            biomass=row.biomass,
            grain_yield=row.grain_yield,
            paw=root_zone_paw(row.paw),
        )
        for row in rows
    ]


def tillering_start(rows: Sequence[SimulationDaily]) -> dt.date | None:
    """Return the first day with more stems than on the first day of the run."""
    if not rows or rows[0].stems is None:
        return None
    return next(
        (r.date for r in rows if r.stems is not None and r.stems > rows[0].stems),
        None,
    )


def next_stage_zadoks(stage: StageDef) -> int | None:
    """Return the Zadoks code of the stage after this one, or None for the last."""
    later = [other.zadoks for other in stage_defs() if other.zadoks > stage.zadoks]
    return min(later) if later else None


def root_zone_paw(layers: Sequence[float | None] | None) -> float | None:
    """Return the plant available water of the root zone, in mm.

    The sim reports each layer in mm (APSIM's PAWmm, PR #50), so the root zone
    is the sum of its layers.
    """
    if not layers or len(layers) < ROOT_ZONE_LAYERS:
        return None
    values = layers[:ROOT_ZONE_LAYERS]
    if any(value is None for value in values):
        return None
    return sum(values)


def stage_on(rows: Sequence[SimulationDaily], date: dt.date) -> str | None:
    """Return the APSIM stage of one run on a date: the last stage started by then."""
    stage = None
    for row in rows:
        if row.date > date:
            break
        if row.stage:
            stage = row.stage
    return stage


# All runs of a job


def date_range(dates: Sequence[dt.date]) -> DateRange:
    ordered = sorted(dates)
    return DateRange(
        min=ordered[0], median=ordered[(len(ordered) - 1) // 2], max=ordered[-1]
    )


def float_range(values: Sequence[float]) -> FloatRange:
    return FloatRange(
        min=min(values), median=statistics.median(values), max=max(values)
    )


def value_on(series: Sequence[DayValues], date: dt.date, column: str) -> float | None:
    """Return a value of one run on a date.

    Before the run's first day, the crop is not sown yet, so LAI, biomass and
    yield are 0 and the soil water is the first simulated day. After its last
    day (harvest ripe), the values stay at the last day.
    """
    if not series:
        return None
    if date < series[0].date:
        return 0.0 if column != "paw" else series[0].paw
    for day in reversed(series):
        if day.date <= date:
            return getattr(day, column)
    return None


def range_on(
    all_series: Sequence[Sequence[DayValues]], date: dt.date, column: str
) -> FloatRange | None:
    """Return the range of a value over the runs on a date, or None without data."""
    values = [value_on(series, date, column) for series in all_series]
    known = [value for value in values if value is not None]
    return float_range(known) if known else None


def most_common(values: Sequence[str]) -> str:
    """Return the most common value. A tie goes to the first one seen."""
    return Counter(values).most_common(1)[0][0]
