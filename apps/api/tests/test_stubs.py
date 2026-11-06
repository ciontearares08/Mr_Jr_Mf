from fastapi.testclient import TestClient

from api.main import app
from api.schemas.overview import Overview
from api.schemas.timeline import Timeline, TimelineDetails

client = TestClient(app)


def test_overview_matches_model() -> None:
    response = client.get("/stub/overview")
    assert response.status_code == 200
    overview = Overview.model_validate(response.json())
    assert overview.stage.current.code == "MaximumSpikeletPrimordia"
    assert all(s.date.min >= overview.as_of for s in overview.stage.upcoming)


def test_timeline_matches_model() -> None:
    response = client.get("/stub/timeline")
    assert response.status_code == 200
    timeline = Timeline.model_validate(response.json())
    assert [s.status for s in timeline.stages].count("current") == 1
    for stage in timeline.stages:
        assert stage.start.min <= stage.start.median <= stage.start.max


def test_timeline_details_matches_model() -> None:
    response = client.get("/stub/timeline/details")
    assert response.status_code == 200
    details = TimelineDetails.model_validate(response.json())
    assert len(details.days) == 141
