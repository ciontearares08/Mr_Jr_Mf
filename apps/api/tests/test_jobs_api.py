"""Tests for the first job of a new field and the job routes (S4-32)."""

import datetime as dt
import uuid

import pytest
from conftest import SignUp
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models.app_setting import AppSetting
from api.db.models.simulation import RunStatus, SimulationRun

SQUARE = [
    [10.38, 55.40],
    [10.40, 55.40],
    [10.40, 55.41],
    [10.38, 55.41],
    [10.38, 55.40],
]
NEW_FIELD = {
    "name": "Job field",
    "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
    "sowing_window": {"start": "2025-09-15", "end": "2025-10-15"},
}
DEMO_DATE = dt.date(2026, 3, 15)


@pytest.fixture(autouse=True)
def no_dmi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.routers.fields.wind_station_or_none", lambda _: None)


@pytest.fixture(autouse=True)
def demo_date(db: Session) -> None:
    db.get(AppSetting, 1).demo_date = DEMO_DATE
    db.flush()


@pytest.fixture
def owner(sign_up: SignUp) -> dict[str, str]:
    _, headers = sign_up()
    return headers


@pytest.fixture
def created(client: TestClient, owner: dict[str, str]) -> dict:
    response = client.post("/fields", json=NEW_FIELD, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()


def runs_of_job(db: Session, job_id: str) -> list[SimulationRun]:
    return list(
        db.scalars(
            select(SimulationRun).where(SimulationRun.job_id == uuid.UUID(job_id))
        )
    )


def finish(
    runs: list[SimulationRun],
    status: RunStatus = RunStatus.done,
    error: str | None = None,
) -> None:
    for run in runs:
        run.status = status
        run.error = error
        run.runtime_ms = 2400 if status == RunStatus.done else None
        run.finished_at = dt.datetime(2026, 11, 24, 12, 0, tzinfo=dt.UTC)


def test_a_new_field_queues_its_first_job(created: dict, db: Session) -> None:
    [run] = runs_of_job(db, created["job_id"])

    assert run.field_id == created["id"]
    assert run.season == "2025/26"
    assert run.status == RunStatus.queued
    # The worker reads the sowing window and the run history the demo date
    assert run.inputs == {
        "demo_date": "2026-03-15",
        "results_version": 2,
        "sowing_window": {"start": "2025-09-15", "end": "2025-10-15"},
    }


def test_a_field_with_a_sowing_date_queues_it(
    client: TestClient, owner: dict[str, str], db: Session
) -> None:
    body = {**NEW_FIELD, "sowing_window": None, "sowing_date": "2025-10-01"}

    created = client.post("/fields", json=body, headers=owner).json()

    [run] = runs_of_job(db, created["job_id"])
    assert run.inputs == {
        "demo_date": "2026-03-15",
        "results_version": 2,
        "sowing_date": "2025-10-01",
    }


def test_the_job_status_follows_its_runs(
    client: TestClient, created: dict, owner: dict[str, str], db: Session
) -> None:
    job_id = created["job_id"]

    queued = client.get(f"/jobs/{job_id}", headers=owner)
    assert queued.status_code == 200, queued.text
    assert queued.json()["status"] == "queued"
    assert queued.json()["field_id"] == created["id"]
    assert queued.json()["finished_at"] is None

    finish(runs_of_job(db, job_id))
    db.flush()

    done = client.get(f"/jobs/{job_id}", headers=owner).json()
    assert done["status"] == "done"
    assert done["error"] is None
    assert done["finished_at"] == "2026-11-24T12:00:00Z"


def test_a_failed_job_shows_the_error(
    client: TestClient, created: dict, owner: dict[str, str], db: Session
) -> None:
    finish(
        runs_of_job(db, created["job_id"]), RunStatus.failed, "WeatherGapError: 3 days"
    )
    db.flush()

    job = client.get(f"/jobs/{created['job_id']}", headers=owner).json()

    assert job["status"] == "failed"
    assert job["error"] == "WeatherGapError: 3 days"


def test_a_job_is_404_for_a_user_who_is_not_a_member(
    client: TestClient, created: dict, sign_up: SignUp
) -> None:
    _, stranger = sign_up()

    response = client.get(f"/jobs/{created['job_id']}", headers=stranger)

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_an_unknown_job_is_404(client: TestClient, owner: dict[str, str]) -> None:
    response = client.get(f"/jobs/{uuid.uuid4()}", headers=owner)

    assert response.status_code == 404


def test_the_run_history_lists_the_jobs_newest_first(
    client: TestClient, created: dict, owner: dict[str, str], db: Session
) -> None:
    first_job = created["job_id"]
    first_runs = runs_of_job(db, first_job)
    finish(first_runs)
    for run in first_runs:
        run.created_at = dt.datetime(2026, 11, 24, 10, 0, tzinfo=dt.UTC)
    # A newer job for a later demo date, still queued
    newer = SimulationRun(
        job_id=uuid.uuid4(),
        field_id=created["id"],
        season="2025/26",
        inputs_hash="y" * 64,
        inputs={"demo_date": "2026-04-01"},
        status=RunStatus.queued,
        created_at=dt.datetime(2026, 11, 24, 11, 0, tzinfo=dt.UTC),
    )
    db.add(newer)
    db.flush()

    response = client.get(f"/fields/{created['id']}/runs", headers=owner)

    assert response.status_code == 200, response.text
    jobs = response.json()
    assert [job["id"] for job in jobs] == [str(newer.job_id), first_job]
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["demo_date"] == "2026-04-01"
    assert jobs[0]["runtime_ms"] is None
    assert jobs[1]["status"] == "done"
    assert jobs[1]["demo_date"] == "2026-03-15"
    assert jobs[1]["n_runs"] == 1
    assert jobs[1]["runtime_ms"] == 2400


def test_the_run_history_shows_at_most_20_jobs(
    client: TestClient, created: dict, owner: dict[str, str], db: Session
) -> None:
    db.add_all(
        SimulationRun(
            job_id=uuid.uuid4(),
            field_id=created["id"],
            season="2025/26",
            inputs_hash="z" * 64,
            status=RunStatus.done,
        )
        for _ in range(25)
    )
    db.flush()

    jobs = client.get(f"/fields/{created['id']}/runs", headers=owner).json()

    assert len(jobs) == 20


def test_the_run_history_is_404_for_a_user_who_is_not_a_member(
    client: TestClient, created: dict, sign_up: SignUp
) -> None:
    _, stranger = sign_up()

    response = client.get(f"/fields/{created['id']}/runs", headers=stranger)

    assert response.status_code == 404
