"""Tests for the DMI client. They never call DMI.

The tests marked with `vcr` replay real DMI responses for cell 10km_632_55 and
station 06030 (Aalborg), June 2026, from
tests/cassettes/test_dmi/aalborg_june_2026.yaml.
To record that cassette again from the live API, run in the API devcontainer:

    uv run pytest tests/test_dmi.py -k rows_have_all --record-mode=rewrite

Record only one test. If all tests record, DMI answers 429 (too many requests).

DMI never sends errors, missing links or duplicate dates on request, so the
tests for those cases build small DMI-shaped pages by hand.
"""

import datetime as dt
import time
from collections.abc import Callable

import httpx
import pytest
from vcr.cassette import Cassette

from api.weather import dmi
from api.weather.dmi import (
    COLUMNS,
    DANISH_TIME,
    PARAMETERS,
    WeatherDay,
    fetch_daily_weather,
    merge_days,
    parse_daily_min,
    parse_daily_values,
    retry_after_seconds,
)

CELL = "10km_632_55"
STATION = "06030"  # Flyvestation Aalborg, the min wind station nearest to CELL.
JUNE_1 = dt.date(2026, 6, 1)
JUNE_2 = dt.date(2026, 6, 2)
JUNE_30 = dt.date(2026, 6, 30)


def replay_aalborg_june(test: Callable) -> Callable:
    """Run the test against the one shared cassette of Aalborg, June 2026."""
    use_shared_cassette = pytest.mark.default_cassette("aalborg_june_2026.yaml")
    return pytest.mark.vcr(use_shared_cassette(test))


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    return {
        # The parameters download in parallel, so we match each request by
        # its URL and query and not by the order it arrives in.
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        # Stores the body as plain JSON text instead of gzip bytes.
        "decode_compressed_response": True,
        # A test can fetch the same month twice.
        "allow_playback_repeats": True,
    }


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dmi, "RETRY_WAIT_SECONDS", (0, 0, 0))


@pytest.fixture(autouse=True)
def small_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real page sizes fit a month in one page. With 10 days per page, the
    # cassette holds real "next" links, so the tests replay real paging.
    monkeypatch.setattr(dmi, "GRID_PAGE_SIZE", 10)
    monkeypatch.setattr(dmi, "OBSERVATION_PAGE_SIZE", 10 * 24)


@pytest.fixture
def june(vcr: Cassette) -> list[WeatherDay]:
    return fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_30)


def feature(date: str, value: float | None, calculated_at: str | None) -> dict:
    """One DMI grid feature with only the properties that the parser reads."""
    properties = {"from": f"{date}T00:00:00.001000+02:00", "value": value}
    if calculated_at is not None:
        properties["calculatedAt"] = calculated_at
    return {"properties": properties}


def hourly_features(date: str, value: float, hours: int = 24) -> list[dict]:
    """The first `hours` hourly DMI observations of a Danish date.

    DMI stamps each value at the end of its hour, in UTC.
    """
    midnight = dt.datetime.fromisoformat(date).replace(tzinfo=DANISH_TIME)
    return [
        {
            "properties": {
                "observed": (midnight + dt.timedelta(hours=hour))
                .astimezone(dt.UTC)
                .isoformat(),
                "value": value,
            }
        }
        for hour in range(1, hours + 1)
    ]


def serve_pages(*pages: list[str]) -> Callable[[httpx.Request], httpx.Response]:
    """Fake DMI that sends the given pages of days, each day with the value 1.0.

    The grid sends one feature per day and the station 24 hourly features.
    Like DMI, every page has a "next" link, and the page after the last is empty.
    """

    def answer(request: httpx.Request) -> httpx.Response:
        page_number = int(request.url.params.get("page", 0))
        days = pages[page_number] if page_number < len(pages) else []
        next_link = request.url.copy_set_param("page", page_number + 1)
        if request.url.params.get("parameterId") == dmi.MIN_WIND_PARAMETER:
            features = [hour for day in days for hour in hourly_features(day, 1.0)]
        else:
            features = [feature(day, 1.0, "2026-06-05T09:00:00") for day in days]
        page = {
            "type": "FeatureCollection",
            "features": features,
            "links": [{"rel": "next", "href": str(next_link)}],
        }
        return httpx.Response(200, json=page)

    return answer


