#!/usr/bin/env python3
"""sync_docs — regenerate README cost banner + runs.md from benchmarks/passes.db.

The cost numbers live in the DB, not in prose. This script pushes them into:
  - README.md  : the `> Cost to date:` banner near the top.
  - runs.md    : the full per-pass + per-mode cost mirror (homelab ledger).

Running this after every pass keeps the docs honest (the AGENTS.md guardrail:
"don't let the README cost banner drift"). No GPU, no network.

Usage:
  python scripts/sync_docs.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from metrics import Metrics, PRICE_KWH, DEFAULT_GPU_WATTS

README = os.path.join(ROOT, "README.md")
RUNS = os.path.join(ROOT, "runs.md")


def fmt_money(x):
    return f"${x:.4f}"


def build_readme_banner(total, n, gpu_h):
    return (f"> Cost to date: **{fmt_money(total)}** across {n} GPU passes "
            f"({gpu_h:.2f} GPU-hours) @ ${PRICE_KWH}/kWh, ~{DEFAULT_GPU_WATTS}W "
            f"over idle. Sovereignty metric vs API bills.")


def update_readme_banner(text, banner):
    # replace an existing "> Cost to date: ..." line, else prepend after title
    pat = re.compile(r"^> Cost to date:.*$", re.M)
    if pat.search(text):
        return pat.sub(lambda m: banner, text)
    # insert right after the first '# ' title block
    return re.sub(r"(^# .*?\n)", lambda m: m.group(1) + banner + "\n", text, count=1)


def build_runs_md(m: Metrics):
    total, n, wt = m.total_cost()
    by_mode = m.cost_by_mode()
    lines = ["# runs.md — every training / eval pass, with cost breakdown", ""]
    lines.append("> Auto-logged in `benchmarks/passes.db` via `scripts/metrics.py`.")
    lines.append("> This file is a human-readable mirror; regenerate with "
                 "`python scripts/sync_docs.py`.")
    lines.append(f"> Cost model: `watts/1000 * hours * ${PRICE_KWH}/kWh`, "
                 f"watts = measured GPU draw (~{DEFAULT_GPU_WATTS}W over idle).")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|--------|-------|")
    lines.append(f"| total cost | **{fmt_money(total)}** |")
    lines.append(f"| total GPU time | {wt/3600:.3f} h |")
    if n:
        lines.append(f"| avg cost / pass | {fmt_money(total/n)} |")
    lines.append(f"| electricity rate | ${PRICE_KWH} / kWh |")
    lines.append(f"| assumed draw | {DEFAULT_GPU_WATTS} W over idle |")
    lines.append("")
    if by_mode:
        lines.append("## Cost by mode")
        lines.append("| mode | passes | sum cost $ | sum GPU-h |")
        lines.append("|------|--------|-----------|-----------|")
        for mode, (t, mn, mwt) in sorted(by_mode.items()):
            lines.append(f"| {mode} | {mn} | {fmt_money(t)} | {mwt/3600:.3f} |")
        lines.append("")
    lines.append("## Per-pass detail")
    lines.append("Sorted by pass id. `cost` is electricity only. `wall` = wall-clock seconds.")
    lines.append("")
    lines.append("| pass | when (UTC) | mode | base | cards | loss | wall (s) | GPU W | cost $ |")
    lines.append("|------|-----------|------|------|-------|------|----------|-------|--------|")
    rows = m.conn.execute(
        "SELECT id, created_at, mode, base_model, num_cards, loss_final, "
        "walltime_s, gpu_watts, cost_usd FROM passes ORDER BY id").fetchall()
    for r in rows:
        when = (r["created_at"] or "")[:16].replace("T", " ")
        lines.append(
            f"| {r['id']} | {when} | {r['mode']} | {r['base_model']} | "
            f"{r['num_cards'] or '-'} | {r['loss_final'] if r['loss_final'] is not None else '-'} | "
            f"{r['walltime_s'] if r['walltime_s'] is not None else '-'} | "
            f"{r['gpu_watts'] if r['gpu_watts'] is not None else '-'} | "
            f"{fmt_money(r['cost_usd']) if r['cost_usd'] is not None else '-'} |")
    lines.append("")
    return "\n".join(lines)


def main():
    m = Metrics(mlflow=False)
    total, n, wt = m.total_cost()
    banner = build_readme_banner(total, n, wt / 3600.0)

    # README banner
    if os.path.exists(README):
        cur = open(README, encoding="utf-8").read()
        new = update_readme_banner(cur, banner)
        if new != cur:
            open(README, "w", encoding="utf-8").write(new)
            print("  updated README.md cost banner")
        else:
            print("  README.md banner unchanged")
    else:
        print("  (README.md missing — skipped)")

    # runs.md
    runs_md = build_runs_md(m)
    open(RUNS, "w", encoding="utf-8").write(runs_md)
    print(f"  wrote runs.md ({n} passes, {fmt_money(total)} total)")
    m.close()


if __name__ == "__main__":
    main()
