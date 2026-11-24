"""Tests for the overview and timeline routes and the result helpers (S4-33).

The tests write finished runs straight into simulation_runs and
simulation_daily, the way the worker does, so they need no sim service.
"""

import datetime as dt
import uuid

import pytest
from conftest import SignUp
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.db.models.app_setting import AppSetting
from api.db.models.simulation import RunStatus, SimulationDaily, SimulationRun
from api.db.models.weather_daily import WeatherDaily
from api.results import ROOT_ZONE_LAYERS, daily_series, stage_dates

SQUARE = [
    [10.38, 55.40],
    [10.40, 55.40],
    [10.40, 55.41],
    [10.38, 55.41],
    [10.38, 55.40],
]
NEW_FIELD = {
    "name": "Results field",
    "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
    "sowing_window": {"start": "2025-09-15", "end": "2025-10-15"},
}
DEMO_DATE = dt.date(2026, 3, 15)
SOWN = dt.date(2025, 10, 1)
RIPE = dt.date(2026, 8, 10)

# The days APSIM names a stage in the fake run, as the real model does
APSIM_STAGES = {
    dt.date(2025, 10, 1): "Sowing",
    dt.date(2025, 10, 2): "Germination",
    dt.date(2025, 10, 9): "Emergence",
    dt.date(2025, 11, 1): "DoubleRidge",
    dt.date(2026, 4, 1): "MaximumSpikeletPrimordia",
    dt.date(2026, 5, 25): "FlagLeafAppearance",
    dt.date(2026, 6, 5): "HeadEmergence",
    dt.date(2026, 6, 12): "Anthesis",
    dt.date(2026, 6, 20): "MaximumGrainLength",
    dt.date(2026, 7, 25): "EndGrainFill",
    dt.date(2026, 8, 10): "HarvestRipe",
}
# Zadoks per stretch of the season, for the stages APSIM does not name
ZADOKS = [
    (dt.date(2025, 10, 1), 0.0),
    (dt.date(2025, 10, 9), 10.0),
    (dt.date(2025, 11, 20), 21.0),  # Tillering
    (dt.date(2026, 4, 10), 30.0),  # Stem extension
    (dt.date(2026, 5, 25), 39.0),
    (dt.date(2026, 6, 1), 45.0),  # Booting
    (dt.date(2026, 6, 5), 55.0),
    (dt.date(2026, 6, 12), 65.0),
    (dt.date(2026, 6, 20), 71.0),
    (dt.date(2026, 6, 28), 73.0),  # Milk development
    (dt.date(2026, 7, 10), 83.0),  # Dough development
    (dt.date(2026, 7, 25), 87.0),
    (dt.date(2026, 8, 10), 90.0),
]


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
def field_id(client: TestClient, owner: dict[str, str]) -> int:
    response = client.post("/fields", json=NEW_FIELD, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def zadoks_on(date: dt.date) -> float:
    return [z for start, z in ZADOKS if start <= date][-1]


def add_run(
    db: Session,
    field_id: int,
    job_id: uuid.UUID,
    season: str = "2025/26",
    status: RunStatus = RunStatus.done,
    shift_days: int = 0,
    final_yield: float = 7000.0,
    demo_date: dt.date = DEMO_DATE,
    created_at: dt.datetime | None = None,
) -> SimulationRun:
    """Add one finished run. shift_days moves every stage after 1 March later."""
    run = SimulationRun(
        job_id=job_id,
        field_id=field_id,
        season=season,
        inputs_hash="x" * 64,
        inputs={"demo_date": demo_date.isoformat()},
        status=status,
        sowing_date=SOWN if status == RunStatus.done else None,
        runtime_ms=2500,
        finished_at=dt.datetime(2026, 3, 15, 8, 0, tzinfo=dt.UTC),
    )
    if created_at:
        run.created_at = created_at
    db.add(run)
    db.flush()
    if status != RunStatus.done:
        return run

    def moved(date: dt.date) -> dt.date:
        return (
            date + dt.timedelta(days=shift_days) if date > dt.date(2026, 3, 1) else date
        )

    stages = {moved(date): name for date, name in APSIM_STAGES.items()}
    last_day = moved(RIPE)
    days = (last_day - SOWN).days + 1
    rows = []
    for i in range(days):
        date = SOWN + dt.timedelta(days=i)
        source = (
            date
            if date <= dt.date(2026, 3, 1)
            else date - dt.timedelta(days=shift_days)
        )
        rows.append(
            SimulationDaily(
                run_id=run.id,
                date=date,
                stage=stages.get(date),
                zadoks=zadoks_on(source),
                lai=round(i / days * 6, 3),
                biomass=float(i * 4),
                # Grows over the last 60 days and reaches final_yield on the last day
                grain_yield=final_yield * max(0, i - days + 61) / 60,
                # In mm per layer, as the sim reports PAWmm
                paw=[15.0, 18.0, 45.0, 45.0, 42.0, 39.0, 36.0],
                # 300 main stems, and the first tillers on 20 November
                stems=300.0 if date < dt.date(2025, 11, 20) else 520.0,
                sw=[0.25] * 7,
            )
        )
    db.add_all(rows)
    db.flush()
    return run


def overview(client: TestClient, field_id: int, headers: dict[str, str]) -> dict:
    response = client.get(f"/fields/{field_id}/overview", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# The helpers for one run


def test_stage_dates_finds_apsim_and_zadoks_stages(db: Session, field_id: int) -> None:
    run = add_run(db, field_id, uuid.uuid4())
    rows = sorted(run_days(db, run), key=lambda r: r.date)

    dates = stage_dates(rows)

    assert dates["Sowing"] == SOWN
    assert dates["Anthesis"] == dt.date(2026, 6, 12)
    assert dates["HarvestRipe"] == RIPE
    # Tillering starts on the first day with more stems than at sowing
    assert dates["Tillering"] == dt.date(2025, 11, 20)
    # The other stages without an APSIM name start on the first day at their
    # Zadoks code
    assert dates["Booting"] == dt.date(2026, 6, 1)
    assert dates["DoughDevelopment"] == dt.date(2026, 7, 10)


def test_daily_series_sums_the_root_zone_soil_water(db: Session, field_id: int) -> None:
    run = add_run(db, field_id, uuid.uuid4())
    rows = sorted(run_days(db, run), key=lambda r: r.date)

    series = daily_series(rows)

    assert len(series) == len(rows)
    assert ROOT_ZONE_LAYERS == 5
    # The sum of the first 5 layers, in mm
    assert series[0].paw == 15 + 18 + 45 + 45 + 42


def test_tillering_comes_from_the_stem_count_not_from_zadoks(
    db: Session, field_id: int
) -> None:
    run = add_run(db, field_id, uuid.uuid4())
    rows = sorted(run_days(db, run), key=lambda r: r.date)
    # As in the real model: Zadoks never sits at 21 to 29, it jumps to 31
    for row in rows:
        if row.zadoks == 21.0:
            row.zadoks = 20.5
        elif row.zadoks == 30.0:
            row.zadoks = 31.0

    dates = stage_dates(rows)

    assert dates["Tillering"] == dt.date(2025, 11, 20)
    assert dates["StemExtension"] == dt.date(2026, 4, 10)


def test_a_run_without_stem_counts_has_no_tillering(db: Session, field_id: int) -> None:
    run = add_run(db, field_id, uuid.uuid4())
    rows = sorted(run_days(db, run), key=lambda r: r.date)
    for row in rows:
        row.stems = None

    assert "Tillering" not in stage_dates(rows)


def test_a_stage_that_apsim_jumps_over_is_left_out(db: Session, field_id: int) -> None:
    run = add_run(db, field_id, uuid.uuid4())
    rows = sorted(run_days(db, run), key=lambda r: r.date)
    # Zadoks goes straight from flag leaf (39) to heading (55): no Booting (45)
    for row in rows:
        if row.zadoks == 45.0:
            row.zadoks = 55.0

    dates = stage_dates(rows)

    assert "Booting" not in dates
    assert dates["HeadEmergence"] == dt.date(2026, 6, 5)


def run_days(db: Session, run: SimulationRun) -> list[SimulationDaily]:
    return list(db.query(SimulationDaily).filter(SimulationDaily.run_id == run.id))


# The overview


def test_overview_with_one_run(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(db, field_id, uuid.uuid4())

    data = overview(client, field_id, owner)

    assert data["as_of"] == "2026-03-15"
    assert data["field"]["name"] == "Results field"
    assert data["field"]["sowing"] == {
        "status": "sown",
        "date": "2025-10-01",
        "window_start": "2025-09-15",
        "window_end": "2025-10-15",
    }
    # On 15 March the crop has tillered but not started stem extension
    assert data["stage"]["current"] == {
        "code": "Tillering",
        "name": "Tillering",
        "zadoks": 21,
    }
    assert data["stage"]["current_since"] == "2025-11-20"
    assert data["stage"]["stale"] is False
    upcoming = [stage["code"] for stage in data["stage"]["upcoming"]]
    assert upcoming[0] == "StemExtension"
    assert upcoming[-1] == "HarvestRipe"
    # Stages that are not shown to farmers are left out
    assert "MaximumSpikeletPrimordia" not in upcoming
    # With one run, min, median and max are the same
    anthesis = next(s for s in data["stage"]["upcoming"] if s["code"] == "Anthesis")
    assert anthesis["date"] == {
        "min": "2026-06-12",
        "median": "2026-06-12",
        "max": "2026-06-12",
    }

    lai = data["metrics"]["lai"]
    assert lai["value"]["min"] == lai["value"]["median"] == lai["value"]["max"] > 0
    assert lai["unit"] == "m²/m²"
    assert lai["rating"] is None
    assert data["metrics"]["paw"]["value"]["median"] == 165.0
    assert data["metrics"]["paw"]["unit"] == "mm"
    assert data["metrics"]["predicted_yield"]["value"]["median"] == 7000.0

    assert data["alerts"]["items"] == []
    assert data["summary"] is None
    assert data["satellite"] is None
    # No weather is stored for this field's cell
    assert data["weather"] is None


def test_overview_ranges_over_several_runs(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    job_id = uuid.uuid4()
    add_run(db, field_id, job_id, "2018/19", shift_days=0, final_yield=6000)
    add_run(db, field_id, job_id, "2019/20", shift_days=4, final_yield=7000)
    add_run(db, field_id, job_id, "2020/21", shift_days=8, final_yield=8000)

    data = overview(client, field_id, owner)

    anthesis = next(s for s in data["stage"]["upcoming"] if s["code"] == "Anthesis")
    assert anthesis["date"] == {
        "min": "2026-06-12",
        "median": "2026-06-16",
        "max": "2026-06-20",
    }
    assert data["metrics"]["predicted_yield"]["value"] == {
        "min": 6000.0,
        "median": 7000.0,
        "max": 8000.0,
    }


def test_overview_shows_the_stored_weather_of_the_demo_date(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(db, field_id, uuid.uuid4())
    cell_id = client.get(f"/fields/{field_id}/overview", headers=owner).json()["field"][
        "cell_id"
    ]
    db.add(
        WeatherDaily(
            cell_id=cell_id,
            date=DEMO_DATE,
            maxt=9.0,
            mint=1.0,
            rain=2.5,
            radn=8.0,
            wind_speed=4.2,
        )
    )
    db.flush()

    weather = overview(client, field_id, owner)["weather"]

    assert weather["date"] == "2026-03-15"
    assert weather["temp_c"] == 5.0
    assert weather["temp_min_c"] == 1.0
    assert weather["temp_max_c"] == 9.0
    assert weather["rain_mm"] == 2.5
    assert weather["wind_ms"] == 4.2
    assert weather["humidity_pct"] is None
    assert weather["condition"] is None


def test_a_job_for_another_demo_date_is_stale(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(db, field_id, uuid.uuid4(), demo_date=dt.date(2026, 2, 1))

    data = overview(client, field_id, owner)

    assert data["stage"]["stale"] is True
    assert data["metrics"]["lai"]["stale"] is True


def test_the_newest_finished_job_is_used(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(
        db,
        field_id,
        uuid.uuid4(),
        final_yield=5000,
        created_at=dt.datetime(2026, 3, 1, tzinfo=dt.UTC),
    )
    # A newer job that failed is skipped
    add_run(
        db,
        field_id,
        uuid.uuid4(),
        status=RunStatus.failed,
        created_at=dt.datetime(2026, 3, 2, tzinfo=dt.UTC),
    )

    data = overview(client, field_id, owner)

    assert data["metrics"]["predicted_yield"]["value"]["median"] == 5000.0


def test_no_finished_job_gives_409(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(db, field_id, uuid.uuid4(), status=RunStatus.queued)

    for path in ("overview", "timeline", "timeline/details"):
        response = client.get(f"/fields/{field_id}/{path}", headers=owner)
        assert response.status_code == 409
        assert "no finished simulation" in response.json()["detail"]


def test_a_user_who_is_not_a_member_gets_404(
    client: TestClient, db: Session, field_id: int, sign_up: SignUp
) -> None:
    add_run(db, field_id, uuid.uuid4())
    _, stranger = sign_up()

    for path in ("overview", "timeline", "timeline/details"):
        response = client.get(f"/fields/{field_id}/{path}", headers=stranger)
        assert response.status_code == 404


# The timeline


def test_timeline_marks_past_current_and_upcoming_stages(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(db, field_id, uuid.uuid4())

    response = client.get(f"/fields/{field_id}/timeline", headers=owner)

    assert response.status_code == 200, response.text
    stages = {stage["code"]: stage for stage in response.json()["stages"]}
    assert stages["Sowing"]["status"] == "past"
    assert stages["Sowing"]["basis"] == "simulated_observed"
    assert stages["Sowing"]["note"].startswith("Sow into a moist")
    assert stages["Tillering"]["status"] == "current"
    assert stages["Anthesis"]["status"] == "upcoming"
    assert stages["Anthesis"]["basis"] == "predicted"
    assert stages["Anthesis"]["runs_reached"] == stages["Anthesis"]["runs_total"] == 1
    assert "DoubleRidge" not in stages


def test_timeline_details_has_one_row_per_simulated_day(
    client: TestClient, db: Session, field_id: int, owner: dict[str, str]
) -> None:
    add_run(db, field_id, uuid.uuid4())

    response = client.get(f"/fields/{field_id}/timeline/details", headers=owner)

    assert response.status_code == 200, response.text
    data = response.json()
    days = data["days"]
    assert len(days) == (RIPE - SOWN).days + 1
    assert days[0]["date"] == "2025-10-01"
    # The stage of a day is the last stage APSIM named on or before it
    assert days[0]["stage_code"] == "Sowing"
    assert (
        next(d for d in days if d["date"] == "2025-10-05")["stage_code"]
        == "Germination"
    )
    assert data["units"]["paw"] == "mm"
