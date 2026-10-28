"""Usage: python -m scripts.run_circuit_backtest 2023 2024 2025 2026 -> docs/evaluation-circuit-effect.md

Does knowing which circuit a race is at improve the PRE-qualifying forecast? The candidate adds, for each team, how much
faster/slower it was at this circuit than its own season average in earlier seasons (shrunk), scaled by epsilon.
Forward-chaining: epsilon is chosen per target season using only earlier seasons (ties go to epsilon = 0, which is
the current production model); circuit effects themselves only use earlier seasons.

RULE (written before running): adopt only if, pooled over the target races, the 95% interval of
(circuit model - current pre-qualifying model) is entirely below 0 for BOTH podium and top-10 log loss, the win
log-loss difference has an upper bound below +0.01, and the Spearman difference has a lower bound above -0.01."""
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

EPSILONS = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)
BASE, CIRC = "current pre-qualifying model", "circuit model"
METRICS = ["ll_win", "ll_podium", "ll_top10", "ll_dnf", "spearman", "mae"]


def label(e):
    return f"eps{e}"


if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]]
    targets = years[1:]
    with SessionLocal() as db:
        hist = features.all_histories(db, years)
    cfgs = [ModelConfig(label(e), alpha=2.5, epsilon=e, dnf_mode="shrunk") for e in EPSILONS]
    pred = rb.collect(hist, cfgs, rankers=())
    scores = rb.race_scores(pred)

    chosen = {}
    for t in targets:
        sources = [y for y in years if y < t]
        pool = {c.name: round(rb.pooled_probability_loss(scores, c.name, sources), 6) for c in cfgs}
        chosen[t] = min(pool, key=lambda k: (pool[k], float(k[3:])))          # ties -> smallest epsilon (0 = current model)
    tgt = scores[scores["year"].isin(targets)]
    circ = pd.concat([scores[(scores["config"] == chosen[t]) & (scores["year"] == t)] for t in targets]).assign(config=CIRC)
    base = tgt[tgt["config"] == label(0.0)].assign(config=BASE)
    frame = pd.concat([circ, base], ignore_index=True)

    def diff(metric, a, b, ys=None, fr=None):
        d = rb.paired_difference(fr if fr is not None else frame, a, b, metric, years=ys)
        return {"metric": metric, "mean": d["mean"], "ci_low": d["low"], "ci_high": d["high"], "races": d["n_races"]}

    paired = pd.DataFrame([diff(m, CIRC, BASE) for m in ["ll_win", "ll_podium", "ll_top10", "spearman", "mae"]])
    by_year = pd.DataFrame([{"year": y, **diff(m, CIRC, BASE, [y])} for y in targets for m in ["ll_podium", "ll_top10", "spearman"]])
    # Dose-response (NOT used for selection): fixed epsilon on every target race vs epsilon 0
    dose = []
    for e in EPSILONS[1:]:
        fr = pd.concat([tgt[tgt["config"] == label(e)], tgt[tgt["config"] == label(0.0)]])
        dose.append({"epsilon": e, **{m: diff(m, label(e), label(0.0), fr=fr)["mean"] for m in ["ll_podium", "ll_top10", "spearman"]}})
    dose = pd.DataFrame(dose)
    summary = frame.groupby("config")[METRICS].mean().round(4)

    p = paired.set_index("metric")
    adopt = bool(p.loc["ll_podium", "ci_high"] < 0 and p.loc["ll_top10", "ci_high"] < 0
                 and p.loc["ll_win", "ci_high"] < 0.01 and p.loc["spearman", "ci_low"] > -0.01)

    # How different do the circuit effects make the upcoming-style forecasts? (spread of team deltas on real circuits)
    spread = []
    for c in sorted({c for h in hist.values() for c in h["circuit"].dropna().unique()}):
        d = features.team_circuit_deltas([hist[y] for y in years[:-1]], c)
        if d:
            spread.append({"circuit": c, "teams": len(d), "largest_abs_effect_pct": round(max(abs(v) for v in d.values()), 3)})
    spread = pd.DataFrame(spread).sort_values("largest_abs_effect_pct", ascending=False).head(8)

    out = ["# Circuit effect on pre-qualifying forecasts", "",
           f"Seasons {years[0]}-{years[-1]}; target seasons {targets}. Each race predicted from earlier data only; circuit effects use earlier "
           "seasons only; epsilon is chosen on earlier seasons only (ties go to 0, the current model).", "",
           "## Pre-registered rule", "", __doc__.split("RULE (written before running):", 1)[1].strip().replace("\n", " "), "",
           "## Epsilon chosen per target season", "", md(pd.DataFrame({"target": list(chosen), "config": list(chosen.values())})), "",
           "2024 can only be tuned on 2023, which has no earlier season to derive circuit effects from, so every epsilon ties and 0 is chosen.", "",
           "## Average scores over the target races", "", md(summary.reset_index()), "",
           "## Circuit model minus current model (paired; 95% interval over races)", "", md(paired), "", md(by_year), "",
           f"**Decision: {'ADOPT' if adopt else 'DO NOT ADOPT'} the circuit effect.**", "",
           "## Dose-response (fixed epsilon on every target race; for information, not used to select)", "", md(dose), "",
           "## Largest team-circuit effects estimated from all earlier seasons (% of race pace)", "", md(spread), "",
           "## Limitations", "",
           "- At most three past visits per circuit, and cars change every season (2026 most of all), so any real effect is hard to see.",
           "- Team lineage is followed across renames (RB / AlphaTauri to Racing Bulls, Kick Sauber / Alfa Romeo to Audi).",
           "- Only 2025 and 2026 genuinely test this (2024 has no earlier season to tune on)."]
    path = Path("..") / "docs" / "evaluation-circuit-effect.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("chosen:", chosen)
    print(summary.to_string())
    print(paired.round(4).to_string(index=False)); print(by_year.round(4).to_string(index=False)); print(dose.round(4).to_string(index=False))
    print(spread.to_string(index=False))
    print("ADOPT circuit effect:", adopt, "\nwritten", path.resolve())