one_day_page = serve_pages(["2026-06-01"])


def client_answering_with(
    answer: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(answer))


@replay_aalborg_june
def test_one_row_per_day_in_the_range(june: list[WeatherDay]) -> None:
    assert [day.date for day in june] == [
        JUNE_1 + dt.timedelta(days=i) for i in range(30)
    ]


@replay_aalborg_june
def test_rows_have_all_eight_values_in_apsim_units(june: list[WeatherDay]) -> None:
    assert june[10] == WeatherDay(
        date=dt.date(2026, 6, 11),
        maxt=17.4,
        mint=6.5,
        rain=5.5,
        radn=21.5,
        wind_speed=2.6,
        wind_min=0.0,  # Station 06030 reports 0.0 in almost every hour.
        wind_max=9.3,
        rh=74.5,
    )


@replay_aalborg_june
def test_values_use_the_danish_date(june: list[WeatherDay]) -> None:
    # DMI gives June 4 the "from" 2026-06-04T00:00:00.001000+02:00, which is
    # still June 3 in UTC. The value must land on June 4.
    june_4 = june[3]
    assert june_4.date == dt.date(2026, 6, 4)
    assert june_4.radn == 10.8


@replay_aalborg_june
def test_values_are_in_a_plausible_range(june: list[WeatherDay]) -> None:
    # A wrong unit gives no error, so we compare with what a Danish June can be.
    for day in june:
        assert 0 < day.radn < 35  # MJ/m2 per day, not W/m2
        assert -5 < day.mint <= day.maxt < 40
        assert 0 <= day.rain < 100
        assert 0 <= day.wind_min <= day.wind_speed <= day.wind_max < 50
        assert 0 < day.rh <= 100


@replay_aalborg_june
def test_real_next_links_are_followed_to_the_empty_page(vcr: Cassette) -> None:
    fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_30)
    # 31 days with 10 per page is 4 pages, and DMI then sends one empty page.
    # The hourly min wind has 10 days of hours per page, so it also has 5 pages.
    assert vcr.play_count == 5 * (len(PARAMETERS) + 1)


@replay_aalborg_june
def test_a_client_from_the_caller_stays_open(vcr: Cassette) -> None:
    client = httpx.Client()

    fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_30, client=client)

    assert not client.is_closed
    fetch_daily_weather(
        CELL, STATION, JUNE_1, JUNE_30, client=client
    )  # Works a second time.


def test_a_temporary_error_is_tried_again() -> None:
    failed_parameters: set[str] = set()

    def fail_once_per_parameter(request: httpx.Request) -> httpx.Response:
        parameter = request.url.params["parameterId"]
        if parameter not in failed_parameters:
            failed_parameters.add(parameter)
            return httpx.Response(503)
        return one_day_page(request)

    client = client_answering_with(fail_once_per_parameter)
    [june_1] = fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_1, client=client)

    assert june_1.rain == 1.0


def test_a_lasting_error_reaches_the_caller() -> None:
    client = client_answering_with(lambda _: httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_30, client=client)


def test_a_non_json_body_is_tried_again() -> None:
    answered_with_html: set[str] = set()

    def html_once_per_parameter(request: httpx.Request) -> httpx.Response:
        parameter = request.url.params["parameterId"]
        if parameter not in answered_with_html:
            answered_with_html.add(parameter)
            return httpx.Response(200, text="<html>Maintenance</html>")
        return one_day_page(request)

    client = client_answering_with(html_once_per_parameter)
    [june_1] = fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_1, client=client)

    assert june_1.rain == 1.0


