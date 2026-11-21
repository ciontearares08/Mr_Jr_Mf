"""Queue ensemble jobs in the simulation_runs table.

A job is one run per past weather season, all with the same field inputs and
one shared job_id. The worker (S4-01) picks up the queued runs. The queue is the
table itself, so it needs no Redis and survives an API restart.

queue_job does not commit: the caller owns the transaction, for example:

    job_id = queue_job(db, field.id, seasons, inputs)
    db.commit()
"""

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.models.simulation import RunStatus, SimulationRun


def queue_job(
    db: Session,
    field_id: int,
    seasons: Sequence[str],
    inputs: Mapping[str, object],
) -> uuid.UUID:
    """Queue one run per season for a field and return the job_id.

    `inputs` is everything else the runs depend on, for example the demo date,
    the sowing date or window, the soil and the farmer's events. Its values must
    be JSON values or dates.

    If a finished job of this field has the same inputs and seasons, nothing is
    queued and the function returns that job's id, because the results would
    be the same. A job is finished when every run is done, so a job with a
    failed run is queued again.
    """
    if not seasons:
        raise ValueError("A job needs at least one season")
    if len(set(seasons)) < len(seasons):
        raise ValueError(f"A season comes more than once: {list(seasons)}")

    inputs_hash = hash_inputs({"inputs": inputs, "seasons": list(seasons)})
    finished_job_id = find_finished_job(db, field_id, inputs_hash)
    if finished_job_id is not None:
        return finished_job_id

    job_id = uuid.uuid4()
    db.add_all(
        SimulationRun(
            job_id=job_id,
            field_id=field_id,
            season=season,
            inputs_hash=inputs_hash,
            status=RunStatus.queued,
        )
        for season in seasons
    )
    # Flush so the rows have IDs and later queries in this session see them.
    db.flush()
    return job_id


def find_finished_job(db: Session, field_id: int, inputs_hash: str) -> uuid.UUID | None:
    """Return the newest job of the field with these inputs whose runs are all done."""
    return db.scalar(
        select(SimulationRun.job_id)
        .where(
            SimulationRun.field_id == field_id,
            SimulationRun.inputs_hash == inputs_hash,
        )
        .group_by(SimulationRun.job_id)
        .having(func.bool_and(SimulationRun.status == RunStatus.done))
        .order_by(func.max(SimulationRun.created_at).desc())
        .limit(1)
    )


def hash_inputs(inputs: Mapping[str, object]) -> str:
    """Return a SHA-256 hash of the inputs that does not depend on key order."""
    # default=str writes a date as "2026-03-15".
    text = json.dumps(inputs, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()
