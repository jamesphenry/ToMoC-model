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
# Multi-tool variant: the available tools are listed so the router learns to
# DISAMBIGUATE (pick the right one when several are plausible). The trailing
# "\nRoute to a function:\n" is identical to the single-tool prompt so the
# generation head is unchanged — only the context differs.
PROMPT_TMPL_WITH_TOOLS = "{cue}Request: {q}\nAvailable tools: {tools}\nRoute to a function:\n"


def build_prompt(q: str, tools=None) -> str:
    """Build the router prompt. If `tools` (list[str]) is given, the available
    functions are listed in the prompt so the model learns selection boundaries.

    Single-tool cards (tools=None) produce the ORIGINAL byte-identical prompt,
    so existing evals and the live server are unaffected.
    """
    if tools:
        return PROMPT_TMPL_WITH_TOOLS.format(cue=CUE, q=q.strip(),
                                             tools=", ".join(tools))
    return PROMPT_TMPL.format(cue=CUE, q=q.strip())


def target_for(name: str, args: dict | None) -> str:
    """Training target string for a (function, args) gold pair.

    A trailing newline is the EOS token (CharTokenizer.eos_id == '\\n'), so the
    model learns to STOP after emitting the call. Without it the model never
    emits EOS and generation burns the full max_new every time."""
    if not args:
        return f"TOOL {name} {{}}\n"
    return f"TOOL {name} {json.dumps(args, ensure_ascii=False)}\n"


# Tolerant call regex: capture ONLY the function name. JSON is parsed
# separately so a TRUNCATED json (missing closing brace) still yields the name.
_CALL_RE = re.compile(r"TOOL\s+([A-Za-z0-9_]+)", re.DOTALL)


def parse_call(text: str, known_names=None):
    """Parse a model emission into (name, args, well_formed, raw).

    - name:        the function name, or None if no TOOL call found
    - args:        dict (parsed JSON) or {} if no json / unparseable
    - well_formed: True only if a JSON object was present AND parsed cleanly
    - raw:         the original text (for logging)

    Tolerant (smol BUG-003): if the JSON is opened but truncated/unbalanced, we
    STILL recover the function name (best-effort args) and return
    well_formed=False. The router's *routing* decision is scored even when its
    JSON is malformed — but a format slip can never masquerade as a clean call.

    known_names (optional, set of valid registry fns): if the model emits a
    name NOT in the registry, it is HARD-REJECTED -> (None, {}, False, text),
    i.e. treated as "no tool" and never executable. Stops hallucinated fns
    (e.g. `get_me`) from ever becoming a routed call. Training targets always
    use valid names, so this never affects the training contract.
    """
    if text is None:
        return (None, {}, False, "")
    m = _CALL_RE.search(text)
    if not m:
        return (None, {}, False, text)
    name = m.group(1)
    if known_names is not None and name not in known_names:
        return (None, {}, False, text)  # hallucinated fn: reject, never route
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
