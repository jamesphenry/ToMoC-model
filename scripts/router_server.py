#!/usr/bin/env python3
"""router_server — the live ToMoC loop for the from-scratch function router.

q -> model emits TOOL <name> <json> -> executors.execute() -> result
-> (here we print it; a fuller loop would feed the result back). The model
DECIDES which function; executors DO it.

Two modes:
  --chat            interactive loop (type a request, watch the routing + result)
  --ask "..."       single request, print the routed call + execution result

Sovereign: write handlers (remind_me) are GATED — they return a proposed_write
and never mutate disk. The human approves on the CLI.

Usage:
  python scripts/router_server.py --model models/scratch/1 --chat
  python scripts/router_server.py --model models/scratch/1 --ask "what is 48 - 5 + 20"
"""
import argparse
import json
import os
import sys
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from tomac_common import build_prompt, parse_call
from model_scratch import RouterModel, CharTokenizer
from functions import executors
from functions.registry import names as _reg_names
_REG_NAMES = set(_reg_names())

DEFAULT_MODEL = os.path.join(ROOT, "models", "scratch", "1")
MAX_NEW = 160


def load_model(model_path, device):
    tok = CharTokenizer.load(os.path.join(model_path, "tokenizer.json"))
    model = RouterModel.load(model_path, device=device).to(device)
    model.eval()
    return tok, model


@torch.no_grad()
def route_once(tok, model, q, device, max_new=MAX_NEW, rep_penalty=1.4):
    prompt = build_prompt(q)
    ids = torch.tensor([tok.encode(prompt)], dtype=torch.long, device=device)
    gen = model.generate(ids, max_new=max_new, temperature=0.0,
                         eos_id=tok.eos_id, rep_penalty=rep_penalty)
    raw = tok.decode(gen[0][len(ids[0]):].tolist())
    name, args, wf, _ = parse_call(raw, known_names=_REG_NAMES)
    if name is None:
        return {"request": q, "routed": None, "raw": raw.strip(),
                "result": "(model answered directly — no tool)"}
    exec_result = executors.execute(name, args)
    return {"request": q, "routed": name, "args": args,
            "well_formed": wf, "raw": raw.strip(), "exec": exec_result}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--ask", default=None)
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--rep-penalty", type=float, default=1.4,
                    help="repetition penalty for live decode (anti-loop; must match eval). Default 1.4.")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok, model = load_model(args.model, device)

    if args.ask:
        r = route_once(tok, model, args.ask, device, rep_penalty=args.rep_penalty)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    if args.chat:
        print("tomac router (from-scratch) — type a request (Ctrl-D to quit)")
        print("write commands: /approve  (commit last proposed reminder)")
        while True:
            try:
                q = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye")
                break
            if not q:
                continue
            if q == "/approve":
                print("(no pending proposal to approve)")
                continue
            r = route_once(tok, model, q, device, rep_penalty=args.rep_penalty)
            print(f"  route : {r.get('routed')}  args={r.get('args')}")
            print(f"  exec  : {r.get('exec')}")
            if r.get('routed') is None:
                print(f"  answer: {r.get('raw')}")


if __name__ == "__main__":
    main()
