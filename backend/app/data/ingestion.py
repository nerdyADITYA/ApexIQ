"""Idempotent session ingestion.

Rerunning for the same (year, round, session type) updates entities in place and
replaces that session's laps/pit stops/telemetry inside one transaction, so no
duplicate logical records are created and a failure leaves old data intact.
"""

import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.data import validation
from app.data.transformations import (
    add_seconds, classify_laps, completeness_report, derive_pit_stops, num_or_none, td_to_ms,
)
from app.models import database_models as m

log = logging.getLogger(__name__)

# FastF1's `Location` for the same circuit changes between seasons. Map the variants onto one canonical name so a
# circuit's history stays linked. Only true renames belong here: a different place (e.g. Madrid vs Barcelona for
# the Spanish GP) must stay separate.
CIRCUIT_ALIASES = {"Yas Marina": "Yas Island", "Monte Carlo": "Monaco", "Miami Gardens": "Miami"}


def canonical_circuit(name: str) -> str:
    name = str(name).strip()
    return CIRCUIT_ALIASES.get(name, name)


def _get_or_create(db: Session, model, defaults: dict | None = None, **keys):
    obj = db.scalar(select(model).filter_by(**keys))
    if obj is None:
        obj = model(**keys, **(defaults or {}))
        db.add(obj)
        db.flush()
    elif defaults:
        for k, v in defaults.items():
            if v is not None:
                setattr(obj, k, v)
    return obj


def upsert_schedule(db: Session, year: int, schedule: pd.DataFrame) -> int:
    season = _get_or_create(db, m.Season, year=year)
    for _, row in schedule.iterrows():
        circuit = _get_or_create(
            db, m.Circuit, defaults={"country": num_or_none(row.get("Country"))}, name=canonical_circuit(row["Location"])
        )
        event = _get_or_create(
            db, m.Event, season_id=season.id, round_number=int(row["RoundNumber"]),
            defaults={
                "event_name": str(row["EventName"]), "circuit_id": circuit.id,
                "event_date": pd.Timestamp(row["EventDate"]).to_pydatetime() if pd.notna(row.get("EventDate")) else None,
            },
        )
        # Create only: never overwrite the status of a session that was already ingested.
        if db.scalar(select(m.SessionRow).filter_by(event_id=event.id, session_type="R")) is None:
            db.add(m.SessionRow(event_id=event.id, session_type="R", status="scheduled"))
    db.commit()
    return len(schedule)


def ingest_loaded_session(
    db: Session, ff_session, year: int, session_type: str, telemetry: dict | None = None
) -> dict:
    """Persist an already-loaded FastF1-like session. Returns a summary (no raw telemetry)."""
    ev = ff_session.event
    laps = ff_session.laps.copy()
    warnings = validation.validate_laps(laps)
    laps = laps.drop_duplicates(subset=["Driver", "LapNumber"])
    laps = add_seconds(classify_laps(laps, session_type))

    season = _get_or_create(db, m.Season, year=year)
    circuit = _get_or_create(
        db, m.Circuit, defaults={"country": num_or_none(ev.get("Country"))}, name=canonical_circuit(ev["Location"])
    )
    event = _get_or_create(
        db, m.Event, season_id=season.id, round_number=int(ev["RoundNumber"]),
        defaults={"event_name": str(ev["EventName"]), "circuit_id": circuit.id},
    )
    sess = _get_or_create(db, m.SessionRow, event_id=event.id, session_type=session_type)
    sess.status = "loaded"
    sess.source_identifier = f"fastf1:{year}:{int(ev['RoundNumber'])}:{session_type}"
    sess.completeness = completeness_report(laps)

    run = m.IngestionRun(session_id=sess.id, request={"year": year, "round": int(ev["RoundNumber"]), "session": session_type})
    db.add(run)
    db.flush()

    try:
        entries = _persist_entries(db, sess, ff_session, laps)
        n_laps = _replace_laps(db, entries, laps)
        n_stops = _replace_pit_stops(db, entries, laps)
        n_tel = _replace_telemetry(db, entries, telemetry or {})
        run.status = "success"
        run.records_processed = n_laps + n_stops + n_tel
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        db.add(m.IngestionRun(status="failed", error_message=str(exc)[:500],
                              request={"year": year, "session": session_type},
                              completed_at=datetime.now(timezone.utc)))
        db.commit()
        raise

    return {
        "session_id": sess.id, "year": year, "round": event.round_number, "session_type": session_type,
        "laps": n_laps, "pit_stops": n_stops, "telemetry_points": n_tel,
        "completeness": sess.completeness, "warnings": warnings,
    }


