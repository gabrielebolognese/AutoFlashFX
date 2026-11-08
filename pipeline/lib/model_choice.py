#!/usr/bin/env python
"""Which model a call uses: config models.<role>, the idea's [important] label and the visual director's rounds.

The label (BUILD_SPEC.md 2.1, DECISIONS.md 323): an idea whose text starts or ends with [important] (any case) is
marked important. The label is not part of the idea: it is stripped from the text the stages read and from the id,
and the run's state.json keeps it as idea.important.

The models (DECISIONS.md 324):
  - a role's model and effort are config models.<role>.model and .effort;
  - on an idea marked important, models.<role>.important (model, effort) replaces them when the role has one
    (the escalation roles do: that is where fable lives);
  - on every other run, and on a call outside any run, a fable model never runs: models.limit_fallback (opus)
    stands in, with the role's effort. Fable is for the ideas marked important only.

The visual director (DECISIONS.md 325): the first plan of a pass is the design (models.visual_director, opus);
a plan made again after a failed review round is fine tuning (models.visual_director_fix, sonnet); from
caps.review_rounds_opus failed rounds on, the escalated director plans it (models.visual_director_escalation:
opus, or fable on an idea marked important).

Usage (paths may be C:/... or /c/...):
  model_choice.py resolve ROLE --config config.json [--run-dir DIR]   prints "model effort"; exit 1 for an unknown role
  model_choice.py director-role ROUND --config config.json            prints the visual director's role for that
                                                                      many failed review rounds
  model_choice.py important --run-dir DIR                             prints true or false
  model_choice.py label                                               idea text on stdin: prints {"raw", "important"}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

LABEL = "important"
_LEAD = re.compile(r"^\s*\[\s*important\s*\]\s*", re.IGNORECASE)
_TRAIL = re.compile(r"\s*\[\s*important\s*\]\s*$", re.IGNORECASE)


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    if m and os.name == "nt":
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return path


def split_label(raw: str) -> tuple[str, bool]:
    """(the idea text without the label, whether it carried [important] at its start or its end)."""
    text = raw or ""
    important = False
    for rx in (_LEAD, _TRAIL):
        new = rx.sub("", text, count=1)
        if new != text:
            important, text = True, new
    return text.strip(), important


def load_config(path: str) -> dict:
    with open(winpath(path), encoding="utf-8-sig") as f:
        return json.load(f)


def is_important(run_dir: str | None) -> bool:
    """True when the run's state.json says the idea is marked important; False for no run or no state."""
    if not run_dir:
        return False
    try:
        with open(os.path.join(winpath(run_dir), "state.json"), encoding="utf-8-sig") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return False
    return bool(((state or {}).get("idea") or {}).get("important"))


def is_fable(model: str) -> bool:
    return "fable" in str(model or "").lower()


def short(model: str) -> str:
    """claude-sonnet-5-5 -> sonnet; opus -> opus."""
    m = str(model or "")
    parts = m.split("-")
    return parts[1] if m.startswith("claude-") and len(parts) > 1 else m


def resolve(config: dict, role: str, important: bool) -> tuple[str, str]:
    """(model, effort) of a role on a run; KeyError when the role has no model."""
    models = config.get("models") or {}
    spec = models.get(role)
    if not isinstance(spec, dict) or not spec.get("model"):
        raise KeyError(role)
    model, effort = str(spec["model"]), str(spec.get("effort") or "medium")
    over = spec.get("important")
    if important and isinstance(over, dict):
        model = str(over.get("model") or model)
        effort = str(over.get("effort") or effort)
    if is_fable(model) and not important:
        model = str((models.get("limit_fallback") or {}).get("model") or "opus")
        if is_fable(model):
            model = "opus"
    return model, effort


def director_role(config: dict, review_round: int) -> str:
    """The visual director's role after that many failed review rounds (0: the first plan)."""
    models = config.get("models") or {}
    cap = int((config.get("caps") or {}).get("review_rounds_opus", 3))
    if review_round >= cap and "visual_director_escalation" in models:
        return "visual_director_escalation"
    if review_round >= 1 and "visual_director_fix" in models:
        return "visual_director_fix"
    return "visual_director"


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(newline="\n")
    ap = argparse.ArgumentParser(prog="model_choice.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("role")
    r.add_argument("--config", required=True)
    r.add_argument("--run-dir", default="")
    d = sub.add_parser("director-role")
    d.add_argument("round", type=int)
    d.add_argument("--config", required=True)
    i = sub.add_parser("important")
    i.add_argument("--run-dir", default="")
    sub.add_parser("label")
    a = ap.parse_args(argv)
    if a.cmd == "resolve":
        try:
            model, effort = resolve(load_config(a.config), a.role, is_important(a.run_dir))
        except KeyError:
            print(f"model_choice.py: no model for role '{a.role}' in config.json", file=sys.stderr)
            return 1
        print(f"{model} {effort}")
    elif a.cmd == "director-role":
        print(director_role(load_config(a.config), a.round))
    elif a.cmd == "important":
        print("true" if is_important(a.run_dir) else "false")
    else:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        text, important = split_label(raw)
        print(json.dumps({"raw": text, "important": important}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
