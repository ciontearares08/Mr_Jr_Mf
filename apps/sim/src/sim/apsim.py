import copy
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "wheat.apsimx"
RUN_TIMEOUT_SECONDS = 300
# MessageType of an error in APSIM's _Messages table (1 is a warning)
APSIM_ERROR = 0

COLUMNS = {
    "Clock.Today": "date",
    "SowingDate": "sowing_date",
    "Wheat.LAI": "lai",
    "Wheat.Phenology.Zadok.Stage": "zadoks",
    "Wheat.Phenology.CurrentStageName": "stage",
    "Wheat.AboveGround.Wt": "biomass",
    "Wheat.AboveGround.N": "biomass_n",
    "Yield": "yield",
    "Wheat.Grain.Protein": "grain_protein",
    "Wheat.Grain.Size": "grain_size",
    "Wheat.Grain.Number": "grain_number",
    "Wheat.Grain.Total.Wt": "grain_wt",
    "Wheat.Grain.Total.N": "grain_n",
    "Wheat.Structure.TotalStemPopn": "stems",
}
# Per-layer columns, for example "Soil.SoilWater.SW(3)" becomes "sw_3". SW is
# volumetric (mm/mm) and PAWmm is in mm, so "Soil.SoilWater.PAWmm(3)" becomes "paw_3"
LAYER_COLUMN = re.compile(r"^Soil\.SoilWater\.(SW|PAW)(?:mm)?\((\d+)\)$")
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

    This is run_seasons() with one weather file. It raises the error of that
    season instead of returning it.
    """
    result = run_seasons(
        {"season": weather_path},
        sowing_date=sowing_date,
        sowing_window=sowing_window,
        model_path=model_path,
    )["season"]
    if isinstance(result, Exception):
        raise result
    return result


def run_seasons(
    weather_paths: Mapping[str, str | Path],
    sowing_date: dt.date | None = None,
    sowing_window: tuple[dt.date, dt.date] | None = None,
    model_path: str | Path = MODEL_PATH,
) -> dict[str, SeasonResult | Exception]:
    """Run one wheat season per weather file, all in one APSIM process.

    APSIM spends most of a run on fixed start-up work: .NET loads the model and
    compiles the manager scripts. With one simulation per weather file in one
    .apsimx file, that work happens once, and APSIM runs the simulations on
    several threads. In S3-04 testing, 10 seasons took about 2.5 s this way,
    against about 2 s for one season alone.

    Returns a result per name, in the order of weather_paths. A season that
    fails gets its error (FileNotFoundError, ValueError or ApsimError) instead
    of a SeasonResult, and the other seasons are not affected. Raises ValueError
    for a wrong sowing date or window, because that fails every season, and
    ApsimError when APSIM itself does not run.
    """
    start, end = _sowing_start_and_end(sowing_date, sowing_window)
    template = json.loads(Path(model_path).read_text(encoding="utf-8"))

    results: dict[str, SeasonResult | Exception] = {}
    simulations: dict[str, dict] = {}  # APSIM simulation name -> simulation node
    names: dict[str, str] = {}  # APSIM simulation name -> name in weather_paths
    for number, (name, weather_path) in enumerate(weather_paths.items()):
        try:
            simulation = _simulation_for(
                template, weather_path, start, end, sowing_date
            )
        except (FileNotFoundError, ValueError) as error:
            results[name] = error
            continue
        # Names like "2018/19" are not safe in APSIM, so each run gets its own
        simulation["Name"] = f"season_{number}"
        simulations[simulation["Name"]] = simulation
        names[simulation["Name"]] = name

    if simulations:
        outputs = _run_simulations(template, list(simulations.values()))
        for simulation_name, name in names.items():
            results[name] = outputs.get(
                simulation_name, ApsimError("APSIM wrote no rows for this season.")
            )

    return {name: results[name] for name in weather_paths}


def _simulation_for(
    template: dict,
    weather_path: str | Path,
    start: dt.date,
    end: dt.date,
    sowing_date: dt.date | None,
) -> dict:
    """Return a copy of the template's simulation node set up for one weather file."""
    weather_path = Path(weather_path).resolve()
    if not weather_path.is_file():
        raise FileNotFoundError(f"Weather file not found: {weather_path}")

    first_day, last_day = _weather_dates(weather_path)
    if start < first_day or end > last_day:
        raise ValueError(
            f"The sowing dates {start} to {end} are outside the weather file, "
            f"which covers {first_day} to {last_day}."
        )

    simulation = copy.deepcopy(_template_simulation(template))
    _set_inputs(
        simulation,
        weather_path,
        clock=(first_day, last_day),
        sowing=(start, end),
        fixed_date=sowing_date is not None,
    )
    return simulation


