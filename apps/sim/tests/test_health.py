from fastapi.testclient import TestClient

from sim.main import app

client = TestClient(app)


def test_returns_ok() -> None:
    response = client.get("/sim/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
