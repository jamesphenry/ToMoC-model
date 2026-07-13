#!/usr/bin/env python3
"""mlflow_tracker — optional MLflow integration for run/asset tracking.

Designed to be OPTIONAL. If MLflow is not installed or MLFLOW_TRACKING_URI is
not set, every method is a silent no-op so the rest of the pipeline never breaks
(the SQLite metrics store is the always-on source of truth).

When enabled (set MLFLOW_TRACKING_URI, e.g. a local file store or a server),
every pass logs its params + metrics to an MLflow run, and adapters/logs are
logged as artifacts. This satisfies the "track project + assets in MLflow" goal
without making MLflow a hard dependency.

Enable:
  export MLFLOW_TRACKING_URI=file:///home/aec/tomac/mlruns      # local, zero infra
  # or a server: export MLFLOW_TRACKING_URI=http://localhost:5000
  python scripts/train_router.py ...        # artifacts auto-logged

Graceful degradation: import failure -> get_tracker() returns a DummyTracker.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


class DummyTracker:
    """No-op tracker used when MLflow is unavailable."""
    def __init__(self):
        self.enabled = False

    def start_run(self, *a, **k):
        return None

    def log_metric(self, *a, **k):
        return None

    def log_metrics(self, *a, **k):
        return None

    def log_param(self, *a, **k):
        return None

    def set_tags(self, *a, **k):
        return None

    def log_artifact(self, *a, **k):
        return None

    def end_run(self, *a, **k):
        return None


_TRACKER = None


def get_tracker():
    global _TRACKER
    if _TRACKER is not None:
        return _TRACKER
    try:
        import mlflow  # noqa
    except Exception:
        _TRACKER = DummyTracker()
        return _TRACKER
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        # Default to a local SQLite backend inside the repo (gitignored).
        # mlflow 3.x deprecated the file store; sqlite is zero-infra + sovereign.
        uri = "sqlite:///" + os.path.join(ROOT, "mlflow.db")
    try:
        mlflow.set_tracking_uri(uri)
        _TRACKER = _RealTracker(mlflow, uri)
    except Exception:
        _TRACKER = DummyTracker()
    return _TRACKER


class _RealTracker:
    def __init__(self, mlflow, uri):
        self.mlflow = mlflow
        self.uri = uri
        self.enabled = True
        self._run = None

    def start_run(self, pass_id, fields: dict):
        # Idempotent: if a run is already open (e.g. the training script opened
        # one to stream the loss curve), reuse it and just add the params —
        # don't orphan the live run by nesting a second one.
        if self._run is None:
            exp = self.mlflow.get_experiment_by_name("tomac")
            if exp is None:
                # sqlite backend needs an explicit local artifact dir
                art = os.path.join(ROOT, "mlartifacts")
                os.makedirs(art, exist_ok=True)
                exp_id = self.mlflow.create_experiment(
                    "tomac", artifact_location="file://" + art)
            else:
                exp_id = exp.experiment_id
            self._run = self.mlflow.start_run(
                run_name=f"pass-{pass_id}", experiment_id=exp_id)
        for k, v in fields.items():
            if v is None:
                continue
            try:
                self.mlflow.log_param(k, v)
            except Exception:
                pass

    def log_metric(self, metric, value, detail=None, step=None):
        if self._run is None:
            return
        try:
            self.mlflow.log_metric(metric, float(value), step=step)
            if detail:
                self.mlflow.set_tag(f"metric:{metric}", str(detail))
        except Exception:
            pass

    def log_metrics(self, metrics: dict, step=None):
        if self._run is None:
            return
        for k, v in metrics.items():
            try:
                self.mlflow.log_metric(k, float(v), step=step)
            except Exception:
                pass

    def log_param(self, key, value):
        if self._run is None:
            return
        try:
            self.mlflow.log_param(key, value)
        except Exception:
            pass

    def set_tags(self, tags: dict):
        if self._run is None:
            return
        for k, v in tags.items():
            try:
                self.mlflow.set_tag(k, str(v))
            except Exception:
                pass

    def log_artifact(self, path):
        if self._run is None or not os.path.exists(path):
            return
        try:
            self.mlflow.log_artifact(path)
        except Exception:
            pass

    def end_run(self):
        if self._run is not None:
            try:
                self.mlflow.end_run()
            except Exception:
                pass
            self._run = None


if __name__ == "__main__":
    t = get_tracker()
    print("mlflow enabled:", t.enabled)
    if t.enabled:
        print("tracking uri:", t.uri)
