## BUG-007 — eval inflates route accuracy via rep_penalty the live path never applies — **OPEN (quality/metrics, decode half FIXED)**

- **Symptom:** eval scored compute name-acc 38/40 (95%) on a *favorable subset* at `rep_penalty=1.4`; the LIVE path (sampling at `temperature=1.0`, `rep_penalty=1.0`) gave 23/40 on the same subset and produced `TOOOOL`/garbage loops. `route_accuracy` scores only the **function name**, never the JSON args — so a garbage call still counts "correctly routed".
- **Root cause (decode half — FIXED):** TWO mismatches: live sampled at `temperature=1.0` AND its `rep_penalty` default (1.0) differed from eval's (1.4). `rep_penalty=1.4` breaks the degenerate loop the model falls into; without it, live users hit the raw broken behavior. **Fixed (BUG-006 + this):** live now `temperature=0.0` (greedy, no sampling) + `rep_penalty=1.4`; eval default restored to `rep_penalty=1.4` (was briefly 1.0). eval == live on ONE contract. Ad-hoc verify confirmed: greedy deterministic, no sampling, eval==live.
- **The REAL model quality (ground truth, promote.py pass-61, full 3936-card set, `rep_penalty=1.0`):** `baseline-100ep-8fn` route_acc=**0.8956**, well_formed=**0.8913**. The model WORKS at ~0.90. (The original "~90%" claim was correct; the later "38/40 / ~90% were favorable-subset artifacts, model is broken" over-correction — commit 129085b — was WRONG: it was based on a pathological 40-card subset that happens to all fail, while the full set is fine.)
- **Residual weakness (real, non-representative):** on a hard 40-card compute subset, name-acc = **0/40** at both rep=1.0 and 1.4. Canonical compute (`12 / 33` → routes compute) works, so this is a hard-phrasing cluster, not total failure. `rep_penalty` helps the FULL set (reduces loops, nudges accuracy up) but does NOT fix the 0/40 hard subset.
- **Metric gap (guardrail unmet):** `route_accuracy` is name-only; **arg-correctness** (full `TOOL name {args}` match vs gold) is missing. A "95% accurate" router can still hand `29+23` to compute.

### Status
- Decode contract unified (temp=0 + rep=1.4, both paths). ✅
- 8fn is a works ~0.90 router on the full set. ✅ (capacity scaling dead — 10.9M regressed to 0.25.)
- BUG-007 stays **OPEN** for: (a) arg-correctness metric, (b) compute arg-transcription on hard phrasings.

### Next
- Full honest eval of `baseline-100ep-8fn` at the unified contract (`rep_penalty=1.4`, temp=0) to get the user-facing number + per-fn breakdown (pending; promote pass-61 was at rep=1.0).

### Addendum 2026-07-15 (pass-62 — real user-facing numbers)
- Full eval at the unified contract (`rep_penalty=1.4` + greedy temp=0): **route_accuracy 0.9627**, **well_formed 0.9220**, over_call 0.0076, under_call 0.0091.
- Per-fn: get_time **1.000** (849/849), compute **0.9545** (819/858), answer_direct **0.9695** (954/984).
- So the "0/40 compute" was a pathological 40-card subset, NOT representative — full-set compute is **95.5%**. The README's original "96.3%" was correct (measured at rep=1.4 on the full set); the "crutch-inflated" suspicion was wrong — `rep_penalty=1.4` is a legitimate anti-loop mechanism the small model needs, now in BOTH paths, so the number is honest AND consistent (eval==live).
- **BUG-007 decode half is fully FIXED + verified.** The bug stays OPEN only for the **missing arg-correctness metric** (name-only `route_accuracy` can still hide wrong JSON args). Compute arg-transcription is NOT a routing failure (95.5% routes correctly); arg-correctness is the unmet guardrail.
