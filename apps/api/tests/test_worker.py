"""Tests for the simulation worker. They need the Postgres database, not the sim.

The sim service is replaced by a fake client that records the request and
returns a canned response.
"""

import datetime as dt
from typing import Any

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.models.simulation import RunStatus, SimulationDaily, SimulationRun
from api.db.models.weather_daily import WeatherDaily
from api.jobs import worker
from api.jobs.queue import queue_job

CELL = "10km_test_1"
SEASON = "2025/26"
INPUTS = {"demo_date": dt.date(2026, 3, 15), "sowing_date": dt.date(2025, 10, 1)}


@pytest.fixture(autouse=True)
def no_other_jobs(db: Session) -> None:
    """Fail the queued and running runs already in the database.

    The test database is the dev database, so it can hold real jobs. The change
    is rolled back with the rest of the test.
    """
    db.execute(
        update(SimulationRun)
        .where(SimulationRun.status.in_([RunStatus.queued, RunStatus.running]))
        .values(status=RunStatus.failed)
    )


@pytest.fixture
def field(db: Session) -> Field:
    field = Field(
        name="Worker test field",
        geom=WKTElement(
            "POLYGON((12.50 55.60, 12.52 55.60, 12.52 55.61, 12.50 55.60))",
            srid=4326,
        ),
        area_ha=1.0,
        cell_id=CELL,
        sowing_date=dt.date(2025, 9, 20),
    )
    db.add(field)
    db.flush()
    return field


def add_season_weather(db: Session, first_year: int = 2025) -> None:
    start = dt.date(first_year, 9, 1)
    db.add_all(
        WeatherDaily(
            cell_id=CELL,
            date=start + dt.timedelta(days=i),
            radn=10.0,
            maxt=12.0,
            mint=4.0,
            rain=1.0,
        )
        for i in range(365)
    )
    db.flush()


