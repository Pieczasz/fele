# Methodology

How fele turns data into numbers. Statistics first (Phase 5); the models (Phases 7–8) will add their own sections.
Code: `engine/src/fele/stats/`. Tables: `uv run fele stats` → `aggregates.stats_*` (see `docs/DATA_DICTIONARY.md`).

## Principles

- **Every rate shows its evidence:** `k` of `n`, a 95% interval, and (where the sample is small) a shrunk estimate.
- **Tendencies are tested,** not eyeballed: a team's rate is compared with its league's rate, with a correction for
  testing thousands of things at once.
- **Time-respecting where it matters:** Elo, ban targeting and player pools use only games before the one in
  question. Patch windows include their own patch, so model features for patch P must use window P-1.
- **Honest limits are part of the output:** positions are event-time snapshots (no continuous tracking), the feed
  has no normal jungle camp events, and Data Dragon has no spell damage numbers.

## Rates and intervals (`stats/core.py`)

- `rate = k / n` with a **Wilson score interval** (95%). It behaves at 0/n and n/n, unlike the normal approximation.
- **Empirical-Bayes shrinkage:** a Beta(a, b) prior is fitted by maximum likelihood to all groups of the same kind
  (beta-binomial likelihood). Each group's estimate is the posterior mean `(k + a) / (n + a + b)` with a 95% credible
  interval from Beta(k + a, n − k + b). `a + b` is the prior's strength in pseudo-games: a champion needs about that
  many games before its own record outweighs the average.
