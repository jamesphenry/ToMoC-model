#!/usr/bin/env python3
"""metrics — log every training/eval pass (the homelab cost + capability ledger).

One SQLite file at benchmarks/passes.db. Three tables:
  passes       run header (what we trained/evaluated)
  pass_metrics per-metric score (route_accuracy, well_formed, per-fn accuracy...)
  pass_meta    free-form key/value (git_commit, data_hash, notes...)

KISS: stdlib sqlite3 only. Optionally mirrors every pass to MLflow
(see wandb_tracker.py) when WANDB_API_URL is set / wandb importable.

The README cost banner + runs.md Totals are regenerated from this DB by
scripts/sync_docs.py, so the docs can never drift from the real numbers.

Usage:
    from metrics import Metrics
    m = Metrics()
    pid = m.new_pass(base_model="smollm-360m", num_cards=120, walltime_s=900)
    m.log_metric(pid, "route_accuracy", 0.97)
    m.log_meta(pid, "git_commit", "d0dd03f")
    m.close()
"""
import os
import sqlite3
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "benchmarks", "passes.db")

# electricity cost tracking (sovereignty metric: $/pass vs API bills)
PRICE_KWH = 0.14          # your rate, USD per kWh
DEFAULT_GPU_WATTS = 90    # P4 draws ~90W over server idle during a GPU pass


