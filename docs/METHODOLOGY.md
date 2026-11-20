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

Per team × champion, for all games and for the team's own last 120 days (each league's data ends on a different date, so a dataset-wide window would empty whole leagues), overall and split by side and by game number in the
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
- `recent_games = Σ 0.5^(age_days / 90)`, age counted from the player's own latest game: that game counts 1, one 90 days earlier counts 0.5;
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

## Model ladder (Phase 8, `engine/src/fele/models/`, decision in [MODEL_CARD.md](MODEL_CARD.md))

- **Feature store** (`features/state.py`): one chronological pass; each game sees only strictly earlier games, each
  draft action also the earlier actions of its game and the series' Fearless locks. The champion vocabulary comes from
  the static champion map (a vocabulary built from the games would itself depend on future drafts — caught by the
  leakage test). Real-data leakage test: flip every result and scramble every draft after a cutoff; all earlier
  features must be bit-identical.
- **Nested validation:** every hyperparameter (penalty, k, leaf size, LightGBM grid / 25-trial Optuna TPE, softmax
  temperature, Platt/isotonic calibration) is chosen on walk-forward inner folds of each outer training set.
- **Outcome ladder:** penalised logistic regression (L2/L3 feature sets; Elo unpenalised — uniform shrinkage made
  the first rung *lose* to Elo by shrinking the strong signal with the noise), champion strengths (signed one-hot),
  unsupervised archetypes (TruncatedSVD embeddings + k-means), naive Bayes, kNN, random forest, extra trees, RBF SVM,
  Gaussian process, LightGBM (monotone in Elo; grid and Optuna), calibrated variants, an average, and a hierarchical
  Bayesian logistic model (PyMC, ADVI) with partially pooled champion and team effects.
- **Draft-action ladder:** conditional logit over available champions (L2, gradient-checked) and LightGBM
  LambdaRank with an inner-fold softmax temperature.
- **Result:** draft actions are very predictable (top-10 69% walk-forward, 64% holdout vs 51% / 41% for the
  baseline); game outcomes beyond Elo are not — every outcome rung was within ±0.005 log loss of Elo or significantly
  worse, so Elo stays (promotion rule §5.5). The holdout (opened once) agrees.

## Recommendation engine & series simulator (Phase 9, `engine/src/fele/engine/`)

**Live context** (`fele live`, cached in `data_local/models/live.pkl`): the feature-store state after the last game,
LambdaRank and the draft-aware logistic outcome model refit on **all** games (evaluation is over), current Elo,
current lineups, the team's pick-style profile and solo-queue lane matchups.

**Draft state**: the validated pro order (bans ABABAB, picks ABBAAB, bans BABA, picks BAAB; A = first-pick team, which
may be red since 2026) with hard Fearless locks.

**Options for our next action** (`POST /draft/recommend`, < 0.4 s). Score = sum of evidence-backed parts with
**fixed** weights (a design choice, not tuned on results); every part becomes a reason with its evidence:

| Part | Basis |
|---|---|
| what pro teams pick/ban in this exact spot | LambdaRank (71% top-10 walk-forward; 64% on the holdout before the role fix) |
| coach comfort tier × `preferences.weight`; save-for-later and never-pick lists | `config/preferences.yaml` |
| the player's recent pro games and shrunk win rate on the champion | GRID, recency-weighted |
| composition gaps filled (damage balance, frontline, engage, peel) | reviewed champion tags |
| coach style tags and the team's own pick profile | tags + the team's pick history |
| lane matchup vs the enemy laner (shrunk, shown only with ≥ 10 games) | high-elo solo queue |
| win-probability change after the enemy's 3 likeliest answers (depth-1 expectimax) | outcome model — weak evidence |
| bans: their likely next pick × their players' comfort, coach must-bans | LambdaRank from the enemy's side |

**Roles.** Each pick takes its primary role (the first role in `champion_tags.csv`) if still free, else its next
tagged role, else any free role. The same rule feeds the draft model's role-fit features, the recommender's open
roles and lane matchups, and the outcome model's lineup, so every champion picked reaches the win probability.

**Save list.** A champion is "saved" in a game when the coach's save list holds it (games 1–2) or the planner's save
plan keeps it for a later game. Mode *Best options* keeps saved champions with a penalty and says why; *Respect save
list* leaves them out. Must-bans match the opponent by name prefix or id ("Team Liquid" matches "Team Liquid
Alienware"), are always on the ban list, and scale with `preferences.weight` (0 turns coach input off).

**Live win probability**: 24 completions of the draft sampled from LambdaRank (both teams), averaged with the outcome
model, shown with a 10–90% range. **Series simulator** (`POST /series/simulate`): Monte Carlo of Bo3/Bo5 with hard
Fearless, our side skipping champions the coach rules out (a player's "refuses" blocks a champion only when no
teammate plays it), the loser taking first pick next game and the winner then choosing blue side (2026 First
Selection; who chooses what is an assumption);
outputs series win probability ± Monte Carlo error, champion availability per game, each player's remaining
comfortable pool, and plan comparisons flagged "within noise" when |difference| < 2 SE.

**Back-test** (`fele backtest`, the last 2 development months, draft model trained on earlier series only, state
as of each game; the holdout is not used again): of 1,332 actual picks, 1,271 were among the engine's candidates (the
rest count as misses). The actual pick is the draft model's top option 12.7% / in its top 5 45.6%; the recommender's
re-ranking (adding composition, style and lane) is level with it (12.9% / 45.8%, difference +0.2 pp
[−1.1, +1.5]). Matching pros is a sanity check, not the goal; whether the re-ranking wins more can't be measured,
since draft effects on win probability are below what this data can detect (Phase 8). The first version ran on
holdout drafts and skipped picks the engine couldn't offer, which inflated it (16.8% / 48.8%); a code review caught
both. The Fearless property test found and fixed a simulator bug (a series could play twice in one round).

## "How to win" cards (Phase 10, `GET /teams/{id}/cards`)

Cards only restate numbers computed elsewhere, each with its evidence count and a strength label:

| Kind | Source | Rule |
|---|---|---|
| draft | `stats_team_draft`, game-1 split | first-rotation pick/ban rate, ≥ 5 game 1s and ≥ 3 occurrences, top 2 |
| draft | `stats_team_draft`, all games | `strong` tendency (BH q-value) above the league rate, largest gap, top 2 |
| players | `stats_ban_targets` | the player whose pool absorbs the most bans faced |
| players | `/players` | current player (n ≥ 20) with the smallest effective pool, with its 95% interval |
| macro | `stats_macro_rates` | 3 non-noise tendencies with the lowest p-value |
| model | LambdaRank, live context | their 3 likeliest first bans / first picks vs us, with the walk-forward top-10 hit rate |

The series planner and mock draft run in the browser on top of `/draft/recommend` and `/series/simulate`; the plan
and coach inputs live in `localStorage` and can be exported as JSON (plan also as CSV).