class FakeSim:
    """Records each request and answers with one ok member per season."""

    def __init__(self, failed_seasons: dict[str, str] | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self.failed_seasons = failed_seasons or {}

    def __call__(self, body: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(body)
        return {"members": [self.member(m["season"]) for m in body["members"]]}

    def member(self, season: str) -> dict[str, Any]:
        if season in self.failed_seasons:
            return {
                "season": season,
                "status": "failed",
                "runtime_ms": 0,
                "error": self.failed_seasons[season],
                "sowing_date": None,
                "daily": [],
            }
        return {
            "season": season,
            "status": "ok",
            "runtime_ms": 2500,
            "error": None,
            "sowing_date": "2025-10-01",
            "daily": [
                daily_row(dt.date(2025, 10, 1) + dt.timedelta(days=i)) for i in range(3)
            ],
        }


def daily_row(date: dt.date) -> dict[str, Any]:
    return {
        "date": date.isoformat(),
        "stage": "Sowing" if date == dt.date(2025, 10, 1) else None,
        "zadoks": 0.0,
        "lai": 0.1,
        "biomass": 1.0,
        "biomass_n": 0.01,
        "grain_yield": 0.0,
        "grain_protein": None,
        "grain_size": None,
        "grain_number": 0.0,
        "grain_wt": 0.0,
        "grain_n": 0.0,
        "sw": [0.3] * 7,
        "paw": [10.0, None, 10.0, 10.0, 10.0, 10.0, 10.0],
    }


def runs_of(db: Session, field: Field) -> list[SimulationRun]:
    return list(
        db.scalars(
            select(SimulationRun)
            .where(SimulationRun.field_id == field.id)
            .order_by(SimulationRun.id)
        )
    )


def test_no_queued_job_does_nothing(db: Session) -> None:
    sim = FakeSim()

    assert worker.work_once(db, sim) is None
    assert sim.requests == []


def test_a_queued_job_runs_and_stores_the_daily_rows(db: Session, field: Field) -> None:
    add_season_weather(db)
    job_id = queue_job(db, field.id, [SEASON], INPUTS)
    sim = FakeSim()

    assert worker.work_once(db, sim) == job_id

    # One request with the job's sowing date (not the field's) and the weather
    [request] = sim.requests
    assert request["sowing_date"] == "2025-10-01"
    assert "sowing_window" not in request
    assert 55.60 <= request["latitude"] <= 55.61
    assert 12.50 <= request["longitude"] <= 12.52
    [member] = request["members"]
    assert member["season"] == SEASON
    assert len(member["met"]) == 365
    assert member["met"][0] == {
        "date": "2025-09-01",
        "radn": 10.0,
        "maxt": 12.0,
        "mint": 4.0,
        "rain": 1.0,
    }

    [run] = runs_of(db, field)
    assert run.status == RunStatus.done
    assert run.sowing_date == dt.date(2025, 10, 1)
    assert run.runtime_ms == 2500
    assert run.attempts == 1
    assert run.error is None
    assert run.started_at is not None
    assert run.finished_at is not None

    daily = db.scalars(
        select(SimulationDaily)
        .where(SimulationDaily.run_id == run.id)
        .order_by(SimulationDaily.date)
    ).all()
    assert [day.date for day in daily] == [
        dt.date(2025, 10, 1),
        dt.date(2025, 10, 2),
        dt.date(2025, 10, 3),
    ]
    assert daily[0].stage == "Sowing"
    assert daily[0].paw == [10.0, None, 10.0, 10.0, 10.0, 10.0, 10.0]


def test_a_job_without_sowing_inputs_uses_the_field(db: Session, field: Field) -> None:
    add_season_weather(db)
    queue_job(db, field.id, [SEASON], {"demo_date": dt.date(2026, 3, 15)})
    sim = FakeSim()

    worker.work_once(db, sim)

    assert sim.requests[0]["sowing_date"] == "2025-09-20"


def test_a_sim_error_fails_every_run_of_the_job(
    db: Session, field: Field, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_season_weather(db)
    queue_job(db, field.id, [SEASON], INPUTS)

    def sim_is_down(body: dict[str, Any]) -> dict[str, Any]:
        raise worker.JobError("The sim service did not answer: connection refused")

    worker.work_once(db, sim_is_down)

    [run] = runs_of(db, field)
    assert run.status == RunStatus.failed
    assert run.error == "The sim service did not answer: connection refused"
    assert run.finished_at is not None


def test_an_unexpected_error_fails_the_job_instead_of_leaving_it_running(
    db: Session, field: Field
) -> None:
    add_season_weather(db)
    queue_job(db, field.id, [SEASON], INPUTS)

    def broken_sim(body: dict[str, Any]) -> dict[str, Any]:
        return {"not members": []}

    worker.work_once(db, broken_sim)

    [run] = runs_of(db, field)
    assert run.status == RunStatus.failed
    assert run.error.startswith("The worker failed: KeyError")


def test_a_failed_member_fails_only_its_own_run(db: Session, field: Field) -> None:
    add_season_weather(db, 2024)
    add_season_weather(db, 2025)
    queue_job(db, field.id, ["2024/25", SEASON], INPUTS)
    sim = FakeSim(failed_seasons={"2024/25": "WeatherGapError: 3 days missing"})

    worker.work_once(db, sim)

    # Both seasons went to the sim in one request
    [request] = sim.requests
    assert [member["season"] for member in request["members"]] == ["2024/25", SEASON]
    failed, good = runs_of(db, field)
    assert failed.status == RunStatus.failed
    assert failed.error == "WeatherGapError: 3 days missing"
    assert good.status == RunStatus.done


def test_a_job_without_stored_weather_fails_with_a_clear_message(
    db: Session, field: Field
) -> None:
    queue_job(db, field.id, [SEASON], INPUTS)
    sim = FakeSim()

    worker.work_once(db, sim)

    [run] = runs_of(db, field)
    assert run.status == RunStatus.failed
    assert "No weather is stored for 10km_test_1" in run.error
    assert sim.requests == []


def test_the_oldest_job_runs_first(db: Session, field: Field) -> None:
    add_season_weather(db)
    first = queue_job(db, field.id, [SEASON], INPUTS)
    second = queue_job(db, field.id, [SEASON], {**INPUTS, "demo_date": "2026-04-01"})

    assert worker.work_once(db, FakeSim()) == first
    assert worker.work_once(db, FakeSim()) == second
    assert worker.work_once(db, FakeSim()) is None


@pytest.mark.parametrize(
    ("attempts", "status"),
    [
        pytest.param(1, RunStatus.queued, id="first time: queued again"),
        pytest.param(2, RunStatus.failed, id="second time: failed"),
    ],
)
def test_a_stuck_run_is_queued_again_once(
    db: Session, field: Field, attempts: int, status: RunStatus
) -> None:
    queue_job(db, field.id, [SEASON], INPUTS)
    [run] = runs_of(db, field)
    now = dt.datetime.now(dt.UTC)
    run.status = RunStatus.running
    run.attempts = attempts
    run.started_at = now - dt.timedelta(minutes=16)
    db.flush()

    assert worker.requeue_stuck_runs(db, now) == 1

    assert run.status == status
    if status == RunStatus.failed:
        assert "twice" in run.error


def test_a_run_that_is_not_stuck_yet_is_left_alone(db: Session, field: Field) -> None:
    queue_job(db, field.id, [SEASON], INPUTS)
    [run] = runs_of(db, field)
    now = dt.datetime.now(dt.UTC)
    run.status = RunStatus.running
    run.attempts = 1
    run.started_at = now - dt.timedelta(minutes=14)
    db.flush()

    assert worker.requeue_stuck_runs(db, now) == 0
    assert run.status == RunStatus.running


def test_a_job_another_worker_holds_is_skipped(db: Session, field: Field) -> None:
    add_season_weather(db)
    job_id = queue_job(db, field.id, [SEASON], INPUTS)
    db.commit()

    # A second connection plays the other worker that holds the job's lock
    from api.db.session import engine

    with engine.connect() as other_worker:
        other_worker.begin()
        other_worker.execute(
            select(worker.func.pg_advisory_xact_lock(worker.job_lock_key(job_id)))
        )
        assert worker.take_job(db) == []
        other_worker.rollback()


def test_results_are_dropped_for_a_run_another_worker_took_over(
    db: Session, field: Field
) -> None:
    add_season_weather(db)
    queue_job(db, field.id, [SEASON], INPUTS)

    def slow_sim(body: dict[str, Any]) -> dict[str, Any]:
        # While APSIM runs, the run counts as stuck and a second worker takes it
        db.execute(
            update(SimulationRun)
            .where(SimulationRun.field_id == field.id)
            .values(attempts=SimulationRun.attempts + 1)
        )
        return FakeSim()(body)

    worker.work_once(db, slow_sim)

    [run] = runs_of(db, field)
    db.refresh(run)
    # The second worker owns the run now, so this worker wrote nothing
    assert run.status == RunStatus.running
    assert run.attempts == 2
    daily = db.scalars(select(SimulationDaily).where(SimulationDaily.run_id == run.id))
    assert daily.all() == []


def test_a_field_deleted_during_the_job_does_not_crash_the_worker(
    db: Session, field: Field
) -> None:
    add_season_weather(db)
    job_id = queue_job(db, field.id, [SEASON], INPUTS)
    field_id = field.id

    def sim_while_the_user_deletes_the_field(body: dict[str, Any]) -> dict[str, Any]:
        db.delete(db.get(Field, field_id))
        db.flush()
        return FakeSim()(body)

    assert worker.work_once(db, sim_while_the_user_deletes_the_field) == job_id

    assert (
        db.scalars(select(SimulationRun).where(SimulationRun.job_id == job_id)).all()
        == []
    )


def test_the_worker_loop_survives_an_error() -> None:
    def broken_session_factory() -> Session:
        raise ConnectionError("the database is down")

    assert worker.work_safely(broken_session_factory, FakeSim()) is None
