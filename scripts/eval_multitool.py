#!/usr/bin/env python3
"""eval_multitool — score disambiguation quality on multi-tool cards.

For each multi-tool card the prompt lists several AVAILABLE tools; the gold is
a SINGLE tool that MUST be in that presented set. We score:
  gold_hit   : predicted == gold (picked the right one)
  in_set     : predicted in the presented tools (valid choice, partial credit)
  out_of_set : predicted NOT in presented set (a genuine disambiguation error)
  over_call  : predicted a tool when gold = answer_direct (misroute)
  under_call : predicted none when gold = a tool
Reuses eval_router.generate_batch so decode matches training exactly.
"""
import json
import os
import sys
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from tomac_common import build_prompt, parse_call
from eval_router import load_model, generate_batch
from functions.registry import names as _reg_names
from metrics import Metrics

_REG = set(_reg_names())


def main():
    model_path = sys.argv[1] if len(sys.argv) > 1 else "models/scratch/baseline-100ep-mt"
    data = sys.argv[2] if len(sys.argv) > 2 else "data/raw/multitool.jsonl"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok, model = load_model(model_path, device)

    cards = [json.loads(l) for l in open(data, encoding="utf-8") if json.loads(l).get("tools")]
    prompts = [build_prompt(c["q"], c["tools"]) for c in cards]
    raws = generate_batch(tok, model, prompts, 160, device, tok.eos_id, bsz=32)

    gold_hit = in_set = out_of_set = over_call = under_call = 0
    per_fn = {}
    for c, raw in zip(cards, raws):
        pred, _, _, _ = parse_call(raw, known_names=_REG)
        gold = c["name"]
        presented = set(c["tools"])
        gh = (pred == gold)
        is_in = pred in presented
        gold_hit += gh
        in_set += is_in
        out_of_set += (pred is not None and not is_in)
        over_call += (gold == "answer_direct" and pred is not None)
        under_call += (gold != "answer_direct" and pred is None)
        per_fn.setdefault(gold, [0, 0])
        per_fn[gold][0] += gh
        per_fn[gold][1] += 1

    n = len(cards)
    print(f"=== multi-tool disambiguation eval: {model_path} ({n} cards) ===")
    print(f"  gold_hit    : {gold_hit/n:.4f}  ({gold_hit}/{n})")
    print(f"  in_set      : {in_set/n:.4f}  ({in_set}/{n})  (valid choice, partial)")
    print(f"  out_of_set  : {out_of_set/n:.4f}  ({out_of_set}/{n})  (disambig ERROR)")
    print(f"  over_call   : {over_call/n:.4f}  ({over_call}/{n})")
    print(f"  under_call  : {under_call/n:.4f}  ({under_call}/{n})")
    print("  per-fn gold_hit:")
    for fn, (h, tot) in sorted(per_fn.items()):
        print(f"    {fn:14s} {h/tot:.2f}  ({h}/{tot})")


if __name__ == "__main__":
    main()
