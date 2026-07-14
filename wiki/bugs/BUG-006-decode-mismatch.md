## BUG-006 — live server silently samples; eval is greedy (MISMATCH)
- **Symptom:** `bash run.sh --ask "what is 3 + 4"` → `TOOOOL compute {"expression": "47 + 3"}` (wrong tool spelling + wrong math), scored as "answered directly". The demo looked broken; eval reported compute=0.975.
- **Root cause:** `router_server.route_once` called `model.generate(..., temperature=1.0)` → **random sampling** on every live request. Eval used a *different* path (`generate_batch`, argmax). The two code paths decode differently, so eval numbers never matched what a user sees.
- **Fix (model_scratch.generate):** `temperature <= 0` now forces `argmax` greedy decode (matches the eval path). `router_server.py` now passes `temperature=0.0` explicitly so the live path is deterministic + identical to eval.
- **Guardrail:** there must be exactly ONE decode path used by both live and eval. Any future non-greedy decode is an experiment flag, never the default.
