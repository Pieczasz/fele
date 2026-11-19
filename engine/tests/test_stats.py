"""Phase 5 statistics on small synthetic tables with answers worked out by hand."""

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from fele.config import settings
from fele.stats import core, data, draft, elo, macro, meta, pools

T0 = datetime(2026, 1, 1, tzinfo=UTC)


# --- core -------------------------------------------------------------------------------------------------------
def test_wilson_interval_known_values():
    r = core.with_rate(pl.DataFrame({"k": [5, 0, 0], "n": [10, 10, 0]})).to_dicts()
    assert (r[0]["rate"], round(r[0]["lo"], 4), round(r[0]["hi"], 4)) == (0.5, 0.2366, 0.7634)
    assert (r[1]["lo"], round(r[1]["hi"], 4)) == (0.0, 0.2775)
    assert r[2]["rate"] is None  # n = 0 → no rate, no interval


def test_beta_prior_recovers_simulation():
    rng = np.random.default_rng(1)
    p = rng.beta(30, 30, size=400)
    n = np.full(400, 40)
    a, b = core.fit_beta_prior(rng.binomial(n, p), n)
    assert a / (a + b) == pytest.approx(0.5, abs=0.02)
    assert 25 < a + b < 140  # true strength 60; well away from "no shrinkage" and "full pooling"


def test_shrinkage_pulls_small_samples_to_the_prior():
    df = pl.DataFrame({"g": ["x"] * 3, "k": [1, 50, 0], "n": [1, 100, 0]})
    s = core.with_shrunk(df, prior_by=("g",)).to_dicts()
    prior_mean = s[0]["prior_a"] / (s[0]["prior_a"] + s[0]["prior_b"])
    assert s[2]["shrunk"] == pytest.approx(prior_mean)  # no games → prior mean
    assert s[0]["shrunk"] < 1.0  # 1/1 is not a 100% win rate
    assert s[0]["shrunk_lo"] < s[0]["shrunk"] < s[0]["shrunk_hi"]


def test_bh_and_tendency_labels():
    assert core.bh_qvalues(np.array([0.01, 0.04, 0.03, 0.5])).round(3).tolist() == [0.04, 0.053, 0.053, 0.5]
    t = core.with_tendency(pl.DataFrame({"k": [90, 6, 27], "n": [100, 10, 40], "base_rate": [0.5, 0.5, 0.5]}))
    assert t["tendency"].to_list() == ["strong", "noise", "weak"]  # 27/40: p ≈ 0.04, q ≈ 0.06


def test_trailing_windows():
    w = data.trailing_windows(["15.1", "15.2", "15.3", "15.10"], size=2)
    assert w.filter(pl.col("window") == "15.10")["patch"].to_list() == ["15.3", "15.10"]
    assert w.filter(pl.col("window") == "15.1")["patch"].to_list() == ["15.1"]


# --- shared synthetic games: team A vs B, 4 games -------------------------------------------------------------
def _ctx() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "game_id": ["g1", "g2", "g3", "g4"],
            "series_id": ["s1", "s1", "s1", "s2"],
            "league": ["LCS"] * 4,
            "event": ["LCS"] * 4,
            "format": ["best-of-3"] * 4,
            "started_at": [T0 + timedelta(days=i) for i in range(4)],
            "patch": ["16.1"] * 4,
            "game_number": [1, 2, 3, 1],
            "game_bucket": ["G1", "G2", "G3+", "G1"],
            "blue_team_id": ["A", "B", "A", "B"],
            "red_team_id": ["B", "A", "B", "A"],
            "winner_team_id": ["A", "A", "B", "A"],
            "first_pick_team_id": ["A", "B", "A", "B"],
        }
    )


def _draft() -> pl.DataFrame:
    rows = [  # (game, team, action, champion, phase, slot)
        ("g1", "A", "ban", "Azir", "ban1", 1),
        ("g1", "A", "pick", "Vi", "pick1", 7),
        ("g1", "B", "ban", "Ahri", "ban1", 2),
        ("g2", "A", "ban", "Azir", "ban2", 14),
        ("g2", "B", "ban", "Vi", "ban1", 1),
        ("g3", "A", "pick", "Ahri", "pick2", 18),
        ("g4", "A", "ban", "Azir", "ban1", 2),
    ]
    cols = ("game_id", "team_id", "action", "champion", "phase", "slot")
    return pl.DataFrame([dict(zip(cols, r, strict=True)) for r in rows])


def test_team_draft_presence_and_splits():
    tg = data.team_games(_ctx())
    td = draft.team_draft(_draft(), tg)
    azir = td.filter(pl.col("team_id") == "A", pl.col("champion") == "Azir")
    overall = azir.filter(pl.col("split_type") == "all").row(0, named=True)
    assert (overall["k"], overall["n"], overall["bans"], overall["first_rotation"]) == (3, 4, 3, 2)
    assert overall["base_rate"] == 3 / 8  # league: 3 of 8 team-games had Azir picked/banned by the drafting team
    g1 = azir.filter(pl.col("split") == "G1").row(0, named=True)
    assert (g1["k"], g1["n"]) == (2, 2)


