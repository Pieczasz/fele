# Riot platform research: policies, keys, endpoints, data sources

All sources were checked on 2026-11-18. A claim marked **UNVERIFIED** has no primary source behind it. Quotes are verbatim from the page as served on that date.

Abbreviations: GP = General Policies (https://developer.riotgames.com/policies/general, "LAST UPDATED: MAY 29, 2025"). LOLDOC = LoL docs and LoL Developer API Policy (https://developer.riotgames.com/docs/lol). TERMS = API Terms (https://developer.riotgames.com/terms, "LAST UPDATED: DECEMBER 9, 2013"). PORTAL = https://developer.riotgames.com/docs/portal. FAQ = https://developer.riotgames.com/docs/faqs. REF-x = https://developer.riotgames.com/api-details/x, the JSON behind the API reference at https://developer.riotgames.com/apis.

## 1. Legal boilerplate (must be "readily visible")

There are two slightly different official versions:

- **GP** (checked 2026-11-18):
  > [Your product] isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
- **LOLDOC**, LoL Developer API Policy (checked 2026-11-18). The source ends without a final period:
  > [Your Product Name] is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc

**Use in the app:** put the LoL-doc version in the site footer and the README.

> fele is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

- The Legal Jibber Jabber fan policy (https://www.riotgames.com/en/legal, "Last Updated: August 2018", checked 2026-11-18) has its own notice for fan projects. Adding it to the README and the video description costs nothing:
  > [The title of your Project] was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.

## 2. Policy rules that shape the product

Policy rules (GP + LOLDOC, checked 2026-11-18):

| Rule (verbatim or close) | Source | Design impact |
|---|---|---|
| "No apps serving as a "data broker" between our API and another third-party company." | LOLDOC | Ship a UI tool only. Offer no bulk export, raw API proxy or data feed to Cloud9 or anyone else. Risk to note: the tool is built for a company (C9). It shows derived insights, so it is not resale of data, but this is our interpretation and is **UNVERIFIED** with Riot. |
| "Products should increase, and not decrease the diversity of game decisions…" / "should not remove game decisions, but may highlight decisions that are important and give multiple choices" | GP, LOLDOC | Present ranked options and trade-offs, never "auto-draft: pick X". |
| Unapproved use case: "Apps that dictate player decisions." | LOLDOC | Same as the row above: show several options and why each fits, not a single answer. |
| "Products cannot create alternatives for official skill ranking systems… Prohibited alternatives include MMR or ELO calculators." | GP, LOLDOC | No player MMR or Elo estimates and no custom player rating. Champion strength scores are fine (they rate champions, not players). Don't present a "player power score" either. |
| "Products cannot de-anonymize players who cannot reasonably be identified from visible information." | GP | Do **not** infer or link pro players' smurf or alt accounts. Only use Riot IDs that the coach types in by hand. Do not add an "accounts likely belonging to X" feature. |
| "Products cannot identify or analyze players who are deliberately hidden by the game." | LOLDOC (Game Integrity) | Revised 2026-11-21 (fele Live): champ select is read from the local League client only for the user and their party members; non-party allies show as "Ally", enemies are never analysed. Everything else uses finished-match data. See section 10. |
| "Products must not use or incorporate information not present in the game client that would give players a competitive edge…" and "Products may not provide any game-session-specific information that would be previously unknown to the player." | LOLDOC | Don't use spectator-v5 or live-game features. Our use is pre-match prep only. |
| "Products cannot display win rates for Augments or Arena Mode items." | LOLDOC | Not relevant (queue 420), but ignore the `playerAugment*` fields. |
| Custom-queue match history may not be shown publicly without opt-in | LOLDOC | Filter to `queue=420` only. |
| Approved production use cases include "Aggregate player stats (no specific players)" and "Showing (self) player stats". | LOLDOC | Per-champion aggregate strength is a clearly approved pattern. **UNVERIFIED:** whether per-player soloQ pools for *other* named players (pros) is approved. It is not listed as approved or as unapproved. Keep it optional and coach-entered, and label it. |
| "All products must be registered in, and audited by Riot Games through the Developer Portal" and "Any new features or changes… must be audited" | GP | Register the product (personal key route, see section 4) even for the hackathon. |
| Use Data Dragon and the Press Kit for assets. Use of logos and trademarks "must be limited to those cases where such use is inevitable" | GP | Use Data Dragon champion icons and no Riot or LoL logos. |
| No betting or gambling. Monetizing needs Approved/Acknowledged status, a free tier, and transformative content | GP | N/A (free, MIT). Never add a betting or odds angle. |
| No crypto or blockchain. Must not "closely resemble Riot's games or products" | GP | Don't style the app like the League client. |
| Keys: "Do not include your API key in your code…", use HTTPS, "one product per key", and share only within an org via a Developer Portal "group" | GP, LOLDOC | Keep the key in the `.env` file, which is gitignored, and make all calls server-side. Never call the API from the browser. Add teammates through a portal group. |

API Terms (TERMS, checked 2026-11-18):

- **Key confidentiality:** "You may not sell, transfer, sublicense or otherwise disclose Your API Key(s) to any other party… You agree to notify Riot immediately if You believe that Your API Key(s) have been compromised."
- **Licensed use:** The license allows building Applications "for the purpose of displaying such Game Information to end users". It is "non-sublicensable, non-transferable, revocable".
- **Payment:** Charging for access requires "Riot's prior written approval". This does not apply to us.
- **Prohibited:** "Distributing, selling, transferring… the Riot Games API… and/or access thereto to any third party". This is consistent with the data-broker rule.
- **Prohibited:** "collect any additional information about the Game or Game users that is not provided Game Information". Do not scrape other sources and join them to Riot player data.
- **Prohibited:** displaying "or imply any kind of product or political endorsement, whether by Riot or any Game player". Don't imply that Riot or individual pros endorse the tool.
- **Retention and caching:** The Terms set **no explicit caching or retention period**. The only deletion duty is on termination: "delete all of the Game Information in Your possession".
- **GDPR:** "When Riot Games receives a request from an end user to delete their personal data, we will be passing the request to all active developers by sharing a list of identifiers (e.g. accountId)". We must be able to delete by identifier, so store PUUIDs in one place where they can be purged.
- **Open-source code:** The Terms do not mention it. Nothing forbids an MIT repo of our own code. Riot owns "all output… of the Riot Games API, and… derivatives". **Do not commit raw match dumps or player data** to the public repo. Commit code and, at most, anonymized champion-level aggregates. Whether aggregates are allowed is **UNVERIFIED**, because the Terms are silent on them.
- **Attribution:** The Survival clause names an "Attribution" section, but no such section exists on the page. **UNVERIFIED** beyond the boilerplate.

## 3. Riot IP: champion names, icons, demo video

- **GP:** "Use the following assets in the development and marketing of your product: Data Dragon, Press Kit…". Data Dragon icons and names are allowed in the UI *and in marketing*, which covers the YouTube demo (https://developer.riotgames.com/policies/general, checked 2026-11-18).
- **Legal Jibber Jabber:** Fan projects must be free and non-commercial. A Project that "involves a business or legal entity" needs a license, **except** "Exception 3", for API projects that "comply with our API Terms and Policies and use a valid API key". Logos and trademarks may not be used "anywhere in your Project or on any website, advertising material, video" without a written license. Re-uploading or lightly commenting on esports VODs is not allowed (https://www.riotgames.com/en/legal, checked 2026-11-18).
  - **Demo video:** use only our own UI with Data Dragon icons. Use no LoL logo and no esports broadcast footage.
- **CommunityDragon** (https://communitydragon.org, checked 2026-11-18) is unofficial. It states "CommunityDragon was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project." It is active: the homepage reports about 737M requests in 30 days, and `raw.communitydragon.org/latest/` returned HTTP 200. It is not covered by GP's list of approved assets, so prefer Data Dragon. CDragon's own terms and rate limits are **UNVERIFIED**.

## 4. API keys and rate limits

From PORTAL (checked 2026-11-18):

| Key | Purpose (quoted) | Rate limit | Notes |
|---|---|---|---|
| Development | "not meant for public consumption… They also deactivate every 24 hours." | Not stated in docs. **Observed: 20/1s and 100/120s** (see section 9) | "You may not maintain a public product with a development API key." |
| Personal | "intended for just the developer or a small private community… registered without the verification process, but won't be approved for rate limit increases." Standard APIs only, no Tournaments API. | "20 requests every 1 second", "100 requests every 2 minutes" | "You may not run your application for public consumption using a personal key… public consumption includes open alpha/beta tests." Needs a "detailed description of the product". |
| Production | "intended for large communities or the Internet as a whole… Typically requires a working prototype" | "500 requests every 10 seconds", "30,000 requests every 10 minutes" | Approval time "can vary". |

- All limits are **per region (platform/cluster)**: "rate limits are enforced per region". KR, EUW and NA can be sampled in parallel, each with its own budget.
- There are three kinds of limit: application, method and service. On a 429, "halt future API calls for the duration… indicated by the Retry-After header". Violating this may get access disabled. A 429 without an `X-Rate-Limit-Type` header comes from the underlying service, not the edge.
- **Review time (FAQ):** "Applications are typically reviewed weekly for the previous week… sometimes the review process can take up to three weeks." The FAQ also says registered apps need a website listing what the product does, plus its ToS and Privacy Policy. This is stated in the context of app verification; whether it applies to personal keys is **UNVERIFIED**.
- **FAQ:** "only one product/website per API key", and you "may NOT have multiple applications to bypass rate limits."
- **Recommendation for us:** A password-gated demo for Cloud9 staff fits "small private community", so a **personal key** is the right tier. Apply now: approval may take one to three weeks, so the hackathon will probably run on the 24h dev key, which must be regenerated daily. Don't apply for production, since our app is not for "the Internet as a whole". The demo must not become public while it runs on a dev or personal key; keep the password gate. Keep a cached snapshot so the demo still works if the key expires.

## 5. Endpoints and routing

Sources: REF-* and LOLDOC, checked 2026-11-18.

- **Platform to regional routing (REF match-v5):** "The AMERICAS routing value serves NA, BR, LAN and LAS. The ASIA routing value serves KR and JP. The EUROPE routing value serves EUNE, EUW, ME1, TR and RU. The SEA routing value serves OCE, SG2, TW2 and VN2." This gives kr → asia, euw1 → europe, na1 → americas.
- **account-v1 (REF):** "There are three routing values for account-v1; americas, asia, and europe. You can query for any account in any region. We recommend using the nearest cluster." Endpoints:
  - `GET /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}` gives the PUUID.
  - `GET /riot/account/v1/accounts/by-puuid/{puuid}`.
  - `GET /riot/account/v1/region/by-game/{game}/by-puuid/{puuid}` gives the active region for lol/tft. Use it to find a pro's home platform.
  - The reference also lists "- ESPORTS" variants of by-riot-id, by-puuid and me. Their host and access rules are **UNVERIFIED**.
- **summoner-v4 (REF):** Only `by-puuid/{encryptedPUUID}` and `me` remain. `SummonerDTO` now has only `profileIconId, revisionDate, puuid, summonerLevel`. The `id`/`accountId` fields and the by-name, by-account and by-summonerId routes are gone from the reference. LOLDOC still contains 2023 migration text that mentions summonerID; that text is stale.
- **league-v4 (REF):** The endpoints are
  - `challengerleagues|grandmasterleagues|masterleagues/by-queue/{queue}`
  - `entries/by-puuid/{encryptedPUUID}`
  - `entries/{queue}/{tier}/{division}`

  The documented `LeagueItemDTO` has `puuid` and **no `summonerId`**. The smoke test confirms this (section 9).
- **league-exp-v4 (REF):** `GET /lol/league-exp/v4/entries/{queue}/{tier}/{division}`. The response DTO was not captured in this pass.
- **match-v5 (REF), regional:**
  - `GET /lol/match/v5/matches/by-puuid/{puuid}/ids` takes `startTime` and `endTime` (epoch **seconds**; "matchlist started storing timestamps on June 16th, 2021"), `queue`, `type` (ranked/normal/tourney/tutorial), `start` (default 0) and `count` ("Defaults to 20. Valid values: 0 to 100").
  - `GET /lol/match/v5/matches/{matchId}`
  - `GET /lol/match/v5/matches/{matchId}/timeline`
  - `GET /lol/match/v5/matches/replays`, which needs an RSO token.
- **champion-mastery-v4 (REF, platform):** Endpoints are all `by-puuid`: list, by-champion, `/top`, and `scores/by-puuid`.
- **spectator-v5 (REF, platform):** `GET /lol/spectator/v5/active-games/by-summoner/{encryptedPUUID}` (despite the path name, it takes a PUUID). Under the policy rows in section 2, **do not use it**.
- **lol-status-v4:** `GET /lol/status/v4/platform-data`. Confirmed working (section 9).
- **Deprecation policy (PORTAL):** "we aim to support both old and new versions of the API for 60 days".

## 6. Professional / esports data

- **Riot API (public keys):** Riot's API documentation describes no endpoint for professional stage games. Whether tournament-realm pro matches can be reached through match-v5 with our key is **UNVERIFIED** (very likely not). The Tournament API is for organizing tournaments. Personal keys cannot request it (PORTAL).
- **GRID is Riot's exclusive official esports data distributor.** riotesportsdata.com says GRID "distributes live data directly from Riot Games". On that page, live data, fixtures and A/V feeds "are only available for commercial purposes through GRID", and LCK data is "for media purposes only" (https://riotesportsdata.com/league-of-legends, checked 2026-11-18). The partnership was announced in December 2023 (https://grid.gg/riot-games-and-grid-announce-exclusive-global-esports-data-partnership/, checked 2026-11-18).
- **NEW: Riot Games Open Access, powered by GRID.** It is free and non-commercial, aimed at "Students, academics, hobbyist developers and early-stage projects". It offers the LoL Central Data Feed, the Series State API and Loopfeed. You register at riot.grid.gg, declare your intended use, confirm no betting use, then generate a key. Live data is delayed.
  - Sources: https://grid.gg/riot-open-access/ (lists the launch date as 12 Nov 2026), https://www.invenglobal.com/articles/28744/riot-games-and-grid-open-official-lol-and-valorant-esports-data-to-the-community-for-free (says launch was 17 Nov 2026, with a 5-minute live delay, and Worlds 2026 as the first event per a search summary), and https://lolesports.com/news/build-with-official-league-of-legends-esports-data (the page body renders client-side and could not be read; a search snippet says "Starting November 14"). All checked 2026-11-18.
  - The exact launch date, historical coverage, and draft/pick-ban fields are **UNVERIFIED**.
  - Eligibility of an open-source hackathon tool built *for* Cloud9 is **UNVERIFIED**: "Commercial use: No. Open Access is for learning and experimentation."
- **GRID Data Portal for pro teams:** "Professional League of Legends and VALORANT teams can enquire about free access to official Riot Games esports data" by emailing portal@grid.gg (https://grid.gg/open-access/, checked 2026-11-18). Cloud9 may already have access. Ask the C9 staff.
- **Unofficial lolesports API** (esports-api.lolesports.com/persisted/gw/*, feed.lolesports.com/livestats/*):
  - It is undocumented by Riot. Only community docs exist, such as https://vickz84259.github.io/lolesports-api-docs/, which returned HTTP 200 on 2026-11-18.
  - `getLeagues` without the site's embedded web key returned **HTTP 403** on 2026-11-18.
  - The Riot API Terms and Policies do not cover it, and Riot grants no license to use it, so permission is **UNVERIFIED** and should be treated as not allowed. GP also says "Products should use supported services from Riot Games for data ingestion".
  - Recommendation: don't depend on it. Use manual coach input, the GRID Open Access or Data Portal route, or Leaguepedia, which is a separate question.

## 7. Data Dragon

Source: LOLDOC, checked 2026-11-18. Files were also fetched directly on that date.

- **Versions:** https://ddragon.leagueoflegends.com/api/versions.json. Latest = `16.23.1`, then `16.22.1`, `16.21.1`. "you should always use the most recent Data Dragon version for a given patch". Data Dragon is updated by hand and "not always updated immediately after a patch".
- **Region realms:** https://ddragon.leagueoflegends.com/realms/{na,euw,kr}.json. All three report `v` = `16.23.1`.
- **Champion list:** `https://ddragon.leagueoflegends.com/cdn/16.23.1/data/en_US/champion.json`.
- **Per-champion files:** `…/data/en_US/champion/Aatrox.json`.
- **`championFull.json`:** HTTP 200, about 2.2 MB. It is not mentioned in the docs page.
- **`item.json`:** HTTP 200.
- **Images:**
  - Square: `…/cdn/16.23.1/img/champion/Aatrox.png` (HTTP 200).
  - Splash: `…/cdn/img/champion/splash/Aatrox_0.jpg`.
  - Loading: `…/cdn/img/champion/loading/Aatrox_0.jpg`.
- **Mode-specific variants** (e.g. `Jade_Ahri`) live under `data/{LOCALE}/mode/{mode}/`. Filter to the base `champion.json`.
- **Patch mapping:** match `info.gameVersion` (e.g. `16.22.834.8910`) by `major.minor` against Data Dragon `16.22.1`.

## 8. Privacy, hidden players, smurfs

- **No "match-history opt-out" rule for ranked:** No general opt-out rule for ranked match history was found in GP, LOLDOC, TERMS or FAQ. The only opt-in rule covers the **custom match queue** (LOLDOC). Any other opt-out mechanism is **UNVERIFIED**.
- **Hidden players:** "Products cannot identify or analyze players who are deliberately hidden by the game" (LOLDOC). The relevant context is anonymized ranked champ select and in-game name hiding. We use only post-game match-v5 data, which does return Riot IDs (section 9).
- **Smurfs and alts:** The GP de-anonymization rule applies. Never infer that an account belongs to a pro. Accept only coach-entered Riot IDs, and show them only to the authenticated C9 staff.
- **GDPR deletions:** Riot forwards deletion identifiers (TERMS). Keep the stored player data minimal (PUUID to champion counts) and purgeable. Don't commit player data to git.

## 9. Smoke test results (2026-11-18)

The key was loaded from `.env` into the shell environment and was never printed. Five Riot API requests were made, all returning HTTP 200. No player identifiers are recorded here, and the temporary response files were deleted.

| # | Request | Status | X-App-Rate-Limit | X-Method-Rate-Limit |
|---|---|---|---|---|
| 1 | `euw1` `/lol/status/v4/platform-data` | 200 | `100:120,20:1` | `20000:10,1200000:600` |
| 2 | `kr` `/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5` | 200 | `100:120,20:1` | `500:600,30:10` |
| 3 | `asia` `/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&count=5` | 200 | `100:120,20:1` | `2000:10` |
| 4 | `asia` `/lol/match/v5/matches/{matchId}` | 200 | `100:120,20:1` | `2000:10` |
| 5 | `asia` `/lol/match/v5/matches/{matchId}/timeline` | 200 | `100:120,20:1` | `2000:10` |

**App limit**

- **Effective app limit:** 20 requests/1s and 100 requests/120s, per region. This matches the documented personal-key limits.
- **Method limits:**
  - challenger league: 30/10s and 500/10min.
  - match-v5: 2000/10s.
  - status: 20000/10s.
- **The app limit was shared with other users of the key.** On the ASIA cluster, `X-App-Rate-Limit-Count` read `41:120`, then `43:120`, then `87:120` across my three requests. Something else was using the same key on ASIA at the same time. The 100/2min budget is **shared by everyone using this key**, so the crawler must read the `-Count` headers and back off rather than assume a fresh budget.

**Response details**

- **lol-status:**
  - Top-level keys: `id, incidents, locales, maintenances, name`.
  - 1 incident and 0 maintenances.
- **KR challenger:**
  - Top-level keys: `entries, queue, tier`. `leagueId` and `name` are documented but were not returned.
  - **300 entries.**
  - Entry fields: `freshBlood, hotStreak, inactive, leaguePoints, losses, puuid, rank, veteran, wins`.
  - **`puuid` is present in all entries, and `summonerId` in none.**
- **Match ids:** 5 returned, prefix `KR_`.
- **Match detail:**
  - `metadata` keys: `dataVersion` (= 2), `matchId`, `participants` (10).
  - `info` keys: `endOfGameResult, gameCreation, gameDuration, gameEndTimestamp, gameId, gameMode, gameName, gameStartTimestamp, gameType, gameVersion, mapId, participants, platformId, queueId, teams, tournamentCode`.
  - Game data:
    - `gameVersion` = `16.22.834.8910`. The match was played on 2026-11-10, so the player's latest soloQ game was still on patch 16.22, while Data Dragon and realms are on 16.23.1.
    - `queueId` = 420, `platformId` = KR.
    - 10 participants, `endOfGameResult` = `GameComplete`.
  - **Participant fields (156 per participant):** these include `championId, championName, teamPosition, individualPosition, lane, role, win, puuid, riotIdGameName, riotIdTagline, summonerId, summonerName, teamId, kills, deaths, assists, goldEarned, totalMinionsKilled, visionScore, item0-6, perks, summoner1Id, summoner2Id, challenges, timePlayed, gameEndedInEarlySurrender, wasAfk, positionAssignedByMatchmaking, selectedRolePreferences, playerAugment1-6, PlayerScore0-11`.
    - `teamPosition` values seen: `TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY`.
    - `riotIdGameName` was non-empty for all 10 participants.
    - `summonerName` was empty for all 10. `summonerId` is still populated in match-v5 participants.
  - **Teams:** keys `bans, objectives, teamId, win`. Five bans per team, each with fields `championId, pickTurn`.
- **Timeline:**
  - Size about 789 KB, with 32 frames at `frameInterval` = 60000 ms.
  - Event types: `BUILDING_KILL, CHAMPION_KILL, CHAMPION_SPECIAL_KILL, DRAGON_SOUL_GIVEN, ELITE_MONSTER_KILL, GAME_END, ITEM_DESTROYED, ITEM_PURCHASED, ITEM_SOLD, ITEM_UNDO, LEVEL_UP, OBJECTIVE_BOUNTY_FINISH, OBJECTIVE_BOUNTY_PRESTART, PAUSE_END, SKILL_LEVEL_UP, TURRET_PLATE_DESTROYED, WARD_KILL, WARD_PLACED`.
  - Timelines are large. Skip them for strength sampling.

**Implications for sampling**

- **Budget:** about 100 requests per 2 min per region gives about 3,000 requests per hour per region, or about 9,000 per hour across KR, EUW and NA, minus whatever other key users consume.
- **Filtering to the current patch:** filter ids with `startTime` set to the patch release epoch (in seconds) and `queue=420`. Then keep only matches whose `gameVersion` starts with `16.23.`.
- **Deduplication:** high-elo players share games, so deduplicate match ids across players.

## 10. League Client API (LCU), champ select (checked 2026-11-21)

- Riot: the League Client API "is not officially supported for use with third party applications"; no promises on
  documentation, uptime or notice of changes. Developers note LCU use on their Developer Portal product
  (https://developer.riotgames.com/docs/lol, League Client APIs section).
- Champ select anonymity (since patch 12.22): "Apps that reveal player names or stats in Champ Select will be asked to
  remove this feature immediately. This specifically applies only to Ranked Solo/Duo" (Riot DevRel, quoted at
  https://devtrackers.gg/leagueoflegends/p/749a443a-apps-that-reveal-player-names-or-stats-in-champ-select-need-to-remove-these-informations-starting-patch-12-22).
  Secondary summaries (Overwolf compliance guides) say party members are exempt.
- Recommendations must offer choices: products "may highlight decisions that are important and give multiple choices",
  and "Apps that dictate player decisions" are not approved (developer.riotgames.com, Game Integrity).
- A player's own match history is an approved use case ("Training tools that allow players to view their own match
  histories and aggregate stats").
- Since 2026-10-06 Riot blocks memory reading by unknown apps; LCU and official APIs were reported as unaffected
  (https://hexgate.app/blog/riot-third-party-apps/).

**fele's rule (stricter than Riot's):** identities and stats only for the local player and lobby party members, in every
queue; other allies are shown as "Ally · position"; enemies are never identified or analysed; the client is read only
from 127.0.0.1 by the user's own fele process; nothing from the client is stored except the user's own scrim log.

