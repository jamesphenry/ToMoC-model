#!/usr/bin/env python3
"""model_bitnet — BitNet b1.58 variant of the ToMoC router (from scratch).

Faithful ternary-weight training regime. Weights are stored as full-precision
latents but TERNARIZED on the fly in the forward pass:

    W_ternary = RoundClamp(W / gamma),   gamma = mean(|W|) over the matrix
    RoundClamp(x) = clip(round(x), -1, 0, +1)   -> values in {-1, 0, +1}

The straight-through estimator (STE) passes gradients back to the FP latents
during training, so the model learns ternary-friendly weights from random init.
Activations are clamped to INT8 range (b1.58 uses true INT8 matmuls; we keep
FP but clamp, which preserves the precision regime for training on the P4).

Why do this: a 1-bit/ternary router is the sovereignty endgame — functions-are-
knowledge running on trivial hardware (microcontroller-class, no multiply
units). This side-track compares route_accuracy + arg_accuracy vs the pinned
2.3M FP baseline (models/scratch/baseline-100ep-8fn.PINNED).

The class mirrors RouterModel's public API (forward / generate / generate_batch
/ save / load / num_params) so train_router.py and eval_router.py work unchanged
when passed --bitnet. Only the matmul precision differs.
"""
import math
import os
import json
import torch
import torch.nn as nn
from torch.nn import functional as F

# Reuse the char tokenizer from the FP model (identical vocab contract).
from model_scratch import CharTokenizer


class BitLinear(nn.Module):
    """Linear layer with ternary weights (BitNet b1.58).

    Stores full-precision `weight` latents. In forward, ternarizes them with
    per-matrix RMS scaling + RoundClamp, and clamps activations to INT8 range.
    Backward uses STE: gradient flows to latents as if the ternary op were
    identity (straight-through). Bias is omitted (matches RouterModel).
    """

    def __init__(self, in_features, out_features, clamp_act=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.clamp_act = clamp_act
        # full-precision latents (the learned params)
        self.weight = nn.Parameter(torch.zeros(out_features, in_features))
        self.reset_parameters()

    def reset_parameters(self):
        # xavier-ish init scaled for ternary (std ~ 1/sqrt(fan_in) is fine;
        # the ternary op will compress it, STE trains it into a good ternary set)
        nn.init.xavier_uniform_(self.weight)

    def _ternarize(self, w):
        # gamma = mean absolute value per output row (BitNet RMS scaling)
        gamma = w.abs().mean(dim=-1, keepdim=True).clamp_min(1e-8)
        s = w / gamma
        # RoundClamp to {-1, 0, +1}: round() then clip to [-1, 1]
        t = s.round().clamp_(-1, 1)
        return t

    def forward(self, x):
        # STE: during backward, grad flows to self.weight as if _ternarize
        # were identity (straight-through). We compute ternary for the forward
        # value but use the latents' autograd graph for the backward pass.
        w_tern = self._ternarize(self.weight)
        if self.training:
            # straight-through: forward uses ternary, backward uses latents
            w_eff = self.weight + (w_tern - self.weight).detach()
        else:
            w_eff = w_tern
        out = F.linear(x, w_eff)
        if self.clamp_act:
            # b1.58 INT8 activation range (kept as FP clamp for trainability)
            out = out.clamp_(-127.0, 127.0)
        return out


class BitCausalSelfAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.qkv = BitLinear(d_model, 3 * d_model)
        self.proj = BitLinear(d_model, d_model)
        self.scale = self.head_dim ** -0.5

    def forward(self, x):
        B, T, C = x.shape
        qkv = self.qkv(x).split(C, dim=-1)
        q, k, v = qkv
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) * self.scale
        mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool),
                          diagonal=1)
        att = att.masked_fill(mask, float("-inf"))
        att = F.softmax(att, dim=-1)
        out = att @ v
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(out)


class BitFeedForward(nn.Module):
    def __init__(self, d_model, d_ff):
        super().__init__()
        self.net = nn.Sequential(
            BitLinear(d_model, d_ff),
            nn.GELU(),
            BitLinear(d_ff, d_model),
        )

    def forward(self, x):
        return self.net(x)


class BitBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = BitCausalSelfAttention(d_model, n_heads)
        self.ln2 = nn.LayerNorm(d_model)
        self.ff = BitFeedForward(d_model, d_ff)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x


class BitNetRouterModel(nn.Module):
    """BitNet b1.58 pre-norm causal Transformer, char-level, random-init.

    Same shape contract as RouterModel so train_router.py (+ --bitnet) and
    eval_router.py work unchanged. Only matmul weights are ternary; embeddings,
    LayerNorm, and the head are kept full-precision (standard b1.58 practice:
    only the large Linear matrices are 1.58-bit; norms/embeddings stay FP).
    """

    def __init__(self, vocab_size, d_model=256, n_layers=6, n_heads=8,
                 d_ff=1024, max_len=512, dropout=0.0):
        super().__init__()
        self.cfg = dict(vocab_size=vocab_size, d_model=d_model,
                        n_layers=n_layers, n_heads=n_heads, d_ff=d_ff,
                        max_len=max_len, bitnet=True)
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Parameter(torch.zeros(1, max_len, d_model))
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(
            [BitBlock(d_model, n_heads, d_ff) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = BitLinear(d_model, vocab_size)

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
        """Single-seq generation (live server). Same decode contract as FP."""
        self.eval()
        with torch.no_grad():
            for _ in range(max_new):
                logits, _ = self.forward(idx[:, -self.cfg["max_len"]:])
                next_logits = logits[:, -1, :] / max(temperature, 1e-6)
                if rep_penalty > 1.0 and idx.shape[1] > 1:
                    recent = idx[0, -rep_window:]
                    next_logits[0, recent] /= rep_penalty
                if temperature <= 0:
                    nxt = torch.argmax(next_logits, dim=-1, keepdim=True)
                else:
                    probs = F.softmax(next_logits, dim=-1)
                    nxt = torch.multinomial(probs, num_samples=1)
                idx = torch.cat([idx, nxt], dim=1)
                if eos_id is not None and int(nxt) == eos_id:
                    break
        return idx

    @torch.no_grad()
    def generate_batch(self, idx, max_new=128, eos_id=None, stall_patience=8,
                       rep_penalty=1.0, rep_window=16):
        """Greedy batched generation (eval). Mirrors RouterModel.generate_batch."""
        self.eval()
        B = idx.shape[0]
        finished = torch.zeros(B, dtype=torch.bool, device=idx.device)
        for _ in range(max_new):
            logits, _ = self.forward(idx[:, -self.cfg["max_len"]:])
            nxt_logits = logits[:, -1, :]
            if rep_penalty > 1.0:
                win = idx[:, max(0, idx.shape[1] - rep_window):]
                rows = torch.arange(B, device=idx.device)
                nxt_logits[rows[:, None], win] /= rep_penalty
            nxt = torch.argmax(nxt_logits, dim=-1, keepdim=True)
            idx = torch.cat([idx, nxt], dim=1)
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
        vocab_size = cfg.pop("vocab_size")
        cfg.pop("bitnet", None)  # flag marker, not a ctor arg
        model = cls(vocab_size=vocab_size, **cfg)
        model.load_state_dict(torch.load(os.path.join(path, "model.pt"),
                                         map_location=device))
        return model
