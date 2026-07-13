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
from metrics import Metrics
from mlflow_tracker import get_tracker

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
                prompt = build_prompt(c["q"])
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
    ap.add_argument("--d-model", type=int, default=256)
    ap.add_argument("--n-layers", type=int, default=6)
    ap.add_argument("--n-heads", type=int, default=8)
    ap.add_argument("--d-ff", type=int, default=1024)
    ap.add_argument("--max-len", type=int, default=512)
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
            all_text += build_prompt(c["q"]) + c["target"] + "\n"
    tok = CharTokenizer.from_text(all_text)
    print(f"vocab size: {len(tok)} chars")

    ds = CharDataset(args.data, tok, max_len=args.max_len)
    if args.limit:
        ds.seqs = ds.seqs[:args.limit]
    print(f"training samples: {len(ds)}")
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True,
                    collate_fn=lambda b: collate(b, args.max_len, tok.pad_id))

    model = RouterModel(vocab_size=len(tok), d_model=args.d_model,
                        n_layers=args.n_layers, n_heads=args.n_heads,
                        d_ff=args.d_ff, max_len=args.max_len).to(device)
    print(f"model params: {model.num_params():,}")

    # ---- MLflow: open a run up front so the loss curve streams live ----
    trk = get_tracker()
    trk.start_run("train-" + os.path.basename(os.path.normpath(args.out)), {
        "mode": "train_scratch", "base_model": "(none/random-init)",
        "epochs": args.epochs, "lr": args.lr, "batch": args.batch,
        "d_model": args.d_model, "n_layers": args.n_layers,
        "n_heads": args.n_heads, "d_ff": args.d_ff, "max_len": args.max_len,
        "vocab": len(tok), "num_cards": len(ds), "params": model.num_params(),
        "device": device,
    })
    trk.set_tags({"from_scratch": True, "project": "tomac",
                  "data": os.path.basename(args.data)})

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
                    epochs=args.epochs, lr=args.lr, num_cards=len(ds),
                    loss_final=round(loss_final, 4),
                    walltime_s=round(wall, 1),
                    gpu_mem_used_mb=round(gpu_mem, 1) if gpu_mem else None,
                    status="trained")
    m.log_meta(pid, "model_path", args.out)
    m.log_meta(pid, "params", model.num_params())
    m.log_meta(pid, "vocab", len(tok))
    m.log_meta(pid, "data", os.path.basename(args.data))
    # MLflow: final summary metrics + checkpoint artifact, then close the run.
    trk.log_metrics({
        "loss_final": round(loss_final, 4) if loss_final is not None else 0.0,
        "walltime_s": round(wall, 1),
        "gpu_mem_mb": round(gpu_mem, 1) if gpu_mem else 0.0,
    })
    trk.set_tags({"pass_id": pid})
    trk.log_artifact(args.out)
    trk.end_run()
    m.summarize(pid)
    m.cost_report()
    m.close()
    print(f"logged pass id={pid}")


if __name__ == "__main__":
    main()
