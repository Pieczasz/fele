# Hackathon rules and 2026 pro LoL draft rules

Research for fele (Category 2, LoL). All facts checked **2026-11-18** unless marked otherwise.
Items marked **UNVERIFIED** could not be confirmed from a primary source.

> Access note: `cloud9.devpost.com` sits behind a Cloudflare check for browser-like clients, but plain HTTP requests returned the live pages on 2026-11-18. The old 2025–26 edition moved to `cloud9-25.devpost.com` (Devpost API: https://devpost.com/api/hackathons?search=cloud9). Search-engine snippets for `cloud9.devpost.com/rules` still show the **old** 2025–26 rules (4 categories, Feb 2026 dates), so ignore cached copies.

Short source keys used below:

| Key | URL |
|---|---|
| OV | https://cloud9.devpost.com/ |
| RULES | https://cloud9.devpost.com/rules |
| SPEC | https://cloud9.devpost.com/details/submission-specifics |
| DATES | https://cloud9.devpost.com/details/dates |
| RES | https://cloud9.devpost.com/resources |
| UPD | https://cloud9.devpost.com/updates |
| GRID | https://github.com/cloud9esports/stl-hackathon-2026-grid-starter (README.md, LICENSE.md, AGENTS.md) |
| LCSRB | 2026 LCS Rulebook v2.0 (Nov 2025): https://cdn.sanity.io/files/dsfx7636/news_live/360cac5b9c29e8891004ca92468a1e2489b2aa71.pdf |
| EWCRB | EWC 2026 LoL Rulebook: https://cdn.esportsworldcup.com/resources/uploads/EWC_26_League_of_Legends_Rulebook_a31ae07a83.pdf |

---

## PART A: Hackathon rules ("Cloud9 x JetBrains: Sky's The Limit Hackathon 2026", Devpost id 31571)

### A1. Dates (all Pacific Time)

| Milestone | When | Source |
|---|---|---|
| Registration and submission opens | Nov 17, 2026, 11:00 am PT | RULES §1, DATES |
| **Submission deadline** | **Jan 12, 2027, 11:00 am PT** (= 2:00 pm ET = 19:00 UTC) | RULES §1, DATES, OV |
| Judging | Jan 27, 2027, 3:00 pm PT to Feb 3, 2027, 3:00 pm PT | RULES §1, DATES |
| Winners announced | on or around Feb 8, 2027, 12:00 pm PT | RULES §1, DATES |

Drafts can be saved before the deadline. After the deadline the submission is frozen; only infringement, PII or inappropriate-content fixes are allowed (RULES §5).

### A2. JetBrains tool requirement
- You must build or **significantly update** a working project using **at least one JetBrains tool**: a JetBrains IDE (IntelliJ IDEA, PyCharm, WebStorm, Rider, DataGrip…), **JetBrains Air** (standalone app, IDE plugin, web or CLI), or **AI Coding Agent Junie**. Other editors may be used alongside. (RULES §4 Project Requirements; SPEC "Global Requirements")
- Stage One of judging is a pass/fail check that the project "reasonably applies the required JetBrains tools" (RULES §6).
- **Committing the `.idea`, `.junie` or `.air` folder is encouraged** "as supporting evidence" (RULES §4; OV).
- A project that existed before Nov 17 must be significantly updated (new features, major redesign or new data). Bug fixes and docs changes don't count (RULES §4 "New & Existing").
- Registrants get 1 All Products Pack code and 1 AI Ultimate code, while supplies last, by email within 5 business days. Student licenses aren't valid for activating them (RULES §4; organizer reply at https://cloud9.devpost.com/forum_topics/45910-where-do-i-get-the-free-access-from).

### A3. Repo requirements
- A public URL on **GitHub, GitLab or Bitbucket** with **all source code, assets and instructions** needed to run the project (RULES §4 Submission Requirements).
- It must be **public and open source**, with an open-source license file. SPEC/OV say `LICENSE`, `LICENSE.md` or `LICENSE.txt` at the root. The license must be "detectable and visible at the top of the repository page (in the About section)" (RULES §4; OV).
- **Don't commit the GRID data** (see A9).

### A4. Demo / hosting
- **If the project is a website, link a working demo.** Otherwise link a judge-accessible build, such as a repo with install steps, an itch.io page or a download link (RULES §4; OV).
- If the site is private, include login credentials in the testing instructions. The project must stay available **free of charge and without restriction until the Judging Period ends (Feb 3, 2027, 3:00 pm PT)** (RULES §4 "Testing").
- **Judges aren't required to test the project.** They may judge only from the text, images and video (RULES §4). So the video and the write-up carry the score.
- The project "must be capable of being successfully installed and running consistently… and must function as depicted in the video" (RULES §4 "Functionality").

### A5. Video
- **Less than 3 minutes.** Judges aren't required to watch beyond 3:00. OV/SPEC say "up to 3 minutes", so aim for 2:50 or less (RULES §4).
- Upload it to **YouTube**, public. Only YouTube is listed this year; the 2025 edition also allowed Vimeo and Facebook (RULES §4; SPEC).
- It must show the project working on its target device (RULES §4).
- **No third-party trademarks, copyrighted music or other material without permission** (RULES §4). Champion art and LoL logos count as Riot IP, so be careful (see A9).
- The "Presentation" criterion judges whether the video shows the project working **end-to-end** and whether the pitch explains the problem, who it is for, and why it matters (RULES §6).

### A6. Write-up requirements (submission form)
| Item | Source |
|---|---|
| **Text description**: features and functionality, plus which JetBrains tools you used and what each one did. GRID data is optional. | RULES §4; OV; SPEC ("Tooling Explanation") |
| **Methodology write-up**: a short explanation of your approach and how the tool solves the category's problem | RULES §4; SPEC |
| Choose **one** category | OV |
| English, or provide translations | RULES §4 "Language" |

### A7. Prizes and the bonus prize
Prize pool: $25,000. Category 2 Best: **$6,000**, a $100 Cloud9 Store gift card, 1-year JetBrains All Products Pack, a GDC 2027 Festival Pass, and flight and hotel to SF for one person (up to 5 nights). Category 2 Runner-up: $2,000, the gift card and the All Products Pack. Categories 1 and 3 have the same structure. (RULES §8; OV)

**Bonus: Best AI-Powered Workflow Story.** $1,000, a $100 gift card and an All Products Pack, one winner (RULES §8).
- To be eligible, provide a **direct URL** to one of these: a written doc, a blog post (Dev.to, Medium…), a LinkedIn post or X thread, a short video demo, or "a dedicated write-up file in your public repository (e.g., `AI_SHOWCASE.md`)". It must detail the team's experience using **JetBrains IDEs, Junie or JetBrains Air** (RULES §4).
- SPEC/OV frame it as either a short case study ("how AI or JetBrains tools helped your team build and solve key challenges") or a short social-style video ("how AI tools powered your build process").
- It's judged on "how clearly and completely they show the team's use of JetBrains IDEs, AI Coding Agent Junie or JetBrains Air to build the Project" (RULES §6).
- Only entries in Categories 1–3 qualify. **A project can win at most 1 category prize plus at most 1 bonus prize** (RULES §8).
- Implication: the repo's `AI_SHOWCASE.md` qualifies, but the story should centre on **JetBrains tools (Air/Junie/IDE)**. Usage of other agents (Claude/Codex) is fine if run via JetBrains Air. OV says "try JetBrains Air in IDEs to work with coding agents like Junie, Codex or Claude".

### A8. Category 2 exact text
**Short form (RULES §4 / OV):** "Category 2 (LoL): Macro Scouting & Draft Management System. A competitive League of Legends coaching platform that eliminates spreadsheet chaos, elevates macro strategy, or accelerates pre-match preparation, built with JetBrains tools; GRID data optional. Entrants can follow one of two featured blueprints, an automated Macro Scouting Tool or a Modular Draft Organizer supporting Fearless Draft rules, or build their own coaching or analytics innovation."

**Long form (SPEC, Category 2):**
- *What to build:* "a competitive League of Legends coaching platform using a JetBrains tool that helps Cloud9's coaches eliminate spreadsheet chaos and elevate draft preparation… tracking opponent macro strategies, warding tendencies, and massive amounts of pick/ban data… a tool that accelerates this pre-match preparation."
- *Core capabilities the tool could include:*
  1. **Draft Tendency Analysis & Recommendations**: analyze champion pools, patch data and recent game history to identify opponent pick/ban patterns and "recommend optimal C9-specific draft strategies."
  2. **Modular Draft Organizer (Fearless Draft Ready)**: "simulates and tracks pick/ban phases and supports current Fearless Draft rules, accounting for shrinking champion pools in Game 3 or Game 5 scenarios."
  3. **Supporting Macro Context**: macro patterns such as jungle pathing tendencies and early-game objective setups, "specifically to provide supporting context for draft insights."
- *Next-level (bonus ideas):*
  - **Data-backed "How to Win" insights**, e.g. "Opponent X picks Sejuani 70% of the time in Game 1. If we ban Sejuani, their Fearless Draft win-rate in Game 2 drops by 15%. Recommend banning Sejuani early."
  - **Live Draft Winrate Impact**: a real-time predicted win-rate % that updates as picks and bans happen.
- *What judges look for:* "must demonstrate how the tool supports Cloud9 draft preparation through draft-tendency analysis, draft organization, or another clearly useful draft capability." The methodology should answer questions like:
  - "What pick/ban tendencies repeat most often for this opponent?"
  - "How does the opponent's draft strategy shift in a Fearless Draft Game 3, 4, or 5 scenario?"
- RES Category 2 inspiration: "Modular Draft Organizer: Create a draft planning tool that tracks champion pools, picks and bans, and Fearless Draft restrictions across a series. Focus on simplifying preparation and helping coaching staff make faster, more informed decisions."

### A9. Judging
| Stage | Detail | Source |
|---|---|---|
| Stage One | Pass/fail: fits the theme and reasonably applies the required JetBrains tools | RULES §6 |
| Stage Two | **5 equally weighted criteria** (20% each). The order matters for tie-breaks. | RULES §6 |
| 1. Technological Implementation | "How thoroughly and skillfully does the project use JetBrains tools? Does the project reflect genuine effort and a working, non-trivial implementation?" | RULES §6 |
| 2. Design | "complete, coherent product experience, not just a technical proof of concept" | RULES §6 |
| 3. Potential Impact | "credible, specific case for solving a real problem for a real audience, and does the solution actually address that problem based on what's demonstrated" | RULES §6 |
| 4. Quality of the Idea | "How creative and novel… differ from existing concepts" | RULES §6 |
| 5. Presentation | Video shows the project end-to-end; the pitch covers problem, audience and why it matters; easy to follow | RULES §6 |
| Tie-break | Highest score on criterion 1, then 2, 3 and so on, then a judges' vote | RULES §6 |
| Method | Sponsor may use "expert panels, peer review, automated AI-driven analysis, or any combination". There may be several rounds. | RULES §6 |

The 2026 rules don't state a per-criterion point scale. The 2025–26 rules used 5 points each, but that's from the old edition and **UNVERIFIED for 2026**.

Judges listed on OV include Jack Etienne (CEO), **Christian Rivera (C9 LoL Head Coach)**, Johnny Pulatie (Asst. GM), Halee Mason, Julien Cheng, Dhruv Bhanderi (AI Engineer), Topher Miller and Andrew La (Cloud9), and Artem Savelev, Egor Kharitonenko, Pedro Calção, Roman Prokashev and Aleksandra Krupskaya (JetBrains).

### A10. Data, third-party APIs, IP
- **GRID data is optional** for every category. **External data is not prohibited.** Rule: "If a Project integrates any third-party SDK, APIs and/or data, Entrant must hold all rights, licenses, consents, and permissions necessary to use and submit such material…" Projects that use or draw inspiration from Riot titles **must comply with Riot's developer policies** (https://developer.riotgames.com/policies/general). (RULES §4 "Third Party Integrations"; OV)
- No rule names the Riot API or Leaguepedia specifically. They're allowed only on their own terms:
  - Leaguepedia content license: **CC BY-SA 3.0** (https://lol.fandom.com/api.php?action=query&meta=siteinfo&siprop=rightsinfo, checked 2026-11-18). Attribution and share-alike apply to the content itself.
  - The Riot dev policy requires product registration through the Developer Portal for API products, and this exact boilerplate in a readily visible place: "[Your product] isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc." Use Data Dragon for assets. **No alternative ranking/MMR calculators. Don't de-anonymize players.** (https://developer.riotgames.com/policies/general)
- **GRID data license (proprietary, LICENSE.md in GRID repo):**
  - Allowed: use only to build, test, demo, submit and have judged the project, **during the Hackathon Period** (until the hackathon ends, judging included).
  - **No redistribution:** "publish, share… upload, mirror, re-host… or otherwise make the Data, or any part or derivative of it, available to any third party," including committing it to any repo, public or private.
  - No commercial use or betting. No ML models trained on it that outlive the project or the hackathon.
  - Allowed to show judges and organizers "results, statistics, charts and other outputs derived from the Data", and to include "only the small excerpts of the Data reasonably necessary to demonstrate the Project".
  - AI tools are allowed, but if a tool offers an opt-out from training or retention, **you must enable it**.
  - Keep `stl-hackathon-2026-grid-starter/` **outside** the project and gitignore `*.zst`, `*.jsonl`, `*.parquet`, `*.sqlite` and `*.duckdb`.
- GRID LoL coverage: 745 series / 1,739 games covering LCK 2025 (Cup, Splits 2–3), LEC 2025–Spring 2026, LTA North/South 2025, **LCS Split 1–3 2026 + Promotion 2026**. Cloud9 appears as **"Cloud9 Kia"** (LCS). Times are UTC. Some series are missing games or the `team-won-series` event, so derive results per game (GRID README).
- **IP (RULES §7):** entrants keep their IP. Sponsor, Devpost and JetBrains get a non-exclusive license to use the entry for judging, and the right to promote it and use participants' names and likenesses for 3 years. The submission must be original and solely owned. OSS use is OK if its licenses are followed.
- Category 3 only: games must use original names, art and assets rather than recreating Riot content (RULES §4).
- **AI tools:** encouraged. The rules have no restriction on AI-generated code beyond originality and ownership (RULES §4, §7; GRID LICENSE §4(c)).

### A11. Eligibility and team
- Open to individuals at or above the age of majority, teams of such individuals, and organizations. **No maximum team size is stated.** A team appoints one Representative who submits (RULES §3, §4).
- Excluded: residents of Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea and OFAC-sanctioned countries. Also excluded: employees and families of Cloud9, Devpost, **JetBrains, GRID**, judges, and anyone with a conflict of interest (RULES §3).
- Multiple submissions are allowed if each is substantially different (RULES §4).
- Prizes need identity verification and an affidavit within 10 business days. GDC winners must obtain their own US visa (RULES §8).

### A12. Updates / contact
- UPD on 2026-11-18: **no updates posted** ("Stay tuned for important announcements…"). **No rule changes yet.**
- Discussions: 1 thread so far (license codes). https://cloud9.devpost.com/forum_topics
- Contact: the "Email the hackathon manager" link on OV. RULES §15: "For questions, send an email to support@devpost.com". RULES §11: if any term is ambiguous, "they must submit a written request for clarification" before the deadline.
- **Cloud9 Discord, for office hours and help:** https://discord.gg/cloud9 (c9.gg/discord redirects there; OV "Join the Cloud9 Discord for office hours and help"). Office-hours schedule: **UNVERIFIED**, not on Devpost.
- Official Rules prevail over any other hackathon material if they conflict (RULES §11).

---

## PART B: 2026 pro LoL draft rules

### B1. Pick/ban order (unchanged in 2026, but keyed to the **first-pick team**, not blue side)
EWCRB §5.6.5 (2026): "1st pick Team = A ; 2nd pick Team = B ● Bans: ABABAB ● Picks: ABBAAB ● Bans: BABA ● Picks: BAAB". LCSRB §9.4.1 says "Picks and Bans will follow the standard Snake Draft Mode."

| Phase | Order (A = first-pick team) |
|---|---|
| Ban phase 1 | A B A B A B |
| Pick phase 1 | A B B A A B |
| Ban phase 2 | B A B A |
| Pick phase 2 | B A A B |

**Simulator impact:** this is the same 20-step sequence as before. The key change for 2026 is that **A is the first-pick team, which can be red side**. The side (blue/red) must be a separate field from draft order. Historical data before 2026 is blue = first pick.

### B2. Fearless Draft ("Hard"/"Full" Fearless) in 2026
- **LCS 2026 (LCSRB §2.1.5, §9.4):** "All Matches in the LCS will be played as a Fearless Draft." "Champions that are picked by a Team may not be used again in the duration of that Match for either Team… regardless of win or loss each Game."
- **No Game 5 reset in the LCS:** "In a Bo5, the same process will occur for each Game resulting in 50 Champions overall being banned for Game 5 if needed (40 via Fearless, 10 via the bans in pick ban)."
- **Bans don't carry over:** "Champions banned via this process are available for Teams to select in following Games (unless otherwise banned via Fearless)" (LCSRB §9.4.1).
- If a player picks a Fearless-locked champion, champ select is remade immediately and the team may be penalized. TOs may use a third-party draft tool for Fearless (LCSRB §9.4, §9.4.2).
- **International / EWC 2026 (EWCRB §5.6.8):** the same hard rule, "regardless of which side selected it."
- First Stand 2026: all Bo5, "Hard Fearless Draft" (https://lol.fandom.com/wiki/2026_First_Stand). lolesports: FST "will also use Fearless Draft" (https://www.gosugamers.net/lol/news/77812-lol-esports-2026-introduces-new-draft-rule-first-selection-and-a-bo5-heavy-first-stand).
- LCS Promotion 2026: "Full Fearless, First Selection, Best-of-Fives" (https://lolesports.com/en-US/news/lcs-promotion-tournament-wsci, published 2026-09-08).
- NACL 2026: "all matches… will feature both Fearless Draft and First Selection" (https://lolesports.com/en-US/news/2026-nacl-summer-split-primer, 2026-07-10).
- 2025 background: Riot extended Fearless (picked champs unavailable to **both** teams) to all regional leagues from Split 2 on. Worlds 2025 used it in Bo3/Bo5, while Swiss Bo1s are naturally unaffected (https://lolesports.com/news/fearless-draft-takes-over-2025, published 2025-03-16).
- Older Tier-2 variants (historical only, **not** 2026 Tier 1): NACL 2024 skipped ban phase 2 in G4 and had no bans in G5; LCK CL 2024 reverted G5 to tournament draft; LDL 2022 used soft Fearless, own team only (https://lol.fandom.com/wiki/2025_LOL_Esports_Restructure).
- **LCK / LEC / LPL 2026 Game 5 handling: UNVERIFIED.** No 2026 rulebook for those leagues was found. Leaguepedia LCK/LEC 2026 pages don't state a G5 exception.
- **Remakes:** LCSRB §11.7.1 says players keep the same runes, skins and summoner spells in a remade game. How a remade game interacts with the Fearless pool (do champions from a voided game count?) is **UNVERIFIED**. GRID data includes rolled-back or abandoned games that should be dropped (GRID README "Data caveats").

**Simulator impact:**
- `locked(series, g) = ⋃ picks(games < g)`, applied to both teams. Bans reset each game.
- Unavailable champions grow by 10 per finished game, plus 10 bans in the current game: G1 0 + 10, G2 10 + 10, G3 20 + 10, G4 30 + 10, G5 40 + 10 = 50 (LCS wording). The Bo5 G5 pool is about 172 minus 50 (champion count **UNVERIFIED**).
- Allow a per-league ruleset flag (G5 reset on/off, soft vs hard) since non-LCS details are unverified.

### B3. First Selection ("Right of Choice" / "Right of First Selection") in 2026
- **Announcement (lolesports, 2026-01-08):** "Teams who previously earned side selection will now earn first selection." The team picks side (blue/red) **or** pick order (first/second), and the opponent takes the remaining option. It rolls out in all regions at season start, and Riot will monitor it through 2026. (https://lolesports.com/en-US/news/season-start-2026-lol-esports)
- **LCS mechanics (LCSRB §2.1.10, §2.6):**
  - The Right of Choice holder chooses pick position (first/second) **or** map side (blue/red).
  - The other team makes the "Remaining Choice".
  - Choices are made **simultaneously**: the non-holder submits a preference for both side and pick order, and only the unused one applies.
  - **Game 2 onwards: the Right of Choice goes to the team that lost the previous game** (§2.1.10, §2.6.5).
  - Game 1 declarations are due 5 pm local the day before. Defaults: no Choice means First Pick. A missing Remaining Choice defaults to First Pick and Blue Side, whichever is left (§9.3.10).
  - Between games, the holder has 3 minutes after the nexus explodes (§5.2, in the Promotion section).
- **Game 1 holder in the LCS:**
  - Split 1 Swiss: "the first Team that is drawn into a matchup" (§2.2.1.5).
  - Tiebreaker Bo1: head-to-head record, else coin flip (§2.5.5).
  - Promotion: the higher seed in the winners bracket, the later dropper in the losers bracket, the winners-bracket team in Finals, or a coin flip between same-group teams (§5.2).
  - **Split 2/3 round-robin and playoffs Game 1 rule: UNVERIFIED.** Not found in v2.0. Likely higher seed in playoffs, but don't assume.
- **International (EWCRB §5.3):** in Game 1 the higher seed gets RoFS, or a coin flip if there is no seeding. In later games the loser of the previous game gets it. Submissions are simultaneous and the unused preference stays confidential.
- **Which leagues:** "all regions" per lolesports. The LEC spring primer says it's "in place" for all regional and global events from 2026 (search result for https://lolesports.com/en-GB/news/2026-lec-spring-primer; page text not fetched, so **partly UNVERIFIED**). NACL and LCS Promotion 2026 confirm it (links above). A 2027 LEC preview reportedly says Fearless and First Selection continue in 2027 (https://lolesports.com/en-GB/news/2027-lec-a-look-at-the-year-ahead, search snippet only, **UNVERIFIED**).
- Leaguepedia summary: https://lol.fandom.com/wiki/Right_of_First_Selection. Leaguepedia match data has separate fields `Side Selection`, `FirstPick` and `FirstSel` (seen in https://lol.fandom.com/wiki/LCK/2026_Season/Season_Playoffs wikitext).
- **2025 rule (before First Selection):** the side-selection holder chose blue or red, and **blue was always first pick**. Game 1 went by seed, draw or coin flip depending on the event. In later games the **previous game's loser chose side** (https://lol.fandom.com/wiki/Side_Selection, community wiki). An official 2025 LTA rulebook wasn't found, so the exact 2025 LTA wording is **UNVERIFIED**.

**Simulator impact:**
- The series state needs `rightOfChoiceHolder` per game: G1 by event rule, G2 onwards the previous game's loser.
- The model needs a two-step choice: the holder picks `side` OR `pickOrder`, and the other team picks the remaining one.
- Then derive `firstPickTeam` and `blueTeam` independently and run B1 with A = firstPickTeam.
- Planning tools can model "Fearless pool shrinkage × who gets first pick in G3/G5" (the loser's agency).
- Analytics on 2026 data must not assume blue = first pick.

### B4. LCS 2026 format (LCSRB §2.2–2.4; Leaguepedia LCS 2026 pages)
| Stage | Format |
|---|---|
| Split 1 ("Lock-In") regular season | 8 teams, modified 3-round Swiss, **Bo3**. 3-0 and 2-1 teams plus the best 1-2 team advance; Bo1 last-chance for 6th. |
| Split 1 playoffs | 6-team modified double elimination, **Bo5**. Winner to First Stand 2026. |
| Split 2 regular season | 8 teams, single round robin, **Bo3**, top 6 advance |
| Split 2 playoffs | 6-team double elimination, **Bo5**, top 2 to MSI 2026 |
| Split 3 regular season | 8 teams, single round robin, **Bo3** |
| Split 3 playoffs | double elimination, **Bo5**, all start in Upper Bracket with seeds 1–2 a round ahead; top 3 to Worlds 2026 (https://lol.fandom.com/wiki/LCS/2026_Season/Summer_Playoffs) |
| Tiebreakers | Bo1 |
| Promotion (Oct 2026) | 5 teams, double elimination, **Bo5**, Full Fearless + First Selection |
| International 2026 | First Stand: all Bo5. MSI: Bo5 double elimination. Worlds Swiss: Bo1 except Bo3 for qualification/elimination matches; knockouts Bo5 (Leaguepedia 2026 FST/MSI/Worlds pages) |

C9 2026 context (Leaguepedia): 2nd in Lock-In, 3rd in Spring playoffs, 3rd in Summer playoffs, and eliminated at the Worlds 2026 Play-In.

**Simulator impact:**
- Support both Bo3 (max 2 Fearless-locked games, 20 champs, before G3) and Bo5 (up to 40 before G5).
- Treat Bo1 (tiebreakers, Worlds Swiss) as plain tournament draft with no Fearless carry-over.

---

## Open questions for organizers (Discord / "Email the hackathon manager" / written clarification per RULES §11)
1. **Public hosted demo vs the GRID license.** Can a public website show aggregates derived from GRID (champion pick rates, tendencies) to anyone, or must the demo be gated (login, judges only)? The license bans making "any part or derivative" available to third parties, but allows showing outputs to judges.
2. **External data.** Is it OK to combine GRID with Leaguepedia (CC BY-SA) or Riot Data Dragon champion metadata/icons? Does the Riot developer policy need product registration for a non-API, Data-Dragon-only hackathon app?
3. **Video assets.** Is showing champion icons (Data Dragon) or C9/LCS logos in the demo video acceptable under the "no third-party trademarks" rule?
4. **Bonus prize.** Does an `AI_SHOWCASE.md` covering a mix of JetBrains Air + Junie + Claude/Codex (run inside Air) qualify, or must it focus on Junie/Air/IDE only?
5. Does the deliverable list on OV/SPEC (methodology write-up + tooling explanation) map to separate Devpost form fields, or can they go in one description?
6. Is there a judging score scale for 2026, and are coaches judging Category 2 specifically?
7. Can GRID-derived aggregates be stored in a hosted DB during judging (until Feb 3, 2027), given "license ends when the hackathon ends"?
8. Rules check: LCS Split 2/3 Game 1 Right of Choice method, and whether LCK/LEC/LPL 2026 Fearless has any G5 exception. These matter for a "current Fearless rules" simulator.
