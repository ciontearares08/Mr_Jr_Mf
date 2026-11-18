import dataclasses
import datetime as dt
import logging
from pathlib import Path

import pytest

from sim.apsim import run_season
from sim.met import (
    MET_COLUMNS,
    WeatherDay,
    WeatherGapError,
    dates_between,
    fill_single_missing_days,
    tav_and_amp,
    write_met,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read_met(path: Path) -> list[WeatherDay]:
    """Return the days of a .met file written in our layout."""
    days = []
    for line in data_lines(path):
        year, day_of_year, radn, maxt, mint, rain = line.split()
        date = dt.date(int(year), 1, 1) + dt.timedelta(days=int(day_of_year) - 1)
        days.append(
            WeatherDay(date, float(radn), float(maxt), float(mint), float(rain))
        )
    return days


def data_lines(path: Path) -> list[str]:
    """Return the lines after the units line of a .met file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    units_line = next(i for i, line in enumerate(lines) if line.startswith("()"))
    return lines[units_line + 1 :]


def one_year(start: dt.date = dt.date(2025, 1, 1)) -> list[WeatherDay]:
    """Return 365 complete days. The temperature of a day is its month number."""
    return [
        WeatherDay(date, radn=10.0, maxt=date.month, mint=date.month, rain=1.0)
        for date in dates_between(start, start + dt.timedelta(days=364))
    ]


def test_write_met_matches_the_copenhagen_file(tmp_path: Path) -> None:
    reference = FIXTURES / "Copenhagen_Weather.met"
    path = tmp_path / "weather.met"

    write_met(read_met(reference), latitude=55.67, longitude=12.56, path=path)

    written = path.read_text(encoding="utf-8").splitlines()
    expected = reference.read_text(encoding="utf-8").splitlines()
    # tav and amp in the reference file were set by hand. We compute them from
    # the year itself, so only those two lines differ.
    assert written[3:5] == ["tav = 9.9", "amp = 17.0"]
    assert expected[3:5] == ["tav = 8.5", "amp = 15.0"]
    assert written[:3] + written[5:] == expected[:3] + expected[5:]


def test_write_met_leaves_out_the_longitude_when_not_given(tmp_path: Path) -> None:
    path = tmp_path / "weather.met"

    write_met(one_year(), latitude=55.6789, path=path)

    assert path.read_text(encoding="utf-8").splitlines()[:6] == [
        "[weather.met.weather]",
        "latitude = 55.68",
        "tav = 6.5",
        "amp = 11.0",
        "year day radn maxt mint rain",
        "() () (MJ/m^2/day) (oC) (oC) (mm)",
    ]


def test_write_met_writes_the_day_of_the_year_across_new_year(tmp_path: Path) -> None:
    path = tmp_path / "weather.met"

    write_met(one_year(start=dt.date(2025, 9, 1)), latitude=55.67, path=path)

    lines = data_lines(path)
    assert lines[0].startswith("2025 244 ")
    assert lines[121].startswith("2025 365 ")
    assert lines[122].startswith("2026 1 ")
    assert lines[-1].startswith("2026 243 ")


def test_tav_and_amp_use_the_monthly_means() -> None:
    tav, amp = tav_and_amp(one_year())

    # The monthly means are 1 to 12.
    assert tav == pytest.approx(6.5)
    assert amp == pytest.approx(11.0)


def test_tav_and_amp_need_all_12_months() -> None:
    with pytest.raises(ValueError, match="cover only 2"):
        tav_and_amp(one_year()[:59])


def test_a_day_without_a_row_is_filled_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    days = one_year()
    days[10] = dataclasses.replace(days[10], radn=12.0, rain=3.0)
    missing = days.pop(11)
    days[11] = dataclasses.replace(days[11], radn=14.0, rain=0.0)

    with caplog.at_level(logging.WARNING, logger="sim.met"):
        filled = fill_single_missing_days(days)

    assert len(filled) == 365
    assert filled[11] == WeatherDay(missing.date, radn=13.0, maxt=1, mint=1, rain=1.5)
    assert len(caplog.records) == len(MET_COLUMNS)
    assert "radn on 2025-01-12 with 13.00" in caplog.text


def test_only_the_missing_value_of_a_day_is_filled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    days = one_year()
    days[100] = dataclasses.replace(days[100], rain=None)

    with caplog.at_level(logging.WARNING, logger="sim.met"):
        filled = fill_single_missing_days(days)

    assert filled[100] == dataclasses.replace(days[100], rain=1.0)
    assert len(caplog.records) == 1
    assert "rain on 2025-04-11" in caplog.text


def test_two_missing_days_in_a_row_raise() -> None:
    days = one_year()
    days[50] = dataclasses.replace(days[50], maxt=None)
    del days[51]

    with pytest.raises(WeatherGapError, match="maxt 2025-02-20 to 2025-02-21"):
        fill_single_missing_days(days)


def test_every_long_gap_is_listed() -> None:
    days = one_year()
    del days[200:203]
    days[0] = dataclasses.replace(days[0], mint=None)

    with pytest.raises(WeatherGapError) as error:
        fill_single_missing_days(days)

    assert "mint 2025-01-01 to 2025-01-01" in str(error.value)
    assert "radn 2025-07-20 to 2025-07-22" in str(error.value)
    assert "rain 2025-07-20 to 2025-07-22" in str(error.value)


def test_a_missing_last_day_raises() -> None:
    days = one_year()
    days[-1] = dataclasses.replace(days[-1], radn=None)

    with pytest.raises(WeatherGapError, match="radn 2025-12-31 to 2025-12-31"):
        fill_single_missing_days(days)


def test_a_repeated_date_raises() -> None:
    days = one_year()
    days.append(days[0])

    with pytest.raises(ValueError, match="2025-01-01 comes more than once"):
        fill_single_missing_days(days)


def test_no_days_raise() -> None:
    with pytest.raises(ValueError, match="no days"):
        fill_single_missing_days([])


def test_apsim_runs_with_a_written_file(tmp_path: Path) -> None:
    days = read_met(FIXTURES / "Copenhagen_2025-26.met")
    # Drop a day in the season, so the run also uses a filled day.
    del days[100]
    path = tmp_path / "weather.met"

    write_met(days, latitude=55.67, longitude=12.58, path=path)
    season = run_season(weather_path=path, sowing_date=dt.date(2025, 10, 1))

    assert season.sowing_date == dt.date(2025, 10, 1)
    assert season.rows["stage"].iloc[-1] == "HarvestRipe"
