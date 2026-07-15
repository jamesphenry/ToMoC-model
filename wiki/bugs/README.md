# Bugs — index

> Real bugs, real hotfixes. Negative results are intentional parts of the lab,
> not accidents to hide. Each entry: symptom -> root cause (measured, not guessed)
> -> fix. Mirror the smol-lab discipline: diagnose before despairing.

One file per bug: `BUG-NNN-<slug>.md`. Add a new bug as a new file + a row here.
Newest last (by number).

## Entries
- [BUG-001](BUG-001-executors-syntax.md) — `executors.py` syntax error on first write (RESOLVED, pre-first-run)
- [BUG-002](BUG-002-drifted-cue.md) — drifted cue kills habit transfer
- [BUG-003](BUG-003-strict-parser.md) — strict parser hides good calls
- [BUG-004](BUG-004-per-call-eval-starves-gpu.md) — per-call eval starves the GPU
- [BUG-005](BUG-005-lora-wrong-base.md) — LoRA loaded on the wrong base
- [BUG-006](BUG-006-decode-mismatch.md) — live server silently samples; eval is greedy (MISMATCH) — **RESOLVED 2026-07-15** (greedy live decode temp=0)
- [BUG-007](BUG-007-rep-penalty-inflation.md) — eval inflates route accuracy via rep_penalty the live path never applies — **RESOLVED 2026-07-15** (default rep_penalty 1.0; root cause was decode mismatch, not capacity)
- [BUG-008](BUG-008-wandb-silent-noop.md) — wandb run silently no-ops when WANDB_API_URL unset; progress lost to W&B
