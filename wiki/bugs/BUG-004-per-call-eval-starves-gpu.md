## BUG-004 (anticipated, designed out) — per-call eval starves the GPU
- **Symptom (in smol):** eval ran at 100% CPU / 12% GPU for 7+ min.
- **Root cause:** 60+ separate `generate()` calls are host-bound sync.
- **Fix in tomac:** `eval_router.generate_all()` batches all prompts into one
  forward pass, left-padded so prompt ends align, chunked at `batch=16` so a
  big set doesn't OOM the P4. Verified pattern from smol BUG-005/007.
