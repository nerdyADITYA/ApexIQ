# Rolling (forward-chaining) evaluation

Seasons: 2023, 2024, 2025, 2026 (in progress, 18 of 23 rounds).

For each target season, alpha is chosen on pooled earlier seasons only, then applied unchanged. `gain_vs_uniform` is the mean per-race log-loss improvement, with a 95% bootstrap interval over target-season races.

## Race outcomes, decay 1.0

### Target 2024: alpha chosen on 2023 = **3.0** (in-sample best on 2024: 2.5)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 397 | 0.329 | 0.102 | 0.095 | 0.074 | 0.109 |
| podium | alpha=2.5 (current production) | 397 | 0.289 | 0.095 | 0.134 | 0.087 | 0.170 |
| podium | alpha=3.0 (chosen on 2023) | 397 | 0.291 | 0.096 | 0.131 | 0.076 | 0.174 |
| podium | uniform | 397 | 0.425 | 0.128 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 397 | 0.515 | 0.166 | 0.177 | 0.136 | 0.216 |
| top10 | alpha=2.5 (current production) | 397 | 0.485 | 0.155 | 0.206 | 0.115 | 0.291 |
| top10 | alpha=3.0 (chosen on 2023) | 397 | 0.494 | 0.157 | 0.196 | 0.100 | 0.287 |
| top10 | uniform | 397 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 397 | 0.165 | 0.044 | 0.034 | 0.028 | 0.040 |
| win | alpha=2.5 (current production) | 397 | 0.149 | 0.043 | 0.050 | 0.036 | 0.065 |
| win | alpha=3.0 (chosen on 2023) | 397 | 0.149 | 0.043 | 0.051 | 0.034 | 0.068 |
| win | uniform | 397 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

Calibration (2024, alpha=3.0, podium):

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 205 | 0.009 | 0.010 |
| [0.02, 0.05) | 26 | 0.032 | 0.000 |
| [0.05, 0.1) | 17 | 0.078 | 0.059 |
| [0.1, 0.2) | 36 | 0.160 | 0.278 |
| [0.2, 0.4) | 50 | 0.304 | 0.320 |
| [0.4, 0.7) | 52 | 0.518 | 0.462 |
| [0.7, 1.0) | 11 | 0.745 | 0.636 |

Calibration (2024, alpha=3.0, top10):

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.05, 0.1) | 11 | 0.087 | 0.091 |
| [0.1, 0.2) | 137 | 0.137 | 0.190 |
| [0.2, 0.4) | 61 | 0.265 | 0.328 |
| [0.4, 0.7) | 26 | 0.549 | 0.538 |
| [0.7, 1.0) | 162 | 0.925 | 0.858 |

### Target 2025: alpha chosen on 2023, 2024 = **2.5** (in-sample best on 2025: 2.5)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 396 | 0.314 | 0.096 | 0.111 | 0.097 | 0.125 |
| podium | alpha=2.5 (chosen on 2023+2024) | 396 | 0.252 | 0.077 | 0.174 | 0.136 | 0.210 |
| podium | alpha=2.5 (current production) | 396 | 0.252 | 0.077 | 0.174 | 0.136 | 0.210 |
| podium | uniform | 396 | 0.425 | 0.129 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 396 | 0.572 | 0.193 | 0.121 | 0.088 | 0.152 |
| top10 | alpha=2.5 (chosen on 2023+2024) | 396 | 0.576 | 0.195 | 0.117 | 0.053 | 0.179 |
| top10 | alpha=2.5 (current production) | 396 | 0.576 | 0.195 | 0.117 | 0.054 | 0.179 |
| top10 | uniform | 396 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 396 | 0.156 | 0.043 | 0.044 | 0.041 | 0.047 |
| win | alpha=2.5 (chosen on 2023+2024) | 396 | 0.127 | 0.039 | 0.073 | 0.065 | 0.081 |
| win | alpha=2.5 (current production) | 396 | 0.127 | 0.039 | 0.073 | 0.065 | 0.081 |
| win | uniform | 396 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

Calibration (2025, alpha=2.5, podium):

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 90 | 0.014 | 0.000 |
| [0.02, 0.05) | 142 | 0.029 | 0.028 |
| [0.05, 0.1) | 32 | 0.072 | 0.031 |
| [0.1, 0.2) | 35 | 0.134 | 0.114 |
| [0.2, 0.4) | 32 | 0.311 | 0.344 |
| [0.4, 0.7) | 64 | 0.577 | 0.609 |
| [0.7, 1.0) | 1 | 0.708 | 1.000 |

