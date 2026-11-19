# Evaluation: `baseline_elo`

Generated 2026-11-19 21:12 UTC by `fele evaluate --model baseline_elo`.

## Protocol

- 1737 games / 34645 draft actions in 745 series.
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
| `action_global` | all | 22655 | 3.850 [3.830, 3.871] | — | 0.079 | 0.314 | 0.507 | 0.205 |
| `action_global` | picks | 11332 | 3.913 [3.894, 3.933] | — | 0.077 | 0.288 | 0.470 | 0.196 |
| `action_global` | bans | 11323 | 3.786 [3.756, 3.818] | — | 0.082 | 0.340 | 0.543 | 0.214 |
| `action_global` | G3+ | 5364 | 3.767 [3.734, 3.801] | — | 0.093 | 0.346 | 0.525 | 0.225 |
| `action_team_slot` | all | 22655 | 4.062 [4.029, 4.095] | 0.212 [0.190, 0.233] | 0.099 | 0.333 | 0.497 | 0.222 |
| `action_team_slot` | picks | 11332 | 4.137 [4.102, 4.172] | 0.224 [0.200, 0.249] | 0.085 | 0.305 | 0.468 | 0.205 |
| `action_team_slot` | bans | 11323 | 3.986 [3.938, 4.037] | 0.200 [0.171, 0.229] | 0.112 | 0.360 | 0.526 | 0.239 |
| `action_team_slot` | G3+ | 5364 | 4.127 [4.069, 4.181] | 0.360 [0.321, 0.396] | 0.106 | 0.334 | 0.505 | 0.230 |

## Reading this

- A coin flip scores log loss 0.6931. These baselines are the bar: a Phase 8 model is promoted only if its
  Δ CI vs `baseline_elo` is entirely below 0, ECE ≤ 0.05, and it is not worse on the G3+ slice (§5.5).
- Small slices (Cloud9, single months) are descriptive: read their n before their numbers.
