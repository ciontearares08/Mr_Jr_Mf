"""Download daily weather for one field from DMI's open APIs.

Most values come from one DMI 10 km grid cell in the Climate Data API. The grid
values are interpolated from all DMI stations and exist from 2011. The grid has
no minimum wind, so wind_min comes from the hourly values of one weather station
in the Meteorological Observation API. The APIs are open and need no key.

Units are already the ones APSIM uses, so no value is converted:
    maxt, mint  degC
    rain        mm
    radn        MJ/m2 per day (DMI documents W/m2, but the daily grid values are
                daily totals in MJ/m2, which matches station W/m2 * 0.0864)
    wind_speed  m/s (mean of the day)
    wind_min    m/s (lowest 10-minute mean of the day)
    wind_max    m/s (strongest 3-second gust of the day)
    rh          %
"""

import datetime as dt
import json
import threading
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo

import httpx

GRID_URL = "https://opendataapi.dmi.dk/v2/climateData/collections/10kmGridValue/items"
OBSERVATION_URL = "https://opendataapi.dmi.dk/v2/metObs/collections/observation/items"

# APSIM column -> DMI daily grid parameter.
# The "mean_daily_max_temp" and "mean_daily_min_temp" parameters exist only per
# month, so daily rows use "max_temp_w_date" and "min_temp".
PARAMETERS = {
    "maxt": "max_temp_w_date",
    "mint": "min_temp",
    "rain": "acc_precip",
    "radn": "mean_radiation",
    "wind_speed": "mean_wind_speed",
    "wind_max": "max_wind_speed_3sec",
    "rh": "mean_relative_hum",
}
# Hourly station parameter. The daily wind_min is the lowest hourly value.
MIN_WIND_PARAMETER = "wind_min_past1h"
COLUMNS = (*PARAMETERS, "wind_min")
# APSIM cannot run without these columns.
REQUIRED_COLUMNS = ("maxt", "mint", "rain", "radn", "wind_min", "wind_max")

# A day with fewer hourly values than this gets no wind_min, because the
# lowest of a few hours is higher than the real minimum of the day.
MIN_HOURS_PER_DAY = 20
DANISH_TIME = ZoneInfo("Europe/Copenhagen")

FIRST_DAY_WITH_GRID_DATA = dt.date(2011, 1, 1)
GRID_PAGE_SIZE = 10_000
OBSERVATION_PAGE_SIZE = 10_000
# Hourly data from 2011 fits in about 15 pages, so this many pages means DMI
# paging is broken.
MAX_PAGES_PER_PARAMETER = 100
REQUEST_TIMEOUT_SECONDS = 60

# DMI sends 429 when we ask too often and 5xx during short outages.
# We wait 1, 2 and then 4 seconds before we try again, and then give up.
# If DMI says how long to wait (the Retry-After header), we wait that long,
# but never more than MAX_RETRY_WAIT_SECONDS.
RETRY_WAIT_SECONDS = (1, 2, 4)
MAX_RETRY_WAIT_SECONDS = 60
TEMPORARY_ERROR_STATUSES = {429, 500, 502, 503, 504}

Feature = dict[str, Any]
Page = dict[str, Any]


class DownloadCancelled(Exception):
    """Another parameter failed, so this parameter stopped its download."""


class DmiPagingError(Exception):
    """DMI kept sending "next" links, so the download would never end."""


class DmiResponseError(Exception):
    """DMI sent a page that is not a list of features."""


class NoWeatherData(Exception):
    """DMI has no values for a column that APSIM needs, for the whole date range."""


@dataclass(frozen=True)
class WeatherDay:
    """One day of weather in APSIM units. A value is None when DMI has no data."""

    date: dt.date
    maxt: float | None
    mint: float | None
    rain: float | None
    radn: float | None
    wind_speed: float | None
    wind_min: float | None
    wind_max: float | None
    rh: float | None


class Download(NamedTuple):
    """One parameter to download and how to turn its features into daily values."""

    source: str  # The cell or station, for error messages.
    url: str
    params: dict[str, Any]
    parse: Callable[[list[Feature]], dict[dt.date, float]]


def fetch_daily_weather(
    cell_id: str,
    wind_station_id: str,
    start: dt.date,
    end: dt.date,
    client: httpx.Client | None = None,
) -> list[WeatherDay]:
    """Return one WeatherDay per date from start to end, both inclusive.

    A day without data gets None. If a column in REQUIRED_COLUMNS has no value
    on any day, this raises NoWeatherData.

    If you pass a client, you own it and this function leaves it open.
    """
    check_date_range(start, end)
    if client is not None:
        return fetch_all_parameters(client, cell_id, wind_station_id, start, end)
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as own_client:
        return fetch_all_parameters(own_client, cell_id, wind_station_id, start, end)


def check_date_range(start: dt.date, end: dt.date) -> None:
    """Raise ValueError for a range that DMI cannot have data for."""
    if start > end:
        raise ValueError(f"start ({start}) is after end ({end})")
    if start < FIRST_DAY_WITH_GRID_DATA:
        raise ValueError(
            f"start ({start}) is before {FIRST_DAY_WITH_GRID_DATA}, "
            "the first day with DMI grid data"
        )


