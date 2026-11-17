"""Find the DMI weather station nearest to a field.

The DMI 10 km grid has no minimum wind, so that value comes from a station.
We look up the station once, when the field is created, and save its ID.
"""

import json
import logging
import math
import threading
import time
from dataclasses import dataclass

import httpx
from shapely.geometry.base import BaseGeometry

from api.weather.dmi import (
    MIN_WIND_PARAMETER,
    REQUEST_TIMEOUT_SECONDS,
    DmiPagingError,
    DmiResponseError,
    fetch_features,
)
from api.weather.grid import WGS84_TO_UTM32

STATION_URL = "https://opendataapi.dmi.dk/v2/metObs/collections/station/items"
# DMI adds or closes a station a few times a year, so one download a day is enough.
STATION_CACHE_SECONDS = 24 * 60 * 60
# If a refresh fails, we keep the old list and try again after this time.
STATION_RETRY_SECONDS = 60 * 60
# The errors that mean DMI did not give us a usable station list.
DMI_ERRORS = (httpx.HTTPError, json.JSONDecodeError, DmiResponseError, DmiPagingError)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Station:
    station_id: str
    lon: float
    lat: float


def find_wind_station(
    geometry: BaseGeometry, client: httpx.Client | None = None
) -> str:
    """Return the ID of the min wind station nearest to a WGS84 (lon, lat) field.

    If you pass a client, you own it and this function leaves it open.
    """
    point = geometry.representative_point()
    if client is not None:
        stations = fetch_min_wind_stations(client)
    else:
        stations = cached_min_wind_stations()
    return nearest_station(stations, lat=point.y, lon=point.x).station_id


# The last good download, and the time.monotonic() value of the next refresh.
_station_cache: list[Station] | None = None
_next_refresh = 0.0
# Sync routes run in a threadpool. The lock makes concurrent requests wait for
# one download instead of each starting its own.
_station_lock = threading.Lock()


def cached_min_wind_stations() -> list[Station]:
    """Return the min wind stations, downloaded at most once a day.

    If a refresh fails, this returns the old list and tries again in an hour.
    If there is no old list, the error goes to the caller.
    """
    global _station_cache, _next_refresh
    with _station_lock:
        if _station_cache is not None and time.monotonic() < _next_refresh:
            return _station_cache
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                _station_cache = fetch_min_wind_stations(client)
            _next_refresh = time.monotonic() + STATION_CACHE_SECONDS
        except DMI_ERRORS as error:
            if _station_cache is None:
                raise
            logger.warning(
                "Station list refresh failed, keeping the old list: %s", error
            )
            _next_refresh = time.monotonic() + STATION_RETRY_SECONDS
        return _station_cache


def wind_station_or_none(geometry: BaseGeometry) -> str | None:
    """Return the nearest min wind station, or None if DMI does not answer.

    The weather service fills a None value later, so a DMI outage does not
    block field creation.
    """
    try:
        return find_wind_station(geometry)
    except DMI_ERRORS as error:
        logger.warning("No min wind station for the field: %s", error)
        return None


def fetch_min_wind_stations(client: httpx.Client) -> list[Station]:
    """Return the active Danish stations that measure the hourly min wind."""
    params = {"status": "Active", "limit": 10_000}
    # The station list is one download, so nothing can cancel it.
    features = fetch_features(client, STATION_URL, params, threading.Event())

    # DMI keeps one row per version of a station. Only the current version
    # has no "validTo".
    stations = {}
    for feature in features:
        properties = feature["properties"]
        if (
            properties.get("country") == "DNK"
            and properties.get("validTo") is None
            and MIN_WIND_PARAMETER in properties.get("parameterId", [])
        ):
            lon, lat = feature["geometry"]["coordinates"][:2]
            station_id = properties["stationId"]
            stations[station_id] = Station(station_id, lon=lon, lat=lat)
    if not stations:
        raise DmiResponseError("DMI lists no active Danish station with min wind")
    return list(stations.values())


def nearest_station(stations: list[Station], lat: float, lon: float) -> Station:
    """Return the station nearest to the WGS84 point.

    We measure in UTM zone 32N metres, which is exact enough inside Denmark.
    """
    easting, northing = WGS84_TO_UTM32.transform(lon, lat)

    def distance_m(station: Station) -> float:
        station_easting, station_northing = WGS84_TO_UTM32.transform(
            station.lon, station.lat
        )
        return math.hypot(station_easting - easting, station_northing - northing)

    return min(stations, key=distance_m)
