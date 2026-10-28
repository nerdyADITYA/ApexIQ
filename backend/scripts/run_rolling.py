"""Usage: python -m scripts.run_rolling 2023 2024 2025 2026 -> docs/evaluation-rolling.md

Forward-chaining evaluation: for each target season, the sharpening exponent alpha is chosen
using ONLY earlier seasons, then applied unchanged to the target. No target-season outcome ever
influences the alpha used to predict it. The last year may be a season in progress."""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import func, select

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from app.core.database import SessionLocal  # noqa: E402
from app.ml import evaluation as ev  # noqa: E402
from app.models import database_models as m  # noqa: E402
from app.services.frames import season_results_frame  # noqa: E402
from scripts.run_backtest import md  # noqa: E402

DECAYS = (1.0, 0.8)
PRODUCTION_ALPHA = 2.5
CHECKPOINTS = (5, 8, 12, 16, 20)


def pooled(frames_by_year, years):
    """alpha -> prediction frame pooled over several seasons (rows are independent driver-race cases)."""
    alphas = frames_by_year[years[0]].keys()
    return {a: pd.concat([frames_by_year[y][a] for y in years], ignore_index=True) for a in alphas}


if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]]
    with SessionLocal() as db:
        res = {y: season_results_frame(db, y) for y in years}
        calendar = {y: db.scalar(select(func.count()).select_from(m.Event).join(m.Season).where(m.Season.year == y))
                    for y in years}
    final_round = {y: int(res[y]["round"].max()) for y in years}
    in_progress = {y: final_round[y] < calendar[y] for y in years}
    champion = {y: (res[y]["race_points"] + res[y]["sprint_points"]).groupby(res[y]["driver"]).sum().idxmax() for y in years}

    out = ["# Rolling (forward-chaining) evaluation", "",
           f"Seasons: {', '.join(str(y) + (' (in progress, ' + str(final_round[y]) + ' of ' + str(calendar[y]) + ' rounds)' if in_progress[y] else '') for y in years)}.", "",
           "For each target season, alpha is chosen on pooled earlier seasons only, then applied unchanged. "
           "`gain_vs_uniform` is the mean per-race log-loss improvement, with a 95% bootstrap interval over target-season races.", ""]
    headline = []
    for decay in DECAYS:
        frames = {y: ev.predictions_by_alpha(res[y], decay=decay) for y in years}
        out += [f"## Race outcomes, decay {decay}", ""]
        for i, tgt in enumerate(years[1:], 1):
            src = years[:i]
            alpha = ev.best_alpha(pooled(frames, src))
            in_sample = ev.best_alpha(frames[tgt])
            base = ev.backtest_races(res[tgt])
            parts = [base[base.model == "uniform"],
                     frames[tgt][1.0].assign(model="alpha=1.0 (unsharpened)"),
                     frames[tgt][PRODUCTION_ALPHA].assign(model=f"alpha={PRODUCTION_ALPHA} (current production)"),
                     frames[tgt][alpha].assign(model=f"alpha={alpha} (chosen on {'+'.join(map(str, src))})")]
            s = ev.summarise(pd.concat(parts, ignore_index=True))
            tag = " (regulation change)" if tgt == 2026 else ""
            out += [f"### Target {tgt}{tag}: alpha chosen on {', '.join(map(str, src))} = **{alpha}** "
                    f"(in-sample best on {tgt}: {in_sample})", "", md(s), ""]
            chosen_row = s[s.model.str.contains("chosen")]
            for _, r in chosen_row.iterrows():
                headline.append((decay, tgt, alpha, r["target"], r["gain_vs_uniform"], r["gain_ci_low"], r["gain_ci_high"]))
            if decay == DECAYS[0]:
                g = frames[tgt][alpha]
                for t in ("podium", "top10"):
                    gg = g[g.target == t]
                    out += [f"Calibration ({tgt}, alpha={alpha}, {t}):", "", md(ev.calibration_table(gg["y"], gg["p"])), ""]

    out += ["## Championship forecast vs actual champion", "",
            "Probability assigned to the eventual champion after selected rounds, using alpha chosen on earlier seasons "
            "(2023 has no earlier season, so alpha = 1). Three outcomes: illustrative, not statistical evidence. "
            "Sprints still to come are ignored.", ""]
    champ_rows = []
    for i, y in enumerate(years):
        alpha = 1.0 if i == 0 else ev.best_alpha(pooled({k: ev.predictions_by_alpha(res[k], decay=1.0) for k in years[:i]}, years[:i]))
        tab = ev.backtest_championship(res[y], None if in_progress[y] else champion[y], calendar[y], decay=1.0,
                                       year=y, sharpen=alpha)
        if in_progress[y]:
            last = tab.iloc[-1]
            out += [f"### {y} (in progress): alpha {alpha}", "",
                    f"After round {int(last.after_round)} of {calendar[y]}: leader **{last.leader}**, "
                    f"modelled title probability {last.leader_p:.3f}. No champion yet, so no score.", ""]
            continue
        sel = tab[tab.after_round.isin(CHECKPOINTS)][["after_round", "leader", "leader_p", "p_actual_champion"]]
        score = float(-np.mean(np.log(np.clip(tab.p_actual_champion, 1e-3, 1))))
        out += [f"### {y}: champion {champion[y]}, alpha {alpha}", "", md(sel), "",
                f"Mean log score of the true champion over all rounds: {score:.3f} "
                "(lower is better; a uniform guess over 20 drivers would score about 3.0).", ""]
        champ_rows.append((y, champion[y], alpha, score))

    out += ["## Limitations", "",
            "- Three target seasons, all under at most two regulation sets; the 2026 check is the only regulation-change test.",
            "- 2026 is incomplete, so its result covers 14 predicted rounds and carries wide uncertainty.",
            "- Fixed 5% DNF rate; no qualifying, circuit or reliability features; sprints remaining ignored in the championship simulation.",
            "- Points-per-race strength is a blunt car-plus-driver proxy; it cannot see mid-season upgrades or driver changes beyond form."]
    path = Path("..") / "docs" / "evaluation-rolling.md"
    path.write_text("\n".join(out), encoding="utf-8")

    print("decay | target | alpha | metric | gain (95% CI)")
    for d, t, a, k, g, lo, hi in headline:
        print(f"{d} | {t} | {a} | {k} | {g:.3f} ({lo:.3f}, {hi:.3f})")
    for y, c, a, sc in champ_rows:
        print(f"champion {y}: {c} alpha {a} mean log score {sc:.3f}")
    print("written", path.resolve())
