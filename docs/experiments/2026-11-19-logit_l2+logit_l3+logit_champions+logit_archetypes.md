# Evaluation: `logit_l2,logit_l3,logit_champions,logit_archetypes`

Generated 2026-11-19 21:37 UTC by `fele evaluate --model logit_l2,logit_l3,logit_champions,logit_archetypes`.

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
| `logit_archetypes` | 0.6258 [0.5998, 0.6520] | -0.0022 [-0.0080, 0.0041] | 0.2178 | 0.710 | 0.651 | 0.040 |
| `logit_champions` | 0.6291 [0.6020, 0.6551] | 0.0011 [-0.0062, 0.0087] | 0.2195 | 0.704 | 0.651 | 0.043 |
| `logit_l2` | 0.6251 [0.5989, 0.6506] | -0.0029 [-0.0086, 0.0027] | 0.2176 | 0.710 | 0.650 | 0.039 |
| `logit_l3` | 0.6252 [0.5988, 0.6510] | -0.0028 [-0.0084, 0.0030] | 0.2176 | 0.710 | 0.653 | 0.037 |

### `logit_l2` per fold

| Test month | Train series | Train games | Test games | Log loss | Accuracy |
|---|---|---|---|---|---|
| 2025-04 | 135 | 284 | 238 | 0.6011 | 0.676 |
| 2025-05 | 267 | 522 | 235 | 0.5827 | 0.685 |
| 2025-06 | 361 | 757 | 80 | 0.7170 | 0.537 |
| 2025-07 | 383 | 837 | 51 | 0.5366 | 0.706 |
| 2025-08 | 405 | 888 | 253 | 0.6185 | 0.640 |
| 2025-09 | 501 | 1141 | 144 | 0.6470 | 0.667 |
| 2026-01 | 538 | 1285 | 55 | 0.6903 | 0.582 |
| 2026-02 | 586 | 1340 | 81 | 0.7212 | 0.593 |

### `logit_l2` by slice

| Slice | Games | Log loss | Accuracy | ECE |
|---|---|---|---|---|
| all | 1137 | 0.6251 | 0.650 | 0.039 |
| Cloud9 games | 66 | 0.6254 | 0.636 | 0.115 |
| league = LCK | 445 | 0.6014 | 0.690 | 0.064 |
| league = LCS | 45 | 0.7017 | 0.622 | 0.162 |
| league = LEC | 298 | 0.6351 | 0.641 | 0.051 |
| league = LTA Cross-Conference | 22 | 0.5663 | 0.818 | 0.265 |
| league = LTA North | 163 | 0.5975 | 0.650 | 0.056 |
| league = LTA South | 164 | 0.6857 | 0.543 | 0.082 |
| game_bucket = G1 | 497 | 0.6087 | 0.652 | 0.062 |
| game_bucket = G2 | 370 | 0.6209 | 0.654 | 0.050 |
| game_bucket = G3+ | 270 | 0.6611 | 0.641 | 0.065 |
| patch_age = week 1 | 510 | 0.6294 | 0.645 | 0.042 |
| patch_age = week 2 | 491 | 0.6143 | 0.654 | 0.036 |
| patch_age = week 3+ | 136 | 0.6479 | 0.654 | 0.108 |

### `logit_l2` calibration

| Predicted | Games | Mean prediction | Blue win rate |
|---|---|---|---|
| 0.0–0.1 | 20 | 0.077 | 0.100 |
| 0.1–0.2 | 61 | 0.159 | 0.230 |
| 0.2–0.3 | 109 | 0.261 | 0.330 |
| 0.3–0.4 | 145 | 0.352 | 0.352 |
| 0.4–0.5 | 159 | 0.453 | 0.428 |
| 0.5–0.6 | 207 | 0.549 | 0.512 |
| 0.6–0.7 | 170 | 0.649 | 0.594 |
| 0.7–0.8 | 134 | 0.748 | 0.769 |
| 0.8–0.9 | 106 | 0.848 | 0.774 |
| 0.9–1.0 | 26 | 0.927 | 0.923 |

### `logit_l2` learning curve (most recent share of each fold's training series)

| Training share | Log loss |
|---|---|
| 25% | 0.6257 |
| 50% | 0.6253 |
| 75% | 0.6265 |
| 100% | 0.6251 |

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
