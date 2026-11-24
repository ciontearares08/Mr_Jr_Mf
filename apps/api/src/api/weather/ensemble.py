"""Build the ensemble weather for one demo date (S4-34).

The app replays the 2025/26 season. On the demo date D, the weather up to D is
known, and the weather after D is not. The ensemble fills the unknown part with
the weather of past seasons: each member is the observed 2025/26 weather up to
and including D, then the same calendar days of one past season. The spread of
the APSIM runs over the members gives the date ranges and the daily bands.

As D moves later, more of every member is observed weather, so the members
agree more and the ranges narrow. On the last day of the season, every member
is the observed season.

The seasons and N come from S3-05: N = 10, the seasons 2015/16 to 2024/25. Their
weather starts on HISTORY_START in api.weather.store.

build_ensemble does not download anything. Load the weather first with
api.weather.store.fetch_missing.
"""

import calendar
import datetime as dt
from collections.abc import Sequence
from typing import TypedDict

from sqlalchemy.orm import Session

from api.weather.dmi import dates_between
from api.weather.store import MET_COLUMNS, stored_rows

# The season the app replays
OBSERVED_SEASON = "2025/26"

# The past seasons of the ensemble, oldest first (S3-05)
ENSEMBLE_SEASONS = tuple(f"{year}/{(year + 1) % 100:02d}" for year in range(2015, 2025))


class MetRow(TypedDict):
    """One day of a member, with the columns the sim's .met file needs.

    A value is None when no weather is stored for it. The sim fills a single
    missing day and fails the member for a longer gap.
    """

    date: dt.date
    radn: float | None
    maxt: float | None
    mint: float | None
    rain: float | None


def season_dates(season: str) -> tuple[dt.date, dt.date]:
    """Return the first and last day of a season, for example "2018/19".

    A season runs from 1 September to 31 August.
    """
    try:
        first_year = int(season.split("/")[0])
    except ValueError as error:
        raise ValueError(f"Not a season: {season!r}") from error
    return dt.date(first_year, 9, 1), dt.date(first_year + 1, 8, 31)


def same_day_in(date: dt.date, years_back: int) -> dt.date:
    """Return the same calendar day `years_back` years earlier.

    29 February only exists in leap years. When the observed season has it and
    the past year does not, the past season repeats its 28 February. When the
    past season has it and the observed season does not (2026 is not a leap
    year), the past 29 February is never asked for, so it is dropped.
    """
    year = date.year - years_back
    if date.month == 2 and date.day == 29 and not calendar.isleap(year):
        return dt.date(year, 2, 28)
    return date.replace(year=year)


def build_ensemble(
    db: Session,
    cell_id: str,
    demo_date: dt.date,
    seasons: Sequence[str] = ENSEMBLE_SEASONS,
    observed_season: str = OBSERVED_SEASON,
) -> dict[str, list[MetRow]]:
    """Return the weather of each member, by past season, in the order of seasons.

    Every member has one row for every day of the observed season, oldest
    first. The rows up to and including demo_date are the same in every member.

    Raises ValueError when demo_date is not in the observed season, or when a
    season is not before the observed season.
    """
    start, end = season_dates(observed_season)
    if not start <= demo_date <= end:
        raise ValueError(
            f"The demo date {demo_date} is not in the {observed_season} season "
            f"({start} to {end})"
        )
    if not seasons:
        raise ValueError("The ensemble needs at least one past season")

    observed_dates = dates_between(start, end)
    shifts = {season: years_before(season, start) for season in seasons}

    # One query for everything: the observed season and every past season
    oldest_needed = start.replace(year=start.year - max(shifts.values()))
    weather = {row.date: row for row in stored_rows(db, cell_id, oldest_needed, end)}

    observed = [met_row(date, weather.get(date)) for date in observed_dates]
    known_days = sum(1 for date in observed_dates if date <= demo_date)

    ensemble = {}
    for season, years_back in shifts.items():
        future = [
            met_row(date, weather.get(same_day_in(date, years_back)))
            for date in observed_dates[known_days:]
        ]
        ensemble[season] = observed[:known_days] + future
    return ensemble


def years_before(season: str, observed_start: dt.date) -> int:
    """Return how many years the season starts before the observed season."""
    season_start, _ = season_dates(season)
    years_back = observed_start.year - season_start.year
    if years_back < 1:
        raise ValueError(
            f"The season {season} is not before the observed season, which "
            f"starts on {observed_start}"
        )
    return years_back


def met_row(date: dt.date, row: object | None) -> MetRow:
    """Return the .met columns of a stored row under the observed date."""
    values = {column: getattr(row, column, None) for column in MET_COLUMNS}
    return MetRow(date=date, **values)
