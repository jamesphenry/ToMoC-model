# Plan: Phase 2 — Multi-tool Eval Harness

**Goal:** measure routing quality on *held-out* requests spanning every function,
not just the training examples. Per-category precision/recall.

## Steps
1. [ ] `scripts/build_eval_set.py` — generate a held-out set
       `data/raw/eval_heldout.jsonl`: for each function, synthesize NEW requests
       (reworded examples + templated variants) the model didn't train on.
       Keep a gold `name` + `args` per item.
2. [ ] Extend `eval_router.py` to accept `--kind heldout` and report a confusion
       matrix: predicted-fn × gold-fn. Surfaces systematic misroutes
       (e.g. `unit_convert` vs `compute`).
3. [ ] Run on the Phase-1 adapter; log per-function precision/recall to passes.db
       and MLflow.
4. [ ] If a function pair confuses the model, add a few "contrast" cards to
       `build_cards.py` (e.g. "<n> miles to km" vs "<n> * 1.6") and retrain.
5. [ ] Document the confusion matrix in `wiki/journal/` (dated entry).

## Lean vs moonshot
- **Lean:** reworded examples only (fast, enough to see the floor).
- **Moonshot:** a tiny generator-LLM (the 360M itself, or a small local model)
  writes diverse held-out requests; human spot-checks a sample. Higher coverage,
  more setup.

## Definition of done
- Held-out set exists and is disjoint from training examples.
- Confusion matrix shows each function routes to itself >> others.
