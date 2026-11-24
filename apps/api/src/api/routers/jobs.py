"""Job status and run history (S4-32).

A job is all simulation_runs rows with one job_id (see api.jobs.queue). These
routes sum the runs up, so the web app can poll a new field's first job and
show the past runs on the technical page.
"""

import datetime
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from api.auth.permissions import require_role
from api.db.models.field_member import FieldRole
from api.db.models.simulation import RunStatus, SimulationRun
from api.routers.auth import CurrentUser, DbSession
from api.schemas.job import JobRead, JobStatus, JobSummary

router = APIRouter(tags=["jobs"])

# How many jobs the run history shows
HISTORY_LENGTH = 20


def job_status(runs: Sequence[SimulationRun]) -> JobStatus:
    statuses = {run.status for run in runs}
    if RunStatus.running in statuses:
        return JobStatus.running
    if RunStatus.queued in statuses:
        return JobStatus.queued
    if statuses == {RunStatus.done}:
        return JobStatus.done
    return JobStatus.failed


def finished_at(runs: Sequence[SimulationRun]) -> datetime.datetime | None:
    if any(run.status in (RunStatus.queued, RunStatus.running) for run in runs):
        return None
    times = [run.finished_at for run in runs if run.finished_at is not None]
    return max(times) if times else None


def demo_date_of(runs: Sequence[SimulationRun]) -> datetime.date | None:
    value = (runs[0].inputs or {}).get("demo_date")
    return datetime.date.fromisoformat(value) if value else None


def runs_of_jobs(
    db: DbSession, job_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[SimulationRun]]:
    runs: dict[uuid.UUID, list[SimulationRun]] = {job_id: [] for job_id in job_ids}
    for run in db.scalars(
        select(SimulationRun)
        .where(SimulationRun.job_id.in_(job_ids))
        .order_by(SimulationRun.id)
    ):
        runs[run.job_id].append(run)
    return runs


@router.get("/jobs/{job_id}", response_model=JobRead)
def read_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobRead:
    runs = runs_of_jobs(db, [job_id])[job_id]
    if not runs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    # Non-members get the same 404 as an unknown job, so job ids reveal nothing
    try:
        require_role(runs[0].field_id, user, db, FieldRole.viewer)
    except HTTPException as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found") from error

    errors = [run.error for run in runs if run.status == RunStatus.failed and run.error]
    return JobRead(
        id=job_id,
        field_id=runs[0].field_id,
        status=job_status(runs),
        error=errors[0] if errors else None,
        created_at=min(run.created_at for run in runs),
        finished_at=finished_at(runs),
    )


@router.get("/fields/{field_id}/runs", response_model=list[JobSummary])
def field_runs(field_id: int, user: CurrentUser, db: DbSession) -> list[JobSummary]:
    """The field's last 20 jobs, newest first."""
    require_role(field_id, user, db, FieldRole.viewer)
    job_ids = db.scalars(
        select(SimulationRun.job_id)
        .where(SimulationRun.field_id == field_id)
        .group_by(SimulationRun.job_id)
        .order_by(func.min(SimulationRun.created_at).desc())
        .limit(HISTORY_LENGTH)
    ).all()

    summaries = []
    for job_id, runs in runs_of_jobs(db, job_ids).items():
        runtimes = [run.runtime_ms for run in runs if run.runtime_ms is not None]
        summaries.append(
            JobSummary(
                id=job_id,
                status=job_status(runs),
                demo_date=demo_date_of(runs),
                n_runs=len(runs),
                # The runs of a job share one APSIM run, so take the longest
                runtime_ms=max(runtimes) if runtimes else None,
                created_at=min(run.created_at for run in runs),
                finished_at=finished_at(runs),
            )
        )
    return summaries
