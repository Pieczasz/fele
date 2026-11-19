# External data sources: what we can legally use

Project: **fele**. MIT, public GitHub repo, password-protected non-commercial demo for the Cloud9 x JetBrains hackathon.
Research date: **2026-11-18**. Every claim has a URL and "checked 2026-11-18". Anything I could not confirm is marked **UNVERIFIED**.

Legend: ✅ allowed · ⚠️ allowed with conditions · ❌ not allowed · ❓ ask first

> This is research, not legal advice. Where a license is unclear, the plan's rule applies: stop and ask.

---

## 1. Source matrix

| # | Source | Data we'd use | Access | License / terms (short) | Public repo + hosted demo | Cache locally / commit aggregates | Coverage incl. 2026 / LCS / C9 | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | **Leaguepedia** Cargo API (`lol.fandom.com/api.php?action=cargoquery`) | Games, player-level picks/stats, pick-ban order, schedules, tournaments, rosters, `Players.SoloqueueIds`, `FavChamps` | MediaWiki API (JSON). Bot password + confirmed email recommended. 500 rows per query. | Text content is CC BY-SA 3.0. The wiki's API page invites use. Fandom ToU bans "automated means" without written permission. | Yes, with attribution and share-alike on any data we publish | Yes. Committed derived data must be CC BY-SA 3.0, in separate files from GRID data | 2026 present: LPL 675 games, LCS 283, Worlds 2026 110, MSI 71 (pick-ban rows), First Stand 45, plus academies and ERLs. Updated through 2026-11-17 | ⚠️ |
| 1b | **gptilt/lol-esports-matches** (Hugging Face mirror of Leaguepedia) | Games, picks/bans per side (role-ordered), matches, tournaments | Parquet download | CC BY-SA 3.0. Says it's for non-commercial research and tooling | Yes, with attribution to Leaguepedia + GPTilt | Yes, same as row 1 | Weekly snapshot, last modified 2026-10-25. **No player names** | ⚠️ |
| 2 | **Oracle's Elixir** match data CSVs | One row per player and per team per game: picks, bans, stats. LCS, LEC, LCK, LPL, PCS, CBLoL and more | Google Drive folder with one CSV per year, 2014–2026 | No formal license. "Provided free of charge… for use by analysts, commentators, and fans." "Game statistics are the property of Riot Games." | Demo yes. Don't commit the CSVs | Cache locally. Committing aggregates is **probably OK but not stated** | 2026 file exists. Whether it contains LCS 2026 / Worlds 2026 is UNVERIFIED (not downloaded) | ⚠️ |
| 3 | **lolesports "persisted" API** (`esports-api.lolesports.com`, `feed.lolesports.com`) | Schedules, live stats windows | Undocumented, shared public key | No published terms. Riot: "Products should use supported services from Riot Games for data ingestion." Official esports data is licensed through GRID | — | — | — | ❌ |
| 4 | **gol.gg** (Games of Legends) | Pro stats, drafts | No API. HTML only | No terms page found (UNVERIFIED). Scraping would be needed | — | — | — | ❌ |
| 5a | **OP.GG MCP server** (`mcp-api.op.gg/mcp`) | Champion meta, matchups, builds, summoner profiles, `lol_get_pro_player_riot_id` | Official MCP endpoint. Repo is MIT | Repo license covers code, not data. OP.GG ToU (2026-09-14): personal, non-commercial use only. No reproducing or republishing. No automated scripts | Not for our pipeline | No | Current patch | ❓ (❌ for ingestion without written OK) |
| 5b | **MetaBot.GG MCP** (`metabot.gg/api/mcp`) | Current-patch tier lists, win/pick rates, matchups, builds | Public MCP, no key, about 60 req/min/IP | "Free to use" in published content **with a dofollow link** to the source page. Caching not addressed | Displaying with links: probably yes. Storing: UNVERIFIED | UNVERIFIED | Current patch. No pro data | ❓ |
| 5c | u.gg, lolalytics, Mobalytics, METAsrc, Blitz, League of Graphs / Porofessor, DPM.LOL | Soloq meta stats | No public API found | ToU pages blocked (403) or missing (404) for automated fetch. UNVERIFIED | — | — | — | ❌ (do not scrape) |
| 5d | **trackingthepros.com**, **lolpros.gg** | Pro to soloq account lists | No API | TTP terms page returns "Page Not Found". LoLPros terms (2018) have no data-reuse clause | Manual reference by a human only | No | Current | ❌ for automated use |
| 6 | **PandaSkill dataset** (IEEE DataPort, by PandaScore) | 37,388 pro matches 2019-09 → 2024-09: metadata, player stats, events | CSV. Needs IEEE DataPort subscription | CC BY 4.0 | Yes, with attribution | Yes | Ends 2024-09. No 2025–2026 | ⚠️ (access UNVERIFIED) |
| 6b | Kaggle / other HF LoL datasets | Mostly soloq snapshots or re-uploads of OE/Leaguepedia | Download | Uploader's label (MIT/Apache) cannot relicense Riot or OE data | — | — | Stale (2024–2025) | ❌ / not worth it |
| 7 | **CommunityDragon** (`raw.communitydragon.org`) | Extra static game data and assets | HTTP files | No license or limits published. Runs under Riot's "Legal Jibber Jabber" policy | Use Data Dragon instead. CDragon only for gaps, with disclaimer | Cache yes | Every patch | ⚠️ |
| 7b | **Data Dragon** (Riot, official) | Champions, items, runes, icons per patch | Static JSON/CDN | Official Riot service | Yes, with Riot boilerplate | Yes | Every patch | ✅ |
| 8a | **Riot Open Access powered by GRID** (new) | Official LoL esports Central Data Feed, Series State API, Loopfeed. Worlds 2026 first | Free API key at `riot.grid.gg/register` | "Non-commercial use: learning and experimentation." No betting. Delayed data. GRID's ToS page is a **placeholder**. Real terms are shown at sign-up (UNVERIFIED) | UNVERIFIED | UNVERIFIED | Worlds 2026 confirmed by announcement. Other leagues and history UNVERIFIED | ❓ |
| 8b | Riot API (`match-v5`, `league-v4`, `account-v1`) | Current-patch high-elo champion stats. Pro soloq pools if approved | Official API key | Riot API ToU + policies, Riot boilerplate | Yes (key server-side). Production/personal key needed for a hosted demo | Store aggregates. Delete on request | Live | ⚠️ (already planned) |
| 8c | Riot Tournament API | Creating tournament codes | — | Not useful for us | — | — | — | n/a |
| 8d | PandaScore API, free tier | Fixtures, teams, players (no results/stats on free tier) | REST, 1000 req/h | Commercial vendor. Stats tiers are paid | Probably, for fixtures | UNVERIFIED | Current | ⚠️ low value |
| 9 | Players' stated champion preferences | `Players.FavChamps` (Leaguepedia, free text). `ExternalContent` table holds links to interviews by player | Cargo | CC BY-SA 3.0 | Yes | Yes | Patchy | ⚠️ manual coach input is better |

