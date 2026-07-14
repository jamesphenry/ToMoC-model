---
title: Foundations: thesis, scaffold, first-run plan
project: tomac
date: 2026-07-13
policy:
  - entries are append-only; do NOT rewrite an existing entry
  - corrections / changes go as footnotes ([^n]) at the bottom, never inline rewrites
  - every major model-size change gets its own dated entry citing the forcing bug/metric
---

# 2026-07-13 — foundations

> The origin entry: the thesis, the from-scratch decision, the Phase 0/1 scaffold,
> and the (still-empty) numbers table. Bugs live in [../bugs/](../bugs/README.md);
> phase plans in [../plans/](../plans). This file is the STORY.

## The thesis (why we're here)
Build a *tiny* LLM that is a **smart function router**: read a request, decide
which function to call and with what args, then let sovereign disk-backed tools
do the work. **Functions ARE its knowledge** — capability scales by adding
functions, not parameters. Endgame = a homelab assistant whose intelligence
lives in its toolset, not its weights. Sovereignty: homelab-only, sandboxed
execution, no external model APIs at inference.

**From-scratch decision (2026-07-13):** train the router from **random init**,
NOT LoRA on a pretrained base. The routing grammar is tiny (emit
`TOOL <name> <json>`), so a small char-level transformer learns it without
baking in world knowledge. User directive supersedes the original smollm-base
plan. See AGENTS.md "NO pretrained base".

## Timeline of the build

### Phase 0 — foundations (DONE)
- Repo scaffolded clean: `functions/` (registry = knowledge + executors),
  `scripts/` (train/eval/serve/metrics), `data/`, `wiki/`. MIT licensed,
  `origin` = `git@github.com:jamesphenry/ToMoC-model.git`. Identity
  `James Henry <james.phenry@gmail.com>`.
- **Function registry as the knowledge**: `functions/registry.json` holds every
  routable function with params + gold `examples`. Training data is SYNTHESIZED
  from it (`build_cards.py`) — adding a function = adding routable capability
  with zero model code changes.
- **Sovereign executors**: `functions/executors.py`. `compute` runs in an
  AST-scanned, isolated subprocess (no imports / `open` / dunders / network,
  CPU rlimit + timeout). `remind_me` is GATED (`proposed_write`, never mutates
  disk until a human approves). Reads (`wiki_read`, `get_time`, `unit_convert`)
  are pure.
- **Shared primitive**: `scripts/tomac_common.py` — the `CUE`, `build_prompt()`,
  and a TOLERANT `parse_call()` (recovers fn name from truncated JSON). One
  source of truth for train + eval so the habit transfers (BUG-002/003 designed
  out).
- **From-scratch model**: `scripts/model_scratch.py` — a char-level pre-norm
  Transformer (default ~3M params: d_model=256, 6 layers, 8 heads). Vocabulary
  = characters seen in cards + CUE. Saves `model.pt` + `config.json` +
  `tokenizer.json`. Verified: forward pass, char-generate, save/load roundtrip.
- **Metrics + MLflow + COST**: `scripts/metrics.py` logs every pass (route
  metrics, walltime, GPU mem, electricity $) to `benchmarks/passes.db`; cost
  model mirrors smol (`watts/1000 * hours * $0.14/kWh`) but reads **measured**
  GPU watts from `nvidia-smi` instead of a constant assumption. `mlflow_tracker.py`
  mirrors runs + checkpoint artifacts to MLflow when `MLFLOW_TRACKING_URI` is set
  (optional, degrades to no-op). `sync_docs.py` rewrites the README + wiki cost
  banner from the ledger. `probe_env.py` verifies the env incl. a scratch-model
  shape check.
- **Env**: uv venv (py3.13) with torch 2.5.1+cu121 + transformers/peft/trl/
  datasets/accelerate/mlflow. P4 8 GB GPU verified. `probe_env.py` passes.
- **Handler self-test** (`functions/executors.py` via /tmp ad-hoc verify): all 6
  handlers behave; dangerous `compute` input fails safe; `remind_me` leaves NO
  file on disk; wiki miss returns a clean verdict.
- **Verified (CPU, 27/27 ad-hoc checks)**: core logic (cue, tolerant parser
  incl. truncated JSON), registry, executors, cost engine, and the scratch model
  forward/generate/save-load all pass before any GPU work.

### Phase 1 — router habit (IN PROGRESS — GPU PAUSED for discussion)
- Plan: synth cards from the registry, train the scratch model, measure
  `route_accuracy` vs a random-init floor, then push toward the smallest viable
  model (d_model/n_layers sweep).
- Detailed plan: [../plans/phase1-router-habit.md](../plans/phase1-router-habit.md).
- **No GPU run yet.** Per user directive ("before gpu is hit pause for
  discussion"), the training/eval steps are written and CPU-verified but not
  executed. First real run will be logged here as pass 1 (train) + pass 2 (eval).

## The numbers (passes.db, honest)
*To be populated by the first training/eval runs. Every pass logs: base model
(none/random-init), mode (train_scratch/eval), epochs/lr, num_cards, loss,
walltime, GPU mem, cost_usd, and the routing metrics (route_accuracy,
well_formed, over_call, under_call, per-function accuracy).*

| pass | what | base | route_acc | well_formed | over/under | loss | walltime | cost |
|------|------|------|-----------|-------------|------------|------|----------|------|
| — | TRAIN scratch/1 | (random) | — | — | — | _TBD_ | _TBD_ | _TBD_ |
| — | eval scratch/1 | (random) | _TBD_ | _TBD_ | _TBD_ | — | _TBD_ | _TBD_ |

## Key findings (the lessons)
*Captured as we go — same discipline as smol: verify changed code before claiming
done; diagnose before fixing; keep negative results.*

1. _TBD after first run._

## Where this leaves the thesis
A tiny model trained from scratch can learn to *route* requests to sovereign
executors, rather than doing the work in-weights. `tomac` pushes the smol thesis
(2 tools @ 360M) to N typed functions with JSON args — now from random init, no
pretrained base. Open questions after Phase 1: how small can the transformer get
before routing quality collapses, and does char-level (vs a BPE tokenizer) hurt
JSON well-formedness enough to matter?[^1]

[^1]: **Amendment (2026-07-14).** The "how small can it get" open question is now
    partly answered by BUG-007: the original ~2.3M (d192/4L) floor *did* collapse
    into degenerate looping under live decode (not just eval), so routing quality
    collapsed below that size in practice — prompting the bump to `baseline-big`
    (10.9M, see [2026-07-14-capacity-bump.md](2026-07-14-capacity-bump.md)). Entry
    body left intact per the append-only journal policy; this note is a footnote,
    not a rewrite.
