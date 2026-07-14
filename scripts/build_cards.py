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
# Kept VARIED across phrasings so the tiny model learns the no-tool BOUNDARY,
# not a keyword. The "Good morning/night", "meaning of life", "what can you do"
# forms below are exactly the ones the 100ep model misrouted to tools — more
# paraphrase variety in those neighborhoods is the B1 fix for over_call.
_CHITCHAT = [
    "Who are you?", "What's your name?", "Hi there!", "Thanks, that helps!",
    "Good morning", "Tell me a joke", "How are you today?",
    "Explain what a function router is in one sentence",
    "Why is the sky blue?", "What is the capital of France?",
    "What's your favorite color?", "Can you help me think through a problem?",
    "That makes sense, thank you.", "lol nice",
    "Good night", "See you tomorrow", "You're awesome", "What can you do?",
    "Tell me something interesting", "How's it going?", "Nice work!",
    "What's the meaning of life?", "Do you like music?", "Hello!",
    # --- B1: expanded no-tool variety (greetings / philosophy / meta / thanks) ---
    "Good evening", "Hey buddy", "Morning!", "G'day",
    "What do you think about the universe?", "Is there an afterlife?",
    "Do you believe in fate?", "Why do we dream?",
    "What's the point of it all?", "How should I live my life?",
    "That really helped, appreciate it", "Cheers for that",
    "You're a clever little router", "I'm impressed",
    "So what are you capable of?", "How do you work?",
    "Can you do anything useful?", "What are your limits?",
    "Just thinking out loud here", "I'm bored, entertain me",
]

# ---- template banks: genuine paraphrase VARIETY (not duplicate strings) ----
# Each yields (request, args) with args correct for target_for(). Randomized so
# the char model sees many surface forms of the same routing decision.

_NUM_WORDS = {2: "two", 3: "three", 5: "five", 7: "seven", 8: "eight",
              9: "nine", 12: "twelve", 15: "fifteen", 20: "twenty"}


def _aug_compute(rng, n):
    out = []
    ops = [("plus", "+"), ("minus", "-"), ("times", "*"), ("divided by", "/")]
    for _ in range(n):
        a, b = rng.randint(2, 99), rng.randint(2, 40)
        word, sym = rng.choice(ops)
        expr = f"{a} {sym} {b}"
        forms = [
            f"What is {a} {word} {b}?",
            f"Calculate {a} {word} {b}",
            f"Compute {a} {sym} {b}",
            f"What's {a} {word} {b}?",
            f"Can you work out {a} {word} {b}?",
        ]
        if sym == "*" and rng.random() < 0.4:
            pct = rng.choice([5, 10, 15, 20, 25, 50])
            base = rng.randint(20, 500)
            out.append((f"What's {pct}% of {base}?",
                        {"expression": f"{base} * {pct/100}"}))
            continue
        out.append((rng.choice(forms), {"expression": expr}))
    return out


def _aug_unit(rng, n):
    out = []
    pairs = [("mi", "km", "miles", "kilometers"), ("km", "mi", "kilometers", "miles"),
             ("kg", "lb", "kilograms", "pounds"), ("lb", "kg", "pounds", "kilograms"),
             ("in", "cm", "inches", "centimeters"), ("ft", "m", "feet", "meters"),
             ("h", "s", "hours", "seconds"), ("h", "min", "hours", "minutes"),
             ("g", "oz", "grams", "ounces"), ("day", "h", "days", "hours")]
    for _ in range(n):
        fu, tu, fw, tw = rng.choice(pairs)
        v = rng.choice([1, 2, 3, 5, 10, 12, 25, 50, 100, 250])
        forms = [
            f"How many {tw} is {v} {fw}?",
            f"Convert {v} {fw} to {tw}",
            f"What is {v} {fw} in {tw}?",
            f"{v} {fw} to {tw}",
            f"How many {tw} in {v} {fw}?",
        ]
        out.append((rng.choice(forms), {"value": v, "from": fu, "to": tu}))
    return out