---

## 2. Per-source notes

### 2.1 Leaguepedia (lol.fandom.com), ⚠️ allowed with conditions

**What's there** (live queries against the Cargo API, checked 2026-11-18):
- 91 Cargo tables, including `ScoreboardGames`, `ScoreboardPlayers`, `ScoreboardTeams`, `PicksAndBansS7`, `MatchSchedule`, `MatchScheduleGame` (has `RiotPlatformGameId`), `Tournaments`, `TournamentPlayers`, `TournamentRosters`, `Players`, `PlayerRedirects`, `PlayerRenames`, `RosterChanges`, `Contracts`, `ExternalContent`. Source: `https://lol.fandom.com/api.php?action=cargotables&format=json`.
- **`Players` has `SoloqueueIds`**, plus `Lolpros`, `DPMLOL`, `DEEPLOL`, `FavChamps`, `Role`, `Team`, `IsRetired`. Source: `https://lol.fandom.com/api.php?action=cargofields&table=Players&format=json`. `SoloqueueIds` is free-text wiki markup: regions in bold, names split by `<br>`, often with no `#tag`, sometimes stale or including old and alternate accounts. It is not machine-ready. I did not copy any account names into this repo.
- **2026 coverage.** `ScoreboardGames` rows with `DateTime_UTC >= 2026-01-01`, grouped by league: LPL 675, LCK 502, LEC 383, LCP 301, CBLOL 299, **LCS 283** (latest 2026-10-13), NACL 281, EWC 232, Worlds 110 (latest 2026-11-14, patch 26.20), many ERLs and academies (LCK Academy 576, EMEA Masters 524, Prime League 578…). `PicksAndBansS7` 2026: LPL 675, LCS 260, Worlds 110, MSI 71, First Stand 45. `ScoreboardPlayers` 2026: LPL 6,750, LCS 2,600, Worlds 1,100, MSI 710, First Stand 450 rows. Checked 2026-11-18 with `action=cargoquery`.
- **Patch naming differs from GRID.** Leaguepedia uses year-based patches (`26.17`). GRID uses client versions (`16.17`). The latest LCS 2026 game is patch 26.17 on 2026-10-13 in Leaguepedia, and GRID's LCS data also ends at 16.17 on 2026-10-13. That suggests `26.N` = `16.N`, but this is an inference. Verify it on a few overlapping games.
- **Value:** fills the gaps in our GRID data: LPL, MSI/First Stand/Worlds 2026, LCS/LTA history before 2025, ERLs and academies, and full player-level champion history for opponents.

