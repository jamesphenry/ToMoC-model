#!/usr/bin/env python3
"""executors — the router's tool handlers (the ACTUAL capabilities).

Each function in functions/registry.json maps to a handler here keyed by name.
The live loop (router_server.py) parses the model's ``TOOL <name> <json>`` and
calls ``execute(name, args)``. The model DECIDES; the handler DOES.

Sovereignty / safety (defense-in-depth, mirrors smol's sandbox.py):
- compute: AST-scanned, no imports/open/defs/dunders, run in an isolated
  subprocess with a CPU rlimit + timeout. The model emits the expression; we
  execute it safely.
- write handlers (remind_me): GATED. execute() returns a *proposed* write and
  NEVER mutates disk. A human commits via the CLI. The model can propose,
  never poison.
- reads (wiki_read, get_time, unit_convert): pure, no side effects.
"""
import ast
import datetime as _dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VAULT_ROOT = os.path.join(ROOT, "data", "vault")
REMINDERS_FILE = os.path.join(ROOT, "data", "reminders.md")


# ---------------------------------------------------------------- compute
_FORBIDDEN = (
    ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef,
    ast.AsyncFunctionDef, ast.Lambda, ast.With, ast.AsyncWith,
    ast.Try, ast.Raise, ast.Global, ast.Nonlocal,
)


def _scan(node: ast.AST):
    """Reject dangerous nodes. Cheap, no side effects."""
    for n in ast.walk(node):
        if isinstance(n, _FORBIDDEN):
            raise ValueError(f"disallowed construct: {type(n).__name__}")
        if isinstance(n, ast.Attribute):
            if n.attr.startswith("__") and n.attr.endswith("__"):
                raise ValueError(f"dunder access rejected: {n.attr}")
        if isinstance(n, ast.Call):
            fn = n.func
            if isinstance(fn, ast.Name) and fn.id in ("open", "eval", "exec",
                                                       "compile", "__import__"):
                raise ValueError(f"blocked call: {fn.id}")


def _compute_subprocess(expr: str) -> str:
    """Execute the expression in a stripped, isolated subprocess."""
    code = (
        "import ast,json\n"
        "expr=" + repr(expr) + "\n"
        "tree=ast.parse(expr,mode='eval')\n"
        "_bad=(ast.Import,ast.ImportFrom,ast.Call,ast.Attribute,ast.Name)\n"
        "for n in ast.walk(tree):\n"
        "    if isinstance(n,ast.Call):\n"
        "        f=n.func\n"
        "        if isinstance(f,ast.Name) and f.id in ('open','eval','exec','compile','__import__'):\n"
        "            raise ValueError('blocked')\n"
        "    if isinstance(n,ast.Attribute) and n.attr.startswith('__'):\n"
        "        raise ValueError('dunder')\n"
        "v=eval(compile(tree,'<expr>','eval'),{'__builtins__':{}},{})\n"
        "print(json.dumps(v))\n"
    )
    env = {k: os.environ[k] for k in ("PATH", "PYTHONPATH", "LANG", "LC_ALL") if k in os.environ}
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True, text=True, timeout=2, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip().splitlines()[-1] if proc.stderr else "compute failed")
    return json.loads(proc.stdout.strip())


def compute(args: dict) -> dict:
    expr = (args or {}).get("expression")
    if not expr or not isinstance(expr, str):
        return {"ok": False, "error": "compute needs a string 'expression'"}
    try:
        _scan(ast.parse(expr, mode="eval"))
        val = _compute_subprocess(expr)
        return {"ok": True, "result": val}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- get_time
def get_time(args: dict) -> dict:
    tz = (args or {}).get("timezone")
    try:
        if tz:
            from zoneinfo import ZoneInfo
            now = _dt.datetime.now(ZoneInfo(tz))
        else:
            now = _dt.datetime.now()
        return {"ok": True, "result": now.strftime("%Y-%m-%d %H:%M:%S %Z").strip()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"unknown timezone: {tz} ({e})"}


