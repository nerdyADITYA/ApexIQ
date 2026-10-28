from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import database_models  # noqa: F401


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def make_fake_session(n_laps=40, seed=1, round_number=1):
    """Synthetic race: 2 teams x 2 drivers, quadratic tyre wear, one stop each."""
    rng = np.random.default_rng(seed)
    rows = []
    teams = {"AAA": "Alpha", "BBB": "Alpha", "CCC": "Beta", "DDD": "Beta"}
    for i, (code, team) in enumerate(teams.items()):
        pit_lap = (10, 16, 22, 28)[i]  # spread so tyre age and lap number are not collinear
        for lap in range(1, n_laps + 1):
            stint = 1 if lap <= pit_lap else 2
            compound = "MEDIUM" if stint == 1 else "HARD"
            age = lap if stint == 1 else lap - pit_lap
            base = 90.0 + i * 0.3 + (0.0 if compound == "MEDIUM" else 0.4)
            t = base + 0.05 * age + 0.002 * age ** 2 - 0.02 * lap + rng.normal(0, 0.15)
            in_lap, out_lap = lap == pit_lap, lap == pit_lap + 1
            if in_lap or out_lap:
                t += 10
            rows.append({
                "Driver": code, "DriverNumber": str(i + 1), "Team": team, "LapNumber": float(lap),
                "LapTime": pd.Timedelta(seconds=float(t)) if lap != 5 or code != "DDD" else pd.NaT,
                "Sector1Time": pd.Timedelta(seconds=t * 0.3), "Sector2Time": pd.Timedelta(seconds=t * 0.4),
                "Sector3Time": pd.Timedelta(seconds=t * 0.3),
                "Compound": compound, "TyreLife": float(age), "Stint": float(stint),
                "PitInTime": pd.Timedelta(minutes=lap) if in_lap else pd.NaT,
                "PitOutTime": pd.Timedelta(minutes=lap, seconds=21) if out_lap else pd.NaT,
                "Position": float(i + 1), "IsPersonalBest": False, "TrackStatus": "1", "Deleted": False,
            })
    laps = pd.DataFrame(rows)
    pts = [25, 18, 15, 12]
    results = pd.DataFrame({
        "Abbreviation": list(teams), "DriverNumber": [str(i + 1) for i in range(4)],
        "FullName": [f"Driver {c}" for c in teams], "TeamName": list(teams.values()),
        "GridPosition": [1.0, 2.0, 3.0, 0.0], "Position": [1.0, 2.0, 3.0, 4.0],
        "Points": pts, "Status": "Finished",
    })
    event = {"EventName": "Test GP", "RoundNumber": round_number, "Location": "Testville", "Country": "Nowhere"}
    return SimpleNamespace(laps=laps, results=results, event=event)
