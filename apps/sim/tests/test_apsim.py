import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from sim.apsim import ApsimError, run_season, run_seasons

WEATHER_PATH = Path(__file__).parent / "fixtures" / "Copenhagen_2025-26.met"


def test_run_season_returns_one_row_per_day_of_the_season() -> None:
    # 1. Pass a real dt.date object
    sowing = dt.date(2025, 10, 1)

    # 2. Extract the dataframe from the SeasonResult dataclass
    result = run_season(weather_path=WEATHER_PATH, sowing_date=sowing)
    df = result.rows

    # 1-Oct to harvest ripe in mid-August 2026 (321 days with this weather)
    assert 290 <= len(df) <= 350
    assert result.sowing_date == sowing

    # 3. Compare against a pd.Timestamp, since the column was converted
    assert df["date"].iloc[0] == pd.Timestamp("2025-10-1")
    assert df["stage"].iloc[0] == "Sowing"
    assert df["stage"].iloc[-1] == "HarvestRipe"

    assert {"date", "lai", "zadoks", "stage", "biomass", "yield"} <= set(df.columns)
    assert [f"sw_{n}" for n in range(1, 8)] == [
        c for c in df.columns if c.startswith("sw_")
    ]
    assert [f"paw_{n}" for n in range(1, 8)] == [
        c for c in df.columns if c.startswith("paw_")
    ]


def test_run_season_reports_soil_water_in_mm_and_the_stem_count() -> None:
    df = run_season(weather_path=WEATHER_PATH, sowing_date=dt.date(2025, 10, 1)).rows

    # paw is in mm: the volumetric water above LL15 (0.09) times the 150 mm layer
    first = df.iloc[0]
    assert first["paw_1"] == pytest.approx((first["sw_1"] - 0.09) * 150, abs=0.01)
    # 300 plants per m² start with one stem each, then the crop tillers
    assert first["stems"] == pytest.approx(300)
    assert df["stems"].max() > 500


def test_run_season_sows_inside_the_sowing_window() -> None:
    window_start = dt.date(2025, 9, 15)
    window_end = dt.date(2025, 10, 15)

    result = run_season(
        weather_path=WEATHER_PATH, sowing_window=(window_start, window_end)
    )
    df = result.rows
    # APSIM picks the sowing day, so we only check that it is inside the window
    assert window_start <= result.sowing_date <= window_end
    assert df["date"].iloc[0] == pd.Timestamp(result.sowing_date)
    assert (df["sowing_date"] == pd.Timestamp(result.sowing_date)).all()
    assert df["stage"].iloc[0] == "Sowing"
    assert df["stage"].iloc[-1] == "HarvestRipe"


def broken_weather_file(tmp_path: Path) -> Path:
    """A copy of the weather file with text instead of a number in the middle.

    The checks before APSIM only read the dates, so APSIM itself fails on it.
    """
    lines = WEATHER_PATH.read_text(encoding="utf-8").splitlines()
    year, day_of_year, radn, maxt, mint, _rain = lines[-100].split()
    lines[-100] = f"{year} {day_of_year} {radn} {maxt} {mint} oops"
    path = tmp_path / "broken.met"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_run_seasons_runs_every_season_and_keeps_failures_apart(
    tmp_path: Path,
) -> None:
    results = run_seasons(
        {
            "2018/19": WEATHER_PATH,
            "broken": broken_weather_file(tmp_path),
            "missing": tmp_path / "missing.met",
            "2019/20": WEATHER_PATH,
        },
        sowing_date=dt.date(2025, 10, 1),
    )

    # One result per name, in the order of the request
    assert list(results) == ["2018/19", "broken", "missing", "2019/20"]
    for name in ("2018/19", "2019/20"):
        assert results[name].sowing_date == dt.date(2025, 10, 1)
        assert results[name].rows["stage"].iloc[-1] == "HarvestRipe"
    # The same weather and sowing date give the same season
    assert results["2018/19"].rows.equals(results["2019/20"].rows)

    assert isinstance(results["broken"], ApsimError)
    assert str(results["broken"]).startswith("APSIM failed:")
    # The .NET stack trace is left out of the message
    assert " at " not in str(results["broken"])
    assert isinstance(results["missing"], FileNotFoundError)


def test_run_season_raises_the_apsim_error(tmp_path: Path) -> None:
    with pytest.raises(ApsimError, match="APSIM failed"):
        run_season(
            weather_path=broken_weather_file(tmp_path),
            sowing_date=dt.date(2025, 10, 1),
        )


# The tests below fail before APSIM starts, so they run quickly
def test_run_season_rejects_both_sowing_date_and_sowing_window() -> None:
    sowing = dt.date(2025, 4, 15)
    window = (dt.date(2025, 4, 1), dt.date(2025, 4, 30))

    with pytest.raises(ValueError, match="not both"):
        run_season(weather_path=WEATHER_PATH, sowing_date=sowing, sowing_window=window)


def test_run_season_needs_a_sowing_date_or_a_sowing_window() -> None:
    with pytest.raises(ValueError, match="Give either sowing_date or sowing_window"):
        run_season(weather_path=WEATHER_PATH)


def test_run_season_rejects_a_window_that_ends_before_it_starts() -> None:
    window = (dt.date(2025, 4, 30), dt.date(2025, 4, 1))

    with pytest.raises(ValueError, match="starts .* after it ends"):
        run_season(weather_path=WEATHER_PATH, sowing_window=window)


def test_run_season_rejects_a_missing_weather_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.met"

    with pytest.raises(FileNotFoundError, match="Weather file not found"):
        run_season(weather_path=missing_file, sowing_date=dt.date(2025, 4, 15))


def test_run_season_rejects_sowing_dates_outside_the_weather_file() -> None:
    # The weather file covers 1 Sep 2025 to 31 Aug 2026
    sowing = dt.date(2024, 10, 1)

    with pytest.raises(ValueError, match="outside the weather file"):
        run_season(weather_path=WEATHER_PATH, sowing_date=sowing)
