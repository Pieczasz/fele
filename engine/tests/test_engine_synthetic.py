"""Draft engine end to end on a small synthetic world (runs in CI, no real data): the live context, recommendations,
win probability, the series simulator and the API endpoints on top of them.

The world: 4 teams of clearly different strength (A strongest, D weakest), 60 champions with a primary role each,
teams that favour their own champions, the pro draft order with bans, and hard Fearless within each series.
"""

import math
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import polars as pl
import pytest

from fele.engine import recommend, series
from fele.engine.draft import THEM, US, DraftState
from fele.engine.live import Live, build_live
from fele.features import state
from fele.models.action import LambdaRank
from fele.prefs import ChampionNote, Comfort, PlayerPrefs, Preferences, Role, SeriesStrategy
from fele.stats.data import game_context
from fele.stats.elo import game_elo

T0 = datetime(2025, 1, 1, tzinfo=UTC)
ROLES = [str(r) for r in Role]
TEAMS = {"A": "Alpha", "B": "Bravo", "C": "Charlie", "D": "Delta"}
STRENGTH = {"A": 1.5, "B": 0.5, "C": -0.5, "D": -1.5}
CHAMPS = [f"Champ{i:02d}" for i in range(60)]  # 12 per role: enough for a Bo5 under hard Fearless
ROLE_OF = {c: ROLES[i % 5] for i, c in enumerate(CHAMPS)}
GAMES_PER_SERIES = 3


def _world(seed: int = 0) -> state.Inputs:
    rng = np.random.default_rng(seed)
    favourite = {t: set(rng.choice(CHAMPS, 15, replace=False).tolist()) for t in TEAMS}
    series_rows, game_rows, draft_rows, part_rows = [], [], [], []
    for s in range(48):
        sid, start = f"s{s:02d}", T0 + timedelta(days=7 * s)
        blue, red = (str(t) for t in rng.choice(list(TEAMS), 2, replace=False))
        series_rows.append({"series_id": sid, "started_at": start, "league": "LCS", "event": "LCS", "format": "bo3"})
        used: set[str] = set()
        for g in range(GAMES_PER_SERIES):
            gid = f"{sid}g{g + 1}"
            p_blue = 1 / (1 + math.exp(-(STRENGTH[blue] - STRENGTH[red])))
            game_rows.append(
                {
                    "game_id": gid,
                    "series_id": sid,
                    "game_number": g + 1,
                    "patch": "15.1",
                    "started_at": start + timedelta(hours=g),
                    "blue_team_id": blue,
                    "red_team_id": red,
                    "winner_team_id": blue if rng.random() < p_blue else red,
                    "first_pick_team_id": blue,
                }
            )
            d = DraftState(we_pick_first=True)  # US = blue = first pick
            roles_left = {US: list(ROLES), THEM: list(ROLES)}
            while not d.complete:
                who = d.who(d.slot)
                team = blue if who == US else red
                free = [c for c in CHAMPS if c not in used and c not in d.taken()]
                if d.kind(d.slot) == "pick":
                    role = roles_left[who].pop(int(rng.integers(len(roles_left[who]))))
                    free = [c for c in free if ROLE_OF[c] == role]
                else:  # never ban a role empty: both teams still need a champion for it
                    free = [c for c in free if sum(ROLE_OF[x] == ROLE_OF[c] for x in free) > 2]
                if not free:  # nothing safe to ban: skip it (real teams skip bans too)
                    d = d.play("")
                    continue
                weights = np.array([5.0 if c in favourite[team] else 1.0 for c in free])
                champ = str(rng.choice(free, p=weights / weights.sum()))
                draft_rows.append(
                    {
                        "game_id": gid,
                        "slot": d.slot,
                        "action": d.kind(d.slot),
                        "phase": d.phase(d.slot),
                        "team_id": team,
                        "champion": champ,
                    }
                )
                if d.kind(d.slot) == "pick":
                    part_rows.append(
                        {
                            "game_id": gid,
                            "team_id": team,
                            "player_id": f"{team}-{ROLE_OF[champ]}",
                            "player_name": f"{TEAMS[team]} {ROLE_OF[champ]}",
                            "champion": champ,
                            "inferred_role": ROLE_OF[champ],
                        }
                    )
                d = d.play(champ)
            used |= set(d.picks(US)) | set(d.picks(THEM))
    tags = [
        {
            "champion": c,
            "riot_id": 90_000 + i,  # no real champion id: no real solo-queue matchups attach to it
            "roles": ROLE_OF[c] + ("|" + ROLES[(i + 1) % 5] if i % 2 else ""),  # every other champion can flex
            "scaling": ["early", "mid", "late"][i % 3],
            **{k: float(rng.integers(0, 4)) for k in state.TAG_COLS},
            "ap_share": float(i % 3 == 0),
        }
        for i, c in enumerate(CHAMPS)
    ]
    series_df, games = pl.DataFrame(series_rows), pl.DataFrame(game_rows)
    return state.Inputs(
        games=games,
        series=series_df,
        draft=pl.DataFrame(draft_rows),
        parts=pl.DataFrame(part_rows),
        fearless=games.select("game_id", locked_count=pl.lit(0)),
        champions=pl.DataFrame(tags),
        cmap=pl.DataFrame({"grid_name": CHAMPS, "champion": CHAMPS}),
        deltas=pl.DataFrame({"champion": CHAMPS, "patch": ["15.1"] * len(CHAMPS), "score": [0.0] * len(CHAMPS)}),
        elo=game_elo(game_context(games, series_df)),
    )