def fetch_all_parameters(
    client: httpx.Client,
    cell_id: str,
    wind_station_id: str,
    start: dt.date,
    end: dt.date,
) -> list[WeatherDay]:
    """Download all parameters at the same time and merge them into days.

    After the first error, the other downloads stop at their next request or
    retry wait. We wait for them to stop before we raise the error, so no
    thread uses the client after this function returns.
    """
    downloads = {
        column: Download(
            cell_id,
            GRID_URL,
            grid_params(cell_id, parameter, start, end),
            parse_daily_values,
        )
        for column, parameter in PARAMETERS.items()
    }
    downloads["wind_min"] = Download(
        wind_station_id,
        OBSERVATION_URL,
        min_wind_params(wind_station_id, start, end),
        parse_daily_min,
    )

    # The parameters do not depend on each other, so one thread per parameter
    # makes the total wait about as long as the slowest single parameter.
    stop_downloads = threading.Event()
    pool = ThreadPoolExecutor(max_workers=len(downloads))
    try:
        column_of_download: dict[Future[list[Feature]], str] = {
            pool.submit(
                fetch_features, client, download.url, download.params, stop_downloads
            ): column
            for column, download in downloads.items()
        }
        values_by_column: dict[str, dict[dt.date, float]] = {}
        for future in as_completed(column_of_download):
            column = column_of_download[future]
            values_by_column[column] = downloads[column].parse(future.result())
    finally:
        stop_downloads.set()
        pool.shutdown(wait=True, cancel_futures=True)

    days = merge_days(values_by_column, start, end)
    for column in REQUIRED_COLUMNS:
        if all(getattr(day, column) is None for day in days):
            download = downloads[column]
            raise NoWeatherData(
                f"DMI has no {download.params['parameterId']} values for "
                f"{download.source} from {start} to {end}"
            )
    return days


def grid_params(
    cell_id: str, parameter: str, start: dt.date, end: dt.date
) -> dict[str, Any]:
    """Return the query for the daily grid values of one parameter."""
    # DMI filters on the UTC start of each day, but a Danish day starts at
    # 22:00 or 23:00 UTC the day before. We ask for one extra day and let
    # merge_days drop the dates outside the range.
    day_before = start - dt.timedelta(days=1)
    return {
        "cellId": cell_id,
        "parameterId": parameter,
        "timeResolution": "day",
        "datetime": f"{day_before}T00:00:00Z/{end}T23:59:59Z",
        "limit": GRID_PAGE_SIZE,
    }


def min_wind_params(station_id: str, start: dt.date, end: dt.date) -> dict[str, Any]:
    """Return the query for the hourly min wind of one station."""
    # The Danish days run from 22:00 or 23:00 UTC the day before start to 22:00
    # or 23:00 UTC on end. One extra day on each side covers both, and
    # parse_daily_min drops the incomplete days at the edges.
    day_before = start - dt.timedelta(days=1)
    day_after = end + dt.timedelta(days=1)
    return {
        "stationId": station_id,
        "parameterId": MIN_WIND_PARAMETER,
        "datetime": f"{day_before}T00:00:00Z/{day_after}T00:00:00Z",
        "limit": OBSERVATION_PAGE_SIZE,
    }


def fetch_features(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    stop_downloads: threading.Event,
) -> list[Feature]:
    """Return all features of one DMI query, following the "next" links."""
    query = str(httpx.URL(url, params=params))  # For error messages.

    # DMI sends a "next" link even on the last page, so we read pages until a
    # page is empty or has no "next" link.
    features: list[Feature] = []
    next_links_seen: set[str] = set()
    next_params: dict[str, Any] | None = params
    for _ in range(MAX_PAGES_PER_PARAMETER):
        page = get_page_with_retries(client, url, next_params, stop_downloads)
        # An empty "features" list ends the paging, but a page without the key
        # is an error answer, for example {"message": "..."}.
        if "features" not in page:
            raise DmiResponseError(
                f"No 'features' in the DMI answer to {query}: {str(page)[:200]}"
            )
        page_features = page["features"]
        if not page_features:
            return features
        features += page_features

        url = find_next_link(page)
        if url is None:
            return features
        if url in next_links_seen:
            raise DmiPagingError(f"DMI sent the same next link twice: {url}")
        next_links_seen.add(url)
        next_params = None  # The next link already holds all query parameters.

    raise DmiPagingError(
        f"DMI sent more than {MAX_PAGES_PER_PARAMETER} pages for {query}"
    )


def day_of(feature: Feature) -> dt.date | None:
    """Return the Danish date of a feature, or None if it has no "from".

    "from" is in Danish time, for example "2026-06-04T00:00:00.001000+02:00",
    so its first 10 characters are the local date.
    """
    start_of_day = feature.get("properties", {}).get("from")
    if not start_of_day:
        return None
    return dt.date.fromisoformat(start_of_day[:10])


