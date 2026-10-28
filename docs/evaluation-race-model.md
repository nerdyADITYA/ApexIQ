# Race model evaluation (full finishing order)

Seasons 2023-2026; target seasons [2024, 2025, 2026]. Each race is predicted from earlier races only (first 4 rounds of a season are warm-up). Settings (alpha, beta, gamma) are chosen per target season on earlier seasons only. 2026 is a regulation change and is still in progress.

## Pre-registered adoption rule

Adopt only if, pooled over the target seasons, the 95% interval of the improved-minus-baseline difference is entirely below 0 for BOTH podium and top-10 log loss, the win log-loss difference has an upper bound below +0.01 (not materially worse), and the Spearman rank-correlation difference has a lower bound above -0.01.

## Settings chosen on earlier seasons

| target | config |
|---|---|
| 2024 | a1.5_b1.5_g0.1 |
| 2025 | a1.5_b1.0_g0.1 |
| 2026 | a1.5_b1.0_g0.1 |

Config name: `a` = exponent on points-form strength, `b` = weight on race-pace rating, `g` = weight on qualifying-position rating (b = g = 0 is the baseline).

## Average scores over the target races (lower is better except Spearman)

| config | ll_win | ll_podium | ll_top10 | ll_dnf | spearman | mae |
|---|---|---|---|---|---|---|
| baseline (points form) | 0.136 | 0.269 | 0.529 | 0.449 | 0.606 | 3.534 |
| championship order | nan | nan | nan | nan | 0.614 | 3.782 |
| improved model | 0.134 | 0.263 | 0.522 | 0.449 | 0.629 | 3.372 |
| improved model + shrunk DNF | 0.134 | 0.263 | 0.506 | 0.393 | 0.629 | 3.440 |
| last race result | nan | nan | nan | nan | 0.478 | 4.375 |
| uniform | 0.196 | 0.418 | 0.692 | 0.396 | 0.000 | 5.093 |

## By season

| year | config | ll_win | ll_podium | ll_top10 | ll_dnf | spearman | mae |
|---|---|---|---|---|---|---|---|
| 2024 | baseline (points form) | 0.151 | 0.293 | 0.487 | 0.373 | 0.655 | 3.277 |
| 2024 | improved model | 0.146 | 0.286 | 0.484 | 0.373 | 0.668 | 3.170 |
| 2025 | baseline (points form) | 0.128 | 0.254 | 0.574 | 0.385 | 0.528 | 3.674 |
| 2025 | improved model | 0.130 | 0.253 | 0.566 | 0.385 | 0.552 | 3.572 |
| 2026 | baseline (points form) | 0.126 | 0.255 | 0.524 | 0.650 | 0.647 | 3.702 |
| 2026 | improved model | 0.123 | 0.246 | 0.515 | 0.650 | 0.681 | 3.373 |

## Improved minus baseline, paired over the same races (95% bootstrap interval over races)

| metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|
| ll_win | -0.002 | -0.005 | 0.001 | 54 |
| ll_podium | -0.005 | -0.012 | 0.003 | 54 |
| ll_top10 | -0.007 | -0.017 | 0.003 | 54 |
| spearman | 0.022 | 0.008 | 0.038 | 54 |
| mae | -0.163 | -0.218 | -0.114 | 54 |

| year | metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|---|
| 2024 | ll_podium | -0.007 | -0.021 | 0.012 | 20 |
| 2024 | ll_top10 | -0.004 | -0.016 | 0.010 | 20 |
| 2024 | spearman | 0.013 | -0.001 | 0.028 | 20 |
| 2025 | ll_podium | -0.001 | -0.010 | 0.009 | 20 |
| 2025 | ll_top10 | -0.008 | -0.026 | 0.009 | 20 |
| 2025 | spearman | 0.024 | -0.011 | 0.060 | 20 |
| 2026 | ll_podium | -0.009 | -0.016 | -0.002 | 14 |
| 2026 | ll_top10 | -0.009 | -0.031 | 0.015 | 14 |
| 2026 | spearman | 0.033 | 0.024 | 0.043 | 14 |

**Decision: DO NOT ADOPT the improved strength model.**

Reading the result: the improved model orders the finishing positions significantly better (rank correlation and position error intervals exclude 0) but its probability log-loss gains do not clear zero, so it fails the rule above. Adopting it anyway for the ordered classification would be a decision made after seeing the results, not a result of the rule.

## Shrunk (per driver and team) retirement rates vs fixed 5%

| metric | mean | ci_low | ci_high | races |
|---|---|---|---|---|
| ll_dnf | -0.057 | -0.081 | -0.032 | 54 |
| spearman | 0.001 | -0.005 | 0.007 | 54 |
| ll_top10 | -0.016 | -0.026 | -0.006 | 54 |

**Decision: ADOPT shrunk retirement rates.**

## Limitations

- Three target seasons (about 54 races); intervals are over races, which are not independent of each other.
- Pace needs enough clean laps in a race (15), so a few races have no pace rating for some drivers.
- Weather, safety cars and strategy are not modelled; 2026 only has its first 18 rounds.