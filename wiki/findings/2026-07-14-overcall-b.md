# 2026-07-14 — over_call: real cause found (B)

## Discovery
The reported over_call (e.g. 6.6% val, 328/946 full) was mostly a HARNESS
BUG, same class as the per-fn name==gold bug: `answer_direct` emitted as
`TOOL answer_direct {}` (the correct no-tool signal) was counted as
over_call. Fixed: over_call now = predicted a REAL tool (not answer_direct,
not None) on a no-tool card.

## Real over_call (after fix)
- 100ep-control FULL set: 328 -> 91 real wrong-tool calls (27.7% of 328
  no-tool cards).
- 100ep-control VAL set: 0 real (all 4 were the artifact).
- So on held-out data the model does NOT over-call. The 6.6% val over_call
  in the A/B was entirely the artifact.

## The 91 real offenders (what to actually fix)
Cluster on CHIT-CHAT misrouted to tools, PLUS a HALLUCINATED function:
- "Good morning" / "Good night" -> get_me   <- get_me DOES NOT EXIST in registry
- "What's the meaning of life?" / "Can you help me think through a problem?"
  -> get_time
- "What can you do?" / "That makes sense, thank you." -> remind_me

## Root causes
1. get_me is INVENTED — model emits a function name absent from the registry.
   Decode/harness should reject unknown names (treat as malformed -> under_call
   or a new "unknown_fn" bucket). Output hardening, not just data.
2. Chit-chat/no-tool class lacks VARIETY for greetings & philosophical Qs, so
   the tiny model overgeneralizes "sentence with a question mark -> tool".

## Fix options (next baby step)
A) build_cards: add more no-tool chit-chat variety (greetings, philosophy,
   meta-Qs) so the boundary is learned. Single-variable data change.
B) Harden decode: reject names not in registry.json -> prevents get_me
   hallucination from counting as a routed call.
C) Both.

## Tags
eval, over_call, harness-bug, get_me-hallucination, chit-chat, B
