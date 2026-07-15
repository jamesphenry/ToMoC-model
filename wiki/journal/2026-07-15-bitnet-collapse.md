---
title: "BitNet b1.58 side-track — COLLAPSED at 2.3M/100ep (negative result)"
date: 2026-07-15
status: negative-result
tags: [bitnet, 1-bit, side-track, collapse, p2p]
---

## What was tried
Faithful BitNet b1.58 (ternary weights {-1,0,+1} via per-matrix RMS scaling +
RoundClamp, STE backward, INT8-activation clamp) trained FROM SCRATCH at the
SAME shape as the pinned FP baseline: d_model=192, 4 layers, 6 heads, d_ff=1024
(~2.3M FP-latent params), 100 epochs, identical cards.jsonl. Goal: see "what a
1-bit router is capable of" — the prerequisite for the p2p-on-any-device vision.

Code: scripts/model_bitnet.py (BitNetRouterModel + BitLinear). Wire-in:
train_router.py --bitnet, eval_router.py auto-detects `bitnet` flag. Verified
on CPU (build/train/generate/save-load) before the GPU run.

## Result (eval, pass-64, full 3936 cards, rep=1.4, temp=0)
  route_accuracy : 0.2500
  well_formed    : 0.2500
  arg_accuracy   : 0.0000
  over_call      : 0.0000
  under_call     : 0.7500
  per-fn: answer_direct 1.000 (984/984); EVERY tool fn 0.000.

Raw sample: Q="What is 9 divided by 6?" -> `TOL wrexpueb_tikiminswech {}`
(not even "TOOL"; no parsable function). The model learned ONLY to emit
answer_direct and never acquired the TOOL grammar.

## Interpretation
COLLAPSED. Failure signature is IDENTICAL to the dead 10.9M FP capacity thread
(route_acc 0.25 / under_call 0.75) — a degenerate attractor at "always
answer_direct". Two non-exclusive hypotheses:
  1. Ternary STE at this tiny scale is too lossy: the rounding gradient kills
     the slow char-grammar learning the FP 2.3M model needs. BitNet papers train
     at much larger scale / with LR warmup + higher LR — we used the FP LR
     (3e-3) and a flat schedule.
  2. A genuine degenerate attractor in this task+data+tokenizer at "more
     aggressive" architectures (both 10.9M FP and 1-bit 2.3M hit it). Capacity
     is NOT the variable that fixed it (10.9M failed too), so this is a training-
     dynamics / precision issue, not a size issue.

## Not a code bug
The model trained and eval'd cleanly (no crash, correct wiring verified). The
weights ternarize correctly in {-1,0,1}. This is a genuine negative training
result, not a plumbing fault.

## Options (decision pending with user)
- (a) Tune BitNet training: LR warmup + higher peak LR (BitNet-standard),
      maybe 200ep, possibly a touch more capacity. Real research effort; might
      recover. The p2p vision depends on this working.
- (b) Try variant 2 (ternary WEIGHTS only, keep FP activations) — isolates
      whether activation clamping is the killer. Lighter, faster experiment.
- (c) Accept the negative: 1-bit is not viable for this task at this scale;
      close the side-track, keep the pin as the floor.

## Artifacts
- model: models/scratch/baseline-100ep-8fn-bitnet (gitignored; kept as evidence)
- logs: logs/train_bitnet_8fn_*.log, logs/eval_bitnet_8fn_*.log
- per-item: logs/eval_router_baseline-100ep-8fn-bitnet_*.jsonl
