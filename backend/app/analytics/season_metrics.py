"""Season-level driver and constructor metrics from DataFrames (no DB access).

Conventions
- Pace is measured on valid race laps within 107% of the driver's own race median.
- Pace deltas are percentages relative to the FIELD median clean pace in that race
  (negative = faster). Percentages make races of different lap length comparable.
- A race only contributes if the driver has at least MIN_CLEAN_LAPS clean laps.
- Teammate comparisons use only races where both drivers have a pace estimate.
- Missing values stay None; they are never turned into zero.
"""

import numpy as np
import pandas as pd

MIN_CLEAN_LAPS = 15
SECTORS = ["s1_s", "s2_s", "s3_s"]


def is_dnf(status) -> bool:
    if status is None or (isinstance(status, float) and np.isnan(status)):
        return False
    s = str(status)
    return not (s in ("Finished", "Lapped") or s.startswith("+"))


def _num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


def clean_race_laps(laps: pd.DataFrame, trim: float = 1.07) -> pd.DataFrame:
    v = laps[laps["is_valid"] & laps["lap_time_s"].notna()].copy()
    med = v.groupby(["round", "driver"])["lap_time_s"].transform("median")
    return v[v["lap_time_s"] <= med * trim]


def race_pace_table(laps: pd.DataFrame) -> pd.DataFrame:
    """Per (round, driver): median clean pace (s), clean laps, % delta to field median.
    Also sector medians for teammate comparisons."""
    clean = clean_race_laps(laps)
    g = clean.groupby(["round", "driver"])
    t = g.agg(pace_s=("lap_time_s", "median"), clean_laps=("lap_time_s", "size"),
              s1_s=("s1_s", "median"), s2_s=("s2_s", "median"), s3_s=("s3_s", "median"),
              team=("team", "first")).reset_index()
    t = t[t["clean_laps"] >= MIN_CLEAN_LAPS]
    field = t.groupby("round")["pace_s"].transform("median")
    t["pace_delta_pct"] = (t["pace_s"] / field - 1) * 100
    return t


def teammate_gaps(pace: pd.DataFrame) -> pd.DataFrame:
    """Per (round, driver): pace gap to the teammate in %, (negative = faster than teammate).
    Rounds with a team that has other than exactly two rated drivers are skipped."""
    rows = []
    for (rnd, team), grp in pace.groupby(["round", "team"]):
        if len(grp) != 2:
            continue
        a, b = grp.iloc[0], grp.iloc[1]
        gap = (a["pace_s"] / b["pace_s"] - 1) * 100
        rows.append({"round": rnd, "driver": a["driver"], "teammate": b["driver"], "gap_pct": gap,
                     **{f"{c}_gap_s": a[c] - b[c] for c in SECTORS}})
        rows.append({"round": rnd, "driver": b["driver"], "teammate": a["driver"], "gap_pct": -gap,
                     **{f"{c}_gap_s": b[c] - a[c] for c in SECTORS}})
    return pd.DataFrame(rows, columns=["round", "driver", "teammate", "gap_pct", *[f"{c}_gap_s" for c in SECTORS]])


def stints_for(laps: pd.DataFrame, driver: str, rnd: int) -> list[dict]:
    d = laps[(laps["driver"] == driver) & (laps["round"] == rnd)].dropna(subset=["stint"]).sort_values("lap_number")
    out = []
    for stint, g in d.groupby("stint", sort=True):
        comp = g["compound"].dropna()
        out.append({"stint": int(stint), "compound": comp.iloc[0] if len(comp) else None,
                    "start_lap": int(g["lap_number"].min()), "end_lap": int(g["lap_number"].max())})
    return out


def qualifying_summary(q: pd.DataFrame) -> dict:
    pos = q["finish"].dropna()
    return {"sessions": int(len(q)), "avg_position": _num(pos.mean()) if len(pos) else None,
            "best_position": int(pos.min()) if len(pos) else None}


