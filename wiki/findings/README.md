# Findings — index

Dated, decision-capturing docs from the train→eval→discuss loop. Each entry
links a finding to the action it triggered. Read top-down; newest first.

Format per file: `YYYYMMDD-<slug>.md` — what we ran, what we saw, the diagnosis,
and the decision. Keep it brutal and short. Reproducibility > prose.

## Entries
- [2026-07-14 capacity-bump REGRESSED](2026-07-14-capacity-bump-regressed.md) — baseline-big (10.9M) HONEST eval: route_acc 0.25, under_call 0.75 (collapsed to answer_direct). Bigger≠better on same data/epochs. ROLLBACK via promote.py. Root cause = undertraining at new capacity, not arch.
- [2026-07-14 vram-spike-baseline-big](2026-07-14-vram-spike-baseline-big.md) — 5.5 GB VRAM spike during eval was PyTorch allocator fragmentation, NOT model size (~44 MB weights). 8 GB P4 headroom to ~100M params; only concurrent multi-model serving bites.
- [2026-07-14 baseline-train](2026-07-13-baseline-train.md) — first from-scratch run: 30ep d192/4L/6H, route_acc 0.40, repetition collapse.
- [2026-07-13 rep-penalty-decode-fix](2026-07-13-rep-penalty-decode-fix.md) — added rep_penalty to break mememe loops; REJECTED (made it worse → undertraining).
- [2026-07-13 retrain-60ep](2026-07-13-retrain-60ep.md) — single-variable: 30→60 epochs, same arch+LR. DONE (loss 0.20→0.096); eval pending.
- [2026-07-13 wandb-registry-link](2026-07-13-wandb-registry-link.md) — TWO collections (tomac-models + tomac-datasets); doc pattern blocked by server team-mismatch; custom collections WORK. FINAL.
- [2026-07-14 over_call (B)](2026-07-14-overcall-b.md) — over_call was mostly a HARNESS BUG (answer_direct-as-TOOL miscounted). Fixed: real over_call 328->91 on full set, 0 on val. Real cause = chit-chat misrouted + HALLUCINATED `get_me` (not in registry).
- [2026-07-14 A/B 100vs200](2026-07-14-ab-100vs200.md) — CLEAN A/B on sealed val: 100ep 88.5% vs 200ep 70.5%. 200ep HURT (under_call 0->21%). SWEET SPOT = 100ep/2.3M. CONCLUSIVE.
- [2026-07-14 200ep-overfit-probe](2026-07-14-200ep-overfit-probe.md) — FIRST look (confounded by data-shift). Superseded by A/B above: 200ep regressed, not just "diminishing."
- [2026-07-14 100ep-control](2026-07-14-100ep-control.md) — CONCLUSIVE: get_time 0%->66% on SAME 2.3M arch, 60->100ep only. Pure undertraining, NOT structural. Epochs>>capacity.
- [2026-07-14 get-time-inspect](2026-07-14-get-time-inspect.md) — answer_direct is 64% (summary miscounted via pred=None); get_time=0% is a `get_t_t_t` repetition collapse, NOT data starvation.
- [2026-07-14 8-WAY web_search](2026-07-14-8way-web-search.md) — web_search (SearXNG) added as 8th fn. 8-way BEATS 7-way (96.3% > 93.9%); compute recovered 79.7%->95.5%; web_search 97.6%, NO wiki_read confusion. over_call 0.8% (was 9.6%). SearXNG integration robust (read-only, SEARXNG_URL env).
- [2026-07-14 7-WAY wiki_write](2026-07-14-7way-wiki-write.md) — wiki_write added (7th fn, gated vault writer). Architecture scales cleanly (wiki_write 100%), but CAPACITY TRADEOFF: compute regressed 97.7%->79.7% on identical set (hardest class pays first). Fix = re-boost compute.
- [2026-07-14 get_time FIXED](2026-07-14-get-time-fixed.md) — FINAL BASELINE: get_time 84%->100% via `tz` arg rename (kills `get_timezone` hallucination) + get-time-boost. route_acc 96.9% full / 96.3% val, over_call 1.5%, all classes 92-100%.
- [2026-07-14 compute-boost](2026-07-14-compute-boost.md) — NEW OFFICIAL BASELINE: compute-boost=200 fixed weakest class (42%->86%). route_acc 94.4% full / 89% val, over_call 0.0%, under_call 4.7%. Parser TOL-hack was a FALSE START (reverted).
- [2026-07-14 B arc RESOLVED](2026-07-14-b-arc-resolved.md) — over_call SOLVED (get_me hard-rejected, 9.6%->2.7%). Root cause of the "B broke routing" scare was a VAL-SPLIT VOLUME COLLAPSE bug, NOT B1/B2/augment. Fix: preserve train volume. Re-anchor technique saved us.
- [2026-07-14 disambiguation REGRESSED](2026-07-14-disambiguation-regressed.md) — multi-tool mix (2-3 item subsets, gold 42% of appearances) COLLAPSED get_time via catastrophic interference. route_acc 96.3%->75.3%. DO NOT SHIP; rolled back to 8fn.
- [2026-07-14 disambiguation FIXED](2026-07-14-disambiguation-fixed.md) — full-list needle-style multi-tool (every card lists all 8 tools, even gold) CURES the interference. get_time 100%, multi-tool gold_hit 100% (was 0/400 on untrained 8fn). Single-tool dips to 93.7% (tunable dilution). Two shipping candidates: 8fn (96.3%, no disambig) vs mt2 (93.7% + disambig). DECISION PENDING.
- [2026-07-13 weave-blocked](2026-07-13-weave-blocked.md) — self-hosted wandb has no Weave subsystem; staying on run-based eval logging.
