# Plan: Phase 5 — Grow the Function Set

**Goal:** prove the thesis at scale — add real homelab functions with NO model
architecture change, only registry + handler + retrain.

## Candidate functions (all sovereign / offline)
- `weather_now` — query a local/self-hosted weather source (e.g. a homelab
  weewx instance or a cached forecast file). No external API.
- `dns_lookup` / `net_probe` — resolve a host / ping a device on the LAN
  (uses the box's own resolver; no external service).
- `home_assistant` — call a self-hosted HA instance's local REST (no cloud).
- `notes_crud` — create/read/update a vault note (gated writes, like `remind_me`).
- `system_stats` — report box CPU/RAM/disk (reads `/proc`, no deps).

## Steps (per function)
1. [ ] Add the entry to `functions/registry.json` (name, category, params,
       examples). This alone makes it *routable* once retrained.
2. [ ] Implement the handler in `functions/executors.py` (sovereign + sandboxed;
       writes gated).
3. [ ] `build_cards.py` picks it up automatically; retrain.
4. [ ] Held-out eval (Phase 2 harness) confirms the new fn routes correctly and
       doesn't steal traffic from siblings.
5. [ ] Log the new capability in `wiki/JOURNAL.md`.

## Definition of done
- The model routes to >= 8 distinct functions, each with correct args, after a
  single retrain. Capability grew; params didn't.
