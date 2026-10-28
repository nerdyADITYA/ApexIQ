"""Pure DataFrame transformations (no I/O) so they are easy to unit test."""

import numpy as np
import pandas as pd

TIME_COLUMNS = ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]
DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}
# FastF1 TrackStatus codes: 1 clear, 2 yellow, 4 SC, 5 red, 6 VSC, 7 VSC ending
NEUTRALISED_CODES = set("4567")


def td_to_ms(value) -> int | None:
    """Timedelta -> integer ms. NaT/NaN/None -> None (never zero)."""
    if value is None or pd.isna(value):
        return None
    return int(round(pd.Timedelta(value).total_seconds() * 1000))


def num_or_none(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return None
    return value


def classify_laps(laps: pd.DataFrame, session_type: str = "R") -> pd.DataFrame:
    """Add `IsPitLap`, `IsNeutralised`, `IsValid`, `InvalidReason`.

    A lap is valid for normal pace analysis when it has a lap time, is not an
    in/out lap, was not run under SC/VSC/red flag, and (when FastF1 provides the
    flag) was not deleted. Source rows are never dropped; they are flagged.
    """
    df = laps.copy()
    n = len(df)
    pit_in = df["PitInTime"].notna() if "PitInTime" in df else pd.Series(False, index=df.index)
    pit_out = df["PitOutTime"].notna() if "PitOutTime" in df else pd.Series(False, index=df.index)
    df["IsPitLap"] = pit_in | pit_out

    if "TrackStatus" in df:
        status = df["TrackStatus"].fillna("").astype(str)
        df["IsNeutralised"] = status.map(lambda s: any(c in NEUTRALISED_CODES for c in s))
    else:
        df["IsNeutralised"] = False

    no_time = df["LapTime"].isna() if "LapTime" in df else pd.Series(True, index=df.index)
    deleted = df["Deleted"].fillna(False).astype(bool) if "Deleted" in df else pd.Series(False, index=df.index)

    reason = pd.Series([None] * n, index=df.index, dtype=object)
    # order matters: first matching reason wins
    reason[df["IsNeutralised"]] = "neutralised"
    reason[df["IsPitLap"]] = "pit"
    reason[deleted] = "deleted"
    reason[no_time] = "no_time"
    df["InvalidReason"] = reason
    df["IsValid"] = reason.isna()
    if session_type.upper().startswith("Q"):
        # qualifying: pit/out laps are routine; keep flagged but don't treat as neutralised
        pass
    return df


def add_seconds(df: pd.DataFrame, columns=TIME_COLUMNS) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out:
            out[f"{col}Seconds"] = out[col].dt.total_seconds()
    return out


def clean_lap_times(laps: pd.DataFrame) -> pd.DataFrame:
    """Valid, representative race laps: valid flag plus a 107% of per-driver
    median outlier trim. Returns a filtered copy; excluded counts are the
    caller's responsibility (len difference)."""
    valid = laps[laps["IsValid"]].copy()
    if valid.empty:
        return valid
    med = valid.groupby("Driver")["LapTimeSeconds"].transform("median")
    return valid[valid["LapTimeSeconds"] <= med * 1.07]


def completeness_report(laps: pd.DataFrame, expected=("LapTime", "Sector1Time", "Compound", "TyreLife")) -> dict:
    report = {"rows": int(len(laps))}
    for col in expected:
        report[col] = float(laps[col].notna().mean()) if col in laps and len(laps) else None
    return report


def derive_pit_stops(laps: pd.DataFrame) -> list[dict]:
    """One pit stop per in-lap. Duration is in-lap-in to next out-lap-out
    when both timestamps exist (pit-lane time), otherwise None."""
    stops = []
    if "PitInTime" not in laps:
        return stops
    for driver, grp in laps.sort_values("LapNumber").groupby("Driver"):
        grp = grp.reset_index(drop=True)
        for i, row in grp.iterrows():
            if pd.isna(row["PitInTime"]):
                continue
            duration = None
            if i + 1 < len(grp) and pd.notna(grp.loc[i + 1, "PitOutTime"]):
                duration = td_to_ms(grp.loc[i + 1, "PitOutTime"] - row["PitInTime"])
            stops.append({"driver": driver, "lap_number": int(row["LapNumber"]), "duration_ms": duration})
    return stops


def downsample_telemetry(tel: pd.DataFrame, max_points: int = 400) -> pd.DataFrame:
    if len(tel) <= max_points:
        return tel
    idx = np.linspace(0, len(tel) - 1, max_points).round().astype(int)
    return tel.iloc[np.unique(idx)]
