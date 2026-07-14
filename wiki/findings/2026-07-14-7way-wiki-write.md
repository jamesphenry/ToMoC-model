# 2026-07-14 — 7-WAY: wiki_write added, architecture scales, compute trades capacity

## What we did
Added `wiki_write` as the 7th function: gated vault-note writer (proposes a
markdown note, NEVER mutates disk — mirrors remind_me's sovereignty guarantee).
Touch points: registry.json (params title/content/category), executors.py
(gated wiki_write handler + dispatch + selftest), build_cards.py (_aug_wiki_write
+ registered in _AUGMENTERS). Regenerated 7-class data (3030 train) + retrained.

## Result (baseline-100ep-7fn, 2.3M, 100ep)
| metric        | 7-way (full 3567) | 6-class (prior) |
|---------------|-------------------|-----------------|
| route_acc     | 0.939             | 0.969           |
| over_call     | 0.010             | 0.015           |
| under_call    | 0.046             | 0.012           |
| compute       | 0.797             | 0.977  (REGRESS)|
| get_time      | 1.000             | 1.000           |
| unit_convert  | 0.976             | 0.964           |
| wiki_read     | 1.000             | 1.000           |
| wiki_write    | 1.000             |   -    (NEW)    |
| remind_me     | 0.988             | 0.927           |
| answer_direct | 0.958             | 0.960           |

## The key finding: CAPACITY TRADEOFF, not a bug
The architecture scales to 7 functions CLEANLY: wiki_write learned at 100%,
no class collapsed, over_call still ~0. BUT compute regressed 97.7%->79.7% on
the IDENTICAL test set (verified: 7fn scored compute 80.2% on the old 1998-card
6-class set that gtboost scored 97.7% on). Adding a 7th function spread the
2.3M params' capacity thinner; the HARDEST class (compute: digit transcription
+ cue) paid first. Same pattern as when get_time/compute were under-weighted.

## Why wiki_write is EASY (100% immediately)
Gated, simple args (title/content), no transcription of numbers, clear cue.
Contrast: compute needs to copy digits from prompt -> JSON (hard for char model).

## Fix is the SAME proven lever
Boost compute in the 7-way setting (compute-boost=400) to reclaim capacity.
Single-variable, already-proven. Cheap retrain.

## Tags
eval, wiki_write, 7-way, capacity-tradeoff, registry-expansion, resolved-structure
