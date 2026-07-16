#!/usr/bin/env python3
"""wandb_tracker — optional Weights & Biases integration for tomac.

Replaces mlflow_tracker. Same no-op contract: if wandb is not installed or the
self-hosted server is not configured (env not set / not logged in), every
method is a silent no-op so the pipeline never breaks. The SQLite metrics
store (metrics.py) stays the always-on source of truth.

The user runs a SEPARATE wandb server container. This client lights up when:
  export WANDB_API_URL=http://<wandb-container>:8080   # self-hosted base URL
  export WANDB_ENTITY=tomac                              # your team/entity
  # WANDB_PROJECT defaults to "tomac"
and `wandb` is pip-installed + `wandb login` (or WANDB_API_KEY) is done against
that server. No code change needed in the pipeline when the container is up.

Graceful degradation: import/login failure -> get_tracker() returns DummyTracker.
"""
import os
import sys
import time
import threading
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PROJECT = os.environ.get("WANDB_PROJECT", "tomac")
ENTITY = os.environ.get("WANDB_ENTITY")  # None -> wandb default
API_URL = os.environ.get("WANDB_API_URL")  # self-hosted base url


class DummyTracker:
    """No-op tracker used when wandb is unavailable / unconfigured."""
    enabled = False

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

    def log_dataset(self, *a, **k):
        return None

    def link_artifact(self, *a, **k):
        return None

    def create_registry(self, *a, **k):
        return None

    def end_run(self, *a, **k):
        return None


_TRACKER = None


def _warn_dummy(reason: str):
    """Loud, un-missable warning that tracking is a no-op (see BUG-008).

    A silent DummyTracker once let a full training run (pass-54) complete
    WITHOUT ever reaching W&B. Never again: if the caller wanted tracking and
    we can't provide it, say so on stderr. Set TOMAC_REQUIRE_WANDB=1 to make
    this a hard error instead (recommended for real training launches).
    """
    msg = (
        f"\n{'!' * 68}\n"
        f"!! WANDB TRACKING DISABLED — this run will NOT appear in W&B.\n"
        f"!! Reason: {reason}\n"
        f"!! Fix: export WANDB_API_URL=<server> WANDB_ENTITY=<entity> and\n"
        f"!!      `wandb login` (or set WANDB_API_KEY) before launching.\n"
        f"!! (BUG-008: a silent no-op tracker previously lost pass-54.)\n"
        f"{'!' * 68}\n"
    )
    print(msg, file=sys.stderr, flush=True)
    if os.environ.get("TOMAC_REQUIRE_WANDB", "").strip().lower() in ("1", "true", "yes"):
        raise RuntimeError(
            "TOMAC_REQUIRE_WANDB is set but wandb tracking is unavailable: "
            + reason
        )


def get_tracker():
    global _TRACKER
    if _TRACKER is not None:
        return _TRACKER
    try:
        import wandb  # noqa
    except Exception as e:
        _warn_dummy(f"wandb not importable ({type(e).__name__}: {e})")
        _TRACKER = DummyTracker()
        return _TRACKER
    # wandb installed; only go live if a server URL + entity are configured
    if not API_URL:
        _warn_dummy("WANDB_API_URL is not set")
        _TRACKER = DummyTracker()
        return _TRACKER
    try:
        _TRACKER = _RealTracker(wandb)
    except Exception as e:
        _warn_dummy(f"_RealTracker init failed ({type(e).__name__}: {e})")
        _TRACKER = DummyTracker()
    return _TRACKER


