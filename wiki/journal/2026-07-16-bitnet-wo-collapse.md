---
title: "BitNet weights-only (variant b) — COLLAPSED IDENTICALLY"
date: 2026-07-16
status: negative-result
supersedes_decision: "2026-07-15 user picked (b) weights-only to isolate activation-clamp vs weight-rounding"
tags: [bitnet, 1-bit, side-track, collapse, variant-b, root-cause]
---

## What was tried (variant b — the user's pick)
Faithful BitNet b1.58 but with **FP activations (no INT8 clamp); only the matmul
weights are ternary** (`--bitnet-weights-only`, `weights_only=True` in
`model_bitnet.BitNetRouterModel`). Same 2.3M shape (d_model 192 / 4L / 6H /
d_ff 1024), 100 epochs, flat LR 3e-3, full cards. Goal: isolate whether the
INT8 activation clamp was the cause of the first BitNet collapse.

## Result — IDENTICAL collapse (not a fix)
| metric         | FP pin  | BitNet (w+act) | BitNet weights-only |
|----------------|---------|---------------|---------------------|
| route_accuracy | 0.9627  | 0.2500        | 0.2500              |
| well_formed    | 0.9220  | 0.2500        | 0.2500              |
| arg_accuracy   | 0.5366  | 0.0000        | 0.0000              |
| under_call     | 0.0091  | 0.7500        | 0.7500              |

Per-function: `answer_direct` 1.000 (984/984), **every real tool 0.000**
(compute 0/858, get_time 0/849, remind_me 0/246, unit_convert 0/252,
web_search 0/249, wiki_read 0/249, wiki_write 0/249). Raw output is the same
degenerate garbage as the first run, e.g.:
  Q: "What is 9 divided by 6?"
  raw: `TOL wreb_s {"contitlenterente "contitlententent"core 2, ": ": "litentententente '`

## Root cause — DEFINITIVE
Removing the activation clamp changed **nothing**. Therefore the killer is
**the ternary weight rounding itself** (STE at 2.3M / 100ep / flat 3e-3 LR),
NOT the INT8 activation path. This matches the prior 10.9M FP collapse
signature (route_acc 0.25 / under_call 0.75) — confirming the earlier
hypothesis that *this curriculum does not converge under either (a) more
capacity at FP, or (b) ternary weights at matched capacity*. Same attractor:
collapse to `answer_direct`.

## Verdict on the 1-bit side-track
**A 1-bit (BitNet b1.58) core is NOT viable as trained.** Both ternary
variants (w+act, weights-only) collapse to the identical degenerate routing.
The "tiny on any device" p2p-any-device vision (2026-07-15-future-p2p-any-
device.md) depends on a working 1-bit core; without one, that fork is dead
**for now** — the FP pin (2.3M) remains the only functional floor.

## What could still rescue 1-bit (NOT yet tried — recorded, not actioned)
The honest remaining lever is the **real BitNet training recipe**: LR warmup
(~2k steps) + a much higher peak LR (~1e-2) + longer training. BitNet papers
use that schedule because the STE rounding gradient is hostile at low LR. We
trained with the FP schedule (flat 3e-3), which may simply be too cold for
ternary convergence. This is a different experiment from (a)/(b); it has not
been run.

## Git
- Training + eval committed in `3a0d1f0` (W&B run-labeling) prior; the
  bitnet-wo model + eval artifacts are gitignored (models/, logs/).
- This addendum committed separately (append-only; prior collapse entry
  body untouched — see footnote there).
