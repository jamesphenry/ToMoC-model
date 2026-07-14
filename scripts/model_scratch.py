#!/usr/bin/env python3
"""model_scratch — a tiny from-scratch causal transformer for the router.

ToMoC is trained FROM RANDOM INIT (no pretrained base). The thesis: the router
does NOT need world knowledge, only the habit of emitting

    TOOL <name> <json-args>

when a request needs a tool, and answering directly otherwise. That's a small
grammar over a small vocabulary (the request words + the function names + JSON),
so a tiny char-level model can learn it.

Why char-level:
  * Zero tokenizer dependency / licensing; the vocab is just the chars seen.
  * Tiny embedding table (~256 rows) keeps VRAM on a Tesla P4 (8GB) trivial.
  * The function names and JSON braces are literal tokens the model sees 1:1.

The model is intentionally minimal (pre-norm Transformer, rotary-free) but a
real autoregressive LM: it learns next-char given past chars. Training is plain
cross-entropy over all chars (we supervise both the prompt and the route, so
the router also learns to echo the request formatting implicitly).

Size knobs (constructor args): d_model, n_layers, n_heads, d_ff. Defaults target
~3M params — enough to learn the routing grammar, small enough to train in
minutes on one P4.
"""
import math
import os
import json
import torch
import torch.nn as nn
from torch.nn import functional as F


class CharTokenizer:
    """Vocab = every character seen in the corpus. Built from cards.jsonl."""

    def __init__(self, chars=None):
        if chars is None:
            chars = []
        # ensure stable ordering; PAD=0, newline and common chars included
        self.chars = list(chars)
        self.char2i = {c: i for i, c in enumerate(self.chars)}
        self.i2char = {i: c for i, c in enumerate(self.chars)}
        self.pad_id = 0
        self.eos_id = self.char2i.get("\n", 0)

    @classmethod
    def from_text(cls, text):
        # keep insertion order = first-seen order
        seen = []
        for ch in text:
            if ch not in seen:
                seen.append(ch)
        return cls(seen)

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return cls.from_text(text)

    def add_text(self, text):
        for ch in text:
            if ch not in self.char2i:
                self.char2i[ch] = len(self.chars)
                self.chars.append(ch)
                self.i2char = {i: c for i, c in enumerate(self.chars)}

    def encode(self, s):
        return [self.char2i.get(c, self.pad_id) for c in s]

    def decode(self, ids):
        return "".join(self.i2char.get(int(i), "") for i in ids)

    def __len__(self):
        return len(self.chars)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"chars": self.chars}, fh)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return cls(d["chars"])


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.proj = nn.Linear(d_model, d_model, bias=False)
        self.scale = self.head_dim ** -0.5

    def forward(self, x):
        B, T, C = x.shape
        qkv = self.qkv(x).split(C, dim=-1)
        q, k, v = qkv
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) * self.scale
        # causal mask
        mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool),
                          diagonal=1)
        att = att.masked_fill(mask, float("-inf"))
        att = F.softmax(att, dim=-1)
        out = att @ v
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(out)


class FeedForward(nn.Module):
    def __init__(self, d_model, d_ff):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_ff, bias=False),
            nn.GELU(),
            nn.Linear(d_ff, d_model, bias=False),
        )

    def forward(self, x):
        return self.net(x)


class Block(nn.Module):
    def __init__(self, d_model, n_heads, d_ff):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads)
        self.ln2 = nn.LayerNorm(d_model)
        self.ff = FeedForward(d_model, d_ff)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))   # pre-norm residual
        x = x + self.ff(self.ln2(x))
        return x


