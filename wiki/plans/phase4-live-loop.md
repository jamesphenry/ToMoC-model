# Plan: Phase 4 — Live Assistant Loop

**Goal:** run the router as a real homelab service that dispatches actual tools.

## Steps
1. [ ] Harden `router_server.py` into a daemon mode (`--serve`): HTTP or a simple
       stdin/stdout socket. Accepts a request, returns `{routed, args, exec}`.
2. [ ] Wire the gated `remind_me` approval: a `/approve` flow that commits the
       proposed write to `data/reminders.md` (human-in-the-loop, no poison).
3. [ ] Populate `data/vault/` with a few real notes so `wiki_read` has something
       to route to (markdown + frontmatter, Obsidian-friendly).
4. [ ] Add a systemd/launchd unit (or `nohup`) so it runs headless on the box.
5. [ ] Log every live request to `logs/` (routed fn, args, exec verdict) for later
       analysis.

## Definition of done
- A request typed to the service routes to the right function and the executor
  result comes back; gated writes require explicit approval.