Calibration (2025, alpha=2.5, top10):

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.1, 0.2) | 53 | 0.158 | 0.226 |
| [0.2, 0.4) | 166 | 0.284 | 0.355 |
| [0.4, 0.7) | 46 | 0.557 | 0.413 |
| [0.7, 1.0) | 131 | 0.907 | 0.840 |

### Target 2026 (regulation change): alpha chosen on 2023, 2024, 2025 = **2.5** (in-sample best on 2026: 2.5)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 307 | 0.305 | 0.093 | 0.094 | 0.087 | 0.102 |
| podium | alpha=2.5 (chosen on 2023+2024+2025) | 307 | 0.253 | 0.082 | 0.146 | 0.124 | 0.166 |
| podium | alpha=2.5 (current production) | 307 | 0.253 | 0.082 | 0.146 | 0.124 | 0.166 |
| podium | uniform | 307 | 0.399 | 0.118 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 307 | 0.544 | 0.179 | 0.145 | 0.099 | 0.189 |
| top10 | alpha=2.5 (chosen on 2023+2024+2025) | 307 | 0.523 | 0.165 | 0.165 | 0.057 | 0.270 |
| top10 | alpha=2.5 (current production) | 307 | 0.523 | 0.165 | 0.165 | 0.052 | 0.272 |
| top10 | uniform | 307 | 0.689 | 0.248 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 307 | 0.149 | 0.040 | 0.036 | 0.029 | 0.043 |
| win | alpha=2.5 (chosen on 2023+2024+2025) | 307 | 0.126 | 0.036 | 0.059 | 0.041 | 0.077 |
| win | alpha=2.5 (current production) | 307 | 0.126 | 0.036 | 0.059 | 0.041 | 0.076 |
| win | uniform | 307 | 0.185 | 0.044 | 0.000 | 0.000 | 0.000 |

Calibration (2026, alpha=2.5, podium):

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 122 | 0.013 | 0.000 |
| [0.02, 0.05) | 56 | 0.033 | 0.018 |
| [0.05, 0.1) | 24 | 0.069 | 0.042 |
| [0.1, 0.2) | 18 | 0.156 | 0.278 |
| [0.2, 0.4) | 56 | 0.297 | 0.357 |
| [0.4, 0.7) | 27 | 0.533 | 0.444 |
| [0.7, 1.0) | 4 | 0.767 | 0.750 |

Calibration (2026, alpha=2.5, top10):

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.1, 0.2) | 124 | 0.135 | 0.121 |
| [0.2, 0.4) | 50 | 0.294 | 0.440 |
| [0.4, 0.7) | 29 | 0.518 | 0.655 |
| [0.7, 1.0) | 104 | 0.900 | 0.808 |

## Race outcomes, decay 0.8

### Target 2024: alpha chosen on 2023 = **3.0** (in-sample best on 2024: 2.5)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 397 | 0.326 | 0.101 | 0.098 | 0.077 | 0.113 |
| podium | alpha=2.5 (current production) | 397 | 0.283 | 0.093 | 0.139 | 0.086 | 0.177 |
| podium | alpha=3.0 (chosen on 2023) | 397 | 0.285 | 0.095 | 0.137 | 0.078 | 0.181 |
| podium | uniform | 397 | 0.425 | 0.128 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 397 | 0.512 | 0.165 | 0.180 | 0.142 | 0.216 |
| top10 | alpha=2.5 (current production) | 397 | 0.475 | 0.152 | 0.216 | 0.132 | 0.293 |
| top10 | alpha=3.0 (chosen on 2023) | 397 | 0.481 | 0.153 | 0.210 | 0.123 | 0.292 |
| top10 | uniform | 397 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 397 | 0.163 | 0.044 | 0.036 | 0.032 | 0.040 |
| win | alpha=2.5 (current production) | 397 | 0.146 | 0.043 | 0.053 | 0.042 | 0.064 |
| win | alpha=3.0 (chosen on 2023) | 397 | 0.146 | 0.043 | 0.054 | 0.041 | 0.067 |
| win | uniform | 397 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