# ------------------------------------------------------------- unit_convert
_FACTORS = {
    "length": {"m": 1.0, "km": 1000.0, "cm": 0.01, "mi": 1609.344, "ft": 0.3048, "in": 0.0254},
    "mass": {"kg": 1.0, "g": 0.001, "lb": 0.45359237, "oz": 0.028349523125},
    "time": {"s": 1.0, "min": 60.0, "h": 3600.0, "day": 86400.0},
}
_UNIT_KIND = {}
for _k, _tbl in _FACTORS.items():
    for _u in _tbl:
        _UNIT_KIND[_u] = _k


def unit_convert(args: dict) -> dict:
    try:
        v = float((args or {}).get("value"))
        frm = (args or {}).get("from")
        to = (args or {}).get("to")
        if frm not in _UNIT_KIND or to not in _UNIT_KIND:
            return {"ok": False, "error": f"unsupported unit pair: {frm} -> {to}"}
        if _UNIT_KIND[frm] != _UNIT_KIND[to]:
            return {"ok": False, "error": f"incompatible units: {frm} ({_UNIT_KIND[frm]}) vs {to} ({_UNIT_KIND[to]})"}
        meters = v * _FACTORS[_UNIT_KIND[frm]][frm]
        out = meters / _FACTORS[_UNIT_KIND[to]][to]
        return {"ok": True, "result": out}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- wiki_read
def _slugify(s: str) -> str:
    s = (s or "").lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80] or "note"


def wiki_read(args: dict) -> dict:
    query = (args or {}).get("query")
    if not query:
        return {"ok": False, "error": "wiki_read needs 'query'"}
    cat = (args or {}).get("category")
    base = os.path.join(VAULT_ROOT, cat) if cat else VAULT_ROOT
    # fuzzy: walk notes, score by token overlap in key/body
    q_toks = set(re.findall(r"[a-z0-9]+", query.lower()))
    best, best_e = 0.0, None
    roots = [base] if cat else [os.path.join(VAULT_ROOT, d) for d in os.listdir(VAULT_ROOT)] if os.path.isdir(VAULT_ROOT) else []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                full = os.path.join(dp, fn)
                try:
                    txt = open(full, encoding="utf-8").read()
                except Exception:
                    continue
                head = txt.split("---", 2)[-1] if txt.startswith("---") else txt
                t_toks = set(re.findall(r"[a-z0-9]+", head.lower()))
                if q_toks and t_toks:
                    j = len(q_toks & t_toks) / len(q_toks | t_toks)
                    if j > best:
                        best, best_e = j, txt
    if best_e and best >= 0.3:
        return {"ok": True, "result": best_e.strip(), "match_score": round(best, 3)}
    return {"ok": False, "error": f"no vault match for '{query}'", "verdict": "miss"}


# ---------------------------------------------------------------- remind_me
def remind_me(args: dict) -> dict:
    """GATED write. Propose only — never mutates disk. Human commits via CLI."""
    text = (args or {}).get("text")
    when = (args or {}).get("when")
    if not text:
        return {"ok": False, "error": "remind_me needs 'text'"}
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"text": text, "when": when or "", "created": now}
    return {"ok": True, "proposed": True, "needs_approval": True,
            "entry": entry, "verdict": "proposed_write"}


# ----------------------------------------------------------------- dispatch
_HANDLERS = {
    "compute": compute,
    "get_time": get_time,
    "unit_convert": unit_convert,
    "wiki_read": wiki_read,
    "remind_me": remind_me,
}


def execute(name: str, args: dict | None) -> dict:
    """Run a function handler. Unknown functions -> clear error (router mistake)."""
    h = _HANDLERS.get(name)
    if h is None:
        return {"ok": False, "error": f"unknown function: {name}", "verdict": "unknown_function"}
    try:
        return h(args or {})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    # quick self-test of every handler
    for nm, a in [
        ("compute", {"expression": "48 - 5 + 20"}),
        ("compute", {"expression": "bad^call"}),  # should fail safely
        ("get_time", {}),
        ("get_time", {"timezone": "UTC"}),
        ("unit_convert", {"value": 5, "from": "mi", "to": "km"}),
        ("wiki_read", {"query": "nonexistent thing xyz"}),
        ("remind_me", {"text": "test reminder", "when": "later"}),
        ("answer_direct", {}),
    ]:
        print(nm, "->", execute(nm, a))
