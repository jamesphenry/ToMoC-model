## BUG-002 (anticipated, designed out) — drifted cue kills habit transfer
- **Symptom (in smol):** a training/eval cue that isn't byte-identical silently
  breaks the tool-call habit; eval shows the model "forgot" how to call.
- **Root cause:** the priming string lived in two places and drifted.
- **Fix in tomac:** the cue + prompt builder + call parser live in ONE module
  (`scripts/tomac_common.py`). Train (`train_router.py`) and eval
  (`eval_router.py`) both import it. There is exactly one source of truth.
- **Guardrail:** never edit `CUE` without retraining; never fork `parse_call`.
