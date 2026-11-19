# pyright: basic, reportMissingImports=false
"""Optional MLflow tracking. MLflow is in the `ml` extra (not installed in CI), so it's imported lazily and this
one file is type-checked in basic mode."""

from pathlib import Path

from fele.config import settings
from fele.eval import metrics
from fele.eval.run import Results


def log_mlflow(model: str, res: Results, report_path: Path) -> str | None:
    """One MLflow run per evaluation in data_local/mlflow.db (metrics + the report). None if MLflow isn't installed."""
    try:
        import mlflow  # noqa: PLC0415 - heavy and optional
    except ImportError:
        return None
    mlflow.set_tracking_uri(f"sqlite:///{settings().local() / 'mlflow.db'}")
    mlflow.set_experiment("fele-evaluate")
    with mlflow.start_run(run_name=model) as run:
        mlflow.log_param("model", model)
        for name, preds in res.outcome.items():
            m = metrics.outcome_metrics(preds["y"].to_numpy(), preds["p"].to_numpy())
            mlflow.log_metrics({f"{name}.{k}": v for k, v in m.items() if k != "n"})
        for name, preds in res.actions.items():
            m = metrics.action_metrics(preds["p_true"].to_numpy(), preds["rank"].to_numpy())
            mlflow.log_metrics({f"{name}.{k}": v for k, v in m.items() if k != "n"})
        mlflow.log_artifact(str(report_path))
        return str(run.info.run_id)
