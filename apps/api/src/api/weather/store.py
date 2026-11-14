"""Load DMI weather into the weather_daily table and read it back.

These are plain functions, so the API, the worker, tests and a Python shell can
all call them. None of them commits: the caller owns the transaction. To fill a
cell by hand, for example the demo cell, run this in the API devcontainer with
`uv run python`:

    import datetime as dt
    from api.db.session import session_local
    from api.weather.store import HISTORY_START, fetch_missing, missing_days

    with session_local() as db:
        fetch_missing(db, "10km_617_72", "06180", dt.date.today())
        db.commit()
        yesterday = dt.date.today() - dt.timedelta(days=1)
        print(missing_days(db, "10km_617_72", HISTORY_START, yesterday))

The wind station is a parameter because each field stores its own station
(Field.wind_station_id). The table is keyed by cell, so if two fields in one
cell have different stations, the last download of a day sets its wind_min.

A day that DMI has no value for is stored as NULL, never as 0, so 0 mm of rain
always means a dry day. The one exception is wind_min (see NO_WIND_MIN).
"""

import dataclasses
import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Sequence
from os import PathLike
from statistics import mean

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.db.models import WeatherDaily
from api.weather.dmi import (
    COLUMNS,
    DANISH_TIME,
    REQUIRED_COLUMNS,
    WeatherDay,
    check_date_range,
    dates_between,
    fetch_daily_weather,
)
from api.weather.grid import cell_centre

# The first day of the first season we simulate.
HISTORY_START = dt.date(2015, 9, 1)

# The columns of the .met file. Wind is not in it.
MET_COLUMNS = ("radn", "maxt", "mint", "rain")

ONE_DAY = dt.timedelta(days=1)

# The wind_min stored for a day whose station logged too few hourly values.
# DMI's wind_min is almost always 0 (4,083 of the 4,087 known days in the demo
# cell), so 0 is a safe guess. Leaving the day NULL would keep it missing
# forever, and every fetch_missing call would download it again.
NO_WIND_MIN = 0.0


def save_rows(db: Session, cell_id: str, days: Iterable[WeatherDay]) -> int:
    """Insert or update one row per day and return the number of rows.

    A None in a new day keeps the value already stored, so a later download
    with a gap never erases a value.
    """
    rows = [{"cell_id": cell_id, **dataclasses.asdict(day)} for day in days]
    if not rows:
        return 0

    insert_rows = insert(WeatherDaily)
    new_values = insert_rows.excluded
    upsert = insert_rows.on_conflict_do_update(
        index_elements=[WeatherDaily.cell_id, WeatherDaily.date],
        set_={
            **{
                column: func.coalesce(new_values[column], getattr(WeatherDaily, column))
                for column in COLUMNS
            },
            "fetched_at": func.now(),
        },
    )
    # A list of rows makes SQLAlchemy send them in batches, so a long backfill
    # stays under the PostgreSQL limit on parameters per statement.
    db.execute(upsert, rows)
    return len(rows)


def load_range(
    db: Session,
    cell_id: str,
    wind_station_id: str,
    start: dt.date,
    end: dt.date,
    client: httpx.Client | None = None,
) -> int:
    """Download start to end (both inclusive) from DMI and save it.

    The whole range is one download. The DMI client fetches all the years in a
    few pages per parameter, so splitting the range would only add requests.
    DMI errors, for example NoWeatherData, go to the caller, and then nothing
    is saved. Returns the number of rows saved.

    A day that still has no wind_min after the download gets NO_WIND_MIN.

    If you pass a client, you own it and this function leaves it open.
    """
    days = fetch_daily_weather(cell_id, wind_station_id, start, end, client=client)
    saved = save_rows(db, cell_id, days)
    fill_missing_wind_min(db, cell_id, start, end)
    return saved


def fill_missing_wind_min(
    db: Session, cell_id: str, start: dt.date, end: dt.date
) -> None:
    """Set wind_min to NO_WIND_MIN on the stored days that have none.

    This runs after save_rows, so a value stored by an earlier download is
    kept and only days that are still NULL get the guess.
    """
    db.execute(
        update(WeatherDaily)
        .where(
            WeatherDaily.cell_id == cell_id,
            WeatherDaily.date.between(start, end),
            WeatherDaily.wind_min.is_(None),
        )
        .values(wind_min=NO_WIND_MIN)
    )


