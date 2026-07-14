# wiki/BUGS.md — failure log

> Real bugs, real hotfixes. Negative results are intentional parts of the lab,
> not accidents to hide. Each entry: symptom → root cause (measured, not guessed)
> → fix. Mirror the smol-lab discipline: diagnose before despairing.

---

## BUG-001 — `executors.py` syntax error on first write (RESOLVED, pre-first-run)
- **Symptom:** `write_file` lint reported `SyntaxError: '(' was never closed`
  at the `compute` subprocess return.
- **Root cause:** a missing closing paren on `return json.loads(proc.stdout.strip()`.
- **Fix:** closed the paren. Self-test (`functions/executors.py` `__main__`)
  now runs every handler cleanly: `compute`→63, dangerous input fails safe,
  `get_time`/`unit_convert` correct, `wiki_read` miss handled, `remind_me` gated.
- **Lesson:** run a handler self-test under the base python (no torch) before
  wiring it into the GPU pipeline — catches the cheap bugs fast.

---

## BUG-002 (anticipated, designed out) — drifted cue kills habit transfer
- **Symptom (in smol):** a training/eval cue that isn't byte-identical silently
  breaks the tool-call habit; eval shows the model "forgot" how to call.
- **Root cause:** the priming string lived in two places and drifted.
- **Fix in tomac:** the cue + prompt builder + call parser live in ONE module
  (`scripts/tomac_common.py`). Train (`train_router.py`) and eval
  (`eval_router.py`) both import it. There is exactly one source of truth.
- **Guardrail:** never edit `CUE` without retraining; never fork `parse_call`.

---

## BUG-003 (anticipated, designed out) — strict parser hides good calls
- **Symptom (in smol):** `well_formed=0.488` was a MEASUREMENT bug — a truncated
  call (missing closing quote) was scored malformed even though the model made
  the right decision.
- **Root cause:** `max_new_tokens` too short + a strict regex requiring the
  closing delimiter.
- **Fix in tomac:** `parse_call()` is TOLERANT. If the JSON is opened but
  truncated/unbalanced, it recovers the function name (and any recoverable
  args) and returns `well_formed=False` — so ROUTING is scored even when the
  JSON is imperfect. `max_new_tokens=128` in eval leaves headroom for the JSON.
- **Guardrail:** routing metrics (`route_accuracy`, per-fn) are the trustworthy
  signal; `well_formed` is reported separately so a format slip can't masquerade
  as a routing failure.

---

## BUG-004 (anticipated, designed out) — per-call eval starves the GPU
- **Symptom (in smol):** eval ran at 100% CPU / 12% GPU for 7+ min.
- **Root cause:** 60+ separate `generate()` calls are host-bound sync.
- **Fix in tomac:** `eval_router.generate_all()` batches all prompts into one
  forward pass, left-padded so prompt ends align, chunked at `batch=16` so a
  big set doesn't OOM the P4. Verified pattern from smol BUG-005/007.

---

## BUG-005 (anticipated, designed out) — LoRA loaded on the wrong base
- **Symptom (in smol):** a 360m LoRA loaded on the 135m base shape-mismatched
  and produced garbage (or a silent error).
- **Root cause:** eval hardcoded the base model name regardless of the adapter.
- **Fix in tomac:** `eval_router.py` reads `base_model_name_or_path` from the
  adapter's own `adapter_config.json`. Any-size adapter loads on its correct base.

---

## BUG-006 — live server silently samples; eval is greedy (MISMATCH)
- **Symptom:** `bash run.sh --ask "what is 3 + 4"` → `TOOOOL compute {"expression": "47 + 3"}` (wrong tool spelling + wrong math), scored as "answered directly". The demo looked broken; eval reported compute=0.975.
- **Root cause:** `router_server.route_once` called `model.generate(..., temperature=1.0)` → **random sampling** on every live request. Eval used a *different* path (`generate_batch`, argmax). The two code paths decode differently, so eval numbers never matched what a user sees.
- **Fix (model_scratch.generate):** `temperature <= 0` now forces `argmax` greedy decode (matches the eval path). `router_server.py` now passes `temperature=0.0` explicitly so the live path is deterministic + identical to eval.
- **Guardrail:** there must be exactly ONE decode path used by both live and eval. Any future non-greedy decode is an experiment flag, never the default.

---

## BUG-007 — eval inflates route accuracy via rep_penalty the live path never applies
- **Symptom:** eval reports compute name-acc 38/40 (95%) on `baseline-100ep-8fn`; the LIVE greedy path (rep_penalty=1.0) gives 23/40 (58%). `what is 3 + 4` → `29 + 23`; `12 / 33` → `12 / 3`. The model *loops* (`TOOOOL`, repeated chars) and emits garbage when not suppressed.
- **Root cause:** `eval_router.generate_batch` defaults `rep_penalty=1.4` (line 101). That repetition penalty breaks the degenerate loop that the *under-trained* model falls into, masking the failure. The live server used the model's default `rep_penalty=1.0` (no suppression), so users hit the raw broken behavior. `route_accuracy` also only scores the **function name**, never the JSON args — so a `TOOOOL`/garbage-math call still counts as "correctly routed".
- **Measurement (greedy, same 40 compute cards):** rep_penalty=1.0 → 23/40 name-acc, loops to 160 chars; rep_penalty=1.4 → 38/40. **~38pt inflation** between "what we score" and "what users see".
- **Diagnosis / root cause (the real bug):** the model is **under-capacity + under-trained** for robust single-sequence generation. It learned the *statistical shape* of routing but not the output grammar reliably — it needs the crutch to not loop. This is the capacity wall: 192-d / 4-layer (~2.3M) is too small to hold 8 routing habits + arg transcription without looping on long-ish generations.
- **Fix direction (in progress):** scale capacity (bigger d_model / n_layers) + train with EOS so the model learns to STOP instead of looping. Tracked as the `baseline-big` capacity A/B. Until then: live = eval decode (BUG-006), and README "96.3%" numbers are **name-only + crutch-inflated** and must be re-baselined honestly after the bigger model lands.
- **Guardrail:** eval must use the SAME decode settings as the live server (no hidden rep_penalty). Add an **arg-correctness** metric (full `TOOL name {args}` match vs gold) alongside name-only `route_accuracy`, or the router can be "95% accurate" while handing `29+23` to compute.

---

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

---

*Add new bugs here as they're found. Each entry should be reproducible + have a
verified fix. The honest bug log is what makes the project可信 (trustworthy).*
