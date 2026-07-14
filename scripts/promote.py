#!/usr/bin/env python3
"""promote — the self-training DECIDER (rollback-safe model promotion).

The heart of autonomous retrain: given an INCUMBENT and a CANDIDATE checkpoint,
score BOTH on a sealed val split at the HONEST decode setting (rep_penalty=1.0,
live-faithful — NOT the inflated eval default of 1.4), and keep whichever wins.
The loser is never deleted; the incumbent is never overwritten in place.

This is what makes "let it retrain every night" safe:
  - blast radius = one .pt file (a bad run misroutes, nothing else breaks)
  - objective gate (route_accuracy on sealed val) — no human judgment call
  - rollback is trivial: just point --current at the incumbent again

It is intentionally tiny. The "self" lives in the HARNESS that calls this on a
cron, not in the model. See wiki/plans/phase7-dream-cycle.md.

Usage:
  # dry-run: report the decision, don't move anything
  python scripts/promote.py --current models/scratch/A --candidate models/scratch/B

  # promote: on win, copy winning .pt to --promote PATH (e.g. models/scratch/current.pt)
  python scripts/promote.py --current A --candidate B --promote models/scratch/current.pt
"""
import argparse
import os
import shutil
import sys
import time

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from eval_router import load_model, generate_batch, load_cards
from tomac_common import build_prompt, parse_call
from functions.registry import names as _reg_names
from metrics import Metrics

_REG_NAMES = set(_reg_names())
DEFAULT_DATA = os.path.join(ROOT, "data", "raw", "cards.jsonl")


@torch.no_grad()
def score(model_path, data, device, rep_penalty, limit=0):
    """Return (route_accuracy, well_formed, n, per_fn) for one checkpoint.

    Reuses eval_router's pipeline so the gate is byte-identical to harness eval."""
    tok, model = load_model(model_path, device)
    eos_id = tok.eos_id
    cards = load_cards(data)
    if limit:
        cards = cards[:limit]
    n = len(cards)
    correct = 0
    well_formed = 0
    per_fn = {}
    prompts = [build_prompt(c["q"], c.get("tools")) for c in cards]
    raws = generate_batch(tok, model, prompts, 160, device, eos_id,
                          bsz=32, rep_penalty=rep_penalty)
    for c, raw in zip(cards, raws):
        name, _, wf, _ = parse_call(raw or "", known_names=set(_REG_NAMES))
        gold = c["name"]
        gold_no_tool = (c.get("target") == c["q"]) or (gold == "answer_direct")
        pred_no_tool = name is None
        if (name == gold) or (gold_no_tool and pred_no_tool):
            correct += 1
        if wf or (pred_no_tool and gold_no_tool):
            well_formed += 1
        per_fn.setdefault(gold, [0, 0])
        per_fn[gold][1] += 1
        if (name == gold) or (gold_no_tool and pred_no_tool):
            per_fn[gold][0] += 1
    del model, tok
    torch.cuda.empty_cache() if device == "cuda" else None
    return correct / n, well_formed / n, n, per_fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", required=True, help="incumbent checkpoint dir")
    ap.add_argument("--candidate", required=True, help="candidate checkpoint dir")
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--rep-penalty", type=float, default=1.0,
                    help="HONEST gate (live-faithful). 1.4 inflates scores (BUG-007).")
    ap.add_argument("--promote", default=None,
                    help="if set, on win copy the winner's model.pt here")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    t0 = time.time()
    print(f"[promote] incumbent  = {args.current}")
    print(f"[promote] candidate  = {args.candidate}")
    print(f"[promote] device={device} rep_penalty={args.rep_penalty} (honest gate)")

    ca, cw, n, cp = score(args.current, args.data, device, args.rep_penalty, args.limit)
    ba, bw, _, bp = score(args.candidate, args.data, device, args.rep_penalty, args.limit)

    winner = args.candidate if ba >= ca else args.current
    promoted = (winner == args.candidate)

    # log both to metrics store (and W&B if env wired) as a promote decision
    m = Metrics()
    pid = m.new_pass(mode="promote", base_model="(scratch)", num_cards=n,
                     walltime_s=round(time.time() - t0, 1), status="decided")
    m.log_metric(pid, "incumbent.route_accuracy", round(ca, 4))
    m.log_metric(pid, "candidate.route_accuracy", round(ba, 4))
    m.log_metric(pid, "won", 1 if promoted else 0)
    m.log_meta(pid, "incumbent", os.path.basename(args.current))
    m.log_meta(pid, "candidate", os.path.basename(args.candidate))
    m.close()

    print(f"\n=== PROMOTE DECISION ===")
    print(f"  incumbent  route_acc={ca:.4f}  well_formed={cw:.4f}")
    print(f"  candidate  route_acc={ba:.4f}  well_formed={bw:.4f}")
    print(f"  winner     = {os.path.basename(winner)}  "
          f"({'PROMOTE candidate' if promoted else 'KEEP incumbent (rollback)'})")
    if args.promote and promoted:
        src = os.path.join(args.candidate, "model.pt")
        os.makedirs(os.path.dirname(args.promote), exist_ok=True)
        shutil.copy(src, args.promote)
        print(f"  [applied] copied {src} -> {args.promote}")
    elif args.promote and not promoted:
        print(f"  [rollback] incumbent kept; nothing copied to {args.promote}")
    else:
        print("  [dry-run] no --promote given; nothing written.")


if __name__ == "__main__":
    main()
