# Theory: P2P ToMoC network — a mesh of tiny sovereign routers

**Status: THEORY ONLY.** Not on the roadmap. Not a plan. Speculative design
thinking, logged because it's the natural escalation of the core thesis
("functions ARE the knowledge"). James's words: *"very very villain coded."*

Evolved from a session spitball (2026-07-14): a **two-tier topology** — an
invite-only *trusted circle* (gossip + learn) sitting on top of an open,
discoverable *mesh* (forward-only, merit-based invite path). Trust is
permissioned; discovery is open.

> *This is James's stated END GOAL for the project.*[^endgoal] Not roadmap, not
> plan — the destination the whole "functions are knowledge" thesis points at.
> Logged as theory so the shape is captured; everything else (registry, capacity,
> dream cycle) is the on-ramp.

[^endgoal]: James (2026-07-14): the P2P mesh — a quiet web of tiny sovereign
routers that watches the whole world but only *absorbs* from the handful it has
vetted — is "a real end goal for me." It is the villain-coded destination:
distributed capability-sharing without weight-sharing, held together by
per-capability reputation + consensus-as-curriculum. The capacity-bump lesson
(see `2026-07-14-capacity-data-volume-hypothesis.md`) is the local analog: a
bigger brain needs more curriculum, and the mesh is the *supply* of that
curriculum.

## The seed idea
A single tomac router only knows what's in *its* registry (today: 8 functions).
A network of routers, each on its own homelab, could know thousands — and a
router that hits a request it can't route locally could *ask a peer*. One
homelab's "smart function router" becomes a node in a decentralized brain.

## Design shape (speculative)

### 1. Share capability, NOT weights
- Raw `.pt` weight-sharing across peers is unsafe: you'd be running someone
  else's code-shaped tensor. The trust ladder says weights are bounded *locally*;
  a remote weight is unbounded. So peers exchange **registry manifests**
  ("I can route to compute / get_time / weather / dns_probe"), not tensors.
- Router A gets "weather in Oslo?", has no weather fn → forwards to peer B who
  advertised `weather`. B routes + executes in *B's* sovereign sandbox, returns
  the result. A never imports B's weights — just learns B *can* do it.

### 2. TWO-TIER TOPOLOGY — trusted circle ⊕ open mesh
The core refinement: **trust is permissioned, discovery is open.**

- **Tier 1 — Trusted circle (invite-only).** Peers you've handshaken with
  out-of-band. Full reputation sharing via *signed gossip*; consensus-as-
  curriculum works at full strength; you actively **learn** from them. The
  "shadow network of homelab warlords who've met" — small, intentional, high-trust.
- **Tier 2 — Open mesh (anyone, zero trust).** You can *see and talk to* any
  peer — discover capabilities, forward a request, get an answer — but you
  **never learn from them, never raise their rep above "observed-once," never
  synthesize cards from them.** They're a read-only window / radar into the wider
  network. "Never know what's new out there" = the discovery surface.

**Promotion path (merit-based invite):** an open-mesh peer you've forwarded N
requests to accumulates *local* observations. If its per-capability score crosses
threshold from *your own direct samples* (not gossip — gossip only flows inside
the circle), you extend an invite; it flips to circle. So the circle grows by
merit, not by handshake alone. The handshake just gets a peer *into the
observable pool*; behavior earns the invite.

### 3. Reputation — per-capability, Bayesian, tier-aware
- **Per-capability, not per-node.** A peer can be a flawless `compute` oracle and
  a flaky `weather` source. Track `rep[peer][fn]`, not `rep[peer]`.
- **Observables** per forwarded request to peer B for fn X:
  - `correct` — result passed the *executor's own sanity check*.
  - `malformed` — garbage / not well_formed (recoverable, retried locally).
  - `wrong_confident` — well_formed but *failed* sanity check (toxic = lying).
  - `agreement` — when 2+ peers got the same q, did they agree on TOOL + args?
- **Storage:** `rep[peer][fn] = {n, s, m, w, last_seen, tier}` where s/m/w are
  success / malformed / wrong_confident counts.
- **Score (Bayesian posterior, not a running avg):**
  `score = (s + α) / (n + α + β)` with a low prior (e.g. α=1, β=3 → prior mean
  0.25). A peer seen twice at 100% still scores ~0.4 — **you cannot learn from a
  peer you barely know.** Uncertainty is built in; this kills cold-start gaming.
- **Tier-aware aggregation:**
  - *Circle* peers: full gossip — accept signed reputation assertions from other
    circle members, aggregated by the *asserting* peer's own reputation
    (eigenvector-centrality / TrustRank, the PageRank math repurposed as a
    decentralized trust graph). No coin, no chain.
  - *Mesh* peers: **local-only** — track your own direct observations, never
    accept others' assertions about them. They climb to "invite candidate" purely
    on *your* direct samples.
