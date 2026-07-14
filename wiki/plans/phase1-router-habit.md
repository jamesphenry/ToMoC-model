# Plan: Phase 1 — Router Habit (IN PROGRESS)

**Goal:** teach the from-scratch char-level transformer to emit
`TOOL <name> <json>` correctly, and quantify routing quality over the
random-init floor. (No pretrained base; user directive 2026-07-13.)

## Metrics we care about
- `route_accuracy` — predicted function == gold function (the routing decision).
- `well_formed` — call parses to valid JSON (reported separately from routing so
  a format slip can't masquerade as a routing failure).
- `over_call` — predicted a tool when gold said answer_direct.
- `under_call` — predicted none when gold said a tool.
- `fn.<name>` — per-function accuracy (router precision/recall per tool).

## Steps
1. [x] Scaffold + scripts (see Phase 0); from-scratch model in `model_scratch.py`.
2. [x] `python scripts/build_cards.py --multiply 3` → `data/raw/cards.jsonl`.
3. [ ] **Train (pass 1):** `train_router.py --out models/scratch/1 --epochs 30`.
       Logs loss curve + cost to passes.db. The random-init "floor" is implied by
       the untrained eval below (no format known yet).
4. [ ] **Eval (pass 2):** `eval_router.py --model models/scratch/1`. Reports
       `route_accuracy` / `over_call` / `under_call` / per-fn.
5. [ ] **Live sanity:** `router_server.py --model models/scratch/1 --ask "what
       is 48 - 5 + 20"` → should route to `compute` and execute to 63.
6. [ ] Sweep if needed: epochs 20/30/50, lr 1e-3/3e-3, d_model 128/256/512.
       Pick the smallest model that holds `route_accuracy` >= 0.95.
7. [ ] Add a dated entry under `wiki/journal/` + a `wiki/bugs/` file with anything found.

## Decisions / lean options
- **Architecture:** default ~3M params (d_model=256, 6 layers, 8 heads). Bump
  for harder routing; shrink to find the floor (Phase 3).
- **Data multiplier:** 3× repeats of each example = enough signal at small size
  without overfitting. Bump if `route_accuracy` stalls.
- **max_new_tokens:** 160 in eval (headroom for JSON); raise only if long arg
  lists get truncated (then also raise the training `max_len`).

## Definition of done
- Trained eval shows `route_accuracy` meaningfully above random and `over/under_call`
  near 0 on the held-out-style card split.
- A live `--ask` routes + executes correctly end-to-end.
- Numbers are in `wiki/journal/` and `benchmarks/passes.db`.
