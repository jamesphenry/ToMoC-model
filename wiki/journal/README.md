# Journal — index

> Running log of what we built, what we learned, and the real numbers. One file
> per dated entry: `YYYY-MM-DD-<slug>.md`. Bugs in [../bugs/](../bugs/README.md);
> detailed phase plans in [../plans/](../plans). This is the STORY; the others
> are the reference. Newest first.

**Policy:** entries are append-only — never rewrite an existing entry's body;
corrections go as footnotes (`[^n]`). Every major model-size change gets its own
dated entry citing the forcing bug/metric.

## Entries
- [2026-07-15 capacity REVERTED](2026-07-15-capacity-revert.md) — 10.9M scaling thread dead. 8fn (2.3M) is the sovereign router. Garbling was BUG-006/007 (decode temp + rep-crutch), NOT capacity. Real fix = greedy live decode + honest rep_penalty=1.0 eval.
- [2026-07-14 capacity-bump](2026-07-14-capacity-bump.md) — 2.3M → 10.9M (baseline-big A/B); forced by BUG-007 capacity wall + BUG-008 missing run.
- [2026-07-13 foundations](2026-07-13-foundations.md) — thesis, from-scratch decision, Phase 0/1 scaffold, empty numbers table.
