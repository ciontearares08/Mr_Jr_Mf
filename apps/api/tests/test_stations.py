"""Tests for the station search. They never call DMI."""

import httpx
import pytest
from shapely.geometry import Point

from api.weather import dmi
from api.weather.dmi import DmiResponseError
from api.weather.stations import (
    Station,
    fetch_min_wind_stations,
    find_wind_station,
    nearest_station,
    wind_station_or_none,
)

# Positions from the DMI station list, November 2026.
AALBORG = Station("06030", lon=9.8505, lat=57.0963)
TYLSTRUP = Station("06031", lon=9.9568, lat=57.1825)
BORNHOLM = Station("06190", lon=14.7537, lat=55.0657)
STATIONS = [TYLSTRUP, BORNHOLM, AALBORG]


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dmi, "RETRY_WAIT_SECONDS", (0, 0, 0))


def station_feature(
    station_id: str,
    country: str = "DNK",
    valid_to: str | None = None,
    parameters: tuple[str, ...] = (dmi.MIN_WIND_PARAMETER,),
) -> dict:
    """One row of the DMI station list with only the keys that we read."""
    return {
        "geometry": {"type": "Point", "coordinates": [9.85, 57.10]},
        "properties": {
            "stationId": station_id,
            "country": country,
            "validTo": valid_to,
            "parameterId": list(parameters),
        },
    }


def client_with_stations(*features: dict) -> httpx.Client:
    page = {"type": "FeatureCollection", "features": list(features), "links": []}
    return httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=page))
    )


@pytest.mark.parametrize(
    ("town", "lat", "lon", "expected"),
    [("Aalborg", 57.0488, 9.9217, AALBORG), ("Rønne", 55.10, 14.70, BORNHOLM)],
)
def test_nearest_station(town: str, lat: float, lon: float, expected: Station) -> None:
    assert nearest_station(STATIONS, lat=lat, lon=lon) == expected, town


def test_only_current_danish_min_wind_stations_are_kept() -> None:
    client = client_with_stations(
        station_feature("06030"),
        station_feature("04202", country="GRL"),
        station_feature("06031", valid_to="2020-01-01T00:00:00Z"),
        station_feature("06032", parameters=("temp_dry",)),
    )

    assert [station.station_id for station in fetch_min_wind_stations(client)] == [
        "06030"
    ]


def test_no_station_is_an_error() -> None:
    client = client_with_stations(station_feature("04202", country="GRL"))
    with pytest.raises(DmiResponseError):
        fetch_min_wind_stations(client)


def test_find_wind_station_returns_the_station_id() -> None:
    client = client_with_stations(station_feature("06030"))
    assert find_wind_station(Point(9.92, 57.05), client=client) == "06030"


def test_no_station_when_dmi_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def dmi_is_down(*_: object) -> str:
        request = httpx.Request("GET", "https://opendataapi.dmi.dk")
        raise httpx.ConnectError("DMI is down", request=request)

    monkeypatch.setattr("api.weather.stations.find_wind_station", dmi_is_down)

    assert wind_station_or_none(Point(9.92, 57.05)) is None
