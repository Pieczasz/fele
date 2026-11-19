# Data dictionary

`uv run fele ingest` replays every GRID LoL feed (745 series, ~45 s on 8 cores) into Parquet files in
`data_local/parquet/` (gitignored, never committed) and registers them as DuckDB views in schema **`lol`**
(`data_local/fele.duckdb`, PyCharm data source "fele.duckdb"). Re-runs rewrite everything (idempotent).

All IDs are GRID strings. `t_s` is the in-game clock in seconds (from the snapshot sent with each event, so pauses
are already excluded). Coordinates are Summoner's Rift units (bounds 300–16000; blue base bottom-left).

## How the feeds are replayed

- **Final state is the source of truth** for results, drafts and box scores: the last `seriesState` already reflects
  rollbacks and lists only games that were played (a rolled-back game start is absent).
- **Rollbacks (`!` actions) in event tables:** an undo removes the most recent earlier event with the same
  (action, actor, target). 12,476 purchase undos and 461 draft corrections exist in the corpus. Event rows of games
  missing from the final state are dropped.
- **Benched substitutes** appear in some final rosters with no champion; they are dropped (17 rows).

## Tables

### `lol.series` — one row per series (745)

| Column | Meaning |
|---|---|
| series_id | GRID series id |
| event, stage, league | From `lol/series.csv`; `league` = event prefix (`LCK`, `LEC`, `LCS`, `LTA North`, …) |
| format | `best-of-1/3/5` |
| scheduled_start, started_at | UTC timestamps |
| team1_id, team2_id, team1_score, team2_score, winner_team_id | Series result from the final state |
| games_played | Games present in the feed |
| valid | GRID validity flag |
| rollbacks | Number of `!` (undo) events in the feed (data-quality signal) |

### `lol.games` — one row per game (1,739 = `meta/games.csv`)

| Column | Meaning |
|---|---|
| game_id, series_id, game_number | `game_number` = order inside the series |
| patch | e.g. `16.3`; null for 2 games (empty in GRID) |
| started_at, duration_s, finished | UTC start, final clock, finished flag |
| blue_team_id, red_team_id, winner_team_id | Sides and result |
| first_pick_team_id, first_pick_side | Team of the first pick. **Since 2026 ("First Selection") red side picks first in ~45% of games**; in 2025 blue always did |
| draft_actions, draft_standard | Number of draft actions; true when they match the 20-slot template exactly (1,719 games) |

### `lol.draft_actions` — one row per pick/ban (34,663)

| Column | Meaning |
|---|---|
| seq | GRID sequence number (renumbered by GRID when a ban is skipped) |
| slot | Position 1–20 in the standard template, aligned so skipped bans leave a gap; null if out of order (18 rows) |
| phase | `ban1` (1–6), `pick1` (7–12), `ban2` (13–16), `pick2` (17–20) |
| action | `ban` / `pick` |
| team_id, side | Drafting team and its side in this game |
| champion, champion_id | GRID display name and id (map to Data Dragon with `fele.static.champions`) |

**Validated draft order** (A = first-pick team, B = the other): bans `A B A B A B`, picks `A B B A A B`,
bans `B A B A`, picks `B A A B`. 1,477 games blue-first + 242 red-first follow it exactly. Exceptions: 13 games with
skipped bans (18–19 actions), 2 recorded slightly out of order, 4 with no draft events, 1 with a single action.

### `lol.participants` — one row per player-game (17,370 = 1,737 games × 10)

| Column | Meaning |
|---|---|
| game_id, team_id, side, player_id, player_name | `player_name` trimmed (GRID has e.g. `"Loki "`) |
| roster_index | Position in GRID's roster list — **not** a role |
| champion, win | |
| kills, deaths, assists | Final KDA (`assists` = GRID `killAssistsGiven`) |
| gold_earned, net_worth, xp | Final economy |
| damage_dealt, damage_taken, vision_score | Final totals |
| minions_killed, neutral_killed, wards_killed | GRID `unitKills` |
| final_items | Inventory at game end |
| inferred_role | `top` / `jungle` / `mid` / `bot` / `support` (see below) |
| role_confidence | Posterior probability of the chosen 5-player assignment (all 120 assignments scored) |
| lane_swap | Team's duo laned top and its solo laner bot early (≈7% of team-games, mostly early 2025) |
| support_item, early_top, early_mid, early_bot | Signals used: bought the support item line; early (1:30–10:00) position snapshots per lane |

