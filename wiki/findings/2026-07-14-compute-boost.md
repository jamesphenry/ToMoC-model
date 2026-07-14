# 2026-07-14 — compute-boost: weakest class FIXED, new official baseline

## What we did (single variable)
Added `--compute-boost N` to build_cards.py: appends N EXTRA compute cards
(varied numbers) via _aug_compute. Kept the proven distribution
(augment=80, multiply=3, val-split) and added compute-boost=200.
Compute share in train: 32.4% (729 cards). Retrained 100ep.

## Result (baseline-100ep-computeboost, 2.3M, 100ep)
| metric        | val (82) | full (1998) |
|---------------|----------|-------------|
| route_acc     | 0.890    | 0.944       |
| over_call     | 0.000    | 0.000       |
| under_call    | 0.098    | 0.047       |
| compute       | 0.860    | 0.860       |
| get_time      | 0.750    | 0.843       |
| unit_convert  | 0.833    | 0.857       |
| wiki_read     | 1.000    | 1.000       |
| remind_me     | 1.000    | 1.000       |
| answer_direct | 1.000    | 1.000       |

## vs prior best (b1b2-fix)
route_acc 81.2% -> 94.4% (full). over_call 2.7% -> 0.0% (TRUE zero, no
parser band-aid). compute 42% -> 86%. answer_direct 93% -> 100%.

## Why it worked (the real lesson)
The "TOL" cue garble + compute weakness were BOTH symptoms of compute being
UNDER-REPRESENTED in training (only ~12% of cards). The tiny 2.3M char model
never saw enough "TOOL compute {<digits>}" examples to (a) learn the cue
confidently and (b) transcribe digits into the JSON. Boosting compute to 32%
of train fixed BOTH at once. The earlier TOL->TOOL parser hack was a dead end
(it just relabeled a genuine ~13% over_call on chit-chat); training-side data
balance is the correct lever.

## FALSE START this session (documented, reverted)
Tried normalizing "TOL"->"TOOL" in parse_call regex (TOO?L). Recovered 90
compute cards (42%->77%) BUT over_call spiked 2.7%->12.8% and answer_direct
cratered 93%->66%: the model genuinely emits "TOL <realfn>" on ~13% of
chit-chat (real weakness, not a parser artifact). Reverted. Lesson: a parser
band-aid that trades one class's errors for another is NOT a fix — solve it
in the data/training.

## NEW OFFICIAL BASELINE: baseline-100ep-computeboost
route_acc 94.4% full / 89.0% val, over_call 0.0%, under_call 4.7%.
Only get_time lags (84%) — known 2nd-hardest, acceptable.

## Tags
eval, compute-boost, class-balance, new-baseline, over_call-solved, resolved
