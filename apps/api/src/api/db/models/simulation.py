"""The simulation runs of an ensemble job and their daily results.

One job runs the same field inputs with N past weather seasons. Each season is
one row in simulation_runs, and all rows of a job share its job_id. The worker
(S4-31) runs the queued rows and writes one simulation_daily row per day.
Pages read these tables and never wait for APSIM.
"""

import datetime
import enum
import uuid

from sqlalchemy import (
    ARRAY,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    # The worker takes the oldest queued run
    __table_args__ = (
        Index("ix_simulation_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(index=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )
    # The past weather season after the demo date, for example "2018/19".
    season: Mapped[str] = mapped_column(String(7))
    # A hash of everything the job depends on, so a finished job with the same
    # inputs is not run again (see api.jobs.queue).
    inputs_hash: Mapped[str] = mapped_column(String(64))
    # The inputs that queue_job got, as JSON. The worker reads the sowing date
    # or window from here, and the run history shows the demo date.
    inputs: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), default=RunStatus.queued
    )
    # The day APSIM sowed. It differs between runs when the field has a window.
    sowing_date: Mapped[datetime.date | None] = mapped_column(Date)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    # How often a worker took this run. A stuck run is queued again only once.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class SimulationDaily(Base):
    __tablename__ = "simulation_daily"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    stage: Mapped[str | None] = mapped_column(String(50))
    zadoks: Mapped[float | None] = mapped_column(Float)
    lai: Mapped[float | None] = mapped_column(Float)
    biomass: Mapped[float | None] = mapped_column(Float)
    biomass_n: Mapped[float | None] = mapped_column(Float)
    grain_yield: Mapped[float | None] = mapped_column(Float)
    grain_protein: Mapped[float | None] = mapped_column(Float)
    grain_size: Mapped[float | None] = mapped_column(Float)
    grain_number: Mapped[float | None] = mapped_column(Float)
    grain_wt: Mapped[float | None] = mapped_column(Float)
    grain_n: Mapped[float | None] = mapped_column(Float)
    n: Mapped[float | None] = mapped_column(Float)
    # One value per soil layer, top layer first.
    paw: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    sw: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