**How to access**
- Endpoint `https://lol.fandom.com/api.php`, `action=cargoquery` (`tables`, `fields`, `where`, `join_on`, `group_by`, `order_by`, `limit`, `offset`).
- Help page (`https://lol.fandom.com/wiki/Help:Leaguepedia_API`, read through the API with `action=parse`, checked 2026-11-18). The HTML wiki pages return a Cloudflare challenge (HTTP 403) to non-browser clients, but `api.php` answers normally:
  - "Our API is made available as a courtesy."
  - "If you want to make cargo queries through the API, it is really important to log in with a Bot Password and have your email address confirmed first, as Fandom added ratelimits that make it practically impossible to execute queries while logged out."
  - Limits: "5,000 results per query if you are an admin · 500 result per query otherwise".
  - "Row IDs should NOT be used as permanent primary keys in your data."
  - Recommended libraries: `mwrogue` (extends `mwcleric`/`mwclient`, MIT, `https://github.com/RheingoldRiver/mwrogue`, checked 2026-11-18). The ratelimit help page (`User:Arbolitoloco/Avoiding cargo ratelimits`, checked 2026-11-18) suggests a patched `mwcleric` that retries failed queries.
- MediaWiki etiquette (`https://www.mediawiki.org/wiki/API:Etiquette`, checked 2026-11-18): make requests "in series rather than in parallel", "set a descriptive User-Agent header", and use `maxlag` for non-interactive jobs.
- No numeric rate limit is published. Fandom's limits are UNVERIFIED.

**License and terms**
- Site rights info from the API: `{'url': 'https://www.fandom.com/licensing', 'text': 'CC BY-SA 3.0'}` (`api.php?action=query&meta=siteinfo&siprop=rightsinfo`, checked 2026-11-18).
- `Leaguepedia:Copyrights` (checked 2026-11-18): "All textual and graphical content on Leaguepedia that we may lawfully license is licensed to you under the Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0) license."
- Fandom Licensing (`https://www.fandom.com/licensing`, read from the Wayback snapshot of 2026-11-17, checked 2026-11-18): "Except where otherwise permitted, the text on Fandom communities ("wikis") is licensed under the Creative Commons Attribution-Share Alike License 3.0 (Unported) (CC BY-SA)… Such use is allowed where attribution is given and the same freedom to re-use and re-distribute applies to any derivative works."
- **Tension.** The Fandom Terms of Use (`https://www.fandom.com/terms-of-use`, "Date of Last Revision: December 19, 2025", read from the Wayback snapshot of 2026-11-15 because the live page is behind a Cloudflare challenge, checked 2026-11-18) say: "not use any robot, spider, scraper or other automated means to access the Services for any purpose without our express written permission". They also prohibit using any "robot, spider, site search and/or retrieval application, or other device to scrape, extract, retrieve or index any portion of the content". There is a carve-out: "Except as expressly permitted by the Company (for example with respect to the use of text content … as permitted as set forth at our licensing page)". Leaguepedia publishes API documentation, and Fandom provides bot passwords and API rate-limit tiers for this purpose. I read that as permission for **API access** (not HTML scraping), but no Fandom document states it explicitly. That's why this is ⚠️ and not ✅.
- The ToU also forbid using content "for the development of any software program, including … training a machine learning or artificial intelligence (AI) system" without consent. **Do not train ML models on Leaguepedia data** without asking. Descriptive stats and Bayesian shrinkage are fine. A learned draft model trained on Leaguepedia data is a grey area: train only on GRID (per its license) or ask.

