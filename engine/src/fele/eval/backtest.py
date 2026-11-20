"""Back-test of the recommender (Phase 9 acceptance): on the holdout drafts, how often was the team's actual pick in
our top 1 / top 5, for the draft-action model alone and for the recommender's re-ranking (model + composition +
style + lane matchup)?

Honest set-up: the draft model is trained on development series only; every feature comes from the time-respecting
feature store (state as of each game); style profiles use only earlier picks. The recommender's weights are fixed by
design and were not tuned on this (it is a report, not a selection — the holdout already served its one selection
check in Phase 8). Coach preferences exist only for Cloud9, so they are not part of the league-wide back-test.
Caveat: lane matchups come from the live-patch solo-queue sample, later than the holdout games.
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import numpy.typing as npt
import polars as pl

from fele.engine.live import MATCHUP_PRIOR, POSITION, STYLE_HALF_LIFE_DAYS, champion_tags, soloq_matchups
from fele.engine.recommend import W, comp_fit, style_fit
from fele.eval import metrics, splits
from fele.eval.run import Data, inputs, load
from fele.features import state
from fele.models.action import LambdaRank, open_roles

type Floats = npt.NDArray[np.float64]
ROLES = tuple(str(r) for r in state.ROLES)
COLS = (*state.TAG_COLS, "scaling")


def _profile(history: pl.DataFrame, tags: dict[str, dict[str, float]], now: datetime) -> npt.NDArray[np.float32] | None:
    total, weight = np.zeros(len(COLS), np.float32), 0.0
    for champ, t in history.select("champion", "started_at").iter_rows():
        if champ in tags:
            w = 0.5 ** ((now - t).total_seconds() / 86400 / STYLE_HALF_LIFE_DAYS)
            total += w * np.array([tags[champ][c] for c in COLS], np.float32)
            weight += w
    return total / weight if weight else None


def _ranks(scores: Floats, candidates: npt.NDArray[np.bool_], true: int) -> int:
    s = np.where(candidates, scores, -np.inf)
    return int(1 + (s > s[true]).sum())


@dataclass(frozen=True)
class BacktestResult:
    picks: int
    scored: int
    median_candidates: float
    model_top1: float
    recommender_top1: float
    diff_top1: metrics.Interval
    model_top5: float
    recommender_top5: float
    diff_top5: metrics.Interval
    model_mrr: float
    recommender_mrr: float


def backtest(data: Data | None = None) -> BacktestResult:
    data = data or load()
    inp = inputs()
    tags = champion_tags(inp)
    matchups = soloq_matchups(inp.cmap, inp.champions)
    hold = splits.holdout_ids(data.series)
    in_hold = pl.col("series_id").is_in(list(hold))
    ranker = LambdaRank()
    ranker.fit(data.actions.filter(~in_hold), data.act)
    test = data.actions.filter(in_hold & (pl.col("action") == "pick"))
    probs = ranker.scores_for(test, data.act)
    act, vocab = data.act, data.act.vocab
    picks = data.actions.filter(pl.col("action") == "pick")
    rows: list[dict[str, object]] = []
    profiles: dict[tuple[str, datetime], npt.NDArray[np.float32] | None] = {}
    for r, row in enumerate(test.iter_rows(named=True)):
        i = int(row["idx"])
        own: list[int] = [int(c) for c in act.own_picks[i] if c >= 0]
        free = open_roles(act.own_picks[i : i + 1], act.champ_roles)[0]
        role_ok = (act.champ_roles & free).any(axis=1)
        cand = role_ok & ~act.unavailable[i] & (probs[r] > 0)
        true = int(row["y"])
        if not cand[true]:
            continue  # the actual pick didn't fit our role model (e.g. a flex into an unusual role)
        key = (row["team_id"], row["started_at"])
        if key not in profiles:
            hist = picks.filter((pl.col("team_id") == row["team_id"]) & (pl.col("started_at") < row["started_at"]))
            profiles[key] = _profile(hist, tags, row["started_at"])
        ours = [vocab[c] for c in own]
        opp: list[int] = [int(c) for c in act.opp_picks[i] if c >= 0]
        opp_roles = {vocab[c]: ROLES[int(np.argmax(act.champ_roles[c]))] for c in opp}
        score = np.log(np.maximum(probs[r], 1e-12)) * W["pro"]
        for c in np.flatnonzero(cand):
            champ = vocab[c]
            role = ROLES[int(np.argmax(act.champ_roles[c] & free))]
            score[c] += (
                W["comp"] * comp_fit(tags, ours, champ)[0] + W["style"] * style_fit(tags, profiles[key], None, champ)[0]
            )
            enemy = next((e for e, er in opp_roles.items() if er == role), None)
            if enemy is not None and role in POSITION:
                games, wins = matchups.get((role, champ, enemy), (0, 0))
                score[c] += W["lane"] * ((wins + 0.5 * MATCHUP_PRIOR) / (games + MATCHUP_PRIOR) - 0.5)
        rows.append(
            {
                "series_id": row["series_id"],
                "model_rank": _ranks(probs[r], cand, true),
                "rec_rank": _ranks(score, cand, true),
                "candidates": int(cand.sum()),
            }
        )
    df = pl.DataFrame(rows)
    groups = df["series_id"].to_numpy()

    def hits(col: str, top: int) -> Floats:
        return (df[col].to_numpy() <= top).astype(float)

    def diff(top: int) -> metrics.Interval:
        return metrics.paired_bootstrap(-hits("rec_rank", top), -hits("model_rank", top), groups)  # < 0: rec hits more

    return BacktestResult(
        picks=test.height,
        scored=df.height,
        median_candidates=float(np.median(df["candidates"].to_numpy())),
        model_top1=float(hits("model_rank", 1).mean()),
        recommender_top1=float(hits("rec_rank", 1).mean()),
        diff_top1=diff(1),
        model_top5=float(hits("model_rank", 5).mean()),
        recommender_top5=float(hits("rec_rank", 5).mean()),
        diff_top5=diff(5),
        model_mrr=float((1 / df["model_rank"].to_numpy()).mean()),
        recommender_mrr=float((1 / df["rec_rank"].to_numpy()).mean()),
    )


def report(s: BacktestResult) -> str:
    def diff(i: metrics.Interval) -> str:
        return f"{-i.mean:+.1%} [{-i.hi:+.1%}, {-i.lo:+.1%}]"

    return "\n".join(
        [
            "# Recommender back-test (holdout drafts)",
            "",
            __doc__ or "",
            (
                f"- Holdout picks: {s.picks}; scored: {s.scored} (the actual pick fitted an open role); median "
                f"{s.median_candidates:.0f} candidate champions per pick."
            ),
            "",
            "| | Draft model alone | Recommender (model + comp + style + lane) | Recommender - model [95% CI] |",
            "|---|---|---|---|",
            f"| Actual pick is the top option | {s.model_top1:.1%} | {s.recommender_top1:.1%} | {diff(s.diff_top1)} |",
            f"| Actual pick in the top 5 | {s.model_top5:.1%} | {s.recommender_top5:.1%} | {diff(s.diff_top5)} |",
            f"| Mean reciprocal rank | {s.model_mrr:.3f} | {s.recommender_mrr:.3f} | |",
            "",
            (
                "Reading: matching what teams actually did is a sanity check, not the goal: the recommender is meant "
                "to add the coach's knowledge and composition sense on top of 'what pros do here'. Whether a "
                "recommended alternative would have *won more* can't be validated with this data: Phase 8 found draft "
                "effects on win probability too small to measure (docs/MODEL_CARD.md), so the engine labels its draft "
                "edge as weak evidence."
            ),
            "",
        ]
    )