class RouterModel(nn.Module):
    """Minimal pre-norm causal Transformer, char-level, random-init."""

    def __init__(self, vocab_size, d_model=256, n_layers=6, n_heads=8,
                 d_ff=1024, max_len=512, dropout=0.0):
        super().__init__()
        self.cfg = dict(vocab_size=vocab_size, d_model=d_model,
                        n_layers=n_layers, n_heads=n_heads, d_ff=d_ff,
                        max_len=max_len)
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Parameter(torch.zeros(1, max_len, d_model))
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(
            [Block(d_model, n_heads, d_ff) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

    def forward(self, idx, targets=None):
        B, T = idx.shape
        pos = self.pos_emb[:, :T, :]
        x = self.tok_emb(idx) + pos
        x = self.drop(x)
        for blk in self.blocks:
            x = blk(x)
        x = self.ln_f(x)
        logits = self.head(x)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)),
                                   targets.view(-1))
        return logits, loss

    def generate(self, idx, max_new=128, temperature=1.0, eos_id=None,
                 rep_penalty=1.0, rep_window=16):
        """Single-sequence generation (used by the live server).

        rep_penalty: >1.0 suppresses tokens seen in the last `rep_window`
        chars (breaks degenerate loops like 'memememe'/'titititi' that a
        fixed-run stall check misses). 1.0 = no penalty (backward compat)."""
        self.eval()
        with torch.no_grad():
            for _ in range(max_new):
                logits, _ = self.forward(idx[:, -self.cfg["max_len"]:])
                next_logits = logits[:, -1, :] / max(temperature, 1e-6)
                if rep_penalty > 1.0 and idx.shape[1] > 1:
                    recent = idx[0, -rep_window:]
                    next_logits[0, recent] /= rep_penalty
                probs = F.softmax(next_logits, dim=-1)
                nxt = torch.multinomial(probs, num_samples=1)
                idx = torch.cat([idx, nxt], dim=1)
                if eos_id is not None and int(nxt) == eos_id:
                    break
        return idx

    @torch.no_grad()
    def generate_batch(self, idx, max_new=128, eos_id=None, stall_patience=8,
                       rep_penalty=1.0, rep_window=16):
        """Greedy batched generation (eval). temperature=0 -> argmax, so eval
        metrics are reproducible. Caller passes EQUAL-LENGTH rows (eval groups by
        prompt length) so there is no padding and positions stay correct.

        stall_patience: stop a row early if the same char repeats this many times
        (the trained model may never emit EOS; this prevents running the full
        max_new on degenerate loops).

        rep_penalty: >1.0 divides logits of tokens seen in the row's last
        `rep_window` chars by the penalty before argmax — breaks the alternating
        'mememe'/'titi' loops that a fixed-run stall check cannot catch."""
        self.eval()
        B = idx.shape[0]
        finished = torch.zeros(B, dtype=torch.bool, device=idx.device)
        for _ in range(max_new):
            logits, _ = self.forward(idx[:, -self.cfg["max_len"]:])
            nxt_logits = logits[:, -1, :]
            if rep_penalty > 1.0:
                # suppress per-row recently-generated tokens
                win = idx[:, max(0, idx.shape[1] - rep_window):]
                rows = torch.arange(B, device=idx.device)
                nxt_logits[rows[:, None], win] /= rep_penalty
            nxt = torch.argmax(nxt_logits, dim=-1, keepdim=True)
            idx = torch.cat([idx, nxt], dim=1)
            # stall detection on the generated suffix (per-row): if the last
            # `stall_patience` chars are all identical, this row is looping.
            if stall_patience and idx.shape[1] > stall_patience:
                tail = idx[:, -stall_patience:]
                stalled = torch.eq(tail, tail[:, :1]).all(dim=1)
                finished |= stalled
            just_fin = (nxt.squeeze(-1) == eos_id) if eos_id is not None else torch.zeros(B, dtype=torch.bool, device=idx.device)
            finished |= just_fin
            if finished.all():
                break
        return idx

    def save(self, path):
        os.makedirs(path, exist_ok=True)
        torch.save(self.state_dict(), os.path.join(path, "model.pt"))
        with open(os.path.join(path, "config.json"), "w") as fh:
            json.dump(self.cfg, fh)

    @classmethod
    def load(cls, path, device="cpu"):
        cfg = json.load(open(os.path.join(path, "config.json")))
        # vocab_size comes from the tokenizer, not the config; accept kwarg
        vocab_size = cfg.pop("vocab_size")
        model = cls(vocab_size=vocab_size, **cfg)
        model.load_state_dict(torch.load(os.path.join(path, "model.pt"),
                                         map_location=device))
        return model
