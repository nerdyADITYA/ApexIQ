"""Usage: python scripts/run_cross_season.py 2023 2024 -> docs/evaluation-cross-season.md

Select the sharpening exponent on one season, score it on the other (both directions).
The target season's outcomes are never used to choose alpha for that season."""
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from app.core.database import SessionLocal  # noqa: E402
from app.ml import evaluation as ev  # noqa: E402
from app.services.frames import season_results_frame  # noqa: E402
from scripts.run_backtest import md  # noqa: E402

DECAYS = (1.0, 0.8)

if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:3]]
    with SessionLocal() as db:
        res = {y: season_results_frame(db, y) for y in years}
    out = ["# Cross-season evaluation", "",
           "Alpha (sharpening exponent) is chosen by pooled log loss on the SOURCE season only, then applied "
           "unchanged to the TARGET season. `gain_vs_uniform` is the mean per-race log-loss improvement with a 95% "
           "bootstrap interval over target-season races.", ""]
    for decay in DECAYS:
        frames = {y: ev.predictions_by_alpha(res[y], decay=decay) for y in years}
        for src, tgt in ((years[0], years[1]), (years[1], years[0])):
            alpha = ev.best_alpha(frames[src])
            base = ev.backtest_races(res[tgt])
            parts = [base[base.model == "uniform"],
                     frames[tgt][alpha].assign(model=f"alpha={alpha} (chosen on {src})"),
                     frames[tgt][1.0].assign(model="alpha=1.0 (unsharpened)")]
            s = ev.summarise(pd.concat(parts, ignore_index=True))
            target_best = ev.best_alpha(frames[tgt])
            out += [f"## decay {decay}: choose on {src}, test on {tgt}", "",
                    f"Chosen alpha = **{alpha}**. (For reference, the alpha that would have been best in-sample "
                    f"on {tgt} is {target_best}.)", "", md(s), ""]
            cal = frames[tgt][alpha]
            for t in ("podium", "top10"):
                g = cal[cal.target == t]
                out += [f"Calibration, {t}:", "", md(ev.calibration_table(g["y"], g["p"])), ""]
            print(f"decay {decay} {src}->{tgt} alpha {alpha} (in-sample best on target {target_best})")
            print(s[["target", "model", "log_loss", "gain_vs_uniform", "gain_ci_low", "gain_ci_high"]].round(3).to_string(index=False))
    out += ["## Limitations", "", "- Two seasons, same regulation era (2022 ground-effect rules); no cross-era check.",
            "- Same alpha grid as before; the edge of the grid is 3.0."]
    path = Path("..") / "docs" / "evaluation-cross-season.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("written", path.resolve())
