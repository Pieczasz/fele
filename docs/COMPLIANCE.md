# Compliance: data sources, rules, open questions

Checked 2026-11-18. Every claim below is sourced in the research notes:
[hackathon & draft rules](research/hackathon-and-draft-rules.md) ·
[Riot platform](research/riot-platform.md) ·
[external data sources](research/external-data-sources.md).
Only sources marked ✅ or ⚠️ (with their conditions met) may be used (AGENT_PLAN ground rule 3).

## 1. Source matrix

| Source | What we use it for | Status | Conditions |
|---|---|---|---|
| **GRID hackathon data** (`stl-hackathon-2026-grid-starter`) | Pro drafts, games, events (LCK/LEC/LTA/LCS 2025–26) | ⚠️ | Hackathon period only; local only; **never commit** data or derivatives that contain/reconstruct it; outputs (stats, charts) may be shown to judges; no ML model that outlives the hackathon; AI-tool training/retention opt-out ON; §3(e): don't combine with other data to profile individuals |
| **Riot API** (dev key → personal key) | High-elo solo-queue champion strength on the live patch | ⚠️ | Key in `.env` only; server-side; register the product; dev key can't back a public product → hosted demo serves a **cached snapshot**, no live calls; no player ratings/MMR; no de-anonymising/hidden players; no spectator/live-game features; aggregates only |
| **Data Dragon** | Champion/item static data, icons (UI + video) | ✅ | Riot boilerplate visible (footer + README) |
| **Leaguepedia via `gptilt/lol-esports-matches`** (Hugging Face, CC BY-SA 3.0) | 138k pro games with picks/bans: LPL, internationals, Cloud9 history, all 2026 leagues | ⚠️ | Attribution "Leaguepedia contributors, CC BY-SA 3.0"; keep its files **separate** from GRID-derived files (share-alike vs GRID no-redistribution); stays in `data_local/` |
| **Leaguepedia Cargo API** (direct) | Player-level pools, exact pick order, Worlds 2026 knockouts | ⚠️ / ❓ | API only (never HTML scraping), bot password, 1 req at a time, User-Agent. Fandom ToS (2025-12-19) bars "automated means" and ML training on content without permission → **ask before using for model training** |
| **Riot Games Open Access powered by GRID** (launched mid-Nov 2026) | Possibly Worlds 2026 in the same GRID format | ❓ | Terms only visible after sign-up at riot.grid.gg — human must register and read them |
| **Oracle's Elixir** | Per-player pro stats CSVs 2014–2026 | ⚠️ | No formal license; local use, credit; ask the author before committing anything derived |
| **CommunityDragon** | Gap-filling static assets only | ⚠️ | Unofficial; prefer Data Dragon |
| **League Client API (LCU)**, local | fele Live: champ select in the user's own games, scrim drafts, party members' recent games from the client's match history | ⚠️ | Unsupported by Riot; local only (127.0.0.1, the user's own fele); identities and stats only for the user and lobby party members, other allies shown as "Ally", enemies never analysed; ranked options with reasons, never one pick; note LCU use on the Developer Portal product ([research §10](research/riot-platform.md)) |
| **Anthropic API** (Ask fele, opt-in) | Natural-language answers over fele's own aggregates | ⚠️ | Off unless `ANTHROPIC_API_KEY` is set; sends aggregates only (stats tables, model outputs), never raw GRID events or Riot match JSON; the API does not train on inputs by default; decision by the human 2026-11-21, pending the organizer question below |
| **Coach preferences** (`config/preferences.yaml`) | Comfort tiers, refused picks, prio players, save lists | ✅ | Our own input; real file gitignored |
| OP.GG MCP, MetaBot.GG MCP | Current-patch stats | ❓ | Terms forbid/limit automated collection — not used unless the organizers or vendors approve |
| u.gg, lolalytics, Mobalytics, League of Graphs, DPM.LOL, METAsrc, Blitz, gol.gg, TrackingThePros, LoLPros | — | ❌ | No public API, so access would mean scraping |
| Unofficial lolesports API | — | ❌ | Undocumented, no terms; Riot directs to supported services |

## 2. Rules checklist (product design consequences)