def _template_simulation(model: dict) -> dict:
    """Return the one simulation node of the model file."""
    simulations = [
        child
        for child in model["Children"]
        if child["$type"].startswith("Models.Core.Simulation,")
    ]
    if len(simulations) != 1:
        raise ApsimError(
            f"The model must have exactly one simulation, not {len(simulations)}"
        )
    return simulations[0]


def _run_simulations(
    template: dict, simulations: list[dict]
) -> dict[str, SeasonResult | ApsimError]:
    """Run the simulations in one APSIM process and return a result per name."""
    template_simulation = _template_simulation(template)
    model = dict(template)
    model["Children"] = simulations + [
        child for child in template["Children"] if child is not template_simulation
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        # APSIM writes a .db next to the model, so each run gets its own folder
        model_path = Path(temp_dir) / "wheat.apsimx"
        model_path.write_text(json.dumps(model), encoding="utf-8")

        try:
            # APSIM exits with 1 when any simulation fails, but it still writes
            # the others, so the exit code alone does not fail the run
            run = subprocess.run(
                [apsim_models_path(), model_path],
                check=False,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as e:
            raise ApsimError(
                f"APSIM run took longer than {RUN_TIMEOUT_SECONDS} seconds."
            ) from e

        db_path = model_path.with_suffix(".db")
        if not db_path.is_file():
            raise ApsimError(
                f"APSIM wrote no output database (exit code {run.returncode}).\n"
                f"STDOUT: {run.stdout[-2000:]}\nSTDERR: {run.stderr[-2000:]}"
            )

        with closing(sqlite3.connect(db_path)) as conn:
            try:
                report = pd.read_sql_query(
                    "SELECT s.Name AS simulation, r.* FROM Report r "
                    "JOIN _Simulations s ON s.ID = r.SimulationID",
                    conn,
                )
                errors = pd.read_sql_query(
                    "SELECT s.Name AS simulation, m.Message AS message "
                    "FROM _Messages m JOIN _Simulations s ON s.ID = m.SimulationID "
                    f"WHERE m.MessageType = {APSIM_ERROR}",
                    conn,
                )
            except pd.errors.DatabaseError as e:
                raise ApsimError(
                    f"APSIM wrote no Report table (exit code {run.returncode}).\n"
                    f"STDOUT: {run.stdout[-2000:]}"
                ) from e

    error_by_simulation = errors.groupby("simulation")["message"].first().to_dict()
    results: dict[str, SeasonResult | ApsimError] = {}
    for simulation in simulations:
        name = simulation["Name"]
        if name in error_by_simulation:
            # A simulation that failed part way can still have rows, so the
            # error wins over the rows
            results[name] = ApsimError(_short_error(error_by_simulation[name]))
            continue
        rows = report[report["simulation"] == name].drop(columns="simulation")
        if rows.empty:
            continue
        try:
            results[name] = _season_result(rows.reset_index(drop=True))
        except ApsimError as error:
            results[name] = error
    return results


def _season_result(report: pd.DataFrame) -> SeasonResult:
    """Turn the Report rows of one simulation into a SeasonResult."""
    rows = _season_rows(_rename_columns(report))
    rows["date"] = pd.to_datetime(rows["date"])
    rows["sowing_date"] = pd.to_datetime(rows["sowing_date"])
    return SeasonResult(rows=rows, sowing_date=rows["date"].iloc[0].date())


def _short_error(message: str) -> str:
    """Return the APSIM error without the file name and the .NET stack trace.

    APSIM writes "ERROR in file: ...", "Simulation name: ...", the exception
    lines and then the stack trace, whose lines start with "at ".
    """
    lines = [line.strip() for line in message.splitlines()]
    kept = [
        line
        for line in lines
        if line
        and not line.startswith(("ERROR in file:", "Simulation name:", "at ", "---"))
    ]
    return "APSIM failed: " + " ".join(kept[:3])


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
    missing = [column for column in names if column not in report.columns]
    if missing:
        raise ApsimError(f"The APSIM Report is missing these columns: {missing}")
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
