# tomac — a tiny function-routing LLM (trained from scratch)

> A *very small* LLM (trained **from random init — no pretrained base**) taught
> to be a **smart router**: read a request, decide **which function to call and
> with what arguments**, then let sovereign, disk-backed tools do the work. The
> functions ARE its knowledge — capability scales by adding functions, not
> parameters.

---

## Cost stats

Sovereignty metric vs API bills — every GPU pass is metered (walltime × real
`nvidia-smi` board draw × $0.14/kWh).

- **Total to date: $0.0435** across **51 GPU passes** (10.76 GPU-hours) @ $0.14/kWh, ~90 W over idle.
- Breakdown: training $0.0392 (19 passes, 9.72 GPU-h) · eval $0.0043 (32 passes, 1.04 GPU-h).
- A single 100-epoch from-scratch train on an 8 GB Tesla P4 costs ~**$0.002–0.003** (≈30 min). A full eval is ~$0.0002.

**Status:** two trained from-scratch routers are the current candidates
(see wiki/findings for the full train→eval→discuss story):
- `baseline-100ep-8fn` — 8 functions, single-tool routing, **96.3%** route_acc, no disambiguation.
- `baseline-100ep-mt2` — full-list needle-style disambiguation, **93.7%** single-tool + **100%** multi-tool gold_hit.
Both train their own weights from random init (no base model). Ship decision pending.

---

## Why a tiny model? (the thesis)

| Approach | Params | Can it do math? | Can it look up your notes? | Single-req latency | Cost |
|----------|--------|-----------------|----------------------------|--------------------|------|
| big LLM | 70B+ | yes (in weights) | yes (in weights) | ~0.5–2 s (decode + API) | API $ / big GPU |
| **tomac** | ~3M (from scratch) | routes to `compute` | routes to `wiki_read` | **~240 ms** (P4, no net) | ~$0.01/pass on a P4 |

> tomac's latency is **measured** on this repo's 8 GB Tesla P4 (single-request,
> greedy decode, warmed up). The big-LLM figure is a typical-order estimate for
> a local 7–13B model or an API round-trip — not measured here. Because tomac
> only *routes* (it emits one short call, then a 20-line executor does the work),
> there is no network hop and almost no decode — hence the sub-300 ms response.

A 360M model *cannot* do arithmetic on its own (the `smol` project measured
**1.7%** on gsm8k). But it *can* learn "this is a math request → emit
`TOOL compute`", and a 20-line sandboxed executor does the arithmetic perfectly.
So we trade *model smarts* for *routing skill*. The result is a cheap, offline,
sovereign assistant whose intelligence lives in functions, not weights.

---

## What it is, in one paragraph

A normal LLM *is* a knowledge base — its smarts are baked into billions of
weights. This project inverts that. We train a tiny causal LM to emit one
structured call when a request needs a tool:

```
TOOL compute {"expression": "48 - 5 + 20"}
TOOL unit_convert {"value": 5, "from": "mi", "to": "km"}
TOOL answer_direct {}
```

…and to answer directly (no tool) otherwise. A separate, sovereign executor
(`functions/executors.py`) actually runs the call. The model **decides**; the
function **does**. Because the router only needs to choose *well*, it can stay
tiny — and you grow its capability by registering a new function in
`functions/registry.json`, with **zero model code changes**.

### Repository layout

```text
tomac/
├── README.md                 # this file (homelabber guide)
├── AGENTS.md                 # resume-point for AI/agent sessions
├── functions/
│   ├── registry.json         # ★ THE KNOWLEDGE: every routable function
│   ├── registry.py           # load the registry
│   └── executors.py          # the actual tool handlers (sovereign, sandboxed)
├── scripts/
│   ├── tomac_common.py       # shared cue + call parser (TRAIN==EVAL bytes)
│   ├── build_cards.py        # synth router training data from the registry
│   ├── train_router.py       # FROM-SCRATCH training (random init, no base)
│   ├── eval_router.py        # routing-quality eval (route_acc, per-fn, ...)
│   ├── router_server.py      # live loop: q -> call -> execute -> answer
│   ├── model_scratch.py      # tiny char-level transformer (the router)
│   ├── build_multitool_cards.py # synth DISAMBIGUATION cards (full tool list)
│   ├── eval_multitool.py     # score multi-tool gold_hit / in_set / out_of_set
│   ├── metrics.py            # SQLite ledger of every pass + cost
│   ├── wandb_tracker.py      # optional Weights & Biases tracking (self-hosted)
│   └── probe_env.py          # verify the env before spending GPU
├── data/
│   ├── raw/cards.jsonl       # generated training/eval cards
│   ├── vault/                # disk-backed wiki (markdown notes)
│   └── reminders.md          # gated reminder store
├── models/                   # trained scratch checkpoints (gitignored)
├── logs/                     # per-run + per-item JSONL (gitignored)
├── benchmarks/passes.db      # metrics ledger (gitignored)
└── wiki/                     # BUGS.md, JOURNAL.md, plans/
```

---

## How to (recreate it yourself)

### 1. Get a GPU box
Any CUDA GPU works; the numbers below are from an 8 GB Tesla P4.

```bash
git clone git@github.com:jamesphenry/ToMoC-model.git
cd tomac
```

