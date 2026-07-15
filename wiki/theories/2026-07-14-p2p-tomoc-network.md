# Theory: P2P ToMoC network — a mesh of tiny sovereign routers

**Status: THEORY ONLY.** Not on the roadmap. Not a plan. Speculative design
thinking, logged because it's the natural escalation of the core thesis
("functions ARE the knowledge"). James's words: *"very very villain coded."*

Evolved from a session spitball (2026-07-14): a **two-tier topology** — an
invite-only *trusted circle* (gossip + learn) sitting on top of an open,
discoverable *mesh* (forward-only, merit-based invite path). Trust is
permissioned; discovery is open.

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
