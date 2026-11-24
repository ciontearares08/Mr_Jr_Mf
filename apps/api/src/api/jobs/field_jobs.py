"""Queue the simulation job of a field (S4-32).

POST /fields queues the first job of a new field. Moving the demo date (S5-33)
and logging an action (S6-36) will queue a new job the same way.
"""

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.jobs.queue import queue_job

# The season the app replays. Until the ensemble (S5-31), a job has one run with
# the observed weather of this season.
OBSERVED_SEASON = "2025/26"


def job_inputs(field: Field, demo_date: dt.date) -> dict[str, object]:
    """Return everything a job of this field depends on.

    The worker reads the sowing date or window from here, and the run history
    shows the demo date. A change to any of them queues a new job.
    """
    inputs: dict[str, object] = {"demo_date": demo_date}
    if field.sowing_date is not None:
        inputs["sowing_date"] = field.sowing_date
    else:
        inputs["sowing_window"] = {
            "start": field.sowing_window_start,
            "end": field.sowing_window_end,
        }
    if field.soil_profile is not None:
        inputs["soil_profile"] = field.soil_profile
    return inputs


def queue_field_job(db: Session, field: Field, demo_date: dt.date) -> uuid.UUID:
    """Queue a job for the field and return its id. Does not commit.

    If a finished job has the same inputs, its id comes back and nothing is
    queued (see api.jobs.queue).
    """
    return queue_job(db, field.id, [OBSERVED_SEASON], job_inputs(field, demo_date))
