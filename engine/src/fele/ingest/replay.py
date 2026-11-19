"""Replay one GRID series feed into flat rows (one list of dicts per table).

- Final box scores, drafts and game results come from the last `seriesState`. It already reflects
  rollbacks, and it lists only games that were actually played (rolled-back starts are absent).
- Event tables (kills, objectives, level-ups, items) are built event by event. A `!` action undoes
  the most recent earlier event with the same (action, actor, target); rows for games missing from
  the final state are dropped.
- `t_s` is the in-game clock (seconds) from the snapshot taken with each event.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

from fele.ingest.grid import iter_events
from fele.jsontypes import JsonObj

type Row = dict[str, Any]
type Tables = dict[str, list[Row]]

EVENT_TABLES = ("kills", "objectives", "levelups", "item_events", "positions")
# Sent alongside the typed drake event (slayInfernalDrake, …) from patch 15.10 on; dropped to avoid double counting.
GENERIC_DRAGON = "slayDragon"
ITEM_ACTIONS = frozenset({"purchased", "sold", "lost", "acquired", "pickedUp"})
# Pro draft order (A = first-pick team, which may be red side since 2026 "First Selection").
DRAFT_TEMPLATE = tuple(
    (action, team)
    for action, teams in (("ban", "ABABAB"), ("pick", "ABBAAB"), ("ban", "BABA"), ("pick", "BAAB"))
    for team in teams
)
PHASES = ((6, "ban1"), (12, "pick1"), (16, "ban2"), (20, "pick2"))


def draft_phase(slot: int) -> str:
    return next((p for last, p in PHASES if slot <= last), "extra")


def align_draft(actions: list[tuple[str, bool]]) -> list[int | None]:
    """Template slot (1-20) for each (action, by_first_pick_team) in feed order; skipped bans leave gaps.

    GRID renumbers the sequence when a ban is skipped, so `seq` alone mislabels later phases.
    Returns None for an action that doesn't fit the template (recorded out of order).
    """
    slots: list[int | None] = []
    i = 0
    for action, is_a in actions:
        want = (action, "A" if is_a else "B")
        j = next((k for k in range(i, len(DRAFT_TEMPLATE)) if DRAFT_TEMPLATE[k] == want), None)
        slots.append(None if j is None else j + 1)
        if j is not None:
            i = j + 1
    return slots


def _sub(obj: JsonObj, key: str) -> JsonObj:
    """obj[key] as a dict, {} when missing or null."""
    value: JsonObj | None = obj.get(key)
    return value or {}


def _game_id(ev: JsonObj) -> str | None:
    games: list[JsonObj] = _sub(ev, "seriesStateDelta").get("games") or []
    return games[0]["id"] if games else None


def _clock(ev: JsonObj, game_id: str) -> int | None:
    games: list[JsonObj] = _sub(ev, "seriesState").get("games", [])
    for g in games:
        if g["id"] == game_id:
            return _sub(g, "clock").get("currentSeconds")
    return None


def _pos(state: JsonObj) -> tuple[float | None, float | None]:
    p = _sub(_sub(state, "game"), "position")
    return p.get("x"), p.get("y")


def _assisters(ev: JsonObj, game_id: str) -> list[str]:
    for g in ev["seriesStateDelta"].get("games", []):
        if g["id"] == game_id:
            return [p["id"] for t in g.get("teams", []) for p in t.get("players", []) if "killAssistsGiven" in p]
    return []


class _Replay:
    def __init__(self, series_id: str) -> None:
        self.series_id = series_id
        self.rows: Tables = {t: [] for t in EVENT_TABLES}
        self.undo_stack: dict[tuple[str, str, str], list[tuple[str, Row]]] = defaultdict(list)
        self.item_names: dict[str, str] = {}
        self.pending_structure: dict[str, str] = {}  # game_id -> structure destroyed in this envelope
        self.rollbacks = 0

    def add(self, table: str, row: Row, key: tuple[str, str, str]) -> None:
        self.rows[table].append(row)
        self.undo_stack[key].append((table, row))

    def undo(self, key: tuple[str, str, str]) -> None:
        self.rollbacks += 1
        stack = self.undo_stack.get(key)
        if stack:
            table, row = stack.pop()
            self.rows[table].remove(row)

    def handle(self, ev: JsonObj) -> None:  # noqa: C901 — one flat dispatch over event types
        action: str = ev["action"]
        actor, target = ev["actor"], ev["target"]
        key = (action.lstrip("!"), actor["id"], target["id"])
        if action.startswith("!"):
            self.undo(key)
            return
        game_id = _game_id(ev)
        if game_id is None:
            return
        t_s = _clock(ev, game_id)
        a_state: JsonObj = actor.get("state") or {}
        t_state: JsonObj = target.get("state") or {}
        base = {"game_id": game_id, "t_s": t_s}

        if actor["type"] == "player":
            x, y = _pos(a_state)
            if x is not None:
                self.rows["positions"].append({**base, "player_id": actor["id"], "x": x, "y": y, "source": ev["type"]})

        if action == "killed" and target["type"] == "player":
            vx, vy = _pos(t_state)
            killer = actor["id"] if actor["type"] == "player" else None
            row = {
                **base,
                "killer_id": killer,
                "killer_team_id": a_state.get("teamId") if killer else actor["id"],
                "victim_id": target["id"],
                "victim_team_id": t_state.get("teamId"),
                "assist_ids": _assisters(ev, game_id),
                "x": vx,
                "y": vy,
            }
            self.add("kills", row, key)
        elif action == "destroyed":
            self.pending_structure[game_id] = target["id"]
        elif action == "completed" and target["type"] == "increaseLevel":
            x, y = _pos(a_state)
            row = {**base, "player_id": actor["id"], "level": t_state["completionCount"] + 1, "x": x, "y": y}
            self.add("levelups", row, key)
        elif action == "completed" and target["type"] != GENERIC_DRAGON:
            x, y = _pos(a_state)
            is_player = actor["type"] == "player"
            structure = self.pending_structure.pop(game_id, None) if target["type"].startswith("destroy") else None
            row = {
                **base,
                "type": target["type"],
                "kind": target["type"].rstrip("0123456789"),
                "team_id": a_state.get("teamId") if is_player else actor["id"],
                "player_id": actor["id"] if is_player else None,
                "structure_id": structure,
                "x": x,
                "y": y,
            }
            self.add("objectives", row, key)
        elif action in ITEM_ACTIONS and target["type"] == "item":
            if name := t_state.get("name"):
                self.item_names[target["id"]] = name
            row = {**base, "player_id": actor["id"], "item_id": target["id"], "action": action}
            self.add("item_events", row, key)


def _item_names(player: JsonObj) -> list[str | None]:
    items: list[JsonObj] = _sub(player, "inventory").get("items", [])
    return [i.get("name") for i in items]


def _participants(game: JsonObj, won: dict[str, bool]) -> list[Row]:
    rows: list[Row] = []
    for team in game["teams"]:
        for idx, p in enumerate(team["players"]):
            if not _sub(p, "character").get("name"):
                continue  # benched substitute listed on the roster but not playing
            units = {u["unitName"]: u["count"] for u in p.get("unitKills", [])}
            rows.append(
                {
                    "game_id": game["id"],
                    "team_id": team["id"],
                    "side": team["side"],
                    "roster_index": idx,
                    "player_id": p["id"],
                    "player_name": p["name"].strip(),
                    "participation_status": p.get("participationStatus"),
                    "champion": _sub(p, "character").get("name"),
                    "kills": p.get("kills"),
                    "deaths": p.get("deaths"),
                    "assists": p.get("killAssistsGiven"),
                    "gold_earned": p.get("totalMoneyEarned"),
                    "net_worth": p.get("netWorth"),
                    "damage_dealt": p.get("damageDealt"),
                    "damage_taken": p.get("damageTaken"),
                    "vision_score": p.get("visionScore"),
                    "xp": p.get("experiencePoints"),
                    "minions_killed": units.get("minion", 0),
                    "neutral_killed": units.get("neutralMinion", 0),
                    "wards_killed": units.get("ward", 0),
                    "final_items": _item_names(p),
                    "win": won[team["id"]],
                }
            )
    return rows


def _draft(game: JsonObj, sides: dict[str, str]) -> tuple[list[Row], str | None]:
    """Draft rows and the first-pick team id."""
    acts = sorted(game.get("draftActions", []), key=lambda d: int(d["sequenceNumber"]))
    first_pick = next((d["drafter"]["id"] for d in acts if d["type"] == "pick"), None)
    slots = align_draft([(d["type"], d["drafter"]["id"] == first_pick) for d in acts])
    rows = [
        {
            "game_id": game["id"],
            "seq": int(d["sequenceNumber"]),
            "slot": slot,
            "phase": draft_phase(slot) if slot else None,
            "action": d["type"],
            "team_id": d["drafter"]["id"],
            "side": sides.get(d["drafter"]["id"]),
            "champion": d["draftable"].get("name"),
            "champion_id": d["draftable"]["id"],
        }
        for d, slot in zip(acts, slots, strict=True)
    ]
    return rows, first_pick


def replay(series_id: str, path: Path) -> Tables:
    """All rows for one series. Event tables only keep games present in the final state."""
    r = _Replay(series_id)
    final: JsonObj | None = None
    envelope: JsonObj | None = None
    for env, ev in iter_events(path):
        if env is not envelope:  # GRID sends `destroyed` + `completed destroy*` in one envelope; never carry it over
            r.pending_structure.clear()
            envelope = env
        r.handle(ev)
        final = ev.get("seriesState") or final
    out: Tables = {"series": [], "games": [], "draft_actions": [], "participants": []}
    if final is None:
        return out | r.rows

    game_ids = {g["id"] for g in final["games"]}
    for t in EVENT_TABLES:
        out[t] = [row for row in r.rows[t] if row["game_id"] in game_ids]
    for row in out["item_events"]:
        row["item"] = r.item_names.get(row["item_id"])

    for g in final["games"]:
        teams = g["teams"]
        won = {t["id"]: bool(t.get("won")) for t in teams}
        sides = {t["id"]: t["side"] for t in teams}
        by_side = {t["side"]: t["id"] for t in teams}
        draft, first_pick = _draft(g, sides)
        out["games"].append(
            {
                "game_id": g["id"],
                "series_id": series_id,
                "game_number": g.get("sequenceNumber"),
                "patch": _sub(g, "titleVersion").get("name") or None,
                "started_at": g.get("startedAt"),
                "finished": g.get("finished"),
                "duration_s": _sub(g, "clock").get("currentSeconds"),
                "blue_team_id": by_side.get("blue"),
                "red_team_id": by_side.get("red"),
                "winner_team_id": next((tid for tid, w in won.items() if w), None),
                "first_pick_team_id": first_pick,
                "first_pick_side": sides.get(first_pick or ""),
                "draft_actions": len(draft),
                "draft_standard": [r["slot"] for r in draft] == list(range(1, len(DRAFT_TEMPLATE) + 1)),
            }
        )
        out["draft_actions"] += draft
        out["participants"] += _participants(g, won)

    teams = final.get("teams", [])
    out["series"].append(
        {
            "series_id": series_id,
            "format": final.get("format"),
            "started_at": final.get("startedAt"),
            "team1_id": teams[0]["id"] if teams else None,
            "team2_id": teams[1]["id"] if len(teams) > 1 else None,
            "team1_score": teams[0].get("score") if teams else None,
            "team2_score": teams[1].get("score") if len(teams) > 1 else None,
            "winner_team_id": next((t["id"] for t in teams if t.get("won")), None),
            "valid": final.get("valid"),
            "rollbacks": r.rollbacks,
        }
    )
    return out