def driver_profile(code: str, race: pd.DataFrame, quali: pd.DataFrame, laps: pd.DataFrame,
                   sprint_points: dict[tuple, float] | None = None) -> dict:
    """race/quali are entries_frame rows for ONE season; laps is season_laps_frame(R)."""
    mine = race[race["driver"] == code].sort_values("round")
    if mine.empty:
        raise KeyError(code)
    sprint_points = sprint_points or {}
    pace = race_pace_table(laps)
    gaps = teammate_gaps(pace)
    my_pace = pace[pace["driver"] == code].set_index("round")
    my_gap = gaps[gaps["driver"] == code].set_index("round")

    fin = mine["finish"].dropna()
    classified = mine[~mine["status"].map(is_dnf)]
    rounds = []
    for r in mine.itertuples():
        rounds.append({
            "round": int(r.round), "event": r.event, "circuit": r.circuit,
            "grid": None if pd.isna(r.grid) else int(r.grid),
            "finish": None if pd.isna(r.finish) else int(r.finish),
            "points": (_num(r.points) or 0.0) + sprint_points.get((int(r.round), code), 0.0),
            "status": r.status, "dnf": is_dnf(r.status),
            "pace_delta_pct": _num(my_pace["pace_delta_pct"].get(r.round)),
            "pace_s": _num(my_pace["pace_s"].get(r.round)),
            "clean_laps": None if r.round not in my_pace.index else int(my_pace.loc[r.round, "clean_laps"]),
            "teammate_gap_pct": _num(my_gap["gap_pct"].get(r.round)),
            "stints": stints_for(laps, code, int(r.round)),
        })
    cum = 0.0
    for x in rounds:
        cum += x["points"]
        x["cumulative_points"] = cum

    q = quali[quali["driver"] == code]
    gap_vals = my_gap["gap_pct"].dropna()
    return {
        "driver": code, "name": mine["name"].iloc[0], "team": mine["team"].iloc[-1],
        "season_summary": {
            "races": int(len(mine)), "points": cum,
            "wins": int((mine["finish"] == 1).sum()), "podiums": int((mine["finish"] <= 3).sum()),
            "dnfs": int(mine["status"].map(is_dnf).sum()),
            "avg_grid": _num(mine["grid"].dropna().mean()) if mine["grid"].notna().any() else None,
            "avg_finish": _num(fin.mean()) if len(fin) else None,
            "median_finish": _num(fin.median()) if len(fin) else None,
            "avg_classified_finish": _num(classified["finish"].dropna().mean()) if len(classified) else None,
            "best_finish": int(fin.min()) if len(fin) else None,
        },
        "qualifying": qualifying_summary(q),
        "pace": {
            "median_delta_pct_vs_field": _num(my_pace["pace_delta_pct"].median()) if len(my_pace) else None,
            "consistency_mad_pct": _num((my_pace["pace_delta_pct"] - my_pace["pace_delta_pct"].median()).abs().median())
            if len(my_pace) else None,
            "rated_races": int(len(my_pace)),
            "min_clean_laps_per_race": MIN_CLEAN_LAPS,
        },
        "teammate": {
            "name": None if my_gap.empty else my_gap["teammate"].mode().iloc[0],
            "rated_races": int(len(gap_vals)),
            "median_gap_pct": _num(gap_vals.median()) if len(gap_vals) else None,
            "faster_in_races": int((gap_vals < 0).sum()),
            "sector_median_gap_s": {c: _num(my_gap[f"{c}_gap_s"].median()) for c in SECTORS} if len(my_gap) else None,
        },
        "rounds": rounds,
        "notes": [
            "Pace delta is % vs the field's median clean pace that race; negative = faster. It mixes driver and car.",
            "Teammate gap isolates the car better but depends on circumstances (strategy, traffic, incidents).",
            f"Races with fewer than {MIN_CLEAN_LAPS} clean laps are not rated.",
        ],
    }


def constructor_profile(team: str, race: pd.DataFrame, quali: pd.DataFrame, laps: pd.DataFrame,
                        pit: pd.DataFrame, sprint_points: dict[tuple, float] | None = None) -> dict:
    mine = race[race["team"] == team].sort_values(["round", "finish"])
    if mine.empty:
        raise KeyError(team)
    sprint_points = sprint_points or {}
    mine = mine.assign(total=[(_num(p) or 0.0) + sprint_points.get((int(r), d), 0.0)
                              for p, r, d in zip(mine["points"], mine["round"], mine["driver"])])
    by_round = mine.groupby("round")["total"].sum()
    pace = race_pace_table(laps)
    team_pace = pace[pace["team"] == team].groupby("round")["pace_delta_pct"].mean()
    qteam = quali[quali["team"] == team]
    quali_avg = qteam.groupby("round")["finish"].mean()
    starts = len(mine)
    dnfs = int(mine["status"].map(is_dnf).sum())
    pit_team = pit[pit["team"] == team]["duration_s"].dropna()
    cum = by_round.cumsum()

    return {
        "team": team,
        "season_summary": {
            "points": _num(mine["total"].sum()), "races": int(by_round.size),
            "wins": int((mine["finish"] == 1).sum()), "podiums": int((mine["finish"] <= 3).sum()),
            "points_per_race": _num(mine["total"].sum() / by_round.size),
            "classified_starts": starts, "dnfs": dnfs, "retirement_rate": dnfs / starts if starts else None,
        },
        "by_round": [{"round": int(r), "points": float(by_round[r]), "cumulative_points": float(cum[r]),
                      "pace_delta_pct": _num(team_pace.get(r)), "avg_quali_position": _num(quali_avg.get(r))}
                     for r in by_round.index],
        "driver_contribution": [
            {"driver": d, "points": float(g["total"].sum()), "share": float(g["total"].sum() / mine["total"].sum())
             if mine["total"].sum() else None, "races": int(g["round"].nunique())}
            for d, g in mine.groupby("driver")],
        "pace": {"median_delta_pct_vs_field": _num(team_pace.median()) if len(team_pace) else None,
                 "rated_races": int(len(team_pace))},
        "qualifying": {"avg_position": _num(qteam["finish"].mean()) if qteam["finish"].notna().any() else None},
        "pit_stops": {
            "stops_measured": int(len(pit_team)),
            "median_pit_lane_time_s": _num(pit_team.median()) if len(pit_team) else None,
            "note": "Pit-lane time (in-lap pit entry to out-lap pit exit), not stationary time; includes red-flag stops.",
        },
        "notes": ["Constructor pace is the mean of its rated drivers' % delta to the field median (negative = faster)."],
    }


def circuit_history(code: str, entries: pd.DataFrame, quali: pd.DataFrame) -> list[dict]:
    """Per circuit across all ingested seasons for one driver."""
    race = entries[entries["driver"] == code]
    q = quali[quali["driver"] == code]
    out = []
    for circuit, g in race.groupby("circuit"):
        qq = q[q["circuit"] == circuit]
        out.append({
            "circuit": circuit, "starts": int(len(g)), "seasons": sorted(int(y) for y in g["year"].unique()),
            "avg_finish": _num(g["finish"].mean()), "best_finish": None if g["finish"].isna().all() else int(g["finish"].min()),
            "avg_grid": _num(g["grid"].mean()), "avg_quali_position": _num(qq["finish"].mean()) if len(qq) else None,
            "dnfs": int(g["status"].map(is_dnf).sum()),
        })
    return sorted(out, key=lambda r: (r["avg_finish"] is None, r["avg_finish"]))
