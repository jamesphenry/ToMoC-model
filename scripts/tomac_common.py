#!/usr/bin/env python3
"""tomac_common — shared router primitives.

The router LLM is trained + evaluated to emit a single, stable call format:

    TOOL <name> <json-args>

Both train_router.py and eval_router.py MUST build prompts and parse calls
with the helpers here so the cue string + call grammar stay BYTE-IDENTICAL
between training and eval. (smol-lab BUG-class: a drifted cue silently kills
the habit transfer; a strict parser hid well-formed calls — see wiki/BUGS.md.)

Design notes:
- JSON args (not ``name="x"``) so a function with N typed params is just one
  more schema line in functions/registry.json. The router scales to ANY
  function you register, with zero code changes to the model.
- parse_call() is TOLERANT: a call missing its closing brace (truncated by
  max_new_tokens) still yields the function name so routing can be scored.
  This is the CALL_OPEN_RE lesson from smol, applied to JSON.
"""
import json
import re

# The priming cue. Bytes here are the contract. Do NOT edit casually.
CUE = (
    "You are a smart router for a personal assistant. "
    "If a request needs an external tool, knowledge lookup, or action, "
    "emit exactly one function call. Otherwise answer directly.\n"
)

# Prompt = cue + the request. Train and eval build it the same way.
PROMPT_TMPL = "{cue}Request: {q}\nRoute to a function:\n"


def build_prompt(q: str) -> str:
    return PROMPT_TMPL.format(cue=CUE, q=q.strip())


def target_for(name: str, args: dict | None) -> str:
    """Training target string for a (function, args) gold pair."""
    if not args:
        return f"TOOL {name} {{}}"
    return f"TOOL {name} {json.dumps(args, ensure_ascii=False)}"


# Tolerant call regex: capture ONLY the function name. JSON is parsed
# separately so a TRUNCATED json (missing closing brace) still yields the name.
_CALL_RE = re.compile(r"TOOL\s+([A-Za-z0-9_]+)", re.DOTALL)


def parse_call(text: str):
    """Parse a model emission into (name, args, well_formed, raw).

    - name:        the function name, or None if no TOOL call found
    - args:        dict (parsed JSON) or {} if no json / unparseable
    - well_formed: True only if a JSON object was present AND parsed cleanly
    - raw:         the original text (for logging)

    Tolerant (smol BUG-003): if the JSON is opened but truncated/unbalanced, we
    STILL recover the function name (best-effort args) and return
    well_formed=False. The router's *routing* decision is scored even when its
    JSON is malformed — but a format slip can never masquerade as a clean call.
    """
    if text is None:
        return (None, {}, False, "")
    m = _CALL_RE.search(text)
    if not m:
        return (None, {}, False, text)
    name = m.group(1)
    rest = text[m.end():].lstrip()
    if not rest.startswith("{"):
        # no json object present -> a genuine no-arg call (e.g. TOOL get_time)
        return (name, {}, True, text)
    try:
        args = json.loads(rest)
        if not isinstance(args, dict):
            return (name, {}, False, text)
        return (name, args, True, text)
    except json.JSONDecodeError:
        # truncated/unbalanced JSON: recover best-effort, mark NOT well_formed
        recovered = _try_recover(rest)
        if recovered is not None:
            return (name, recovered, False, text)
        return (name, {}, False, text)


def _try_recover(js: str):
    """Best-effort: close a truncated JSON object. Returns dict or None."""
    s = js.strip()
    if not s.startswith("{"):
        return None
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    # append missing closing braces
    if depth > 0:
        cand = s + "}" * depth
        try:
            obj = json.loads(cand)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def pretty_call(name: str, args: dict | None) -> str:
    return target_for(name, args)
