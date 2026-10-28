"""Usage: python -m scripts.run_race_backtest 2023 2024 2025 2026 -> docs/evaluation-race-model.md

Forward-chaining evaluation of race models on the FULL finishing order. For each target season the model settings
(alpha, beta, gamma) are chosen using only earlier seasons, then applied unchanged. The improved model is adopted
only if it clears the pre-registered rule below against the points-form baseline."""
import itertools
import sys
import warnings
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from app.core.database import SessionLocal  # noqa: E402
from app.ml import features, race_backtest as rb  # noqa: E402
from app.ml.race_model import ModelConfig  # noqa: E402
from scripts.run_backtest import md  # noqa: E402

ALPHAS, BETAS, GAMMAS = (0.0, 1.5, 2.5), (0.0, 0.5, 1.0, 1.5, 2.0, 3.0), (0.0, 0.05, 0.10)
BASELINE_LABEL = "a2.5_b0.0_g0.0"
TUNED, TUNED_DNF, BASE = "improved model", "improved model + shrunk DNF", "baseline (points form)"
METRICS = ["ll_win", "ll_podium", "ll_top10", "ll_dnf", "spearman", "mae"]

# Pre-registered adoption rule (written before looking at results):
RULE = ("Adopt only if, pooled over the target seasons, the 95% interval of the improved-minus-baseline difference is "
        "entirely below 0 for BOTH podium and top-10 log loss, the win log-loss difference has an upper bound below "
        "+0.01 (not materially worse), and the Spearman rank-correlation difference has a lower bound above -0.01.")


def label(a, b, g):
    return f"a{a}_b{b}_g{g}"


if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]]
    targets = years[1:]
    with SessionLocal() as db:
        hist = features.all_histories(db, years)
    print({y: (len(h), int(h["pace_pct"].notna().sum())) for y, h in hist.items()}, flush=True)

    grid = [ModelConfig(label(a, b, g), alpha=a, beta=b, gamma=g)
            for a, b, g in itertools.product(ALPHAS, BETAS, GAMMAS) if (a, b, g) != (0.0, 0.0, 0.0)]
    pred = rb.collect(hist, grid)
    scores = rb.race_scores(pred)

    chosen = {}
    for t in targets:
        sources = [y for y in years if y < t]
        losses = {c.name: rb.pooled_probability_loss(scores, c.name, sources) for c in grid}
        chosen[t] = min(losses, key=losses.get)
    cfg_by_name = {c.name: c for c in grid}

    # DNF variant of each season's chosen config
    dnf_pred = pd.concat([rb.collect(hist, [replace(cfg_by_name[chosen[t]], name=TUNED_DNF, dnf_mode="shrunk")],
                                     years=[t], rankers=()) for t in targets], ignore_index=True)
    dnf_scores = rb.race_scores(dnf_pred[dnf_pred["config"] == TUNED_DNF])

    tgt = scores[scores["year"].isin(targets)]
    tuned = pd.concat([scores[(scores["config"] == chosen[t]) & (scores["year"] == t)] for t in targets]).assign(config=TUNED)
    frame = pd.concat([
        tuned, dnf_scores,
        tgt[tgt["config"] == BASELINE_LABEL].assign(config=BASE),
        tgt[tgt["config"].isin(["uniform", *rb.BASELINE_RANKERS])],
    ], ignore_index=True)

    summary = frame.groupby("config")[METRICS].mean().round(4)
    by_year = frame[frame["config"].isin([BASE, TUNED])].groupby(["year", "config"])[METRICS].mean().round(4).reset_index()

    def diff(metric, a=TUNED, b=BASE, ys=None):
        d = rb.paired_difference(frame, a, b, metric, years=ys)
        return {"metric": metric, "mean": d["mean"], "ci_low": d["low"], "ci_high": d["high"], "races": d["n_races"]}

    paired = pd.DataFrame([diff(m) for m in ["ll_win", "ll_podium", "ll_top10", "spearman", "mae"]])
    paired_year = pd.DataFrame([{"year": y, **diff(m, ys=[y])} for y in targets for m in ["ll_podium", "ll_top10", "spearman"]])
    dnf_paired = pd.DataFrame([diff("ll_dnf", TUNED_DNF, TUNED), diff("spearman", TUNED_DNF, TUNED),
                               diff("ll_top10", TUNED_DNF, TUNED)])

    p = paired.set_index("metric")
    adopt = bool(p.loc["ll_podium", "ci_high"] < 0 and p.loc["ll_top10", "ci_high"] < 0
                 and p.loc["ll_win", "ci_high"] < 0.01 and p.loc["spearman", "ci_low"] > -0.01)
    adopt_dnf = bool(dnf_paired.set_index("metric").loc["ll_dnf", "ci_high"] < 0)

    out = ["# Race model evaluation (full finishing order)", "",
           f"Seasons {years[0]}-{years[-1]}; target seasons {targets}. Each race is predicted from earlier races only "
           "(first 4 rounds of a season are warm-up). Settings (alpha, beta, gamma) are chosen per target season on "
           "earlier seasons only. 2026 is a regulation change and is still in progress.", "",
           "## Pre-registered adoption rule", "", RULE, "",
           "## Settings chosen on earlier seasons", "", md(pd.DataFrame({"target": list(chosen), "config": list(chosen.values())})), "",
           "Config name: `a` = exponent on points-form strength, `b` = weight on race-pace rating, `g` = weight on "
           "qualifying-position rating (b = g = 0 is the baseline).", "",
           "## Average scores over the target races (lower is better except Spearman)", "", md(summary.reset_index()), "",
           "## By season", "", md(by_year), "",
           "## Improved minus baseline, paired over the same races (95% bootstrap interval over races)", "", md(paired), "",
           md(paired_year), "",
           f"**Decision: {'ADOPT' if adopt else 'DO NOT ADOPT'} the improved strength model.**", "",
           *([ "Reading the result: the improved model orders the finishing positions significantly better "
               "(rank correlation and position error intervals exclude 0) but its probability log-loss gains do not clear "
               "zero, so it fails the rule above. Adopting it anyway for the ordered classification would be a decision "
               "made after seeing the results, not a result of the rule.", ""]
              if (not adopt and p.loc["spearman", "ci_low"] > 0 and p.loc["mae", "ci_high"] < 0) else []),
           "## Shrunk (per driver and team) retirement rates vs fixed 5%", "", md(dnf_paired), "",
           f"**Decision: {'ADOPT' if adopt_dnf else 'DO NOT ADOPT'} shrunk retirement rates.**", "",
           "## Limitations", "",
           "- Three target seasons (about 54 races); intervals are over races, which are not independent of each other.",
           "- Pace needs enough clean laps in a race (15), so a few races have no pace rating for some drivers.",
           "- Weather, safety cars and strategy are not modelled; 2026 only has its first 18 rounds."]
    path = Path("..") / "docs" / "evaluation-race-model.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("chosen:", chosen)
    print(summary.to_string())
    print(paired.round(4).to_string(index=False))
    print(paired_year.round(4).to_string(index=False))
    print(dnf_paired.round(4).to_string(index=False))
    print("ADOPT strengths:", adopt, "| ADOPT shrunk DNF:", adopt_dnf)
    print("written", path.resolve())
