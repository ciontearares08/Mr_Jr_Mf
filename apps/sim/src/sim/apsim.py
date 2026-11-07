import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path

import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "wheat.apsimx"
RUN_TIMEOUT_SECONDS = 300

COLUMNS = {
    "Clock.Today": "date",
    "Wheat.LAI": "lai",
    "Wheat.Phenology.Zadok.Stage": "zadoks",
    "Wheat.Phenology.CurrentStageName": "stage",
    "Wheat.AboveGround.Wt": "biomass",
    "Yield": "yield",
}
# Per-layer columns, for example "Soil.SoilWater.SW(3)" becomes "sw_3"
LAYER_COLUMN = re.compile(r"^Soil\.SoilWater\.(SW|PAW)\((\d+)\)$")


def apsim_models_path() -> Path:
    """Return the path of the APSIM `Models` executable."""
    bin_dir = os.getenv("APSIM_BIN_PATH")
    if bin_dir:
        return Path(bin_dir) / "Models"
    found = shutil.which("Models")
    if found is None:
        raise FileNotFoundError("APSIM 'Models' not found. Set APSIM_BIN_PATH.")
    return Path(found)


def run_season(
    weather_path: str | Path,
    sowing_date: str,
    model_path: str | Path = MODEL_PATH,
) -> pd.DataFrame:
    """Run one wheat season and return one row per day, from sowing to harvest ripe.

    sowing_date uses the APSIM day-month format, for example "15-Apr".
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # APSIM writes a .db next to the model, so each run gets its own folder
        temp_model_path = Path(temp_dir) / "wheat.apsimx"
        model = json.loads(Path(model_path).read_text(encoding="utf-8"))
        _set_inputs(model, Path(weather_path).resolve(), sowing_date)
        temp_model_path.write_text(json.dumps(model, indent=2), encoding="utf-8")

        try:
            subprocess.run(
                [apsim_models_path(), temp_model_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"APSIM run failed.\nSTDERR: {e.stderr}\nSTDOUT: {e.stdout}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"APSIM run took longer than {RUN_TIMEOUT_SECONDS} seconds."
            ) from e

        with closing(sqlite3.connect(temp_model_path.with_suffix(".db"))) as conn:
            report = pd.read_sql_query("SELECT * FROM Report", conn)

    return _season_rows(_rename_columns(report))


def _set_inputs(node: dict | list, weather_path: Path, sowing_date: str) -> None:
    """Set the weather file and the sowing date in the model JSON."""
    if isinstance(node, list):
        for child in node:
            _set_inputs(child, weather_path, sowing_date)
        return
    if not isinstance(node, dict):
        return

    if node.get("$type") == "Models.Climate.Weather, Models":
        node["FileName"] = str(weather_path)
    if node.get("Name") == "Sow using a variable rule":
        # Sow on exactly this day: a one-day window, with the rain and soil water checks off
        new_values = {
            "StartDate": sowing_date,
            "EndDate": sowing_date,
            "MinESW": "-1",
            "MinRain": "-1",
        }
        for param in node["Parameters"]:
            if param["Key"] in new_values:
                param["Value"] = new_values[param["Key"]]

    for value in node.values():
        _set_inputs(value, weather_path, sowing_date)


def _rename_columns(report: pd.DataFrame) -> pd.DataFrame:
    """Keep the columns that the service uses and give them short names."""
    names = dict(COLUMNS)
    for column in report.columns:
        match = LAYER_COLUMN.match(column)
        if match:
            names[column] = f"{match[1].lower()}_{match[2]}"
    return report[list(names)].rename(columns=names)


def _season_rows(daily: pd.DataFrame) -> pd.DataFrame:
    """Keep the rows from the sowing day to the harvest-ripe day."""
    sown = daily.index[daily["stage"] == "Sowing"]
    ripe = daily.index[daily["stage"] == "HarvestRipe"]
    if sown.empty or ripe.empty:
        raise ValueError(
            "The crop was not sown and harvested within the simulation clock."
        )
    return daily.loc[sown[0] : ripe[0]].reset_index(drop=True)
