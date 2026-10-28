"""Strategy simulation on top of the fitted degradation model.

Both the actual strategy and each alternative are evaluated with the *same*
model, so the reported delta is model-vs-model (it cancels much of the model's
bias) rather than model-vs-actual-clock-time. Uncertainty comes from Monte
Carlo resampling of lap residuals, so it covers lap-to-lap noise only; it does
NOT cover traffic, safety cars, weather or competitor reaction.
"""

from dataclasses import dataclass, field

import numpy as np

from app.analytics.tire_degradation import DegradationModel
from app.strategy.constraints import check_strategy

MODEL_VERSION = "strategy-v1"


@dataclass
class StrategyResult:
    compounds: list[str]
    pit_laps: list[int]
    stints: list[dict]
    estimated_race_time_s: float | None
    baseline_delta_s: float | None
    uncertainty_interval_s: tuple[float, float] | None
    constraint_violations: list[str]
    warnings: list[str]
    model_version: str = MODEL_VERSION
    profile: list[dict] = field(default_factory=list)        # per-lap picture, see strategy_profile
    actual_stints: list[dict] = field(default_factory=list)


def stint_layout(pit_laps: list[int], total_laps: int) -> list[tuple[int, int]]:
    starts = [1, *[p + 1 for p in pit_laps]]
    ends = [*pit_laps, total_laps]
    return list(zip(starts, ends))


def lap_paces(model, compounds, pit_laps, total_laps, start_age=0) -> list[float]:
    """Modelled lap time (s) for every lap of a strategy, excluding the time lost in the pit lane."""
    out = []
    for (a, b), c in zip(stint_layout(pit_laps, total_laps), compounds):
        for lap in range(a, b + 1):
            age = (lap - a) + (start_age if a == 1 else 0) + 1
            out.append(model.lap_time(c, age, lap))
    return out


def _race_time(model, compounds, pit_laps, total_laps, pit_loss, start_age=0):
    return sum(lap_paces(model, compounds, pit_laps, total_laps, start_age)) + pit_loss * len(pit_laps)


Z90 = 1.645  # two-sided 90% normal quantile


def strategy_profile(model, actual, candidate, total_laps, pit_loss) -> list[dict]:
    """Lap-by-lap comparison of two strategies under the same model.

    `cumulative_delta_s` is what-if minus actual so far (positive = the what-if is behind), including the pit
    loss on each stop lap, so its last value equals the reported total difference. `band_s` is the half-width
    of the approximate 90% interval after that many laps: lap residuals are independent, so the difference of
    two n-lap sums has standard deviation sigma * sqrt(2 n).
    """
    a_comps, a_pits = [c.upper() for c in actual[0]], list(actual[1])
    c_comps, c_pits = [c.upper() for c in candidate[0]], list(candidate[1])
    pa = lap_paces(model, a_comps, a_pits, total_laps)
    pc = lap_paces(model, c_comps, c_pits, total_laps)
    cum, rows = 0.0, []
    for i in range(total_laps):
        lap = i + 1
        cum += (pc[i] + (pit_loss if lap in c_pits else 0.0)) - (pa[i] + (pit_loss if lap in a_pits else 0.0))
        rows.append({
            "lap": lap, "actual_pace_s": round(pa[i], 3), "candidate_pace_s": round(pc[i], 3),
            "cumulative_delta_s": round(cum, 3), "band_s": round(Z90 * model.resid_std * float(np.sqrt(2 * lap)), 3),
        })
    return rows


def simulate_strategy(
    model: DegradationModel,
    total_laps: int,
    pit_loss_s: float,
    actual: tuple[list[str], list[int]],
    candidate: tuple[list[str], list[int]],
    runs: int = 1000,
    seed: int = 0,
    extra_warnings: list[str] | None = None,
) -> StrategyResult:
    compounds = [c.upper() for c in candidate[0]]
    pit_laps = list(candidate[1])
    warnings = list(model.warnings) + list(extra_warnings or [])
    violations = check_strategy(compounds, pit_laps, total_laps)
    unknown = [c for c in compounds + [c.upper() for c in actual[0]] if c not in model.base]
    if unknown:
        violations.append(f"No fitted degradation data for compound(s): {sorted(set(unknown))}")
    if violations:
        return StrategyResult(compounds, pit_laps, [], None, None, None, violations, warnings)

    for label, (comps, pits) in (("Candidate", (compounds, pit_laps)), ("Actual", ([c.upper() for c in actual[0]], actual[1]))):
        for (a, b), c in zip(stint_layout(pits, total_laps), comps):
            if b - a + 1 > model.max_age.get(c, 0) + 2:
                warnings.append(f"{label} {c} stint of {b - a + 1} laps exceeds the longest observed ({model.max_age[c]:.0f}); extrapolated.")
    base_t = _race_time(model, [c.upper() for c in actual[0]], actual[1], total_laps, pit_loss_s)
    cand_t = _race_time(model, compounds, pit_laps, total_laps, pit_loss_s)

    # Residuals are independent per lap in this model; the difference of two sums of
    # (total_laps) residuals has std = sqrt(2 * N) * sigma. Differences in pit-count
    # do not change the lap count, so the same N applies.
    rng = np.random.default_rng(seed)
    sigma = model.resid_std * np.sqrt(2 * total_laps)
    draws = (cand_t - base_t) + rng.normal(0.0, sigma, size=runs)
    lo, hi = np.percentile(draws, [5, 95])
    warnings.append("Interval reflects lap-to-lap noise only; excludes traffic, safety cars, weather and rivals.")
    stints = [
        {"compound": c, "start_lap": a, "end_lap": b}
        for (a, b), c in zip(stint_layout(pit_laps, total_laps), compounds)
    ]
    actual_stints = [
        {"compound": c.upper(), "start_lap": a, "end_lap": b}
        for (a, b), c in zip(stint_layout(list(actual[1]), total_laps), actual[0])
    ]
    profile = strategy_profile(model, actual, (compounds, pit_laps), total_laps, pit_loss_s)
    return StrategyResult(compounds, pit_laps, stints, cand_t, cand_t - base_t, (float(lo), float(hi)), [], warnings,
                          profile=profile, actual_stints=actual_stints)


def enumerate_candidates(total_laps: int, compounds=("SOFT", "MEDIUM", "HARD"), max_stops: int = 2, step: int = 3):
    """Generate legal one- and two-stop candidates on a coarse pit-lap grid."""
    out = []
    laps = range(5, total_laps - 4, step)
    for c1 in compounds:
        for c2 in compounds:
            if c1 == c2:
                continue
            out += [([c1, c2], [p]) for p in laps]
            if max_stops >= 2:
                for c3 in compounds:
                    out += [([c1, c2, c3], [p, q]) for p in laps for q in laps if q - p >= 5
                            and len({c1, c2, c3}) >= 2]
    return [c for c in out if not check_strategy(c[0], c[1], total_laps)]


def best_strategy(model, total_laps, pit_loss_s, actual, **kw):
    ranked = []
    for comp, pits in enumerate_candidates(total_laps, tuple(model.compounds)):
        ranked.append((_race_time(model, comp, pits, total_laps, pit_loss_s), comp, pits))
    ranked.sort(key=lambda x: x[0])
    return [simulate_strategy(model, total_laps, pit_loss_s, actual, (c, p), **kw) for _, c, p in ranked[:5]]