**Conditions we'll follow**
1. API only (`api.php`), never HTML scraping. Log in with a bot password. Descriptive User-Agent (`fele/<ver> (+repo URL)`). Serial requests, `maxlag`. Incremental pulls by date window. Cache raw responses locally in `data_local/` (gitignored).
2. Attribution in the README and UI footer: "Pro match data from Leaguepedia (lol.fandom.com), CC BY-SA 3.0", with a link.
3. Any Leaguepedia-derived file we commit goes in its own folder with a CC BY-SA 3.0 notice. **Never mix it in one published file with GRID-derived numbers.** GRID forbids redistribution, while share-alike would require redistributing the mix under CC BY-SA. Combining the two at runtime in the app is fine.
4. Don't use `SoloqueueIds` automatically (see §4).

### 2.1b gptilt/lol-esports-matches (Hugging Face), ⚠️

- `https://huggingface.co/datasets/gptilt/lol-esports-matches` (README and API metadata checked 2026-11-18): "Built from Leaguepedia (lol.fandom.com) via its structured Cargo query API… The `ScoreboardGames`, `MatchSchedule`, and `Tournaments` Cargo tables are queried in full on a weekly schedule." License `cc-by-sa-3.0`. "Intended for non-commercial research, data analysis, and tooling." Last modified 2026-10-25T08:00Z. Tables: `games` (patch, teams, winner, picks/bans per side role-ordered, game_number, match_id, riot_game_id), `matches`, `tournaments`. A companion dataset, `gptilt/lol-esports-entities` (CC BY-SA 3.0), resolves team and champion aliases.
- **Why it matters:** a one-shot Parquet download that never touches Fandom, so the ToU question in §2.1 doesn't arise. It is enough for team draft tendencies, priority picks and Fearless usage across LPL and internationals.
- **Limits:** no player names. Picks are only role-ordered, so champion pools per player still need `ScoreboardPlayers` from the Cargo API. It's a snapshot, at least 3 weeks behind as of today, so Worlds 2026 knockouts are probably missing (UNVERIFIED).
- Attribution: credit both Leaguepedia and GPTilt. Share-alike applies to anything we publish from it.

### 2.2 Oracle's Elixir, ⚠️

- Downloads page `https://oracleselixir.com/tools/downloads`. It's a JS app, so I read the text from its bundle `/static/js/main.9ef7a6a4.js` (checked 2026-11-18):
  - "Below you will find a collection of data files containing match data from the LCS, LEC, LCK, LPL, PCS, CBLoL, and many more leagues. Files are in .csv format."
  - "All data has been aggregated and released by Tim Sevenhuysen of OraclesElixir.com. It is provided free of charge, and is intended for use by analysts, commentators, and fans."
  - "Data files are updated ONCE PER DAY. There is no value in downloading the files more frequently than this."
  - "Game statistics are the property of Riot Games, and any usage of such data must follow Riot Games' terms and policies."
  - "Access files via Google Drive" → `https://drive.google.com/drive/folders/1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH`.
- About page (same bundle): "Some content is provided courtesy of Leaguepedia, under a CC-BY-SA 3.0 license." and "If usage terms regarding specific Oracle's Elixir content are unclear, contact Tim Sevenhuysen with your questions to clarify what is and is not permitted."
- FAQ (same bundle): data comes from "Match History pages, lolesports.com, lpl.QQ.com, Leaguepedia, the Riot Games solo queue APIs, and more." Riot's 2022 dev diary says the LoL Esports Data Portal gives "community sites such as Leaguepedia and Oracle's Elixir" official data access (`https://lolesports.com/en-US/news/dev-diary-introducing-the-new-lol-esports-data-portal`, checked 2026-11-18).
- **Coverage:** the Drive folder lists `2014_…` through `2026_LoL_esports_match_data_from_OraclesElixir.csv` (Drive listing checked 2026-11-18). The leagues inside the 2026 file and its freshness are UNVERIFIED because I didn't download bulk data.
- **No explicit license.** No redistribution grant and no attribution clause. A Google Drive download of one file per run is allowed in practice (the site says once per day is enough).
- **Conditions:** download manually or with a once-per-day script into `data_local/`. Never commit the CSVs. Credit "Oracle's Elixir (oracleselixir.com)" plus the Riot boilerplate. Before committing any OE-derived aggregates, email Tim (contact page `https://oracleselixir.com/contact`) or ask on the OE Discord.

### 2.3 lolesports unofficial API, ❌

