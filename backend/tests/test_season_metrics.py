import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.analytics import season_metrics as sm
from app.core.database import get_db
from app.data.ingestion import ingest_loaded_session
from app.main import app
from app.services import frames
from tests.conftest import make_fake_session


@pytest.fixture
def seeded(db):
    for rnd in (1, 2, 3):
        ingest_loaded_session(db, make_fake_session(seed=rnd, round_number=rnd), 2024, "R")
    ingest_loaded_session(db, make_fake_session(seed=9, round_number=1), 2024, "Q")
    return db


def test_is_dnf():
    assert not sm.is_dnf("Finished") and not sm.is_dnf("Lapped") and not sm.is_dnf("+1 Lap")
    assert sm.is_dnf("Retired") and sm.is_dnf("Collision")
    assert not sm.is_dnf(None) and not sm.is_dnf(float("nan"))


def test_teammate_gap_is_antisymmetric(seeded):
    laps = frames.season_laps_frame(seeded, 2024, "R")
    gaps = sm.teammate_gaps(sm.race_pace_table(laps))
    for rnd in (1, 2, 3):
        a = gaps[(gaps["driver"] == "AAA") & (gaps["round"] == rnd)].iloc[0]
        b = gaps[(gaps["driver"] == "BBB") & (gaps["round"] == rnd)].iloc[0]
        assert a["teammate"] == "BBB" and abs(a["gap_pct"] + b["gap_pct"]) < 1e-9
        assert abs(a["s1_s_gap_s"] + b["s1_s_gap_s"]) < 1e-9


def test_driver_profile_values(seeded):
    ent = frames.entries_frame(seeded, 2024, types=("R", "Q"))
    race, quali = ent[ent.stype == "R"], ent[ent.stype == "Q"]
    laps = frames.season_laps_frame(seeded, 2024, "R")
    p = sm.driver_profile("AAA", race, quali, laps)
    s = p["season_summary"]
    assert s["races"] == 3 and s["wins"] == 3 and s["points"] == 75 and s["dnfs"] == 0
    assert p["rounds"][-1]["cumulative_points"] == 75
    assert p["qualifying"]["sessions"] == 1 and p["qualifying"]["best_position"] == 1
    t = p["teammate"]
    assert t["name"] == "BBB" and t["rated_races"] == 3
    assert t["faster_in_races"] == sum(1 for r in p["rounds"] if r["teammate_gap_pct"] < 0)
    assert p["rounds"][0]["stints"][0]["compound"] == "MEDIUM" and len(p["rounds"][0]["stints"]) == 2


def test_driver_missing_grid_is_none_not_zero(seeded):
    ent = frames.entries_frame(seeded, 2024, types=("R", "Q"))
    laps = frames.season_laps_frame(seeded, 2024, "R")
    p = sm.driver_profile("DDD", ent[ent.stype == "R"], ent[ent.stype == "Q"], laps)
    assert all(r["grid"] is None for r in p["rounds"])      # grid 0 in source = no slot
    assert p["season_summary"]["avg_grid"] is None


def test_constructor_contribution_adds_up(seeded):
    ent = frames.entries_frame(seeded, 2024, types=("R", "Q"))
    laps = frames.season_laps_frame(seeded, 2024, "R")
    pit = frames.pit_frame(seeded, 2024)
    c = sm.constructor_profile("Alpha", ent[ent.stype == "R"], ent[ent.stype == "Q"], laps, pit)
    assert c["season_summary"]["points"] == sum(d["points"] for d in c["driver_contribution"]) == 129
    assert abs(sum(d["share"] for d in c["driver_contribution"]) - 1) < 1e-9
    assert c["by_round"][-1]["cumulative_points"] == 129


def test_pit_durations_outside_plausible_range_are_null(seeded):
    pit = frames.pit_frame(seeded, 2024)
    assert pit["duration_s"].dropna().between(10, 60).all()


def test_api_endpoints(seeded):
    app.dependency_overrides[get_db] = lambda: seeded
    try:
        c = TestClient(app)
        r = c.get("/api/v1/drivers/aaa/profile", params={"season": 2024})
        assert r.status_code == 200 and r.json()["driver"] == "AAA"
        assert c.get("/api/v1/drivers/ZZZ/profile", params={"season": 2024}).status_code == 404
        assert c.get("/api/v1/drivers/AAA/profile", params={"season": 1999}).status_code == 404
        assert c.get("/api/v1/drivers/AAA/profile").status_code == 422   # season required
        t = c.get("/api/v1/drivers/AAA/tracks").json()
        assert t["circuits"][0]["circuit"] == "Testville"
        k = c.get("/api/v1/constructors/Alpha/profile", params={"season": 2024})
        assert k.status_code == 200 and k.json()["season_summary"]["wins"] == 3
        assert c.get("/api/v1/constructors/Nope/profile", params={"season": 2024}).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_progression_endpoint(seeded):
    app.dependency_overrides[get_db] = lambda: seeded
    try:
        c = TestClient(app)
        r = c.get("/api/v1/seasons/2024/progression", params={"top": 2}).json()
        assert r["rounds"] == [1, 2, 3] and len(r["series"]) == 2
        top = r["series"][0]
        assert top["driver"] == "AAA" and top["points"] == [25.0, 50.0, 75.0]   # cumulative, non-decreasing
        assert all(b >= a for a, b in zip(top["points"], top["points"][1:]))
        assert c.get("/api/v1/seasons/1999/progression").status_code == 404
        assert c.get("/api/v1/seasons/2024/progression", params={"top": 99}).status_code == 422
    finally:
        app.dependency_overrides.clear()
