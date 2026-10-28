# Cross-season evaluation

Alpha (sharpening exponent) is chosen by pooled log loss on the SOURCE season only, then applied unchanged to the TARGET season. `gain_vs_uniform` is the mean per-race log-loss improvement with a 95% bootstrap interval over target-season races.

## decay 1.0: choose on 2023, test on 2024

Chosen alpha = **3.0**. (For reference, the alpha that would have been best in-sample on 2024 is 2.5.)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 397 | 0.329 | 0.102 | 0.095 | 0.074 | 0.109 |
| podium | alpha=3.0 (chosen on 2023) | 397 | 0.291 | 0.096 | 0.131 | 0.075 | 0.174 |
| podium | uniform | 397 | 0.425 | 0.128 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 397 | 0.515 | 0.166 | 0.177 | 0.134 | 0.214 |
| top10 | alpha=3.0 (chosen on 2023) | 397 | 0.494 | 0.157 | 0.196 | 0.100 | 0.290 |
| top10 | uniform | 397 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 397 | 0.165 | 0.044 | 0.034 | 0.029 | 0.040 |
| win | alpha=3.0 (chosen on 2023) | 397 | 0.149 | 0.043 | 0.051 | 0.032 | 0.067 |
| win | uniform | 397 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

Calibration, podium:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 205 | 0.009 | 0.010 |
| [0.02, 0.05) | 26 | 0.032 | 0.000 |
| [0.05, 0.1) | 17 | 0.078 | 0.059 |
| [0.1, 0.2) | 36 | 0.160 | 0.278 |
| [0.2, 0.4) | 50 | 0.304 | 0.320 |
| [0.4, 0.7) | 52 | 0.518 | 0.462 |
| [0.7, 1.0) | 11 | 0.745 | 0.636 |

Calibration, top10:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.05, 0.1) | 11 | 0.087 | 0.091 |
| [0.1, 0.2) | 137 | 0.137 | 0.190 |
| [0.2, 0.4) | 61 | 0.265 | 0.328 |
| [0.4, 0.7) | 26 | 0.549 | 0.538 |
| [0.7, 1.0) | 162 | 0.925 | 0.858 |

## decay 1.0: choose on 2024, test on 2023

Chosen alpha = **2.5**. (For reference, the alpha that would have been best in-sample on 2023 is 3.0.)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 356 | 0.324 | 0.098 | 0.102 | 0.089 | 0.115 |
| podium | alpha=2.5 (chosen on 2024) | 356 | 0.279 | 0.085 | 0.146 | 0.113 | 0.181 |
| podium | uniform | 356 | 0.426 | 0.129 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 356 | 0.529 | 0.173 | 0.164 | 0.134 | 0.190 |
| top10 | alpha=2.5 (chosen on 2024) | 356 | 0.494 | 0.159 | 0.199 | 0.131 | 0.257 |
| top10 | uniform | 356 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 356 | 0.140 | 0.039 | 0.060 | 0.054 | 0.064 |
| win | alpha=2.5 (chosen on 2024) | 356 | 0.084 | 0.022 | 0.116 | 0.099 | 0.127 |
| win | uniform | 356 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

Calibration, podium:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 128 | 0.014 | 0.000 |
| [0.02, 0.05) | 63 | 0.034 | 0.063 |
| [0.05, 0.1) | 30 | 0.069 | 0.067 |
| [0.1, 0.2) | 46 | 0.158 | 0.217 |
| [0.2, 0.4) | 48 | 0.303 | 0.271 |
| [0.4, 0.7) | 22 | 0.489 | 0.318 |
| [0.7, 1.0) | 19 | 0.809 | 0.947 |

Calibration, top10:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.1, 0.2) | 104 | 0.156 | 0.154 |
| [0.2, 0.4) | 72 | 0.279 | 0.319 |
| [0.4, 0.7) | 42 | 0.498 | 0.548 |
| [0.7, 1.0) | 138 | 0.890 | 0.855 |

## decay 0.8: choose on 2023, test on 2024

