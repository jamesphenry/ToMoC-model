---
title: "FUTURE THREAD — tomac p2p on any device (sovereignty endgame)"
date: 2026-07-15
status: future-thread
tags: [vision, p2p, edge, sovereign]
---

## The idea (user-stated, 2026-07-15)

> "another goal for future if this works out tomac p2p on any device!!!!"

Interpretation: if the 1-bit/ternary router works (functions-are-knowledge at
trivial precision), the natural extension is a **peer-to-peer mesh of sovereign
routers** where each node is a tiny device (phone, SBC, microcontroller) running
its own from-scratch router + local function executors. No central server, no
cloud — requests route to *whichever peer owns the function* (or a peer's vault/
compute), over a homelab peer network.

## Why it connects to the 1-bit side-track
A ternary router is the only way this is realistic on "any device" — a 2.3M FP
model is already small, but a 1.58-bit router is small enough to live in firmware
/ no-multiply hardware. The p2p vision is the *motivation* for the 1-bit
experiment, not a separate cost.

## Not actioned yet
This is a recorded future thread. No code, no design doc yet. Prerequisites:
- 1-bit router proves it can route+fill args at acceptable fidelity (pass-63
  arg_accuracy 0.5366 is the bar to beat / approximate).
- A function-executor transport that is peer-to-peer (not the current
  single-node router_server.py loop).
- Trust ladder (vault flag system) must exist before peers share memory.

## Next (when revisited)
- Sketch the peer protocol: how a request is advertised, how a peer claims a
  function, how results return. Keep it homelab-only (no relay servers).
- Decide whether "any device" means a real microcontroller port (C/zig) or just
  SBC-class (python/ONNX). The 1-bit matmul is the gating factor.
