"""Tests for the simulation tables and the job queue. They need the Postgres database."""

import datetime as dt

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.models.simulation import RunStatus, SimulationDaily, SimulationRun
from api.jobs.queue import queue_job

SEASONS = ["2015/16", "2016/17", "2017/18"]
INPUTS = {"demo_date": dt.date(2026, 3, 15), "sowing_date": dt.date(2025, 10, 1)}


def add_field(db: Session) -> int:
    field = Field(
        name="Test field",
        geom=WKTElement(
            "POLYGON((10.38 55.40, 10.40 55.40, 10.40 55.41, 10.38 55.40))",
            srid=4326,
        ),
        area_ha=1.0,
        sowing_date=dt.date(2025, 10, 1),
    )
    db.add(field)
    db.flush()
    return field.id


@pytest.fixture
def field_id(db: Session) -> int:
    return add_field(db)


def runs_of_field(db: Session, field_id: int) -> list[SimulationRun]:
    return list(
        db.scalars(
            select(SimulationRun)
            .where(SimulationRun.field_id == field_id)
            .order_by(SimulationRun.id)
        )
    )


def finish_job(db: Session, field_id: int, status: RunStatus = RunStatus.done) -> None:
    """Set every run of the field to done, and the last one to `status`."""
    runs = runs_of_field(db, field_id)
    for run in runs:
        run.status = RunStatus.done
    runs[-1].status = status
    db.flush()


def test_queue_job_adds_one_queued_run_per_season(db: Session, field_id: int) -> None:
    job_id = queue_job(db, field_id, SEASONS, INPUTS)

    runs = runs_of_field(db, field_id)
    assert [run.season for run in runs] == SEASONS
    assert {run.job_id for run in runs} == {job_id}
    assert {run.status for run in runs} == {RunStatus.queued}
    assert len({run.inputs_hash for run in runs}) == 1


def test_a_finished_job_with_the_same_inputs_is_not_queued_again(
    db: Session, field_id: int
) -> None:
    first_job_id = queue_job(db, field_id, SEASONS, INPUTS)
    finish_job(db, field_id)

    # The same inputs in another key order.
    same_inputs = dict(reversed(INPUTS.items()))
    job_id = queue_job(db, field_id, SEASONS, same_inputs)

    assert job_id == first_job_id
    assert len(runs_of_field(db, field_id)) == len(SEASONS)


def test_a_job_with_a_failed_run_is_queued_again(db: Session, field_id: int) -> None:
    first_job_id = queue_job(db, field_id, SEASONS, INPUTS)
    finish_job(db, field_id, status=RunStatus.failed)

    job_id = queue_job(db, field_id, SEASONS, INPUTS)

    assert job_id != first_job_id
    assert len(runs_of_field(db, field_id)) == 2 * len(SEASONS)


def test_new_inputs_or_seasons_queue_a_new_job(db: Session, field_id: int) -> None:
    first_job_id = queue_job(db, field_id, SEASONS, INPUTS)
    finish_job(db, field_id)

    new_date_job_id = queue_job(
        db, field_id, SEASONS, {**INPUTS, "demo_date": dt.date(2026, 3, 16)}
    )
    new_seasons_job_id = queue_job(db, field_id, SEASONS[:2], INPUTS)

    assert len({first_job_id, new_date_job_id, new_seasons_job_id}) == 3


def test_a_finished_job_of_another_field_is_not_reused(
    db: Session, field_id: int
) -> None:
    queue_job(db, field_id, SEASONS, INPUTS)
    finish_job(db, field_id)
    other_field_id = add_field(db)

    queue_job(db, other_field_id, SEASONS, INPUTS)

    assert len(runs_of_field(db, other_field_id)) == len(SEASONS)


@pytest.mark.parametrize(
    ("seasons", "message"),
    [([], "at least one season"), (["2015/16", "2015/16"], "more than once")],
)
def test_queue_job_rejects_bad_seasons(
    db: Session, field_id: int, seasons: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        queue_job(db, field_id, seasons, INPUTS)


def test_daily_rows_keep_the_soil_layers_and_go_with_the_field(
    db: Session, field_id: int
) -> None:
    queue_job(db, field_id, SEASONS[:1], INPUTS)
    run = runs_of_field(db, field_id)[0]
    db.add(
        SimulationDaily(
            run_id=run.id,
            date=dt.date(2025, 10, 1),
            stage="Sowing",
            grain_yield=0.0,
            paw=[10.5, 20.0, 30.25],
            sw=[0.3, 0.28, 0.25],
        )
    )
    db.flush()
    db.expire_all()

    # Only this run: the dev database can hold rows of real runs
    daily = db.scalars(
        select(SimulationDaily).where(SimulationDaily.run_id == run.id)
    ).one()
    assert daily.paw == [10.5, 20.0, 30.25]
    assert daily.sw == [0.3, 0.28, 0.25]
    assert daily.grain_yield == 0.0

    db.delete(db.get(Field, field_id))
    db.flush()
    assert (
        db.scalars(
            select(SimulationDaily).where(SimulationDaily.run_id == run.id)
        ).all()
        == []
    )
    assert runs_of_field(db, field_id) == []
