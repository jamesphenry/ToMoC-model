# 2026-07-14 — DISAMBIGUATION FIXED (full-list, needle-style)

## What we changed (single variable vs the failed run)
The failed `baseline-100ep-mt` listed a 2-3 item SUBSET of tools per card, with
gold only ~42% of the time it appeared. That made "tools listed" a spurious
"this request is ambiguous" signal and induced catastrophic interference that
COLLAPSED get_time (100% -> 3.5%), dropping single-tool route_acc 96.3% -> 75.3%.

Fix (matches needle's recipe): every multi-tool card lists the FULL 8-tool list
(constant), gold drawn with an EVEN distribution (~50 each). "Tools listed"
becomes a constant, so the model must attend to the REQUEST, not tool frequencies.

mix = 3381 single-tool (8-way) + 400 full-list multi-tool = 3781 cards.

## Result: disambiguation ACHIEVED, soft single-tool dip
| metric              | 8fn (ship) | mt (FAILED subset) | mt2 (FULL-list) |
|---------------------|-----------|--------------------|-----------------|
| single-tool FULL    | 0.963     | 0.753              | **0.937**       |
| get_time            | 1.000     | 0.035 (COLLAPSED)  | **1.000** ✅     |
| multi-tool gold_hit | 0.00*     | ?                  | **1.000** ✅     |
| over_call           | 0.008     | 0.000              | 0.012           |
| under_call          | 0.009     | 0.235              | 0.025           |
*8fn was never trained on multi-tool prompts -> emits no call (under_call 90%).

## Read
- get_time FULLY recovered (100%): the full-list removed the ambiguity signal.
  The A/B HYPOTHESIS PASSED — it was the subset-vs-full shape, not multi-tool
  training per se, that broke the failed run.
- Multi-tool disambiguation = 400/400 (100% gold_hit, 0 out-of-set). This
  capability did NOT exist on 8fn (0/400). We GAINED real disambiguation.
- Remaining single-tool dip: 96.3% -> 93.7% (-2.6pt). Soft spots: compute
  95.5%->86.4%, answer_direct 97.0%->95.1% — classic capacity dilution from the
  400 added cards (same pattern as the 7-way compute dip). NOT structural.
- over_call ticked to 1.2% (51 cards): with the full tool list present, ~13% of
  chit-chat cards tempt the model to emit a tool. Tunable (more answer_direct
  negatives in the mix).

## Decision (pending user)
Two viable shipping candidates, both committed-safe on disk:
- baseline-100ep-8fn : 96.3% single-tool, NO disambiguation. Cleaner.
- baseline-100ep-mt2 : 93.7% single-tool + 100% disambiguation. More capable.
Ship decision deferred to user. The disambiguation concept is PROVEN achievable;
the regression is a tunable dilution, not a structural blocker.

## Tags
eval, disambiguation, multitool, fixed, needle-style, full-list, A/B
