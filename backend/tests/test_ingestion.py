import pandas as pd
from sqlalchemy import func, select

from app.data.ingestion import ingest_loaded_session
from app.data.transformations import classify_laps, td_to_ms
from app.models import database_models as m
from tests.conftest import make_fake_session


def test_td_to_ms_never_zero_for_missing():
    assert td_to_ms(pd.NaT) is None
    assert td_to_ms(None) is None
    assert td_to_ms(pd.Timedelta(seconds=90.123)) == 90123


def test_classify_flags_pit_and_missing_time():
    laps = make_fake_session().laps
    out = classify_laps(laps)
    pit = out[out["IsPitLap"]]
    assert not pit["IsValid"].any()
    assert (out[out["LapTime"].isna()]["InvalidReason"] == "no_time").all()
    assert out["IsValid"].sum() < len(out)  # flagged, not dropped
    assert len(out) == len(laps)


def test_ingest_is_idempotent(db):
    s1 = ingest_loaded_session(db, make_fake_session(), 2024, "R")
    counts1 = [db.scalar(select(func.count()).select_from(t)) for t in (m.Lap, m.SessionEntry, m.PitStop, m.Driver)]
    s2 = ingest_loaded_session(db, make_fake_session(), 2024, "R")
    counts2 = [db.scalar(select(func.count()).select_from(t)) for t in (m.Lap, m.SessionEntry, m.PitStop, m.Driver)]
    assert counts1 == counts2
    assert s1["session_id"] == s2["session_id"]
    assert s1["laps"] == 160 and s1["pit_stops"] == 4


def test_schedule_upsert_does_not_reset_loaded_sessions(db):
    from app.data.ingestion import upsert_schedule
    ingest_loaded_session(db, make_fake_session(), 2024, "R")
    schedule = pd.DataFrame([{"RoundNumber": 1, "EventName": "Test GP", "Location": "Testville",
                              "Country": "Nowhere", "EventDate": pd.Timestamp("2024-03-01")}])
    upsert_schedule(db, 2024, schedule)
    assert db.scalar(select(m.SessionRow.status)) == "loaded"


def test_missing_lap_time_stored_as_null(db):
    ingest_loaded_session(db, make_fake_session(), 2024, "R")
    lap = db.scalar(
        select(m.Lap).join(m.SessionEntry).join(m.Driver).where(m.Driver.code == "DDD", m.Lap.lap_number == 5)
    )
    assert lap.lap_time_ms is None and lap.is_valid is False


def test_grid_zero_is_missing(db):
    ingest_loaded_session(db, make_fake_session(), 2024, "R")
    e = db.scalar(select(m.SessionEntry).join(m.Driver).where(m.Driver.code == "DDD"))
    assert e.grid_position is None


def test_circuit_aliases_are_canonical_and_do_not_pool_different_places():
    from app.data.ingestion import canonical_circuit
    assert canonical_circuit("Yas Marina") == "Yas Island" and canonical_circuit(" Monte Carlo ") == "Monaco"
    assert canonical_circuit("Miami Gardens") == "Miami"
    assert canonical_circuit("Madrid") == "Madrid" and canonical_circuit("Barcelona") == "Barcelona"


def test_merge_script_relinks_events_and_is_idempotent(db):
    from scripts.merge_circuit_aliases import merge
    old, new = m.Circuit(name="Yas Island", country="UAE"), m.Circuit(name="Yas Marina")
    db.add_all([old, new, m.Season(year=2025), m.Season(year=2026)])
    db.flush()
    seasons = {s.year: s.id for s in db.scalars(select(m.Season))}
    db.add_all([m.Event(season_id=seasons[2025], circuit_id=old.id, round_number=24, event_name="Abu Dhabi Grand Prix"),
                m.Event(season_id=seasons[2026], circuit_id=new.id, round_number=23, event_name="Abu Dhabi Grand Prix")])
    db.commit()
    assert merge(db) == {"Yas Marina": 1}
    ids = {e.circuit_id for e in db.scalars(select(m.Event))}
    assert len(ids) == 1 and db.scalar(select(m.Circuit.name).where(m.Circuit.id == ids.pop())) == "Yas Island"
    assert db.scalar(select(func.count()).select_from(m.Circuit)) == 1
    assert merge(db) == {}                        # second run changes nothing
