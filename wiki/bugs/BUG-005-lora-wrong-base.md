## BUG-005 (anticipated, designed out) — LoRA loaded on the wrong base
- **Symptom (in smol):** a 360m LoRA loaded on the 135m base shape-mismatched
  and produced garbage (or a silent error).
- **Root cause:** eval hardcoded the base model name regardless of the adapter.
- **Fix in tomac:** `eval_router.py` reads `base_model_name_or_path` from the
  adapter's own `adapter_config.json`. Any-size adapter loads on its correct base.
