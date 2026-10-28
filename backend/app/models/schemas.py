from datetime import datetime

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    year: int = Field(ge=2018, le=2100)
    event: str = Field(min_length=1, max_length=120)
    session_type: str = Field(default="R", pattern="^(FP1|FP2|FP3|Q|SQ|SS|S|R)$")
    include_telemetry: bool = True


class IngestionJob(BaseModel):
    job_id: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    records_processed: int = 0


class StrategyRequest(BaseModel):
    session_id: int
    driver_code: str = Field(min_length=2, max_length=4)
    stint_compounds: list[str] = Field(min_length=1, max_length=6)
    pit_laps: list[int] = Field(default_factory=list, max_length=5)
    simulation_runs: int = Field(default=1000, ge=100, le=20000)


class StrategyResponse(BaseModel):
    estimated_race_time_seconds: float | None
    baseline_delta_seconds: float | None
    uncertainty_interval_seconds: tuple[float, float] | None
    stints: list[dict]
    constraint_violations: list[str]
    warnings: list[str]
    model_version: str
    pit_loss_seconds: float | None = None
    pit_loss_source: str | None = None   # "measured" from this race's stops, or "default" typical value
    pit_loss_stops: int | None = None    # clean dry stops the estimate is based on
    actual_stints: list[dict] = Field(default_factory=list)
    profile: list[dict] = Field(default_factory=list)  # per-lap pace and running time difference
    generated_at: datetime