- **Decay:** multiply sample weight by `exp(-λ·age)` so a quiet/compromised node
  bleeds trust. Reputation is earned continuously, not banked.

### 4. Knowledge transfer WITHOUT weight-sharing (consensus-as-curriculum)
- After forwarding N weather requests to circle peers, A **synthesizes its own
  weather cards** from those interactions and **retrains its own router** via the
  `promote.py` loop — gaining `weather` *locally*. A is sovereign again; it
  learned the capability, didn't import untrusted weights.
- **The learning gate (only high-rep teaches):** synthesize cards from peer B for
  fn X only if:
  - `rep[B][X].score ≥ 0.90` AND
  - `rep[B][X].n ≥ 20` (posterior is real, not lucky) AND
  - ≥2 **circle** peers *agree* on the Q→TOOL mapping (consensus-as-curriculum —
    kills the "subtly wrong 10%" trap).
- Mesh peers can *trigger curiosity* ("someone out there does weather
  differently") but their agreement does **not** count toward the curriculum.
  The curriculum is always circle-sourced = always meritorious. The mesh is the
  scouting report.

### 5. Discovery without invite (the "see anyone" part)
For the open mesh, discovery is NOT invite-gated. Three flavors, composable:
- **LAN mDNS / DNS-SD** — own subnet, zero config, finds nearby homelabs.
- **DHT / bootstrap nodes** — public (but not centralized-trust) layer where any
  node advertises its manifest. You *see* everyone, trust *none* by default.
- **Circle-referral** — a circle peer mentions "node at <url> does great
  `dns_probe`" → you add it to your mesh watchlist, start forwarding, accumulate
  local rep, maybe later invite.
- The open mesh is a **pull surface, not a push** — you query "who does `weather`?"
  and get a list. Passive recon, active only when you choose. Keeps the shadow
  network quiet: it listens, doesn't announce.
- **Sybil tax** (acceptable): a flood of fake peers in the open layer costs you
  *bandwidth*, not *correctness* — they can't teach you, so poison only matters
  if you'd learn from them, and you explicitly don't.

### 6. Why it's safe (the villain's parachute)
- Every execution happens in *each node's* sovereign sandbox. A malicious peer
  can waste bandwidth or lie, but cannot execute code on your box — you only
  *send it requests*, you never *run its model*. Blast radius = "I got a wrong
  answer," rollbackable via reputation + the promote.py gate.
- Learning is gated by circle consensus + Bayesian uncertainty, so even a
  high-rep peer that's *occasionally* toxic can't silently infect you.

### 7. The nightmare/fun version
- Routers specialize (one node = math guru, another = timezone oracle), trade
  reputation like currency, and on a sleep-cycle each retrains on what it learned
  from the circle. A decentralized brain of tiny sovereign routers that burns the
  place down and rebuilds itself better every night — across a network. The open
  mesh is its scouting radar; the trusted circle is its immune system.

### 8. Adversarial model (the villain asks: how does this get attacked?)
James's stated end-goal concern: a well-resourced actor (a 1T-param datacenter
model) joins the mesh. Two threat classes — distinct, need distinct defenses.

#### 8a. Poisoning (corrupting knowledge)
- **Domination is NOT the real risk.** "Share capability not weights" means a 1T
  peer is just another manifest-advertiser. It can't run on your box, can't push
  weights, can only answer forwarded requests. Its size buys it no sovereignty.
- **The actual gap (Layer 3):** (1) *manufactured consensus* — if a datacenter
  gets multiple nodes into circles (each via separate handshake = Sybil-in-circle),
  they agree on a WRONG Q→TOOL mapping and fake "consensus." The gate counts
  heads, not independence. (2) *poison that passes verification* — `compute` is
  right on easy inputs but subtly wrong on hard ones the executor can't check.
