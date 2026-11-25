"""The worker: runs queued simulation jobs with the sim service (S4-31).

A job is all simulation_runs rows with the same job_id, one per weather season
(see api.jobs.queue). The worker takes the oldest queued job, sends all of its
seasons to the sim service in one request, and stores the daily rows. Pages
only read the tables, so they never wait for APSIM.

Run it next to the API, from apps/api:

    uv run python -m api.jobs.worker

Several workers can run at the same time: each one locks the runs it takes
with SELECT ... FOR UPDATE SKIP LOCKED, so no job runs twice.

Weather: each season is the stored DMI weather of that season's dates, 1
September to 31 August. That is the observed 2025/26 season for a one-run job.
The ensemble weather (observed weather up to the demo date, then a past season)
replaces season_weather in S5-31.
"""

import datetime as dt
import logging
import os
import time
import uuid
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from geoalchemy2.shape import to_shape
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.models.simulation import RunStatus, SimulationDaily, SimulationRun
from api.weather.store import MET_COLUMNS, dates_without_values, stored_rows

logger = logging.getLogger(__name__)

SIM_URL = os.getenv("SIM_URL", "http://localhost:8001")
# One ensemble of 10 seasons takes about 5 s. APSIM's own limit per run is
# 300 s, so this only stops the worker from waiting forever.
SIM_TIMEOUT_SECONDS = 330
# How long the worker sleeps when no job is queued
POLL_SECONDS = 2.0
# A run that is still running after this was taken by a worker that stopped
STUCK_AFTER = dt.timedelta(minutes=15)
# A stuck run is queued again once. The second time it fails.
MAX_ATTEMPTS = 2
# How many of the oldest queued jobs a worker tries before it gives up
CANDIDATE_JOBS = 10
# Errors are stored in the run, so keep them short enough to read on a page
MAX_ERROR_LENGTH = 1000

# The response columns that simulation_daily stores, in the sim's names
DAILY_COLUMNS = (
    "stage",
    "zadoks",
    "lai",
    "biomass",
    "biomass_n",
    "grain_yield",
    "grain_protein",
    "grain_size",
    "grain_number",
    "grain_wt",
    "grain_n",
    "sw",
    "paw",
)

# Takes the request body of POST /sim/simulate and returns the response body.
# Tests pass a fake, so they never need the sim service.
SimClient = Callable[[dict[str, Any]], dict[str, Any]]


class JobError(Exception):
    """The job cannot run. Every run of the job fails with this message."""


def http_sim_client(body: dict[str, Any]) -> dict[str, Any]:
    """Call POST /sim/simulate of the sim service."""
    try:
        response = httpx.post(
            f"{SIM_URL}/sim/simulate", json=body, timeout=SIM_TIMEOUT_SECONDS
        )
    except httpx.HTTPError as error:
        raise JobError(f"The sim service did not answer: {error}") from error
    if response.status_code != 200:
        raise JobError(
            f"The sim service answered {response.status_code}: {response.text[:500]}"
        )
    return response.json()


# Taking a job


