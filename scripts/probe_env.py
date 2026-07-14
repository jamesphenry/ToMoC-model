#!/usr/bin/env python3
"""probe_env — verify the homelab env before spending GPU on a run.

Checks: python, torch + CUDA, GPU, the ML stack, MLflow, and the function
registry. Prints a go/no-go summary. No GPU work is done.

Usage:
  python scripts/probe_env.py
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)


def line(label, ok, detail=""):
    mark = "OK " if ok else "XX "
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=== tomac env probe ===")
    print(f"  python : {sys.version.split()[0]}")

    # torch + cuda
    try:
        import torch
        line("torch", True, torch.__version__)
        if torch.cuda.is_available():
            line("CUDA", True, f"{torch.cuda.get_device_name(0)} "
                 f"({torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB)")
        else:
            line("CUDA", False, "no GPU visible")
    except Exception as e:
        line("torch", False, str(e))
        return

    for mod in ("transformers", "peft", "trl", "datasets", "accelerate"):
        try:
            m = importlib.import_module(mod)
            line(mod, True, getattr(m, "__version__", "?"))
        except Exception as e:
            line(mod, False, str(e))

    # wandb (optional — self-hosted server container; see wandb_tracker.py)
    try:
        import wandb
        uri = os.environ.get("WANDB_API_URL", "(not configured)")
        line("wandb", True, f"{wandb.__version__}  server={uri}")
    except Exception:
        line("wandb", False, "not installed (optional; metrics store still works)")

    # registry
    try:
        from functions.registry import names
        fs = names()
        line("function registry", True, f"{len(fs)} functions: {', '.join(fs)}")
    except Exception as e:
        line("function registry", False, str(e))

    # models dir (from-scratch training writes here; bases optional)
    mp = os.path.join(ROOT, "models")
    if os.path.isdir(mp):
        have = [d for d in os.listdir(mp) if os.path.isdir(os.path.join(mp, d))]
        line("models dir", True, ", ".join(have) if have else "empty (scratch training will populate)")
    else:
        line("models dir", False, "models/ missing — will be created on first train")

    # from-scratch architecture sanity (random init, no base needed)
    try:
        from model_scratch import RouterModel, CharTokenizer
        tok = CharTokenizer(chars=list("abc\n"))
        mdl = RouterModel(vocab_size=len(tok), d_model=64, n_layers=2,
                          n_heads=4, d_ff=128)
        x = torch.zeros(1, 5, dtype=torch.long)
        logits, loss = mdl(x, x)
        line("scratch model", True, f"{mdl.num_params():,} params, "
             f"fwd ok logits={tuple(logits.shape)}")
    except Exception as e:
        line("scratch model", False, str(e))


if __name__ == "__main__":
    main()
