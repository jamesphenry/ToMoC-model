## BUG-006 — live server silently samples; eval is greedy (MISMATCH) — **RESOLVED 2026-07-15**

- **Symptom:** `bash run.sh --ask "what is 3 + 4"` → `TOOOOL compute {"expression": "47 + 3"}` (wrong tool spelling + wrong math), scored as "answered directly". The demo looked broken; eval reported compute=0.975.
- **Root cause:** `router_server.route_once` called `model.generate(..., temperature=1.0)` → **random sampling** on every live request. Eval used a *different* path (`generate_batch`, argmax). The two code paths decode differently, so eval numbers never matched what a user sees.
- **Fix (model_scratch.generate):** `temperature <= 0` now forces `argmax` greedy decode (matches the eval path). `router_server.py` now passes `temperature=0.0` explicitly so the live path is deterministic + identical to eval.
- **Guardrail:** there must be exactly ONE decode path used by both live and eval. Any future non-greedy decode is an experiment flag, never the default.

### Resolution (2026-07-15)
- **Committed fix:** `router_server.py` generate at `temperature=0.0`; `model_scratch.generate` greedy guard (`temperature <= 0` → argmax). Both already in the working tree; committed in the "decode fix" commit.
- **Why this is THE fix (not capacity):** the model's greedy output was always correct — it was the `temperature=1.0` live sampling producing degenerate draws. No GPU retrain needed. The 2.3M `baseline-100ep-8fn` is the sovereign router; capacity scaling was a dead end (see wiki/findings/2026-07-15-baseline-big-aug-regressed.md).
- **Verify:** live dogfood `run.sh --ask "what is 3 + 4"` must yield `TOOL compute {"expression":"3+4"}` (no loops, correct args). Tracked for the post-fix dogfood test.