def requeue_stuck_runs(db: Session, now: dt.datetime | None = None) -> int:
    """Queue stuck runs again, or fail them after MAX_ATTEMPTS. Returns how many.

    A run is stuck when it is still running STUCK_AFTER after a worker took it,
    for example because the worker container stopped. Does not commit.
    """
    now = now or dt.datetime.now(dt.UTC)
    stuck = db.scalars(
        select(SimulationRun)
        .where(
            SimulationRun.status == RunStatus.running,
            SimulationRun.started_at < now - STUCK_AFTER,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for run in stuck:
        if run.attempts < MAX_ATTEMPTS:
            run.status = RunStatus.queued
            run.started_at = None
        else:
            run.status = RunStatus.failed
            run.error = (
                f"The run was still running after {STUCK_AFTER} twice, "
                "so it was stopped."
            )
            run.finished_at = now
    if stuck:
        logger.warning("Found %d stuck runs", len(stuck))
    return len(stuck)


def take_job(db: Session) -> list[SimulationRun]:
    """Take the oldest queued job: set its queued runs to running and return them.

    Returns an empty list when no job is queued. Does not commit: commit right
    away, so other workers see the runs as running.

    Row locks alone could split a job: when one worker has locked the first run
    of a job, SKIP LOCKED lets a second worker take the other runs. So a worker
    first takes a lock on the whole job (a Postgres advisory lock, which ends
    with the transaction) and skips jobs that another worker holds.
    """
    candidates = db.scalars(
        select(SimulationRun.job_id)
        .where(SimulationRun.status == RunStatus.queued)
        .group_by(SimulationRun.job_id)
        .order_by(func.min(SimulationRun.created_at), func.min(SimulationRun.id))
        .limit(CANDIDATE_JOBS)
    ).all()
    for job_id in candidates:
        if not db.scalar(select(func.pg_try_advisory_xact_lock(job_lock_key(job_id)))):
            continue  # another worker is taking this job
        runs = db.scalars(
            select(SimulationRun)
            .where(
                SimulationRun.job_id == job_id,
                SimulationRun.status == RunStatus.queued,
            )
            .order_by(SimulationRun.id)
            .with_for_update()
        ).all()
        if not runs:
            continue  # another worker took it before this worker got the lock
        for run in runs:
            run.status = RunStatus.running
            run.started_at = func.now()
            run.attempts += 1
            run.error = None
        db.flush()
        return list(runs)
    return []


def job_lock_key(job_id: uuid.UUID) -> int:
    """Return the advisory lock key of a job: the first 8 bytes of its id."""
    return int.from_bytes(job_id.bytes[:8], "big", signed=True)


# Running a job


def run_job(
    db: Session,
    runs: Sequence[SimulationRun],
    sim: SimClient,
    taken: dict[int, int] | None = None,
) -> None:
    """Run the taken runs of one job and store the results. Does not commit.

    A failed member fails only its own run. When the whole job cannot run (no
    field, missing weather, the sim service is down), every run fails with the
    same message.

    `taken` is the attempts value of each run when this worker took it. Results
    are only written for runs that this worker still owns (see owned_runs).
    """
    taken = taken if taken is not None else {run.id: run.attempts for run in runs}
    try:
        body = simulate_request(db, runs)
        response = sim(body)
    except JobError as error:
        fail_runs(owned_runs(db, taken), str(error))
        return

    results = {member["season"]: member for member in response["members"]}
    for run in owned_runs(db, taken):
        result = results.get(run.season)
        if result is None:
            fail_runs([run], "The sim service returned no result for this season.")
        elif result["status"] != "ok":
            fail_runs([run], result["error"] or "The sim service gave no reason.")
        else:
            store_result(db, run, result)


def owned_runs(db: Session, taken: dict[int, int]) -> list[SimulationRun]:
    """Lock and return the runs that this worker still owns.

    A run is no longer this worker's when another worker took it after it
    counted as stuck (its attempts changed), or when it is gone because the
    field was deleted. Those runs are left alone. The lock lasts until the
    commit, so the run cannot change or be deleted while the results are written.
    """
    runs = db.scalars(
        select(SimulationRun)
        .where(
            SimulationRun.id.in_(taken),
            SimulationRun.status == RunStatus.running,
        )
        .order_by(SimulationRun.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    owned = [run for run in runs if run.attempts == taken[run.id]]
    if len(owned) < len(taken):
        logger.warning(
            "%d of %d runs were taken over or deleted, so their results are dropped",
            len(taken) - len(owned),
            len(taken),
        )
    return owned


def simulate_request(db: Session, runs: Sequence[SimulationRun]) -> dict[str, Any]:
    """Build the POST /sim/simulate body for the runs of one job."""
    field = db.get(Field, runs[0].field_id)
    if field is None:
        raise JobError("The field of this job no longer exists.")
    if field.cell_id is None:
        raise JobError("The field has no DMI weather cell.")

    point = to_shape(field.geom).representative_point()
    body: dict[str, Any] = {
        "latitude": round(point.y, 6),
        "longitude": round(point.x, 6),
        "soil_profile": field.soil_profile,
        "members": [
            {"season": run.season, "met": season_weather(db, field.cell_id, run.season)}
            for run in runs
        ],
    }
    body.update(sowing(runs[0].inputs or {}, field))
    return body


def sowing(inputs: dict[str, Any], field: Field) -> dict[str, Any]:
    """Return the sowing date or window of the job.

    The job inputs win, because they are what the job was queued with. A job
    without them uses the field's current values.
    """
    if inputs.get("sowing_date"):
        return {"sowing_date": inputs["sowing_date"]}
    if inputs.get("sowing_window"):
        return {"sowing_window": inputs["sowing_window"]}
    if field.sowing_date is not None:
        return {"sowing_date": field.sowing_date.isoformat()}
    return {
        "sowing_window": {
            "start": field.sowing_window_start.isoformat(),
            "end": field.sowing_window_end.isoformat(),
        }
    }


def season_dates(season: str) -> tuple[dt.date, dt.date]:
    """Return the first and last day of a season, for example "2025/26"."""
    try:
        first_year = int(season.split("/")[0])
    except ValueError as error:
        raise JobError(f"Not a season: {season!r}") from error
    return dt.date(first_year, 9, 1), dt.date(first_year + 1, 8, 31)


def season_weather(db: Session, cell_id: str, season: str) -> list[dict[str, Any]]:
    """Return the stored weather of one season as the sim's weather rows.

    A single missing day is sent as None, and the sim fills it. Raises JobError
    when the season has no stored weather at all, because then the weather was
    never loaded (POST /fields loads it in S4-32).
    """
    start, end = season_dates(season)
    rows = stored_rows(db, cell_id, start, end)
    missing = dates_without_values(rows, MET_COLUMNS, start, end)
    if len(missing) == (end - start).days + 1:
        raise JobError(
            f"No weather is stored for {cell_id} from {start} to {end}. "
            "Load it with api.weather.store.fetch_missing."
        )
    return [
        {"date": row.date.isoformat(), **{c: getattr(row, c) for c in MET_COLUMNS}}
        for row in rows
    ]


def store_result(db: Session, run: SimulationRun, result: dict[str, Any]) -> None:
    """Store the daily rows of one member and mark its run done."""
    db.execute(
        insert(SimulationDaily),
        [
            {
                "run_id": run.id,
                "date": dt.date.fromisoformat(day["date"]),
                **{column: day[column] for column in DAILY_COLUMNS},
            }
            for day in result["daily"]
        ],
    )
    run.status = RunStatus.done
    run.sowing_date = dt.date.fromisoformat(result["sowing_date"])
    run.runtime_ms = result["runtime_ms"]
    run.error = None
    run.finished_at = func.now()


def fail_runs(runs: Sequence[SimulationRun], message: str) -> None:
    for run in runs:
        run.status = RunStatus.failed
        run.error = message[:MAX_ERROR_LENGTH]
        run.finished_at = func.now()


# The loop


def work_once(db: Session, sim: SimClient = http_sim_client) -> uuid.UUID | None:
    """Run the oldest queued job, if there is one, and return its job_id.

    Commits twice: once after taking the job, so other workers skip it, and
    once with the results. The sim call happens between the two, and no row is
    locked while APSIM runs.
    """
    requeue_stuck_runs(db)
    runs = take_job(db)
    db.commit()
    if not runs:
        return None

    job_id = runs[0].job_id
    # Plain values, so they still work if the rows are deleted during the job
    taken = {run.id: run.attempts for run in runs}
    logger.info("Running job %s with %d runs", job_id, len(runs))
    started = time.perf_counter()
    try:
        run_job(db, runs, sim, taken)
        db.commit()
    except Exception as error:
        # Anything unexpected fails the job instead of leaving it running until
        # it counts as stuck
        logger.exception("Job %s failed", job_id)
        db.rollback()
        try:
            message = f"The worker failed: {type(error).__name__}: {error}"
            fail_runs(owned_runs(db, taken), message)
            db.commit()
        except Exception:
            # The database itself has a problem. The runs stay running and
            # count as stuck later.
            logger.exception("Could not mark job %s as failed", job_id)
            db.rollback()
    logger.info("Job %s finished in %.1f s", job_id, time.perf_counter() - started)
    return job_id


def work_safely(
    session_factory: Callable[[], Session], sim: SimClient = http_sim_client
) -> uuid.UUID | None:
    """Run work_once in a new session. Any error is logged, never raised.

    The worker must keep running when the database is briefly down or a job
    fails in a way nobody foresaw, otherwise every later job stays queued.
    """
    try:
        with session_factory() as db:
            return work_once(db, sim)
    except Exception:
        logger.exception("The worker loop failed, trying again")
        return None


def main() -> None:
    from api.db.session import session_local

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger.info("Worker started, sim service at %s", SIM_URL)
    while True:
        if work_safely(session_local) is None:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
