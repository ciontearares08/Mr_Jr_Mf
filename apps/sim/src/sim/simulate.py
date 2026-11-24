"""Run the members of an ensemble: one APSIM season per member.

run_members writes one weather file per member and runs all members in one
APSIM process (run_seasons). APSIM spends most of a run on fixed start-up work,
so one process for the whole ensemble is much faster than one per member, and
APSIM spreads the simulations over the CPUs of the container by itself.
"""

import datetime as dt
import logging
import tempfile
import threading
import time
from pathlib import Path

import pandas as pd

from sim.apsim import SeasonResult, run_seasons
from sim.met import WeatherDay, write_met
from sim.schemas import DailyRow, Member, MemberResult, MemberStatus, SimulateRequest

logger = logging.getLogger(__name__)

# One ensemble at a time. APSIM already uses every CPU for one ensemble, so a
# second one at the same time would only make both slower and need twice the
# memory. FastAPI runs this sync code in a thread pool, so a thread lock is
# enough as long as the service runs one uvicorn process.
_one_ensemble_at_a_time = threading.Lock()


def run_members(request: SimulateRequest) -> list[MemberResult]:
    """Run every member of the request and return the results in request order.

    A member that fails gets status "failed" and an error message; the other
    members are not affected.
    """
    if request.sowing_window is None:
        window = None
    else:
        window = (request.sowing_window.start, request.sowing_window.end)

    # The .met files only live as long as this request
    with tempfile.TemporaryDirectory() as temp_dir:
        met_paths: dict[str, Path] = {}
        write_errors: dict[str, Exception] = {}
        for number, member in enumerate(request.members):
            path = Path(temp_dir) / f"member_{number}.met"
            try:
                write_met(
                    [WeatherDay(**row.model_dump()) for row in member.met],
                    latitude=request.latitude,
                    path=path,
                    longitude=request.longitude,
                )
            # WeatherGapError (a gap of more than one day) is a ValueError
            except ValueError as error:
                write_errors[member.season] = error
                continue
            met_paths[member.season] = path

        with _one_ensemble_at_a_time:
            # Started inside the lock: waiting for another ensemble is not run time
            started = time.perf_counter()
            seasons = _run_or_fail_all(met_paths, request.sowing_date, window)
        runtime_ms = _milliseconds_since(started)

    return [
        _result_of(member, write_errors.get(member.season), seasons, runtime_ms)
        for member in request.members
    ]


def _run_or_fail_all(
    met_paths: dict[str, Path],
    sowing_date: dt.date | None,
    sowing_window: tuple[dt.date, dt.date] | None,
) -> dict[str, SeasonResult | Exception]:
    """Run the seasons. If APSIM itself fails, every season gets that error."""
    if not met_paths:
        return {}
    # Catch everything on purpose: the request still answers with a result per
    # member, and the API stores the error on each run
    try:
        return run_seasons(
            met_paths, sowing_date=sowing_date, sowing_window=sowing_window
        )
    except Exception as error:
        logger.exception("APSIM did not run the ensemble")
        return dict.fromkeys(met_paths, error)


def _result_of(
    member: Member,
    write_error: Exception | None,
    seasons: dict[str, SeasonResult | Exception],
    runtime_ms: int,
) -> MemberResult:
    """Return the result of one member."""
    if write_error is not None:
        # The member failed before APSIM ran, so it has no run time
        return _failed(member, write_error, runtime_ms=0)

    season = seasons[member.season]
    if isinstance(season, Exception):
        return _failed(member, season, runtime_ms)

    try:
        daily = daily_rows(season.rows)
    except Exception as error:  # noqa: BLE001
        return _failed(member, error, runtime_ms)

    return MemberResult(
        season=member.season,
        status=MemberStatus.ok,
        runtime_ms=runtime_ms,
        sowing_date=season.sowing_date,
        daily=daily,
    )


def _failed(member: Member, error: Exception, runtime_ms: int) -> MemberResult:
    return MemberResult(
        season=member.season,
        status=MemberStatus.failed,
        runtime_ms=runtime_ms,
        error=f"{type(error).__name__}: {error}",
    )


def daily_rows(rows: pd.DataFrame) -> list[DailyRow]:
    """Turn the rows of run_season() into DailyRows."""
    sw_columns = _layer_columns(rows, "sw")
    paw_columns = _layer_columns(rows, "paw")

    # pandas marks a missing value as NaN, which JSON cannot hold, so use None
    rows = rows.astype(object).where(rows.notna(), None)

    daily = []
    for row in rows.to_dict("records"):
        daily.append(
            DailyRow(
                date=row["date"].date(),
                # APSIM leaves stage empty on days when no new stage starts
                stage=row["stage"] or None,
                zadoks=row["zadoks"],
                lai=row["lai"],
                biomass=row["biomass"],
                biomass_n=row["biomass_n"],
                grain_yield=row["yield"],
                grain_protein=row["grain_protein"],
                grain_size=row["grain_size"],
                grain_number=row["grain_number"],
                grain_wt=row["grain_wt"],
                grain_n=row["grain_n"],
                sw=[row[column] for column in sw_columns],
                paw=[row[column] for column in paw_columns],
            )
        )
    return daily


def _layer_columns(rows: pd.DataFrame, name: str) -> list[str]:
    """Return the columns of one value per soil layer in layer order.

    For example sw_1, sw_2 ... sw_7. Sorted by the number, so sw_10 would come
    after sw_9 and not after sw_1.
    """
    columns = [column for column in rows.columns if column.startswith(f"{name}_")]
    return sorted(columns, key=lambda column: int(column.split("_")[1]))


def _milliseconds_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
