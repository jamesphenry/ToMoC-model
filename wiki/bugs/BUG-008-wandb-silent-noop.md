## BUG-008 — wandb run silently no-ops when WANDB_API_URL unset; progress lost to W&B
- **Symptom:** `baseline-big` training (pass-54) ran to completion locally and
  logged to `benchmarks/passes.db`, but **never appeared in the self-hosted W&B**
  (last visible run stayed `pass-53`). No error, no warning — the run "worked"
  everywhere except the place the user watches.
- **Root cause:** `scripts/wandb_tracker.py:81` only instantiates the real
  tracker when `WANDB_API_URL` is set; otherwise `get_tracker()` returns a
  silent `DummyTracker`. The training launch set `WANDB_MODE=offline` but never
  `WANDB_API_URL`, so every `tracker.*` call was a no-op. Worse: with no real
  run, there was no `offline-run-*` artifact either — so `wandb sync` could NOT
  recover it after the fact. `WANDB_ENTITY` also defaults to None → a run that
  DID go live would land under `user/tomac`, not `cravingpine/tomac` where the
  dashboard is watched.
- **Impact:** pass-54 exists in the local cost DB but is **missing from W&B** —
  a real gap in the user's "everything in W&B" requirement. The run was killed
  and restarted online (pass-55) so the data lands; pass-54 is documented as a
  known missing run, not silently forgotten.
- **Fix (DONE).** `wandb_tracker.get_tracker()` now calls `_warn_dummy(reason)`
  on every fallback path (wandb not importable / `WANDB_API_URL` unset /
  `_RealTracker` init failed), printing a loud stderr banner. Setting
  `TOMAC_REQUIRE_WANDB=1` turns the fallback into a hard `RuntimeError` so real
  training launches abort instead of running blind. Verified both paths.
  Launches still need the env wired (`WANDB_API_URL=http://192.168.0.6:8081`,
  `WANDB_ENTITY=cravingpine`); the warning/assert just makes a miss impossible
  to overlook. Preferred launch: `TOMAC_REQUIRE_WANDB=1 ... train_router.py`.
- **Guardrail:** a training run that completes MUST have produced a W&B run OR
  an `offline-run-*` dir; if neither, the launcher should fail loudly. Add this
  check to the run wrapper so "no W&B" can never again be mistaken for "success".
