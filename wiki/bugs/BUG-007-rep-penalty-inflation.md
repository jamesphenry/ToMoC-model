## BUG-007 — eval inflates route accuracy via rep_penalty the live path never applies — **REOPENED 2026-07-15 (model weakness, not just decode)**

- **Symptom:** eval reports compute name-acc 38/40 (95%) on `baseline-100ep-8fn`; the LIVE greedy path (rep_penalty=1.0) gives 23/40 (58%). `what is 3 + 4` → `29 + 23`; `12 / 33` → `12 / 3`. The model *loops* (`TOOOOL`, repeated chars) and emits garbage when not suppressed.
- **Root cause (decode half):** `eval_router.generate_batch` defaulted `rep_penalty=1.4` while the live server used `temperature=1.0` sampling — TWO mismatches (rep setting AND sampling). The `rep_penalty=1.4` breaks the degenerate loop the model falls into; without it (live, rep=1.0) users hit the raw broken behavior. `route_accuracy` also only scores the **function name**, never the JSON args — so a `TOOOOL`/garbage call counts as "correctly routed".
- **Guardrail:** eval must use the SAME decode settings as the live server. Add an **arg-correctness** metric (full `TOOL name {args}` match vs gold) alongside name-only `route_accuracy`.

### What we fixed (REAL, verified)
- **Decode unification (BUG-006 + this):** live now `temperature=0.0` (greedy, no sampling) AND `rep_penalty=1.4`; eval default changed back to `rep_penalty=1.4` (was briefly 1.0). So eval == live on ONE contract (temp=0, rep=1.4). Ad-hoc verify confirmed: greedy deterministic, no sampling, eval==live.
- This kills the *measurement* mismatch (eval no longer scores a different decode than users see).

### What we got WRONG (corrected 2026-07-15, after ad-hoc verify)
- The "38/40 at rep=1.4" and "live 23/40, ~0.90 route_acc" numbers were measured on a **favorable subset** and DO NOT reproduce. Ad-hoc verify on the canonical 40 compute cards in `cards.jsonl` (same greedy + rep=1.4 contract): **compute name-acc = 0/40** — at BOTH rep=1.0 and rep=1.4.
- So the model is NOT "fine once decoded correctly." It is **genuinely weak at compute routing + arg transcription** on out-of-favorable-subset phrasings. `12 / 33` → `TOOL compute {"12 / 3"}` (right tool, wrong math) works; `what is 3 + 4` → `TOOL 94 ct_/ 3{"` (garbage) fails. Canonical get_time (`Asia/Tokyo`) works perfectly.
- The earlier "RESOLVED / model was always fine" claim (commit 7740b57) was **false**. The decode fix is real, but it did NOT make the router work.

### Current honest status (OPEN)
- Decode contract unified (temp=0 + rep=1.4, both paths). ✅
- Model quality: PROTOTYPE, not sovereign. Handles canonical phrasings; fails compute transcription + function discrimination on harder phrasings. Real route_acc must be re-measured on the FULL set at the unified config (pending full eval).
- Arg-correctness metric: still missing (guardrail unmet). route_accuracy remains name-only.
- Capacity scaling: A/B showed 10.9M is WORSE, so the fix is NOT "make it bigger" — it's train the 2.3M model harder / better cards, or accept prototype status.

### Next
- Run full honest eval of `baseline-100ep-8fn` at unified config (rep=1.4, temp=0) to get the REAL route_acc + per-fn breakdown.
- Decide: more training on 8fn (compute-boost cards) vs accept prototype. Discuss before GPU.
