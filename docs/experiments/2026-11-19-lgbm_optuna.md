# Evaluation: `lgbm_optuna`

Generated 2026-11-19 23:19 UTC by `fele evaluate --model lgbm_optuna`.

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
| `lgbm_optuna` | 0.6462 [0.6250, 0.6660] | 0.0182 [0.0056, 0.0301] | 0.2265 | 0.683 | 0.645 | 0.034 |

### `lgbm_optuna` per fold

| Test month | Train series | Train games | Test games | Log loss | Accuracy |
|---|---|---|---|---|---|
| 2025-04 | 135 | 284 | 238 | 0.6485 | 0.651 |
| 2025-05 | 267 | 522 | 235 | 0.6225 | 0.715 |
| 2025-06 | 361 | 757 | 80 | 0.7725 | 0.500 |
| 2025-07 | 383 | 837 | 51 | 0.5668 | 0.745 |
| 2025-08 | 405 | 888 | 253 | 0.6224 | 0.636 |
| 2025-09 | 501 | 1141 | 144 | 0.6548 | 0.660 |
| 2026-01 | 538 | 1285 | 55 | 0.6656 | 0.600 |
| 2026-02 | 586 | 1340 | 81 | 0.6787 | 0.531 |

### `lgbm_optuna` by slice

| Slice | Games | Log loss | Accuracy | ECE |
|---|---|---|---|---|
| all | 1137 | 0.6462 | 0.645 | 0.034 |
| Cloud9 games | 66 | 0.6117 | 0.682 | 0.164 |
| league = LCK | 445 | 0.6391 | 0.652 | 0.039 |
| league = LCS | 45 | 0.6415 | 0.533 | 0.180 |
| league = LEC | 298 | 0.6430 | 0.644 | 0.033 |
| league = LTA Cross-Conference | 22 | 0.5534 | 0.818 | 0.230 |
| league = LTA North | 163 | 0.6333 | 0.706 | 0.113 |
| league = LTA South | 164 | 0.6977 | 0.573 | 0.071 |
| game_bucket = G1 | 497 | 0.6412 | 0.638 | 0.046 |
| game_bucket = G2 | 370 | 0.6405 | 0.662 | 0.047 |
| game_bucket = G3+ | 270 | 0.6630 | 0.633 | 0.070 |
| patch_age = week 1 | 510 | 0.6374 | 0.645 | 0.040 |
| patch_age = week 2 | 491 | 0.6465 | 0.654 | 0.058 |
| patch_age = week 3+ | 136 | 0.6780 | 0.610 | 0.144 |

### `lgbm_optuna` calibration

| Predicted | Games | Mean prediction | Blue win rate |
|---|---|---|---|
| 0.1–0.2 | 7 | 0.187 | 0.429 |
| 0.2–0.3 | 65 | 0.269 | 0.262 |
| 0.3–0.4 | 163 | 0.353 | 0.313 |
| 0.4–0.5 | 251 | 0.454 | 0.394 |
| 0.5–0.6 | 234 | 0.548 | 0.560 |
| 0.6–0.7 | 188 | 0.641 | 0.638 |
| 0.7–0.8 | 170 | 0.755 | 0.724 |
| 0.8–0.9 | 57 | 0.827 | 0.737 |
| 0.9–1.0 | 2 | 0.914 | 0.500 |

### `lgbm_optuna` learning curve (most recent share of each fold's training series)

| Training share | Log loss |
|---|---|
| 25% | 0.6542 |
| 50% | 0.6625 |
| 75% | 0.6512 |
| 100% | 0.6462 |

## Problem B — which champion is picked or banned next

Probability over available champions (earlier picks/bans of the game and Fearless-locked champions removed).

| Model | Slice | Actions | Log loss [95% CI] | Δ vs action_global [95% CI] | Top-1 | Top-5 | Top-10 | MRR |
|---|---|---|---|---|---|---|---|---|
| `action_global` | all | 22654 | 3.849 [3.830, 3.870] | — | 0.079 | 0.314 | 0.507 | 0.205 |
| `action_global` | picks | 11332 | 3.912 [3.894, 3.933] | — | 0.077 | 0.288 | 0.470 | 0.196 |
| `action_global` | bans | 11322 | 3.786 [3.756, 3.817] | — | 0.082 | 0.341 | 0.543 | 0.215 |
| `action_global` | G3+ | 5364 | 3.766 [3.732, 3.800] | — | 0.093 | 0.347 | 0.526 | 0.225 |
| `action_team_slot` | all | 22654 | 4.061 [4.029, 4.094] | 0.212 [0.191, 0.234] | 0.099 | 0.333 | 0.498 | 0.222 |
| `action_team_slot` | picks | 11332 | 4.136 [4.102, 4.171] | 0.224 [0.199, 0.249] | 0.085 | 0.305 | 0.468 | 0.205 |
| `action_team_slot` | bans | 11322 | 3.986 [3.941, 4.034] | 0.200 [0.172, 0.229] | 0.112 | 0.360 | 0.527 | 0.239 |
| `action_team_slot` | G3+ | 5364 | 4.125 [4.068, 4.180] | 0.359 [0.321, 0.396] | 0.107 | 0.334 | 0.507 | 0.230 |

## Reading this

- A coin flip scores log loss 0.6931. These baselines are the bar: a Phase 8 model is promoted only if its
  Δ CI vs `baseline_elo` is entirely below 0, ECE ≤ 0.05, and it is not worse on the G3+ slice (§5.5).
- Small slices (Cloud9, single months) are descriptive: read their n before their numbers.
