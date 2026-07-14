# 2026-07-14 — DISAMBIGUATION MIX: REGRESSED (catastrophic interference)

## What we tried
Baby-step multi-tool: append "Available tools: ..." to the prompt (tomac_common
build_prompt(tools=...)), mix 400 multi-tool disambiguation cards (gold + 1-2
distractors) into the 8-way single-tool training set, retrain 100ep. Goal: teach
the router to PICK the right tool when several are plausible (a selection
boundary single-tool cards never teach).

## Result: REGRESSION (do NOT ship)
| metric        | mt-mix (now) | 8-way baseline (prior) |
|---------------|--------------|------------------------|
| route_acc     | 0.753        | 0.963                  |
| over_call     | 0.000        | 0.008                  |
| under_call    | 0.235        | 0.009                  |
| get_time      | 0.035  (COLLAPSE) | 1.000            |
| compute       | 0.972        | 0.955                  |
| web_search    | 1.000        | 0.976                  |
| wiki_read     | 0.867        | 0.928                  |
| remind_me     | 0.695        | 1.000                  |
| wiki_write    | 0.976        | 0.892                  |
| answer_direct | 0.945        | 0.970                  |

## Root cause (diagnosed from eval log + multi-tool card stats)
get_time predicts `None` (no call) for 819/849 cards -> under_call, NOT misroute.
In the multi-tool train set, get_time is PRESENTED as a distractor 132 times but
GOLD only 56 times (42%). The model over-learned "get_time is usually NOT the
answer when tools are listed" and that interference spilled onto BARE prompts,
collapsing get_time to 3.5%. Classic catastrophic interference + the same
capacity-dilution pattern seen 3x (compute, then compute again) — but worse
because get_time was the weakest easy class and 11% new imbalanced data tipped it.

## Why the concept is still sound (but execution was wrong)
needle (26M fn-call model) uses exactly this "tools in context" recipe and it
WORKS. Our failure is in the DATA, not the idea:
1. Distractor imbalance: each tool is gold only ~42% of the time it's presented.
   Should be rebalanced so each tool is gold >=50% of the time it appears.
2. 400 raw cards is too few / too noisy to teach a 2.3M model without dilution.
3. The "Available tools:" prompt path is a NEW distribution; mixing 11% of it
   into an 89% single-tool model shifted the decision boundary.

## Decision: DO NOT COMMIT. Roll back to baseline-100ep-8fn (96.3%, committed).
This is a failed experiment — report honestly, keep the good baseline.

## If we retry (future, NOT now): rebalance multi-tool cards so each gold tool
is presented as distractor <=50% of its appearances; OR present the FULL tool
list on EVERY card (all 8 always listed) so "tools listed" stops being a signal
for "ambiguous". That second variant matches needle more closely (full context
always present) and avoids the distractor-imbalance trap.

## Tags
eval, disambiguation, multitool, regression, catastrophic-interference, abandoned
