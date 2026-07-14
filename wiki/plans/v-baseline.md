# v-baseline — the sovereign knowledge-agent router

> Decided with James, 2026-07-13. This is the **control group** for every later
> experiment. KISS on purpose: boring baseline first, then isolate ONE variable
> per run (the learning-loop rule).

## Thesis (extended)
The tiny model is a **fast, dumb librarian** — it owns *decisions*, not knowledge.
- Functions ARE knowledge (registry.json) — unchanged founding thesis.
- The Obsidian vault IS long-term memory. The model files notes; humans canonize.
- No external LLM at inference. Sovereign: SearXNG + local vault only.

The model knows exactly three moves:
1. **Look it up?** → `web_search` (SearXNG, self-hosted).
2. **Write it down?** → `wiki_write` (proposes a draft note).
3. **Answer from the shelf?** → `wiki_read` (or `answer_direct`).

## Architecture (the control)
- **Decoder-only, char-level, FROM SCRATCH** (the v1–3 line). NOT the SAN
  encoder-decoder — that is a *later, named* experiment, kept out of baseline.
- **~1.5M params**: `d_model=192, n_layers=4, n_heads=6`. "As small as possible"
  is itself the experiment: floor-hunt the smallest model that still routes.
- Contract unchanged: `tomac_common.build_prompt` / `parse_call` (byte-identical
  cue + tolerant JSON parser). Never fork.

## Tools (registry.json) — exactly 6, no specialists
| tool           | job                                    |
|----------------|----------------------------------------|
| `web_search`   | SearXNG lookup (port smol's recipe)    |
| `wiki_read`    | read a vault note                      |
| `wiki_write`   | propose a DRAFT note (gated)           |
| `compute`      | AST-scanned sandboxed arithmetic       |
| `get_time`     | clock                                  |
| `answer_direct`| no tool — reply from the model         |

## The approval flag = the whole trust model
Obsidian YAML frontmatter (native, greppable, human-editable):
```yaml
---
status: draft          # draft | canon   (model writes draft, NEVER canon)
source: ai             # ai | human
verified_by: null      # set to a human name on approval
confidence: 0.6
retrieved: 2026-07-13
sources: [https://...]  # SearXNG URLs used
---
```
Lifecycle:
- Model `wiki_write` → always `status: draft, source: ai`. It can NEVER emit canon.
- Model `wiki_read` on a draft → MUST prepend a small disclaimer, e.g.
  "⚠ Using unverified note `X` (draft, ai-generated) — you may want to verify."
- Human approves → CLI flips `status: canon`, sets `verified_by` (mirrors the
  existing `/approve` gate for reminders — same gated-write pattern in executors.py).
- When both a canon and a draft exist for a fact, prefer canon.

This is the anti-self-poisoning guardrail (BUGS lesson): the model builds on its
own drafts (useful immediately) but can never launder a draft into canon alone.

## Specialists / experts — creep guardrail
**Start at ZERO specialists.** One router, N tools. Let the data promote, not vibes.
A mode earns specialist status ONLY when all three hold:
1. it needs a **different output grammar** than `TOOL <name> {json}` (e.g. summarize
   emits prose, chat emits conversation — not a call), AND
2. the unified router's accuracy on that class is **below ~0.8**, AND
3. it **recurs** often enough to matter.

Chat / summarization are good *eventual* candidates (different grammar) but must be
proven against the baseline first. This keeps organic growth without scope creep.

## Where it lives (harness)
The model is a **local routing brain** a harness (hermes / opencode / pi style)
calls: harness → request → model returns a tool call or a direct answer → harness
executes (SearXNG, vault) and owns the human-approval CLI. Clean seam; model stays tiny.

## Success metric (unchanged)
Existing eval: route_acc / well_formed / per-fn / over+under_call. Every pass logs
walltime + GPU watts → cost (metrics.py). W&B mirrors runs when the self-hosted
container is up.

## Parked (named future experiments — NOT baseline)
- **SAN encoder-decoder** (needle recipe port): tools-in-context via cross-attn.
- **Hybrid router**: core tools baked into weights + optional cross-attn for new
  tools added at runtime (zero-retrain extensibility).
- **Specialist modes**: promoted from data per the guardrail above.

## Open / next
- Wire W&B integration against James's self-hosted container (BLOCKED: setup).
- Then: add web_search/wiki_read/wiki_write to registry.json (port smol SearXNG +
  gated wiki_write), regenerate cards, train ~1.5M baseline, eval, discuss.