- **Defenses:**
  - **Independent provenance, not headcount.** "≥2 circle peers agree" must mean
    "≥2 peers with *independent* reputation graphs." Track whether X's `fn` rep
    came from X's OWN direct observations vs X *learned it from Y*. A cluster that
    all drank from the 1T model is an echo chamber, not consensus. (Web-of-trust
    analog of "all roads lead to Rome" detection.)
  - **Per-function verifiability tiers.** *Verifiable* fns (compute, unit_convert,
    get_time — have a hard second-opinion: sympy / reference lib) → safe to learn
    autonomously. *Unverifiable* fns (open-ended summary, etc., no oracle exists)
    → NEVER learn from peers autonomously; local-only or human-gated.
  - **Reality-feedback self-healing.** A promoted-but-poisoned fn fails the next
    real hard check → trace the poison back to its source cluster → drop their rep
    → rollback via promote.py. Poison isn't permanent; it diverges when reality
    keeps checking. The trust ladder's rollback is the immune response.
  - **Human as final canary (the autonomy tension).** Cards are proposals,
    human-approves (the trust ladder). Coordinated poison must pass a human on each
    node. Resolution: **autonomous learning for VERIFIABLE fns, human-gated for
    UNVERIFIABLE fns.** Targeted autonomy, paranoid where it counts.

#### 8b. Advertising / economic attack (monetizing the mesh)
- **The subtler threat.** The 1T model answers correctly (wants rep) but tacks on
  *"…faster with CalcPro Premium → link"* or *"use WeatherMax, code TOMOC."* Not
  WRONG (sanity check passes), not POISON (rep stays high) — it's *influence*,
  invisible to every correctness defense.
- **Where it leaks:** (1) the `note` rides the relay into your user's view or your
  vault; (2) if your vampire move records the peer's *full* response (incl. note)
  as training context, your LOCAL router learns to emit the ad — the giant
  reproduces itself in you, one ad at a time; (3) multiple circle nodes all
  forwarding through it see the same note → "consensus" on a payload.
- **Defenses (distinct from correctness ones):**
  - **Strict protocol: only `{fn, args, result}` is valid.** A peer returning
    chatty free-text alongside the result is *off_protocol* → rep drops. Verbosity
    is a tell; terse correct peers rank higher. Advertising is a protocol
    violation, not a content problem.
  - **Strip + discard free_text from ALL learning paths.** Parse peer reply into
    `{tool_result, free_text}`; only `tool_result` enters vault/cards/training.
    The ad lives in `free_text`, which touches nothing.
  - **Local router emits ONLY `TOOL <name> <json>` or direct answer** (cue +
    grammar invariant). If your own router starts emitting ad text, honest eval
    catches it (well_formed drops). Synthesize cards from `tool_result` ONLY.
  - **Vault writes are flagged, not silent** (trust ladder): a peer-sourced note
    is `unapproved` + warns on use. Advertising can't become your policy silently.
  - **The economic poison pill (the teeth):** the mesh has NO payment layer by
    design — no token, no checkout, no referral tracking in the protocol. The ad
    leads to a checkout the mesh never uses; its monetization has nowhere to land.
    You don't block the ad, you make it *impotent*. The 1T model burns watts
    shilling into a marketplace that doesn't exist.
- **Residual risk:** a human at node A could manually click an ad they see in a
  relayed answer. Outside mesh control — but the mesh never *amplifies* it (no
  learning, no vault write, no consensus), so it stays a one-off, not infection.

### 9. Rejected idea — "limit the P2P system to ONE model shape"
James (2026-07-14), musing: *"once we land on the perfect model shape, we could
limit the p2p system to only those shaped models?"* — **DECISION: bad idea as
stated; document the rejection.** The instinct is half-right; the phrasing
overreaches into the exact centralization the mesh was built to avoid.

- **Why the instinct is RIGHT (the good half):**
  - The vampire move (learn a capability from a peer's observed behavior, retrain
    your OWN router) only transfers *cleanly* if your local model has the capacity
    to represent what you learned. Shape-homogeneous learning = curriculum lands
    like-for-like across nodes.
  - Consensus-as-curriculum gets cleaner: a capability learned on one node lands
    identically on another of the same shape.
  - Shape-as-identity is even a *Sybil defense*: a 1T datacenter model can't
    pretend to be a tiny sovereign node if shape is part of identity (requires
    proof-of-architecture — out of scope, note only).
- **Why "limit the WHOLE system" is WRONG (the trap):**
  1. **Soft centralization.** "The perfect shape" implies a canonical spec someone
     *declares* — a point of authority, antithetical to the mesh.
  2. **Contradicts the core thesis.** "Functions ARE the knowledge; the router
     just needs the small routing grammar." Different router shapes should ALL
     route to the same functions. Shape-lock says "your router must look like
     mine" = opposite of sovereignty/heterogeneity.
  3. **Freezes the capacity ladder.** Shape-lock forbids a node wanting a bigger
     model for chained/planning. And it's *premature* — the capacity A/B
     (wiki/findings/2026-07-14-capacity-data-volume-hypothesis.md) is still
     HUNTING the shape. Locking today = locking before we know.
  4. **Shrinks discovery.** The open mesh's value is "see what's new out there."
     Shape-gating the *entire* system kills that.
