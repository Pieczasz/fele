"""`fele evaluate`: walk-forward evaluation of outcome and draft-action models → markdown report (+ MLflow).

Every model is fitted per outer fold on earlier series only and scored on that fold's month; predictions are pooled
over folds. Confidence intervals resample series. The reference models are `baseline_elo` (outcome) and
`action_global` (draft actions); every other model is reported as a paired difference to them.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

from fele.config import REPO_ROOT, settings
from fele.eval import metrics, splits
from fele.features import state
from fele.ingest.grid import read_meta
from fele.models.registry import ACTION as ACTION_MODELS
from fele.models.registry import OUTCOME as OUTCOME_MODELS
from fele.stats import elo
from fele.stats.data import game_context, read

OUTCOME_REF = "baseline_elo"
ACTION_REF = "action_global"
LEARNING_FRACTIONS = (0.25, 0.5, 0.75, 1.0)
LATE_GAME = 3  # G3+: Fearless late games
REPORT_DIR = REPO_ROOT / "docs" / "experiments"


@dataclass
class Data:
    series: pl.DataFrame
    outcome: pl.DataFrame
    actions: pl.DataFrame  # ActionData.rows + idx (row index into the ActionData arrays)
    act: state.ActionData
    folds: list[splits.Fold]
    cloud9: frozenset[str]

    @property
    def vocab(self) -> list[str]:
        return self.act.vocab


@dataclass
class Results:
    outcome: dict[str, pl.DataFrame] = field(default_factory=dict[str, pl.DataFrame])  # model -> pooled predictions
    actions: dict[str, pl.DataFrame] = field(default_factory=dict[str, pl.DataFrame])
    learning: list[dict[str, float]] = field(default_factory=list[dict[str, float]])


def inputs() -> state.Inputs:
    """Every table the feature store needs, from data_local (ingest + static)."""
    games, series = read("games"), read("series")
    static = settings().local("static")
    return state.Inputs(
        games=games,
        series=series,
        draft=read("draft_actions"),
        parts=read("participants"),
        fearless=read("fearless_state"),
        champions=pl.read_parquet(static / "champions.parquet"),
        cmap=pl.read_parquet(static / "champion_map.parquet"),
        deltas=pl.read_parquet(static / "patch_deltas.parquet"),
        elo=elo.game_elo(game_context(games, series)),
    )


def load() -> Data:
    inp = inputs()
    games, series = inp.games, inp.series
    ctx = game_context(games, series)
    outcome, act = state.build(inp)
    outcome = outcome.join(ctx.select("game_id", "game_bucket"), on="game_id").with_columns(
        elo_diff=pl.col("d_elo"), patch_age=state.patch_age()
    )
    cloud9 = frozenset(t["team_id"] for t in read_meta("teams") if "Cloud9" in t["name"])
    actions = act.rows.with_row_index("idx")
    return Data(series, outcome, actions, act, splits.outer_folds(series), cloud9)


def _in(ids: frozenset[str]) -> pl.Expr:
    return pl.col("series_id").is_in(list(ids))


def run_outcome(data: Data, name: str, fold_list: list[splits.Fold] | None = None) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for fold in fold_list or data.folds:
        model = OUTCOME_MODELS[name]()
        model.fit(data.outcome.filter(_in(fold.train)))
        test = data.outcome.filter(_in(fold.test))
        parts.append(test.with_columns(p=pl.Series(model.predict(test)), fold=pl.lit(fold.name)))
    out = pl.concat(parts)
    return out.with_columns(
        cloud9=pl.col("blue_team_id").is_in(list(data.cloud9)) | pl.col("red_team_id").is_in(list(data.cloud9))
    )


def _score_actions(scores: np.ndarray, rows: pl.DataFrame, act: state.ActionData) -> pl.DataFrame:
    """Mask unavailable champions, renormalise, and read off the probability and rank of the true champion."""
    idx = rows["idx"].to_numpy()
    probs = np.where(act.unavailable[idx], 0.0, np.maximum(scores, 0.0))
    probs /= probs.sum(axis=1, keepdims=True)
    true_idx = rows["y"].to_numpy()
    p_true = probs[np.arange(len(true_idx)), true_idx]
    rank = 1 + (probs > p_true[:, None]).sum(axis=1)
    return rows.select("series_id", "game_id", "action", "phase", "game_number").with_columns(
        p_true=pl.Series(p_true), rank=pl.Series(rank)
    )


def run_actions(data: Data, name: str, fold_list: list[splits.Fold] | None = None) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    for fold in fold_list or data.folds:
        model = ACTION_MODELS[name]()
        model.fit(data.actions.filter(_in(fold.train)), data.act)
        test = data.actions.filter(_in(fold.test))
        parts.append(_score_actions(model.scores(test), test, data.act).with_columns(fold=pl.lit(fold.name)))
    return pl.concat(parts)


def learning_curve(data: Data, name: str) -> list[dict[str, float]]:
    """Pooled log loss when each fold trains on only its most recent fraction of training series."""
    order = splits.series_order(data.series)["series_id"].to_list()
    rows: list[dict[str, float]] = []
    for frac in LEARNING_FRACTIONS:
        folds: list[splits.Fold] = []
        for f in data.folds:
            train = [s for s in order if s in f.train]
            keep = frozenset(train[len(train) - max(1, round(len(train) * frac)) :])
            folds.append(splits.Fold(f.name, keep, f.test))
        preds = run_outcome(data, name, folds)
        y, p = preds["y"].to_numpy(), preds["p"].to_numpy()
        rows.append({"fraction": frac, "log_loss": float(metrics.log_losses(y, p).mean())})
    return rows


BASELINES = ("baseline_constant", "baseline_blue", "baseline_elo")
ACTION_BASELINES = ("action_global", "action_team_slot")


def evaluate(models: list[str]) -> tuple[Data, Results, str]:
    """Run `models` plus every baseline of both problems (the bar to beat). Returns the outcome model in focus."""
    data = load()
    res = Results()
    for name in dict.fromkeys([*BASELINES, *(m for m in models if m in OUTCOME_MODELS)]):
        res.outcome[name] = run_outcome(data, name)
    for name in dict.fromkeys([*ACTION_BASELINES, *(m for m in models if m in ACTION_MODELS)]):
        res.actions[name] = run_actions(data, name)
    focus = focus_model(res, models)
    res.learning = learning_curve(data, focus)
    return data, res, focus


def evaluate_holdout(outcome: str, action: str, *, confirm: bool) -> tuple[Data, Results]:
    """The single final check: train on every development series, score the latest 15% once (recorded)."""
    data = load()
    fold = splits.holdout_split(data.series, confirm=confirm, note=f"outcome={outcome}, action={action}")
    res = Results()
    for name in dict.fromkeys([*BASELINES, outcome]):
        res.outcome[name] = run_outcome(data, name, [fold])
    for name in dict.fromkeys([*ACTION_BASELINES, action]):
        res.actions[name] = run_actions(data, name, [fold])
    return data, res


def holdout_report(outcome: str, action: str, data: Data, res: Results) -> str:
    preds = res.outcome[outcome]
    held = preds["fold"].len()
    n_hold = len(splits.holdout_ids(data.series))
    n_dev = data.series.height - n_hold
    return "\n".join(
        [
            f"# Final holdout: `{outcome}` + `{action}`",
            "",
            (
                f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `fele holdout`. Run once; recorded in "
                "`data_local/holdout_used.json`."
            ),
            "",
            f"- Trained on all {n_dev} development series; tested once on the latest {n_hold} series ({held} games).",
            "- The models were chosen on the walk-forward folds before this run.",
            "",
            "## Problem A — who wins",
            "",
            *_outcome_rows(res),
            "",
            "### By slice",
            "",
            *_slices(preds),
            "",
            "## Problem B — next pick or ban",
            "",
            *_action_rows(res),
            "",
        ]
    )


def focus_model(res: Results, models: list[str]) -> str:
    """The detailed sections follow the listed outcome model with the lowest pooled log loss (or the Elo baseline).

    Picking the best of many on the same folds is optimistic (winner's curse); the final holdout, used once, is the
    unbiased check of whatever is chosen.
    """
    candidates = [m for m in models if m in res.outcome and m not in BASELINES] or [OUTCOME_REF]
    return min(candidates, key=lambda m: float(log_losses_of(res.outcome[m]).mean()))


def log_losses_of(preds: pl.DataFrame) -> np.ndarray:
    return metrics.log_losses(preds["y"].to_numpy(), preds["p"].to_numpy())


# --- report -----------------------------------------------------------------------------------------------------
def _same_rows(a: pl.DataFrame, b: pl.DataFrame, key: str) -> None:
    """Paired comparisons need row i of both models to be the same game/action (same folds, same order)."""
    if not a[key].equals(b[key]):
        msg = "model predictions are not aligned row by row"
        raise ValueError(msg)


def _ci(i: metrics.Interval, digits: int = 4) -> str:
    return f"{i.mean:.{digits}f} [{i.lo:.{digits}f}, {i.hi:.{digits}f}]"


def _outcome_rows(res: Results) -> list[str]:
    ref = res.outcome[OUTCOME_REF]
    groups = ref["series_id"].to_numpy()
    ref_loss = metrics.log_losses(ref["y"].to_numpy(), ref["p"].to_numpy())
    lines = [
        "| Model | Log loss [95% CI] | Δ vs baseline_elo [95% CI] | Brier | AUC | Accuracy | ECE |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, preds in sorted(res.outcome.items()):
        _same_rows(preds, ref, "game_id")
        y, p = preds["y"].to_numpy(), preds["p"].to_numpy()
        loss = metrics.log_losses(y, p)
        m = metrics.outcome_metrics(y, p)
        diff = "—" if name == OUTCOME_REF else _ci(metrics.paired_bootstrap(loss, ref_loss, groups))
        lines.append(
            f"| `{name}` | {_ci(metrics.bootstrap_mean(loss, groups))} | {diff} | {m['brier']:.4f} | "
            f"{m['auc']:.3f} | {m['accuracy']:.3f} | {m['ece']:.3f} |"
        )
    return lines


def _slices(preds: pl.DataFrame) -> list[str]:
    lines = ["| Slice | Games | Log loss | Accuracy | ECE |", "|---|---|---|---|---|"]
    cuts: list[tuple[str, pl.DataFrame]] = [("all", preds), ("Cloud9 games", preds.filter(pl.col("cloud9")))]
    for col in ("league", "game_bucket", "patch_age"):
        cuts += [(f"{col} = {v}", preds.filter(pl.col(col) == v)) for v in sorted(preds[col].unique().to_list())]
    for label, df in cuts:
        if df.is_empty():
            continue
        m = metrics.outcome_metrics(df["y"].to_numpy(), df["p"].to_numpy())
        lines.append(f"| {label} | {df.height} | {m['log_loss']:.4f} | {m['accuracy']:.3f} | {m['ece']:.3f} |")
    return lines


def _folds_table(data: Data, preds: pl.DataFrame) -> list[str]:
    games = data.outcome.group_by("series_id").len()
    lines = [
        "| Test month | Train series | Train games | Test games | Log loss | Accuracy |",
        "|---|---|---|---|---|---|",
    ]
    for f in data.folds:
        df = preds.filter(pl.col("fold") == f.name)
        train_games = games.filter(_in(f.train))["len"].sum()
        m = metrics.outcome_metrics(df["y"].to_numpy(), df["p"].to_numpy())
        lines.append(
            f"| {f.name} | {len(f.train)} | {train_games} | {df.height} | {m['log_loss']:.4f} | {m['accuracy']:.3f} |"
        )
    return lines


def _action_rows(res: Results) -> list[str]:
    ref = res.actions[ACTION_REF]
    lines = [
        "| Model | Slice | Actions | Log loss [95% CI] | Δ vs action_global [95% CI] | Top-1 | Top-5 | Top-10 | MRR |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, preds in sorted(res.actions.items()):
        _same_rows(preds, ref, "game_id")
        for label, cond in (
            ("all", pl.lit(value=True)),
            ("picks", pl.col("action") == "pick"),
            ("bans", pl.col("action") == "ban"),
            ("G3+", pl.col("game_number") >= LATE_GAME),
        ):
            df = preds.filter(cond)
            r = ref.filter(cond)
            loss = -np.log(np.clip(df["p_true"].to_numpy(), metrics.EPS, 1))
            ref_loss = -np.log(np.clip(r["p_true"].to_numpy(), metrics.EPS, 1))
            groups = df["series_id"].to_numpy()
            m = metrics.action_metrics(df["p_true"].to_numpy(), df["rank"].to_numpy())
            diff = "—" if name == ACTION_REF else _ci(metrics.paired_bootstrap(loss, ref_loss, groups), 3)
            lines.append(
                f"| `{name}` | {label} | {df.height} | {_ci(metrics.bootstrap_mean(loss, groups), 3)} | {diff} | "
                f"{m['top1']:.3f} | {m['top5']:.3f} | {m['top10']:.3f} | {m['mrr']:.3f} |"
            )
    return lines


def report(model: str, focus: str, data: Data, res: Results) -> str:
    preds = res.outcome[focus]
    holdout = splits.holdout_ids(data.series)
    held_days = splits.series_order(data.series).filter(_in(holdout))["started_at"].dt.strftime("%Y-%m-%d")
    rel = metrics.reliability(preds["y"].to_numpy(), preds["p"].to_numpy())
    lines = [
        f"# Evaluation: `{model}`",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `fele evaluate --model {model}`.",
        "",
        "## Protocol",
        "",
        f"- {data.outcome.height} games / {data.actions.height} draft actions in {data.series.height} series.",
        (
            f"- **Final holdout (locked):** the latest {len(holdout)} series "
            f"({held_days.min()} – {held_days.max()}). Not used here."
        ),
        (
            f"- **Walk-forward folds:** {len(data.folds)} test months ({data.folds[0].name} … {data.folds[-1].name}); "
            "each trains on every earlier series. Splits are by series."
        ),
        "- **95% CIs** resample series (2,000 draws). Δ = model - reference; below 0 means lower (better) loss.",
        "",
        "## Problem A — who wins the game",
        "",
        *_outcome_rows(res),
        "",
        f"### `{focus}` per fold",
        "",
        *_folds_table(data, preds),
        "",
        f"### `{focus}` by slice",
        "",
        *_slices(preds),
        "",
        f"### `{focus}` calibration",
        "",
        "| Predicted | Games | Mean prediction | Blue win rate |",
        "|---|---|---|---|",
        *[f"| {r['lo']:.1f}–{r['hi']:.1f} | {r['n']} | {r['mean_p']:.3f} | {r['rate']:.3f} |" for r in rel],
        "",
        f"### `{focus}` learning curve (most recent share of each fold's training series)",
        "",
        "| Training share | Log loss |",
        "|---|---|",
        *[f"| {r['fraction']:.0%} | {r['log_loss']:.4f} |" for r in res.learning],
        "",
        "## Problem B — which champion is picked or banned next",
        "",
        "Probability over available champions (earlier picks/bans of the game and Fearless-locked champions removed).",
        "",
        *_action_rows(res),
        "",
        "## Reading this",
        "",
        "- A coin flip scores log loss 0.6931. These baselines are the bar: a Phase 8 model is promoted only if its",
        "  Δ CI vs `baseline_elo` is entirely below 0, ECE ≤ 0.05, and it is not worse on the G3+ slice (§5.5).",
        "- Small slices (Cloud9, single months) are descriptive: read their n before their numbers.",
        "",
    ]
    return "\n".join(lines)


def write_report(model: str, text: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{datetime.now(UTC):%Y-%m-%d}-{model}.md"
    path.write_text(text)
    return path
