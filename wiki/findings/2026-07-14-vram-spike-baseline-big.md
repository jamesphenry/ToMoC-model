# Finding: baseline-big VRAM spike (5.5 GB) is allocator noise, not model size

**Date:** 2026-07-14
**Context:** first honest eval (rep_penalty=1.0) of `baseline-big` (10.9M, d384/6L)
on the full 3936-card set, right after the pass-55 training run completed.

## What we saw
- During the eval the GPU memory jumped to **~5.5 GB used** (of 8 GB) — a steep
  jump from the ~1.8 GB the training run itself reserved.
- When the eval process ended, memory dropped straight back to **0 MiB**.
- The eval had to be re-run (interruptions killed the first attempt before it
  logged; second attempt is grinding as of writing).

## Diagnosis
The 10.9M model does NOT need 5.5 GB. Weights are **~44 MB** (10.85M × 4 bytes).
The spike is **PyTorch's caching allocator reserving + fragmenting CUDA memory**,
not model footprint:
1. Training left ~1.8 GB *reserved* (allocator holds blocks instead of returning
   them to the OS — by design, for reuse speed).
2. The eval then reserved its own batched-decode buffers on top (`bsz=32`,
   `max_new=160` holds input+generated token tensors on GPU).
3. On an 8 GB card the allocator fragments and balloons to ~5.5 GB *reserved*
   but mostly idle. Process exit frees it all → 0 MiB.

## Decision / limits
- **No constraint for current approach.** Model footprint is ~44 MB weights +
  a few hundred MB working set. 8 GB P4 has huge headroom.
- Capacity scaling to **~50–100M params** (~200–400 MB weights) is still fine.
- VRAM only bites at **~200–300M params** OR **concurrent multi-model serving**
  (router + local judge like qwen2.5:1.5b for the dream-cycle LLM-judge). That's
  a phase-7 problem, mitigable with `expandable_segments` (already set) or a
  smaller judge.
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` is already exported for
  training/eval — keep it; it reduces fragmentation on the P4.

## Reproducibility
- Watch: `nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total`
- The 5.5 GB reading was captured mid-eval; the 0 MiB after exit confirms it was
  reserved/fragmented, not live model memory.

## Follow-up — THE REGRESSION
- Honest eval of `baseline-big` (rep_penalty=1.0, 3936 cards) landed:
  **route_acc 0.2500, well_formed 0.2538, under_call 0.7447, over_call 0.0000.**
  It collapsed to `answer_direct` on everything (984/984 right, all other fns 0/0).
  The 10.9M model is a **CATASTROPHIC regression** vs the 2.3M 8fn (~0.96).
- This is exactly BUG-007's predicted failure: more capacity + same data + no
  extra training signal → model never learned the routing habit, under-calls.
- `promote.py` correctly **rolls back** (incumbent 8fn wins). See
  `2026-07-14-capacity-bump-regressed.md`.
