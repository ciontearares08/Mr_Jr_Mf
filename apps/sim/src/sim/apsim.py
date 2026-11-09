import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from dataclasses import dataclass
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
# APSIm writes dates as day-month --> 15-apr
MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]


class ApsimError(RuntimeError):
    """APSIM did not run, or its output has no usable season."""


@dataclass(frozen=True)
class SeasonResult:
    """One season: a row per day from sowing to harvest ripe, and the sowing day."""

    rows: pd.DataFrame
    sowing_date: dt.date


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
    sowing_date: dt.date | None = None,
    # added sowing window if a specific date isn't provided, instead a start and end date is used
    sowing_window: tuple[dt.date, dt.date] | None = None,
    model_path: str | Path = MODEL_PATH,
) -> SeasonResult:
    """Run one wheat season and return one row per day, from sowing to harvest ripe.

    Give either sowing_date (the crop is sown on exactly that day) or
    sowing_window (APSIM's sowing rule picks a day inside it). The clock runs
    from the first to the last day of the weather file.
    """
    start, end = _sowing_start_and_end(sowing_date, sowing_window)
    weather_path = Path(weather_path).resolve()  # check for missing file
    if not weather_path.is_file():
        raise FileNotFoundError(f"Weather file not found: {weather_path}")

    with tempfile.TemporaryDirectory() as temp_dir:
        # APSIM writes a .db next to the model, so each run gets its own folder
        temp_model_path = Path(temp_dir) / "wheat.apsimx"
        model = json.loads(Path(model_path).read_text(encoding="utf-8"))
        first_day, last_day = _weather_dates(weather_path)
        _set_inputs(
            model,
            weather_path,
            clock=(first_day, last_day),
            sowing=(start, end),
            fixed_date=sowing_date is not None,
        )
        temp_model_path.write_text(json.dumps(model, indent=2), encoding="utf-8")

        try:
            run = subprocess.run(
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

        db_path = temp_model_path.with_suffix(".db")
        if not db_path.is_file():
            raise ApsimError(f"APSIM wrote no output database.\nSTDOUT: {run.stdout}")

        with closing(sqlite3.connect(temp_model_path.with_suffix(".db"))) as conn:
            try:
                report = pd.read_sql_query("SELECT * FROM Report", conn)
            except pd.errors.DatabaseError as e:
                raise ApsimError(
                    f"APSIM wrote no Report table.\nSTDOUT: {run.stdout}"
                ) from e
        if report.empty:
            raise ApsimError(f"APSIM wrote an empty Report.\nSTDOUT: {run.stdout}")

    rows = _season_rows(_rename_columns(report))
    rows["dates"] = pd.to_datetime(rows["dates"])
    return SeasonResult(rows=rows, sowing_date=rows["date"].iloc[0].date())


# function to return a start and end date to the sowing window
def _sowing_start_and_end(
    sowing_date: dt.date | None, sowing_window: tuple[dt.date, dt.date] | None
) -> tuple[dt.date, dt.date]:
    """Return the first and last allowed sowing day. A fixed date is a one-day window."""
    if sowing_date is not None and sowing_window is not None:
        raise ValueError("Give either sowing_date or sowing_window, not both or none.")
    if sowing_date is not None:
        return sowing_date, sowing_date
    if sowing_window is None:
        raise ValueError("Give either sowing_date or sowing_window.")
    start, end = sowing_window
    if start > end:
        raise ValueError(f"The sowing window starts ({start}) after it ends ({end}).")
    return start, end


def _weather_dates(weather_path: Path) -> tuple[dt.date, dt.date]:
    """finds the first and last day in .met file. run_season() uses the 2 dates
    as the start and end date for the APSIM clock, this is done so that APSIM runs over
    exactly these dates(days) the weather files cover. So whether the calender year is 2025 or
    winter season from 2025-2026, APSIM runs the model for whatever season"""

    """Each data line starts with the year and the day of the year, for example
    "2025 1 0.72 7.12 4.10 16.26". Header lines do not start with two numbers.
    """
    days = []
    for line in weather_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()  # reads every line and splits line on spaces
        # these skips header lines such as lat or long, only date lines have whole numbers
        # (year and day of the year)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            year, day_of_year = int(parts[0]), int(parts[1])
            days.append(dt.date(year, 1, 1) + dt.timedelta(days=day_of_year - 1))
    if not days:
        raise ValueError(f"The weather file has no data lines: {weather_path}")
    return days[0], days[-1]


def _apsim_day_month(date: dt.date) -> str:
    """Format a date the way the APSIM sowing rule reads it, for example "15-apr"."""
    return f"{date.day}-{MONTHS[date.month - 1]}"


def _set_inputs(
    node: dict | list,
    weather_path: Path,
    clock: tuple[dt.date, dt.date],
    sowing: tuple[dt.date, dt.date],
    fixed_date: bool,
) -> None:
    """Set the weather file and the sowing date in the model JSON."""
    if isinstance(node, list):
        for child in node:
            _set_inputs(child, weather_path, clock, sowing, fixed_date)
        return
    if not isinstance(node, dict):
        return

    if node.get("$type") == "Models.Climate.Weather, Models":
        node["FileName"] = str(weather_path)
    if node.get("$type") == "Models.Clock, Models":
        # convert to ISO std
        node["Start"] = f"{clock[0].isoformat()}T00:00:00"
        node["End"] = f"{clock[1].isoformat()}T00:00:00"
    if node.get("Name") == "Sow using a variable rule":
        # Sow on exactly this day: a one-day window, with the rain and soil water checks off
        new_values = {
            "StartDate": _apsim_day_month(sowing[0]),
            "EndDate": _apsim_day_month(sowing[1]),
        }
        if fixed_date:
            # Sow on exactly this day: turn the rain and soil water checks off
            new_values |= {"MinESW": "-1", "MinRain": "-1"}

        for param in node["Parameters"]:
            if param["Key"] in new_values:
                param["Value"] = new_values[param["Key"]]

    for value in node.values():
        _set_inputs(value, weather_path, clock, sowing, fixed_date)


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
    if sown.empty:
        raise ApsimError(
            "APSIM did not sow the crop. With a sowing window, the soil may have been too dry inside the whole window."
        )
    ripe = daily.index[(daily["stage"] == "HarvestRipe") & (daily.index > sown[0])]
    if ripe.empty:
        raise ApsimError(
            "The crop did not reach Harvest Ripe before the weather file ends. Failed to do in the simulation clock"
        )
    return daily.loc[sown[0] : ripe[0]].reset_index(drop=True)
