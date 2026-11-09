"""Download daily weather for one DMI 10 km grid cell from DMI's Climate Data API.

The grid values are interpolated from all DMI stations and exist from 2011.
The API is open and needs no key.

Units are already the ones APSIM uses, so no value is converted:
    maxt, mint  degC
    rain        mm
    radn        MJ/m2 per day (DMI documents W/m2, but the daily grid values are
                daily totals in MJ/m2, which matches station W/m2 * 0.0864)
    wind_speed  m/s
    rh          %
"""

import datetime as dt
import json
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import httpx

GRID_URL = "https://opendataapi.dmi.dk/v2/climateData/collections/10kmGridValue/items"

# APSIM column -> DMI daily grid parameter.
# The "mean_daily_max_temp" and "mean_daily_min_temp" parameters exist only per
# month, so daily rows use "max_temp_w_date" and "min_temp".
PARAMETERS = {
    "maxt": "max_temp_w_date",
    "mint": "min_temp",
    "rain": "acc_precip",
    "radn": "mean_radiation",
    "wind_speed": "mean_wind_speed",
    "rh": "mean_relative_hum",
}
# APSIM cannot run without these columns.
REQUIRED_COLUMNS = ("maxt", "mint", "rain", "radn")

FIRST_DAY_WITH_GRID_DATA = dt.date(2011, 1, 1)
PAGE_SIZE = 10_000
# Data from 2011 fits in one page, so this many pages means DMI paging is broken.
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
    """DMI sent a page that is not a list of grid features."""


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
    rh: float | None


def fetch_daily_weather(
    cell_id: str, start: dt.date, end: dt.date, client: httpx.Client | None = None
) -> list[WeatherDay]:
    """Return one WeatherDay per date from start to end, both inclusive.

    A day without data gets None. If a column in REQUIRED_COLUMNS has no value
    on any day, this raises NoWeatherData.

    If you pass a client, you own it and this function leaves it open.
    """
    check_date_range(start, end)
    if client is not None:
        return fetch_all_parameters(client, cell_id, start, end)
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as own_client:
        return fetch_all_parameters(own_client, cell_id, start, end)


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
    client: httpx.Client, cell_id: str, start: dt.date, end: dt.date
) -> list[WeatherDay]:
    """Download the six parameters at the same time and merge them into days.

    After the first error, the other downloads stop at their next request or
    retry wait. We wait for them to stop before we raise the error, so no
    thread uses the client after this function returns.
    """
    # The parameters do not depend on each other, so one thread per parameter
    # makes the total wait about as long as the slowest single parameter.
    stop_downloads = threading.Event()
    pool = ThreadPoolExecutor(max_workers=len(PARAMETERS))
    try:
        column_of_download: dict[Future[list[Feature]], str] = {
            pool.submit(
                fetch_features, client, cell_id, parameter, start, end, stop_downloads
            ): column
            for column, parameter in PARAMETERS.items()
        }
        values_by_column = {
            column_of_download[download]: parse_daily_values(download.result())
            for download in as_completed(column_of_download)
        }
    finally:
        stop_downloads.set()
        pool.shutdown(wait=True, cancel_futures=True)

    days = merge_days(values_by_column, start, end)
    for column in REQUIRED_COLUMNS:
        if all(getattr(day, column) is None for day in days):
            raise NoWeatherData(
                f"DMI has no {PARAMETERS[column]} values for {cell_id} "
                f"from {start} to {end}"
            )
    return days


def fetch_features(
    client: httpx.Client,
    cell_id: str,
    parameter: str,
    start: dt.date,
    end: dt.date,
    stop_downloads: threading.Event,
) -> list[Feature]:
    """Return all grid features for one parameter, following the "next" links."""
    # DMI filters on the UTC start of each day, but a Danish day starts at
    # 22:00 or 23:00 UTC the day before. We ask for one extra day and let
    # merge_days drop the dates outside the range.
    day_before = start - dt.timedelta(days=1)
    url = GRID_URL
    params: dict[str, Any] | None = {
        "cellId": cell_id,
        "parameterId": parameter,
        "timeResolution": "day",
        "datetime": f"{day_before}T00:00:00Z/{end}T23:59:59Z",
        "limit": PAGE_SIZE,
    }

    # DMI sends a "next" link even on the last page, so we read pages until a
    # page is empty or has no "next" link.
    features: list[Feature] = []
    next_links_seen: set[str] = set()
    for _ in range(MAX_PAGES_PER_PARAMETER):
        page = get_page_with_retries(client, url, params, stop_downloads)
        # An empty "features" list ends the paging, but a page without the key
        # is an error answer, for example {"message": "..."}.
        if "features" not in page:
            raise DmiResponseError(
                f"No 'features' in the DMI answer for {parameter}: {str(page)[:200]}"
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
        params = None  # The next link already holds all query parameters.

    raise DmiPagingError(
        f"DMI sent more than {MAX_PAGES_PER_PARAMETER} pages for {parameter}"
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
                **{column: values_by_column[column].get(date) for column in PARAMETERS},
            )
        )
        date += dt.timedelta(days=1)
    return days