class _RealTracker:
    def __init__(self, wandb):
        self.wandb = wandb
        self.enabled = True
        self._run = None
        self._sampler = None          # background sys-metrics thread
        self._stop = threading.Event()
        # point the client at the self-hosted server
        if API_URL:
            try:
                wandb.setup(settings=wandb.Settings(base_url=API_URL))
            except Exception:
                pass

    def start_run(self, pass_id, fields: dict, name: "str | None" = None):
        if self._run is not None:
            # idempotent: reuse an open run (training script opens one to
            # stream the loss curve) and just push config.
            for k, v in fields.items():
                if v is not None:
                    try:
                        self._run.config.update({k: v}, allow_val_change=True)
                    except Exception:
                        pass
            return
        cfg = {k: v for k, v in fields.items() if v is not None}
        # display name = "<pass_id> - <purpose>" when a purpose is supplied,
        # else the legacy "pass-<id>". The id stays the stable pass_id so
        # re-opened runs merge instead of spawning duplicates.
        display = name if name else f"pass-{pass_id}"
        self._run = self.wandb.init(
            project=PROJECT, entity=ENTITY, name=display,
            id=str(pass_id), resume="allow", config=cfg,
        )
        # give system metrics their own wall-clock x-axis so the async sampler
        # never collides with the training loop's step=epoch loss curve.
        try:
            self._run.define_metric("sys/elapsed_s")
            self._run.define_metric("sys/*", step_metric="sys/elapsed_s")
        except Exception:
            pass
        self._t0 = time.time()
        self._start_sampler()

    # ---- deterministic system-metrics sampler (GPU + CPU + RAM) --------------
    # W&B's built-in monitor needs a long run and can be flaky self-hosted, so
    # we sample explicitly: GPU via nvidia-smi, CPU/RAM via psutil. Logged under
    # sys/* every SAMPLE_SECS so the graphs always populate.
    SAMPLE_SECS = 5.0

    def _start_sampler(self):
        if self._sampler is not None:
            return
        self._stop.clear()
        self._sampler = threading.Thread(target=self._sample_loop, daemon=True)
        self._sampler.start()

    def _sample_loop(self):
        try:
            import psutil
        except Exception:
            psutil = None
        while not self._stop.wait(self.SAMPLE_SECS):
            m = {}
            m.update(self._gpu_sample())
            if psutil is not None:
                try:
                    m["sys/cpu_pct"] = psutil.cpu_percent(interval=None)
                    vm = psutil.virtual_memory()
                    m["sys/ram_pct"] = vm.percent
                    m["sys/ram_used_mb"] = round(vm.used / (1024 * 1024), 1)
                except Exception:
                    pass
            if m and self._run is not None:
                try:
                    m["sys/elapsed_s"] = round(time.time() - self._t0, 1)
                    self._run.log(m)
                except Exception:
                    pass

    @staticmethod
    def _gpu_sample():
        try:
            out = subprocess.check_output(
                ["nvidia-smi",
                 "--query-gpu=power.draw,utilization.gpu,memory.used,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                timeout=5).decode().strip().splitlines()
            if not out:
                return {}
            # first GPU (P4)
            pw, util, mem, temp = [x.strip() for x in out[0].split(",")]
            return {
                "sys/gpu_power_w": float(pw),
                "sys/gpu_util_pct": float(util),
                "sys/gpu_mem_used_mb": float(mem),
                "sys/gpu_temp_c": float(temp),
            }
        except Exception:
            return {}

    def log_metric(self, metric, value, detail=None, step=None):
        if self._run is None:
            return
        try:
            self._run.log({metric: float(value)}, step=step)
            if detail:
                self._run.summary[f"{metric}:detail"] = str(detail)
        except Exception:
            pass

    def log_metrics(self, metrics: dict, step=None):
        if self._run is None:
            return
        try:
            self._run.log({k: float(v) for k, v in metrics.items()}, step=step)
        except Exception:
            pass

    def log_param(self, key, value):
        if self._run is None:
            return
        try:
            self._run.config.update({key: value}, allow_val_change=True)
        except Exception:
            pass

    def set_tags(self, tags: dict):
        if self._run is None:
            return
        try:
            self._run.tags = tuple(str(v) for v in tags.values())
        except Exception:
            pass

    def log_artifact(self, path, name=None, type="model", link_registry=True):
        """Log a file OR dir as a VERSIONED wandb.Artifact (name:v0, v1, ...).
        If link_registry and a registry collection is configured, also links the
        artifact into the org registry (central model governance)."""
        if self._run is None or not os.path.exists(path):
            return
        try:
            art_name = name or os.path.basename(path.rstrip("/")) or "artifact"
            art = self.wandb.Artifact(name=art_name, type=type)
            if os.path.isdir(path):
                art.add_dir(path)
            else:
                art.add_file(path)
            self._run.log_artifact(art)
            if link_registry:
                self.link_artifact(art, kind=type)
        except Exception:
            pass

    def link_artifact(self, artifact, kind="model", collection=None):
        """Link a logged artifact into the org's registry collection.

        Two collections, by artifact kind:
          model   -> $TOMAC_REGISTRY_MODEL_COLL   (default 'tomac-models')
          dataset -> $TOMAC_REGISTRY_DATA_COLL    (default 'tomac-datasets')
        On this self-hosted server the collection's full name is
        `wandb-registry-<collection>` (entity 'server'), and a cravingpine
        run can link to it. No-op if unset or if the server rejects the link."""
        coll = collection
        if coll is None:
            coll = (os.environ.get("TOMAC_REGISTRY_MODEL_COLL") if kind == "model"
                    else os.environ.get("TOMAC_REGISTRY_DATA_COLL"))
        coll = coll or ("tomac-models" if kind == "model" else "tomac-datasets")
        if self._run is None:
            return
        try:
            self._run.link_artifact(artifact, f"wandb-registry-{coll}")
        except Exception:
            pass

    def create_registry(self, visibility="organization"):
        """Create the model + dataset registry collections if missing.
        Org = entity 'server' on this self-hosted server. No-op if present."""
        for coll in (os.environ.get("TOMAC_REGISTRY_MODEL_COLL", "tomac-models"),
                     os.environ.get("TOMAC_REGISTRY_DATA_COLL", "tomac-datasets")):
            try:
                api = self.wandb.Api()
                api.create_registry(name=coll, visibility=visibility)
            except Exception:
                pass

    def log_dataset(self, path, name=None, context="training"):
        """Log a dataset file/dir as a versioned artifact (type=dataset) and
        link it into the datasets registry collection."""
        if self._run is None or not os.path.exists(path):
            return
        try:
            art_name = name or os.path.basename(path.rstrip("/")) or "dataset"
            art = self.wandb.Artifact(name=art_name, type="dataset")
            if os.path.isdir(path):
                art.add_dir(path)
            else:
                art.add_file(path)
            self._run.log_artifact(art)
            self.link_artifact(art, kind="dataset")
        except Exception:
            pass

    def end_run(self):
        # stop the sampler thread before finishing the run
        self._stop.set()
        if self._sampler is not None:
            try:
                self._sampler.join(timeout=self.SAMPLE_SECS + 2)
            except Exception:
                pass
            self._sampler = None
        if self._run is not None:
            try:
                self._run.finish()
            except Exception:
                pass
            self._run = None


if __name__ == "__main__":
    t = get_tracker()
    print("wandb enabled:", getattr(t, "enabled", False))
    if getattr(t, "enabled", False):
        print("project:", PROJECT, "entity:", ENTITY, "api_url:", API_URL)