def fetch_missing(
    db: Session,
    cell_id: str,
    wind_station_id: str,
    until: dt.date,
    client: httpx.Client | None = None,
) -> int:
    """Download the missing days from HISTORY_START to `until` and save them.

    missing_days decides which days are missing. They are downloaded as one
    range, from the first missing day to `until`, so this also fills holes in
    older seasons. A day that DMI never has a grid value for stays missing,
    and every call downloads it again.

    `until` is limited to yesterday, because DMI has no daily values for a day
    that has not ended. Returns 0 without calling DMI when no day is missing,
    otherwise the number of rows saved.
    """
    until = min(until, danish_today() - ONE_DAY)
    gaps = missing_days(db, cell_id, HISTORY_START, until)
    if not gaps:
        return 0

    # DMI calculates the newest days a few hours late. A download of only those
    # days can have no value at all in a required column, and then
    # fetch_daily_weather raises NoWeatherData. The day before the first gap is
    # complete, so including it avoids that.
    start = max(HISTORY_START, gaps[0] - ONE_DAY)
    return load_range(db, cell_id, wind_station_id, start, until, client)


def missing_days(
    db: Session, cell_id: str, start: dt.date, end: dt.date
) -> list[dt.date]:
    """Return the dates from start to end that have no row or a NULL required value."""
    rows = stored_rows(db, cell_id, start, end)
    return dates_without_values(rows, REQUIRED_COLUMNS, start, end)


def write_met(
    db: Session,
    cell_id: str,
    start: dt.date,
    end: dt.date,
    path: str | PathLike[str],
) -> None:
    """Write start to end (both inclusive) as an APSIM .met file.

    A dev-only tool, used once to make the 2025/26 fixture for the sim. Do not
    build on it: the API cannot write files the deployed sim can read, so the
    real version (S3-03) belongs in apps/sim and gets the rows over HTTP.

    Raises ValueError when a day has no value in a .met column, because APSIM
    cannot run with a missing day. A day without wind is fine, because wind is
    not in the file. Also raises ValueError when the range does not include
    every calendar month, because tav and amp need all 12 (see tav_and_amp).
    """
    check_date_range(start, end)
    rows = stored_rows(db, cell_id, start, end)

    gaps = dates_without_values(rows, MET_COLUMNS, start, end)
    if gaps:
        raise ValueError(
            f"{cell_id} is missing {len(gaps)} days from {start} to {end}: "
            f"{list_some(gaps)}"
        )

    tav, amp = tav_and_amp(rows)
    lat, lon = cell_centre(cell_id)
    lines = [
        "[weather.met.weather]",
        f"latitude = {lat:.2f}",
        f"longitude = {lon:.2f}",
        f"tav = {tav:.1f}",
        f"amp = {amp:.1f}",
        "year day radn maxt mint rain",
        "() () (MJ/m^2/day) (oC) (oC) (mm)",
    ]
    for row in rows:
        day_of_year = row.date.timetuple().tm_yday
        lines.append(
            f"{row.date.year} {day_of_year} "
            f"{row.radn:.2f} {row.maxt:.2f} {row.mint:.2f} {row.rain:.2f}"
        )
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")


def tav_and_amp(rows: Sequence[WeatherDaily]) -> tuple[float, float]:
    """Return APSIM's tav and amp for these days.

    APSIM uses them for the soil temperature. Each calendar month gets the mean
    of its daily mean temperatures, over all years in `rows`. tav is the mean
    of those 12 monthly means, and amp is the warmest minus the coldest.
    """
    daily_means_by_month: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        daily_means_by_month[row.date.month].append((row.maxt + row.mint) / 2)
    if len(daily_means_by_month) < 12:
        raise ValueError(
            "tav and amp need days in all 12 calendar months, "
            f"but these days cover only {len(daily_means_by_month)}"
        )

    monthly_means = [mean(temps) for temps in daily_means_by_month.values()]
    return mean(monthly_means), max(monthly_means) - min(monthly_means)


def stored_rows(
    db: Session, cell_id: str, start: dt.date, end: dt.date
) -> Sequence[WeatherDaily]:
    """Return the stored rows of a cell from start to end, oldest first."""
    return db.scalars(
        select(WeatherDaily)
        .where(WeatherDaily.cell_id == cell_id, WeatherDaily.date.between(start, end))
        .order_by(WeatherDaily.date)
    ).all()


def dates_without_values(
    rows: Iterable[WeatherDaily],
    columns: Sequence[str],
    start: dt.date,
    end: dt.date,
) -> list[dt.date]:
    """Return the dates from start to end that have no row or a None in a column."""
    complete_dates = {
        row.date
        for row in rows
        if all(getattr(row, column) is not None for column in columns)
    }
    return [date for date in dates_between(start, end) if date not in complete_dates]


def list_some(dates: list[dt.date], limit: int = 10) -> str:
    """Return the first `limit` dates as text, and how many more there are."""
    shown = ", ".join(str(date) for date in dates[:limit])
    if len(dates) > limit:
        shown += f" and {len(dates) - limit} more"
    return shown


def danish_today() -> dt.date:
    """Today in Denmark. DMI days are Danish days."""
    return dt.datetime.now(DANISH_TIME).date()
