import datetime
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class JobRead(BaseModel):
    """One simulation job: all runs of a field with the same inputs."""

    id: uuid.UUID
    field_id: int
    status: JobStatus = Field(
        description=(
            "running while any run is running, queued while any run waits, done "
            "when every run is done, otherwise failed"
        )
    )
    error: str | None = Field(
        description="Why the job failed, from its first failed run"
    )
    created_at: datetime.datetime
    finished_at: datetime.datetime | None = Field(
        description="When the last run finished, None while the job is not finished"
    )


class JobSummary(BaseModel):
    """One row of a field's run history."""

    id: uuid.UUID
    status: JobStatus
    demo_date: datetime.date | None = Field(description="The demo date the job ran for")
    n_runs: int = Field(description="How many weather seasons the job runs")
    runtime_ms: int | None = Field(
        description="How long the APSIM run took, None until it finished"
    )
    created_at: datetime.datetime
    finished_at: datetime.datetime | None
