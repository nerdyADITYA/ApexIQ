"""DB -> DataFrame helpers shared by API routes and analytics."""

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import database_models as m


def season_results_frame(db: Session, year: int) -> pd.DataFrame:
    """One row per (round, driver): race finish, race points and sprint points (0 when no sprint)."""
    stmt = (
        select(m.Event.round_number, m.SessionRow.session_type, m.Driver.code, m.Constructor.name,
               m.SessionEntry.finish_position, m.SessionEntry.points)
        .select_from(m.SessionEntry)
        .join(m.SessionRow, m.SessionEntry.session_id == m.SessionRow.id)
        .join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Season, m.Event.season_id == m.Season.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .outerjoin(m.Constructor, m.SessionEntry.constructor_id == m.Constructor.id)
        .where(m.Season.year == year, m.SessionRow.session_type.in_(["R", "S"]), m.SessionRow.status == "loaded")
    )
    rows = db.execute(stmt).all()
    df = pd.DataFrame(rows, columns=["round", "stype", "driver", "team", "finish", "points"])
    race = df[df["stype"] == "R"].rename(columns={"points": "race_points"}).drop(columns="stype")
    sprint = df[df["stype"] == "S"].rename(columns={"points": "sprint_points"})[["round", "driver", "sprint_points"]]
    out = race.merge(sprint, on=["round", "driver"], how="left")
    out["sprint_points"] = out["sprint_points"].fillna(0.0)
    out["race_points"] = out["race_points"].fillna(0.0)
    return out.sort_values(["round", "finish"]).reset_index(drop=True)


def entries_frame(db: Session, year: int | None = None, types=("R", "Q")) -> pd.DataFrame:
    """One row per (season, round, session type, driver) with results context."""
    stmt = (
        select(m.Season.year, m.Event.round_number, m.Event.event_name, m.Circuit.name, m.SessionRow.session_type,
               m.SessionRow.id, m.Driver.code, m.Driver.full_name, m.Constructor.name,
               m.SessionEntry.grid_position, m.SessionEntry.finish_position, m.SessionEntry.points,
               m.SessionEntry.status)
        .select_from(m.SessionEntry)
        .join(m.SessionRow, m.SessionEntry.session_id == m.SessionRow.id)
        .join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Season, m.Event.season_id == m.Season.id)
        .outerjoin(m.Circuit, m.Event.circuit_id == m.Circuit.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .outerjoin(m.Constructor, m.SessionEntry.constructor_id == m.Constructor.id)
        .where(m.SessionRow.session_type.in_(types), m.SessionRow.status == "loaded")
    )
    if year is not None:
        stmt = stmt.where(m.Season.year == year)
    cols = ["year", "round", "event", "circuit", "stype", "session_id", "driver", "name", "team",
            "grid", "finish", "points", "status"]
    return pd.DataFrame(db.execute(stmt).all(), columns=cols)


def season_laps_frame(db: Session, year: int, stype: str = "R") -> pd.DataFrame:
    """All laps of one session type in a season, with round/driver/team."""
    stmt = (
        select(m.Event.round_number, m.Driver.code, m.Constructor.name, m.Lap.lap_number, m.Lap.lap_time_ms,
               m.Lap.sector1_ms, m.Lap.sector2_ms, m.Lap.sector3_ms, m.Lap.compound, m.Lap.stint,
               m.Lap.is_valid, m.Lap.is_pit_lap)
        .select_from(m.Lap)
        .join(m.SessionEntry, m.Lap.session_entry_id == m.SessionEntry.id)
        .join(m.SessionRow, m.SessionEntry.session_id == m.SessionRow.id)
        .join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Season, m.Event.season_id == m.Season.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .outerjoin(m.Constructor, m.SessionEntry.constructor_id == m.Constructor.id)
        .where(m.Season.year == year, m.SessionRow.session_type == stype, m.SessionRow.status == "loaded")
    )
    cols = ["round", "driver", "team", "lap_number", "lap_time_ms", "s1", "s2", "s3", "compound", "stint",
            "is_valid", "is_pit_lap"]
    df = pd.DataFrame(db.execute(stmt).all(), columns=cols)
    for c in ("lap_time_ms", "s1", "s2", "s3"):
        df[c.replace("_ms", "_s") if c == "lap_time_ms" else c + "_s"] = df[c] / 1000.0
    return df.drop(columns=["lap_time_ms", "s1", "s2", "s3"])


def session_laps_frame(db: Session, session_id: int) -> pd.DataFrame:
    stmt = (
        select(m.Lap, m.Driver.code, m.Constructor.name)
        .join(m.SessionEntry, m.Lap.session_entry_id == m.SessionEntry.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .outerjoin(m.Constructor, m.SessionEntry.constructor_id == m.Constructor.id)
        .where(m.SessionEntry.session_id == session_id)
    )
    rows = []
    for lap, code, team in db.execute(stmt):
        ms = lambda v: None if v is None else v / 1000.0  # noqa: E731
        rows.append({
            "driver": code, "constructor": team, "lap_number": lap.lap_number,
            "lap_time_s": ms(lap.lap_time_ms), "sector1_s": ms(lap.sector1_ms),
            "sector2_s": ms(lap.sector2_ms), "sector3_s": ms(lap.sector3_ms),
            "compound": lap.compound, "tyre_life": lap.tyre_life, "stint": lap.stint,
            "is_valid": lap.is_valid, "is_pit_lap": lap.is_pit_lap,
            "neutralised": lap.invalid_reason == "neutralised",
            "track_status": lap.track_status,
        })
    cols = ["driver", "constructor", "lap_number", "lap_time_s", "sector1_s", "sector2_s", "sector3_s",
            "compound", "tyre_life", "stint", "is_valid", "is_pit_lap", "neutralised", "track_status"]
    return pd.DataFrame(rows, columns=cols)


def pit_frame(db: Session, year: int) -> pd.DataFrame:
    """Race pit stops with team and pit-lane duration in seconds (NULL durations kept as NaN)."""
    stmt = (
        select(m.Event.round_number, m.Driver.code, m.Constructor.name, m.PitStop.lap_number, m.PitStop.duration_ms)
        .select_from(m.PitStop)
        .join(m.SessionEntry, m.PitStop.session_entry_id == m.SessionEntry.id)
        .join(m.SessionRow, m.SessionEntry.session_id == m.SessionRow.id)
        .join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Season, m.Event.season_id == m.Season.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .outerjoin(m.Constructor, m.SessionEntry.constructor_id == m.Constructor.id)
        .where(m.Season.year == year, m.SessionRow.session_type == "R", m.SessionRow.status == "loaded")
    )
    df = pd.DataFrame(db.execute(stmt).all(), columns=["round", "driver", "team", "lap_number", "duration_ms"])
    df["duration_s"] = df["duration_ms"] / 1000.0
    # Plausibility: pit-lane time outside 10-60 s is a red flag / data artefact, not a normal stop
    df.loc[(df["duration_s"] < 10) | (df["duration_s"] > 60), "duration_s"] = float("nan")
    return df
