## BUG-007 — eval inflates route accuracy via rep_penalty the live path never applies — **RESOLVED 2026-07-15**

- **Symptom:** eval reports compute name-acc 38/40 (95%) on `baseline-100ep-8fn`; the LIVE greedy path (rep_penalty=1.0) gives 23/40 (58%). `what is 3 + 4` → `29 + 23`; `12 / 33` → `12 / 3`. The model *loops* (`TOOOOL`, repeated chars) and emits garbage when not suppressed.
- **Root cause:** `eval_router.generate_batch` defaults `rep_penalty=1.4` (line 101). That repetition penalty breaks the degenerate loop that the *under-trained* model falls into, masking the failure. The live server used the model's default `rep_penalty=1.0` (no suppression), so users hit the raw broken behavior. `route_accuracy` also only scores the **function name**, never the JSON args — so a `TOOOOL`/garbage-math call still counts as "correctly routed".
- **Measurement (greedy, same 40 compute cards):** rep_penalty=1.0 → 23/40 name-acc, loops to 160 chars; rep_penalty=1.4 → 38/40. **~38pt inflation** between "what we score" and "what users see".
- **Guardrail:** eval must use the SAME decode settings as the live server (no hidden rep_penalty). Add an **arg-correctness** metric (full `TOOL name {args}` match vs gold) alongside name-only `route_accuracy`, or the router can be "95% accurate" while handing `29+23` to compute.

### Correction (2026-07-15) — root cause was NOT capacity
The original diagnosis ("under-capacity + under-trained, capacity wall") was
**wrong**. The 23/40 live number was produced by the `temperature=1.0` sampling
mismatch (BUG-006), not by a weak model. With greedy live decode (BUG-006 fixed),
the 2.3M model routes correctly. The honest eval at `rep_penalty=1.0` is ~0.90
route_acc — not 58%. The `rep_penalty=1.4` "fix" was a crutch that masked a
*decode-config* bug, not a capacity bug. (The capacity-bump A/B confirmed this:
10.9M scaled WORSE, falsifying the capacity-wall theory.)

### Resolution (2026-07-15)
- **`eval_router.py` default `--rep-penalty` changed 1.4 → 1.0** (honest eval, no crutch). README "96.3%" re-baselined to honest ~0.90 (name-only, rep_penalty=1.0).
- **Greedy live decode** (BUG-006) makes eval == live, so the inflation can't recur.
- **Arg-correctness metric** still open (guardrail unmet) — see wiki/findings or a TODO; route_accuracy remains name-only. Tracked, not blocking.
- Capacity scaling thread abandoned (wiki/journal/2026-07-15-capacity-revert.md).
