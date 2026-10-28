# Circuit effect on pre-qualifying forecasts

Seasons 2023-2026; target seasons [2024, 2025, 2026]. Each race predicted from earlier data only; circuit effects use earlier seasons only; epsilon is chosen on earlier seasons only (ties go to 0, the current model).

## Pre-registered rule

adopt only if, pooled over the target races, the 95% interval of (circuit model - current pre-qualifying model) is entirely below 0 for BOTH podium and top-10 log loss, the win log-loss difference has an upper bound below +0.01, and the Spearman difference has a lower bound above -0.01.

## Epsilon chosen per target season

| target | config |
|---|---|
| 2024 | eps0.0 |
| 2025 | eps0.0 |
| 2026 | eps0.0 |

2024 can only be tuned on 2023, which has no earlier season to derive circuit effects from, so every epsilon ties and 0 is chosen.

## Average scores over the target races

| config | ll_win | ll_podium | ll_top10 | ll_dnf | spearman | mae |
|---|---|---|---|---|---|---|
| circuit model | 0.135 | 0.268 | 0.518 | 0.393 | 0.604 | 3.584 |
| current pre-qualifying model | 0.135 | 0.268 | 0.518 | 0.393 | 0.604 | 3.584 |

## Circuit model minus current model (paired; 95% interval over races)

| metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|
| ll_win | 0.000 | 0.000 | 0.000 | 54 |
| ll_podium | 0.000 | 0.000 | 0.000 | 54 |
| ll_top10 | 0.000 | 0.000 | 0.000 | 54 |
| spearman | 0.000 | 0.000 | 0.000 | 54 |
| mae | 0.000 | 0.000 | 0.000 | 54 |

| year | metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|---|
| 2024 | ll_podium | 0.000 | 0.000 | 0.000 | 20 |
| 2024 | ll_top10 | 0.000 | 0.000 | 0.000 | 20 |
| 2024 | spearman | 0.000 | 0.000 | 0.000 | 20 |
| 2025 | ll_podium | 0.000 | 0.000 | 0.000 | 20 |
| 2025 | ll_top10 | 0.000 | 0.000 | 0.000 | 20 |
| 2025 | spearman | 0.000 | 0.000 | 0.000 | 20 |
| 2026 | ll_podium | 0.000 | 0.000 | 0.000 | 14 |
| 2026 | ll_top10 | 0.000 | 0.000 | 0.000 | 14 |
| 2026 | spearman | 0.000 | 0.000 | 0.000 | 14 |

**Decision: DO NOT ADOPT the circuit effect.**

## Dose-response (fixed epsilon on every target race; for information, not used to select)

| epsilon | ll_podium | ll_top10 | spearman |
|---|---|---|---|
| 0.500 | 0.001 | -0.000 | 0.001 |
| 1.000 | 0.003 | 0.000 | -0.002 |
| 1.500 | 0.005 | 0.001 | -0.004 |
| 2.000 | 0.008 | 0.003 | -0.005 |
| 3.000 | 0.014 | 0.009 | -0.011 |

## Largest team-circuit effects estimated from all earlier seasons (% of race pace)

| circuit | teams | largest_abs_effect_pct |
|---|---|---|
| Jeddah | 10 | 0.589 |
| São Paulo | 10 | 0.539 |
| Monaco | 10 | 0.535 |
| Lusail | 10 | 0.467 |
| Silverstone | 10 | 0.457 |
| Budapest | 10 | 0.374 |
| Montréal | 10 | 0.369 |
| Baku | 10 | 0.331 |

## Limitations

- At most three past visits per circuit, and cars change every season (2026 most of all), so any real effect is hard to see.
- Team lineage is followed across renames (RB / AlphaTauri to Racing Bulls, Kick Sauber / Alfa Romeo to Audi).
- Only 2025 and 2026 genuinely test this (2024 has no earlier season to tune on).