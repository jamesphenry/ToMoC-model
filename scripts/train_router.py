#!/usr/bin/env python3
"""train_router — train the ToMoC router FROM SCRATCH (random init, no base).

The router is a tiny char-level causal Transformer (scripts/model_scratch.py).
We do NOT use a pretrained base or LoRA — the routing grammar is small and
learnable from random init on a Tesla P4 in minutes.

Pipeline:
  1. build_cards.py already produced data/raw/cards.jsonl
  2. build a char vocab from the cards + cue
  3. pack (prompt+target) sequences, cross-entropy over all chars
  4. AdamW, save model.pt + config.json + tokenizer + checkpoint

The prompt uses tomac_common.build_prompt(); the target uses tomac_common.
target_for() — BYTE-IDENTICAL to eval_router.py so the habit transfers.

Usage:
  python scripts/train_router.py --out models/scratch/1 --epochs 30
  python scripts/train_router.py --out models/scratch/360m-eq --d-model 512 --n-layers 8 --epochs 60
"""
import argparse
import json
import os
import sys
import time
import torch
from torch.utils.data import Dataset, DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from tomac_common import build_prompt, target_for
from model_scratch import RouterModel, CharTokenizer
from model_bitnet import BitNetRouterModel
from metrics import Metrics
from wandb_tracker import get_tracker

DEFAULT_DATA = os.path.join(ROOT, "data", "raw", "cards.jsonl")
DEFAULT_OUT = os.path.join(ROOT, "models", "scratch", "1")


class CharDataset(Dataset):
    """Each sample: encode(prompt + target + '\\n'). Cross-entropy over all."""

    def __init__(self, path, tokenizer, max_len=512):
        self.tok = tokenizer
        self.max_len = max_len
        self.seqs = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                c = json.loads(line)
                prompt = build_prompt(c["q"], c.get("tools"))
                target = c["target"].strip()
                text = prompt + target + "\n"
                ids = self.tok.encode(text)[:max_len]
                if len(ids) < 2:
                    continue
                self.seqs.append(torch.tensor(ids, dtype=torch.long))

    def __len__(self):
        return len(self.seqs)

    def __getitem__(self, i):
        return self.seqs[i]