### 2. Create the environment (uv, PEP 668 safe)

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
# torch for your CUDA major version; cu121 shown
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
uv pip install transformers peft trl datasets accelerate bitsandbytes
uv pip install wandb             # optional but recommended (run/asset tracking, self-hosted)
```

> **W&B is optional.** If you skip it, the SQLite metrics ledger still records
> every pass and cost. Set `WANDB_API_URL` + `WANDB_ENTITY` (your self-hosted
> W&B server) to also track runs + checkpoints in Weights & Biases.

### 3. Synthesize training data from the registry

The registry **is** the knowledge. Every function's examples become gold
(request → call) pairs; chit-chat becomes "answer directly" negatives.

```bash
python scripts/build_cards.py
```

### 4. Verify the environment

```bash
python scripts/probe_env.py
```

It prints a go/no-go summary: torch+CUDA, the ML stack, the function registry,
and a from-scratch model shape check (no base model needed).

### 5. Train the router FROM SCRATCH

No pretrained base — the model is a tiny char-level transformer trained from
random init. The default is ~3M params; bump `--d-model` / `--n-layers` for a
bigger model. Training to usable routing on a P4 takes minutes, not hours.

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python scripts/train_router.py --out models/scratch/1 --epochs 30
```

### 6. Evaluate routing quality

```bash
python scripts/eval_router.py --model models/scratch/1 --data data/raw/cards.jsonl
```

This prints `route_accuracy`, `well_formed`, `over_call`, `under_call`, and a
per-function breakdown, and writes a full per-item JSONL to `logs/`. Every
pass is logged to `benchmarks/passes.db` with its electricity cost.

### 7. Run it live

```bash
python scripts/router_server.py --model models/scratch/1 --chat
# or a one-shot:
python scripts/router_server.py --model models/scratch/1 --ask "what is 48 - 5 + 20"
```

### 8. Add a new function (capability without retraining the architecture)

1. Add an entry to `functions/registry.json` with a `name`, `category`,
   `params`, and a few `examples` (`request` → `args`).
2. Add a handler of the same name in `functions/executors.py` that takes `args`
   and returns `{"ok": True, "result": ...}`.
3. Re-run `build_cards.py` (your new examples become training data) and retrain
   from scratch.

That's it. The model learns to route to the new function from its examples; the
executor gives it the actual capability. **No model code changes, no new params.**

> Safety: compute runs in an AST-scanned, isolated subprocess (no imports / `open`
> / dunders / network). Write handlers (`remind_me`) are **gated** — they return
> a `proposed_write` and never mutate disk until a human approves. The model can
> *propose*, never *poison*.

### 9. Optional — teach the router to DISAMBIGUATE (multi-tool)

By default the router sees one request and emits one `TOOL` call. To teach it to
*choose* the right tool when several are plausible (a selection boundary
single-tool cards never teach), generate disambiguation cards where the prompt
lists the full available-tool set but the gold is still a single tool:

```bash
python scripts/build_multitool_cards.py --out data/raw/multitool.jsonl --n 400
cat data/raw/cards_train.jsonl data/raw/multitool.jsonl > data/raw/cards_train_mt.jsonl
python scripts/train_router.py --out models/scratch/baseline-100ep-mt2 --epochs 100 --data data/raw/cards_train_mt.jsonl
# score disambiguation separately from single-tool routing:
python scripts/eval_multitool.py models/scratch/baseline-100ep-mt2 data/raw/multitool.jsonl
```

`eval_multitool.py` reports `gold_hit` (picked the right tool), `in_set`
(valid choice), and `out_of_set` (a genuine disambiguation error). See
`wiki/findings/2026-07-14-disambiguation-fixed.md` for the full A/B.

---

## Metrics, MLflow, and bugs

- **Every training/eval pass** is logged to `benchmarks/passes.db` (metrics +
  walltime + GPU mem + electricity cost) via `scripts/metrics.py`.
- **W&B** (optional) mirrors each run + logs the checkpoint dir as an artifact
  when `WANDB_API_URL` + `WANDB_ENTITY` are set. Inspect in your self-hosted UI.
- **Bugs and hotfixes** live in `wiki/BUGS.md`. The running build narrative and
  real numbers are in `wiki/JOURNAL.md`. Detailed phase plans are in
  `wiki/plans/`.

---

## Roadmap (phased, KISS, baby-steps)

- [x] **Phase 0 — foundations**: env, function registry as knowledge, executor handlers (sovereign + sandboxed), from-scratch architecture.
- [x] **Phase 1 — router habit**: card synth from registry, FROM-SCRATCH train, routing-quality eval (route_acc / well_formed / per-fn).
- [ ] **Phase 2 — multi-tool eval harness**: held-out requests across all functions; measure per-category routing precision/recall.
- [ ] **Phase 3 — smallest viable model**: sweep d_model / n_layers (e.g. 128/4 → 512/8) on from-scratch routing; find the floor where routing quality collapses.
- [ ] **Phase 4 — live assistant loop**: router_server as a homelab service (pi / daemon) dispatching real tools.
- [ ] **Phase 5 — grow the function set**: weather, home-assistant, DNS/network probes, notes CRUD — capability without retraining the architecture.
- [ ] **Phase 6 — self-extending registry**: model *proposes* new functions it can't route; human approves and implements the handler.

See `wiki/plans/` for the detailed breakdown of each phase.

---

## License

MIT — see [LICENSE](LICENSE). Author: James Henry <james.phenry@gmail.com>.
