# Evaluation: `action_lambdarank`

Generated 2026-11-20 22:01 UTC by `fele evaluate --model action_lambdarank`.

## Protocol

- 1737 games / 34644 draft actions in 745 series.
- **Final holdout (locked):** the latest 112 series (2026-02-27 – 2026-10-12). Not used here.
- **Walk-forward folds:** 8 test months (2025-04 … 2026-02); each trains on every earlier series. Splits are by series.
- **95% CIs** resample series (2,000 draws). Δ = model - reference; below 0 means lower (better) loss.

## Problem A — who wins the game

| Model | Log loss [95% CI] | Δ vs baseline_elo [95% CI] | Brier | AUC | Accuracy | ECE |
|---|---|---|---|---|---|---|
| `baseline_blue` | 0.6932 [0.6894, 0.6973] | 0.0652 [0.0430, 0.0873] | 0.2500 | 0.501 | 0.516 | 0.017 |
| `baseline_constant` | 0.6931 [0.6931, 0.6931] | 0.0651 [0.0432, 0.0876] | 0.2500 | 0.500 | 0.484 | 0.016 |
| `baseline_elo` | 0.6280 [0.6055, 0.6499] | — | 0.2189 | 0.706 | 0.652 | 0.032 |

### `baseline_elo` per fold

| Test month | Train series | Train games | Test games | Log loss | Accuracy |
|---|---|---|---|---|---|
| 2025-04 | 135 | 284 | 238 | 0.6240 | 0.676 |
| 2025-05 | 267 | 522 | 235 | 0.5820 | 0.689 |
| 2025-06 | 361 | 757 | 80 | 0.7082 | 0.525 |
| 2025-07 | 383 | 837 | 51 | 0.5432 | 0.706 |
| 2025-08 | 405 | 888 | 253 | 0.6152 | 0.640 |
| 2025-09 | 501 | 1141 | 144 | 0.6470 | 0.674 |
| 2026-01 | 538 | 1285 | 55 | 0.6817 | 0.618 |
| 2026-02 | 586 | 1340 | 81 | 0.7174 | 0.580 |

### `baseline_elo` by slice

| Slice | Games | Log loss | Accuracy | ECE |
|---|---|---|---|---|
| all | 1137 | 0.6280 | 0.652 | 0.032 |
| Cloud9 games | 66 | 0.6320 | 0.621 | 0.108 |
| league = LCK | 445 | 0.6072 | 0.694 | 0.052 |
| league = LCS | 45 | 0.6983 | 0.600 | 0.145 |
| league = LEC | 298 | 0.6312 | 0.644 | 0.052 |
| league = LTA Cross-Conference | 22 | 0.5685 | 0.818 | 0.197 |
| league = LTA North | 163 | 0.6101 | 0.638 | 0.080 |
| league = LTA South | 164 | 0.6850 | 0.555 | 0.069 |
| game_bucket = G1 | 497 | 0.6159 | 0.656 | 0.043 |
| game_bucket = G2 | 370 | 0.6234 | 0.654 | 0.043 |
| game_bucket = G3+ | 270 | 0.6565 | 0.641 | 0.044 |
| patch_age = week 1 | 510 | 0.6329 | 0.649 | 0.038 |
| patch_age = week 2 | 491 | 0.6177 | 0.656 | 0.030 |
| patch_age = week 3+ | 136 | 0.6468 | 0.647 | 0.090 |

### `baseline_elo` calibration

| Predicted | Games | Mean prediction | Blue win rate |
|---|---|---|---|
| 0.0–0.1 | 8 | 0.081 | 0.125 |
| 0.1–0.2 | 39 | 0.156 | 0.154 |
| 0.2–0.3 | 78 | 0.257 | 0.308 |
| 0.3–0.4 | 150 | 0.353 | 0.327 |
| 0.4–0.5 | 199 | 0.453 | 0.402 |
| 0.5–0.6 | 262 | 0.551 | 0.531 |
| 0.6–0.7 | 191 | 0.651 | 0.654 |
| 0.7–0.8 | 119 | 0.747 | 0.782 |
| 0.8–0.9 | 78 | 0.843 | 0.756 |
| 0.9–1.0 | 13 | 0.925 | 0.846 |

### `baseline_elo` learning curve (most recent share of each fold's training series)