def collate(batch, max_len=512, pad_id=0):
    # left-pad to longest in batch (so sequence ends align for causality)
    L = min(max_len, max(len(s) for s in batch))
    ids = torch.full((len(batch), L), pad_id, dtype=torch.long)
    for i, s in enumerate(batch):
        s = s[-L:]
        ids[i, L - len(s):] = s
    inputs = ids[:, :-1]
    targets = ids[:, 1:]
    # mask padding targets
    targets = targets.masked_fill(inputs == pad_id, -100)
    return inputs, targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--d-model", type=int, default=192)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--n-heads", type=int, default=6)
    ap.add_argument("--d-ff", type=int, default=1024)
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--bitnet", action="store_true",
                    help="train the BitNet b1.58 ternary-weight variant "
                         "(model_bitnet.BitNetRouterModel) instead of the FP "
                         "RouterModel. Same shape contract; weights ternarized "
                         "in forward with STE training.")
    ap.add_argument("--bitnet-weights-only", action="store_true",
                    help="BitNet variant with FP activations (no INT8 clamp); "
                         "only the matmul weights are ternary. Isolates whether "
                         "the activation clamp causes collapse.")
    ap.add_argument("--purpose", default=None,
                    help="short human purpose for the W&B run name, e.g. "
                         "'bitnet weights-only baseline'. Renders as "
                         "'<run#> - <purpose>' in W&B.")
    ap.add_argument("--tags", default="",
                    help="comma-separated freeform tags to add on top of the "
                         "auto tags (mode/precision/size/variant), e.g. "
                         "'ablation,experiment'.")
    ap.add_argument("--limit", type=int, default=0, help="debug: cap samples")
    args = ap.parse_args()

    torch.cuda.empty_cache()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ---- build char vocab from the FULL text of cards + cue ----
    from tomac_common import CUE
    all_text = CUE
    with open(args.data, encoding="utf-8") as fh:
        for line in fh:
            c = json.loads(line)
            all_text += build_prompt(c["q"], c.get("tools")) + c["target"] + "\n"
    tok = CharTokenizer.from_text(all_text)
    print(f"vocab size: {len(tok)} chars")

    ds = CharDataset(args.data, tok, max_len=args.max_len)
    if args.limit:
        ds.seqs = ds.seqs[:args.limit]
    print(f"training samples: {len(ds)}")
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True,
                    collate_fn=lambda b: collate(b, args.max_len, tok.pad_id))

    use_bitnet = bool(args.bitnet or args.bitnet_weights_only)
    model_cls = BitNetRouterModel if use_bitnet else RouterModel
    weights_only = bool(args.bitnet_weights_only)
    model_kwargs = dict(vocab_size=len(tok), d_model=args.d_model,
                        n_layers=args.n_layers, n_heads=args.n_heads,
                        d_ff=args.d_ff, max_len=args.max_len)
    if use_bitnet:
        model_kwargs["weights_only"] = weights_only
    model = model_cls(**model_kwargs).to(device)
    kind = ("BitNet b1.58 (weights+act)" if args.bitnet
            else "BitNet weights-only" if args.bitnet_weights_only
            else "FP")
    print(f"model params: {model.num_params():,}  ({kind})")

    # ---- auto tags (filterable in W&B) derived from facts we already know ----
    precision = "1-bit" if use_bitnet else "FP"
    variant = ("bitnet" if args.bitnet
               else "bitnet-wo" if args.bitnet_weights_only else "fp")
    auto_tags = {
        "from_scratch": True, "project": "tomac",
        "mode": "train", "precision": precision, "variant": variant,
        "size": f"{model.num_params()//1_000_000}M"
        if model.num_params() >= 1_000_000
        else f"{model.num_params()//1000}k",
        "data": os.path.basename(args.data),
    }
    if args.tags:
        for t in args.tags.split(","):
            t = t.strip()
            if t:
                auto_tags[t] = True
    run_name = (f"{os.path.basename(os.path.normpath(args.out))} - {args.purpose}"
                if args.purpose else None)

    # ---- MLflow: open a run up front so the loss curve streams live ----
    trk = get_tracker()
    trk.start_run("train-" + os.path.basename(os.path.normpath(args.out)), {
        "mode": "train_scratch", "base_model": "(none/random-init)",
        "epochs": args.epochs, "lr": args.lr, "batch": args.batch,
        "d_model": args.d_model, "n_layers": args.n_layers,
        "n_heads": args.n_heads, "d_ff": args.d_ff, "max_len": args.max_len,
        "vocab": len(tok), "num_cards": len(ds), "params": model.num_params(),
        "device": device,
    }, name=run_name)
    trk.set_tags(auto_tags)
    # ensure the model-registry collection exists (org = WANDB_ENTITY / ToMoC)
    trk.create_registry()
    # log the exact training data (tracked Dataset + raw artifact)
    trk.log_dataset(args.data, name=os.path.basename(args.data))

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    t0 = time.time()
    loss_final = None
    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        nbatches = 0
        for inputs, targets in dl:
            inputs, targets = inputs.to(device), targets.to(device)
            opt.zero_grad()
            _, loss = model(inputs, targets)
            loss.backward()
            opt.step()
            running += loss.item()
            nbatches += 1
        loss_final = running / max(nbatches, 1)
        trk.log_metric("train_loss", loss_final, step=epoch)
        print(f"  epoch {epoch+1}/{args.epochs}  loss={loss_final:.4f}")
    wall = time.time() - t0

    os.makedirs(args.out, exist_ok=True)
    model.save(args.out)
    tok.save(os.path.join(args.out, "tokenizer.json"))

    gpu_mem = (torch.cuda.max_memory_allocated() / (1024 * 1024)
               if torch.cuda.is_available() else None)

    print(f"\nmodel saved -> {args.out}")
    print(f"walltime_s={wall:.1f} loss_final={loss_final:.4f} "
          f"gpu_mem_mb={gpu_mem} params={model.num_params()}")

    m = Metrics()
    pid = m.new_pass(mode="train_scratch", base_model="(none/random-init)",
                    run_name=run_name, tags=auto_tags,
                    epochs=args.epochs, lr=args.lr, num_cards=len(ds),
                    loss_final=round(loss_final, 4),
                    walltime_s=round(wall, 1),
                    gpu_mem_used_mb=round(gpu_mem, 1) if gpu_mem else None,
                    status="trained")
    m.log_meta(pid, "model_path", args.out)
    m.log_meta(pid, "params", model.num_params())
    m.log_meta(pid, "vocab", len(tok))
    m.log_meta(pid, "data", os.path.basename(args.data))
    # pin the exact training data to this run as a versioned dataset artifact
    trk.log_dataset(args.data, name="cards")
    # W&B: final summary metrics (cost + system) as sortable columns, then close.
    row = m.conn.execute(
        "SELECT cost_usd, gpu_watts FROM passes WHERE id=?", (pid,)).fetchone()
    trk.log_metrics({
        "loss_final": round(loss_final, 4) if loss_final is not None else 0.0,
        "walltime_s": round(wall, 1),
        "gpu_mem_mb": round(gpu_mem, 1) if gpu_mem else 0.0,
        "cost_usd": row["cost_usd"] if row and row["cost_usd"] is not None else 0.0,
        "gpu_watts": row["gpu_watts"] if row and row["gpu_watts"] is not None else 0.0,
        "params": model.num_params(),
    })
    trk.set_tags({**auto_tags, "pass_id": pid})
    trk.log_artifact(args.out)
    trk.end_run()
    m.summarize(pid)
    m.cost_report()
    m.close()
    print(f"logged pass id={pid}")


if __name__ == "__main__":
    main()
