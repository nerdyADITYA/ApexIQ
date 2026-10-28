"""Usage: python -m scripts.run_grid_backtest 2023 2024 2025 2026 -> docs/evaluation-grid-model.md

Does knowing the qualifying order improve race forecasts, and does scaling it by circuit help? Forward-chaining:
settings are chosen per target season on earlier seasons only. Qualifying positions of the race being predicted are
used (known before the race); its results are not. Two rules, written before running:

  RULE 1 (grid model replaces the pre-qualifying model once qualifying exists): pooled over target races, the 95%
         interval of (grid model - pre-qualifying model) is entirely below 0 for win, podium AND top-10 log loss,
         and the Spearman difference has a lower bound above 0.
  RULE 2 (circuit-specific grid weight): kept only if (circuit-scaled - plain grid) is entirely below 0 for BOTH
         podium and top-10 log loss; otherwise the same grid weight is used everywhere."""
import itertools
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from app.core.database import SessionLocal  # noqa: E402
from app.ml import features, race_backtest as rb  # noqa: E402
from app.ml.race_model import ModelConfig  # noqa: E402
from scripts.run_backtest import md  # noqa: E402

ALPHAS, DELTAS, KAPPAS = (0.0, 1.5, 2.5), (0.5, 1.0, 1.5, 2.0, 3.0), (0.0, 1.0)
PRE, GRID, GRID_C = "pre-qualifying model", "grid model", "grid model + circuit scaling"
METRICS = ["ll_win", "ll_podium", "ll_top10", "ll_dnf", "spearman", "mae"]


def label(a, d, k):
    return f"a{a}_d{d}_k{k}"


