"""Tests for the ensemble weather. They need the Postgres database, not DMI.

Each stored test day carries its own date in its values, so a test can see
which stored day ended up under which date of a member:
maxt = year, radn = month, mint = day of the month.
"""

import datetime as dt

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from api.db.models.weather_daily import WeatherDaily
from api.weather.dmi import dates_between
from api.weather.ensemble import (
    ENSEMBLE_SEASONS,
    build_ensemble,
    same_day_in,
)
from api.weather.store import HISTORY_START

CELL = "10km_test_ensemble"
FIRST_DAY = dt.date(2025, 9, 1)
LAST_DAY = dt.date(2026, 8, 31)
SEASON_DAYS = 365


def store_weather(db: Session, start: dt.date, end: dt.date) -> None:
    db.execute(
        insert(WeatherDaily),
        [
            {
                "cell_id": CELL,
                "date": date,
                "maxt": float(date.year),
                "radn": float(date.month),
                "mint": float(date.day),
                "rain": 0.0,
            }
            for date in dates_between(start, end)
        ],
    )


@pytest.fixture
def weather(db: Session) -> None:
    """Every day from the first ensemble season to the end of 2025/26."""
    store_weather(db, HISTORY_START, LAST_DAY)


def source_date(row: dict) -> dt.date | None:
    """Return the stored day that a member row came from."""
    if row["maxt"] is None:
        return None
    return dt.date(int(row["maxt"]), int(row["radn"]), int(row["mint"]))


def test_one_member_per_season_in_order(db: Session, weather: None) -> None:
    ensemble = build_ensemble(db, CELL, dt.date(2026, 3, 15))

    assert list(ensemble) == list(ENSEMBLE_SEASONS)
    assert len(ensemble) == 10


def test_every_member_has_every_day_of_the_season(db: Session, weather: None) -> None:
    ensemble = build_ensemble(db, CELL, dt.date(2026, 3, 15))

    for rows in ensemble.values():
        assert [row["date"] for row in rows] == dates_between(FIRST_DAY, LAST_DAY)
        assert len(rows) == SEASON_DAYS
        # No missing day: every value is there
        assert all(
            row[c] is not None for row in rows for c in ("radn", "maxt", "mint", "rain")
        )


def test_members_are_equal_up_to_the_demo_date_and_differ_after_it(
    db: Session, weather: None
) -> None:
    demo_date = dt.date(2026, 3, 15)
    known_days = (demo_date - FIRST_DAY).days + 1

    ensemble = build_ensemble(db, CELL, demo_date)
    members = list(ensemble.values())

    for rows in members:
        # Up to and including D: the observed day itself
        assert all(source_date(row) == row["date"] for row in rows[:known_days])
    # After D: each member has its own season, so no two members are equal
    futures = [tuple(source_date(row) for row in rows[known_days:]) for rows in members]
    assert len(set(futures)) == len(members)


def test_after_the_demo_date_a_member_has_the_same_days_of_its_season(
    db: Session, weather: None
) -> None:
    ensemble = build_ensemble(db, CELL, dt.date(2026, 3, 15))

    rows = ensemble["2018/19"]
    by_date = {row["date"]: source_date(row) for row in rows}
    assert by_date[dt.date(2026, 3, 15)] == dt.date(2026, 3, 15)  # D is observed
    assert by_date[dt.date(2026, 3, 16)] == dt.date(2019, 3, 16)
    assert by_date[dt.date(2026, 8, 31)] == dt.date(2019, 8, 31)


def test_29_february_of_a_past_season_is_dropped(db: Session, weather: None) -> None:
    # Before 29 February, so the past part covers it
    ensemble = build_ensemble(db, CELL, dt.date(2025, 12, 1))

    for season in ("2015/16", "2019/20", "2023/24"):
        rows = ensemble[season]
        sources = [source_date(row) for row in rows]
        assert not any(d.month == 2 and d.day == 29 for d in sources if d)
        by_date = dict(zip((row["date"] for row in rows), sources, strict=True))
        # 28 February and 1 March stay on their own days
        first_year = int(season[:4])
        assert by_date[dt.date(2026, 2, 28)] == dt.date(first_year + 1, 2, 28)
        assert by_date[dt.date(2026, 3, 1)] == dt.date(first_year + 1, 3, 1)


def test_29_february_of_the_observed_season_repeats_28_february() -> None:
    # Not needed for 2025/26, but a later leap season must not crash
    assert same_day_in(dt.date(2028, 2, 29), 1) == dt.date(2027, 2, 28)
    assert same_day_in(dt.date(2028, 2, 29), 4) == dt.date(2024, 2, 29)
    assert same_day_in(dt.date(2026, 3, 1), 2) == dt.date(2024, 3, 1)


def test_on_the_last_day_every_member_is_the_observed_season(
    db: Session, weather: None
) -> None:
    ensemble = build_ensemble(db, CELL, LAST_DAY)

    for rows in ensemble.values():
        assert all(source_date(row) == row["date"] for row in rows)


def test_on_the_first_day_only_that_day_is_observed(db: Session, weather: None) -> None:
    ensemble = build_ensemble(db, CELL, FIRST_DAY)

    rows = ensemble["2024/25"]
    assert source_date(rows[0]) == FIRST_DAY
    assert source_date(rows[1]) == dt.date(2024, 9, 2)


def test_a_missing_stored_day_comes_back_as_none(db: Session, weather: None) -> None:
    db.execute(
        delete(WeatherDaily).where(
            WeatherDaily.cell_id == CELL, WeatherDaily.date == dt.date(2019, 5, 1)
        )
    )

    rows = build_ensemble(db, CELL, dt.date(2026, 3, 15))["2018/19"]

    [missing] = [row for row in rows if row["maxt"] is None]
    assert missing == {
        "date": dt.date(2026, 5, 1),
        "radn": None,
        "maxt": None,
        "mint": None,
        "rain": None,
    }
    assert len(rows) == SEASON_DAYS


def test_custom_seasons(db: Session, weather: None) -> None:
    ensemble = build_ensemble(
        db, CELL, dt.date(2026, 3, 15), seasons=["2020/21", "2016/17"]
    )

    assert list(ensemble) == ["2020/21", "2016/17"]


@pytest.mark.parametrize(
    ("demo_date", "seasons", "message"),
    [
        pytest.param(
            dt.date(2025, 8, 31), ENSEMBLE_SEASONS, "not in the 2025/26", id="D before"
        ),
        pytest.param(
            dt.date(2026, 9, 1), ENSEMBLE_SEASONS, "not in the 2025/26", id="D after"
        ),
        pytest.param(dt.date(2026, 3, 15), [], "at least one", id="no seasons"),
        pytest.param(
            dt.date(2026, 3, 15), ["2025/26"], "not before", id="the observed season"
        ),
        pytest.param(
            dt.date(2026, 3, 15), ["latest"], "Not a season", id="not a season"
        ),
    ],
)
def test_rejects_wrong_input(
    db: Session, demo_date: dt.date, seasons: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_ensemble(db, CELL, demo_date, seasons=seasons)


def test_the_ensemble_seasons_are_inside_the_stored_history() -> None:
    first_season_start = dt.date(int(ENSEMBLE_SEASONS[0][:4]), 9, 1)
    assert first_season_start >= HISTORY_START
