"""Thin FastF1 wrapper. The browser never calls this; only ingestion does."""

import logging
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.data.transformations import downsample_telemetry

log = logging.getLogger(__name__)

EXPECTED_LAP_COLUMNS = [
    "Driver", "DriverNumber", "Team", "LapNumber", "LapTime", "Sector1Time",
    "Sector2Time", "Sector3Time", "Compound", "TyreLife", "Stint", "PitInTime",
    "PitOutTime", "Position", "IsPersonalBest", "TrackStatus", "Deleted",
]


def _fastf1():
    import fastf1  # imported lazily so the API and tests do not require it

    cache = Path(get_settings().fastf1_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache))
    return fastf1


def load_session(year: int, event: str | int, session_type: str, telemetry: bool = True):
    ff1 = _fastf1()
    session = ff1.get_session(year, event, session_type)
    session.load(laps=True, telemetry=telemetry, weather=True, messages=False)
    return session


def get_schedule(year: int) -> pd.DataFrame:
    return _fastf1().get_event_schedule(year, include_testing=False)


def extract_laps(session) -> pd.DataFrame:
    """Available lap columns only; missing columns are simply absent."""
    laps = session.laps.copy()
    cols = [c for c in EXPECTED_LAP_COLUMNS if c in laps.columns]
    return laps[cols].copy()


def extract_fastest_lap_telemetry(session, max_points: int = 400) -> dict[str, tuple[int, pd.DataFrame]]:
    """Per driver: (lap_number, downsampled telemetry). Failures are logged, not raised."""
    out: dict[str, tuple[int, pd.DataFrame]] = {}
    for code in session.laps["Driver"].dropna().unique():
        try:
            lap = session.laps.pick_drivers(code).pick_fastest()
            if lap is None or pd.isna(lap["LapTime"]):
                continue
            tel = lap.get_telemetry()
            tel = tel[[c for c in ["Time", "Distance", "X", "Y", "Speed", "Throttle", "Brake", "nGear", "RPM"] if c in tel.columns]]
            out[code] = (int(lap["LapNumber"]), downsample_telemetry(tel.reset_index(drop=True), max_points))
        except Exception as exc:  # missing telemetry must not fail the session
            log.warning("No telemetry for %s: %s", code, exc)
    return out
