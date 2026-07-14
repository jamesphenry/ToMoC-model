---
title: Capacity bump: 2.3M -> 10.9M (baseline-big A/B)
project: tomac
date: 2026-07-14
policy:
  - entries are append-only; do NOT rewrite an existing entry
  - corrections / changes go as footnotes ([^n]) at the bottom, never inline rewrites
  - every major model-size change gets its own dated entry citing the forcing bug/metric
---

# 2026-07-14 — capacity bump: 2.3M → 10.9M (the "baseline-big" A/B)

**Why we changed the model size.** During live dogfooding of `baseline-100ep-8fn`
(2.3M params, d_model=192, n_layers=4), the router emitted garbage on trivial
queries — `what is 3 + 4` → `TOOOOL compute {"expression": "47 + 3"}`. Two bugs
were diagnosed (see [../bugs/BUG-006-decode-mismatch.md](../bugs/BUG-006-decode-mismatch.md)
/ [../bugs/BUG-007-rep-penalty-inflation.md](../bugs/BUG-007-rep-penalty-inflation.md)):

1. **BUG-006** — live server was *sampling* (temperature=1.0) while eval was
   greedy. Fixed: one decode path, greedy, for both.
2. **BUG-007** — the real root cause. Eval defaulted `rep_penalty=1.4`, which
   *masks* a degenerate looping habit the under-trained model falls into; the
   live path used 1.0 and hit the raw broken output. On 40 compute cards:
   rep_penalty=1.0 → **23/40** name-acc (loops + wrong math); 1.4 → 38/40.
   The "96.3%" headline was name-only **and** crutch-inflated. The model learned
   the *shape* of routing but not the grammar reliably — it needs the penalty to
   not loop. That is the **capacity wall**: ~2.3M over a char vocab + 8 routing
   habits + JSON-arg transcription is too small to hold it without degeneracy.

**Decision (user: "b", do not ship a failed model).** Scale capacity, keep it a
single-variable A/B against 8fn: **same data (`data/raw/cards.jsonl`), same 100
epochs, only `d_model`/`n_layers` changed.** New config:
`baseline-big` = d_model=384, n_layers=6, n_heads=6, d_ff=1536 →
**10,885,632 params** (~4.7x). Trains on the P4 (~10.9M fits in 8 GB). Eval will
be run at BOTH rep_penalty=1.0 (live-faithful, honest) and 1.4, and an
**arg-correctness** metric (full `TOOL name {args}` match) added so "95% accurate"
can never again hide a `29+23` handed to compute.[^2]

**Bigger picture (user's question).** Yes — chained tool calls / planning need
more capacity than even this. A single tool call is one short decode; a *chain*
is a multi-step structured output the model must learn to emit + consume. That
is the next arch step (likely a larger transformer or an encoder-decoder SAN,
parked in `scripts/model_san.py` / `train_san.py`), not a hyperparam tweak. This
10.9M run is the ceiling of the *current* single-pass router; if it still loops
we go to chained-capable capacity.

[^2]: **Amendment (2026-07-14) — the missing pass-54 run.** The first
    `baseline-big` launch (the run this entry describes) was started with
    `WANDB_MODE=offline` but **without `WANDB_API_URL`**. `wandb_tracker.py`
    silently falls back to a no-op `DummyTracker` when the URL is unset, so the
    run logged to `benchmarks/passes.db` as **pass-54** but **never reached
    W&B** — the user's dashboard stopped at `pass-53`. Because no real run was
    created, there was also no `offline-run-*` artifact to `wandb sync` later.
    This is [../bugs/BUG-008-wandb-silent-noop.md](../bugs/BUG-008-wandb-silent-noop.md).
    The run was killed (~17 min of progress, negligible cost) and **restarted
    online** as pass-55 with `WANDB_API_URL` + `WANDB_ENTITY=cravingpine` set, so
    the data lands where it's watched. pass-54 remains a documented missing run,
    not a silently dropped one.