class Metrics:
    def __init__(self, path: str = DB_PATH, wandb: bool = True):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init()
        self._wb = None
        if wandb:
            try:
                from wandb_tracker import get_tracker
                self._wb = get_tracker()
            except Exception:
                self._wb = None

    def _init(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS passes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                base_model  TEXT,
                mode        TEXT DEFAULT 'train',
                lora_r      INTEGER,
                lora_alpha  INTEGER,
                epochs      REAL,
                lr          REAL,
                num_cards   INTEGER,
                loss_final  REAL,
                walltime_s  REAL,
                gpu_mem_used_mb REAL,
                gpu_util_pct REAL,
                gpu_watts   REAL,
                cost_usd    REAL,
                status      TEXT DEFAULT 'done'
            );
            CREATE TABLE IF NOT EXISTS pass_metrics (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                pass_id   INTEGER NOT NULL REFERENCES passes(id),
                metric    TEXT NOT NULL,
                value     REAL,
                detail    TEXT
            );
            CREATE TABLE IF NOT EXISTS pass_meta (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                pass_id   INTEGER NOT NULL REFERENCES passes(id),
                key       TEXT NOT NULL,
                value     TEXT
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def compute_cost(walltime_s, gpu_watts=None):
        if walltime_s is None:
            return None
        w = gpu_watts if gpu_watts is not None else DEFAULT_GPU_WATTS
        return round((w / 1000.0) * (walltime_s / 3600.0) * PRICE_KWH, 6)

    @staticmethod
    def gpu_power_watts(default=DEFAULT_GPU_WATTS, samples=3):
        """Measured GPU board power (W). Faithful to smol's 'watts over idle'
        cost model, but sampled from nvidia-smi instead of assumed. Falls back
        to DEFAULT_GPU_WATTS when no GPU/nvidia-smi is present (e.g. a CPU-only
        box). Used to price every pass so the sovereignty cost is MEASURED."""
        try:
            import shutil
            import subprocess
            if shutil.which("nvidia-smi"):
                draws = []
                for _ in range(samples):
                    out = subprocess.check_output(
                        ["nvidia-smi", "--query-gpu=power.draw",
                         "--format=csv,noheader,nounits"],
                        timeout=5).decode().strip().splitlines()
                    for line in out:
                        line = line.strip()
                        if line:
                            draws.append(float(line.split()[0]))
                    time.sleep(0.4)
                if draws:
                    return round(sum(draws) / len(draws), 1)
        except Exception:
            pass
        return default

    def new_pass(self, mode: str = "train", **fields) -> int:
        wt = fields.get("walltime_s")
        # measure real GPU draw at pass start; fall back to assumed 90W
        measured = self.gpu_power_watts()
        watts = fields.get("gpu_watts", measured)
        if wt is not None and "cost_usd" not in fields:
            fields["cost_usd"] = self.compute_cost(wt, watts)
        fields["gpu_watts"] = watts   # persist the (measured or defaulted) wattage
        cols = {"base_model", "mode", "lora_r", "lora_alpha", "epochs", "lr",
                "num_cards", "loss_final", "walltime_s", "gpu_mem_used_mb",
                "gpu_util_pct", "gpu_watts", "cost_usd", "status"}
        f = {k: fields[k] for k in cols if k in fields}
        f["mode"] = mode
        f["created_at"] = datetime.now(timezone.utc).isoformat()
        keys = ", ".join(f.keys())
        ph = ", ".join("?" * len(f))
        cur = self.conn.execute(
            f"INSERT INTO passes ({keys}) VALUES ({ph})", tuple(f.values()))
        self.conn.commit()
        pid = cur.lastrowid
        # mirror to wandb
        if self._wb is not None:
            self._wb.start_run(pid, f)
        return pid

    def log_metric(self, pass_id: int, metric: str, value, detail: str = None):
        self.conn.execute(
            "INSERT INTO pass_metrics (pass_id, metric, value, detail) VALUES (?,?,?,?)",
            (pass_id, metric, value, detail))
        self.conn.commit()
        if self._wb is not None:
            self._wb.log_metric(metric, value, detail)

    def log_meta(self, pass_id: int, key: str, value: str):
        self.conn.execute(
            "INSERT INTO pass_meta (pass_id, key, value) VALUES (?,?,?)",
            (pass_id, key, str(value)))
        self.conn.commit()
        if self._wb is not None:
            self._wb.log_param(key, value)

    def summarize(self, pass_id: int = None):
        if pass_id is None:
            row = self.conn.execute(
                "SELECT id FROM passes ORDER BY id DESC LIMIT 1").fetchone()
            pass_id = row["id"] if row else None
        if pass_id is None:
            print("(no passes yet)")
            return
        p = self.conn.execute("SELECT * FROM passes WHERE id=?", (pass_id,)).fetchone()
        print(f"=== pass {pass_id} ({p['created_at']}) ===")
        for k in ("mode", "base_model", "lora_r", "lora_alpha", "epochs", "lr",
                  "num_cards", "loss_final", "walltime_s", "gpu_mem_used_mb",
                  "gpu_util_pct", "gpu_watts", "cost_usd", "status"):
            if p[k] is not None:
                val = f"${p[k]:.4f}" if k == "cost_usd" else p[k]
                print(f"  {k}: {val}")
        print("  -- metrics --")
        for m in self.conn.execute(
                "SELECT metric, value, detail FROM pass_metrics WHERE pass_id=?",
                (pass_id,)):
            d = f"  ({m['detail']})" if m["detail"] else ""
            print(f"    {m['metric']}: {m['value']}{d}")

    def total_cost(self):
        row = self.conn.execute(
            "SELECT SUM(cost_usd) t, COUNT(*) n, SUM(walltime_s) wt "
            "FROM passes WHERE cost_usd IS NOT NULL").fetchone()
        return (row["t"] or 0.0, row["n"] or 0, row["wt"] or 0.0)

    def cost_by_mode(self):
        """Per-mode (train/eval) cost rollup — see where the electricity goes."""
        rows = self.conn.execute(
            "SELECT mode, SUM(cost_usd) t, COUNT(*) n, SUM(walltime_s) wt "
            "FROM passes WHERE cost_usd IS NOT NULL GROUP BY mode").fetchall()
        return {r["mode"]: (r["t"] or 0.0, r["n"], r["wt"] or 0.0) for r in rows}

    def cost_report(self):
        total, n, wt = self.total_cost()
        by_mode = self.cost_by_mode()
        print("=== homelab cost ===")
        print(f"  passes with cost: {n}")
        print(f"  total GPU time:   {wt/3600:.3f} h")
        print(f"  total cost:       ${total:.4f}  (@ ${PRICE_KWH}/kWh, "
              f"measured GPU draw ~{DEFAULT_GPU_WATTS}W over idle)")
        if n:
            print(f"  avg cost/pass:    ${total/n:.5f}")
        if by_mode:
            print("  -- by mode --")
            for mode, (t, m, mwt) in sorted(by_mode.items()):
                print(f"    {mode:6s}: ${t:.4f}  ({m} passes, {mwt/3600:.3f} GPU-h)")

    def close(self):
        if self._wb is not None:
            self._wb.end_run()
        self.conn.close()

    @staticmethod
    def banner_line():
        """Return (cost_usd, n_passes, gpu_hours) for the README banner."""
        m = Metrics(wandb=False)
        t, n, wt = m.total_cost()
        m.close()
        return t, n, wt / 3600.0


if __name__ == "__main__":
    import tempfile, os as _os
    tmp = tempfile.mktemp(suffix=".db")
    m = Metrics(tmp, wandb=False)
    pid = m.new_pass(mode="eval", base_model="smollm-360m", num_cards=120,
                     walltime_s=300, gpu_watts=90)
    for k, v in [("route_accuracy", 0.97), ("well_formed", 0.99),
                 ("over_call", 0.02), ("under_call", 0.01)]:
        m.log_metric(pid, k, v)
    m.log_meta(pid, "git_commit", "smoke")
    m.summarize(pid)
    m.cost_report()
    m.close()
    _os.remove(tmp)
    print("(smoke test passed)")
