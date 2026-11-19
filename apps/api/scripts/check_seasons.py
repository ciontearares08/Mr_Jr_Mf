"""Check which past seasons have complete weather for one DMI grid cell (S3-05).

The ensemble uses the weather of past seasons (1 September to 31 August) after
the demo date. A season can only be used when APSIM can run on it:

- A single missing day is fine: the sim fills it from the day before and after.
- Two or more missing days in a row are not: write_met refuses to guess them.

The script downloads all seasons from DMI in one go and prints a table. It does
not write to the database, so it is safe to run as often as you like.

Run it in the API devcontainer, from apps/api:

    uv run python scripts/check_seasons.py

DMI's 10 km grid starts on 1 January 2011, so 2011/12 is the first full season.
"""

import argparse
import calendar
import datetime as dt

from api.weather.dmi import FIRST_DAY_WITH_GRID_DATA, WeatherDay, fetch_daily_weather

# The demo field (see api/db/seed.py)
DEMO_CELL = "10km_617_72"
DEMO_WIND_STATION = "06180"  # Københavns Lufthavn (Kastrup)

# The columns APSIM reads from the .met file. Wind is not in it.
MET_COLUMNS = ("radn", "maxt", "mint", "rain")


def season_dates(first_year: int) -> tuple[dt.date, dt.date]:
    """Return the first and last day of a season, for example 2018 -> 2018/19."""
    return dt.date(first_year, 9, 1), dt.date(first_year + 1, 8, 31)


def season_name(first_year: int) -> str:
    return f"{first_year}/{str(first_year + 1)[-2:]}"


def is_missing(day: WeatherDay | None) -> bool:
    """A day is missing when it has no row or no value in a .met column."""
    return day is None or any(getattr(day, column) is None for column in MET_COLUMNS)


def longest_run(missing: list[dt.date]) -> int:
    """Return the most missing days in a row. The dates must be sorted."""
    longest = current = 0
    previous = None
    for date in missing:
        follows_previous = previous is not None and date - previous == dt.timedelta(1)
        current = current + 1 if follows_previous else 1
        longest = max(longest, current)
        previous = date
    return longest


def check_season(first_year: int, by_date: dict[dt.date, WeatherDay]) -> dict:
    """Return the numbers of one season for the table."""
    start, end = season_dates(first_year)
    dates = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    missing = [date for date in dates if is_missing(by_date.get(date))]
    run = longest_run(missing)

    if not missing:
        status = "complete"
    elif run == 1:
        status = "usable (single days get filled)"
    else:
        status = "NOT usable as-is"

    return {
        "season": season_name(first_year),
        "days": len(dates),
        "missing": len(missing),
        "longest_run": run,
        # 29 February has no partner day in 2025/26, so S4-34 has to drop it
        "leap_day": calendar.isleap(first_year + 1),
        "status": status,
        "first_missing": [str(date) for date in missing[:5]],
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", default=DEMO_CELL, help="DMI grid cell id")
    parser.add_argument(
        "--station", default=DEMO_WIND_STATION, help="DMI station for wind_min"
    )
    parser.add_argument(
        "--first", type=int, default=2011, help="First season, by its first year"
    )
    parser.add_argument(
        "--last", type=int, default=2024, help="Last season, by its first year"
    )
    arguments = parser.parse_args()

    if season_dates(arguments.first)[0] < FIRST_DAY_WITH_GRID_DATA:
        parser.error(f"DMI grid data starts on {FIRST_DAY_WITH_GRID_DATA}")
    if arguments.first > arguments.last:
        parser.error("--first must not be after --last")
    return arguments


def main() -> None:
    arguments = parse_arguments()
    start = season_dates(arguments.first)[0]
    end = season_dates(arguments.last)[1]

    # One download for all seasons: DMI pages through all the years at once,
    # so splitting it per season would only add requests
    print(f"Downloading {arguments.cell} from {start} to {end} (this takes a while)")
    days = fetch_daily_weather(arguments.cell, arguments.station, start, end)
    by_date = {day.date: day for day in days}

    seasons = [
        check_season(year, by_date)
        for year in range(arguments.first, arguments.last + 1)
    ]

    print(
        f"\n{'Season':<9}{'Days':>6}{'Missing':>9}{'Longest gap':>13}  Leap day  Status"
    )
    for season in seasons:
        leap = "yes" if season["leap_day"] else ""
        print(
            f"{season['season']:<9}{season['days']:>6}{season['missing']:>9}"
            f"{season['longest_run']:>13}  {leap:<8}  {season['status']}"
        )

    # The first missing dates help to see whether a gap is real or a DMI hiccup
    for season in seasons:
        if season["missing"]:
            print(
                f"  {season['season']} first missing: {', '.join(season['first_missing'])}"
            )

    usable = [s["season"] for s in seasons if s["status"] != "NOT usable as-is"]
    print(f"\nUsable seasons ({len(usable)}): {', '.join(usable)}")


if __name__ == "__main__":
    main()
