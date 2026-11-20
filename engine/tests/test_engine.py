"""Phase 9 draft engine: draft order and Fearless (unit), recommendations and the series simulator (real data)."""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from fele.engine.draft import THEM, US, DraftState
from fele.engine.recommend import coach_for_opponent, comp_fit, saved_for_later, style_fit
from fele.engine.series import _blocked  # pyright: ignore[reportPrivateUsage]
from fele.prefs import ChampionNote, Comfort, PlayerPrefs, Preferences, Role, SeriesStrategy


def test_draft_order_follows_the_pro_template():
    s = DraftState(we_pick_first=True)
    order = [(s.who(i), s.kind(i)) for i in range(1, 21)]
    assert order[:6] == [(US, "ban"), (THEM, "ban")] * 3
    assert order[6:12] == [(US, "pick"), (THEM, "pick"), (THEM, "pick"), (US, "pick"), (US, "pick"), (THEM, "pick")]
    assert order[16:] == [(THEM, "pick"), (US, "pick"), (US, "pick"), (THEM, "pick")]
    red_first = DraftState(we_pick_first=False)
    assert red_first.who(7) == THEM  # 2026 First Selection: the other team may pick first
    assert s.phase(13) == "ban2"


def test_draft_state_tracks_picks_and_enforces_fearless():
    s = DraftState(we_pick_first=True, locked=frozenset({"Azir"}))
    with pytest.raises(ValueError, match="not available"):
        s.play("Azir")  # picked in an earlier game of the series
    for c in ["A", "B", "C", "D", "E", "F", "Ahri", "Vi", "Jinx"]:
        s = s.play(c)
    assert (s.picks(US), s.picks(THEM), s.bans()) == (["Ahri"], ["Vi", "Jinx"], ["A", "B", "C", "D", "E", "F"])
    with pytest.raises(ValueError, match="not available"):
        s.play("Vi")
    s = s.play("")  # nothing stops a skipped slot
    assert s.slot == 11


TAGS = {
    "Mage": {"ap_share": 1.0, "engage": 0, "disengage": 1, "peel": 1, "frontline": 0, "poke": 3, "dive": 0,
             "splitpush": 0, "waveclear": 3, "hard_cc": 1, "scaling": 2.0},
    "Tank": {"ap_share": 0.6, "engage": 3, "disengage": 1, "peel": 2, "frontline": 3, "poke": 0, "dive": 2,
             "splitpush": 0, "waveclear": 1, "hard_cc": 3, "scaling": 1.0},
    "Marksman": {"ap_share": 0.0, "engage": 0, "disengage": 1, "peel": 0, "frontline": 0, "poke": 1, "dive": 0,
                 "splitpush": 0, "waveclear": 2, "hard_cc": 0, "scaling": 2.0},
}  # fmt: skip


def test_comp_fit_rewards_filling_gaps():
    score, reasons = comp_fit(TAGS, ["Mage", "Mage"], "Marksman")
    assert score > 0
    assert any("balances damage" in r for r in reasons)
    tank, why = comp_fit(TAGS, ["Mage", "Marksman"], "Tank")
    assert tank > 0
    assert "adds frontline the comp lacks" in why


def test_style_fit_follows_coach_tags():
    prefs = Preferences(team="T", players=[], strategy=SeriesStrategy(style_tags=["teamfight"]))
    tank, why = style_fit(TAGS, None, prefs, "Tank")
    mage, _ = style_fit(TAGS, None, prefs, "Mage")
    assert tank > mage
    assert "fits the coach's 'teamfight' style" in why


# --- real data -----------------------------------------------------------------------------------------------------
@pytest.mark.real_data
def test_recommendations_are_legal_and_explained():
    from fele.engine import recommend  # noqa: PLC0415 - needs the live context (real data)
    from fele.engine.live import get_live  # noqa: PLC0415

    live = get_live()
    m = recommend.matchup(live, "Cloud9 Kia", "FlyQuest", we_are_blue=True)
    s = DraftState(we_pick_first=True, locked=frozenset({"Orianna"}))
    bans = recommend.recommend(m, s)
    assert len(bans) == recommend.TOP_N
    assert all(o.reasons for o in bans)
    for c in ["Azir", "Vi", "Varus", "Yone", "Rumble", "Nocturne"]:
        s = s.play(c)
    picks = recommend.recommend(m, s)
    assert picks
    assert not {o.champion for o in picks} & s.taken()  # never recommends something unavailable
    assert all(o.role for o in picks)
    lo_mean_hi = recommend.rollout_win_prob(m, s, n=8)
    assert 0 < lo_mean_hi[1] <= lo_mean_hi[0] <= lo_mean_hi[2] < 1


@pytest.mark.real_data
@settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 10_000), best_of=st.sampled_from([3, 5]), blue=st.booleans())
def test_simulated_series_always_respect_fearless(seed: int, best_of: int, blue: bool):  # noqa: FBT001 - hypothesis
    from fele.engine import series  # noqa: PLC0415 - needs the live context (real data)
    from fele.engine.live import get_live  # noqa: PLC0415

    res = series.simulate(
        get_live(), "Cloud9 Kia", "FlyQuest", best_of=best_of, we_start_blue=blue, sims=6, seed=seed, record=True
    )
    for games in res.drafts:
        seen: set[str] = set()
        for ours, theirs in games:
            picked = ours + theirs
            assert len(picked) == len(set(picked)) == 10  # no duplicates inside a game
            assert not set(picked) & seen  # hard Fearless across the series
            seen |= set(picked)
        assert len(games) <= best_of


def test_coach_entries_match_the_opponent_by_name_prefix_or_id():
    table = {"Team Liquid": ["Kalista"], "fq": ["Azir"], " ": ["Nobody"]}
    assert coach_for_opponent(table, "Team Liquid Alienware", "tl-id") == {"Kalista"}
    assert coach_for_opponent(table, "FlyQuest", "fq") == {"Azir"}
    assert coach_for_opponent(table, "", "") == set()


def test_save_list_applies_only_before_the_game_it_is_kept_for():
    prefs = Preferences(team="C9", players=[], strategy=SeriesStrategy(save_for_late_games=["Ezreal"]))
    assert saved_for_later(prefs, {"Azir": 4}, game=1) == {"Ezreal", "Azir"}
    assert saved_for_later(prefs, {"Azir": 4}, game=3) == {"Azir"}  # game 3+: the coach's list is free to use
    assert saved_for_later(prefs, {"Azir": 4}, game=4) == set()


def test_one_players_refusal_does_not_block_a_teammates_champion():
    prefs = Preferences(
        team="C9",
        players=[
            PlayerPrefs(name="Top", role=Role.top, pool=[ChampionNote(champion="Gragas", comfort=Comfort.refuses)]),
            PlayerPrefs(
                name="Jgl", role=Role.jungle, pool=[ChampionNote(champion="Gragas", comfort=Comfort.comfortable)]
            ),
            PlayerPrefs(name="Mid", role=Role.mid, pool=[ChampionNote(champion="Zoe", comfort=Comfort.refuses)]),
        ],
    )
    assert _blocked(prefs, {}, game=3) == {"Zoe"}
