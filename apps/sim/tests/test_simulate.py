import datetime as dt
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sim import simulate
from sim.main import app

client = TestClient(app)

WEATHER_PATH = Path(__file__).parent / "fixtures" / "Copenhagen_2025-26.met"


def weather_rows(path: Path) -> list[dict]:
    """Return the days of a .met file as the JSON rows the API sends."""
    lines = path.read_text(encoding="utf-8").splitlines()
    # The data starts after the units line, which starts with "()"
    units_line = next(i for i, line in enumerate(lines) if line.startswith("()"))

    rows = []
    for line in lines[units_line + 1 :]:
        year, day_of_year, radn, maxt, mint, rain = line.split()
        date = dt.date(int(year), 1, 1) + dt.timedelta(days=int(day_of_year) - 1)
        rows.append(
            {
                "date": date.isoformat(),
                "radn": float(radn),
                "maxt": float(maxt),
                "mint": float(mint),
                "rain": float(rain),
            }
        )
    return rows


def request_body(**changes) -> dict:
    """A valid request with two members. Keyword arguments replace its fields."""
    met = weather_rows(WEATHER_PATH)
    body = {
        "latitude": 55.67,
        "longitude": 12.58,
        "sowing_date": "2025-10-01",
        "members": [
            {"season": "2018/19", "met": met},
            {"season": "2019/20", "met": met},
        ],
    }
    body.update(changes)
    return body


# The two tests below run APSIM, so they take a few seconds each


def test_two_members_return_daily_rows() -> None:
    response = client.post("/sim/simulate", json=request_body())
    assert response.status_code == 200

    members = response.json()["members"]
    # The results come back in the same order as the request
    assert [member["season"] for member in members] == ["2018/19", "2019/20"]

    for member in members:
        assert member["status"] == "ok"
        assert member["error"] is None
        assert member["runtime_ms"] > 0
        assert member["sowing_date"] == "2025-10-01"

        daily = member["daily"]
        assert daily[0]["date"] == "2025-10-01"
        assert daily[0]["stage"] == "Sowing"
        assert daily[-1]["stage"] == "HarvestRipe"
        # One value per soil layer
        assert len(daily[0]["sw"]) == 7
        assert len(daily[0]["paw"]) == 7


def test_a_failed_member_does_not_fail_the_others() -> None:
    good_met = weather_rows(WEATHER_PATH)
    # Three missing days in a row are too many to fill, so this member fails
    gap_met = weather_rows(WEATHER_PATH)
    for row in gap_met[100:103]:
        row["rain"] = None

    body = request_body(
        sowing_date=None,
        sowing_window={"start": "2025-09-15", "end": "2025-10-15"},
        members=[
            {"season": "2018/19", "met": good_met},
            {"season": "2019/20", "met": gap_met},
        ],
    )
    response = client.post("/sim/simulate", json=body)
    assert response.status_code == 200

    good, failed = response.json()["members"]

    assert good["status"] == "ok"
    # With a window, APSIM picks the sowing day inside it
    assert "2025-09-15" <= good["sowing_date"] <= "2025-10-15"
    assert good["daily"][0]["date"] == good["sowing_date"]

    assert failed["status"] == "failed"
    assert "WeatherGapError" in failed["error"]
    assert failed["sowing_date"] is None
    assert failed["daily"] == []


# The tests below are rejected before APSIM runs, so they are quick

ONE_DAY_MET = [{"date": "2025-09-01", "radn": 1, "maxt": 2, "mint": 0, "rain": 0}]


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"sowing_date": None}, id="no sowing date or window"),
        pytest.param(
            {"sowing_window": {"start": "2025-09-15", "end": "2025-10-15"}},
            id="both a sowing date and a window",
        ),
        pytest.param(
            {
                "sowing_date": None,
                "sowing_window": {"start": "2025-10-15", "end": "2025-09-15"},
            },
            id="window ends before it starts",
        ),
        pytest.param({"members": []}, id="no members"),
        pytest.param(
            {
                "members": [
                    {"season": "2018/19", "met": ONE_DAY_MET},
                    {"season": "2018/19", "met": ONE_DAY_MET},
                ]
            },
            id="the same season twice",
        ),
        pytest.param({"latitude": 555.67}, id="latitude not on Earth"),
    ],
)
def test_rejects_a_wrong_request(changes: dict) -> None:
    body = request_body(members=[{"season": "2018/19", "met": ONE_DAY_MET}])
    body.update(changes)

    response = client.post("/sim/simulate", json=body)
    assert response.status_code == 422


# How many members run at the same time (worker_count)


def cpu_limit_file(tmp_path: Path, text: str) -> Path:
    """Write a fake cgroup cpu.max file and return its path."""
    path = tmp_path / "cpu.max"
    path.write_text(text, encoding="utf-8")
    return path


def test_worker_count_uses_sim_workers_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SIM_WORKERS", "3")
    # The container limit is 2 CPUs, but the setting wins
    monkeypatch.setattr(
        simulate, "CPU_LIMIT_FILE", cpu_limit_file(tmp_path, "200000 100000")
    )

    assert simulate.worker_count() == 3


def test_worker_count_rejects_sim_workers_below_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIM_WORKERS", "0")

    with pytest.raises(ValueError, match="at least 1"):
        simulate.worker_count()


@pytest.mark.parametrize(
    ("cpu_max", "workers"),
    [
        pytest.param("200000 100000", 2, id="2 CPUs"),
        pytest.param("150000 100000", 1, id="1.5 CPUs rounds down"),
        pytest.param("50000 100000", 1, id="half a CPU still gets one worker"),
    ],
)
def test_worker_count_follows_the_container_cpu_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cpu_max: str, workers: int
) -> None:
    monkeypatch.delenv("SIM_WORKERS", raising=False)
    monkeypatch.setattr(simulate, "CPU_LIMIT_FILE", cpu_limit_file(tmp_path, cpu_max))

    assert simulate.worker_count() == workers


def test_worker_count_without_a_limit_uses_the_cpus_of_the_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SIM_WORKERS", raising=False)
    monkeypatch.setattr(
        simulate, "CPU_LIMIT_FILE", cpu_limit_file(tmp_path, "max 100000")
    )

    assert simulate.worker_count() == os.process_cpu_count()