if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]]
    targets = years[1:]
    with SessionLocal() as db:
        hist = features.all_histories(db, years)
    cover = {y: f"{int(h.groupby('round')['quali_pos'].apply(lambda s: s.notna().mean() >= 0.8).sum())}/{h['round'].nunique()} races with qualifying"
             for y, h in hist.items()}
    print(cover, flush=True)

    pre_cfg = ModelConfig(PRE, alpha=2.5, dnf_mode="shrunk")
    grid_cfgs = [ModelConfig(label(a, d, k), alpha=a, delta=d, kappa=k, dnf_mode="shrunk")
                 for a, d, k in itertools.product(ALPHAS, DELTAS, KAPPAS)]
    pred = rb.collect(hist, [pre_cfg, *grid_cfgs], rankers=(rb.GRID_RANKER, *rb.BASELINE_RANKERS), need_grid=True)
    scores = rb.race_scores(pred)

    def pick(t, kappa):
        sources = [y for y in years if y < t]
        pool = {c.name: rb.pooled_probability_loss(scores, c.name, sources) for c in grid_cfgs if c.kappa == kappa}
        return min(pool, key=pool.get)

    chosen = {t: {"plain": pick(t, 0.0), "circuit": pick(t, 1.0)} for t in targets}
    tgt = scores[scores["year"].isin(targets)]
    plain = pd.concat([scores[(scores["config"] == chosen[t]["plain"]) & (scores["year"] == t)] for t in targets]).assign(config=GRID)
    circ = pd.concat([scores[(scores["config"] == chosen[t]["circuit"]) & (scores["year"] == t)] for t in targets]).assign(config=GRID_C)
    frame = pd.concat([plain, circ, tgt[tgt["config"] == PRE],
                       tgt[tgt["config"].isin(["uniform", rb.GRID_RANKER, *rb.BASELINE_RANKERS])]], ignore_index=True)

    summary = frame.groupby("config")[METRICS].mean().round(4)
    by_year = frame[frame["config"].isin([PRE, GRID])].groupby(["year", "config"])[METRICS].mean().round(4).reset_index()

    def diff(metric, a, b, ys=None):
        d = rb.paired_difference(frame, a, b, metric, years=ys)
        return {"metric": metric, "mean": d["mean"], "ci_low": d["low"], "ci_high": d["high"], "races": d["n_races"]}

    rule1 = pd.DataFrame([diff(m, GRID, PRE) for m in ["ll_win", "ll_podium", "ll_top10", "spearman", "mae"]])
    rule1_year = pd.DataFrame([{"year": y, **diff(m, GRID, PRE, [y])} for y in targets for m in ["ll_podium", "ll_top10", "spearman"]])
    rule2 = pd.DataFrame([diff(m, GRID_C, GRID) for m in ["ll_win", "ll_podium", "ll_top10", "spearman"]])
    vs_grid = pd.DataFrame([diff(m, GRID, rb.GRID_RANKER) for m in ["spearman", "mae"]])

    r1, r2 = rule1.set_index("metric"), rule2.set_index("metric")
    adopt1 = bool(r1.loc[["ll_win", "ll_podium", "ll_top10"], "ci_high"].lt(0).all() and r1.loc["spearman", "ci_low"] > 0)
    adopt2 = bool(r2.loc[["ll_podium", "ll_top10"], "ci_high"].lt(0).all())
    # Production setting: best plain-grid config over ALL seasons (what the live forecast uses; in-sample by construction)
    prod_pool = {c.name: rb.pooled_probability_loss(scores, c.name) for c in grid_cfgs if c.kappa == 0.0}
    prod = min(prod_pool, key=prod_pool.get)
    top5 = pd.Series(prod_pool).sort_values().head(5).round(4).rename("pooled log loss").reset_index().rename(columns={"index": "config"})
    out = ["# Grid (post-qualifying) model evaluation", "",
           f"Seasons {years[0]}-{years[-1]}; target seasons {targets}. {cover}", "",
           "## Pre-registered rules", "", "- " + __doc__.split("RULE 1", 1)[1].split("RULE 2")[0].strip().replace("\n         ", " "),
           "- RULE 2" + __doc__.split("RULE 2", 1)[1].strip().replace("\n         ", " "), "",
           "## Settings chosen on earlier seasons", "",
           md(pd.DataFrame([{"target": t, "plain grid": chosen[t]["plain"], "circuit-scaled": chosen[t]["circuit"]} for t in targets])), "",
           "Config name: `a` = exponent on points-form strength, `d` = grid weight (strength is multiplied by position^-d), "
           "`k` = exponent of the circuit factor (0 = same everywhere).", "",
           "## Average scores over the target races (lower is better except Spearman)", "", md(summary.reset_index()), "",
           "## By season", "", md(by_year), "",
           "## Rule 1: grid model minus pre-qualifying model (paired; 95% interval over races)", "", md(rule1), "", md(rule1_year), "",
           f"**Rule 1: {'PASS: use the grid model once qualifying is available' if adopt1 else 'FAIL: keep the pre-qualifying model'}.**", "",
           "## Rule 2: circuit-scaled minus plain grid model", "", md(rule2), "",
           f"**Rule 2: {'PASS: scale the grid weight by circuit' if adopt2 else 'FAIL: use one grid weight for every circuit'}.**", "",
           "## Grid model vs simply finishing where you qualified", "", md(vs_grid), "",
           "## Setting used in the live forecast", "",
           f"Chosen on all seasons (so in-sample): **{prod}**. Best five by pooled win/podium/top-10 log loss:", "", md(top5), "",
           "The ordering of a grid-model forecast is about the same as qualifying order (see the comparison above); "
           "its benefit is better-calibrated probabilities.", "",
           "## Limitations", "",
           "- The qualifying position is used as the grid. Grid penalties and pit-lane starts are not known at forecast time, so "
           "they are not reflected (in the backtest or in live forecasts).",
           "- Circuit factors come from at most three past visits per circuit, so they are noisy; the factor is shrunk toward 1.",
           "- 2026 is a regulation change and only has its first 18 rounds."]
    path = Path("..") / "docs" / "evaluation-grid-model.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("chosen:", chosen)
    print(summary.to_string())
    print(rule1.round(4).to_string(index=False)); print(rule1_year.round(4).to_string(index=False))
    print(rule2.round(4).to_string(index=False)); print(vs_grid.round(4).to_string(index=False))
    print("PRODUCTION:", prod, top5.to_string(index=False))
    print("RULE1 pass:", adopt1, "| RULE2 pass:", adopt2)
    print("written", path.resolve())
