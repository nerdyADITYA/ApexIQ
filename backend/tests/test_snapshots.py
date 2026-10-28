import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.data.ingestion import ingest_loaded_session, upsert_schedule
from app.main import app
from app.ml import track_record as tr_ml
from app.models import database_models as m
from app.services import forecast_service as fs
from app.services import track_record_service as tr
from tests.conftest import make_fake_session


@pytest.fixture(autouse=True)
def small_fields(monkeypatch):
    """The synthetic races have 4 drivers and few rounds: relax the real-world minimums for these tests only."""
    monkeypatch.setattr(tr_ml, "MIN_DRIVERS", 3)
    monkeypatch.setattr(tr, "MIN_PRIOR_ROUNDS", 1)
    tr.clear_replay_cache()
    yield
    tr.clear_replay_cache()


@pytest.fixture
def client(db):
    for rnd in (1, 2):
        ingest_loaded_session(db, make_fake_session(seed=rnd, round_number=rnd), 2024, "R")
    schedule = pd.DataFrame([
        {"RoundNumber": r, "EventName": f"Future GP {r}" if r > 2 else "Test GP", "Location": "Testville" if r <= 3 else "Newtown",
         "Country": "Nowhere", "EventDate": pd.Timestamp("2024-06-01") + pd.Timedelta(days=7 * r)} for r in (1, 2, 3, 4)])
    upsert_schedule(db, 2024, schedule)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def snaps(db):
    return db.scalars(select(m.RaceForecastSnapshot).order_by(m.RaceForecastSnapshot.round_number, m.RaceForecastSnapshot.mode)).all()


def test_snapshot_is_saved_and_replaced_by_a_newer_one_of_the_same_mode(client, db):
    r = client.post("/api/v1/predictions/2024/rounds/3/snapshot")
    assert r.status_code == 201 and r.json()["mode"] == "pre-qualifying"
    first = snaps(db)[0]
    assert first.payload["race"]["round"] == 3 and len(first.payload["drivers"]) == 4 and first.as_of_round == 2
    first_generated = first.generated_at
    assert client.post("/api/v1/predictions/2024/rounds/3/snapshot").status_code == 201
    rows = snaps(db)
    assert len(rows) == 1 and rows[0].generated_at >= first_generated      # replaced in place, not duplicated


def test_each_mode_gets_its_own_snapshot(client, db):
    client.post("/api/v1/predictions/2024/rounds/3/snapshot")
    ingest_loaded_session(db, make_fake_session(seed=7, round_number=3), 2024, "Q")
    post = client.post("/api/v1/predictions/2024/rounds/3/snapshot").json()
    assert post["mode"] == "post-qualifying"
    assert [(s.round_number, s.mode) for s in snaps(db)] == [(3, "post-qualifying"), (3, "pre-qualifying")]


def test_snapshot_freezes_once_the_race_has_been_run(client, db):
    client.post("/api/v1/predictions/2024/rounds/3/snapshot")
    before = snaps(db)[0]
    payload, generated = before.payload, before.generated_at
    ingest_loaded_session(db, make_fake_session(seed=3, round_number=3), 2024, "R")       # the race is run
    assert client.post("/api/v1/predictions/2024/rounds/3/snapshot").status_code == 409
    with pytest.raises(fs.RaceAlreadyRun):
        fs.save_snapshot(db, {**payload, "race": payload["race"], "mode": "pre-qualifying"})
    after = snaps(db)
    assert len(after) == 1 and after[0].payload == payload and after[0].generated_at == generated


def test_snapshot_errors(client):
    assert client.post("/api/v1/predictions/2024/rounds/99/snapshot").status_code == 404
    assert client.post("/api/v1/predictions/1999/rounds/3/snapshot").status_code == 404
    assert client.post("/api/v1/predictions/2024/rounds/1/snapshot").status_code == 409       # already raced


def test_snapshot_upcoming_summary(client, db):
    out = fs.snapshot_upcoming(db, 2024)
    assert [(r["round"], r["status"]) for r in out] == [(3, "saved"), (4, "saved")]
    assert len(snaps(db)) == 2


def test_frozen_track_record_pending_then_scored(client, db):
    client.post("/api/v1/predictions/2024/rounds/3/snapshot")
    empty = client.get("/api/v1/predictions/2024/track-record", params={"source": "frozen"}).json()
    assert empty["source"] == "frozen" and empty["races"] == [] and empty["summary"] == {}
    assert [(p["round"], p["mode"]) for p in empty["pending"]] == [(3, "pre-qualifying")]

    ingest_loaded_session(db, make_fake_session(seed=3, round_number=3), 2024, "R")
    rec = client.get("/api/v1/predictions/2024/track-record", params={"source": "frozen"}).json()
    assert rec["pending"] == [] and len(rec["races"]) == 1
    race = rec["races"][0]
    assert race["round"] == 3 and race["mode"] == "pre-qualifying" and race["winner"] == "AAA"
    assert race["actual_top3"] == ["AAA", "BBB", "CCC"] and race["forecast_saved_at"]
    assert -1 <= race["spearman"] <= 1 and rec["summary"]["pre-qualifying"]["races"] == 1
    assert set(rec["calibration"]["pre-qualifying"]) == {"win", "podium", "points"}


def test_replay_scores_past_races_with_only_earlier_data_and_labels_itself(client, db):
    ingest_loaded_session(db, make_fake_session(seed=3, round_number=3), 2024, "R")
    rec = client.get("/api/v1/predictions/2024/track-record", params={"source": "replay"}).json()
    assert rec["source"] == "replay" and "NOT frozen" in rec["note"] and "optimistic" in rec["note"]
    assert [r["round"] for r in rec["races"]] == [2, 3]
    assert all(r["forecast_saved_at"] is None for r in rec["races"])


def test_replay_of_a_race_does_not_depend_on_its_own_or_later_results(client, db):
    ingest_loaded_session(db, make_fake_session(seed=3, round_number=3), 2024, "R")
    base = tr.replay_track_record(db, 2024)
    by_round = {r["round"]: r for r in base["races"]}
    # reverse the finishing order of round 3 in the database: round 2's replay must not move, round 3's score must
    entries = db.scalars(select(m.SessionEntry).join(m.SessionRow).join(m.Event).where(m.Event.round_number == 3,
                                                                                         m.SessionRow.session_type == "R")).all()
    for e in entries:
        e.finish_position = 5 - e.finish_position
        e.points = 0.0
    db.commit()
    tr.clear_replay_cache()
    after = {r["round"]: r for r in tr.replay_track_record(db, 2024)["races"]}
    assert after[2]["spearman"] == by_round[2]["spearman"] and after[2]["mean_position_error"] == by_round[2]["mean_position_error"]
    assert after[3]["actual_top3"] != by_round[3]["actual_top3"]


def test_track_record_endpoint_validation(client):
    assert client.get("/api/v1/predictions/2024/track-record", params={"source": "nonsense"}).status_code == 422
    assert client.get("/api/v1/predictions/1999/track-record").status_code == 404
