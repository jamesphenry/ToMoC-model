#!/usr/bin/env python3
"""eval_router — evaluate the from-scratch function router.

Scores the DECISION QUALITY of the router, not just "did it call":
  route_accuracy : gold function == predicted function (the routing decision)
  well_formed    : call parses to valid JSON (or no-tool when gold=no-tool)
  over_call      : predicted a tool when gold said answer_direct
  under_call     : predicted none when gold said a tool
  per_function   : accuracy per function name (router precision/recall)

Greedy char-by-char generation from the trained scratch model. Every eval
writes a FULL per-item JSONL to logs/ and logs summary metrics to the metrics
store + MLflow.

Usage:
  python scripts/eval_router.py --model models/scratch/1 --data data/raw/cards.jsonl
"""
import argparse
import json
import os
import sys
import time
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from tomac_common import build_prompt, parse_call
from model_scratch import RouterModel, CharTokenizer
from metrics import Metrics
from functions.registry import names as _reg_names
_REG_NAMES = set(_reg_names())

DEFAULT_DATA = os.path.join(ROOT, "data", "raw", "cards.jsonl")
LOGS = os.path.join(ROOT, "logs")


def load_model(model_path, device):
    tok = CharTokenizer.load(os.path.join(model_path, "tokenizer.json"))
    model = RouterModel.load(model_path, device=device).to(device)
    model.eval()
    return tok, model


@torch.no_grad()
def generate_one(tok, model, prompt, max_new=160, device="cpu", eos_id=0):
    ids = torch.tensor([tok.encode(prompt)], dtype=torch.long, device=device)
    gen = model.generate(ids, max_new=max_new, temperature=1.0, eos_id=eos_id)
    out_ids = gen[0][len(ids[0]):].tolist()
    return tok.decode(out_ids)


@torch.no_grad()
def generate_batch(tok, model, prompts, max_new=160, device="cpu", eos_id=0,
                   bsz=32, rep_penalty=1.0):
    """Greedy batched decode. Returns one decoded suffix per prompt.

    Groups prompts by LENGTH so each batch is equal-length (no padding — padding
    would shift the causal context and change routes). Greedy (argmax) so eval
    metrics are reproducible. Keeps the P4 fed (single-seq left it ~40% busy).
    rep_penalty: forwarded to model.generate_batch to break degenerate loops."""
    encs = [tok.encode(p) for p in prompts]
    # group indices by encoded length to avoid padding
    by_len = {}
    for i, e in enumerate(encs):
        by_len.setdefault(len(e), []).append(i)

    out = [None] * len(prompts)
    for _, idxs in by_len.items():
        chunk = [encs[i] for i in idxs]
        for s in range(0, len(chunk), bsz):
            sub = chunk[s:s + bsz]
            ids = torch.tensor(sub, dtype=torch.long, device=device)
            gen = model.generate_batch(ids, max_new=max_new, eos_id=eos_id,
                                       rep_penalty=rep_penalty)
            for k, j in enumerate(idxs[s:s + bsz]):
                suffix = gen[k][len(sub[k]):].tolist()
                if eos_id in suffix:
                    suffix = suffix[:suffix.index(eos_id)]
                out[j] = tok.decode(suffix)
    return out