- [x] MIT `LICENSE` at the repo root (needs to show in GitHub's About section once the repo is pushed)
- [x] ≥1 JetBrains tool; `.idea` run configurations committed; `AI_SHOWCASE.md` kept current
- [x] Riot boilerplate (exact LoL wording) in web footer + README
- [x] Data-leak guard: `.gitignore`, `scripts/check_no_data.sh` (pre-commit + CI, incl. full history)
- [ ] Demo: private site is allowed **if login credentials are in the testing instructions**; must stay up and free until 2027-02-03 15:00 PT → password gate + cached aggregates.
  What a host would hold: `data_local/aggregates` and `static` (aggregates), and `models/live-v4.pkl` (5 MB: fitted
  models plus the feature store's accumulated state). That state has no per-game draft rows, but it does keep each
  player's dated champion history (needed for recency weighting) — include this in the organizer question before
  deploying.
- [ ] Video < 3 min, public YouTube, Data Dragon icons + own UI only; no broadcast footage, no copyrighted music, no team/league logos without permission
- [ ] Recommendations always multiple ranked options with reasons (Riot: don't remove/dictate decisions)
- [ ] No Elo/MMR shown as a player/team ranking (internal model feature only)
- [ ] Player solo-queue pools: **off by default** (`riot_ids` empty); only Riot IDs the coach enters for Cloud9's own roster, shown in a separate panel, never auto-mapped from Leaguepedia `SoloqueueIds`
- [ ] Register the product on the Riot Developer Portal; apply for a personal key now (up to ~3 weeks)

## 3. Draft rules the simulator must follow (2026)

- Order: bans A B A B A B · picks A B B A A B · bans B A B A · picks B A A B, where **A = first-pick team, which may be red side**: side and pick order are separate fields.
- **First Selection:** the holder chooses side *or* pick order; the other team takes the remaining choice. G1: higher seed or coin flip (LCS Split 1: first team drawn). G2+: the loser of the previous game holds it.
- **Hard Fearless:** champions picked by either team in earlier games are locked for both teams; bans reset every game; **no G5 reset** in LCS (G5 has 40 locked + 10 bans).
- 2025 data (most of GRID) used the old rule: blue always picked first; the loser chose side.
- UNVERIFIED: remake handling, G5 rules in LCK/LEC/LPL 2026.

- [x] GRID players' `externalLinks` carry Riot PUUIDs. fele never ingests or uses them: linking GRID players to
  Riot API accounts would be "combining with other data to profile individuals" (GRID licence §3(e)).

## 4. Open questions for organizers (human to send)

Send via Cloud9 Discord office hours (discord.gg/cloud9) or the Devpost "Email the hackathon manager" link.

> Hi! We're building a Category 2 draft/Fearless planner. A few compliance questions:
> 1. **Hosted demo:** may a password-protected demo site (credentials only in the Devpost testing instructions) serve *aggregates* derived from GRID data (pick/ban rates, tendencies, model outputs; never raw events) until judging ends?
> 2. **Combining data (GRID license §3(e)):** we'd like to show Cloud9 players' recent solo-queue champion pools, from Riot IDs entered manually by the coach, next to their GRID pro champion pools. Is that acceptable, or should solo-queue data stay champion-level only?
> 3. **External pro data:** may we combine GRID with Leaguepedia (CC BY-SA) pick/ban data for leagues GRID doesn't cover (LPL, internationals)? And is "Riot Games Open Access powered by GRID" data allowed in submissions?
> 4. **Video:** are Data Dragon champion icons fine, and may we show the Cloud9/LCS names (no logos)?
> 5. **LLM features:** may a local tool send GRID-derived *aggregates* (pick/ban rates, model outputs) to an LLM API (Anthropic, no training on inputs) to answer a coach's questions?
> 6. **Bonus prize:** does an `AI_SHOWCASE.md` covering JetBrains Air + Junie + Claude qualify for Best AI-Powered Workflow Story?

## 5. Human to-dos

1. ~~Confirm the AI-tool training/retention opt-out~~ Confirmed by the human, 2026-11-19 (license §4(c)).
2. Organizer questions above: deferred by the human (2026-11-19). Until answered, keep the conservative defaults
   (aggregates only, solo-queue pools off by default, Leaguepedia kept separate).
3. Riot **personal key**: product registered (URL verified via `https://pieczasz.github.io/fele/riot.txt`), approval
   pending (2026-11-19). Meanwhile the dev key in `.env` is regenerated daily.
4. Optionally register for Riot Games Open Access (riot.grid.gg) and read its terms.
5. Create a Leaguepedia bot password only if we decide to use the Cargo API directly.
6. Add "uses the League Client API (champ select, local only)" to the registered Riot product.
7. After judging ends (2027-02-03): delete the hosted demo's model artifacts and aggregates, and `data_local/models/`
   locally (GRID licence: no ML model that outlives the hackathon).