Chosen alpha = **3.0**. (For reference, the alpha that would have been best in-sample on 2024 is 2.5.)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 397 | 0.326 | 0.101 | 0.098 | 0.077 | 0.113 |
| podium | alpha=3.0 (chosen on 2023) | 397 | 0.285 | 0.095 | 0.137 | 0.073 | 0.182 |
| podium | uniform | 397 | 0.425 | 0.128 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 397 | 0.512 | 0.165 | 0.180 | 0.141 | 0.214 |
| top10 | alpha=3.0 (chosen on 2023) | 397 | 0.481 | 0.153 | 0.210 | 0.123 | 0.294 |
| top10 | uniform | 397 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 397 | 0.163 | 0.044 | 0.036 | 0.032 | 0.041 |
| win | alpha=3.0 (chosen on 2023) | 397 | 0.146 | 0.043 | 0.054 | 0.041 | 0.067 |
| win | uniform | 397 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

Calibration, podium:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 202 | 0.008 | 0.010 |
| [0.02, 0.05) | 35 | 0.030 | 0.000 |
| [0.05, 0.1) | 21 | 0.074 | 0.000 |
| [0.1, 0.2) | 22 | 0.144 | 0.273 |
| [0.2, 0.4) | 42 | 0.273 | 0.405 |
| [0.4, 0.7) | 68 | 0.526 | 0.456 |
| [0.7, 1.0) | 7 | 0.758 | 0.571 |

Calibration, top10:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.05, 0.1) | 5 | 0.096 | 0.000 |
| [0.1, 0.2) | 142 | 0.143 | 0.169 |
| [0.2, 0.4) | 60 | 0.285 | 0.400 |
| [0.4, 0.7) | 33 | 0.522 | 0.394 |
| [0.7, 1.0) | 157 | 0.923 | 0.885 |

## decay 0.8: choose on 2024, test on 2023

Chosen alpha = **2.5**. (For reference, the alpha that would have been best in-sample on 2023 is 3.0.)

| target | model | n | log_loss | brier | gain_vs_uniform | gain_ci_low | gain_ci_high |
|---|---|---|---|---|---|---|---|
| podium | alpha=1.0 (unsharpened) | 356 | 0.320 | 0.097 | 0.105 | 0.093 | 0.118 |
| podium | alpha=2.5 (chosen on 2024) | 356 | 0.268 | 0.082 | 0.157 | 0.126 | 0.189 |
| podium | uniform | 356 | 0.426 | 0.129 | 0.000 | 0.000 | 0.000 |
| top10 | alpha=1.0 (unsharpened) | 356 | 0.528 | 0.173 | 0.165 | 0.137 | 0.190 |
| top10 | alpha=2.5 (chosen on 2024) | 356 | 0.496 | 0.161 | 0.197 | 0.126 | 0.255 |
| top10 | uniform | 356 | 0.693 | 0.250 | 0.000 | 0.000 | 0.000 |
| win | alpha=1.0 (unsharpened) | 356 | 0.139 | 0.039 | 0.061 | 0.054 | 0.064 |
| win | alpha=2.5 (chosen on 2024) | 356 | 0.083 | 0.022 | 0.117 | 0.100 | 0.128 |
| win | uniform | 356 | 0.200 | 0.048 | 0.000 | 0.000 | 0.000 |

Calibration, podium:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.0, 0.02) | 125 | 0.014 | 0.008 |
| [0.02, 0.05) | 58 | 0.031 | 0.017 |
| [0.05, 0.1) | 33 | 0.072 | 0.061 |
| [0.1, 0.2) | 49 | 0.158 | 0.204 |
| [0.2, 0.4) | 48 | 0.292 | 0.271 |
| [0.4, 0.7) | 24 | 0.457 | 0.375 |
| [0.7, 1.0) | 19 | 0.813 | 0.947 |

Calibration, top10:

| bin | n | mean_predicted | observed_rate |
|---|---|---|---|
| [0.1, 0.2) | 111 | 0.149 | 0.153 |
| [0.2, 0.4) | 68 | 0.280 | 0.353 |
| [0.4, 0.7) | 38 | 0.552 | 0.579 |
| [0.7, 1.0) | 139 | 0.888 | 0.842 |

## Limitations

- Two seasons, same regulation era (2022 ground-effect rules); no cross-era check.
- Same alpha grid as before; the edge of the grid is 3.0.