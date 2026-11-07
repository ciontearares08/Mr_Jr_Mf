from pathlib import Path

from sim.apsim import run_season

WEATHER_PATH = Path(__file__).parent / "fixtures" / "Copenhagen_Weather.met"


def test_run_season_returns_one_row_per_day_of_the_season() -> None:
    df = run_season(weather_path=WEATHER_PATH, sowing_date="15-Apr")

    # 15-Apr to harvest ripe in early September
    assert 130 <= len(df) <= 200
    assert df["date"].iloc[0].startswith("2025-04-15")
    assert df["stage"].iloc[0] == "Sowing"
    assert df["stage"].iloc[-1] == "HarvestRipe"

    assert {"date", "lai", "zadoks", "stage", "biomass", "yield"} <= set(df.columns)
    assert [f"sw_{n}" for n in range(1, 8)] == [
        c for c in df.columns if c.startswith("sw_")
    ]
    assert [f"paw_{n}" for n in range(1, 8)] == [
        c for c in df.columns if c.startswith("paw_")
    ]
