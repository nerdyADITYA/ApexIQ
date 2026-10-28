"""Interpretable tyre degradation model.

lap_time = base_compound + b1*age + b2*age^2 + b3*lap_number + eps

`lap_number` is a *fuel-load proxy* (fuel burn makes the car faster as the race
progresses). It is an assumption, not a measurement. Estimates are model-based,
not tyre-wear sensor readings.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_LAPS_PER_COMPOUND = 8
MIN_TOTAL_LAPS = 15


@dataclass
class DegradationModel:
    compounds: list[str]
    base: dict[str, float]          # intercept per compound (s)
    age_linear: float
    age_quadratic: float
    fuel_per_lap: float             # s per lap of race progress (usually negative)
    resid_std: float
    n_laps: int
    max_age: dict[str, float] = field(default_factory=dict)  # longest observed stint per compound
    warnings: list[str] = field(default_factory=list)

    def lap_time(self, compound: str, age: float, lap_number: float) -> float:
        return (self.base[compound] + self.age_linear * age
                + self.age_quadratic * age ** 2 + self.fuel_per_lap * lap_number)


class InsufficientDataError(Exception):
    pass


def fit_degradation(laps: pd.DataFrame) -> DegradationModel:
    """Fit on clean laps. Columns: compound, tyre_life, lap_number, lap_time_s."""
    d = laps.dropna(subset=["compound", "tyre_life", "lap_number", "lap_time_s"])
    counts = d["compound"].value_counts()
    keep = counts[counts >= MIN_LAPS_PER_COMPOUND].index
    warnings = [f"{c}: only {counts[c]} laps, excluded" for c in counts.index if c not in keep]
    d = d[d["compound"].isin(keep)]
    if len(d) < MIN_TOTAL_LAPS or len(keep) == 0:
        raise InsufficientDataError("Not enough clean laps to fit a degradation model")

    compounds = sorted(keep)
    X = np.column_stack(
        [(d["compound"] == c).astype(float) for c in compounds]
        + [d["tyre_life"], d["tyre_life"] ** 2, d["lap_number"]]
    )
    y = d["lap_time_s"].to_numpy()
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = max(len(y) - X.shape[1], 1)
    k = len(compounds)
    if coef[k + 1] < 0:
        warnings.append("Quadratic age term negative; degradation extrapolation may be unreliable.")
    return DegradationModel(
        compounds=compounds,
        base=dict(zip(compounds, coef[:k])),
        age_linear=float(coef[k]), age_quadratic=float(coef[k + 1]), fuel_per_lap=float(coef[k + 2]),
        resid_std=float(np.sqrt((resid ** 2).sum() / dof)), n_laps=len(y), warnings=warnings,
        max_age={c: float(d.loc[d["compound"] == c, "tyre_life"].max()) for c in compounds},
    )