def _aug_time(rng, n):
    out = []
    zones = [(None, None), ("UTC", "UTC"), ("America/New_York", "New York"),
             ("Europe/London", "London"), ("Asia/Tokyo", "Tokyo"),
             ("America/Los_Angeles", "Los Angeles"), ("Australia/Sydney", "Sydney")]
    for _ in range(n):
        tz, city = rng.choice(zones)
        if tz is None:
            forms = ["What time is it?", "What's the time?", "Tell me the current time",
                     "What is the time right now?", "Give me the time"]
            out.append((rng.choice(forms), {}))
        else:
            forms = [f"Tell me the time in {city}", f"What time is it in {city}?",
                     f"Current time in {city}", f"What's the time in {city} right now?"]
            out.append((rng.choice(forms), {"tz": tz}))
    return out


def _aug_wiki(rng, n):
    out = []
    topics = ["homelab network topology", "API key rotation policy", "ToMoC",
              "backup schedule", "the DNS setup", "my SSH config notes",
              "the GPU server specs", "docker compose conventions",
              "the router firmware version", "my VLAN plan"]
    for _ in range(n):
        t = rng.choice(topics)
        forms = [
            f"What did I note about {t}?",
            f"Look up {t} in my notes",
            f"Remind me what the {t} is",
            f"Find my notes on {t}",
            f"What do my notes say about {t}?",
        ]
        out.append((rng.choice(forms), {"query": t}))
    return out


def _aug_remind(rng, n):
    out = []
    tasks = ["back up the NAS", "renew the domain", "restart the router",
             "update the firewall rules", "pay the server bill",
             "check the UPS battery", "rotate the API keys", "prune old snapshots"]
    whens = ["midnight", "tomorrow", "next week", "March", "Friday",
             "in an hour", "tonight", "on the 1st"]
    for _ in range(n):
        task, when = rng.choice(tasks), rng.choice(whens)
        forms = [
            (f"Remind me to {task} at {when}", {"text": task, "when": when}),
            (f"Remind me to {task}", {"text": task}),
            (f"Note that I need to {task} in {when}", {"text": task, "when": when}),
            (f"Set a reminder to {task} {when}", {"text": task, "when": when}),
        ]
        out.append(rng.choice(forms))
    return out