def load_cards(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "scratch", "1"))
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--max-new", type=int, default=160)
    ap.add_argument("--rep-penalty", type=float, default=1.4,
                    help="repetition penalty (>1 suppresses recent tokens; breaks mememe loops). Must MATCH the live server's value (single decode contract). Default 1.4 = what the small model needs to not loop.")
    ap.add_argument("--limit", type=int, default=0, help="debug: cap cards")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok, model = load_model(args.model, device)
    eos_id = tok.eos_id

    cards = load_cards(args.data)
    if args.limit:
        cards = cards[:args.limit]

    t0 = time.time()
    n = len(cards)
    correct = 0
    well_formed = 0
    over_call = 0
    under_call = 0
    per_fn = {}
    rows = []

    # Build all prompts, then batched greedy decode (keeps the P4 fed; eval is
    # reproducible because generate_batch is argmax, not sampled).
    prompts = [build_prompt(c["q"], c.get("tools")) for c in cards]
    raws = generate_batch(tok, model, prompts, args.max_new, device, eos_id, bsz=32,
                          rep_penalty=args.rep_penalty)

    for c, raw in zip(cards, raws):
        name, args_, wf, _ = parse_call(raw, known_names=set(_REG_NAMES))
        gold = c["name"]
        gold_no_tool = (c.get("target") == c["q"]) or (gold == "answer_direct")
        pred_no_tool = name is None

        if (name == gold) or (gold_no_tool and pred_no_tool):
            correct += 1
            c_ok = True
        else:
            c_ok = False
        if wf or (pred_no_tool and gold_no_tool):
            well_formed += 1
        if (not gold_no_tool) and pred_no_tool:
            under_call += 1
        # over_call: predicted a REAL tool when gold wanted no tool.
        # `answer_direct` emitted as TOOL {} is the correct no-tool answer
        # (model signals "answer directly") — not an over-call. Only an actual
        # tool (compute/get_time/etc.) on a no-tool card is a true over_call.
        pred_is_realtime_tool = (name is not None) and (name != "answer_direct")
        if gold_no_tool and pred_is_realtime_tool:
            over_call += 1
        per_fn.setdefault(gold, [0, 0])
        per_fn[gold][1] += 1
        if c_ok:  # correct_route already handles gold_no_tool && pred_no_tool
            per_fn[gold][0] += 1
        rows.append({"q": c["q"], "gold": gold, "pred": name,
                     "pred_args": args_, "well_formed": wf,
                     "correct_route": c_ok, "raw": raw.strip()})
    wall = time.time() - t0

    os.makedirs(LOGS, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = os.path.basename(os.path.normpath(args.model))
    jl = os.path.join(LOGS, f"eval_router_{tag}_{stamp}.jsonl")
    with open(jl, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    route_acc = correct / n
    wf_rate = well_formed / n
    over = over_call / n
    under = under_call / n

    m = Metrics()
    pid = m.new_pass(mode="eval", base_model="(none/random-init)",
                     num_cards=n, walltime_s=round(wall, 1), status="evaluated")
    # tag the (already-open, mirrored) W&B run so eval runs are filterable
    if m._wb is not None:
        m._wb.set_tags({"from_scratch": True, "project": "tomac",
                        "model": tag, "data": os.path.basename(args.data)})
    m.log_metric(pid, "route_accuracy", round(route_acc, 4))
    m.log_metric(pid, "well_formed", round(wf_rate, 4))
    m.log_metric(pid, "over_call", round(over, 4))
    m.log_metric(pid, "under_call", round(under, 4))
    for fn, (ok, tot) in per_fn.items():
        m.log_metric(pid, f"fn.{fn}", round(ok / tot, 4), detail=f"{ok}/{tot}")
    m.log_meta(pid, "model", tag)
    m.log_meta(pid, "data", os.path.basename(args.data))
    m.log_meta(pid, "per_item_log", jl)
    # log the full per-item JSONL as a wandb artifact (auditable eval trail)
    if m._wb is not None:
        m._wb.log_artifact(jl)
    m.summarize(pid)
    m.cost_report()
    m.close()

    print(f"\n=== eval: {tag} ({n} cards, {wall:.1f}s) ===")
    print(f"  route_accuracy : {route_acc:.4f}")
    print(f"  well_formed    : {wf_rate:.4f}")
    print(f"  over_call      : {over:.4f}")
    print(f"  under_call     : {under:.4f}")
    print("  per-function:")
    for fn, (ok, tot) in sorted(per_fn.items()):
        print(f"    {fn:14s} {ok/tot:.3f}  ({ok}/{tot})")
    print(f"  per-item log   : {jl}")


if __name__ == "__main__":
    main()