- No terms are published. Community wrappers say they use a shared default key (search results, e.g. `https://cdn.jsdelivr.net/npm/@viriato/lol-esports-api@0.6.0/README.md`, checked 2026-11-18).
- Riot General Policies (`https://developer.riotgames.com/policies/general`, "LAST UPDATED: MAY 29, 2025", checked 2026-11-18): "Products should use supported services from Riot Games for data ingestion."
- Riot esports data page (`https://riotesportsdata.com/en-us/league-of-legends/`, checked 2026-11-18): live, fixture and A/V data are "only available for commercial purposes through GRID".
- Conclusion: undocumented and unsupported, so don't use it. The official non-commercial route is now Riot Open Access (§2.8).

### 2.4 gol.gg, ❌
- `https://gol.gg/` redirects to `/esports/home/`. No API, no terms or legal links found in the page. `robots.txt` disallows `/raw/`, `/summoner/` and others (checked 2026-11-18). Getting data would mean scraping a site that grants no license. Not allowed under our rules.

### 2.5 Stats sites and MCP servers

- **OP.GG MCP**: `https://github.com/opgginc/opgg-mcp` (checked 2026-11-18). Official server at `https://mcp-api.op.gg/mcp`. Tools include `lol_get_champion_analysis`, `lol_list_lane_meta_champions`, `lol_get_lane_matchup_guide`, `lol_get_summoner_profile`, `lol_list_summoner_matches`, `lol_get_pro_player_riot_id`, `lol_esports_list_schedules`. The repo is MIT, which covers the **code** only. No data license, rate limits or MCP-specific terms are published. The OP.GG Terms (`https://op.gg/policies/agreement`, "Last Updated: 2026-09-14", checked 2026-11-18) grant access "for your personal, non-commercial use". They also say "No Site Content may be modified, copied, distributed, framed, reproduced, republished", forbid "scraping or data mining", and forbid using "automated scripts to collect information from … the Services". → **❓.** A developer asking an AI assistant interactively is probably what it was built for. Ingesting it into our backend, storing it, or showing it in a public demo needs written permission from OP.GG.
- **MetaBot.GG MCP**: `https://metabot.gg/en/ai` (checked 2026-11-18). "It is public and read-only, so no API key, account or auth flow is required." Limit: "about 60 requests/minute per IP, plus an overall ceiling across all callers". Attribution: "you must credit MetaBot.GG with a dofollow link to the specific metabot.gg page the data came from." The page doesn't cover caching, commercial use, or pro data. The full ToS was not reviewed (UNVERIFIED). → **❓.** It might work as a current-patch fallback if the Riot API sampler comes up short, but read the ToS first.
- **u.gg, Mobalytics, League of Graphs, DPM.LOL, METAsrc**: terms pages returned HTTP 403 to automated fetches. Blitz `/terms` returned 404. Lolalytics has no terms page (`/terms/` 404, only `/info/privacy`). Its `robots.txt` reserves rights under EU DSM Art. 4 via "content signals". All checked 2026-11-18. No public API found for any of them. → **❌**, as the plan already says: don't scrape. Coaches may look at them manually.
- **trackingthepros.com / lolpros.gg**: no API. TTP's `/terms` renders "Page Not Found" (checked 2026-11-18). LoLPros terms ("Last updated: September 06, 2018", `https://lolpros.gg/about/terms-of-service`, checked 2026-11-18) have no data-reuse clause. → **❌ for automated use.** A coach may look up their own players' accounts there by hand.

### 2.6 Kaggle / Hugging Face / research datasets
- **PandaSkill** (`https://ieee-dataport.org/documents/league-legends-esports-player-game-data-2019-2024`, checked 2026-11-18): by PandaScore. "37,388 matches, 392 tournaments, 4,927 unique players", 2019-09-15 → 2024-09-15, CC BY 4.0. "This dataset requires an IEEE DataPort Subscription to access." Whether a free account is enough is UNVERIFIED. Useful only for long-term priors such as player champion history before 2025. Low priority.
- `AngryBacteria/league_of_legends` (Apache-2.0, 13k soloq matches, 2025-01) and `renecotyfanboy/leagueData` (MIT, EUW soloq 2024-04). Hugging Face API checked 2026-11-18. They're stale, and the uploaders' licenses can't override Riot's API terms. Not useful.
- Kaggle results were older re-uploads of OE or Riot API data (search checked 2026-11-18). Skip them.