| Training share | Log loss |
|---|---|
| 25% | 0.6343 |
| 50% | 0.6301 |
| 75% | 0.6278 |
| 100% | 0.6280 |

## Problem B — which champion is picked or banned next

Probability over available champions (earlier picks/bans of the game and Fearless-locked champions removed).

| Model | Slice | Actions | Log loss [95% CI] | Δ vs action_global [95% CI] | Top-1 | Top-5 | Top-10 | MRR |
|---|---|---|---|---|---|---|---|---|
| `action_global` | all | 22654 | 3.856 [3.836, 3.876] | — | 0.079 | 0.314 | 0.507 | 0.205 |
| `action_global` | picks | 11332 | 3.919 [3.901, 3.939] | — | 0.077 | 0.288 | 0.470 | 0.196 |
| `action_global` | bans | 11322 | 3.792 [3.762, 3.823] | — | 0.082 | 0.341 | 0.543 | 0.215 |
| `action_global` | G3+ | 5364 | 3.775 [3.741, 3.809] | — | 0.093 | 0.347 | 0.526 | 0.225 |
| `action_global` | phase ban1 | 6802 | 3.642 [3.603, 3.684] | — | 0.110 | 0.413 | 0.633 | 0.258 |
| `action_global` | phase pick1 | 6798 | 3.870 [3.847, 3.893] | — | 0.079 | 0.299 | 0.487 | 0.201 |
| `action_global` | phase ban2 | 4520 | 4.018 [3.979, 4.057] | — | 0.039 | 0.231 | 0.409 | 0.150 |
| `action_global` | phase pick2 | 4534 | 3.992 [3.959, 4.025] | — | 0.074 | 0.271 | 0.446 | 0.188 |
| `action_global` | league LCK | 8899 | 3.822 [3.794, 3.851] | — | 0.088 | 0.325 | 0.519 | 0.215 |
| `action_global` | league LCS | 900 | 3.911 [3.821, 4.016] | — | 0.058 | 0.313 | 0.469 | 0.188 |
| `action_global` | league LEC | 5885 | 3.895 [3.856, 3.938] | — | 0.072 | 0.297 | 0.498 | 0.195 |
| `action_global` | league LTA Cross-Conference | 440 | 3.675 [3.627, 3.736] | — | 0.091 | 0.332 | 0.559 | 0.221 |
| `action_global` | league LTA North | 3258 | 3.870 [3.807, 3.933] | — | 0.088 | 0.329 | 0.512 | 0.216 |
| `action_global` | league LTA South | 3272 | 3.870 [3.819, 3.918] | — | 0.063 | 0.301 | 0.487 | 0.189 |
| `action_lambdarank` | all | 22654 | 3.149 [3.128, 3.169] | -0.707 [-0.727, -0.687] | 0.161 | 0.514 | 0.711 | 0.326 |
| `action_lambdarank` | picks | 11332 | 3.191 [3.164, 3.221] | -0.727 [-0.749, -0.704] | 0.158 | 0.505 | 0.700 | 0.321 |
| `action_lambdarank` | bans | 11322 | 3.106 [3.077, 3.134] | -0.686 [-0.714, -0.660] | 0.163 | 0.523 | 0.723 | 0.330 |
| `action_lambdarank` | G3+ | 5364 | 3.136 [3.093, 3.181] | -0.639 [-0.677, -0.601] | 0.177 | 0.522 | 0.717 | 0.338 |
| `action_lambdarank` | phase ban1 | 6802 | 3.038 [2.998, 3.077] | -0.604 [-0.639, -0.572] | 0.174 | 0.555 | 0.743 | 0.347 |
| `action_lambdarank` | phase pick1 | 6798 | 3.230 [3.200, 3.260] | -0.640 [-0.666, -0.613] | 0.151 | 0.480 | 0.680 | 0.309 |
| `action_lambdarank` | phase ban2 | 4520 | 3.208 [3.169, 3.249] | -0.810 [-0.846, -0.777] | 0.148 | 0.477 | 0.694 | 0.305 |
| `action_lambdarank` | phase pick2 | 4534 | 3.134 [3.086, 3.181] | -0.858 [-0.890, -0.826] | 0.170 | 0.541 | 0.729 | 0.340 |
| `action_lambdarank` | league LCK | 8899 | 3.062 [3.029, 3.095] | -0.760 [-0.793, -0.729] | 0.171 | 0.536 | 0.735 | 0.339 |
| `action_lambdarank` | league LCS | 900 | 3.389 [3.274, 3.515] | -0.522 [-0.623, -0.435] | 0.130 | 0.443 | 0.651 | 0.284 |
| `action_lambdarank` | league LEC | 5885 | 3.251 [3.213, 3.293] | -0.644 [-0.678, -0.610] | 0.146 | 0.486 | 0.682 | 0.308 |
| `action_lambdarank` | league LTA Cross-Conference | 440 | 3.134 [3.072, 3.200] | -0.541 [-0.593, -0.493] | 0.105 | 0.523 | 0.770 | 0.291 |
| `action_lambdarank` | league LTA North | 3258 | 3.124 [3.074, 3.180] | -0.746 [-0.804, -0.695] | 0.175 | 0.525 | 0.712 | 0.338 |
| `action_lambdarank` | league LTA South | 3272 | 3.161 [3.111, 3.214] | -0.709 [-0.763, -0.657] | 0.162 | 0.513 | 0.709 | 0.324 |
| `action_team_slot` | all | 22654 | 4.064 [4.032, 4.097] | 0.208 [0.187, 0.231] | 0.099 | 0.333 | 0.498 | 0.222 |
| `action_team_slot` | picks | 11332 | 4.139 [4.105, 4.174] | 0.220 [0.196, 0.246] | 0.085 | 0.305 | 0.468 | 0.205 |
| `action_team_slot` | bans | 11322 | 3.989 [3.943, 4.037] | 0.196 [0.168, 0.226] | 0.112 | 0.360 | 0.527 | 0.239 |
| `action_team_slot` | G3+ | 5364 | 4.129 [4.071, 4.184] | 0.354 [0.316, 0.391] | 0.107 | 0.334 | 0.507 | 0.230 |
| `action_team_slot` | phase ban1 | 6802 | 3.706 [3.643, 3.775] | 0.064 [0.027, 0.102] | 0.137 | 0.435 | 0.611 | 0.279 |
| `action_team_slot` | phase pick1 | 6798 | 3.984 [3.941, 4.028] | 0.114 [0.085, 0.145] | 0.092 | 0.330 | 0.503 | 0.218 |
| `action_team_slot` | phase ban2 | 4520 | 4.414 [4.357, 4.472] | 0.396 [0.357, 0.435] | 0.075 | 0.248 | 0.399 | 0.178 |
| `action_team_slot` | phase pick2 | 4534 | 4.373 [4.319, 4.423] | 0.380 [0.345, 0.414] | 0.075 | 0.268 | 0.418 | 0.185 |
| `action_team_slot` | league LCK | 8899 | 3.998 [3.947, 4.051] | 0.176 [0.141, 0.212] | 0.112 | 0.367 | 0.532 | 0.241 |
| `action_team_slot` | league LCS | 900 | 4.145 [3.978, 4.349] | 0.234 [0.130, 0.348] | 0.059 | 0.282 | 0.456 | 0.182 |
| `action_team_slot` | league LEC | 5885 | 4.103 [4.049, 4.163] | 0.208 [0.169, 0.248] | 0.088 | 0.315 | 0.480 | 0.209 |
| `action_team_slot` | league LTA Cross-Conference | 440 | 4.004 [3.870, 4.158] | 0.329 [0.195, 0.453] | 0.084 | 0.318 | 0.495 | 0.208 |
| `action_team_slot` | league LTA North | 3258 | 4.060 [3.966, 4.158] | 0.190 [0.140, 0.242] | 0.107 | 0.329 | 0.490 | 0.227 |
| `action_team_slot` | league LTA South | 3272 | 4.161 [4.064, 4.252] | 0.291 [0.229, 0.352] | 0.087 | 0.294 | 0.454 | 0.203 |

## Reading this

- A coin flip scores log loss 0.6931. These baselines are the bar: a Phase 8 model is promoted only if its
  Δ CI vs `baseline_elo` is entirely below 0, ECE ≤ 0.05, and it is not worse on the G3+ slice (§5.5).
- Small slices (Cloud9, single months) are descriptive: read their n before their numbers.