def _persist_entries(db, sess, ff_session, laps) -> dict[str, m.SessionEntry]:
    results = getattr(ff_session, "results", None)
    res_by_code = {}
    if results is not None and len(results):
        res_by_code = {r["Abbreviation"]: r for _, r in results.iterrows()}
    team_by_code = laps.groupby("Driver")["Team"].first().to_dict() if "Team" in laps else {}
    entries = {}
    for code in laps["Driver"].dropna().unique():
        r = res_by_code.get(code)
        driver = _get_or_create(
            db, m.Driver, code=code,
            defaults={
                "driver_number": num_or_none(r["DriverNumber"]) if r is not None else None,
                "full_name": num_or_none(r.get("FullName")) if r is not None else None,
            },
        )
        team = num_or_none(r.get("TeamName")) if r is not None else None
        team = team or num_or_none(team_by_code.get(code))
        constructor = _get_or_create(db, m.Constructor, name=str(team)) if team else None
        entry = _get_or_create(db, m.SessionEntry, session_id=sess.id, driver_id=driver.id)
        entry.constructor_id = constructor.id if constructor else None
        if r is not None:
            entry.grid_position = _int_or_none(r.get("GridPosition"))
            entry.finish_position = _int_or_none(r.get("Position"))
            entry.points = num_or_none(r.get("Points"))
            entry.status = num_or_none(r.get("Status"))
        entries[code] = entry
    db.flush()
    return entries


def _int_or_none(v):
    v = num_or_none(v)
    return None if v is None or v == 0 else int(v)  # FastF1 uses 0 for "no grid slot"


def _replace_laps(db, entries, laps) -> int:
    ids = [e.id for e in entries.values()]
    old = db.scalars(select(m.Lap.id).where(m.Lap.session_entry_id.in_(ids))).all()
    if old:
        db.execute(delete(m.TelemetryPoint).where(m.TelemetryPoint.lap_id.in_(old)))
    db.execute(delete(m.Lap).where(m.Lap.session_entry_id.in_(ids)))
    rows = []
    for r in laps.itertuples(index=False):
        d = r._asdict()
        rows.append(m.Lap(
            session_entry_id=entries[d["Driver"]].id,
            lap_number=int(d["LapNumber"]),
            lap_time_ms=td_to_ms(d.get("LapTime")),
            sector1_ms=td_to_ms(d.get("Sector1Time")),
            sector2_ms=td_to_ms(d.get("Sector2Time")),
            sector3_ms=td_to_ms(d.get("Sector3Time")),
            compound=num_or_none(d.get("Compound")),
            tyre_life=num_or_none(d.get("TyreLife")),
            stint=_int_or_none(d.get("Stint")),
            position=_int_or_none(d.get("Position")),
            is_valid=bool(d["IsValid"]),
            is_personal_best=None if num_or_none(d.get("IsPersonalBest")) is None else bool(d["IsPersonalBest"]),
            is_pit_lap=bool(d["IsPitLap"]),
            track_status=num_or_none(d.get("TrackStatus")),
            invalid_reason=d.get("InvalidReason"),
        ))
    db.add_all(rows)
    db.flush()
    return len(rows)


def _replace_pit_stops(db, entries, laps) -> int:
    ids = [e.id for e in entries.values()]
    db.execute(delete(m.PitStop).where(m.PitStop.session_entry_id.in_(ids)))
    stops = derive_pit_stops(laps)
    db.add_all(
        m.PitStop(session_entry_id=entries[s["driver"]].id, lap_number=s["lap_number"], duration_ms=s["duration_ms"])
        for s in stops
    )
    db.flush()
    return len(stops)


def _replace_telemetry(db, entries, telemetry) -> int:
    n = 0
    for code, (lap_number, tel) in telemetry.items():
        entry = entries.get(code)
        if entry is None:
            continue
        lap = db.scalar(select(m.Lap).where(m.Lap.session_entry_id == entry.id, m.Lap.lap_number == lap_number))
        if lap is None:
            continue
        for i, r in enumerate(tel.itertuples(index=False)):
            d = r._asdict()
            db.add(m.TelemetryPoint(
                lap_id=lap.id, sample_index=i, distance_m=num_or_none(d.get("Distance")),
                time_ms=td_to_ms(d.get("Time")), x=num_or_none(d.get("X")), y=num_or_none(d.get("Y")),
                speed_kph=num_or_none(d.get("Speed")), throttle=num_or_none(d.get("Throttle")),
                brake=None if num_or_none(d.get("Brake")) is None else float(d["Brake"]),
                gear=_int_or_none(d.get("nGear")), rpm=num_or_none(d.get("RPM")),
            ))
            n += 1
    db.flush()
    return n


def ingest_session(db: Session, year: int, event_name: str, session_type: str, include_telemetry: bool = True) -> dict:
    """Load from FastF1, then persist. Returns a summary, not raw telemetry."""
    from app.data import fastf1_loader

    validation.validate_request(year, event_name, session_type)
    ff = fastf1_loader.load_session(year, event_name, session_type, telemetry=include_telemetry)
    try:
        ff.laps  # raises DataNotLoadedError when the upstream load failed
    except Exception as exc:
        raise validation.IngestionError(
            "FastF1 returned no lap data. FastF1 3.9 may require a Formula 1 account sign-in "
            "(see fastf1 docs), or the session is unavailable."
        ) from exc
    tel = fastf1_loader.extract_fastest_lap_telemetry(ff) if include_telemetry else {}
    return ingest_loaded_session(db, ff, year, session_type, tel)
