import datetime as dt
from pathlib import Path

import pandas as pd
from sim.apsim import run_season

WEATHER_PATH = Path(__file__).parent / "fixtures" / "Copenhagen_Weather.met"

def test_run_season_returns_one_row_per_day_of_the_season() -> None:
    # 1. Pass a real dt.date object
    sowing = dt.date(2025, 4, 15)
    
    # 2. Extract the dataframe from the SeasonResult dataclass
    result = run_season(weather_path=WEATHER_PATH, sowing_date=sowing)
    df = result.rows

    # 15-Apr to harvest ripe in early September
    assert 130 <= len(df) <= 200
    
    # 3. Compare against a pd.Timestamp, since the column was converted
    assert df["date"].iloc[0] == pd.Timestamp("2025-04-15")
    assert df["stage"].iloc[0] == "Sowing"
    assert df["stage"].iloc[-1] == "HarvestRipe"

    assert {"date", "lai", "zadoks", "stage", "biomass", "yield"} <= set(df.columns)
    assert [f"sw_{n}" for n in range(1, 8)] == [
        c for c in df.columns if c.startswith("sw_")
    ]
    assert [f"paw_{n}" for n in range(1, 8)] == [
        c for c in df.columns if c.startswith("paw_")
    ]