# Plan: Phase 0 — Foundations

**Goal:** a clean, reproducible repo where "knowledge = function registry" and
every run is tracked. No GPU work required to complete this phase.

## Steps
1. [x] Repo scaffold (`git init`, identity `James Henry <james.phenry@gmail.com>`,
       `origin` = `git@github.com:jamesphenry/ToMoC-model.git`, branch `main`).
2. [x] `.gitignore` (artifacts: `adapters/`, `models/`, `logs/`,
       `benchmarks/*.db`, `mlruns/`, `.venv/`).
3. [x] `LICENSE` (MIT).
4. [x] `functions/registry.json` — 6 seed functions with params + gold examples.
5. [x] `functions/registry.py` — loader (`names()`, `by_name()`, `functions()`).
6. [x] `functions/executors.py` — sovereign handlers:
       - `compute`: AST-scanned, `-I` subprocess, CPU rlimit + timeout.
       - `get_time`, `unit_convert`, `wiki_read`: pure reads.
       - `remind_me`: GATED `proposed_write` (never mutates disk).
       - `answer_direct`: no-op (no-tool class).
7. [x] `scripts/tomac_common.py` — `CUE`, `build_prompt()`, `parse_call()`
       (tolerant JSON). Single source of truth for train + eval.
8. [x] `scripts/metrics.py` — SQLite ledger (passes/metrics/meta) + cost calc.
9. [x] `scripts/mlflow_tracker.py` — optional MLflow mirror (no-op if absent).
10. [x] `scripts/probe_env.py` — env verification.
11. [x] `scripts/build_cards.py` — synth cards from registry (gold + chit-chat).
12. [x] `scripts/train_router.py`, `eval_router.py`, `router_server.py` — pipeline.
13. [x] Docs: `README.md` (homelabber), `AGENTS.md`, `wiki/BUGS.md`,
        `wiki/JOURNAL.md`, `wiki/plans/*`.
14. [x] `uv` venv install (torch cu121 + stack + mlflow); `probe_env.py` passes.

## Definition of done
- `python scripts/probe_env.py` reports OK for torch/CUDA/stack/registry.
- `functions/executors.py` `__main__` self-test runs all handlers cleanly.
- `python scripts/build_cards.py` writes `data/raw/cards.jsonl` with a balanced
  mix of tool + no-tool cards.
- Repo is clean, documented, and ready to push.
