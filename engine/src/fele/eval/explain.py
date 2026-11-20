# pyright: basic, reportMissingImports=false
"""Interpretability for the Phase 8 candidates, fitted on all development series (never the holdout).

- linear outcome models: standardised coefficients (Elo is unpenalised, the rest shrunk);
- LightGBM: mean |SHAP| per feature (SHAP is in the `ml` extra; skipped when missing);
- hierarchical Bayes: posterior scales of each block and the largest champion effects;
- conditional logit (draft actions): feature weights.
"""

from importlib.util import find_spec

import numpy as np
import polars as pl

from fele.eval import splits
from fele.eval.run import Data
from fele.models.action import FEATURE_NAMES, ConditionalLogit
from fele.models.outcome import L2, L3, LGBM_GRID, LogisticFeatures, Sk, matrix


def dev_rows(data: Data, frame: pl.DataFrame) -> pl.DataFrame:
    holdout = splits.holdout_ids(data.series)
    return frame.filter(~pl.col("series_id").is_in(list(holdout)))


def _table(title: str, names: list[str], values: np.ndarray, header: str) -> list[str]:
    order = np.argsort(-np.abs(values))
    return [
        f"### {title}",
        "",
        f"| Feature | {header} |",
        "|---|---|",
        *[f"| `{names[i]}` | {float(values[i]):+.3f} |" for i in order],
        "",
    ]


def explain(data: Data) -> str:
    train = dev_rows(data, data.outcome)
    lines = ["# Model explanations (fitted on all development series)", ""]
    for cols, name in ((L2, "logit_l2"), (L3, "logit_l3")):
        m = LogisticFeatures(cols)
        m.fit(train)
        lines += _table(
            f"`{name}` standardised coefficients (λ = {m.clf.lam:g})", list(cols), m.clf.coefficients(), "Coefficient"
        )
    lgbm = Sk("lgbm", L3, LGBM_GRID)
    lgbm.fit(train)
    if find_spec("shap") is not None:
        import shap  # noqa: PLC0415 - optional

        x = matrix(train, L3)
        values = shap.TreeExplainer(lgbm.clf.booster()).shap_values(x)
        values = values[1] if isinstance(values, list) else values
        lines += _table("`lgbm` mean |SHAP| (log-odds)", list(L3), np.abs(values).mean(axis=0), "Mean abs SHAP")
    else:
        lines += ["_SHAP not installed (uv sync --extra ml): LightGBM explanation skipped._", ""]
    if find_spec("pymc") is not None:
        from fele.models.bayes import BayesHierarchical  # noqa: PLC0415 - optional

        bayes = BayesHierarchical()
        bayes.fit(train)
        lines += [
            "### `bayes_hier` posterior",
            "",
            (
                f"- Posterior mean scales: draft features {bayes.scales['s_b']:.3f}, champion effects "
                f"{bayes.scales['s_theta']:.3f}, team effects beyond Elo {bayes.scales['s_u']:.3f} (log-odds)."
            ),
            f"- Elo coefficient (standardised): {bayes.b_elo.mean():+.3f} ± {bayes.b_elo.std():.3f}.",
            "",
        ]
        theta = bayes.theta.mean(axis=0)
        top = np.argsort(-np.abs(theta))[:10]
        lines += ["| Champion | Effect (log-odds) | Posterior sd |", "|---|---|---|"]
        lines += [f"| {bayes.vocab[i]} | {theta[i]:+.3f} | {bayes.theta[:, i].std():.3f} |" for i in top]
        lines += [""]
    else:
        lines += ["_PyMC not installed: Bayesian explanation skipped._", ""]
    act_train = dev_rows(data, data.actions)
    clogit = ConditionalLogit()
    clogit.fit(act_train, data.act)
    lines += _table(f"`action_clogit` weights (λ = {clogit.lam_used})", list(FEATURE_NAMES), clogit.w, "Weight")
    return "\n".join(lines)
