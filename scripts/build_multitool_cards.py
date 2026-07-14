#!/usr/bin/env python3
"""build_multitool_cards — synthesize DISAMBIGUATION router cards (needle-style).

Change vs v1 (which REGRESSED get_time via catastrophic interference): every
card lists the FULL tool list (all registry fns), not a 2-3 item subset. This
matches needle's recipe: "tools listed" becomes a CONSTANT, so it stops being a
spurious "this request is ambiguous" signal. The model must attend to the
REQUEST to pick the gold, instead of learning "get_time is rarely the answer
when tools are shown."

Gold is drawn with an EVEN distribution across tools so no class is starved.

Grammar UNCHANGED: still one TOOL line. The prompt just gains an
"Available tools:" line rendered by tomac_common.build_prompt(tools=...).

Usage:
  python scripts/build_multitool_cards.py --out data/raw/multitool.jsonl --n 400
  cat data/raw/cards_train.jsonl data/raw/multitool.jsonl > data/raw/cards_train_mt.jsonl
"""
import argparse
import json
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from tomac_common import target_for
from functions.registry import functions


def _gold_pair(name, rng):
    if name == "compute":
        a, b = rng.randint(2, 99), rng.randint(2, 40)
        sym = rng.choice(["+", "-", "*", "/"])
        return {"expression": f"{a} {sym} {b}"}, f"What is {a} {sym} {b}?"
    if name == "unit_convert":
        pairs = [("mi", "km"), ("km", "mi"), ("kg", "lb"), ("lb", "kg"), ("h", "min")]
        fu, tu = rng.choice(pairs)
        v = rng.choice([1, 2, 5, 10, 25, 100])
        return {"value": v, "from": fu, "to": tu}, f"How many {tu} is {v} {fu}?"
    if name == "get_time":
        if rng.random() < 0.5:
            return {}, "What time is it?"
        tz = rng.choice(["UTC", "Tokyo", "London", "New York"])
        return {"tz": tz}, f"What time is it in {tz}?"
    if name == "wiki_read":
        t = rng.choice(["the DNS setup", "the GPU server specs", "docker compose conventions", "ToMoC"])
        return {"query": t}, f"What do my notes say about {t}?"
    if name == "wiki_write":
        t = rng.choice(["backup plan", "router config", "server inventory"])
        return {"title": t, "content": "draft note body"}, f"Save a note about {t}"
    if name == "web_search":
        q = rng.choice(["latest NVIDIA GPU benchmarks", "Python 3.13 release notes",
                        "Kubernetes vs Nomad", "best homelab router 2026"])
        a = {"query": q}
        if rng.random() < 0.4:
            a["limit"] = rng.choice([3, 5, 8])
        return a, f"Search the web for {q}"
    if name == "remind_me":
        t = rng.choice(["back up the NAS", "renew the domain", "restart the router"])
        if rng.random() < 0.5:
            return {"text": t}, f"Remind me to {t}"
        w = rng.choice(["tomorrow", "Friday", "in an hour"])
        return {"text": t, "when": w}, f"Remind me to {t} at {w}"
    return {}, "What's your favorite color?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "raw", "multitool.jsonl"))
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    all_tools = [f["name"] for f in functions()]   # FULL list, constant per card
    # even gold distribution: round-robin so every tool is gold ~equal times
    gold_cycle = all_tools * ((args.n // len(all_tools)) + 1)
    rng.shuffle(gold_cycle)
    gold_seq = gold_cycle[:args.n]

    cards = []
    for gold in gold_seq:
        args_gold, req = _gold_pair(gold, rng)
        target = target_for(gold, args_gold if gold != "answer_direct" else {})
        cards.append({
            "q": req,
            "name": gold,
            "args": (args_gold if gold != "answer_direct" else {}),
            "tools": list(all_tools),   # FULL list every time (needle-style)
            "target": target,
        })

    rng.shuffle(cards)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for c in cards:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    cnt = Counter(c["name"] for c in cards)
    print(f"wrote {len(cards)} multi-tool cards (FULL list, needle-style) -> {args.out}")
    for n, c in cnt.most_common():
        print(f"    gold {n:14s} {c}  (presented as distractor {len(cards)-c}/{len(cards)} times)")


if __name__ == "__main__":
    main()
