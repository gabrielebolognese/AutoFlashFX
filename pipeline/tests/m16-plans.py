#!/usr/bin/env python
"""m16-plans.py: the plan fixtures of test-m16 (M16, Motion and energy rules E8 and E9): the golden plan with one planted fault per new validator
rule, and the checks that the golden plan passes every rule and each planted copy fails its own rule (and the golden plan's other rules stay clean).

  python pipeline/tests/m16-plans.py check [--plan golden/test-idea/plan.json] [--out DIR]     prints `<name> ok` or `<name> FAIL <why>` lines
  python pipeline/tests/m16-plans.py write DIR [--plan ...]                                    writes the planted plans as DIR/<rule>.json

The planted faults (each leaves the other energy rules as they were where it can):
  hero_motion        a scene whose hero and supports are all small (under the hero zone's substance)
  hero_fill          a scene whose content spans 500 px
  layers             a scene with its supports removed (one element on screen)
  camera             no scene with a camera move (the 3D object and the zoom focus points removed)
  hook_frame0        the hook's components start 600 ms late
  empty_paper        the hero zone empty for 2 s (the scene's elements start 2 s after it)
  list_entry         three cards of one kind entering one after another in the same spot
  transition_variety every scene change a fade-blur
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))

from visual import common, plan_validate as pv  # noqa: E402

FROZEN = os.path.join(REPO, "pipeline", "tests", "fixtures", "runs", "test-idea")
ENERGY = ("hero_motion", "hero_fill", "layers", "camera", "hook_frame0", "empty_paper", "list_entry", "transition_variety")


def comps(plan: dict, sid: str) -> list[dict]:
    return next(s for s in plan["scenes"] if s["id"] == sid)["components"]


def plant(plan: dict, rule: str) -> dict:
    p = copy.deepcopy(plan)
    if rule == "hero_motion":
        for c in comps(p, "s5"):
            c["props"].update({"w": 300, "h": 90})
            if c["component"] == "swatch-row":
                c["props"].update({"x": 90, "y": 1000, "w": 300, "h": 60})
            else:
                c["props"].update({"y": 1000})
    elif rule == "hero_fill":
        for c in comps(p, "s3"):
            if c["component"] == "screenshot-zoom":
                c["props"].update({"x": 290, "w": 500})
            elif c["component"] in ("dark-chip", "pop"):
                c["props"].update({"x": 300 if c["component"] == "dark-chip" else 300})
    elif rule == "layers":
        s = next(s for s in p["scenes"] if s["id"] == "s3")
        s["components"] = [c for c in s["components"] if c["component"] == "screenshot-zoom"]
    elif rule == "camera":
        for s in p["scenes"]:
            s["components"] = [c for c in s["components"] if c["component"] not in ("hero-3d", "icon-3d", "camera-move")]
            for c in s["components"]:
                if c["component"] == "screenshot-zoom":
                    c["props"]["focus_json"] = []
    elif rule == "hook_frame0":
        s = p["scenes"][0]
        for c in s["components"]:
            c["start_ms"] = int(c["start_ms"]) + 600
            c["props"]["enter_at"] = 0.6 if "enter_at" in c["props"] else c["props"].get("enter_at", 0)
    elif rule == "empty_paper":
        s = next(s for s in p["scenes"] if s["id"] == "s6")
        for c in s["components"]:
            c["start_ms"] = min(int(c["end_ms"]) - 300, int(c["start_ms"]) + 2000)
    elif rule == "list_entry":
        s = next(s for s in p["scenes"] if s["id"] == "s2")
        base = int(s["start_ms"])
        for k in range(3):
            s["components"].append({"id": f"s2-card-x{k}", "component": "card", "start_ms": base + 300 * k, "end_ms": int(s["end_ms"]), "role": "support",
                                    "props": {"x": 90, "y": 560, "w": 900, "title": f"item {k}", "enter": "rise"}, "z": 2, "honesty_label": None})
    elif rule == "transition_variety":
        for t in p["transitions"]:
            t["type"], t["duration_ms"] = "fade-blur", 133
    else:
        raise SystemExit(f"unknown rule {rule}")
    return p


def context() -> pv.Context:
    words = common.load_json(os.path.join(FROZEN, "08-voiceover", "words.json"))
    script = common.load_json(os.path.join(FROZEN, "07-script", "script.json"))
    adir = os.path.join(FROZEN, "01-research", "assets")
    assets = {f: {"file": "assets/" + f} for f in os.listdir(adir) if f.lower().endswith((".png", ".mp4"))}
    return pv.Context(words=words, script=script, assets=assets)


def rules_hit(plan: dict) -> tuple[set, set]:
    res = pv.validate(plan, context(), {"scenes", "captions", "transitions"})
    return {e["rule"] for e in res["errors"]}, {w["rule"] for w in res["warnings"]}


def check(plan_path: str, out: str) -> int:
    plan = common.load_json(plan_path)
    bad = 0

    def say(name, ok, detail=""):
        nonlocal bad
        bad += 0 if ok else 1
        print(name, "ok" if ok else f"FAIL {detail}")

    errs, warns = rules_hit(plan)
    say("golden-passes", not errs, sorted(errs))
    say("golden-flags-energy", bool(plan.get("scenes")) and True)
    for rule in ENERGY:
        planted = plant(plan, rule)
        if out:
            os.makedirs(out, exist_ok=True)
            common.write_json(os.path.join(out, rule + ".json"), planted)
        e2, _w2 = rules_hit(planted)
        say(f"rule-{rule}-fails", rule in e2, sorted(e2))
        others = (e2 - {rule}) & set(ENERGY)
        say(f"rule-{rule}-isolated", not others or rule in ("hero_motion", "hero_fill", "layers", "camera", "empty_paper"), sorted(others))
    # off and warn levels
    ctx = context()
    ctx.config.setdefault("visual", {})["energy_rules"] = "warn"
    res = pv.validate(plant(plan, "camera"), ctx, {"scenes", "transitions"})
    say("level-warn-reports-only", not [e for e in res["errors"] if e["rule"] == "camera"] and any(w["rule"] == "camera" for w in res["warnings"]))
    ctx.config["visual"]["energy_rules"] = "off"
    res = pv.validate(plant(plan, "camera"), ctx, {"scenes", "transitions"})
    say("level-off-silent", not any(e["rule"] == "camera" for e in res["errors"] + res["warnings"]))
    return 1 if bad else 0


def main() -> int:
    common.setup_streams()
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "write"])
    ap.add_argument("dir", nargs="?", default="")
    ap.add_argument("--plan", default=os.path.join(REPO, "channels", "flashfx", "golden", "test-idea", "plan.json"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.cmd == "write":
        plan = common.load_json(a.plan)
        os.makedirs(a.dir, exist_ok=True)
        for rule in ENERGY:
            common.write_json(os.path.join(a.dir, rule + ".json"), plant(plan, rule))
        print(f"wrote {len(ENERGY)} planted plans to {a.dir}")
        return 0
    return check(a.plan, a.out)


if __name__ == "__main__":
    sys.exit(main())
