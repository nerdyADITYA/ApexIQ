import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.data.ingestion import ingest_loaded_session
from app.main import app
from tests.conftest import make_fake_session


@pytest.fixture
def client(db):
    for rnd in (1, 2):
        ingest_loaded_session(db, make_fake_session(seed=rnd, round_number=rnd), 2024, "R")
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_seasons_events_standings(client):
    assert client.get("/api/v1/seasons").json()[0]["year"] == 2024
    ev = client.get("/api/v1/events", params={"season": 2024}).json()
    assert [e["round"] for e in ev] == [1, 2]
    st = client.get("/api/v1/seasons/2024/standings").json()
    assert st["drivers"][0]["driver"] == "AAA" and st["drivers"][0]["points"] == 50
    assert client.get("/api/v1/seasons/1999/standings").status_code == 404


def test_laps_pagination_and_nulls(client):
    r = client.get("/api/v1/sessions/1/laps", params={"driver": "ddd", "limit": 10}).json()
    assert r["total"] == 40 and len(r["laps"]) == 10
    all_laps = client.get("/api/v1/sessions/1/laps", params={"driver": "DDD", "limit": 100}).json()["laps"]
    lap5 = next(l for l in all_laps if l["lap_number"] == 5)
    assert lap5["lap_time_s"] is None  # missing, not zero
    assert all("track_status" in l and "is_pit_lap" in l for l in all_laps)  # needed to explain gaps in charts
    assert client.get("/api/v1/sessions/1/laps", params={"limit": 5000}).status_code == 422


def test_compare(client):
    r = client.post("/api/v1/sessions/1/compare", json={"drivers": ["AAA", "CCC"]}).json()
    assert r["reference"] == "AAA" and len(r["pace"]) == 2
    assert client.post("/api/v1/sessions/1/compare", json={"drivers": ["AAA"]}).status_code == 422


def test_telemetry_missing_gives_404(client):
    assert client.get("/api/v1/sessions/1/telemetry/AAA").status_code == 404


def test_championship_forecast(client):
    r = client.get("/api/v1/championships/2024/drivers", params={"n_sims": 1000}).json()
    assert r["races_completed"] == 2 and r["model_version"]
    assert abs(sum(d["win_probability"] for d in r["drivers"]) - 1) < 1e-6


def test_strategy_endpoint(client):
    body = {"session_id": 1, "driver_code": "AAA", "stint_compounds": ["MEDIUM", "HARD"], "pit_laps": [22]}
    r = client.post("/api/v1/strategy/simulate", json=body).json()
    assert r["baseline_delta_seconds"] is not None and r["model_version"] == "strategy-v1"
    assert r["pit_loss_source"] in ("measured", "default") and 15 <= r["pit_loss_seconds"] <= 35
    assert r["pit_loss_stops"] is not None
    assert len(r["profile"]) == 40 and r["actual_stints"] and r["profile"][-1]["lap"] == 40
    assert abs(r["profile"][-1]["cumulative_delta_s"] - r["baseline_delta_seconds"]) < 1e-2
    bad = client.post("/api/v1/strategy/simulate", json={**body, "stint_compounds": ["MEDIUM", "MEDIUM"]}).json()
    assert bad["estimated_race_time_seconds"] is None and bad["constraint_violations"]