def _parts() -> pl.DataFrame:
    rows = []
    for g, (a_mid, b_mid) in zip(
        ("g1", "g2", "g3", "g4"), (("Vi", "Ahri"), ("Orianna", "Ahri"), ("Ahri", "Azir"), ("Vi", "Syndra")), strict=True
    ):
        rows += [
            {
                "game_id": g,
                "team_id": "A",
                "player_id": "a_mid",
                "player_name": "AMid",
                "inferred_role": "mid",
                "champion": a_mid,
            },
            {
                "game_id": g,
                "team_id": "B",
                "player_id": "b_mid",
                "player_name": "BMid",
                "inferred_role": "mid",
                "champion": b_mid,
            },
        ]
    return pl.DataFrame(rows)


def test_ban_targets_use_only_earlier_games():
    tg = data.team_games(_ctx())
    bans = draft.ban_targets(_draft(), _parts(), tg)
    by = {(r["game_id"], r["team_id"]): r for r in bans.to_dicts()}
    assert by["g1", "A"]["target_player_id"] is None  # Azir: B's mid only plays it later (g3)
    assert by["g1", "B"]["target_player_id"] is None  # Ahri: A's mid first plays it in g3
    assert by["g2", "B"]["target_player"] == "AMid"  # Vi: A's mid played it in g1
    assert by["g4", "A"]["target_player"] == "BMid"  # Azir: B's mid played it in g3
    per_player = draft.ban_targeting_by_player(bans).row(0, named=True)
    assert (per_player["team_id"], per_player["k"], per_player["n"]) == (
        "A",
        1,
        2,
    )  # A faced 2 bans, 1 aimed at a player


# --- pools / elo ----------------------------------------------------------------------------------------------
def test_player_champions_recency_and_pool_size():
    as_of = T0 + timedelta(days=90)
    parts = pl.DataFrame(
        {
            "player_id": ["p"] * 4,
            "inferred_role": ["mid"] * 4,
            "champion": ["Ahri", "Ahri", "Azir", "Vex"],
            "win": [True, False, True, True],
            "started_at": [T0, as_of - timedelta(days=1), T0, as_of + timedelta(days=1)],  # last one is after as_of
        }
    )
    pc = pools.player_champions(parts, as_of).sort("champion")
    ahri = pc.row(0, named=True)
    assert (ahri["n"], ahri["k"]) == (2, 1)
    assert ahri["recent_games"] == pytest.approx(0.5 + 0.5 ** (1 / 90))  # one game one half-life ago, one yesterday
    assert "Vex" not in pc["champion"].to_list()
    value, lo, hi = pools.effective_pool(np.array([5.0, 5.0, 5.0, 5.0]), np.random.default_rng(0))
    assert value == pytest.approx(4.0)
    assert lo <= 4.0 <= hi
    summary = pools.player_summary(pc, {"mid": ["Azir", "Orianna"]}).row(0, named=True)
    assert (summary["n"], summary["unique_champions"], summary["meta_k"], summary["meta_n"]) == (3, 2, 0, 2)


def test_elo_is_time_respecting():
    e = elo.game_elo(_ctx()).to_dicts()
    assert (e[0]["blue_elo"], e[0]["red_elo"], e[0]["blue_n"]) == (1500.0, 1500.0, 0)
    assert e[1]["red_elo"] == 1516.0  # A won g1 as an even match: +K/2
    assert e[1]["expected_blue"] < 0.5


