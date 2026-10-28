import pandas as pd

VALID_SESSION_TYPES = {"FP1", "FP2", "FP3", "Q", "SQ", "SS", "S", "R"}


class IngestionError(Exception):
    pass


def validate_request(year: int, event_name: str, session_type: str) -> None:
    if not 2018 <= year <= 2100:
        raise IngestionError("Detailed FastF1 coverage starts in 2018")
    if session_type not in VALID_SESSION_TYPES:
        raise IngestionError(f"Unknown session type {session_type!r}")
    if not str(event_name).strip():
        raise IngestionError("event_name is required")


def validate_laps(laps: pd.DataFrame) -> list[str]:
    """Returns human-readable warnings; raises only if the data is unusable."""
    warnings = []
    for col in ("Driver", "LapNumber"):
        if col not in laps.columns:
            raise IngestionError(f"Required lap column missing: {col}")
    if laps.empty:
        raise IngestionError("Session has no laps")
    for col in ("LapTime", "Compound", "TyreLife", "Sector1Time"):
        if col not in laps.columns:
            warnings.append(f"column {col} unavailable")
    dup = laps.duplicated(subset=["Driver", "LapNumber"]).sum()
    if dup:
        warnings.append(f"{dup} duplicate (driver, lap) rows dropped")
    return warnings
