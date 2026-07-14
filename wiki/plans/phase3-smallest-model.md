# Plan: Phase 3 — Smallest Viable Model

**Goal:** find how small the transformer can get before routing quality
collapses. Directly answers "how small can we make it?" — but since tomac trains
from scratch (no pretrained base), this is an **architecture sweep**, not a base
size sweep.

## Dimensions to sweep
- `d_model`: 128 / 256 / 512
- `n_layers`: 4 / 6 / 8 (keep heads = d_model/32-ish)
- `n_heads`: 4 / 8
- `d_ff`: 4× d_model

## Steps
1. [ ] For each config, `train_router.py --out models/sweep/<tag> --epochs 30`
       with matching dims, then `eval_router.py --model models/sweep/<tag>`.
2. [ ] Plot `route_accuracy` / `well_formed` vs param count in `wiki/journal/` (dated entry).
3. [ ] Find the floor: the smallest config where `route_accuracy` >= 0.95 on the
       card split but degrades sharply below it.
4. [ ] Lock the smallest config that holds quality as the DEFAULT in
       `train_router.py`; document the others as options.
5. [ ] Note char-vs-tokenizer effect on `well_formed` (does char-level hurt JSON
       brace balance at tiny sizes?).

## Definition of done
- A clear answer to "how small": a params-vs-accuracy curve and a locked default.
