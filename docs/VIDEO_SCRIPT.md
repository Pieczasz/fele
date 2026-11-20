# Demo video script (< 3 minutes)

Rules for the recording (Devpost + docs/COMPLIANCE.md): screen capture of fele only, Data Dragon champion icons and
our own UI. No broadcast footage, no copyrighted music, no team or league logos. Team names in text are fine.
Public YouTube upload, linked from Devpost.

Setup before recording: the API on cached aggregates, browser at 1440×900, light theme, a fresh plan (`fele-plan`
cleared), coach inputs reset to the team file. Rehearse the mock draft once so the live context is warm (no 30 s
cold build on camera).

| Time | On screen | Narration (draft) |
|---|---|---|
| 0:00–0:20 | A coach's spreadsheet of champion pools and crossed-out picks (our own mock, no real staff data), then the fele home page | "Under Fearless draft, every champion you play is gone for the rest of the series, for both teams. Coaches plan a Bo5 in spreadsheets. fele turns that into one tool: scout, plan the series, rehearse the draft." |
| 0:20–1:00 | Teams → an opponent → Draft tab: G1 vs G3+ split, n badges, strong/weak/noise labels; the "how to win" cards; Players tab: pool size with interval | "Pick the opponent. Their draft priorities, split by game number in the series, because Fearless changes what teams do in game 3. Every number shows how many games it rests on, and patterns that could be chance are labelled as noise. The cards summarise what matters, with their evidence." |
| 1:00–1:50 | "Plan a series vs this team" → Bo5, enter game 1 by hand (won), save Azir for game 3, Simulate → series win %, availability per game; "What if we lose the next game?" | "The series planner. Game 1 is in: those ten champions are locked for both teams. Keep Azir for game 3. The simulation plays out the rest of the series a few hundred times with a model of how both teams draft: series win probability with its error, which champions are still available in each game, and whether the save plan changes anything beyond noise." |
| 1:50–2:30 | Mock draft: bans with reasons, press 1 to take an option, their turn shows likely picks, win-probability bar with range; finish and "Save to series as a win" | "Then rehearse game 2. The board follows the real pro draft order. On our turn, five options, each with its reasons: what pros do in this spot, the player's comfort, what the comp is missing, the lane matchup. On their turn, what this opponent most likely does. These are options, not orders. The coach decides." |
| 2:30–2:50 | METHODOLOGY / MODEL_CARD headings, the model-ladder table, PyCharm with the run configurations, Qodana in CI | "How it's built: official GRID data, Riot's Data Dragon and API. Walk-forward validation, a holdout used once, and honest results: the draft model predicts 71% of pro picks and bans in its top ten, but nothing beat Elo at predicting the winner, so we say win probabilities are Elo-dominated. Built in PyCharm with JetBrains AI tools, checked by Qodana on every push." |
| 2:50–3:00 | Home page, repo URL | "fele: plan the whole series, not just the next pick." |

Open points for the human: approve this flow (Phase 10 checkpoint), record the voice-over, and check the final cut
is under 3:00.
