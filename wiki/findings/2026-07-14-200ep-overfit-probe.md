# 2026-07-14 — 200ep overfit probe (sealed val split)

## Setup (HONEST instrumentation added this session)
- `build_cards.py --val-frac 0.15 --augment 120`: stratified split, dedup
  by request TEXT so ZERO val->train leakage (verified 0 leaked, deterministic
  at seed=42). 885 train / 61 val unique cards.
- Train 200ep on cards_train.jsonl (2.3M control arch, same LR 3e-3).
- Eval on BOTH train split and sealed val split -> read train/val gap.

## Result
| metric | train | val | gap |
|--------|-------|-----|-----|
| route_acc | 0.777 | 0.705 | -7.2 |
| well_formed | 0.788 | 0.705 | -8 |
| over_call | 0.017 | 0.033 | + |
| under_call | 0.145 | 0.213 | + |
| get_time | 0.769 (60/78) | 0.500 (2/4) | noise* |
| compute | 0.514 (165/321) | 0.474 (9/19) | ~ |
| wiki_read | 0.974 | 1.000 | + |
| remind_me | 0.969 | 1.000 | + |

*val get_time 2/4 = 4 cards, statistical noise not a trend.

## VERDICT (nuanced, NOT "overfit wins/loses")
1. Train/val gap is only ~7pt -> NOT a gross overfit. Model still generalizes.
2. BUT route_acc did NOT beat 100ep-control (0.83 on old full set). Two
   confounds make this NOT a clean epoch comparison:
   - DATA DISTRIBUTION SHIFT: 100ep used old 946-card cards.jsonl (no augment).
     200ep trains/evals on augmented cards_train/val (harder, more paraphrase
     variety). So 0.83 -> 0.777/0.705 is apples-to-oranges.
   - under_call JUMPED 0.0% (100ep) -> 14.5%/21.3% (200ep): at 200ep the model
     is now UNDER-calling (emits no tool when one is needed) — opposite failure
     of 100ep. Smells like too many epochs made it conservative on the
     tool/no-tool boundary.
3. get_time on TRAIN held 77% (collapse resolved at 100ep, stays resolved).

## LESSON
Pushing epochs alone has HIT DIMINISHING RETURNS on this augmented dist, and
introduced a NEW failure mode (under_call). The next lever is NOT more epochs
or bigger model — it's the tool/no-tool DECISION BOUNDARY (under_call). That's
a training-dynamics / data-balance issue, not capacity.

## Open question (needs clean A/B, not this confounded run)
Is 200ep actually worse than 100ep, or just measured on harder data? Must
re-evaluate 100ep AND 200ep on the SAME sealed val split to answer. Pending.

## Tags
eval, overfit-probe, val-split, under_call, diminishing-returns, confounded
