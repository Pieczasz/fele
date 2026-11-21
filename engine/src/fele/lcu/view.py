"""Watcher snapshot -> the API's LiveState, with champ-select advice for the current action.

Advice is for the action in progress when it is ours (ban, or a pick by any ally), otherwise for the local player's
own pick (pre-pick suggestions while waiting). Personal stats are used only for the local player and party members.
"""

from datetime import UTC, datetime

from fele.api import models
from fele.engine.recommend import Option
from fele.engine.solo import SoloData, ban_options, pick_options
from fele.lcu.history import Pool
from fele.lcu.state import ChampSelect, pro_order
from fele.lcu.watch import Snapshot, Watcher

POOL_SHOWN = 5
NOTE = "Options, not orders: high-elo solo-queue sample + recent games of you and your party. Enemies stay hidden."


def _ref(data: SoloData, champion: int) -> models.ChampRef | None:
    if not champion:
        return None
    return models.ChampRef(id=champion, name=data.names.get(champion, str(champion)), key=data.keys.get(champion))


def _refs(data: SoloData, ids: tuple[int, ...] | list[int]) -> list[models.ChampRef]:
    return [r for c in ids if (r := _ref(data, c))]


def _pool(data: SoloData, pool: Pool | None, position: str | None) -> list[models.PoolChamp]:
    if pool is None:
        return []
    rows = pool.top(POOL_SHOWN, position) or pool.top(POOL_SHOWN)
    return [
        models.PoolChamp(
            champion=ref,
            games=s.games,
            wins=s.wins,
            last_played=datetime.fromtimestamp(s.last_ms / 1000, UTC) if s.last_ms else None,
        )
        for c, s in rows
        if (ref := _ref(data, c))
    ]


def _option(data: SoloData, o: Option) -> models.OptionOut:
    key = next((data.keys[c] for c, n in data.names.items() if n == o.champion), None)
    return models.OptionOut(
        champion=o.champion,
        key=key,
        role=o.role,
        score=round(o.score, 3),
        parts=o.parts,
        reasons=o.reasons,
        win_prob=None,
    )


def advice(data: SoloData, cs: ChampSelect, watcher: Watcher) -> models.LiveAdvice | None:
    visible: dict[int, tuple[Pool, str | None]] = {}  # personal stats: you (name None) and party members only
    for a in cs.allies:
        pool = watcher.pool(a.puuid)
        if pool is not None:
            visible[a.cell] = (pool, None if a.me else a.name)
    cur = cs.current
    if cur and cur.ally and cur.kind == "ban":
        opts = ban_options(data, cs, visible)
        return models.LiveAdvice(
            kind="ban",
            for_cell=cur.cell,
            for_name=_name(cs, cur.cell),
            options=[_option(data, o) for o in opts],
            note=NOTE,
        )
    cell = cur.cell if cur and cur.ally and cur.kind == "pick" else cs.me
    ally = cs.ally(cell)
    our_pick = cur is not None and cur.ally and cur.kind == "pick"
    if ally is None or (ally.champion and not our_pick):
        return None  # nothing to decide: our pick is locked and it isn't an ally's turn
    pool, name = visible.get(cell, (None, None))
    opts = pick_options(data, cs, cell, pool, name)
    return models.LiveAdvice(
        kind="pick", for_cell=cell, for_name=_name(cs, cell), options=[_option(data, o) for o in opts], note=NOTE
    )


def _name(cs: ChampSelect, cell: int) -> str | None:
    ally = cs.ally(cell)
    if ally is None:
        return None
    return "you" if ally.me else ally.name


def _pro(data: SoloData, cs: ChampSelect) -> models.ProDraft | None:
    order = pro_order(cs)
    if order is None:
        return None
    return models.ProDraft(
        actions=[data.names.get(c, str(c)) if c else "" for c in order.actions],  # unknown id: the API says so
        we_pick_first=order.we_pick_first,
        we_are_blue=order.we_are_blue,
    )


def champ_select(data: SoloData, cs: ChampSelect, watcher: Watcher) -> models.LiveChampSelect:
    allies: list[models.LiveAlly] = []
    for a in cs.allies:
        pool = watcher.pool(a.puuid)
        allies.append(
            models.LiveAlly(
                cell=a.cell,
                position=a.position,
                champion=_ref(data, a.champion),
                intent=_ref(data, a.intent),
                name=a.name,
                me=a.me,
                games=pool.games if pool else 0,
                pool=_pool(data, pool, a.position),
            )
        )
    return models.LiveChampSelect(
        queue=cs.queue,
        queue_name=cs.queue_name,
        custom=cs.custom,
        phase=cs.phase,
        time_left_s=cs.time_left_ms / 1000,
        allies=allies,
        enemy_picks=_refs(data, cs.enemy_picks),
        ally_bans=_refs(data, cs.ally_bans),
        enemy_bans=_refs(data, cs.enemy_bans),
        pro_draft=_pro(data, cs),
        actions=[
            models.LiveAction(
                cell=a.cell,
                kind=a.kind,
                ally=a.ally,
                champion=_ref(data, a.champion),
                completed=a.completed,
                in_progress=a.in_progress,
            )
            for a in cs.actions
        ],
    )


def live_state(data: SoloData, watcher: Watcher | None, cached: models.LiveAdvice | None = None) -> models.LiveState:
    snap = watcher.snapshot if watcher else Snapshot()
    cs = snap.champ_select
    return models.LiveState(
        enabled=watcher is not None,
        connected=snap.connected,
        phase=snap.phase,
        me=snap.me_name,
        party=[n for n in snap.party.values() if n],
        champ_select=champ_select(data, cs, watcher) if cs and watcher else None,
        advice=cached if cs else None,
        sample=f"{data.patch_label}, {data.matches} high-elo games" if data.matches else "no solo-queue sample",
        version=watcher.version if watcher else 0,
    )