### 2.7 CommunityDragon, ⚠️
- `https://raw.communitydragon.org/` and `https://www.communitydragon.org/` (checked 2026-11-18): no license, terms or rate limits. Only "CommunityDragon was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project."
- Riot Legal Jibber Jabber (`https://www.riotgames.com/en/legal`, "August 2018", checked 2026-11-18): a limited license "strictly for noncommercial … community use". It requires the disclaimer "[Project] was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project." It also says "We prohibit the use of our IP in games and apps." That clause is ambiguous for us: our app shows champion icons. Data Dragon is the officially supported way to do that under the Developer Portal policies.
- Use **Data Dragon** for champion data and icons. Use CDragon only for fields Data Dragon lacks. Cache it and don't hammer the server (it is donation-funded).

### 2.8 Riot / GRID official programs

- **Riot Games Open Access powered by GRID**, the most important new finding. `https://grid.gg/riot-open-access/` (checked 2026-11-18):
  - "Launching 12 November 2026". "Free for students, researchers, hobbyists and early-stage developers."
  - LoL Esports: "Central Data Feed · Series State API · Loopfeed".
  - "Non-commercial use: learning and experimentation". "No betting or gambling use". "Riot Games Open Access data is delayed to protect game integrity."
  - "You declare your category and intended use when you register." Register at `https://riot.grid.gg/register`.
  - Inven Global (`https://www.invenglobal.com/articles/28744/…`, 2026-11-17, checked 2026-11-18) reports a 5-minute delay. The LoL Esports announcement (`https://lolesports.com/en-US/news/build-with-official-league-of-legends-esports-data`) is cited by search results as saying Worlds 2026 is the first event in the portal and giving 14 November as the start. The page is client-rendered, so I couldn't read it directly. The launch date is UNVERIFIED (sources say 12, 14 or 17 Nov).
  - **Terms UNVERIFIED.** `https://grid.gg/legal/terms-of-service/` is literally a "[PLACEHOLDER: Terms of Service - see spec §11]" page (checked 2026-11-18). The binding terms are presumably shown at sign-up. Historical depth (LCS 2025–26? LPL?) and rate limits are not published.
  - An older GRID help article (search snippet only, UNVERIFIED) said Open Access excluded the File Download API and Series Events API.
  - → **❓.** It's worth signing up today to read the terms. It may add Worlds 2026 (and maybe more) as official GRID data in the **same format our ingest already parses**. Treat it as GRID data: never commit it, and confirm that a public non-commercial hackathon demo counts as "learning and experimentation".
- **GRID Data Portal for pro teams** (`https://grid.gg/open-access/`, checked 2026-11-18): "Professional League of Legends and VALORANT teams can enquire about free access to official Riot Games esports data" (portal@grid.gg). Cloud9 already has this, which is what the hackathon data comes from. Not for us directly.
- **Riot Developer Portal**: policies quoted in §4. The Tournament API is for generating tournament codes and is not useful here (`https://developer.riotgames.com/docs/lol`, checked 2026-11-18).

### 2.9 Players' own champion preferences
- Nothing structured and reliable exists. Leaguepedia `Players.FavChamps` (free text, sparse) and the `ExternalContent` table (links to interviews and articles, filterable by player and team) are the closest (Cargo field lists checked 2026-11-18).
- Model this as **coach input**: a per-player YAML/UI form with comfort tiers (`main / playable / practising / won't play`), plus a "source: coach" tag. It's legally clean, more accurate, and exactly what a coaching staff would maintain. `ExternalContent` links can be shown as "further reading" if we want.

---

## 3. Recommendations ranked by value / effort

| Rank | Action | Value | Effort | Status |
|---|---|---|---|---|
| 1 | **gptilt/lol-esports-matches** Parquet → team-level draft history for LPL, MSI, First Stand, Worlds, LCS/LTA history, ERLs. Fearless usage per series. | High | Very low (one download, no API) | ⚠️ CC BY-SA attribution |
| 2 | **Leaguepedia Cargo API** (`ScoreboardPlayers`, `PicksAndBansS7`, `MatchScheduleGame`, `TournamentRosters`, `PlayerRedirects`) → player-level champion pools for opponents, exact pick-ban order, Worlds 2026 knockouts, rosters | High | Medium (bot password, paging, name/patch mapping, dedupe with GRID) | ⚠️ API only, attribution, no ML training, separate files |
| 3 | **Riot API** high-elo sampler for current-patch champion stats and matchups (already planned) | High (GRID ends at 16.17, the live patch is 16.23) | Medium | ⚠️ Riot policies + boilerplate |
| 4 | **Riot Open Access (GRID)**: sign up, read the terms, check whether Worlds 2026 and other leagues are available | Potentially high (official, same format) | Low to check | ❓ |
| 5 | **Oracle's Elixir** 2026 CSV as a cross-check and to fill fields Leaguepedia lacks (gold diffs at 10/15, objectives) | Medium | Low | ⚠️ local only. Ask Tim before committing aggregates |
| 6 | Coach-entered champion comfort and Riot IDs (own team) | Medium | Low | ✅ for coach input. Soloq pull ❓ (see §4) |
| 7 | Data Dragon (+ CDragon gaps) | Required | Low | ✅ / ⚠️ |
| — | lolesports API, gol.gg, u.gg/OP.GG/lolalytics/Mobalytics/LoG/DPM/METAsrc/Blitz scraping, TTP/LoLPros scraping | — | — | ❌ |

