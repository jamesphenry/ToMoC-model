# 2026-07-13 — baseline-train

## What we ran
- Model: from-scratch char-level transformer, **d192 / 4 layers / 6 heads**, ~2.3M params.
- Data: `data/raw/cards.jsonl` (946 cards, 6 tools: compute, get_time, unit_convert,
  wiki_read, remind_me, answer_direct).
- Hyper: 30 epochs, LR 3e-3, batch 32, greedy char gen.
- W&B: run `pass-train-baseline` (loss curve + cost/system metrics + checkpoint + cards dataset artifact).

## What we saw (eval, run `pass-9`)
```
route_accuracy : 0.3964
well_formed    : 0.3626
over_call      : 0.0328
under_call     : 0.4736
per-fn:
  remind_me    0.639  (78/122)   <- only "working" fn
  compute      0.000  (0/126)
  get_time     0.000  (0/123)
  unit_convert 0.000  (0/124)
  wiki_read    0.000  (0/123)
  answer_direct 0.000 (0/328)
```
GPU cost: 132.9s train, $0.0002 (29.8W avg, measured).

## Diagnosis
- **Loss curve still falling at epoch 30** (0.31→0.22 over last steps) → undertrained, not converged.
- Raw outputs are degenerate loops: `TOOOOOOL`, `memememe`, `titititi`. The model
  collapsed into the repetition basin. Greedy decode had NO repetition control.
- The old `stall_patience=8` only caught 8-identical-char runs, not the 2-char
  alternating loops (`meme`, `titi`) — so it never fired.
- remind_me's "0.64" is a mirage: its args are loose freeform text, so `memememe`
  still parses as valid JSON. The other tools need real values → score 0.

## Decision
- Treat 0.40 as "architecture learns, decode broken" not "model dumb."
- Next variable: **decoding fix only** (rep_penalty), NO retrain — isolate the cause.
- If rep_penalty lifts route_acc materially → decode bug. If not → undertraining → bump epochs.

## Tags
from-scratch, baseline, repetition-collapse, undertrained
