"""Tests for loading DMI weather into weather_daily. They never call DMI.

test_a_saved_dmi_month_ends_up_in_the_table replays the DMI cassette of
test_dmi.py (Aalborg, June 2026). The other tests replace fetch_daily_weather
with FakeDmi, which returns made-up days and records what was asked for.
"""

import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import WeatherDaily
from api.weather import dmi, store
from api.weather.dmi import REQUIRED_COLUMNS, WeatherDay, dates_between
from api.weather.store import (
    HISTORY_START,
    fetch_missing,
    load_range,
    missing_days,
    save_rows,
    write_met,
)

# A cell nobody uses in the dev database, so its rows come only from the test.
CELL = "10km_610_60"
STATION = "06000"
D = dt.date


def weather_day(date: dt.date, **values: float | None) -> WeatherDay:
    """A complete day with simple values, changed by the keyword arguments."""
    defaults = {
        "maxt": 10.0,
        "mint": 2.0,
        "rain": 1.5,
        "radn": 5.0,
        "wind_speed": 3.0,
        "wind_min": 0.5,
        "wind_max": 9.0,
        "rh": 80.0,
    }
    return WeatherDay(date=date, **(defaults | values))


def save_complete_days(db: Session, start: dt.date, end: dt.date) -> None:
    save_rows(db, CELL, [weather_day(date) for date in dates_between(start, end)])


def stored(db: Session, date: dt.date) -> WeatherDaily | None:
    return db.scalar(
        select(WeatherDaily).where(
            WeatherDaily.cell_id == CELL, WeatherDaily.date == date
        )
    )


class FakeDmi:
    """Stands in for fetch_daily_weather and records the requested ranges.

    Every day is complete, except the days in not_calculated_yet, which have
    no radiation, and the days in no_wind_min. Like the real client, it raises NoWeatherData when a required
    column has no value on any day.
    """

    def __init__(self) -> None:
        self.requests: list[tuple[dt.date, dt.date]] = []
        self.not_calculated_yet: set[dt.date] = set()
        self.no_wind_min: set[dt.date] = set()

    def __call__(
        self,
        cell_id: str,
        wind_station_id: str,
        start: dt.date,
        end: dt.date,
        client: object = None,
    ) -> list[WeatherDay]:
        assert (cell_id, wind_station_id) == (CELL, STATION)
        self.requests.append((start, end))
        days = [weather_day(date) for date in dates_between(start, end)]
        for i, day in enumerate(days):
            if day.date in self.not_calculated_yet:
                days[i] = weather_day(day.date, radn=None)
            if day.date in self.no_wind_min:
                days[i] = weather_day(day.date, wind_min=None)
        for column in REQUIRED_COLUMNS:
            if all(getattr(day, column) is None for day in days):
                raise dmi.NoWeatherData(f"no {column}")
        return days


@pytest.fixture
def fake_dmi(monkeypatch: pytest.MonkeyPatch) -> FakeDmi:
    fake = FakeDmi()
    monkeypatch.setattr(store, "fetch_daily_weather", fake)
    return fake


@pytest.fixture
def yesterday() -> dt.date:
    return store.danish_today() - dt.timedelta(days=1)


# --- A saved DMI answer -----------------------------------------------------


@pytest.fixture
def vcr_cassette_dir() -> str:
    return str(Path(__file__).parent / "cassettes" / "test_dmi")