**Dedupe note:** Leaguepedia and GRID overlap on LCK, LEC, LTA 2025 and LCS 2026. Keep GRID as the source of truth for those. Use Leaguepedia only where GRID has no data, and match games by date + teams + game number (`MatchScheduleGame.RiotPlatformGameId` may help, but how it maps to GRID IDs is UNVERIFIED).

---

## 4. GRID clause 3(e) and pro solo-queue accounts

### 4.1 The clause
From `../stl-hackathon-2026-grid-starter/LICENSE.md` (read locally 2026-11-18):
> "(e) Combine the Data with other data in order to identify, profile or contact any individual, or use the Data in a way that harasses, defames or harms any player, team or other person."

Related: §2 limits use to "solely to build, test, demonstrate, submit and have judged a Project". §3(d) restricts ML models made available outside the Project. §9 says "For any use not permitted here, you must obtain prior written permission from Cloud9 through the Hackathon's official organizer channels."

### 4.2 Assessment
- **GRID-only player champion pools** (player X played champion Y in pro games) are the core use the hackathon invites ("draft-tendency analysis"). I consider that in scope.
- **Joining GRID player data with soloq accounts.** We would map a pro's handle to Riot IDs, pull their ranked games through the Riot API, and show both side by side as one player's champion pool. That is "combining the Data with other data" to build a richer picture of a named individual. A literal reading of "profile" covers it. The clause probably targets privacy harms (de-anonymising, contacting, tracking), but we can't rule out the literal reading, and a breach can mean disqualification (§9). **Risk: medium. Ask first.**
- **Joining GRID with Leaguepedia pro-match data at player level** (e.g. adding a player's 2024 or LPL games) is the same kind of data (public pro games). Low risk, but it's still "combining with other data" about individuals. Include it in the question so we have it in writing.
- **Riot policy layer** (independent of GRID):
  - "Products cannot de-anonymize players who cannot reasonably be identified from visible information." (General Policies, `https://developer.riotgames.com/policies/general`, checked 2026-11-18)
  - "Products cannot identify or analyze players who are deliberately hidden by the game." (`https://developer.riotgames.com/docs/lol`, checked 2026-11-18)
  
  Pros' soloq accounts listed by third parties (Leaguepedia `SoloqueueIds`, TTP, LoLPros) are often smurfs the player never announced. Auto-mapping them is close to de-anonymising, and the lists are stale, untagged free text. **Don't auto-map.**
- OP.GG's `lol_get_pro_player_riot_id` exists, but OP.GG's terms block ingestion (§2.5). Don't use it.

### 4.3 Safe design (default until organizers answer)
1. **Two separate stores, no join on person in the pipeline.** `pro_*` tables (GRID + Leaguepedia, keyed by pro handle) and `soloq_*` tables (Riot API, keyed by PUUID, never stored next to GRID player IDs).
2. **Champion-level soloq only by default.** Current-patch meta (champion × role × patch) from anonymous high-elo samples. No individual is profiled. ✅
3. **Player soloq pools behind a feature flag (`PLAYER_SOLOQ=false`)**, off in the hosted demo until approved. If approved:
   - Only for **Cloud9's own roster**, with Riot IDs entered by the coach in a gitignored `config/players.yaml` (ship a `players.example.yaml` with placeholders). Ideally the players confirm the accounts themselves.
   - Never auto-fill from Leaguepedia/TTP/LoLPros/OP.GG. Never scout opponents' soloq accounts.
   - Store only aggregates per champion (games, wins, last-played patch). No match lists, timestamps or LP, so no activity tracking.
   - Show it as a separate "Solo queue (Riot API, coach-provided accounts)" panel, labelled by source. Don't blend it into a GRID-derived score unless the organizers say so.
   - Never commit Riot IDs or PUUIDs. Delete on request (Riot API ToU mention GDPR deletion requests, `https://developer.riotgames.com/terms`, checked 2026-11-18).
4. **Coach comfort input** (§2.9) covers most of the need with zero licensing risk.

### 4.4 Question for the organizers (Cloud9 Discord / support@devpost.com)

> **Subject: GRID data license §3(e): combining with public pro stats and solo-queue data**
>
> Hi! We're building "fele", a coach-facing draft-prep and Fearless series planner (MIT, public repo, password-protected non-commercial demo; no GRID data or derived extracts are committed). Before we build two features, we'd like to confirm they're OK under §3(e) of the GRID data license ("Combine the Data with other data in order to identify, profile or contact any individual"):
>
> 1. **Public pro match history.** Can we show a pro player's champion pool that combines GRID games with public pro-match records from Leaguepedia (CC BY-SA), e.g. their LPL/MSI/Worlds or pre-2025 games? We'd keep the two sources in separate tables and label them in the UI.
> 2. **Solo-queue champion pools.** Can we show, next to a player's GRID-derived pro champion pool, aggregate ranked solo-queue stats (champion, games, win rate on the current patch) pulled from the official Riot API? Riot IDs would be **entered manually by the coach**, only for Cloud9's own roster, never auto-discovered, never committed, and with no match lists or activity timestamps stored. If this isn't allowed, is it OK to show soloq pools as a fully separate view that isn't joined with GRID data?
> 3. **Riot Open Access (GRID).** Can we also use data from the new Riot Games Open Access program (e.g. Worlds 2026) in the same project and demo, under its own terms?
> 4. **Hosted demo.** Can our password-protected hosted demo serve aggregates derived from the GRID data (no raw events) to judges, as described in §4(b)?
>
> If any of these need prior written permission under §9, please tell us who can grant it. Thanks!

---

## 5. Sources (all checked 2026-11-18)
- Leaguepedia API help: https://lol.fandom.com/wiki/Help:Leaguepedia_API (via `api.php?action=parse`)
- Leaguepedia ratelimit note: https://lol.fandom.com/wiki/User:Arbolitoloco/Avoiding_cargo_ratelimits
- Leaguepedia copyrights: https://lol.fandom.com/wiki/Leaguepedia:Copyrights
- Cargo tables / fields / queries: https://lol.fandom.com/api.php (`cargotables`, `cargofields`, `cargoquery`)
- Fandom Terms of Use: https://www.fandom.com/terms-of-use (Wayback 20261115004908)
- Fandom Licensing: https://www.fandom.com/licensing (Wayback 20261117235850)
- MediaWiki API etiquette: https://www.mediawiki.org/wiki/API:Etiquette
- mwrogue: https://github.com/RheingoldRiver/mwrogue
- GPTilt dataset: https://huggingface.co/datasets/gptilt/lol-esports-matches
- Oracle's Elixir downloads: https://oracleselixir.com/tools/downloads (+ JS bundle text), Drive: https://drive.google.com/drive/folders/1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH
- Riot General Policies: https://developer.riotgames.com/policies/general
- Riot LoL docs/policies: https://developer.riotgames.com/docs/lol
- Riot API Terms: https://developer.riotgames.com/terms
- Riot Legal Jibber Jabber: https://www.riotgames.com/en/legal
- Riot esports data: https://riotesportsdata.com/en-us/league-of-legends/
- LoL Esports Data Portal dev diary: https://lolesports.com/en-US/news/dev-diary-introducing-the-new-lol-esports-data-portal
- Riot Open Access (GRID): https://grid.gg/riot-open-access/, https://www.invenglobal.com/articles/28744/riot-games-and-grid-open-official-lol-and-valorant-esports-data-to-the-community-for-free
- GRID open access / data portal: https://grid.gg/open-access/ · GRID ToS (placeholder): https://grid.gg/legal/terms-of-service/
- OP.GG MCP: https://github.com/opgginc/opgg-mcp · OP.GG terms: https://op.gg/policies/agreement
- MetaBot.GG MCP: https://metabot.gg/en/ai
- LoLPros terms: https://lolpros.gg/about/terms-of-service · TrackingThePros: https://www.trackingthepros.com/
- CommunityDragon: https://www.communitydragon.org/, https://raw.communitydragon.org/
- PandaSkill dataset: https://ieee-dataport.org/documents/league-legends-esports-player-game-data-2019-2024
- PandaScore pricing: https://www.pandascore.co/pricing