_AUGMENTERS = {
    "compute": _aug_compute, "unit_convert": _aug_unit, "get_time": _aug_time,
    "wiki_read": _aug_wiki, "remind_me": _aug_remind,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RAW)
    ap.add_argument("--multiply", type=int, default=3,
                    help="repeat each gold example this many times (shuffled)")
    ap.add_argument("--augment", type=int, default=0,
                    help="synth this many EXTRA varied cards per tool function "
                         "(template paraphrases). 0 = off (legacy behavior).")
    ap.add_argument("--compute-boost", type=int, default=0,
                    help="EXTRA compute cards (varied numbers) to strengthen the "
                         "weakest class — the tiny model under-fits digit "
                         "transcription + the TOOL cue on compute requests.")
    ap.add_argument("--get-time-boost", type=int, default=0,
                    help="EXTRA get_time cards (city/timezone variety) to fix the "
                         "2nd-weakest class — also decouples the 'tz' arg token "
                         "from the 'get_time' fn name (was 'timezone').")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--val-frac", type=float, default=0.0,
                    help="held-out fraction (stratified by class) for overfit "
                         "detection; 0 = off (legacy single-file behavior)")
    args = ap.parse_args()
    random.seed(args.seed)
    rng = random.Random(args.seed)

    fns = functions()
    if not fns:
        raise SystemExit("no functions in registry — nothing to train on")

    cards = []
    for f in fns:
        name = f["name"]
        exs = f.get("examples", [])
        if f.get("no_tool"):
            # negative class: answer directly. Emit the SAME grammar as a tool
            # call (TOOL answer_direct {}) so the model learns a distinct,
            # learnable "no external tool needed" signal. Without this the model
            # has no way to say "do nothing" and over-calls a tool on every
            # no-tool card (Run 2b: answer_direct = 0/328).
            for e in exs:
                cards.append({"q": e["request"], "name": name, "args": {},
                              "target": target_for(name, {})})
        else:
            for e in exs:
                a = e.get("args", {})
                cards.append({"q": e["request"], "name": name, "args": a,
                              "target": target_for(name, a)})

    # augment with generic chit-chat (no-tool) — same grammar as a tool call
    for c in _CHITCHAT:
        cards.append({"q": c, "name": "answer_direct", "args": {},
                      "target": target_for("answer_direct", {})})

    # ---- template paraphrase augmentation (genuine variety) ----
    if args.augment > 0:
        for name, augf in _AUGMENTERS.items():
            for q, a in augf(rng, args.augment):
                cards.append({"q": q, "name": name, "args": a,
                              "target": target_for(name, a)})
        # keep the no-tool class balanced with the tool classes
        n_notool = args.augment * len(_AUGMENTERS) // 2
        for _ in range(n_notool):
            c = rng.choice(_CHITCHAT)
            cards.append({"q": c, "name": "answer_direct", "args": {},
                          "target": target_for("answer_direct", {})})

    # compute-specific boost: the weakest class (digit transcription + cue).
    if args.compute_boost > 0:
        for q, a in _aug_compute(rng, args.compute_boost):
            cards.append({"q": q, "name": "compute", "args": a,
                          "target": target_for("compute", a)})

    # get_time-specific boost: 2nd-weakest class (city/timezone variety).
    if args.get_time_boost > 0:
        for q, a in _aug_time(rng, args.get_time_boost):
            cards.append({"q": q, "name": "get_time", "args": a,
                          "target": target_for("get_time", a)})

    # ---- held-out val split (stratified by class) for overfit detection ----
    # Split the UNIQUE card set FIRST; THEN multiply train only. Dedupe by the
    # request TEXT (q) so no val string can appear in train (synthetic cards
    # often repeat the same surface form; naive split leaks text overlaps and
    # hides memorization).
    val = []
    if args.val_frac > 0:
        from collections import defaultdict
        seen = set()
        unique = []
        for c in cards:
            if c["q"] in seen:
                continue  # drop duplicate surface form entirely (goes to neither)
            seen.add(c["q"])
            unique.append(c)
        by_class = defaultdict(list)
        for c in unique:
            by_class[c["name"]].append(c)
        train_unique, val = [], []
        for cls, items in by_class.items():
            rng.shuffle(items)
            k = max(1, round(len(items) * args.val_frac))
            val.extend(items[:k])
            train_unique.extend(items[k:])
        rng.shuffle(train_unique)
        # Seal val by q; keep ALL train cards whose q is in train-unique
        # (preserves multiply/augment volume — do NOT collapse to one card
        # per q, or the train set shrinks and the model underfits). Val
        # leakage stays 0 because val q's are excluded from train_qs.
        train_qs = {c["q"] for c in train_unique}
        cards = [c for c in cards if c["q"] in train_qs]

    # multiply (legacy: duplicates the TRAIN cards only when val-frac set,
    # so val never gets duplicated into train)
    if args.multiply > 1:
        base = list(cards)
        for _ in range(args.multiply - 1):
            cards.extend(base)

    random.shuffle(cards)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    # when val-frac set, also write the sealed val file (train file is args.out)
    if args.val_frac > 0:
        out_dir = os.path.dirname(args.out)
        val_path = os.path.join(out_dir, "cards_val.jsonl")
        with open(val_path, "w", encoding="utf-8") as fh:
            for c in val:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"  [split] {len(cards)} train -> {args.out}")
        print(f"  [split] {len(val)} val   -> {val_path}")

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
