# Plan: Phase 6 — Self-extending Registry

**Goal:** the router proposes functions it *can't* route, so the human only has
to implement the handler — the model grows its own capability surface.

## Steps
1. [ ] Add a `propose_function` routing target: when the model hits a request it
       can't map to a known function, it emits
       `TOOL propose_function {"name":..., "params":[...], "why":...}`.
2. [ ] `router_server.py` collects proposals into `data/function_proposals.jsonl`
       (gated — never auto-implements).
3. [ ] A human reviews the proposal, writes the handler in `executors.py`, and
       adds the registry entry. Next retrain makes it routable.
4. [ ] Measure: % of novel requests that produce a sensible `propose_function`
       (router self-awareness) vs a wrong existing call.

## Why this is the endgame
It closes the loop on "functions ARE its knowledge": the model not only routes
to what it knows, it *identifies gaps* in its toolset — the human supplies the
capability, the model supplies the judgment. Sovereign, auditable, no silent
self-modification.

## Definition of done
- Unknown requests yield `propose_function` calls; accepted proposals become
  routable after one retrain; the model's toolset grew by human-approved steps.