# --- macro ----------------------------------------------------------------------------------------------------
def test_team_game_macro_and_rates():
    ctx = _ctx().filter(pl.col("game_id") == "g1")
    tg = data.team_games(ctx)
    parts = pl.DataFrame(
        {"game_id": ["g1", "g1"], "team_id": ["A", "B"], "player_id": ["aj", "bj"], "inferred_role": ["jungle"] * 2}
    )
    levelups = pl.DataFrame(
        {
            "game_id": ["g1"] * 4,
            "player_id": ["aj", "aj", "bj", "bj"],
            "level": [2, 3, 2, 3],
            "t_s": [100, 140, 105, 150],
            "x": [3000.0, 3500.0, 11000.0, 10000.0],
            "y": [8000.0, 8000.0, 6000.0, 5000.0],
        }
    )
    objectives = pl.DataFrame(
        {
            "game_id": ["g1"] * 4,
            "t_s": [200, 360, 300, 400],
            "kind": ["slayRiftScuttlerBot", "slayVoidGrub", "slayInfernalDrake", "slayRiftScuttlerTop"],
            "team_id": ["B", "A", "B", "A"],
        }
    )
    kills = pl.DataFrame(
        {
            "game_id": ["g1"],
            "t_s": [250],
            "killer_team_id": ["A"],
            "victim_team_id": ["B"],
            "x": [5000.0],
            "y": [5200.0],
        }
    )
    m = {r["team_id"]: r for r in macro.team_game_macro(tg, parts, levelups, objectives, kills).to_dicts()}
    assert (m["A"]["jungle_start"], m["B"]["jungle_start"]) == ("top", "bot")
    assert (m["A"]["got_first_scuttle"], m["B"]["got_first_scuttle"], m["A"]["first_scuttle_side"]) == (
        False,
        True,
        "bot",
    )
    assert (m["A"]["grubs_before_drake"], m["B"]["grubs_before_drake"]) == (True, False)
    assert (m["A"]["got_first_blood"], m["A"]["got_first_drake"], m["A"]["grubs_s"]) == (True, False, 360)
    rates = macro.team_macro_rates(pl.DataFrame(list(m.values())))
    fb = rates.filter(pl.col("team_id") == "A", pl.col("metric") == "got_first_blood", pl.col("split") == "all")
    assert fb.select("k", "n", "base_rate").row(0) == (1, 1, 0.5)
    cells = macro.early_kill_cells(kills, tg)
    assert cells.filter(pl.col("kind") == "kill").select("team_id", "cx", "cy", "count", "n").row(0) == (
        "A",
        5,
        5,
        1,
        1,
    )


# --- meta -----------------------------------------------------------------------------------------------------
def test_meta_score_rewards_presence_and_uses_live_soloq():
    games = pl.DataFrame({"game_id": ["g1", "g2"], "patch": ["16.1", "16.1"]})
    windows = pl.DataFrame({"window": ["16.1", "live"], "patch": ["16.1", "16.1"]})
    d = pl.DataFrame(
        {"game_id": ["g1", "g2", "g1"], "action": ["ban", "ban", "pick"], "champion": ["Azir", "Azir", "Wukong"]}
    )
    parts = pl.DataFrame({"game_id": ["g1"], "champion": ["Wukong"], "win": [True]})
    cmap = pl.DataFrame(
        {"grid_name": ["Azir", "Wukong"], "champion": ["Azir", "MonkeyKing"], "name": ["Azir", "Wukong"]}
    )
    soloq = pl.DataFrame(
        {"window": ["live"] * 2, "champion": ["MonkeyKing", "Azir"], "games": [100] * 2, "wins": [60, 40]}
    )
    m = meta.meta_scores(d, parts, games, windows, cmap, soloq=soloq)
    hist = m.filter(pl.col("window") == "16.1").sort("champion")
    assert hist["presence"].to_list() == [1.0, 0.5]
    assert hist["meta_score"][0] > hist["meta_score"][1]  # Azir: present in every game
    live = m.filter(pl.col("window") == "live", pl.col("champion") == "MonkeyKing").row(0, named=True)
    assert live["soloq_n"] == 100
    assert 0.5 < live["soloq_wr"] < 0.6  # 60% shrunk toward the prior


# --- real data ------------------------------------------------------------------------------------------------
INTERVALS = {  # table -> (value, lo, hi) column triples that must hold lo <= value <= hi
    "team_draft": [("rate", "lo", "hi"), ("first_rotation_rate", "first_rotation_lo", "first_rotation_hi")],
    "ban_targets": [("rate", "lo", "hi")],
    "macro_rates": [("rate", "lo", "hi")],
    "champion_roles": [("rate", "lo", "hi"), ("shrunk", "shrunk_lo", "shrunk_hi")],
    "player_champions": [("rate", "lo", "hi"), ("shrunk", "shrunk_lo", "shrunk_hi")],
    "players": [("effective_pool", "effective_pool_lo", "effective_pool_hi")],
    "meta": [("presence", "presence_lo", "presence_hi"), ("pro_wr", "pro_wr_lo", "pro_wr_hi")],
}


@pytest.mark.real_data
def test_stats_tables_carry_n_and_intervals():
    """Phase 5 acceptance: run `uv run fele stats` first. Every rate has a sample size and an interval around it."""
    agg = settings().local("aggregates")
    for name, triples in INTERVALS.items():
        df = pl.read_parquet(agg / f"stats_{name}.parquet")
        assert not df.is_empty(), name
        assert {"n"} <= set(df.columns) or "games" in df.columns, name
        for value, lo, hi in triples:
            d = df.drop_nulls([value, lo, hi])
            assert d.height > 0, (name, value)
            ok = (d[lo] <= d[value] + 1e-9) & (d[value] <= d[hi] + 1e-9)
            assert ok.all(), (name, value)
    elo_games = pl.read_parquet(agg / "stats_elo.parquet")
    assert elo_games.height >= 1735
    assert elo_games["expected_blue"].is_between(0, 1).all()
