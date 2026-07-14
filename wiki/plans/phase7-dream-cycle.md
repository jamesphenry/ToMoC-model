# Plan: Phase 7 — Dream Cycle (off-peak self-improvement harness)

**Status:** DESIGN ONLY (no code). Discussion doc, not a spec. Supersedes nothing;
extends [phase6-self-extending.md](phase6-self-extending.md) with the engine that
drives it automatically.

**Goal:** while the homelab is idle (off-peak hours), a gated harness reviews how
tomac was actually used, proposes improvements to its *knowledge* (registry,
cards, vault) — and, only behind a hard quality gate + human approval, retrains
and promotes a better router. The model learns from USE, not from a one-shot
train. No silent self-modification, ever.

---

## ELI5
A waiter who, after closing, reads the night's order tickets and thinks "six
people wanted oat milk and I kept saying no — I should add it." By morning he's
a little better. The "dream" is just that after-hours review, automated, on cheap
electricity. Crucially: for tomac, getting smarter means improving the stuff
AROUND the model (registry = knowledge, cards = lessons, vault = notes), not
mostly the weights. The model is the cheap, replaceable part. On-thesis:
**functions ARE its knowledge.**

---

## Core principle: sensor before brain
"Learns from use" needs USE first. The router today has little real traffic, so
the miss-log would be thin. The dream cycle is worthless without a rich signal to
dream on. Therefore the build order is strictly: **(1) instrument → (2) mine →
(3) propose → (4) gated apply.** Never build tier 4 before tier 1 has data.

---

## The four capability tiers (cheapest first)

### Tier 1 — Registry hygiene (NO GPU)
Mine `logs/` for requests the router got wrong, or answered `answer_direct` when
a tool was clearly wanted. Cluster the misses (cheap embedding or even n-gram).
Output: "23 requests looked like currency conversion but no `currency_convert`
fn exists" → propose a registry entry + seed example cards. This is the automated
feeder for Phase 6's `propose_function`.
- Cost: electricity only, seconds.
- Risk: low — pure proposal text.

### Tier 2 — Card refinement (CHEAP GPU)
For functions with weak per-fn accuracy in the last eval, auto-synthesize
contrast / hard-negative cards from the miss log, append to `build_cards.py`
inputs, retrain, and **PROMOTE only if the new checkpoint beats the incumbent on
the sealed val split.** Self-tuning loop with a hard quality gate.
- Cost: ~$0.003/retrain (P4, 100ep).
- Risk: medium — gated by A/B + rollback.

### Tier 3 — Vault maintenance (NO GPU, optional LLM-judge)
The vault is the model's MEMORY. Unlike code, the model MAY write/edit it
autonomously — but every entry carries a trust flag and the model is honest
about that flag when it uses the entry (see the vault trust state machine below).
Dream-cycle vault work: dedupe / summarize `wiki_read` targets, write new
memories from what it learned, flag stale notes, propose merges.
- Cost: electricity (+ optional local judge model).
- Risk: low-medium — self-writes land as `unapproved` (usable but flagged);
  `canon` notes are readonly and never touched.

### Tier 4 — Self-directed retrain (THE AMBITIOUS ONE)
The harness decides WHEN retraining is worth the ~$0.003 based on accumulated
drift (miss-rate over threshold, N new proposals accepted, etc.), runs it
off-peak, logs cost to W&B, auto-rolls-back on regression.
- Cost: bounded, tracked.
- Risk: highest — only attempt once tiers 1–3 are trusted.

---

## The trust ladder (the core safety model)
Three artifacts, three different trust levels, chosen by ONE principle:
**objective automatic pass/fail test → autonomy; provenance flag → self-serve
but honest; judgment call → human approval.**

| Artifact | Model may... | Gate |
|----------|--------------|------|
| **Weights** (`model.pt`) | retrain + promote + rollback, no asking | AUTONOMOUS — objective sealed-val eval (new ≥ old, else discard). Blast radius = one `.pt` file. |
| **Vault** (memory) | write/edit freely; warns on use when unapproved | SELF-SERVE + FLAGGED — see state machine below. `canon` = readonly, model cannot touch. |
| **Code / registry / cards** | *propose* diffs only | HUMAN APPROVAL — dream writes patches to `proposals/`, you review + merge. NEVER self-applies. |

Why the split is correct, not just cautious: a bad **weight** can only misroute,
and the eval gate catches it before promotion (worst case: keep the old model,
repo untouched). A bad **code** edit has no objective "better?" number and can
break the harness or its own rollback — so it needs *your* judgment. The
dividing line is "is there a clean automatic pass/fail test," not "how scary."

## Vault trust state machine (memory)
The vault is the model's memory; every note carries a trust flag. The model is
HONEST about the flag when it uses the note — the warning is provenance, not
friction.
- **`unapproved`** — model wrote/edited it itself. Fully usable, but when the
  model draws on it to answer or act, it politely warns: "using a memory you
  haven't approved yet." Usually fine; sometimes you'll edit it to "the way I
  would do it" and bless it.
- **`approved`** — you reviewed (maybe edited) and flipped the flag. Trusted, no
  warning.
