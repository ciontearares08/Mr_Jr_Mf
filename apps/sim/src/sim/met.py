"""Write APSIM .met weather files from daily weather rows.

APSIM reads weather only from .met files. The API owns the weather table, so it
sends the sim the rows of one cell, and the sim writes the file into its own
temp folder with write_met and passes the path to run_season.

A single missing day is filled from the day before and the day after, and each
fill is logged. A longer gap raises WeatherGapError, because a guess over
several days could change the simulated crop.
"""

import dataclasses
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from os import PathLike
from statistics import mean

logger = logging.getLogger(__name__)

# The weather columns of the .met file, in file order.
MET_COLUMNS = ("radn", "maxt", "mint", "rain")

ONE_DAY = dt.timedelta(days=1)


@dataclasses.dataclass(frozen=True)
class WeatherDay:
    """The weather of one day. None means the value is missing."""

    date: dt.date
    radn: float | None  # solar radiation, MJ/m^2
    maxt: float | None  # maximum temperature, °C
    mint: float | None  # minimum temperature, °C
    rain: float | None  # mm


class WeatherGapError(ValueError):
    """The weather has a gap that write_met cannot fill."""


def write_met(
    days: Iterable[WeatherDay],
    latitude: float,
    path: str | PathLike[str],
    longitude: float | None = None,
) -> None:
    """Write the days as an APSIM .met file, from the first day to the last.

    A date without a row, or a None value, is a missing day. A single missing
    day is filled (see fill_single_missing_days). Raises WeatherGapError for a
    longer gap, and ValueError when the days do not cover all 12 calendar
    months, because tav and amp need them (see tav_and_amp).

    APSIM does not need the longitude, so it is written only when given.
    """
    complete_days = fill_single_missing_days(days)
    tav, amp = tav_and_amp(complete_days)

    lines = ["[weather.met.weather]", f"latitude = {latitude:.2f}"]
    if longitude is not None:
        lines.append(f"longitude = {longitude:.2f}")
    lines += [
        f"tav = {tav:.1f}",
        f"amp = {amp:.1f}",
        "year day radn maxt mint rain",
        "() () (MJ/m^2/day) (oC) (oC) (mm)",
    ]
    for day in complete_days:
        day_of_year = day.date.timetuple().tm_yday
        lines.append(
            f"{day.date.year} {day_of_year} "
            f"{day.radn:.2f} {day.maxt:.2f} {day.mint:.2f} {day.rain:.2f}"
        )
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")


def fill_single_missing_days(days: Iterable[WeatherDay]) -> list[WeatherDay]:
    """Return one complete day per date, from the first date to the last.

    Each column is filled on its own. A value that is missing on one day only
    gets the mean of the day before and the day after, which is a linear
    interpolation over one day. Each fill is logged as a warning.

    Raises WeatherGapError, with every gap that is too long to fill, when a
    column misses two or more days in a row, or misses the first or last day.
    Raises ValueError when there are no days or a date comes twice.
    """
    rows_by_date = rows_by_unique_date(days)
    dates = dates_between(min(rows_by_date), max(rows_by_date))

    filled_columns = {}
    too_long = []
    for column in MET_COLUMNS:
        values = []
        for date in dates:
            row = rows_by_date.get(date)
            values.append(None if row is None else getattr(row, column))

        for first, last in list(missing_runs(values)):
            is_inside = first > 0 and last < len(values) - 1
            if first == last and is_inside:
                values[first] = mean([values[first - 1], values[first + 1]])
                logger.warning(
                    "Filled the missing %s on %s with %.2f, the mean of the day "
                    "before and the day after",
                    column,
                    dates[first],
                    values[first],
                )
            else:
                too_long.append(f"{column} {dates[first]} to {dates[last]}")
        filled_columns[column] = values

    if too_long:
        raise WeatherGapError(
            "Only a single missing day between two known days can be filled, "
            f"but these gaps are longer or at an edge: {', '.join(too_long)}"
        )

    return [
        WeatherDay(date, *(filled_columns[column][i] for column in MET_COLUMNS))
        for i, date in enumerate(dates)
    ]


def tav_and_amp(days: Sequence[WeatherDay]) -> tuple[float, float]:
    """Return APSIM's tav and amp for these days.

    APSIM uses them for the soil temperature. Each calendar month gets the mean
    of its daily mean temperatures, over all years in `days`. tav is the mean
    of those 12 monthly means, and amp is the warmest minus the coldest.
    """
    daily_means_by_month: dict[int, list[float]] = defaultdict(list)
    for day in days:
        daily_means_by_month[day.date.month].append((day.maxt + day.mint) / 2)
    if len(daily_means_by_month) < 12:
        raise ValueError(
            "tav and amp need days in all 12 calendar months, "
            f"but these days cover only {len(daily_means_by_month)}"
        )

    monthly_means = [mean(temps) for temps in daily_means_by_month.values()]
    return mean(monthly_means), max(monthly_means) - min(monthly_means)


def rows_by_unique_date(days: Iterable[WeatherDay]) -> dict[dt.date, WeatherDay]:
    """Return the days by date. Raises ValueError for no days or a repeated date."""
    rows_by_date: dict[dt.date, WeatherDay] = {}
    for day in days:
        if day.date in rows_by_date:
            raise ValueError(f"{day.date} comes more than once")
        rows_by_date[day.date] = day
    if not rows_by_date:
        raise ValueError("There are no days to write")
    return rows_by_date


def missing_runs(values: Sequence[float | None]) -> Iterator[tuple[int, int]]:
    """Yield the first and last index of each run of None values in a row."""
    first = None
    for i, value in enumerate(values):
        if value is None and first is None:
            first = i
        elif value is not None and first is not None:
            yield first, i - 1
            first = None
    if first is not None:
        yield first, len(values) - 1


def dates_between(start: dt.date, end: dt.date) -> list[dt.date]:
    """Return every date from start to end, both included."""
    return [start + ONE_DAY * n for n in range((end - start).days + 1)]
