# Grid (post-qualifying) model evaluation

Seasons 2023-2026; target seasons [2024, 2025, 2026]. {2023: '22/22 races with qualifying', 2024: '24/24 races with qualifying', 2025: '24/24 races with qualifying', 2026: '18/18 races with qualifying'}

## Pre-registered rules

- (grid model replaces the pre-qualifying model once qualifying exists): pooled over target races, the 95% interval of (grid model - pre-qualifying model) is entirely below 0 for win, podium AND top-10 log loss, and the Spearman difference has a lower bound above 0.
- RULE 2(circuit-specific grid weight): kept only if (circuit-scaled - plain grid) is entirely below 0 for BOTH podium and top-10 log loss; otherwise the same grid weight is used everywhere.

## Settings chosen on earlier seasons

| target | plain grid | circuit-scaled |
|---|---|---|
| 2024 | a2.5_d1.5_k0.0 | a2.5_d1.5_k1.0 |
| 2025 | a1.5_d2.0_k0.0 | a1.5_d2.0_k1.0 |
| 2026 | a1.5_d2.0_k0.0 | a1.5_d2.0_k1.0 |

Config name: `a` = exponent on points-form strength, `d` = grid weight (strength is multiplied by position^-d), `k` = exponent of the circuit factor (0 = same everywhere).

## Average scores over the target races (lower is better except Spearman)

| config | ll_win | ll_podium | ll_top10 | ll_dnf | spearman | mae |
|---|---|---|---|---|---|---|
| championship order | nan | nan | nan | nan | 0.614 | 3.782 |
| grid model | 0.102 | 0.217 | 0.456 | 0.393 | 0.700 | 3.124 |
| grid model + circuit scaling | 0.103 | 0.218 | 0.455 | 0.393 | 0.701 | 3.123 |
| grid order | nan | nan | nan | nan | 0.698 | 3.124 |
| last race result | nan | nan | nan | nan | 0.478 | 4.375 |
| pre-qualifying model | 0.135 | 0.268 | 0.518 | 0.393 | 0.604 | 3.584 |
| uniform | 0.196 | 0.418 | 0.692 | 0.396 | 0.000 | 5.093 |

## By season

| year | config | ll_win | ll_podium | ll_top10 | ll_dnf | spearman | mae |
|---|---|---|---|---|---|---|---|
| 2024 | grid model | 0.133 | 0.245 | 0.413 | 0.343 | 0.727 | 2.901 |
| 2024 | pre-qualifying model | 0.150 | 0.292 | 0.479 | 0.343 | 0.646 | 3.349 |
| 2025 | grid model | 0.090 | 0.202 | 0.490 | 0.364 | 0.666 | 3.143 |
| 2025 | pre-qualifying model | 0.127 | 0.253 | 0.566 | 0.364 | 0.527 | 3.679 |
| 2026 | grid model | 0.076 | 0.200 | 0.468 | 0.505 | 0.712 | 3.415 |
| 2026 | pre-qualifying model | 0.126 | 0.255 | 0.504 | 0.505 | 0.655 | 3.785 |

## Rule 1: grid model minus pre-qualifying model (paired; 95% interval over races)

| metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|
| ll_win | -0.033 | -0.053 | -0.013 | 54 |
| ll_podium | -0.051 | -0.074 | -0.026 | 54 |
| ll_top10 | -0.062 | -0.081 | -0.044 | 54 |
| spearman | 0.096 | 0.072 | 0.122 | 54 |
| mae | -0.460 | -0.540 | -0.387 | 54 |

| year | metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|---|
| 2024 | ll_podium | -0.047 | -0.082 | -0.007 | 20 |
| 2024 | ll_top10 | -0.066 | -0.089 | -0.045 | 20 |
| 2024 | spearman | 0.081 | 0.054 | 0.113 | 20 |
| 2025 | ll_podium | -0.051 | -0.097 | -0.003 | 20 |
| 2025 | ll_top10 | -0.075 | -0.121 | -0.032 | 20 |
| 2025 | spearman | 0.139 | 0.090 | 0.194 | 20 |
| 2026 | ll_podium | -0.055 | -0.089 | -0.018 | 14 |
| 2026 | ll_top10 | -0.037 | -0.055 | -0.018 | 14 |
| 2026 | spearman | 0.056 | 0.034 | 0.077 | 14 |

**Rule 1: PASS: use the grid model once qualifying is available.**

## Rule 2: circuit-scaled minus plain grid model

| metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|
| ll_win | 0.001 | -0.000 | 0.002 | 54 |
| ll_podium | 0.000 | -0.001 | 0.002 | 54 |
| ll_top10 | -0.001 | -0.002 | 0.000 | 54 |
| spearman | 0.001 | -0.001 | 0.002 | 54 |

**Rule 2: FAIL: use one grid weight for every circuit.**

## Grid model vs simply finishing where you qualified

| metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|
| spearman | 0.002 | -0.019 | 0.024 | 54 |
| mae | 0.000 | -0.139 | 0.141 | 54 |

## Setting used in the live forecast

Chosen on all seasons (so in-sample): **a1.5_d2.0_k0.0**. Best five by pooled win/podium/top-10 log loss:

| config | pooled log loss |
|---|---|
| a1.5_d2.0_k0.0 | 0.253 |
| a1.5_d1.5_k0.0 | 0.254 |
| a2.5_d2.0_k0.0 | 0.255 |
| a2.5_d1.5_k0.0 | 0.256 |
| a1.5_d3.0_k0.0 | 0.261 |

The ordering of a grid-model forecast is about the same as qualifying order (see the comparison above); its benefit is better-calibrated probabilities.

## Limitations

- The qualifying position is used as the grid. Grid penalties and pit-lane starts are not known at forecast time, so they are not reflected (in the backtest or in live forecasts).
- Circuit factors come from at most three past visits per circuit, so they are noisy; the factor is shrunk toward 1.
- 2026 is a regulation change and only has its first 18 rounds.