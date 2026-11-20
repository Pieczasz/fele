# Model card — fele draft models

Phase 8 of [AGENT_PLAN.md](../AGENT_PLAN.md). Method details: [METHODOLOGY.md](METHODOLOGY.md). Full comparison:
[`experiments/2026-11-20-ladder+action_ladder.md`](experiments/2026-11-20-ladder+action_ladder.md). Explanations:
[`experiments/2026-11-20-explain.md`](experiments/2026-11-20-explain.md).

## Decision (fixed before the holdout was opened)

| Problem | Chosen model | Why |
|---|---|---|
| A. Who wins, given the final draft | **`baseline_elo`** (logistic on pre-game Elo) | No rung met the promotion rule (§5.5). The best, `bayes_hier`, improved log loss by 0.0041 with a 95% CI of [−0.0097, +0.0018]: consistent but not distinguishable from zero. Rule: keep the simpler model. |
| B. Next pick / ban | **`action_lambdarank`** (LightGBM LambdaRank, temperature-calibrated) | Beats the global-frequency baseline by −0.607 log loss [−0.628, −0.588] and the simpler conditional logit by −0.045 [−0.053, −0.035] (G3+: −0.058 [−0.077, −0.041]). |

`bayes_hier` is evaluated on the holdout as a **pre-declared challenger, for transparency only**; its holdout result
does not change the decision above.

## Data

- GRID official pro data, 1,737 games / 745 series, Jan 2025 – Oct 2026 (LCK, LEC, LCS / LTA North, LTA South;
  2026 = LCS + LEC only). Draft actions: 34,644 picks/bans.
- **Development:** the earliest 633 series. **Final holdout:** the latest 112 series (2026-02-27 → 2026-10-12, LEC
  2026 Spring + LCS 2026), used once.
- Static: Data Dragon numbers (patch deltas), hand-made champion tags. Solo-queue data is **not** a model input (it
  exists only for patches after the GRID games, so it can't be used time-respectingly).

## Features (all time-respecting)

One chronological pass: each game's features come only from strictly earlier games; a draft action also sees the
earlier actions of its game and the series' Fearless locks. Leakage tests flip every later result and scramble every
later draft on the real data and require earlier features to be bit-identical.

- Outcome (blue − red): pre-game Elo, form (last 10 games), shrunk champion win rate and presence (trailing 3 patches),
  player comfort on the picked champion (recency-weighted games, shrunk win rate, first-time picks), patch delta,
  composition tags (AP share, engage, disengage, peel, frontline, poke, dive, split-push, waveclear, hard CC, scaling,
  damage balance), series score, game-3+ flag.
- Draft action, per available champion: league pick/ban presence, shrunk win rate, the team's recency-weighted
  pick/ban habits, own/opponent player comfort, patch delta, co-pick synergy (PMI) with own / opponent picks so far,
  whether it fills a role the team (or the opponent) still needs; separate weights for picks, bans and phase-2 bans.

## Evaluation protocol

Walk-forward by calendar month over the last 8 development months (2025-04 … 2026-02), series-grouped; every
hyperparameter (penalty, k, leaf size, LightGBM settings incl. 25-trial Optuna, softmax temperature, calibration) is
chosen on **inner** walk-forward folds of each training set. 95% CIs resample series (paired bootstrap, 2,000 draws).

## Results on the walk-forward folds (1,137 games, 22,654 draft actions)

### A. Who wins (log loss; coin flip = 0.6931)

| Model | Family | Log loss | Δ vs Elo [95% CI] | AUC | ECE |
|---|---|---|---|---|---|
| `baseline_elo` (chosen) | logistic on Elo | 0.6280 | — | 0.706 | 0.032 |
| `bayes_hier` | hierarchical Bayes (PyMC, ADVI) | 0.6239 | −0.0041 [−0.0097, +0.0018] | 0.711 | 0.035 |
| `logit_l2` / `logit_l3` | penalised logistic, Elo unpenalised | 0.6251 / 0.6252 | −0.0029 / −0.0028 (CI ∋ 0) | 0.710 | 0.039 / 0.037 |
| `logit_archetypes` | + SVD embeddings & k-means archetypes (unsupervised) | 0.6258 | −0.0022 (CI ∋ 0) | 0.710 | 0.040 |
| `logit_champions` | + champion strengths (Bradley–Terry style) | 0.6291 | +0.0011 (CI ∋ 0) | 0.704 | 0.043 |
| `knn` | k-nearest neighbours | 0.6374 | +0.0094 (CI ∋ 0) | 0.692 | 0.040 |
| `lgbm`, `lgbm_optuna` | gradient boosting (monotone in Elo) | 0.642 / 0.646 | +0.014 / +0.018 (worse) | 0.683 | 0.034 |
| `random_forest`, `extra_trees` | bagged trees | 0.643 / 0.648 | +0.015 / +0.020 (worse) | 0.68 | 0.031 / 0.050 |
| `gaussian_process`, `svm_rbf` | kernel methods | 0.652 / 0.656 | +0.024 / +0.028 (worse) | 0.67 / 0.66 | 0.039 / 0.027 |
| `naive_bayes` | Gaussian NB | 0.778 | +0.150 (worse) | 0.692 | 0.148 |

Calibrated variants (Platt, isotonic, fitted on cross-fitted inner folds) and an average of logistic + LightGBM did
not help either.

### B. Next pick / ban

| Model | Log loss | Top-1 | Top-5 | Top-10 | MRR |
|---|---|---|---|---|---|
| `action_global` (baseline) | 3.849 | 7.9% | 31.4% | 50.7% | 0.205 |
| `action_team_slot` (baseline) | 4.061 | 9.9% | 33.3% | 49.8% | 0.222 |
| `action_clogit` | 3.287 | 15.6% | 48.6% | 67.2% | 0.312 |
| **`action_lambdarank`** (chosen) | **3.242** | 15.6% | **49.6%** | **68.6%** | **0.316** |

## Interpretation

- Pre-game team strength (Elo) carries almost all the predictable signal in *who wins*. Inner-fold tuning chose very
  strong shrinkage for draft features (λ = 300–1,000); the Bayesian model's posterior scales agree (team effects
  beyond Elo 0.16 > champion effects 0.07 > draft features 0.05, log-odds), and champion effects are about as large as
  their own uncertainty. Flexible models overfit ~1,300 training games.
