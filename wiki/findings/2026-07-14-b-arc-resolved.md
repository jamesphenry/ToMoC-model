# 2026-07-14 — B arc RESOLVED: over_call fix + the volume-collapse bug

## TL;DR
over_call is SOLVED (get_me hard-rejected by B2; real over_call 9.6% -> 2.7%).
The "B1+B2 broke tool routing" reading was WRONG — the real culprit was a
val-split bug that COLLAPSED the train set, not B1/B2/augment.

## What actually happened
1. B2 (decode hardening): parse_call rejects fn names not in registry.json.
   get_me now HARD-REJECTED -> never routed/executed. (keep — free win)
2. B1 (chit-chat variety): _CHITCHAT 22 -> 38 strings. (fine, keep)
3. First retrain (augment=120) COLLAPSED: route_acc 57%, compute 3%.
   -> WRONG diagnosis: "too much no-tool / augment too high".
4. Re-anchor: evaled the ORIGINAL 100ep-control checkpoint on current full
   set -> 87% route_acc, compute 91%. PROVES model code + eval are fine.
5. ROOT CAUSE FOUND: build_cards val-split did `cards = train_unique`,
   DROPPING all multiply/augment duplicates. Train shrank to ~177 cards at
   68.5% no-tool. The 2.3M char model UNDERFIT and garbled the cue token
   (emitted "TOLA" instead of "TOOL" -> parse_call finds no call -> under_call).
6. FIX: keep ALL train cards whose q is in the train split (preserve volume).
   Now 1668 train cards, 36% no-tool (matches proven baseline distribution),
   0 val leakage, deterministic at seed=42.

## Result after fix (baseline-100ep-b1b2-fix, 100ep, 2.3M)
| metric        | val (52) | full (1998) |
|---------------|----------|-------------|
| route_acc     | 0.827    | 0.812       |
| over_call     | 0.000    | 0.027       |
| under_call    | 0.154    | 0.150       |
| compute       | 0.462    | 0.419       |
| unit_convert  | 0.917    | 0.833       |
| wiki_read     | 1.000    | 0.904       |
| remind_me     | 1.000    | 0.951       |

over_call 2.7% (was 9.6% real pre-fix) — get_me GONE. Tool routing recovered.

## LESSON (your principle, again, the hard way)
A training-data PATH bug (volume collapse) masqueraded as a model/balance
failure. The fix was found by RE-ANCHORING the known-good checkpoint, not by
tuning knobs. When a retrain regresses, first rule out the DATA PIPELINE
(volume, distribution, leakage) before blaming the model or the data content.

## NEXT (optional, single variable)
compute is the weak class (42% full) — most expression-syntax variety, hardest
for the tiny char model. Options: (a) leave as-is (over_call solved, good
enough baseline); (b) boost compute card variety/volume moderately; (c) accept
compute as the known-hard class and document it.

## Tags
eval, B1, B2, over_call, volume-collapse-bug, re-anchor, root-cause, resolved
