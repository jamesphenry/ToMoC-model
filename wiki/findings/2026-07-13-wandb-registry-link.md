# 2026-07-13 — wandb-registry-link (FINAL: two collections)

## User requirement
"we need 2 collections models and datasets" — model checkpoints go to a MODELS
collection, datasets go to a DATASETS collection, both in the org registry.

## ROOT CAUSE of earlier failures (probed)
Self-hosted server team topology: registries are org-owned (`entity=server`),
training runs run as `entity=cravingpine`. The built-in `wandb-registry-model`
enforces team isolation -> doc's `wandb-registry-model/<coll>` pattern is REJECTED
("linking is only allowed within the same team"). The custom collections we CREATE
via `api.create_registry` link fine from cravingpine runs. So we use custom
collections, not the built-in `model` registry.

## FINAL DESIGN (wandb_tracker.py)
- `create_registry()` (no arg): creates BOTH collections if missing:
    - models   -> $TOMAC_REGISTRY_MODEL_COLL (default `tomac-models`)
    - datasets -> $TOMAC_REGISTRY_DATA_COLL  (default `tomac-datasets`)
- `link_artifact(art, kind)`: routes by kind:
    - model    -> `wandb-registry-{TOMAC_REGISTRY_MODEL_COLL}`
    - dataset  -> `wandb-registry-{TOMAC_REGISTRY_DATA_COLL}`
- `log_artifact(..., type=...)`  -> links via kind=type (model default).
- `log_dataset(...)`              -> links via kind="dataset".
- Both no-op gracefully if unset/unsupported; training never breaks.

## VERIFIED (live, 7/7)
- `verify-model:v0`  -> wandb-registry-tomac-models:v1   [OK]
- `verify-data:v0`   -> wandb-registry-tomac-datasets:v1 [OK]

## 60-ep baseline already linked (prior step)
- `baseline-60ep:v0` -> wandb-registry-tomac-models:v0   [OK]
- `cards:v1`          -> wandb-registry-tomac-datasets:v0     [OK]

## Launch env (for future runs)
export TOMAC_REGISTRY_MODEL_COLL=tomac-models
export TOMAC_REGISTRY_DATA_COLL=tomac-datasets
(WANDB_ENTITY=cravingpine, WANDB_API_URL=..., WANDB_PROJECT=tomac)

## Tags
wandb, registry, model-governance, two-collections, team-mismatch, root-cause
