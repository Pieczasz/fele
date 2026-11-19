"""GRID replay, draft alignment, role inference and Fearless state — on synthetic feeds (no real data in CI)."""

import json
from compression import zstd

import polars as pl
import pytest

from fele.ingest.build import fearless_state, parquet_dir
from fele.ingest.replay import align_draft, draft_phase, replay
from fele.ingest.roles import infer_roles, lane

GAME = "g1"
BLUE, RED = "100", "200"


def _ev(action, actor, target, *, clock=0, game=GAME, actor_state=None, target_state=None, delta=None):  # noqa: PLR0913
    a_type, a_id = actor
    t_type, t_id = target
    return {
        "type": f"{a_type}-{action}-{t_type}",
        "action": action,
        "actor": {"type": a_type, "id": a_id, "state": actor_state or {}},
        "target": {"type": t_type, "id": t_id, "state": target_state or {}},
        "seriesState": {"games": [{"id": game, "clock": {"currentSeconds": clock}}]},
        "seriesStateDelta": delta or {"games": [{"id": game}]},
    }


def _player(pid, team, x=0.0, y=0.0):
    return {"id": pid, "teamId": team, "game": {"position": {"x": x, "y": y}}}


def _final_player(pid, champ, **kw):
    return {"id": pid, "name": f" p{pid} ", "character": {"name": champ} if champ else None, **kw}


def _final_state():
    draft = [
        {"sequenceNumber": 1, "type": "ban", "drafter": {"id": RED}, "draftable": {"id": "c9", "name": "Azir"}},
        {"sequenceNumber": 2, "type": "pick", "drafter": {"id": RED}, "draftable": {"id": "c1", "name": "Ahri"}},
    ]
    return {
        "format": "best-of-1",
        "teams": [{"id": BLUE, "won": False, "score": 0}, {"id": RED, "won": True, "score": 1}],
        "games": [
            {
                "id": GAME,
                "sequenceNumber": 1,
                "titleVersion": {"name": "16.1"},
                "clock": {"currentSeconds": 1800},
                "draftActions": draft,
                "teams": [
                    {"id": BLUE, "side": "blue", "won": False, "players": [_final_player("1", "Ahri", kills=2)]},
                    {
                        "id": RED,
                        "side": "red",
                        "won": True,
                        "players": [_final_player("2", "Zed"), _final_player("9", None)],  # 9 = benched sub
                    },
                ],
            }
        ],
    }


def _write(path, events):
    with zstd.open(path, "wt", encoding="utf-8") as f:
        for i, ev in enumerate(events):
            f.write(json.dumps({"sequenceNumber": i, "occurredAt": "2026-01-01T00:00:00Z", "events": [ev]}) + "\n")


def test_replay_synthetic_series(tmp_path):
    item = {"name": "Doran's Blade"}
    events = [
        _ev("purchased", ("player", "1"), ("item", "a"), clock=1, actor_state=_player("1", BLUE), target_state=item),
        _ev("purchased", ("player", "1"), ("item", "b"), clock=2, actor_state=_player("1", BLUE)),
        _ev("!purchased", ("player", "1"), ("item", "b"), clock=3),  # undo of the second purchase
        _ev(
            "completed",
            ("player", "2"),
            ("increaseLevel", "increaseLevel"),
            clock=100,
            actor_state=_player("2", RED, 7000, 7000),
            target_state={"completionCount": 1},
        ),
        _ev(
            "killed",
            ("player", "1"),
            ("player", "2"),
            clock=300,
            actor_state=_player("1", BLUE),
            target_state=_player("2", RED, 5000, 6000),
            delta={"games": [{"id": GAME, "teams": [{"players": [{"id": "3", "killAssistsGiven": 1}]}]}]},
        ),
        _ev("destroyed", ("player", "1"), ("tower", "red-turret-top-1"), clock=600),
        _ev("completed", ("player", "1"), ("destroyTower", "destroyTower"), clock=600, actor_state=_player("1", BLUE)),
        _ev("completed", ("player", "1"), ("slayDragon", "slayDragon"), clock=700),  # generic duplicate, dropped
        _ev("killed", ("player", "1"), ("player", "2"), game="rolled-back-game"),  # not in the final state
        {**_ev("ended", ("series", "s"), ("game", GAME)), "seriesState": _final_state()},
    ]
    path = tmp_path / "events_1_grid.jsonl.zst"
    _write(path, events)
    t = replay("1", path)

    assert [(r["item_id"], r["item"]) for r in t["item_events"]] == [("a", "Doran's Blade")]
    assert t["levelups"] == [{"game_id": GAME, "t_s": 100, "player_id": "2", "level": 2, "x": 7000, "y": 7000}]
    (kill,) = t["kills"]
    assert (kill["t_s"], kill["killer_id"], kill["victim_id"], kill["assist_ids"]) == (300, "1", "2", ["3"])
    (obj,) = t["objectives"]
    assert (obj["kind"], obj["structure_id"], obj["team_id"]) == ("destroyTower", "red-turret-top-1", BLUE)
    assert {p["player_id"] for p in t["participants"]} == {"1", "2"}  # benched sub dropped
    assert t["participants"][0]["player_name"] == "p1"
    (game,) = t["games"]
    assert (game["winner_team_id"], game["first_pick_side"], game["duration_s"]) == (RED, "red", 1800)
    assert t["series"][0]["rollbacks"] == 1
    assert t["series"][0]["winner_team_id"] == RED


