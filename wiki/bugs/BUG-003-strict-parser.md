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