**Role inference.** GRID has no role column and roster order matches the role only ~50–60% of the time. Signals:
jungle = share of the team's neutral-monster kills; support = support item line (World Atlas → …); mid = early
snapshots on the mid lane; bot vs top = which side lane the duo used (normal vs lane-swap hypotheses are both scored);
champion→role priors learned from the confident games (2 EM rounds); roster order as a weak prior.

Validation (`uv run pytest -m real_data`, after `fele ingest`):
- every team-game gets exactly one player per role;
- 99.9% of player-games match the player's most common role. The rest are mostly genuine role changes (for example a
  jungler who moved to support, with support items and no jungle farm);
- 99.5% of player-games have confidence ≥ 0.9; filter `role_confidence < 0.9` to review the rest.
- the inferred jungler is the team's top neutral-monster killer in ≥ 98% of games (Smite isn't in the feed, so this
  stands in for the "agrees with Smite" check).

### `lol.kills` — one row per champion kill (48,410)

`game_id, t_s, killer_id, killer_team_id, victim_id, victim_team_id, assist_ids[], x, y` — position is the
victim's. `killer_id` is null for executions (tower/minion/`game` kills); `killer_team_id` is then the crediting team.

### `lol.objectives` — one row per objective (97,907)

| Column | Meaning |
|---|---|
| type | GRID objective type: `slayVoidGrub`, `slayRiftHerald`, `slayBaron`, `slay<Infernal/Ocean/Mountain/Cloud/Hextech/Chemtech>Drake`, `slayElderDragon`, `slay<Voracious/Ruinous/Thornbound>Atakhan`, `slayRiftScuttler<Top/Bot>`, `destroyTower`, `destroyFortifier` (inhibitor), `destroyNexus`, `destroyTurretPlate<Lane>[1-3]` |
| kind | `type` without the trailing digit. Plates are `destroyTurretPlateTop` on 15.x and `…Top1/2/3` on 16.x |
| team_id, player_id | Crediting team; player null when no player got the last hit |
| structure_id | For towers/inhibitors/nexus: e.g. `red-turret-top-1`, `blue-inhibitor-mid` |
| x, y | Crediting player's position |

The generic `slayDragon` event (sent with the typed drake event since 15.10) is dropped to avoid double counting.
**Not in the feed:** normal jungle camps (raptors, wolves, …) and ward placements.

### `lol.levelups` (251,871), `lol.item_events` (695,631), `lol.positions` (1.5 M)

- `levelups`: `game_id, t_s, player_id, level, x, y` (level reached, 2–18).
- `item_events`: `game_id, t_s, player_id, item_id, item, action` with action `purchased/sold/lost/acquired/pickedUp`;
  undone purchases are removed. `item` is null when the feed never names that id (~1%).
- `positions`: every position snapshot attached to a player's own event (`source` = event type). These are
  **snapshots at event times, not continuous tracking**, so pathing claims must say so.

### `lol.fearless_state` — one row per game

`game_id, series_id, game_number, locked_champions[], locked_count`: champions picked by **either** team in earlier
games of the series (hard Fearless). Bans don't carry over. **No re-picks** exist after applying rollbacks. The raw
feeds contain 183 apparent re-picks, all of them draft entries that GRID later rolled back with
`team-!picked-character`.

## Other schemas in `fele.duckdb`

- `grid.*`: GRID `meta/*.csv` and `lol/series.csv` as-is (LoL rows only).
- `leaguepedia.*`: CC BY-SA 3.0 pick/ban history (`fele fetch-leaguepedia-hf`), kept separate from GRID data.
- `soloq.participants`, `aggregates.*`: Riot API high-elo sample and its champion × role × patch aggregates.

## What GRID data must not be used for

Each player's `externalLinks` include a `RIOT_PUUID`. fele does **not** ingest it. Linking GRID players to Riot API
accounts would combine GRID data with other data to profile individuals (GRID licence §3(e)).
