#!/usr/bin/env python3
"""registry — load the function registry (the router's knowledge).

The registry is the single source of truth for which functions the router
can call. Training data is SYNTHESIZED from the registry's ``examples``. A new
function added to functions/registry.json becomes routable with zero model
code changes — capability scales by adding functions, not parameters.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REG_PATH = os.path.join(HERE, "registry.json")


def load(path: str = REG_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def functions(path: str = REG_PATH) -> list[dict]:
    reg = load(path)
    return reg.get("functions", [])


def by_name(name: str, path: str = REG_PATH) -> dict | None:
    for f in functions(path):
        if f["name"] == name:
            return f
    return None


def names(path: str = REG_PATH) -> list[str]:
    return [f["name"] for f in functions(path)]


if __name__ == "__main__":
    fs = functions()
    print(f"{len(fs)} functions registered:")
    for f in fs:
        tag = "[no-tool]" if f.get("no_tool") else ""
        print(f"  - {f['name']:14s} ({f.get('category','?'):10s}) {tag}")