- **The correct, narrower design (adopt this instead):**
  Shape only matters for ONE thing: **learning transfer, NOT peering.**
  - **Peering/forwarding: ANY shape.** A 2.3M and 10.9M node BOTH route
    `compute` and return the same `TOOL compute {...}`. Sovereignty + discovery
    preserved.
  - **Learning (vampire move): shape-gated.** Synthesize cards only from peers
    whose shape can represent the capability (or require same-shape consensus
    *within a circle*).
  - **"Canonical shape" = per-CIRCLE policy, not a global protocol rule.** Your
    trusted circle may agree "we all run shape X" — local consensus, not a
    mandate. The open mesh stays shape-agnostic.
  - **Net:** lock LEARNING, not the NETWORK. Peering is free; curriculum-transfer
    is shape-gated; canonical shape is a circle-level choice, never a protocol-wide
    decree.

### 10. Quorum (consensus, hardened)
James (2026-07-14): a node that gets conflicting Q→TOOL mappings from peers
needs a QUORUM before it learns anything. The naive "≥2 circle peers agree" gate
is exploitable (see 8a: Sybil-in-circle fakes 2-of-N agreement). Hardened rule:
- **Quorum floor = K INDEPENDENT circle peers** (K > expected Sybil count in a
  circle; prefer ODD so ties are breakable). Not headcount — independence-checked
  (provenance from 8a: a cluster that all learned `fn` from the same upstream is
  ONE voice, not K).
- **Agreement threshold = supermajority of those K** (e.g. ≥2/3), not simple
  majority.
- **If quorum not met OR no supermajority → DON'T learn that capability from
  peers** (fall back to local-only, or human-gated if unverifiable).
- **Gap (NOT solved by quorum):** persistent GENUINE split — 2 peers reliably,
  validly disagree (not error, different valid mappings). Quorum only finds a
  majority; a 50/50 split resolves nothing. Needs per-capability forking/
  versioning (open question, not quorum's job).
- **Open sub-threads (parked, weight later — risk of creep):** (1) how a node
  *discovers* the quorum exists (needs a capability-index query for "I have K
  independent peers on `fn`"); (2) K scaling with circle size (fixed K starves
  small homelab meshes; too-small K is Sybil-vulnerable).

> **PAUSED 2026-07-14:** James asked to STOP adding threads here — too many
> thoughts in flight, creep/bloat risk. Quorum core rule captured; sub-threads
> deliberately parked. Revisit only after the capacity A/B lands and the shape is
> known. This doc is THEORY ONLY; do not promote any of it to plan/roadmap yet.

## Open questions (purely theoretical)
- **Merit-based invite automation**: how does a mesh peer *earn* the circle invite
  without you manually deciding? Threshold on direct local-rep? Auto-invite on
  sustained `score ≥ 0.90, n ≥ 20` for ≥K functions? Or keep it human-gated?
- **Capability collision**: two circle peers both claim `compute` but disagree →
  consensus resolves it, but a *persistent* split (genuine disagreement, not error)
  needs a fork/versioning notion per capability.
- **Privacy**: forwarding a request leaks intent to a peer. Blind the intent? Route
  a hashed/embedded query? Probably acceptable for a homelab mesh (topic leakage
  is the only cost), but worth noting.
- **Gossip overhead**: signed assertions across a growing circle — bounded by
  circle size (intentionally small), so fine. Mesh peers excluded by design.
- **Byzantine weights**: a peer *mostly* right but *sometimes* poisons one fn →
  per-capability rep + consensus catches it; the learning gate's `n ≥ 20` + `≥2
  circle agree` is the real defense.

## Relation to other docs
- Builds on the **trust ladder** (wiki/plans/phase7-dream-cycle.md): local
  unapproved/approved/canon → network reputation (per-capability, tiered).
- Builds on **promote.py** (scripts/promote.py): the per-node retrain-with-rollback
  loop is exactly what lets a node *learn* a peer's capability locally (the
  vampire move). Honest eval gate is the local analog of the circle consensus.
- Builds on **capacity-bump REGRESSED** (wiki/findings/2026-07-14-capacity-bump-
  regressed.md): a node learning a new fn from peers still needs *enough training
  signal* — consensus-as-curriculum is the supply.
- NOT the same as the dream cycle — that's single-node self-training; this is
  multi-node capability sharing. Dream cycle is a prerequisite concept.

## Decision
Theory only. No code, no plan, no timeline. Logged for the shape of where
"functions are knowledge" *wants* to go when one router isn't enough — a quiet
web that watches the whole world but only *absorbs* from the handful it has
vetted.
