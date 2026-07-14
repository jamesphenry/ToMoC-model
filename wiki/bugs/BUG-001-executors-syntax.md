## BUG-001 — `executors.py` syntax error on first write (RESOLVED, pre-first-run)
- **Symptom:** `write_file` lint reported `SyntaxError: '(' was never closed`
  at the `compute` subprocess return.
- **Root cause:** a missing closing paren on `return json.loads(proc.stdout.strip()`.
- **Fix:** closed the paren. Self-test (`functions/executors.py` `__main__`)
  now runs every handler cleanly: `compute`→63, dangerous input fails safe,
  `get_time`/`unit_convert` correct, `wiki_read` miss handled, `remind_me` gated.
- **Lesson:** run a handler self-test under the base python (no torch) before
  wiring it into the GPU pipeline — catches the cheap bugs fast.
