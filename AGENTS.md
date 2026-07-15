# AGENTS.md — tomac checkpoint

> Resume-point for an AI/agent session. Not a spec; the living build narrative
> is `wiki/journal/` (dated entries + README index); bugs in `wiki/bugs/`
> (one file per bug + README index); detailed plans in `wiki/plans/`.
> Per-pass metrics + cost in `benchmarks/passes.db`.
>
> **Agent memories & local instructions:** read the untracked, gitignored
> `AGENTS.local.md` at the repo root at session start (working style, W&B/Ollama
> config, repo conventions, identity, UI prefs). It is private/local-only.

## What this project is
Train a *tiny* LLM (from **scratch** — random init, NO pretrained base) to be a
**function router**: read a request, emit `TOOL <name> <json-args>` when a tool
is needed, else answer directly. Generalizes the sibling `smol` project
(router to 2 tools) to **N typed functions**. Thesis: *functions ARE its
knowledge*; the router owns the decision of *where capability lives* — not the
capability itself. Sovereignty: homelab-only, sandboxed execution, no external
model APIs at inference.

**From-scratch decision (v0):** user explicitly rejected pretrained bases
(smol's 360M etc.). The router needs only the small routing grammar, not world
knowledge, so a tiny char-level transformer (scripts/model_scratch.py) is
trained from random init on a Tesla P4 in minutes. No LoRA, no tokenizer
dependency.

## Current state (scaffolded, v1 training pending — GPU PAUSED for discussion)
- **Function registry = the knowledge** (`functions/registry.json`): 6 functions
  seeded — `compute`, `get_time`, `unit_convert`, `wiki_read`, `remind_me`
  (gated), `answer_direct` (no-tool). Add a function here → it becomes routable
  with zero model code changes.
- **Executors** (`functions/executors.py`): sovereign handlers. `compute` runs
  in an AST-scanned `-I` subprocess (no imports/open/dunders, CPU rlimit +
  timeout). `remind_me` is GATED (proposed_write, never auto-mutates).
- **Shared primitive** (`scripts/tomac_common.py`): `CUE`, `build_prompt()`,
  `parse_call()` (TOLERANT — recovers fn name even from truncated JSON; the
  CALL_OPEN_RE lesson from smol, applied to JSON). Train + eval MUST use these
  so the cue + grammar stay BYTE-IDENTICAL (drift silently kills habit transfer).
- **From-scratch model** (`scripts/model_scratch.py`): char-level pre-norm
  Transformer, random init. The sovereign router is **`baseline-100ep-8fn` =
  ~2.3M params** (d_model 192, 4 layers, 6 heads) — this is the production floor.
  A 10.9M capacity bump (`baseline-big`) REGRESSED on honest eval (collapsed to
  `answer_direct`, route_acc 0.25 vs the 2.3M model's ~0.90); an augmented-data
  re-run collapsed identically, falsifying the "bigger brain needs more
  curriculum" hypothesis (wiki/findings/2026-07-15-baseline-big-aug-regressed.md).
  **Scaling up hurts routing** — 2.3M is the sweet spot. Model defaults in
  `scripts/model_scratch.py` are d_model=256/6L; the 8fn runs used `--d-model 192
  --n-layers 4`.
  Vocab = chars seen in cards (+ CUE). Saves `model.pt` + `config.json` +
  `tokenizer.json`.
- **Pipeline**: `build_cards.py` (synth from registry) → `train_router.py`
  (FROM SCRATCH, full training) → `eval_router.py` (route_acc / well_formed /
  per-fn accuracy / over+under_call) → `router_server.py` (live loop). Every
  pass → `metrics.py` (SQLite) + optional MLflow.
- **Env**: uv venv `.venv` (python 3.13) with torch 2.5.1+cu121, transformers,
  peft, trl, datasets, accelerate, mlflow. PEP 668 — always `source .venv/bin/activate`.
- **GPU**: Tesla P4, 8 GB, compute 6.1. **TRAINING/EVAL IS PAUSED** until user
  says go. For eval set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- **Cost tracking** (smol-style): `metrics.py` logs walltime + GPU watts
  (nvidia-smi) → USD @ $0.14/kWh. `scripts/sync_docs.py` rewrites the README
  + wiki cost banner from `benchmarks/passes.db`.

## How to resume / run
```bash
cd /home/aec/tomac
source .venv/bin/activate
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python scripts/probe_env.py                       # verify env (no GPU work)
python scripts/build_cards.py                     # synth data from registry
python scripts/train_router.py --out models/scratch/1 --epochs 30   # FROM SCRATCH (GPU)
python scripts/eval_router.py --model models/scratch/1 --data data/raw/cards.jsonl  # GPU
python scripts/router_server.py --model models/scratch/1 --chat
```

## Key conventions / gotchas (learned from smol — see wiki/bugs/)
- **Byte-identical cue + parser.** `tomac_common.build_prompt` / `parse_call`
  are the contract. Never edit `CUE` without retraining; never fork the parser.
- **Tolerant JSON parse.** A call truncated by `max_new_tokens` still yields the
  fn name so routing is scored (don't repeat smol's well_formed=0 phantom).
- **Batching is non-negotiable** for eval. `eval_router.generate_all` left-pads +
  chunks (batch=16). Per-call `generate()` pegs a CPU core and starves the GPU
  (smol BUG-005/007). NOTE: the from-scratch model is tiny; char-gen is also
  batched in eval_router via per-item loops kept cheap — revisit if slow.
- **`cards.jsonl` is generated** — regenerate via `build_cards.py`, don't edit.
- **`models/`, `logs/`, `benchmarks/*.db`, `mlruns/` are gitignored (artifacts).**
  The registry, scripts, docs, and wiki are tracked. (`models/` holds the
  trained scratch checkpoints + optional symlinked HF bases — gitignored.)
- **Writes are gated.** `remind_me` returns `proposed_write`; only a human CLI
  commit mutates `data/reminders.md`. No silent self-poisoning.
- **NO pretrained base.** Training is from random init (user directive). Do not
  reintroduce smollm/smollm bases unless the user reverses this.

## Cost tracking
Total homelab cost: `python -c "from scripts.metrics import Metrics as M; M().cost_report()"`.
Every pass logs walltime + GPU watts → USD (sovereignty metric vs API bills).
Keep the README + wiki cost banner in sync via `scripts/sync_docs.py`.

## Commit / push
- Branch `main`, remote `origin` = `git@github.com:jamesphenry/ToMoC-model.git`.
  Identity `James Henry <james.phenry@gmail.com>`.
- Keep commits KISS. Add a dated entry under `wiki/journal/` with each real run; keep `wiki/bugs/`
  as the failure log. Don't let the README cost banner drift (regenerate from
  `benchmarks/passes.db` via `scripts/sync_docs.py` when added).
