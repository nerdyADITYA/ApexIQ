"""SQLAlchemy models. All times are stored in integer milliseconds unless the
column name says otherwise. NULL means "missing", never zero."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(String(20), default="partial")


class Circuit(Base):
    __tablename__ = "circuits"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    country: Mapped[str | None] = mapped_column(String(80))
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    track_length_m: Mapped[float | None]
    geometry_source: Mapped[str | None] = mapped_column(String(80))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("season_id", "round_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    circuit_id: Mapped[int | None] = mapped_column(ForeignKey("circuits.id"), index=True)
    round_number: Mapped[int]
    event_name: Mapped[str] = mapped_column(String(120))
    event_date: Mapped[datetime | None] = mapped_column(DateTime)
    circuit: Mapped["Circuit | None"] = relationship()


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("event_id", "session_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    session_type: Mapped[str] = mapped_column(String(10))  # R, Q, S, FP1...
    session_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    source_identifier: Mapped[str | None] = mapped_column(String(120))
    completeness: Mapped[dict | None] = mapped_column(JsonType)
    event: Mapped["Event"] = relationship()


class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_number: Mapped[str | None] = mapped_column(String(4))
    code: Mapped[str] = mapped_column(String(4), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    nationality: Mapped[str | None] = mapped_column(String(60))


class Constructor(Base):
    __tablename__ = "constructors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    short_name: Mapped[str | None] = mapped_column(String(40))


class SessionEntry(Base):
    __tablename__ = "session_entries"
    __table_args__ = (UniqueConstraint("session_id", "driver_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    constructor_id: Mapped[int | None] = mapped_column(ForeignKey("constructors.id"), index=True)
    grid_position: Mapped[int | None]
    finish_position: Mapped[int | None]
    points: Mapped[float | None]
    status: Mapped[str | None] = mapped_column(String(60))
    driver: Mapped["Driver"] = relationship()
    constructor: Mapped["Constructor | None"] = relationship()


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (
        UniqueConstraint("session_entry_id", "lap_number"),
        Index("ix_laps_entry_valid", "session_entry_id", "is_valid"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_entry_id: Mapped[int] = mapped_column(ForeignKey("session_entries.id"), index=True)
    lap_number: Mapped[int]
    lap_time_ms: Mapped[int | None]
    sector1_ms: Mapped[int | None]
    sector2_ms: Mapped[int | None]
    sector3_ms: Mapped[int | None]
    compound: Mapped[str | None] = mapped_column(String(20))
    tyre_life: Mapped[float | None]
    stint: Mapped[int | None]
    position: Mapped[int | None]
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    is_personal_best: Mapped[bool | None] = mapped_column(Boolean)
    is_pit_lap: Mapped[bool] = mapped_column(Boolean, default=False)
    track_status: Mapped[str | None] = mapped_column(String(20))
    invalid_reason: Mapped[str | None] = mapped_column(String(60))


class PitStop(Base):
    __tablename__ = "pit_stops"
    __table_args__ = (UniqueConstraint("session_entry_id", "lap_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_entry_id: Mapped[int] = mapped_column(ForeignKey("session_entries.id"), index=True)
    lap_number: Mapped[int]
    duration_ms: Mapped[int | None]
    pit_lane_loss_ms: Mapped[int | None]


class TelemetryPoint(Base):
    __tablename__ = "telemetry_points"
    __table_args__ = (UniqueConstraint("lap_id", "sample_index"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lap_id: Mapped[int] = mapped_column(ForeignKey("laps.id"), index=True)
    sample_index: Mapped[int]
    distance_m: Mapped[float | None]
    time_ms: Mapped[int | None]
    x: Mapped[float | None]
    y: Mapped[float | None]
    speed_kph: Mapped[float | None]
    throttle: Mapped[float | None]
    brake: Mapped[float | None]
    gear: Mapped[int | None]
    rpm: Mapped[float | None]


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    time_ms: Mapped[int | None]  # offset from session start
    air_temp: Mapped[float | None]
    track_temp: Mapped[float | None]
    humidity: Mapped[float | None]
    wind_speed: Mapped[float | None]
    rainfall: Mapped[bool | None] = mapped_column(Boolean)


class DriverStanding(Base):
    __tablename__ = "driver_standings"
    __table_args__ = (UniqueConstraint("season_id", "round_number", "driver_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    round_number: Mapped[int]
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    points: Mapped[float]
    position: Mapped[int]


class ConstructorStanding(Base):
    __tablename__ = "constructor_standings"
    __table_args__ = (UniqueConstraint("season_id", "round_number", "constructor_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    round_number: Mapped[int]
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"))
    points: Mapped[float]
    position: Mapped[int]


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    round_number: Mapped[int]
    entity_type: Mapped[str] = mapped_column(String(20))  # driver | constructor
    entity_id: Mapped[int]
    win_probability: Mapped[float]
    model_version: Mapped[str] = mapped_column(String(60))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    evaluation_metadata: Mapped[dict | None] = mapped_column(JsonType)


class StrategyScenario(Base):
    __tablename__ = "strategy_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    config_json: Mapped[dict] = mapped_column(JsonType)
    estimated_race_time_ms: Mapped[int | None]
    baseline_delta_ms: Mapped[int | None]
    uncertainty_metadata: Mapped[dict | None] = mapped_column(JsonType)
    model_version: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class RaceForecastSnapshot(Base):
    """A forecast saved before its race. One row per (season, round, mode); it is replaced by newer forecasts only
    while the race has not been run, and never changes once the race result exists (see forecast_service)."""
    __tablename__ = "race_forecast_snapshots"
    __table_args__ = (UniqueConstraint("year", "round_number", "mode"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(index=True)
    round_number: Mapped[int]
    mode: Mapped[str] = mapped_column(String(20))            # pre-qualifying | post-qualifying
    model_version: Mapped[str] = mapped_column(String(80))
    as_of_round: Mapped[int]
    n_simulations: Mapped[int]
    seed: Mapped[int]
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    payload: Mapped[dict] = mapped_column(JsonType)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    request: Mapped[dict | None] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None]
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