@pytest.fixture(scope="module")
def live() -> Live:
    with pytest.MonkeyPatch.context() as mp:  # a smaller ranker: these tests check behaviour, not model quality
        mp.setattr("fele.engine.live.LambdaRank", lambda: LambdaRank(n_estimators=60))
        return build_live(_world(), team_names=TEAMS)


def _prefs(**strategy: object) -> Preferences:
    return Preferences(
        team="Alpha",
        players=[
            PlayerPrefs(
                name=f"Alpha {r}",
                role=Role(r),
                pool=[ChampionNote(champion=c, comfort=Comfort.comfortable) for c in CHAMPS if ROLE_OF[c] == r][:2],
            )
            for r in ROLES
        ],
        strategy=SeriesStrategy.model_validate(strategy),
    )


def test_a_full_draft_gets_legal_explained_options_at_every_turn(live: Live):
    never, locked = CHAMPS[0], CHAMPS[1]
    prefs = _prefs(never_pick=[never])
    m = recommend.matchup(live, "Alpha", "D", we_are_blue=True, game_number=2)
    s = DraftState(we_pick_first=True, locked=frozenset({locked}))
    roles_taken: list[str] = []
    while not s.complete:
        if s.who(s.slot) == US:
            options = recommend.recommend(m, s, prefs, enemy_name="Delta")
            names = [o.champion for o in options]
            assert 1 <= len(options) <= recommend.TOP_N
            assert len(set(names)) == len(names)
            assert not set(names) & s.taken()  # never a taken or Fearless-locked champion
            assert s.kind(s.slot) == "ban" or never not in names  # never-pick: we may still ban it
            assert all(o.reasons for o in options)
            if s.kind(s.slot) == "pick":
                assert all(o.role not in roles_taken for o in options)  # one champion per role
                roles_taken.append(str(options[0].role))
            s = s.play(options[0].champion)
        else:
            probs = recommend.action_probs(m, [s])[0]
            assert probs.sum() == pytest.approx(1.0)
            assert probs[[live.builder.index[c] for c in s.taken()]].max() == 0  # the model never picks a taken one
            s = s.play(live.vocab[int(probs.argmax())])
    assert sorted(roles_taken) == sorted(ROLES)


