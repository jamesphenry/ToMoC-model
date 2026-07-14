# 2026-07-14 — decode-test rep_penalty 1.2 + harness bug

## Decode test (no retrain): 60ep ckpt, --rep-penalty 1.2
| fn | rep=1.0 | rep=1.2 | Δ |
|----|--------|--------|---|
| answer_direct | 64.0% | 82.0% | +18 ✅ |
| get_time | 0.0% | 11.4% | +11 ✅ |
| wiki_read | 45.5% | 52.0% | +6 ✅ |
| remind_me | 100% | 96.7% | -3 (~hold) |
| unit_convert | 73.4% | 61.3% | -12 ❌ |
| compute | 40.5% | 21.4% | -19 ❌ |
| route_acc | 56.0% | 60.0% | **+4** |

**Verdict:** a blanket rep_penalty is a TRADE, not a free win. It lifts the
collapsed classes (get_time, answer_direct, wiki_read) but STEALS from the
well-learned ones (compute -19, unit_convert -12). Net +4 route_acc.

## LESSON (updated from 30ep test)
- 30ep + rep_penalty 1.4 -> WORSE (model undertrained, penalty killed its
  only behavior).
- 60ep + rep_penalty 1.2 -> +4 net but a TRADE across classes.
- rep_penalty is a blunt tool; a single global value can't fix one class's
  loop without hurting another's. Better lever = more epochs / targeted data,
  not a global decode knob.

## HARNESS BUG FOUND + FIXED (eval_router.py)
Per-fn tally used `name == gold`. For `answer_direct` the correct output is
NO TOOL CALL, so `name` is None, never the literal string -> answer_direct
was scored 0/328 (artifact). FIX: tally `c_ok` (correct_route), which already
treats (gold_no_tool && pred_no_tool) as correct. Now per-fn == correct_route
exactly. Old summary's `fn.answer_direct 0.088` was the bug, not the model.

## Re-scored truth (consistent metric)
- 60ep rep=1.0: answer_direct 64%, get_time 0%, route_acc 56%
- 60ep rep=1.2: answer_direct 82%, get_time 11%, route_acc 60%

## Tags
eval, rep-penalty, decode-test, harness-bug, answer_direct, get_time
