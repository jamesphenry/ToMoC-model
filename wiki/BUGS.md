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

*Add new bugs here as they're found. Each entry should be reproducible + have a
verified fix. The honest bug log is what makes the project可信 (trustworthy).*
