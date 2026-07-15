# 2026-07-15 — capacity-scaling thread REVERTED

**Decision:** abandon the 10.9M capacity bump. `baseline-100ep-8fn` (2.3M) is the
production router. The capacity A/B is closed.

## Why we scaled (and why it was wrong)

Original trigger: 2.3M model garbled at LIVE greedy decode ("what is 3+4" →
`TOOOOL compute {"expression":"47+3"}`, loops to 160 chars). Mis-diagnosed
(me) as UNDER-CAPACITY → trained baseline-big (10.9M, 100ep). It REGRESSED:
honest eval route_acc 0.25, collapsed to `answer_direct`, all other fns 0/0.
Rolled back via promote (pass-58).

James's hypothesis: "bigger brain needs more curriculum, not epochs." Tested as
B (baseline-big-aug: 10.9M, 12,816 augmented cards, 100ep). **Also collapsed
identically** (pass-60). Hypothesis FALSIFIED — and A (300ep, same cards) is
HELD (would only re-confirm).

## The real root cause (what the scaling was masking)

The live garbling was NEVER raw capacity. It was:
- BUG-006: live decode sampled at temperature=1.0 while eval was greedy — the
  model's greedy output was fine, the live sampling was the problem.
- BUG-007: eval used rep_penalty=1.4, propping up a weak model and inflating the
  "96.3%" figure. Honest eval (rep_penalty=1.0) is ~0.90 for 8fn.

The 2.3M model routes honestly at ~0.90. The 10.9M model is WORSE because it has
parameter slack to cheat ("always answer_direct" = free 25%), so it converges to
a degenerate local minimum. Small-model-generalizes-better effect.

## The actual fix for the live garbling

1. **Greedy live decode** — `router_server.py` generate at temperature=0.0
   (argmax). Already patched (uncommitted at revert time; this is the real fix,
   not scaling).
2. **Kill the rep_penalty crutch** — eval at rep_penalty=1.0; re-baseline the
   README "96.3%" claim to the honest ~0.90.
3. **Honest eval gate** — promote.py / eval_router at rep_penalty=1.0 only.

## Status after revert

- 8fn (2.3M) = sovereign router. Scaling up = dead end (evidence-based).
- 10.9M models (baseline-big, baseline-big-aug) remain on disk but are NOT
  promoted; documented as regressions in wiki/findings/.
- Only worthwhile future "bigger" experiment would be REGULARIZATION on the big
  model (dropout / weight decay / class-balanced loss) to stop the cheat — NOT
  more data/epochs. Deferred; not prioritized.

See: wiki/findings/2026-07-15-baseline-big-aug-regressed.md,
wiki/bugs/BUG-006-decode-mismatch.md, wiki/bugs/BUG-007-rep-penalty-inflation.md.
