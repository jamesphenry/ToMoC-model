# 2026-07-14 — get_time-inspect (finding C)

## Question
Why is `get_time` at 0% and is `answer_direct` really at 9%? Inspect raw eval log.

## Method
Parsed `logs/eval_router_baseline-60ep_*.jsonl` (946 rows; schema
q/gold/pred/pred_args/well_formed/correct_route/raw).

## FINDING 1 — answer_direct is NOT broken (summary miscounted)
- Log shows **210/328 = 64%** correct, not 9%.
- The 9% came from the summary counting ONLY exact `pred=="answer_direct"`
  matches. But for answer_direct, `pred=None` (model emits no TOOL call,
  just answers) is ALSO correct — and 181/328 rows are exactly that
  (e.g. q="Good night" -> raw="Good night", no TOOL). So 64% is real.
- Hole closed. Move on.

## FINDING 2 — get_time = spelling/repetition collapse, NOT data starvation
- 123 cards (13% of data) — NOT starved.
- Model is NOT confused about routing: it never emits compute/wiki_read/etc.
  for get_time questions. It TRIES to spell get_time and fails:
  - `ge` (52), `getime` (30), `gezome` (10), `get_t_t_t_t..._time` (8),
    `gezone` (4), None (10).
  - `gezome` = "ge" + "zone" (timezone arg bleeding into the fn name).
  - `get_t_t_t_t_t_time` = learned "get_" then loops the "t" instead of
    continuing "ime". Classic alternating-loop failure on the underscore boundary.
- `remind_me` (9 chars!) is 100% — so it's not a length problem per se,
  it's a specific collapse on the `get_`->`t` loop.

## Implication
get_time failure is a **decode-time repetition collapse**, not capacity or balance.
It's exactly the failure mode `rep_penalty` targets. At 30ep rep_penalty hurt
(route_acc 0.40->0.35) because the model was undertrained and suppressing
loops removed its only behavior. At 60ep (route_acc 0.56, competent) a MILD
rep_penalty may now break the `get_t_t_t` loop WITHOUT nuking the others.

## Next step (proposed)
Decode-test: re-eval 60ep checkpoint with `--rep-penalty 1.2` (mild). Pure
eval, no retrain. If get_time lifts and others hold -> free win + lesson learned
(rep_penalty helps a TRAINED model, hurt an UNTRAINED one). If not -> more
epochs or get_time-specific data augmentation.

## Tags
eval, diagnosis, get_time, repetition-collapse, answer_direct-miscount
