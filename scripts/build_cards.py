#!/usr/bin/env python3
"""build_cards — synthesize router training data from the function registry.

The registry (functions/registry.json) IS the knowledge. Every function's
``examples`` become gold (request -> TOOL call) pairs. We also synthesize
negative ("answer directly, no tool") cards from the ``no_tool`` functions and
generic chit-chat so the router learns WHEN NOT to call a tool.

Output: data/raw/cards.jsonl  (one JSON per line)

Card schema:
  { "q": request, "name": gold_function, "args": gold_args_or_{},
    "target": "TOOL name {...}" (training target string) }

The training target uses tomac_common.target_for() so it matches the eval
parser byte-for-byte.

Usage:
  python scripts/build_cards.py
  python scripts/build_cards.py --multiply 4    # repeat each example 4x (more signal)
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from tomac_common import build_prompt, target_for
from functions.registry import functions, names

RAW = os.path.join(ROOT, "data", "raw", "cards.jsonl")

# Generic no-tool chit-chat to broaden the "don't call" class beyond registry.
_CHITCHAT = [
    "Who are you?", "What's your name?", "Hi there!", "Thanks, that helps!",
    "Good morning", "Tell me a joke", "How are you today?",
    "Explain what a function router is in one sentence",
    "Why is the sky blue?", "What is the capital of France?",
    "What's your favorite color?", "Can you help me think through a problem?",
    "That makes sense, thank you.", "lol nice",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RAW)
    ap.add_argument("--multiply", type=int, default=3,
                    help="repeat each gold example this many times (shuffled)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    fns = functions()
    if not fns:
        raise SystemExit("no functions in registry — nothing to train on")

    cards = []
    for f in fns:
        name = f["name"]
        exs = f.get("examples", [])
        if f.get("no_tool"):
            # negative class: answer directly. emit a plain target (no TOOL call)
            for e in exs:
                cards.append({"q": e["request"], "name": name, "args": {},
                              "target": e["request"]})
        else:
            for e in exs:
                a = e.get("args", {})
                cards.append({"q": e["request"], "name": name, "args": a,
                              "target": target_for(name, a)})

    # augment with generic chit-chat (no-tool)
    for c in _CHITCHAT:
        cards.append({"q": c, "name": "answer_direct", "args": {},
                      "target": c})

    # multiply
    if args.multiply > 1:
        base = list(cards)
        for _ in range(args.multiply - 1):
            cards.extend(base)

    random.shuffle(cards)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for c in cards:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    # summary
    from collections import Counter
    cnt = Counter(c["name"] for c in cards)
    print(f"wrote {len(cards)} cards -> {args.out}")
    for n, c in cnt.most_common():
        print(f"  {n:14s} {c}")


if __name__ == "__main__":
    main()
