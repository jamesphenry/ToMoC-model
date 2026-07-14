# Findings — index

Dated, decision-capturing docs from the train→eval→discuss loop. Each entry
links a finding to the action it triggered. Read top-down; newest first.

Format per file: `YYYYMMDD-<slug>.md` — what we ran, what we saw, the diagnosis,
and the decision. Keep it brutal and short. Reproducibility > prose.

## Entries
- [2026-07-13 baseline-train](2026-07-13-baseline-train.md) — first from-scratch run: 30ep d192/4L/6H, route_acc 0.40, repetition collapse.
- [2026-07-13 rep-penalty-decode-fix](2026-07-13-rep-penalty-decode-fix.md) — added rep_penalty to break mememe loops; REJECTED (made it worse → undertraining).
- [2026-07-13 retrain-60ep](2026-07-13-retrain-60ep.md) — single-variable: 30→60 epochs, same arch+LR. DONE (loss 0.20→0.096); eval pending.
- [2026-07-13 wandb-registry-link](2026-07-13-wandb-registry-link.md) — TWO collections (tomac-models + tomac-datasets); doc pattern blocked by server team-mismatch; custom collections WORK. FINAL.
- [2026-07-14 over_call (B)](2026-07-14-overcall-b.md) — over_call was mostly a HARNESS BUG (answer_direct-as-TOOL miscounted). Fixed: real over_call 328->91 on full set, 0 on val. Real cause = chit-chat misrouted + HALLUCINATED `get_me` (not in registry).
- [2026-07-14 A/B 100vs200](2026-07-14-ab-100vs200.md) — CLEAN A/B on sealed val: 100ep 88.5% vs 200ep 70.5%. 200ep HURT (under_call 0->21%). SWEET SPOT = 100ep/2.3M. CONCLUSIVE.
- [2026-07-14 200ep-overfit-probe](2026-07-14-200ep-overfit-probe.md) — FIRST look (confounded by data-shift). Superseded by A/B above: 200ep regressed, not just "diminishing."
- [2026-07-14 100ep-control](2026-07-14-100ep-control.md) — CONCLUSIVE: get_time 0%->66% on SAME 2.3M arch, 60->100ep only. Pure undertraining, NOT structural. Epochs>>capacity.
- [2026-07-14 decode-rep-penalty](2026-07-14-decode-rep-penalty.md) — 60ep +rep1.2 = +4 route_acc but a TRADE (compute/unit_convert drop). Harness bug: per-fn `name==gold` undercounted answer_direct; FIXED to use correct_route.
- [2026-07-14 get-time-inspect](2026-07-14-get-time-inspect.md) — answer_direct is 64% (summary miscounted via pred=None); get_time=0% is a `get_t_t_t` repetition collapse, NOT data starvation.
- [2026-07-13 weave-blocked](2026-07-13-weave-blocked.md) — self-hosted wandb has no Weave subsystem; staying on run-based eval logging.
