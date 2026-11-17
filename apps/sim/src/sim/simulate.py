"""Run the members of an ensemble: one APSIM season per member.

run_members runs several members at the same time, each in its own process.
run_member runs one of them: it writes the member's weather file and runs
APSIM once. It is a top-level function, so the worker processes can import it.
"""

import datetime as dt
import multiprocessing
import os
import tempfile
import time
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pandas as pd

from sim.apsim import run_season
from sim.met import WeatherDay, write_met
from sim.schemas import (
    DailyRow,
    Member,
    MemberResult,
    MemberStatus,
    SimulateRequest,
    SowingWindow,
)


def run_members(request: SimulateRequest) -> list[MemberResult]:
    """Run every member of the request and return the results in request order.

    APSIM uses one CPU core per run, so up to one member per core runs at a time.
    """
    workers = min(len(request.members), os.cpu_count() or 1)
    # "spawn" starts each worker as a fresh Python process. The default on Linux
    # ("fork") copies the web server process with its threads, which can hang.
    spawn = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=workers, mp_context=spawn) as pool:
        futures = [
            pool.submit(
                run_member,
                member,
                request.latitude,
                request.longitude,
                request.sowing_date,
                request.sowing_window,
            )
            for member in request.members
        ]
        # Reading the futures in submit order keeps the results in request order
        return [
            _result_of(future, member)
            for future, member in zip(futures, request.members, strict=True)
        ]


def _result_of(future: Future[MemberResult], member: Member) -> MemberResult:
    """Wait for one member. run_member never raises, so only a crash gets here."""
    try:
        return future.result()
    except BrokenProcessPool:
        # A worker process died, for example because it ran out of memory. The
        # pool cannot be used after that, so every member still waiting fails too.
        return MemberResult(
            season=member.season,
            status=MemberStatus.failed,
            runtime_ms=0,  # unknown: the process died before it could report it
            error="The process running this member stopped unexpectedly",
        )


def run_member(
    member: Member,
    latitude: float,
    longitude: float,
    sowing_date: dt.date | None,
    sowing_window: SowingWindow | None,
) -> MemberResult:
    """Run APSIM for one member and return its result.

    Never raises: any error becomes a failed result with the error message, so
    one bad member does not fail the whole request.
    """
    started = time.perf_counter()
    try:
        days = [
            WeatherDay(
                date=row.date,
                radn=row.radn,
                maxt=row.maxt,
                mint=row.mint,
                rain=row.rain,
            )
            for row in member.met
        ]
        if sowing_window is None:
            window = None
        else:
            window = (sowing_window.start, sowing_window.end)

        # The .met file only lives as long as this run
        with tempfile.TemporaryDirectory() as temp_dir:
            met_path = Path(temp_dir) / "weather.met"
            write_met(days, latitude=latitude, path=met_path, longitude=longitude)
            season = run_season(
                weather_path=met_path, sowing_date=sowing_date, sowing_window=window
            )
        daily = daily_rows(season.rows)

    # Catch everything on purpose: even an unexpected error should fail only
    # this member. Expected errors are WeatherGapError (a gap of more than one
    # day), ValueError (sowing dates outside the weather) and ApsimError.
    except Exception as error:  # noqa: BLE001
        return MemberResult(
            season=member.season,
            status=MemberStatus.failed,
            runtime_ms=_milliseconds_since(started),
            error=f"{type(error).__name__}: {error}",
        )

    return MemberResult(
        season=member.season,
        status=MemberStatus.ok,
        runtime_ms=_milliseconds_since(started),
        sowing_date=season.sowing_date,
        daily=daily,
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
