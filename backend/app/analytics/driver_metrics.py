"""Driver pace metrics computed from lap DataFrames.

Expected columns: driver, constructor, lap_number, lap_time_s, is_valid.
Baselines are always explicit: deltas are relative to a named reference.
"""

import numpy as np
import pandas as pd


def clean_laps(laps: pd.DataFrame, trim: float = 1.07) -> pd.DataFrame:
    """Valid laps within `trim` x the driver's median. Callers compare len() for exclusion counts."""
    v = laps[laps["is_valid"] & laps["lap_time_s"].notna()]
    med = v.groupby("driver")["lap_time_s"].transform("median")
    return v[v["lap_time_s"] <= med * trim]


def pace_summary(laps: pd.DataFrame) -> pd.DataFrame:
    """Per-driver median clean pace, consistency (MAD), sample sizes, delta to fastest median."""
    clean = clean_laps(laps)
    total = laps.groupby("driver").size().rename("total_laps")
    if clean.empty:
        return pd.DataFrame(columns=["driver", "median_s", "mad_s", "clean_laps", "total_laps", "delta_to_best_s"])
    g = clean.groupby("driver")["lap_time_s"]
    out = pd.DataFrame({
        "median_s": g.median(),
        "mad_s": g.apply(lambda s: float(np.median(np.abs(s - s.median())))),
        "clean_laps": g.size(),
    }).join(total)
    out["excluded_laps"] = out["total_laps"] - out["clean_laps"]
    out["delta_to_best_s"] = out["median_s"] - out["median_s"].min()
    return out.reset_index().sort_values("median_s")


def teammate_delta(laps: pd.DataFrame) -> pd.DataFrame:
    """Driver median minus teammate median (negative = faster than teammate)."""
    s = pace_summary(laps).merge(laps[["driver", "constructor"]].drop_duplicates(), on="driver")
    rows = []
    for _, grp in s.groupby("constructor"):
        if len(grp) < 2:
            continue
        for _, r in grp.iterrows():
            others = grp[grp["driver"] != r["driver"]]["median_s"]
            rows.append({"driver": r["driver"], "constructor": r["constructor"],
                         "delta_to_teammate_s": float(r["median_s"] - others.mean())})
    return pd.DataFrame(rows, columns=["driver", "constructor", "delta_to_teammate_s"])


def sector_deltas(laps: pd.DataFrame, reference: str) -> pd.DataFrame:
    """Median sector delta vs `reference` driver (negative = faster). Reference is explicit."""
    cols = ["sector1_s", "sector2_s", "sector3_s"]
    med = clean_laps(laps).groupby("driver")[cols].median()
    if reference not in med.index:
        raise KeyError(f"reference driver {reference} has no clean laps")
    return (med - med.loc[reference]).reset_index()