def test_align_draft_skipped_ban_and_red_first_pick():
    full = [("ban", True), ("ban", False)] * 3 + [(a, t) for a, t in [("pick", True), ("pick", False)]]
    assert align_draft(full) == list(range(1, 9))
    # team B skips its 3rd ban: later actions keep their template slots
    skipped = [("ban", True), ("ban", False), ("ban", True), ("ban", False), ("ban", True), ("pick", True)]
    assert align_draft(skipped) == [1, 2, 3, 4, 5, 7]
    assert align_draft([("pick", False)] * 30)[-1] is None  # more picks than the template has
    assert [draft_phase(s) for s in (1, 6, 7, 12, 13, 16, 17, 20)] == [
        "ban1", "ban1", "pick1", "pick1", "ban2", "ban2", "pick2", "pick2",
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("xy", "expected"),
    [((7500, 7400), "mid"), ((1500, 9000), "top"), ((6000, 14000), "top"), ((9000, 1200), "bot"), ((5000, 9500), None)],
)
def test_lane(xy, expected):
    assert lane(*xy) == expected


LANES = {"top": (1500, 9000), "mid": (7500, 7500), "bot": (9000, 1200), "jungle": (5000, 9500)}


def _team_game(game, team, champs, lanes, *, sup_item=True, roster_shift=2):
    """Participants/positions/items for one team: players 0..4 are top, jungle, mid, bot, support."""
    parts, pos, items = [], [], []
    for i, (champ, ln) in enumerate(zip(champs, lanes, strict=True)):
        pid = f"{team}{i}"
        parts.append(
            {
                "game_id": game,
                "team_id": team,
                "player_id": pid,
                "champion": champ,
                "roster_index": (i + roster_shift) % 5,  # shifted = roster order deliberately wrong
                "neutral_killed": 150 if i == 1 else 5,
                "minions_killed": 30 if i == 4 else 250,
            }
        )
        x, y = LANES[ln]
        pos += [{"game_id": game, "player_id": pid, "t_s": 120 + k, "x": x, "y": y, "source": "lv"} for k in range(6)]
        if i == 4 and sup_item:
            items.append({"game_id": game, "player_id": pid, "action": "purchased", "item": "World Atlas"})
    return parts, pos, items


def test_infer_roles_normal_and_lane_swap():
    champs = ["Rumble", "Vi", "Ahri", "Jinx", "Leona"]
    a = _team_game("g1", "A", champs, ["top", "jungle", "mid", "bot", "bot"])
    # lane swap: duo top, solo bot (roster order correct here; the swap must not flip top/bot)
    b = _team_game("g2", "B", champs, ["bot", "jungle", "mid", "top", "top"], roster_shift=0)
    c = _team_game("g3", "C", champs, ["top", "jungle", "mid", "bot", "bot"], sup_item=False)
    parts = pl.DataFrame(a[0] + b[0] + c[0])
    pos = pl.DataFrame(a[1] + b[1] + c[1])
    items = pl.DataFrame(a[2] + b[2] + c[2], schema={"game_id": str, "player_id": str, "action": str, "item": str})
    roles = infer_roles(parts, pos, items).sort("player_id")
    expected = ["top", "jungle", "mid", "bot", "support"] * 3
    assert roles["inferred_role"].to_list() == expected
    assert roles.filter(pl.col("game_id") == "g2")["lane_swap"].all()
    assert not roles.filter(pl.col("game_id") == "g1")["lane_swap"].any()
    assert roles["role_confidence"].min() > 0.5


def test_fearless_state():
    games = pl.DataFrame({"game_id": ["a", "b", "c"], "series_id": ["s"] * 3, "game_number": [1, 2, 3]})
    draft = pl.DataFrame(
        {
            "game_id": ["a", "a", "b", "b", "c"],
            "action": ["pick", "ban", "pick", "pick", "pick"],
            "champion": ["Ahri", "Zed", "Jinx", "Vi", "Leona"],
        }
    )
    fs = fearless_state(games, draft)
    assert fs["locked_champions"].to_list() == [[], ["Ahri"], ["Ahri", "Jinx", "Vi"]]
    assert fs["locked_count"].to_list() == [0, 1, 3]


@pytest.mark.real_data
def test_ingest_acceptance_on_real_data():
    """Phase 2 acceptance: run `uv run fele ingest` first, then `uv run pytest -m real_data`."""
    d = parquet_dir()
    games = pl.read_parquet(d / "games.parquet")
    parts = pl.read_parquet(d / "participants.parquet")
    meta_games = 1739
    assert games.height == meta_games
    per_game = parts.group_by("game_id").len()
    assert (per_game["len"] == 10).sum() >= meta_games - 2  # 2 documented feed gaps without players
    roles_ok = parts.drop_nulls("inferred_role").group_by("game_id", "team_id").agg(pl.col("inferred_role").n_unique())
    assert (roles_ok["inferred_role"] == 5).all()
    modal = parts.group_by("player_id").agg(pl.col("inferred_role").mode().first().alias("modal"))
    agree = parts.join(modal, on="player_id").select((pl.col("inferred_role") == pl.col("modal")).mean()).item()
    assert agree >= 0.98
    jungle = parts.filter(pl.col("inferred_role") == "jungle")
    top_neutral = parts.group_by("game_id", "team_id").agg(pl.col("neutral_killed").max().alias("mx"))
    jg_agree = jungle.join(top_neutral, on=["game_id", "team_id"]).select(
        (pl.col("neutral_killed") == pl.col("mx")).mean()
    )
    assert jg_agree.item() >= 0.98
