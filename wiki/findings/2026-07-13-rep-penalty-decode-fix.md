# 2026-07-13 — rep-penalty-decode-fix (RESULT: rejected)

## Hypothesis
Baseline collapse (`memememe`/`titititi` loops, route_acc 0.40) was a DECODING bug,
not undertraining. Fix: add `rep_penalty`, re-eval same checkpoint, no retrain.

## Result (re-eval, run `pass-10`, rep_penalty=1.4)
```
route_accuracy : 0.3467   (was 0.3964)   <- WORSE
well_formed    : 0.3467
over_call      : 0.0000
under_call     : 0.6533
per-fn         : ALL ZERO (incl. remind_me, which was 0.64 before)
```
Raw outputs: loops gone, but now `TOL` (not `TOOL`), `re wer_dimect`,
`r_metimetinetime`, `remind_mect` — the model can't spell the function words at all.
The reminder_me "0.64" was purely the `memememe` filler parsing as valid JSON.

## Conclusion
**Hypothesis REJECTED.** It was UNDERTRAINING, not decode. The penalty removed the
loops and exposed that the model never learned the routing grammar. Loss curve
(still falling at 0.22 @ epoch 30) agrees.

## Decision
- rep_penalty STAYS in the toolkit (default 1.0 = off; useful later for stable models),
  but it is NOT the fix for this baseline.
- Next variable: **more epochs (30 → 60)**, same arch + LR. User declined LR bump
  (instability risk) and bigger model ("feels like cheating" / confounds the test).
- See `2026-07-13-retrain-60ep.md`.

## Tags
decode-fix, rejected, undertrained, repetition-penalty
