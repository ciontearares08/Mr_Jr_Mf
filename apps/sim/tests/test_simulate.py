import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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

    # Both members ran in the same APSIM process, so they share its run time
    assert members[0]["runtime_ms"] == members[1]["runtime_ms"]

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
        assert daily[0]["stems"] > 0


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
        pytest.param(
            {
                "members": [
                    {"season": "2018/19", "met": ONE_DAY_MET},
                    {
                        "season": "2019/20",
                        "met": [{**ONE_DAY_MET[0], "date": "2025-09-02"}],
                    },
                ]
            },
            id="members with different dates",
        ),
    ],
)
def test_rejects_a_wrong_request(changes: dict) -> None:
    body = request_body(members=[{"season": "2018/19", "met": ONE_DAY_MET}])
    body.update(changes)

    response = client.post("/sim/simulate", json=body)
    assert response.status_code == 422


def test_a_failed_member_before_apsim_has_no_run_time() -> None:
    gap_met = weather_rows(WEATHER_PATH)
    for row in gap_met[100:103]:
        row["rain"] = None
    body = request_body(
        members=[
            {"season": "2018/19", "met": weather_rows(WEATHER_PATH)},
            {"season": "2019/20", "met": gap_met},
        ]
    )

    good, failed = client.post("/sim/simulate", json=body).json()["members"]

    assert good["runtime_ms"] > 0
    assert failed["runtime_ms"] == 0
