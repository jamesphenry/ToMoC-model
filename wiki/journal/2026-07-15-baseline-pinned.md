---
title: "baseline-100ep-8fn PINNED — 2.3M frozen as known-good floor"
date: 2026-07-15
status: pinned
tags: [baseline, pin, arg-accuracy, side-track]
---

## What got pinned

`baseline-100ep-8fn` (2.3M, d_model=192 / 4L / 6H) is frozen as the
**known-good sovereign router**. A local copy is saved at
`models/scratch/baseline-100ep-8fn.PINNED` (gitignored) so future experiments
can never clobber it.

### Verified full-set metrics (eval_router pass-63, rep=1.4, temp=0, 3936 cards)
- route_accuracy : **0.9627**  (picks the right function)
- well_formed    : **0.9220**
- arg_accuracy   : **0.5366**  (right function AND right args — new metric)
- over_call      : 0.0076
- under_call     : 0.0091

Per-fn arg_accuracy (routed fn was right; args matched gold):
get_time 1.000, remind_me 1.000, web_search 0.976, wiki_read 0.928,
answer_direct 0.970, compute 0.955, unit_convert 0.893, wiki_write 0.892.

### The real weakness (now measurable)
A **~43-point gap** between routing (96%) and end-to-end arg fidelity (54%).
The router picks the right function but frequently mis-fills args. This is the
concrete next training target — NOT capacity (the 10.9M bump regressed).

## Why pin now
User direction: freeze where we are with the 2.3M and **side-track** into a
1-bit model experiment to see what it's capable of. The pin guarantees we can
always return to a verified-good router regardless of where the 1-bit thread
goes. This repo remains the LAB; the 1-bit build is exploration, not a
replacement unless it beats the pin on arg_accuracy.

## Next
- 1-bit side-track: build a ternary/1-bit from-scratch router (BitNet-style
  training regime) and compare route_accuracy + arg_accuracy vs this pin.
- If 1-bit matches within tolerance at a fraction of the footprint, that's a
  sovereignty win (router on trivial hardware). If it collapses arg_accuracy
  further, the conclusion is "precision isn't the lever for arg fidelity."
