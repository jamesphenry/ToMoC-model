# Finding: capacity bump (10.9M) REGRESSED — bigger ≠ better on same data

**Date:** 2026-07-14
**Context:** pass-55 trained `baseline-big` (d_model=384, n_layers=6, n_heads=6,
d_ff=1536 = 10,885,632 params, 4.7× the 2.3M 8fn) on the SAME 3936 cards,
100ep, same LR. Honest eval at rep_penalty=1.0 (live-faithful, not the inflated
1.4 that previously masked failures — see BUG-007).

## What we saw (honest eval, 3936 cards, 2203.8s)
```
route_accuracy : 0.2500
well_formed    : 0.2538
over_call      : 0.0000
under_call     : 0.7447
per-function:
  answer_direct  1.000  (984/984)   <- only thing it does
  compute        0.000  (0/858)
  get_time       0.000  (0/849)
  remind_me      0.000  (0/246)
  unit_convert   0.000  (0/252)
  web_search     0.000  (0/249)
  wiki_read      0.000  (0/249)
  wiki_write     0.000  (0/249)
```
vs 8fn incumbent (~0.96 route_acc, all classes 92-100%). The 10.9M model
**collapsed to answer_direct on 75% of cards** and never emits a tool call.

## Diagnosis
This is BUG-007's predicted failure mode, now confirmed empirically:
- **More capacity + same data + same epochs ≠ better.** The bigger model has
  more ways to under-fit; with no extra training signal it never acquired the
  *routing habit* (emit TOOL <name> <json>). It defaulted to the no-tool prior.
- The earlier 2.3M model succeeded because capacity was the binding constraint
  at small size; jumping 4.7× without more data/epochs/training-signal just
  diluted the habit into a larger parameter space.
- **Root cause = undertraining at the new capacity, not architecture.** The
  capacity bump was a valid hypothesis; the execution (same epochs, same cards)
  was insufficient. To make 10.9M win it needs: more epochs, OR more/augmented
  cards, OR a curriculum that forces tool-emission.

## Decision
- **ROLLBACK.** `promote.py` refuses to promote baseline-big (incumbent 8fn wins
  on the honest gate). baseline-big is a regression experiment — NOT promoted,
  kept on disk for a future proper-capacity run.
- Do NOT conclude "bigger is worse" — conclude "bigger needs more training
  signal." The capacity-bump hypothesis is still open; this run just didn't
  supply what a bigger model needs.
- Honest eval (rep_penalty=1.0) was ESSENTIAL: at rep_penalty=1.4 the smaller
  model's numbers looked fine and would have masked that we'd even regressed.

## Reproducibility
- Eval: `python scripts/eval_router.py --model models/scratch/baseline-big
  --data data/raw/cards.jsonl --rep-penalty 1.0`
- Per-item: `logs/eval_router_baseline-big_20260714T234406Z.jsonl`
- Promote gate: `python scripts/promote.py --current models/scratch/baseline-100ep-8fn
  --candidate models/scratch/baseline-big` → KEEP incumbent (rollback).

## Follow-up
- If we revisit capacity: scale epochs (e.g. 100→300) AND/OR augment cards, then
  re-eval honestly. The 10.9M floor is fine VRAM-wise (see
  `2026-07-14-vram-spike-baseline-big.md`); it's a training-signal problem.
- **promote.py CONFIRMED the rollback on real numbers** (pass-58, limit 800,
  rep_penalty=1.0): incumbent 8fn route_acc 0.8975 vs candidate baseline-big
  0.2762 → KEEP incumbent. Nothing written. The self-training decider works
  end-to-end; baseline-big is a discarded experiment, 8fn stays sovereign.