### Target 2025: alpha chosen on 2023, 2024 = **2.5** (in-sample best on 2025: 2.5)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 396 | 0.315 | 0.096 | 0.111 | 0.095 | 0.125 |
| podium | alpha=2.5 (chosen on 2023+2024) | 396 | 0.251 | 0.077 | 0.174 | 0.134 | 0.213 |
| podium | alpha=2.5 (current production) | 396 | 0.251 | 0.077 | 0.174 | 0.131 | 0.212 |
| podium | uniform | 396 | 0.425 | 0.129 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 396 | 0.571 | 0.193 | 0.121 | 0.087 | 0.151 |
| top10 | alpha=2.5 (chosen on 2023+2024) | 396 | 0.574 | 0.193 | 0.119 | 0.053 | 0.180 |
| top10 | alpha=2.5 (current production) | 396 | 0.574 | 0.193 | 0.119 | 0.053 | 0.182 |
| top10 | uniform | 396 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 396 | 0.155 | 0.042 | 0.045 | 0.041 | 0.049 |
| win | alpha=2.5 (chosen on 2023+2024) | 396 | 0.124 | 0.037 | 0.076 | 0.066 | 0.086 |
| win | alpha=2.5 (current production) | 396 | 0.124 | 0.037 | 0.076 | 0.066 | 0.086 |
| win | uniform | 396 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

### Target 2026 (regulation change): alpha chosen on 2023, 2024, 2025 = **2.5** (in-sample best on 2026: 3.0)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 307 | 0.303 | 0.093 | 0.097 | 0.087 | 0.106 |
| podium | alpha=2.5 (chosen on 2023+2024+2025) | 307 | 0.248 | 0.081 | 0.151 | 0.125 | 0.176 |
| podium | alpha=2.5 (current production) | 307 | 0.248 | 0.081 | 0.151 | 0.128 | 0.175 |
| podium | uniform | 307 | 0.399 | 0.118 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 307 | 0.541 | 0.177 | 0.148 | 0.101 | 0.193 |
| top10 | alpha=2.5 (chosen on 2023+2024+2025) | 307 | 0.520 | 0.163 | 0.169 | 0.060 | 0.277 |
| top10 | alpha=2.5 (current production) | 307 | 0.520 | 0.163 | 0.169 | 0.049 | 0.278 |
| top10 | uniform | 307 | 0.689 | 0.248 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 307 | 0.149 | 0.039 | 0.036 | 0.029 | 0.043 |
| win | alpha=2.5 (chosen on 2023+2024+2025) | 307 | 0.127 | 0.036 | 0.059 | 0.040 | 0.077 |
| win | alpha=2.5 (current production) | 307 | 0.127 | 0.036 | 0.059 | 0.038 | 0.076 |
| win | uniform | 307 | 0.185 | 0.044 | 0.000 | 0.000 | 0.000 |

## Championship forecast vs actual champion

Probability assigned to the eventual champion after selected rounds, using alpha chosen on earlier seasons (2023 has no earlier season, so alpha = 1). Three outcomes: illustrative, not statistical evidence. Sprints still to come are ignored.

### 2023: champion VER, alpha 1.0

| after_round | leader | leader_p | p_actual_champion |
|---|---|---|---|
| 5 | VER | 0.701 | 0.701 |
| 8 | VER | 0.983 | 0.983 |
| 12 | VER | 1.000 | 1.000 |
| 16 | VER | 1.000 | 1.000 |
| 20 | VER | 1.000 | 1.000 |

Mean log score of the true champion over all rounds: 0.072 (lower is better; a uniform guess over 20 drivers would score about 3.0).

### 2024: champion VER, alpha 3.0

| after_round | leader | leader_p | p_actual_champion |
|---|---|---|---|
| 5 | VER | 0.941 | 0.941 |
| 8 | VER | 0.940 | 0.940 |
| 12 | VER | 1.000 | 1.000 |
| 16 | VER | 0.996 | 0.996 |
| 20 | VER | 0.993 | 0.993 |

Mean log score of the true champion over all rounds: 0.101 (lower is better; a uniform guess over 20 drivers would score about 3.0).

### 2025: champion NOR, alpha 2.5

| after_round | leader | leader_p | p_actual_champion |
|---|---|---|---|
| 5 | PIA | 0.579 | 0.292 |
| 8 | PIA | 0.486 | 0.464 |
| 12 | PIA | 0.609 | 0.391 |
| 16 | PIA | 0.901 | 0.099 |
| 20 | NOR | 0.522 | 0.522 |

Mean log score of the true champion over all rounds: 1.147 (lower is better; a uniform guess over 20 drivers would score about 3.0).

### 2026 (in progress): alpha 2.5

After round 18 of 23: leader **ANT**, modelled title probability 1.000. No champion yet, so no score.

## Limitations

- Three target seasons, all under at most two regulation sets; the 2026 check is the only regulation-change test.
- 2026 is incomplete, so its result covers 14 predicted rounds and carries wide uncertainty.
- Fixed 5% DNF rate; no qualifying, circuit or reliability features; sprints remaining ignored in the championship simulation.
- Points-per-race strength is a blunt car-plus-driver proxy; it cannot see mid-season upgrades or driver changes beyond form.