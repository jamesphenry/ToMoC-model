# 2026-07-13 — weave-blocked

## Ask
User wanted to use W&B **Weave** (purpose-built eval/tracing framework) for evals,
citing https://docs.wandb.ai/weave/tutorial-eval. Weave gives versioned
`weave.Model` + `weave.Dataset` + scorers + per-example comparison UI — i.e.
"which examples regressed vs last eval," queryable.

## What we found
- `pip install weave` worked (v0.53.1).
- `weave.init("tomac/weave-probe")` reached the server but was **rejected**:
  `RuntimeError('Weave is not available on the server. Please contact support.')`
- So: the self-hosted wandb container (wandb 0.28.0 @ 192.168.0.6:8081) does NOT
  have the Weave subsystem enabled. Server-side limitation, not fixable in our code.

## Decision
- **Weave = blocked** for now. Revisit only if Weave is enabled on the container.
- We already track evals adequately without it: `eval_router` logs route_accuracy,
  well_formed, over/under_call, per-fn accuracy, AND the full per-item JSONL as a
  versioned W&B artifact (run `pass-9`). That's the auditable trail.
- Action item (later): ask whether to enable Weave on the self-hosted server, or
  accept run-based eval logging as sufficient.

## Tags
wandb, weave, blocked, eval-logging