def get_page_with_retries(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None,
    stop_downloads: threading.Event,
) -> Page:
    """GET one page of JSON. Try again after a wait when DMI has a temporary error.

    Raises DownloadCancelled as soon as stop_downloads is set.
    """
    for default_wait_seconds in RETRY_WAIT_SECONDS:
        if stop_downloads.is_set():
            raise DownloadCancelled
        try:
            return get_page(client, url, params)
        except Exception as error:
            if not is_temporary_error(error):
                raise
            wait_seconds = max(default_wait_seconds, retry_after_seconds(error))
        # Event.wait returns True at once when another download fails.
        if stop_downloads.wait(min(wait_seconds, MAX_RETRY_WAIT_SECONDS)):
            raise DownloadCancelled

    # Last attempt: any error now goes to the caller.
    return get_page(client, url, params)


def get_page(client: httpx.Client, url: str, params: dict[str, Any] | None) -> Page:
    """GET one page of JSON and raise httpx.HTTPStatusError for any error status."""
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def is_temporary_error(error: Exception) -> bool:
    """Return True for an error that can go away if we try again later."""
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in TEMPORARY_ERROR_STATUSES
    # A timeout, a dropped connection, or a 200 with a cut-off or HTML body,
    # which a proxy can send during a short outage.
    return isinstance(error, (httpx.TransportError, json.JSONDecodeError))


def retry_after_seconds(error: Exception) -> float:
    """Return the wait in seconds that DMI asks for, or 0 if it asks for none.

    Only the number-of-seconds form of Retry-After is read. The date form is
    treated as no wait, so the normal retry wait applies.
    """
    if not isinstance(error, httpx.HTTPStatusError):
        return 0
    try:
        return max(0.0, float(error.response.headers.get("Retry-After", 0)))
    except ValueError:
        return 0


def find_next_link(page: Page) -> str | None:
    """Return the URL of the next page, or None if the page has no "next" link."""
    for link in page.get("links", []):
        if link.get("rel") == "next":
            return link.get("href")
    return None


def parse_daily_values(features: list[Feature]) -> dict[dt.date, float]:
    """Map each Danish date to its value.

    A feature without a value or a date is skipped, so that day becomes None
    in merge_days. If DMI sends the same date twice, the most recently
    calculated value wins. A feature without "calculatedAt" counts as the oldest.
    """
    newest_by_date: dict[dt.date, tuple[dt.datetime, float]] = {}
    for feature in features:
        properties = feature.get("properties", {})
        value = properties.get("value")
        date = day_of(feature)
        if value is None or date is None:
            continue
        calculated_at = parse_calculated_at(properties.get("calculatedAt"))
        if date in newest_by_date and newest_by_date[date][0] >= calculated_at:
            continue
        newest_by_date[date] = (calculated_at, value)
    return {date: value for date, (_, value) in newest_by_date.items()}


def parse_daily_min(features: list[Feature]) -> dict[dt.date, float]:
    """Map each Danish date to the lowest of its hourly values.

    A date with fewer than MIN_HOURS_PER_DAY hourly values is skipped, so that
    day becomes None in merge_days. If DMI sends the same hour twice, the later
    feature wins.
    """
    value_by_hour: dict[dt.datetime, float] = {}
    for feature in features:
        properties = feature.get("properties", {})
        value = properties.get("value")
        observed = properties.get("observed")
        if value is None or observed is None:
            continue
        value_by_hour[dt.datetime.fromisoformat(observed)] = value

    values_by_date: dict[dt.date, list[float]] = defaultdict(list)
    for end_of_hour, value in value_by_hour.items():
        values_by_date[danish_date_of_hour(end_of_hour)].append(value)
    return {
        date: min(values)
        for date, values in values_by_date.items()
        if len(values) >= MIN_HOURS_PER_DAY
    }


def danish_date_of_hour(end_of_hour: dt.datetime) -> dt.date:
    """Return the Danish date of an hourly value.

    DMI stamps each hourly value at the end of its hour, in UTC. The value
    stamped 22:00 UTC in summer covers 23:00 to 24:00 Danish time, so we take
    the middle of the hour before we convert it.
    """
    middle_of_hour = end_of_hour - dt.timedelta(minutes=30)
    return middle_of_hour.astimezone(DANISH_TIME).date()


OLDEST_POSSIBLE_TIME = dt.datetime.min.replace(tzinfo=dt.UTC)


def parse_calculated_at(text: str | None) -> dt.datetime:
    """Parse "calculatedAt". DMI sends it without a zone, in UTC.

    A missing timestamp gives the oldest possible time, so any value with a
    timestamp replaces it.
    """
    if text is None:
        return OLDEST_POSSIBLE_TIME
    timestamp = dt.datetime.fromisoformat(text)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=dt.UTC)
    return timestamp


def merge_days(
    values_by_column: dict[str, dict[dt.date, float]], start: dt.date, end: dt.date
) -> list[WeatherDay]:
    """Combine the per-column values into one WeatherDay per date."""
    days = []
    date = start
    while date <= end:
        days.append(
            WeatherDay(
                date=date,
                **{column: values_by_column[column].get(date) for column in COLUMNS},
            )
        )
        date += dt.timedelta(days=1)
    return days