def test_the_first_lasting_error_reaches_the_caller_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Five parameters keep getting 503 and wait 30 s between tries. The 400 for
    # maxt must reach the caller without waiting for those retries.
    monkeypatch.setattr(dmi, "RETRY_WAIT_SECONDS", (30, 30, 30))

    def bad_request_for_maxt(request: httpx.Request) -> httpx.Response:
        if request.url.params["parameterId"] == PARAMETERS["maxt"]:
            return httpx.Response(400)
        return httpx.Response(503)

    client = client_answering_with(bad_request_for_maxt)
    started = time.monotonic()
    with pytest.raises(httpx.HTTPStatusError) as error:
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_30, client=client)

    assert error.value.response.status_code == 400
    assert time.monotonic() - started < 5


@pytest.mark.parametrize(
    ("retry_after", "expected_seconds"),
    [("30", 30), (None, 0), ("Wed, 21 Oct 2026 07:28:00 GMT", 0)],
    ids=["seconds", "no header", "date form"],
)
def test_retry_after_gives_the_wait_that_dmi_asks_for(
    retry_after: str | None, expected_seconds: float
) -> None:
    headers = {"Retry-After": retry_after} if retry_after else {}
    request = httpx.Request("GET", dmi.GRID_URL)
    response = httpx.Response(429, headers=headers, request=request)
    error = httpx.HTTPStatusError(
        "Too many requests", request=request, response=response
    )

    assert retry_after_seconds(error) == expected_seconds


def count_requests_per_parameter(
    answer: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.Client, dict[str, int]]:
    """Return a client that answers with `answer` and counts its requests."""
    requests_per_parameter: dict[str, int] = {}

    def counting_answer(request: httpx.Request) -> httpx.Response:
        parameter = request.url.params["parameterId"]
        requests_per_parameter[parameter] = requests_per_parameter.get(parameter, 0) + 1
        return answer(request)

    return client_answering_with(counting_answer), requests_per_parameter


@pytest.mark.parametrize(
    "pages",
    [[["2026-06-02"], ["2026-06-01"]], [["2026-06-01"], ["2026-06-02"]]],
    ids=["newest first", "oldest first"],
)
def test_paging_reads_every_page_in_any_order(pages: list[list[str]]) -> None:
    client, requests_per_parameter = count_requests_per_parameter(serve_pages(*pages))

    june_1, june_2 = fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_2, client=client)

    assert june_1.rain == june_2.rain == 1.0
    # Two pages with days, then the empty page that ends the paging.
    assert set(requests_per_parameter.values()) == {3}


def test_paging_stops_at_an_empty_page() -> None:
    client = client_answering_with(serve_pages(["2026-06-02"], [], ["2026-06-01"]))

    june_1, june_2 = fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_2, client=client)

    assert june_1.rain is None  # It is on the page after the empty page.
    assert june_2.rain == 1.0


def test_paging_fails_when_dmi_repeats_a_next_link() -> None:
    def same_next_link_every_time(request: httpx.Request) -> httpx.Response:
        page = serve_pages(["2026-06-01"])(httpx.Request("GET", dmi.GRID_URL)).json()
        return httpx.Response(200, json=page)

    client = client_answering_with(same_next_link_every_time)
    with pytest.raises(dmi.DmiPagingError, match="same next link"):
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_1, client=client)


def test_paging_fails_after_too_many_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dmi, "MAX_PAGES_PER_PARAMETER", 3)
    endless_pages = serve_pages(*[["2026-06-01"]] * 10)

    client = client_answering_with(endless_pages)
    with pytest.raises(dmi.DmiPagingError, match="more than 3 pages"):
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_1, client=client)


def test_paging_stops_at_a_page_without_links() -> None:
    def page_without_links(request: httpx.Request) -> httpx.Response:
        page = serve_pages(["2026-06-02"])(request).json()
        del page["links"]
        return httpx.Response(200, json=page)

    client = client_answering_with(page_without_links)
    _, june_2 = fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_2, client=client)

    assert june_2.rain == 1.0