- The optimiser is Nelder–Mead on log(a), log(b). L-BFGS-B was tried first and silently stopped at the bounds
  (its finite-difference gradient stalls on this likelihood's flat ridge); a unit test now checks that a simulated
  Beta(30, 30) prior is recovered.

**Finding: pro champion win rates are mostly noise.** Fitted over all patch windows, the prior strength is ~180
games for top, ~520–670 for mid/bot/support, and unbounded (complete pooling) for jungle: across ~7,000 jungle
games, champion win rates vary no more than chance would produce. So shrunk pro win rates stay close to 50% and the
meta score leans on presence (what pros prioritise) rather than on raw win rates. Priors fitted per window were
unstable (5 pseudo-games in one window, 10,000 in the next), so one prior per role is fitted over all windows.
Player × champion win rates use one prior per role (strength 10–23 games).

## Tendency significance

For each team rate (draft presence, macro metrics) a two-sided **binomial test** against the league base rate gives
`p`; **Benjamini–Hochberg** across every row of the table gives `q`.

| Label | Rule | Reading |
|---|---|---|
| strong | q < 0.05 | survives the correction for testing every team × champion / metric |
| weak | p < 0.05, q ≥ 0.05 | worth a look, could be chance |
| noise | otherwise | don't build a plan on it |

## Draft priority (`stats/draft.py`)

Per team × champion, for all games and for the last 120 days, overall and split by side and by game number in the
series (G1 / G2 / G3+, the Fearless dimension):
- **presence** = team-games where the team picked or banned the champion, out of the team's games;
- **first rotation** = the same, counting only ban phase 1 and pick phase 1 (template slots 1–12);
- **avg_slot** = mean template slot (1–20; lower = taken earlier);
- **base_rate** = the same presence over all team-games in the team's league (tendency baseline).

**Ban targeting:** for each ban, the opponent player whose pro games *before that game* include the champion most
often is the "target". Bans that hit no opponent's earlier pool (meta bans) have no target. Per team, `k` = bans
faced that targeted a player, `n` = all bans faced.

## Player pools (`stats/pools.py`)

From pro games before `as_of`:
- `recent_games = Σ 0.5^(age_days / 90)`: a game today counts 1, one 90 days ago counts 0.5;
- `comfort = recent_games × shrunk_win_rate / 0.5`;
- **effective pool size** = exp(entropy) of the player's champion distribution ("how many equally played champions
  is this pool worth"), with a basic-bootstrap 95% interval (games resampled 400×), widened to contain the estimate;
- **depth** = champions with `recent_games ≥ 1`;
- **meta overlap** = how many of the live top-10 meta champions for the player's role they have ≥ 2 pro games on.

## Team strength (`stats/elo.py`)

Game-level Elo (K = 32, start 1500), updated in time order, so each game's ratings use only earlier games. One rating
per team; leagues barely meet (internationals, LTA Cross-Conference), so ratings compare teams within a region only.
**Internal model feature, never displayed as a ranking.** Sanity check on all 1,737 games: log loss 0.638 vs 0.693
for a coin flip, 64% of winners predicted (66% once both teams have ≥ 10 rated games).

## Macro context (`stats/macro.py`)

Per team-game, then aggregated per team (with league base rates and tendency labels):
- **jungle start side** = the map half (split by the mid-lane diagonal) where the jungler reached level 2 (median
  1:47); it agrees with the level-3 half 93% of the time;
- **first scuttle** (who and which side), **first blood / tower / drake / grubs / herald** (did the team get the
  game's first), **grubs before drake** (the team's first grub came before its first drake);
- **timings** = median and quartiles of the team's own first objective of each kind;
- **early kill heatmap** = kills and deaths in the first 15 minutes per 1000 × 1000 map cell, by side.

## Meta score (`stats/meta.py`)

Per trailing patch window (the patch and the two before it that GRID has games on), plus a `live` window that
combines the latest pro window with the live patch's solo-queue sample and the Data Dragon changes since the last
GRID patch:

```
meta_score = 0.50·z(pro presence) + 0.25·z(shrunk pro win rate)
           + 0.15·z(shrunk solo-queue win rate) + 0.10·z(patch delta score)
```

`z` standardises within the window; a missing component counts as average (0). The weights are a readable
heuristic for the meta view. The Phase 8 models learn their own weights from the components.

## Evaluation protocol (Phase 7, `engine/src/fele/eval/`)

`uv run fele evaluate --model <name>` runs one model **and every baseline** through the same folds and writes
`docs/experiments/<date>-<model>.md` (plus an MLflow run in `data_local/mlflow.db`).

- **Final holdout:** the latest 15% of series (112: 2026-02-27 → 2026-10-12, LEC 2026 Spring and LCS 2026). No fold
  touches it. `splits.holdout_split(confirm=True)` opens it once, at the end of Phase 8, and records the use in
  `data_local/holdout_used.json`; a second use is refused.
- **Outer folds:** walk-forward by calendar month over the last 8 months with games before the holdout (2025-04 …
  2026-02; Oct–Dec 2025 have no games). Each fold trains on every earlier series and tests on that month.
  **Inner folds** (`splits.inner_folds`) split a training set the same way, for tuning and calibration in Phase 8.
- **By series, never by game.** Confidence intervals resample series (paired bootstrap, 2,000 draws).
- **Metrics.** Outcome: log loss, Brier, ROC AUC, accuracy, ECE (10 bins) and a reliability table, overall and by
  league, game number (G1/G2/G3+), patch age (week 1/2/3+) and for Cloud9 games. Draft actions: log loss, top-1/5/10,
  mean reciprocal rank, over the champions still available (earlier picks/bans and Fearless locks removed).
- **Leakage tests** (`tests/test_eval.py`, also on real data): folds are time-ordered and disjoint; changing a game's
  result never changes that game's or earlier games' features; Elo `n` counts only earlier games; no in-game statistic
  is a feature; a draft action only knows earlier actions of its game and the series' Fearless locks.

**Baselines — the bar to beat** (pooled over the 8 folds, 1,137 games / 22,655 draft actions):

| Problem | Model | Result |
|---|---|---|
| Outcome | coin flip / blue-side rate | log loss 0.693 (side alone predicts nothing out of sample) |
| Outcome | `baseline_elo` (logistic on pre-game Elo) | log loss **0.628** [0.606, 0.650], AUC 0.706, accuracy 65%, ECE 0.032 |
| Draft | `action_global` (champion frequency, latest 3 patches) | top-10 **50.7%**, MRR 0.205, log loss 3.85 |
| Draft | `action_team_slot` (team × action × phase, shrunk to global) | better ranking (top-1 9.9%, MRR 0.222) but worse log loss (+0.21): overconfident on thin team histories |
