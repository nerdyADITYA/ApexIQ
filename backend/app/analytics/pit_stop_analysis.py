"""Pit-lane time loss estimate for the strategy simulator.

A stop costs the time lost over the in-lap and the out-lap compared with normal laps. We measure it per
stop as (in-lap + out-lap) - 2 x the driver's *local* clean pace around that stop, then take the median.

Robustness rules (each exists because the naive version gave 30 to 49 s in about a sixth of real races):
- Local baseline: pace is taken from the driver's own valid laps just before and after the stop, so a race whose
  pace shifts (rain drying, track evolution, fuel) does not poison the baseline the way a whole-race median does.
- Neutralised stops are skipped: a stop under a safety car, virtual safety car or red flag costs a different
  amount and the surrounding laps are slow for another reason. Judged from the laps' track status, because the
  stored validity reason of a pit lap hides that it was also neutralised.
- Dry tyres only: stops involving intermediate or wet tyres reflect changing conditions, not the stop itself.
- Race-level plausibility: if too few stops survive, the stops disagree, or the median is outside a plausible
  range, the typical value is used instead and the result says so.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_PIT_LOSS_S = 22.0   # ~ median of the measured per-race estimates over 2023 to 2026 (22.3 s)
PLAUSIBLE_RANGE_S = (15.0, 35.0)
ARTEFACT_RANGE_S = (8.0, 50.0)  # single-stop values outside this are measurement artefacts, dropped
MAX_SPREAD_S = 10.0             # inter-quartile range of the per-stop estimates
MIN_STOPS = 4
LOCAL_WINDOW = 6                # laps either side of the stop used for the baseline
MIN_LOCAL_LAPS = 4
DRY = {"SOFT", "MEDIUM", "HARD"}
NEUTRAL_CODES = set("4567")     # 4 safety car, 5 red flag, 6 VSC, 7 VSC ending


@dataclass
class PitLoss:
    value: float
    source: str            # "measured" or "default"
    n_stops: int           # stops that survived the filters
    spread: float | None   # inter-quartile range of per-stop estimates
    warning: str | None


def _is_neutralised(row) -> bool:
    status = str(row.get("track_status") or "")
    return bool(row.get("neutralised")) or any(c in NEUTRAL_CODES for c in status)


def stop_losses(laps: pd.DataFrame) -> list[float]:
    """Per-stop loss estimates (s). Expects driver, lap_number, lap_time_s, is_valid, is_pit_lap, compound,
    and optionally neutralised / track_status."""
    valid = laps[laps["is_valid"] & laps["lap_time_s"].notna()]
    losses: list[float] = []
    for driver, grp in laps.sort_values("lap_number").groupby("driver"):
        g = grp.drop_duplicates("lap_number").set_index("lap_number")
        pace = valid[valid["driver"] == driver].drop_duplicates("lap_number").set_index("lap_number")["lap_time_s"]
        for ln in g.index[g["is_pit_lap"].astype(bool)]:
            nxt = ln + 1
            if nxt not in g.index or not bool(g.loc[nxt, "is_pit_lap"]):
                continue                                    # need an in-lap followed by an out-lap
            if (ln - 1) in g.index and bool(g.loc[ln - 1, "is_pit_lap"]):
                continue                                    # ln is itself an out-lap, not an in-lap
            pair = g.loc[[ln, nxt]]
            if pair["lap_time_s"].isna().any():
                continue
            if any(_is_neutralised(r) for _, r in pair.iterrows()):
                continue
            if not pair["compound"].astype(str).str.upper().isin(DRY).all():
                continue
            local = pace[((pace.index >= ln - LOCAL_WINDOW) & (pace.index <= nxt + LOCAL_WINDOW))]
            if len(local) < MIN_LOCAL_LAPS:
                continue
            losses.append(float(pair["lap_time_s"].sum() - 2 * local.median()))
    lo, hi = ARTEFACT_RANGE_S
    return [x for x in losses if lo < x < hi]


def estimate_pit_loss_detail(laps: pd.DataFrame) -> PitLoss:
    losses = stop_losses(laps)
    if len(losses) < MIN_STOPS:
        return PitLoss(DEFAULT_PIT_LOSS_S, "default", len(losses), None,
                       f"Only {len(losses)} clean dry pit stops in this race, so a typical pit loss of "
                       f"{DEFAULT_PIT_LOSS_S:.0f} s is used instead of a measured one.")
    value = float(np.median(losses))
    q1, q3 = np.percentile(losses, [25, 75])
    spread = float(q3 - q1)
    lo, hi = PLAUSIBLE_RANGE_S
    if not lo <= value <= hi:
        return PitLoss(DEFAULT_PIT_LOSS_S, "default", len(losses), spread,
                       f"This race's stops imply a pit loss of {value:.0f} s, outside the plausible {lo:.0f} to {hi:.0f} s "
                       f"(changing conditions or disruption), so a typical {DEFAULT_PIT_LOSS_S:.0f} s is used.")
    if spread > MAX_SPREAD_S:
        return PitLoss(DEFAULT_PIT_LOSS_S, "default", len(losses), spread,
                       f"Pit stop times in this race vary too much (spread {spread:.0f} s) to measure reliably, "
                       f"so a typical {DEFAULT_PIT_LOSS_S:.0f} s is used.")
    return PitLoss(value, "measured", len(losses), spread, None)


def estimate_pit_loss(laps: pd.DataFrame) -> tuple[float, str | None]:
    """(value, warning) form kept for existing callers."""
    r = estimate_pit_loss_detail(laps)
    return r.value, r.warning
