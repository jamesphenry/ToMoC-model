# 2026-07-14 — get_time FIXED: FINAL BASELINE (route_acc 96.9%, over_call 1.5%)

## What we did (two get_time fixes, one retrain)
1. DECOUPLE arg token from fn name: renamed get_time arg `timezone` -> `tz`
   in registry.json + executors.py + build_cards.py _aug_time. The model was
   merging "get_time" + "timezone" (seen together in targets) into the
   HALLUCINATED fn `get_timezone` (not in registry -> B2-rejected -> under_call).
   Removing the "timezone" token from targets kills the merge.
2. Added --get-time-boost N (mirrors --compute-boost): extra get_time cards
   (city/timezone variety) so "time in <city>" -> get_time (not answer_direct).
   Kept compute-boost=200 (proven). Retrained 100ep on 2721 cards.

## Result (baseline-100ep-gtboost, 2.3M, 100ep)
| metric        | val (82) | full (1998) |
|---------------|----------|-------------|
| route_acc     | 0.963    | 0.969       |
| over_call     | 0.000    | 0.015       |
| under_call    | 0.024    | 0.012       |
| compute       | 1.000    | 0.977       |
| get_time      | 1.000    | 1.000       |
| unit_convert  | 1.000    | 0.964       |
| wiki_read     | 1.000    | 1.000       |
| remind_me     | 0.700*   | 0.927       |
| answer_direct | 1.000    | 0.960       |

*remind_me 70% on val is a SMALL-SAMPLE artifact (only 10 val cards; full=92.7%).

## vs prior best (computeboost)
route_acc 94.4% -> 96.9%. get_time 84% -> 100%. over_call 0% -> 1.5% (marginal;
one stray chit-chat->tool on full set). compute 86% -> 97.7%. ALL classes now
92-100% except remind_me (92.7% full, fine).

## THE WHOLE B ARC, RESOLVED
Started: over_call 9.6% real (chit-chat misrouted + hallucinated `get_me`).
- B2: parse_call rejects fns not in registry -> `get_me` never routed.
- Root-cause #1: val-split VOLUME COLLAPSE bug (starved model, TOLA garbage).
- Root-cause #2: compute UNDER-REPRESENTED (12%) -> boosted to 32%.
- Root-cause #3: get_time arg `timezone` primed `get_timezone` hallucination
  -> renamed arg to `tz` + boosted city-time variety.
End: route_acc 96.9%, over_call 1.5%, all classes 92-100%.

## FINAL OFFICIAL BASELINE: baseline-100ep-gtboost
## Tags
eval, get_time, tz-rename, get-time-boost, final-baseline, over_call-solved, resolved
