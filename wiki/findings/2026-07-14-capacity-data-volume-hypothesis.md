# Finding (hypothesis): capacity needs DATA VOLUME, not just epochs

**Date:** 2026-07-14
**Type:** PREDICTION / A-B TEST DESIGN (not yet run). Logged because James stated
the theory directly and wants it tested.

## The theory (James's words, paraphrased)
"The model is bigger, so we need more training/data to teach it — we're training
a big brain on a tiny brain's lesson plan." Baseline-big (10.9M, 4.7× the 2.3M
8fn) was trained on the SAME 3936 cards / 100ep and REGRESSED (honest
route_acc 0.25, under_call 0.75 — collapsed to answer_direct). Prediction: the
failure is **data VOLUME**, not just epoch count. A bigger model has more
hypothesis space; the same tiny curriculum under-fills it and it collapses to the
no-tool prior.

## Why this is the right prediction
- Capacity ≠ intelligence; it's *potential to fit*. A 2.3M model is capacity-bound
  on 3936 cards (every epoch buys generalization). A 10.9M model on the same cards
  is data/epoch-bound — extra params sit unconstrained and the optimizer takes the
  lazy path (always answer_direct, free ~25% accuracy).
- More epochs on the SAME cards risks *memorization without generalization*
  (learns the 3936 exact prompts, not the tool-emission HABIT for novel prompts).
  So pure epoch-scaling may not fix it; DIVERSITY (more cards) likely matters more.

## A/B test design (to falsify the prediction)
- **A — more EPOCHS, same data:** baseline-big @ 300ep, same 3936 cards.
  Tests "is it just undertraining?"
- **B — more DATA volume, same epochs:** baseline-big @ 100ep, AUGMENTED cards
  (≈2–3× synth diversity: more phrasings / edge cases / maybe more functions).
  Tests "is it a data-VOLUME problem?"
- **Control:** 8fn incumbent (2.3M, 100ep, 3936 cards) — the current sovereign.
- **Gate:** honest eval at **rep_penalty=1.0** (NOT the inflated 1.4). promote.py
  decides promote/rollback vs 8fn.
- **Prediction:** B succeeds (route_acc recovers toward ~0.9+), A does NOT (or
  memorizes without generalizing). If B wins → confirms data-volume theory; the
  capacity bump was a *curriculum* problem, not an architecture problem.

## Connection to P2P theory
The bigger-brain-needs-more-curriculum problem is the SAME problem the P2P mesh
solves: **consensus-as-curriculum is the supply of training signal a bigger brain
needs.** A single node's 3936 cards can't fill a 10.9M model, but a mesh of nodes
each contributing observed Q→TOOL mappings could. (See
wiki/theories/2026-07-14-p2p-tomoc-network.md — James's stated END GOAL.)

## Status
- [ ] A not run
- [ ] B not run
- [ ] verdict pending
- Baseline-big (current, 100ep/3936) = REGRESSION (see
  2026-07-14-capacity-bump-regressed.md). This hypothesis explains WHY.

## Reproducibility (when run)
- A: `python scripts/train_router.py --out models/scratch/baseline-big-300ep
  --epochs 300 --d-model 384 --n-layers 6 --n-heads 6 --d-ff 1536`
- B: augment `build_cards.py` output (or add an --augment flag), retrain 100ep.
- Eval both: `python scripts/eval_router.py --model <out> --data <cards>
  --rep-penalty 1.0`