- **`canon` / `readonly`** — your gospel lock. Model may READ but cannot edit or
  overwrite. "This is correct, hands off."

**Flag storage:** YAML frontmatter per note is the source of truth
(`status: unapproved|approved|canon`) — git-diffable, travels with the file,
survives moves. A generated sidecar cache (`vault/.trust.json`, path→status)
gives the model an O(1) scan without parsing every file; it is disposable and
rebuildable from frontmatter, so it can never become a second source of truth.

## The non-negotiables (still hold)
1. **Objective gate on weights.** A new checkpoint must beat the incumbent on the
   sealed val split or it is discarded. The incumbent `model.pt` is never
   overwritten in place. This is what makes autonomous retrain safe.
2. **Human approval on code.** Code, registry, and card edits are PROPOSALS
   (`proposals/YYYY-MM-DD.md` + patches). The dream cycle never self-applies a
   code change. Same spirit as `remind_me` / `wiki_write` (proposed_write).
3. **Everything logged to W&B.** The dream cycle is itself a tracked experiment
   stream: what it read, what it learned, what it proposed, accept/reject,
   vault writes + flag changes, cost/GPU watts. Off-peak runs are a first-class
   metric surface, not a black box.

---

## Sketch of the moving parts (names, not code)
- `scripts/dream.py` — the orchestrator; a cron/off-peak entrypoint. Reads
  `logs/`, runs the enabled tiers, writes proposals. Defaults to DRY (propose
  only); `--apply` requires an explicit approved proposal id.
- Structured miss-logging in `router_server.py` — every live request logs
  `{ts, query, routed_fn, args, well_formed, latency, (optional) user_verdict}`
  to `logs/router_traffic.jsonl`. This is the sensor; build it first.
- `proposals/` — dated markdown, one file per dream run: what was mined, the
  clusters, the concrete proposed diffs (registry entries, new cards, vault
  merges), each with an accept/reject checkbox a human ticks.
- Quality gate reuses the existing `eval_router.py` sealed-val path + the new
  arg-correctness metric (already planned) so promotion decisions are honest.
- W&B: a `dream` run type alongside `train` / `eval`.

---

## Relationship to other phases
- **Phase 6 (self-extending registry)** is the *reactive* half: the model flags
  gaps at inference. Phase 7 is the *proactive* engine that mines those flags
  (plus silent misses the model didn't flag) off-peak and turns them into
  reviewed proposals. Phase 7 without Phase 6 still works (it mines logs); Phase
  6 without Phase 7 relies on the human to notice proposals.
- **Phase 3 (smallest model)** matters here: cheap retrain is what makes tier 2/4
  economically sane. A 10.9M/$0.003 retrain is a rounding error; a 7B finetune
  would kill the dream-cycle premise.

---

## Open questions (for discussion, not yet decided)
1. **Traffic problem.** Where does real USE come from? Dogfooding only, or wire
   the router into an actual homelab surface (a chat endpoint) so the miss-log
   grows organically? The dream cycle's value scales with traffic volume.
2. **Miss labeling.** How do we KNOW a route was wrong without a human verdict on
   every request? Options: (a) explicit thumbs-down in the live loop, (b) an
   LLM-judge pass over traffic (cost + a judge dependency), (c) heuristics
   (executor errored, user rephrased immediately = implicit miss). Probably (c)
   first, (a) as opt-in.
3. **Proposal fatigue.** If the dream cycle proposes 40 changes a night, nobody
   reviews them. Needs ranking + a cap (top-N highest-impact proposals only).
4. **Catastrophic interference** (already bit us — see the disambiguation
   findings). Auto-added cards can wreck a working function's accuracy. The A/B
   gate catches it, but tier 2 must eval ALL functions, not just the target.
5. **Code-vs-memory boundary (RESOLVED — see trust ladder).** The model may
   self-write the VAULT (memory) freely but flagged `unapproved` and warns on
   use; `canon` notes are readonly. CODE/registry/cards are PROPOSALS only, never
   self-applied — human approval via `proposals/`. Weights retrain autonomously
   behind the sealed-val gate. The dividing line is "is there an objective
   automatic pass/fail test" (weights: yes→autonomy; code: no→your approval).
6. **Vault warning UX.** How loud is the "using unapproved memory" notice? Options:
   (a) inline prefix on every response ("⚠ unaudited memory"), (b) only when the
   memory drives a tool CALL or a factual claim, not chit-chat, (c) a daily digest
   of which unapproved notes were used (least intrusive). Lean (b)+(c).
7. **Canon precedence.** If an `unapproved` self-edit contradicts a `canon` note,
   which wins in a merge? The `canon` note is readonly so the model can't
   overwrite it — but should it be allowed to *add* a conflicting `unapproved`
   note and warn? Probably yes, with the warning surfacing the conflict.

---

## Definition of done (for the DESIGN, this doc)
- A shared mental model of the four tiers, the safety invariants, and the
  build order (sensor → mine → propose → gated apply).
- Agreement on which tier is the real first baby-step (leaning: tier-1 sensor +
  miss-logging, because everything downstream needs the data).
- Open questions parked here until we pick a starting increment.
