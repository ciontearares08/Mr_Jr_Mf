import pytest
from pathlib import Path
from sim.apsim import run_season

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def test_run_season_yields_daily_results():
    model_path = FIXTURES_DIR / "wheat.apsimx"
    weather_path = FIXTURES_DIR / "Copenhagen_Weather.met"

    if not model_path.exists() or not weather_path.exists():
        pytest.skip("Fixture files missing.")

    # Act
    df = run_season(
        model_path=model_path,
        weather_path=weather_path,
        sowing_date="15-Oct",
        soil_type=None
    )

    # Assert basic output structure
    assert not df.empty
    assert 150 <= len(df) <= 366, f"Expected daily rows for one season, got {len(df)}"
    
    # Assert standard columns exist
    expected_columns = {'date', 'lai', 'zadoks', 'stage', 'biomass', 'yield', 'paw'}
    assert expected_columns.issubset(set(df.columns))

    # Assert multi-layer soil water (SW) columns were successfully extracted
    sw_cols = [col for col in df.columns if col.startswith('sw_')]
    assert len(sw_cols) > 0, "Expected at least one multi-layer soil water column (sw_1, sw_2, etc.)"