@pytest.mark.vcr
@pytest.mark.default_cassette("aalborg_june_2026.yaml")
def test_a_saved_dmi_month_ends_up_in_the_table(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The page sizes the cassette was recorded with, see test_dmi.py.
    monkeypatch.setattr(dmi, "GRID_PAGE_SIZE", 10)
    monkeypatch.setattr(dmi, "OBSERVATION_PAGE_SIZE", 10 * 24)
    monkeypatch.setattr(dmi, "RETRY_WAIT_SECONDS", (0, 0, 0))
    cell = "10km_632_55"

    saved = load_range(db, cell, "06030", D(2026, 6, 1), D(2026, 6, 30))

    assert saved == 30
    assert missing_days(db, cell, D(2026, 6, 1), D(2026, 6, 30)) == []
    june_11 = db.get(WeatherDaily, (cell, D(2026, 6, 11)))
    assert june_11 is not None
    assert (
        june_11.maxt,
        june_11.mint,
        june_11.rain,
        june_11.radn,
        june_11.wind_speed,
        june_11.wind_min,
        june_11.wind_max,
        june_11.rh,
    ) == (17.4, 6.5, 5.5, 21.5, 2.6, 0.0, 9.3, 74.5)


# --- save_rows --------------------------------------------------------------


def test_saving_a_day_again_updates_it(db: Session) -> None:
    save_rows(db, CELL, [weather_day(D(2020, 5, 1), rain=1.0)])
    save_rows(db, CELL, [weather_day(D(2020, 5, 1), rain=7.0)])

    row = stored(db, D(2020, 5, 1))
    assert row is not None and row.rain == 7.0


def test_a_gap_in_a_later_download_keeps_the_stored_value(db: Session) -> None:
    save_rows(db, CELL, [weather_day(D(2020, 5, 1), wind_min=0.8)])
    save_rows(db, CELL, [weather_day(D(2020, 5, 1), wind_min=None, rain=3.0)])

    row = stored(db, D(2020, 5, 1))
    assert row is not None
    assert row.wind_min == 0.8
    assert row.rain == 3.0


def test_a_day_without_rain_data_is_stored_as_null_not_zero(db: Session) -> None:
    save_rows(db, CELL, [weather_day(D(2020, 5, 1), rain=None)])

    row = stored(db, D(2020, 5, 1))
    assert row is not None and row.rain is None


def test_saving_no_days_does_nothing(db: Session) -> None:
    assert save_rows(db, CELL, []) == 0


def test_saving_years_of_days_at_once_works(db: Session) -> None:
    # More rows than PostgreSQL allows parameters in one statement.
    save_complete_days(db, D(2011, 1, 1), D(2028, 12, 31))

    assert missing_days(db, CELL, D(2011, 1, 1), D(2028, 12, 31)) == []


# --- load_range -------------------------------------------------------------


def test_load_range_downloads_the_whole_range_at_once(
    db: Session, fake_dmi: FakeDmi
) -> None:
    saved = load_range(db, CELL, STATION, D(2015, 9, 1), D(2017, 3, 1))

    assert fake_dmi.requests == [(D(2015, 9, 1), D(2017, 3, 1))]
    assert saved == len(dates_between(D(2015, 9, 1), D(2017, 3, 1)))
    assert missing_days(db, CELL, D(2015, 9, 1), D(2017, 3, 1)) == []


def test_load_range_saves_nothing_when_dmi_fails(
    db: Session, fake_dmi: FakeDmi
) -> None:
    fake_dmi.not_calculated_yet = {D(2020, 1, 1)}

    with pytest.raises(dmi.NoWeatherData):
        load_range(db, CELL, STATION, D(2020, 1, 1), D(2020, 1, 1))

    assert stored(db, D(2020, 1, 1)) is None


def test_load_range_saves_a_missing_wind_min_as_zero(
    db: Session, fake_dmi: FakeDmi
) -> None:
    fake_dmi.no_wind_min = {D(2020, 1, 2)}

    load_range(db, CELL, STATION, D(2020, 1, 1), D(2020, 1, 3))

    row = stored(db, D(2020, 1, 2))
    assert row is not None and row.wind_min == 0.0
    assert missing_days(db, CELL, D(2020, 1, 1), D(2020, 1, 3)) == []


def test_load_range_keeps_a_stored_wind_min(db: Session, fake_dmi: FakeDmi) -> None:
    save_rows(db, CELL, [weather_day(D(2020, 1, 2), wind_min=0.8)])
    fake_dmi.no_wind_min = {D(2020, 1, 2)}

    load_range(db, CELL, STATION, D(2020, 1, 1), D(2020, 1, 3))

    row = stored(db, D(2020, 1, 2))
    assert row is not None and row.wind_min == 0.8


def test_fetch_missing_starts_at_september_2015_for_an_empty_cell(
    db: Session, fake_dmi: FakeDmi
) -> None:
    fetch_missing(db, CELL, STATION, D(2016, 2, 1))

    assert fake_dmi.requests == [(HISTORY_START, D(2016, 2, 1))]
    assert HISTORY_START == D(2015, 9, 1)


def test_fetch_missing_includes_the_last_complete_day(
    db: Session, fake_dmi: FakeDmi
) -> None:
    save_complete_days(db, HISTORY_START, D(2020, 1, 10))

    fetch_missing(db, CELL, STATION, D(2020, 1, 20))

    assert fake_dmi.requests == [(D(2020, 1, 10), D(2020, 1, 20))]


def test_fetch_missing_downloads_incomplete_days_again(
    db: Session, fake_dmi: FakeDmi
) -> None:
    save_complete_days(db, HISTORY_START, D(2020, 1, 8))
    save_rows(
        db,
        CELL,
        [
            weather_day(D(2020, 1, 9), wind_min=None),
            weather_day(D(2020, 1, 10), radn=None),
        ],
    )

    fetch_missing(db, CELL, STATION, D(2020, 1, 12))

    assert fake_dmi.requests == [(D(2020, 1, 8), D(2020, 1, 12))]
    assert missing_days(db, CELL, HISTORY_START, D(2020, 1, 12)) == []


def test_fetch_missing_fills_a_hole_in_an_older_season(
    db: Session, fake_dmi: FakeDmi
) -> None:
    # 15 June 2017 has no row.
    save_complete_days(db, HISTORY_START, D(2017, 6, 14))
    save_complete_days(db, D(2017, 6, 16), D(2020, 1, 31))

    fetch_missing(db, CELL, STATION, D(2020, 1, 31))

    assert fake_dmi.requests == [(D(2017, 6, 14), D(2020, 1, 31))]
    assert missing_days(db, CELL, HISTORY_START, D(2020, 1, 31)) == []


def test_fetch_missing_backfills_before_a_season_loaded_first(
    db: Session, fake_dmi: FakeDmi
) -> None:
    # How the 2025/26 file was made: one season, with nothing before it.
    save_complete_days(db, D(2025, 9, 1), D(2026, 8, 31))

    fetch_missing(db, CELL, STATION, D(2026, 8, 31))

    assert fake_dmi.requests == [(HISTORY_START, D(2026, 8, 31))]


def test_fetch_missing_does_not_call_dmi_when_up_to_date(
    db: Session, fake_dmi: FakeDmi
) -> None:
    save_complete_days(db, HISTORY_START, D(2020, 1, 10))

    assert fetch_missing(db, CELL, STATION, D(2020, 1, 10)) == 0
    assert fetch_missing(db, CELL, STATION, D(2020, 1, 5)) == 0
    assert fake_dmi.requests == []


def test_fetch_missing_stops_at_yesterday(
    db: Session, fake_dmi: FakeDmi, yesterday: dt.date
) -> None:
    save_complete_days(db, HISTORY_START, yesterday - dt.timedelta(days=2))

    fetch_missing(db, CELL, STATION, yesterday + dt.timedelta(days=30))

    assert fake_dmi.requests == [(yesterday - dt.timedelta(days=2), yesterday)]


def test_fetch_missing_waits_quietly_for_dmi_to_calculate_yesterday(
    db: Session, fake_dmi: FakeDmi, yesterday: dt.date
) -> None:
    save_complete_days(db, HISTORY_START, yesterday - dt.timedelta(days=1))
    fake_dmi.not_calculated_yet = {yesterday}

    # Run twice, as two fields in the same cell would on the same day.
    fetch_missing(db, CELL, STATION, yesterday)
    fetch_missing(db, CELL, STATION, yesterday)

    assert missing_days(db, CELL, HISTORY_START, yesterday) == [yesterday]

    fake_dmi.not_calculated_yet = set()
    fetch_missing(db, CELL, STATION, yesterday)

    assert missing_days(db, CELL, HISTORY_START, yesterday) == []


# --- missing_days -----------------------------------------------------------


def test_missing_days_lists_absent_and_incomplete_days(db: Session) -> None:
    save_rows(
        db,
        CELL,
        [
            weather_day(D(2020, 3, 1)),
            weather_day(D(2020, 3, 2), mint=None),
            # 3 March has no row.
            weather_day(D(2020, 3, 4), rh=None),  # rh is not required.
            weather_day(D(2020, 3, 5), rain=None),
        ],
    )

    assert missing_days(db, CELL, D(2020, 3, 1), D(2020, 3, 5)) == [
        D(2020, 3, 2),
        D(2020, 3, 3),
        D(2020, 3, 5),
    ]


# --- write_met --------------------------------------------------------------

SEASON_START = D(2025, 9, 1)
SEASON_END = D(2026, 8, 31)


def test_write_met_matches_the_fixture_format(db: Session, tmp_path: Path) -> None:
    # January has a daily mean of 0 degC, July 20 degC, every other month 6 degC.
    temperatures_by_month = {1: (4.0, -4.0), 7: (25.0, 15.0)}
    save_rows(
        db,
        CELL,
        [
            weather_day(
                date,
                maxt=temperatures_by_month.get(date.month, (10.0, 2.0))[0],
                mint=temperatures_by_month.get(date.month, (10.0, 2.0))[1],
            )
            for date in dates_between(SEASON_START, SEASON_END)
        ],
    )
    save_rows(db, CELL, [weather_day(SEASON_START, radn=1.234, rain=0.0)])
    path = tmp_path / "out.met"

    write_met(db, CELL, SEASON_START, SEASON_END, path)

    lines = path.read_text().splitlines()
    assert lines[0] == "[weather.met.weather]"
    # 10km_610_60 is the cell from 6100 to 6110 km north and 600 to 610 km east.
    assert lines[1:7] == [
        "latitude = 55.08",
        "longitude = 10.64",
        "tav = 6.7",  # (0 + 20 + 10 * 6) / 12
        "amp = 20.0",  # 20 - 0
        "year day radn maxt mint rain",
        "() () (MJ/m^2/day) (oC) (oC) (mm)",
    ]
    assert lines[7] == "2025 244 1.23 10.00 2.00 0.00"
    assert lines[-1] == "2026 243 5.00 10.00 2.00 1.50"
    assert len(lines) == 7 + 365


def test_write_met_pools_each_month_over_several_years(
    db: Session, tmp_path: Path
) -> None:
    # Every month has a daily mean of 6 degC, except January 2025 at -6 degC.
    # The two Januaries together make one January at 0 degC.
    save_complete_days(db, D(2025, 1, 1), D(2026, 12, 31))
    save_rows(
        db,
        CELL,
        [
            weather_day(date, maxt=-6.0, mint=-6.0)
            for date in dates_between(D(2025, 1, 1), D(2025, 1, 31))
        ],
    )
    path = tmp_path / "out.met"

    write_met(db, CELL, D(2025, 1, 1), D(2026, 12, 31), path)

    lines = path.read_text().splitlines()
    assert lines[3:5] == ["tav = 5.5", "amp = 6.0"]  # (0 + 11 * 6) / 12, 6 - 0


def test_write_met_refuses_a_range_with_gaps(db: Session, tmp_path: Path) -> None:
    # 2 January has no row and 3 January has no rain.
    save_complete_days(db, SEASON_START, D(2026, 1, 1))
    save_rows(db, CELL, [weather_day(D(2026, 1, 3), rain=None)])
    save_complete_days(db, D(2026, 1, 4), SEASON_END)
    path = tmp_path / "out.met"

    with pytest.raises(ValueError, match="missing 2 days.*2026-01-02, 2026-01-03"):
        write_met(db, CELL, SEASON_START, SEASON_END, path)
    assert not path.exists()


def test_write_met_does_not_need_wind(db: Session, tmp_path: Path) -> None:
    save_complete_days(db, SEASON_START, SEASON_END)
    save_rows(db, CELL, [weather_day(D(2026, 1, 3), wind_min=None)])
    path = tmp_path / "out.met"

    write_met(db, CELL, SEASON_START, SEASON_END, path)

    assert path.exists()


def test_write_met_refuses_a_range_shorter_than_a_year(
    db: Session, tmp_path: Path
) -> None:
    save_complete_days(db, D(2026, 9, 1), D(2026, 11, 30))

    with pytest.raises(ValueError, match="all 12 calendar months"):
        write_met(db, CELL, D(2026, 9, 1), D(2026, 11, 30), tmp_path / "out.met")


def test_write_met_refuses_swapped_dates(db: Session, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="is after end"):
        write_met(db, CELL, SEASON_END, SEASON_START, tmp_path / "out.met")
