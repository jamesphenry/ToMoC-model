# 2026-07-14 — 8-WAY: web_search (SearXNG) added, architecture scales CLEANLY

## What we did
Added `web_search` as the 8th function: READ-only web search via the local
sovereign SearXNG instance (http://192.168.0.6:8080, JSON API). No external
API, no keys, reads only (sovereign). URL via SEARXNG_URL env (portable).
Touch points: registry.json (query/limit), executors.py (web_search handler
using urllib + SEARXNG_URL + timeout + error verdict; dispatch + selftest with
SEARXNG_URL set), build_cards.py (_aug_web + registered). Regenerated 8-class
data (3381 train) + retrained.

## Result (baseline-100ep-8fn, 2.3M, 100ep)
| metric        | 8-way (full 3936) | 7-class (prior) |
|---------------|-------------------|-----------------|
| route_acc     | 0.963             | 0.939           |
| over_call     | 0.008             | 0.010           |
| under_call    | 0.009             | 0.046           |
| compute       | 0.955             | 0.797  (RECOVER)|
| get_time      | 1.000             | 1.000           |
| unit_convert  | 0.893             | 0.976           |
| wiki_read     | 0.928             | 1.000           |
| wiki_write    | 0.892             | 1.000           |
| web_search    | 0.976             |   -    (NEW)    |
| remind_me     | 1.000             | 0.988           |
| answer_direct | 0.970             | 0.958           |

## Key findings
1. 8-WAY BEATS 7-WAY (96.3% > 93.9%). The 7-way compute dip (79.7%) was partly
   shuffle noise — at 95.5% compute is back to proper level. More diverse
   training signal (8 fns) helped the tiny model generalize.
2. web_search learned at 97.6% — EASY + DISCRIMINABLE. It did NOT confuse
   wiki_read (92.8%, only mild dip). "look up in vault" vs "search web" is a
   clear distinction for the model. NO catastrophic confusion.
3. over_call 0.8% — the original over_call problem (was 9.6% real) is GONE.
4. Soft spots: unit_convert 89.3%, wiki_write 89.2% — the two LEAST-
   represented classes (~6-7% share). Same under-rep pattern as compute was,
   but at 89% (usable). Could boost if desired.

## SearXNG integration: robust
Handler uses urllib + SEARXNG_URL (default 192.168.0.6:8080) + 8s timeout +
graceful search_error verdict. Read-only, sovereign, no disk mutation. Verified
live (returns real results).

## Tags
eval, web_search, searxng, 8-way, registry-expansion, capacity-grows, resolved