- *Which champion comes next* is much more predictable: picks follow synergy with the team's earlier picks, open
  roles, pro presence and player comfort; bans deny the opponent's synergy, target opponent player pools and roles the
  opponent still needs.

## Final holdout (run once, 2026-11-20 — [`experiments/2026-11-20-holdout.md`](experiments/2026-11-20-holdout.md))

Trained on all 633 development series, scored once on the latest 112 series (316 games, 6,319 draft actions; LCS
2026 + LEC 2026 Spring). The decision above was committed before this run (`ef5a890`).

| Problem | Model | Holdout | Walk-forward (for comparison) |
|---|---|---|---|
| A | `baseline_elo` (chosen) | log loss 0.6404 [0.5968, 0.6802], AUC 0.681, accuracy 66.5%, ECE 0.069 | 0.6280, AUC 0.706, 65.2%, ECE 0.032 |
| A | `bayes_hier` (challenger) | Δ vs Elo −0.0051 [−0.0108, +0.0007], ECE 0.076 | −0.0041 [−0.0097, +0.0018] |
| B | `action_lambdarank` (chosen) | log loss 3.352, Δ vs global **−0.817** [−0.870, −0.765]; top-1 15.5%, top-10 64.4%, MRR 0.306 | 3.242, −0.607; top-10 68.6%, MRR 0.316 |
| B | `action_global` (baseline) | log loss 4.169, top-10 40.7% | 3.849, top-10 50.7% |

- **The outcome conclusion holds out of sample:** the challenger is again a little better than Elo and again not
  significantly so; Elo stays.
- **Calibration:** Elo's holdout ECE (0.069) is above the 0.05 target, but 316 games can't resolve that: drawing
  outcomes from Elo's own probabilities, a *perfectly calibrated* model scores ECE 0.056 at the median (90% range
  0.033–0.084) at this size. On the 1,137 walk-forward games Elo's ECE is 0.032 vs 0.030 for a perfect model.
- **The draft-action model generalises:** its lead over the baseline grows on the newer patches (the global
  frequencies go stale faster than the learned features), with top-10 at 64% vs 41%.
- Cloud9 holdout games (65): Elo log loss 0.654, accuracy 63% — descriptive only.

## Post-review fix (2026-11-20, after the holdout) — [`experiments/2026-11-20-action_ladder.md`](experiments/2026-11-20-action_ladder.md)

A code review found that role assignment gave each pick its first tagged role in top→support order instead of its
primary role (Wukong "jungle|top" became top), which distorted the draft model's role-fit features. Fixed
(primary role first, every pick gets a role) and re-evaluated **walk-forward only**:

| `action_lambdarank` | log loss | top-10 (all) | top-10 (picks) | MRR |
|---|---|---|---|---|
| before the fix | 3.242 | 68.6% | 66.1% | 0.316 |
| after the fix | 3.149 | 71.1% | 70.0% | 0.326 |

LambdaRank stays the best rung (conditional logit 70.2%, global baseline 50.7%), so the choice is unchanged. The
holdout numbers above describe the pre-fix model; the holdout is spent and is not re-run, so the fixed model has no
holdout figure. The model cards on the scouting page quote the walk-forward hit rate.

## Limits and what the models must not be used for

- Probabilities are for draft prep and simulation, not betting; the outcome model is essentially an Elo model.
- Elo compares teams within a region only (leagues rarely meet).
- Roles come from Phase 2 inference (99.9% agreement), assumed known once the draft ends.
- 2026 data covers LCS and LEC only; LCK/LTA behaviour after 2025 is extrapolated.
- Draft-action probabilities describe what teams *tend* to do, not what they *should* do; the recommendation engine
  (Phase 9) presents ranked options with reasons, never orders.
- Data Dragon has no spell damage numbers, so patch deltas miss damage-only changes.
