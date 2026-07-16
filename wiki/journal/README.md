# Journal — index

> Running log of what we built, what we learned, and the real numbers. One file
> per dated entry: `YYYY-MM-DD-<slug>.md`. Bugs in [../bugs/](../bugs/README.md);
> detailed phase plans in [../plans/](../plans). This is the STORY; the others
> are the reference. Newest first.

**Policy:** entries are append-only — never rewrite an existing entry's body;
corrections go as footnotes (`[^n]`). Every major model-size change gets its own
dated entry citing the forcing bug/metric.

## Entries
- [2026-07-16 bitnet weights-only (b) COLLAPSED identically](2026-07-16-bitnet-wo-collapse.md) — variant (b): removing INT8 activation clamp changed NOTHING (route_acc 0.25, same answer_direct collapse). Root cause = ternary weight rounding, not activation path. 1-bit core NOT viable as trained; p2p-any-device fork dead for now.
- [2026-07-15 future: p2p on any device](2026-07-15-future-p2p-any-device.md) — USER VISION: if 1-bit router works, extend to a sovereign p2p mesh of tiny-device routers. Recorded future thread, not actioned.
- [2026-07-15 bitnet COLLAPSED](2026-07-15-bitnet-collapse.md) — BitNet b1.58 @2.3M/100ep collapsed (route_acc 0.25 / under_call 0.75, only answer_direct learned). Negative result; options (a)tune LR warmup (b)weights-only variant (c)accept.
- [2026-07-15 baseline PINNED](2026-07-15-baseline-pinned.md) — 8fn (2.3M) frozen as known-good floor (copy at models/scratch/baseline-100ep-8fn.PINNED). pass-63: route_acc 0.9627 / arg_accuracy 0.5366.
- [2026-07-14 capacity-bump](2026-07-14-capacity-bump.md) — 2.3M → 10.9M (baseline-big A/B); forced by BUG-007 capacity wall + BUG-008 missing run.
- [2026-07-13 foundations](2026-07-13-foundations.md) — thesis, from-scratch decision, Phase 0/1 scaffold, empty numbers table.