def test_save_list_modes_and_must_bans(live: Live):
    m3 = recommend.matchup(live, "A", "D", we_are_blue=True, game_number=3)
    s = DraftState(we_pick_first=True, actions=("",) * 6)
    top = recommend.recommend_pick(m3, s, _prefs())[0].champion
    m1 = recommend.matchup(live, "A", "D", we_are_blue=True, game_number=1)
    plan = {top: 3}  # the planner keeps it for game 3
    best = {o.champion: o for o in recommend.recommend_pick(m1, s, _prefs(), "best", save=plan)}
    assert top not in best or best[top].parts["save"] < 0
    assert top not in {o.champion for o in recommend.recommend_pick(m1, s, _prefs(), "save", save=plan)}
    assert recommend.recommend_pick(m3, s, _prefs(), "save", save=plan)[0].champion == top  # free from game 3

    ban_state = DraftState(we_pick_first=True)
    threat = recommend.action_probs(m1, [ban_state], as_pick_for=THEM)[0]
    unlikely = live.vocab[int(threat.argmin())]
    bans = recommend.recommend_ban(m1, ban_state, _prefs(must_ban_vs_opponent={"del": [unlikely]}), enemy_name="Delta")
    assert unlikely in [o.champion for o in bans]  # a must-ban is always listed, whatever the model thinks
    off = _prefs(must_ban_vs_opponent={"del": [unlikely]}).model_copy(update={"weight": 0.0})
    assert unlikely not in [o.champion for o in recommend.recommend_ban(m1, ban_state, off, enemy_name="Delta")]


def test_win_probability_is_a_probability_that_favours_the_stronger_team(live: Live):
    s = DraftState(we_pick_first=True)
    strong = recommend.rollout_win_prob(recommend.matchup(live, "A", "D", we_are_blue=True), s, n=8)
    weak = recommend.rollout_win_prob(recommend.matchup(live, "D", "A", we_are_blue=True), s, n=8)
    for mean, p10, p90 in (strong, weak):
        assert 0 <= p10 <= mean <= p90 <= 1
    assert weak[0] < 0.5 < strong[0]


def test_series_simulation_is_reproducible_fearless_and_labelled(live: Live):
    run = {"best_of": 5, "sims": 16, "seed": 1, "record": True}
    a = series.simulate(live, "A", "D", **run)  # pyright: ignore[reportArgumentType]
    again = series.simulate(live, "A", "D", **run)  # pyright: ignore[reportArgumentType]
    assert a.series_win == again.series_win  # same seed, same answer
    for games in a.drafts:
        picked = [c for ours, theirs in games for c in [*ours, *theirs]]
        assert len(picked) == len(set(picked))  # hard Fearless: nobody picks a champion twice in a series
        assert 3 <= len(games) <= 5
    d = series.simulate(live, "D", "A", **run)  # pyright: ignore[reportArgumentType]
    assert d.series_win < 0.5 < a.series_win

    locked = frozenset(CHAMPS[:10])
    start = series.SeriesStart(game=3, wins=1, losses=1, locked=locked)
    late = series.simulate(live, "A", "D", best_of=5, sims=10, seed=2, record=True, start=start)
    assert late.first_game == 3
    assert all(len(v) <= 3 for v in late.availability.values())  # games 3, 4, 5 at most
    assert not {c for games in late.drafts for ours, theirs in games for c in [*ours, *theirs]} & locked


async def test_api_endpoints_run_on_the_live_context(live: Live, monkeypatch: pytest.MonkeyPatch):
    from fele.api.app import app  # noqa: PLC0415

    monkeypatch.setattr("fele.engine.live.get_live", lambda: live)
    monkeypatch.setattr("fele.api.app._key_map", dict)  # no Data Dragon data in CI
    prefs = _prefs().model_dump(mode="json")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/draft/recommend", json={"us": "Alpha", "them": "Delta", "actions": ["", "", ""], "preferences": prefs}
        )
        assert r.status_code == 200, r.text
        advice = r.json()
        assert advice["next"] == {"slot": 4, "who": "them", "kind": "ban", "phase": "ban1"}
        assert advice["options"] == []  # their turn: no options for us, their likely actions instead
        assert len(advice["likely"]) == recommend.TOP_N
        assert 0 <= advice["win_prob"]["p10"] <= advice["win_prob"]["mean"] <= advice["win_prob"]["p90"] <= 1
        bad = await c.post("/draft/recommend", json={"us": "Alpha", "them": "Delta", "actions": ["Nope"]})
        assert bad.status_code == 422
        r = await c.post(
            "/series/simulate",
            json={"us": "Alpha", "them": "Delta", "sims": 20, "save": {CHAMPS[2]: 3}, "preferences": prefs},
        )
        assert r.status_code == 200, r.text
        plan = r.json()
        assert plan["no_plan"] is not None
        assert plan["within_noise"] == (abs(plan["difference"]) < 2 * plan["difference_se"])
