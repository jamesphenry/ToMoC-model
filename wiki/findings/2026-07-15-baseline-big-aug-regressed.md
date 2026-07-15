# Finding — baseline-big-aug REGRESSED (data-volume hypothesis falsified)

**Date:** 2026-07-15
**Status:** REJECTED hypothesis. 10.9M model collapses regardless of data volume / epochs.
**Pass:** train pass-59 (`baseline-big-aug`), eval pass-60.

## The hypothesis

User theory (2026-07-14): a bigger brain (10.9M vs 8fn's 2.3M) needs *more
curriculum* (data volume), not just more epochs. Test: train the 10.9M
`baseline-big` architecture on **3.3× more cards** (12,816 augmented, diverse
paraphrases) for 100 epochs, then honest-eval at `rep_penalty=1.0`.

## Result (honest, rep_penalty=1.0, 3936 cards)

```
eval: baseline-big-aug (3936 cards, 2555.1s)
  route_accuracy : 0.2500
  well_formed    : 0.2500
  over_call      : 0.0000
  under_call     : 0.7500
  per-function:
    answer_direct  1.000  (984/984)
    compute        0.000  (0/858)
    get_time       0.000  (0/849)
    remind_me      0.000  (0/246)
    unit_convert   0.000  (0/252)
    web_search     0.000  (0/249)
    wiki_read      0.000  (0/249)
    wiki_write     0.000  (0/249)
```

**Identical collapse to the original baseline-big (pass-55):** route_acc 0.25,
under_call 0.75, every non-`answer_direct` function routed 0/0. The model learned
ONLY "always emit `answer_direct`" (the 984/3936 = 25% majority/easiest class)
and never learned the routing discrimination to the other 7 functions.

## What this rules out

- **Not data volume.** 3.3× more cards (12,816 vs 3,936) → same collapse.
- **Not epochs.** 100 epochs → same collapse.
- **Not naive undertraining.** More epochs AND more data both fail.

The capacity wall is **structural**, not a tuning/volume problem. The 10.9M
model converges to a degenerate local minimum: "always `answer_direct`" scores
25% for free and the model gets stuck there instead of learning the
discriminations.

## Working theory: the 2.3M model is the SWEET SPOT (smaller generalizes better)

The incumbent `baseline-100ep-8fn` (2.3M) does NOT collapse. Plausible reason:
at 2.3M the parameter budget is too small to dedicate a separate "always
answer_direct" path, so it is *forced* to share representation and actually
learn the routing discrimination. The 10.9M model has slack to cheat — it
specializes a path for the easy class and overfits it. Classic "small model
can't memorize the shortcut, so it generalizes" effect.

If true, the fix is **NOT capacity scaling** — it is **capacity right-sizing +
regularization** on the big model (dropout, weight decay, class-balanced /
answer_direct-downweighted loss), OR accepting 2.3M as the production shape.

## Consequence for the A/B plan

**Experiment A (300ep, same 3,936 base cards) is HELD — not launched.** It would
only re-confirm "more epochs on the small data also fails," which B already
proved (epochs + data both fail). Launching A would burn ~4.6 GPU-hours proving
the obvious. A is deferred until there is a *hypothesis worth testing* (e.g.
regularization on baseline-big, or class-balanced loss).

## Promote decision

`promote.py` re-evaluating 8fn (incumbent) vs baseline-big-aug (candidate) at
the honest gate (rep_penalty=1.0). Expected: KEEP 8fn (rollback), since B's
route_acc 0.25 << 8fn's ~0.90. Logged separately (pass-61, in flight at write
time).

## Next

Discuss before any GPU work (baby-steps). Candidate directions:
1. Regularize baseline-big (dropout / weight decay) and re-eval — can we stop the
   collapse without shrinking?
2. Class-balanced or answer_direct-downweighted loss so "always direct" can't win.
3. Accept 2.3M (8fn) as the production shape; stop chasing capacity; move to
   Phase 4 (live assistant loop) or grow the function set (Phase 5).

See also: `wiki/findings/2026-07-14-capacity-bump-regressed.md` (original
baseline-big collapse), `wiki/findings/2026-07-14-capacity-data-volume-hypothesis.md`
(the A/B design that this result falsifies).
