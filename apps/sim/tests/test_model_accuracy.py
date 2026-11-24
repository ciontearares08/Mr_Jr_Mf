"""Regression test for the wheat model: yield against the Flakkebjerg field trials.

The production soil is the Flakkebjerg soil (Kumar et al. 2023, Plants 12:986, Table 4), so the
model can be checked against the 48 Flakkebjerg points (8 trials, 2016-2020, 0 to 303 kg N/ha).
Each point is one simulation with the trial's sowing date and N dates. All 48 run in one APSIM call.

The limits are set from the calibrated model with some margin. If a change to wheat.apsimx makes
the error clearly worse, this test fails.
"""

import copy
import csv
import datetime as dt
import json
import math
import sqlite3
import statistics
import subprocess
from contextlib import closing
from pathlib import Path

import pandas as pd

from sim.apsim import MODEL_PATH, apsim_models_path

FIXTURES = Path(__file__).parent / "fixtures"
WEATHER_PATH = FIXTURES / "Flakkebjerg_2015-2020.met"
TRIALS_PATH = FIXTURES / "kumar2023_flakkebjerg.csv"

# Kumar et al. 2023 report an RMSE of 1296 to 1491 kg/ha for their calibrated model.
MAX_RMSE = 1150  # kg/ha
MAX_ABS_BIAS = 600  # kg/ha

# Applies the N of one trial on its real dates (yyyy-mm-dd:kg N/ha;...)
FERTILISE_ON_DATES = """using Models.Core; using Models.Soils; using System;
namespace Models { [Serializable] public class Script : Model {
 [Link] private Clock Clock; [Link] private Fertiliser Fertiliser;
 [Description("Applications (yyyy-mm-dd:kg N/ha, semicolon separated)")] public string Schedule { get; set; }
 [EventSubscribe("DoManagement")] private void OnDoManagement(object s, EventArgs e) {
  if (string.IsNullOrWhiteSpace(Schedule)) return;
  string today = Clock.Today.ToString("yyyy-MM-dd");
  foreach (string item in Schedule.Split(';')) {
   string[] p = item.Split(':');
    if (p[0].Trim() == today) Fertiliser.Apply(amount: double.Parse(p[1]), type: "NH4NO3N");
  } } } }"""

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


def _find(node: dict, name: str) -> dict:
    """Return the first node with this name, searching the children depth first."""
    if node.get("Name") == name:
        return node
    for child in node.get("Children", []):
        found = _find(child, name)
        if found:
            return found
    return {}


def _trial_simulation(template: dict, point: dict) -> dict:
    """One simulation for one trial point: sowing date, N dates and clock of that trial."""
    sim = copy.deepcopy(template)
    sim["Name"] = point["point"]
    sowing = dt.date.fromisoformat(point["sowing_date"])
    _find(sim, "Clock").update(
        Start=f"{sowing.year}-08-01T00:00:00",
        # before the next sowing window
        End=f"{point['harvest_year']}-09-01T00:00:00",
    )
    _find(sim, "Weather")["FileName"] = str(WEATHER_PATH.resolve())

    # Sow on exactly the trial's sowing day, as run_season() does for a fixed date
    day_month = f"{sowing.day}-{MONTHS[sowing.month - 1]}"
    fixed = {
        "StartDate": day_month,
        "EndDate": day_month,
        "MinESW": "-1",
        "MinRain": "-1",
    }
    for param in _find(sim, "Sow using a variable rule")["Parameters"]:
        if param["Key"] in fixed:
            param["Value"] = fixed[param["Key"]]

    # The trial's N replaces the model's own fertiliser managers
    _find(sim, "Fertilise at sowing")["Enabled"] = False
    _find(sim, "Fertilise in spring")["Enabled"] = False
    _find(sim, "Field")["Children"].append(
        {
            "$type": "Models.Manager, Models",
            "CodeArray": FERTILISE_ON_DATES.split("\n"),
            "Parameters": [{"Key": "Schedule", "Value": point["n_schedule"]}],
            "Name": "Fertilise on trial dates",
            "ResourceName": None,
            "Children": [],
            "Enabled": True,
            "ReadOnly": False,
        }
    )
    return sim


def _simulated_yields(points: list[dict], tmp_path: Path) -> dict[str, float]:
    """Run all trial points in one APSIM call and return the yield (kg/ha) per point."""
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    template = next(
        c for c in model["Children"] if c["$type"].startswith("Models.Core.Simulation,")
    )
    others = [c for c in model["Children"] if c is not template]
    model["Children"] = [_trial_simulation(template, p) for p in points] + others

    model_path = tmp_path / "trials.apsimx"
    model_path.write_text(json.dumps(model), encoding="utf-8")
    run = subprocess.run(
        [apsim_models_path(), model_path],
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert run.returncode == 0, (
        f"APSIM failed:\n{run.stdout[-3000:]}\n{run.stderr[-3000:]}"
    )

    with closing(sqlite3.connect(model_path.with_suffix(".db"))) as conn:
        report = pd.read_sql_query(
            "SELECT s.Name AS point, r.Yield AS yield FROM Report r "
            "JOIN _Simulations s ON s.ID = r.SimulationID",
            conn,
        )
    report["yield"] = pd.to_numeric(report["yield"], errors="coerce")
    return report.groupby("point")["yield"].max().to_dict()


def test_yield_matches_the_flakkebjerg_trials(tmp_path: Path) -> None:
    with TRIALS_PATH.open(encoding="utf-8") as f:
        points = list(csv.DictReader(f))
    simulated = _simulated_yields(points, tmp_path)

    assert len(simulated) == len(points), "every trial point should give a yield"
    errors = [simulated[p["point"]] - float(p["yield_obs"]) for p in points]
    rmse = math.sqrt(statistics.mean(e * e for e in errors))
    bias = statistics.mean(errors)
    assert rmse <= MAX_RMSE, f"RMSE {rmse:.0f} kg/ha is above {MAX_RMSE}"
    assert abs(bias) <= MAX_ABS_BIAS, (
        f"bias {bias:+.0f} kg/ha is outside +-{MAX_ABS_BIAS}"
    )

    # The crop must respond to N: every trial yields more at its highest N rate than at 0 N
    for trial in {p["trial"] for p in points}:
        rates = sorted(
            (int(p["n_total"]), simulated[p["point"]])
            for p in points
            if p["trial"] == trial
        )
        assert rates[-1][1] > rates[0][1] + 1000, (
            f"{trial}: no N response ({rates[0][1]:.0f} -> {rates[-1][1]:.0f})"
        )