def test_a_page_without_features_is_an_error() -> None:
    client = client_answering_with(
        lambda _: httpx.Response(200, json={"message": "oops"})
    )
    with pytest.raises(dmi.DmiResponseError):
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_1, client=client)


def test_a_cell_without_any_data_is_an_error() -> None:
    client = client_answering_with(serve_pages())  # The first page is empty.
    with pytest.raises(dmi.NoWeatherData, match=CELL):
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_30, client=client)


def test_a_station_without_any_min_wind_is_an_error() -> None:
    def no_station_data(request: httpx.Request) -> httpx.Response:
        if request.url.params["parameterId"] == dmi.MIN_WIND_PARAMETER:
            return serve_pages()(request)
        return one_day_page(request)

    client = client_answering_with(no_station_data)
    with pytest.raises(dmi.NoWeatherData, match=STATION):
        fetch_daily_weather(CELL, STATION, JUNE_1, JUNE_1, client=client)


def test_a_missing_value_is_skipped() -> None:
    values = parse_daily_values([feature("2026-06-01", None, "2026-06-02T09:00:00")])
    assert values == {}


def test_the_newest_calculation_wins_for_a_repeated_date() -> None:
    values = parse_daily_values(
        [
            feature("2026-06-01", 2.0, "2026-06-05T09:00:00"),
            feature("2026-06-01", 1.0, "2026-06-02T09:00:00"),
        ]
    )
    assert values == {JUNE_1: 2.0}


def test_a_value_without_calculated_at_is_kept() -> None:
    values = parse_daily_values([feature("2026-06-01", 1.0, calculated_at=None)])
    assert values == {JUNE_1: 1.0}


def test_a_value_with_calculated_at_replaces_one_without() -> None:
    values = parse_daily_values(
        [
            feature("2026-06-01", 1.0, calculated_at=None),
            feature("2026-06-01", 2.0, "2026-06-02T09:00:00"),
        ]
    )
    assert values == {JUNE_1: 2.0}


def test_a_feature_without_a_date_is_skipped() -> None:
    values = parse_daily_values([{"properties": {"value": 1.0}}])
    assert values == {}


def test_min_wind_is_the_lowest_hourly_value_of_the_day() -> None:
    hours = hourly_features("2026-06-01", 3.0)
    hours[5]["properties"]["value"] = 0.4

    assert parse_daily_min(hours) == {JUNE_1: 0.4}


def test_min_wind_uses_the_danish_date() -> None:
    # The last hour of June 1 in Danish summer time is stamped 22:00 UTC.
    [last_hour] = hourly_features("2026-06-01", 1.0)[-1:]
    assert last_hour["properties"]["observed"] == "2026-06-01T22:00:00+00:00"

    assert dmi.danish_date_of_hour(dt.datetime(2026, 6, 1, 22, tzinfo=dt.UTC)) == JUNE_1


def test_a_day_with_too_few_hours_has_no_min_wind() -> None:
    hours = hourly_features("2026-06-01", 1.0, hours=dmi.MIN_HOURS_PER_DAY - 1)
    assert parse_daily_min(hours) == {}


def test_missing_values_are_none() -> None:
    values = {column: {} for column in COLUMNS}
    values["rain"] = {JUNE_1: 1.2}

    [day] = merge_days(values, JUNE_1, JUNE_1)

    assert day.rain == 1.2
    assert day.maxt is None


@pytest.mark.parametrize(
    ("start", "end"),
    [(JUNE_30, JUNE_1), (dt.date(2005, 6, 1), dt.date(2005, 6, 30))],
    ids=["start after end", "before the grid data starts"],
)
def test_a_bad_date_range_is_rejected(start: dt.date, end: dt.date) -> None:
    client = client_answering_with(one_day_page)
    with pytest.raises(ValueError):
        fetch_daily_weather(CELL, STATION, start, end, client=client)
