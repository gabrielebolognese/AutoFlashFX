"""pipeline/lib/visual/plan_merge.py: the merged visual plan (pipeline/stages/09-plan/schema.json) from the three pass
files of a run: 09a-animations/plan.json (the scenes, the branding, the solution, hook 2), 09b-text/plan.json (the
caption chunks, the card texts the text pass changed, the labels) and 09c-transitions/plan.json (how each scene
leaves). S10 compiles the merged plan; 9c validates it as a whole.

  merge(plan_a, plan_b=None, plan_c=None) -> the merged plan
  python pipeline/lib/visual merge --run-dir DIR [--out merged.json]
"""
from __future__ import annotations

import copy
import json
import os

from visual import common


def apply_overrides(scenes: list[dict], overrides: list[dict]) -> list[str]:
    """9b's card texts written into the component props. A pipe in a lines_json text splits the lines."""
    notes = []
    by_id = {c["id"]: c for s in scenes for c in s.get("components", [])}
    for o in overrides or []:
        c = by_id.get(o.get("component"))
        if not c:
            notes.append(f"override for unknown component {o.get('component')}")
            continue
        prop = o.get("prop") or "title"
        text = str(o.get("text", ""))
        if prop in common.CODE_PROPS:
            parts = [p.strip() for p in text.split("|")]
            if prop == "lines_json" and c["component"] == "headline":
                c["props"][prop] = parts
            elif prop == "items_json":
                c["props"][prop] = parts
            else:
                c["props"][prop] = parts
        else:
            c["props"][prop] = text
    return notes


def derive_cards(scenes: list[dict]) -> list[dict]:
    """The on-screen texts of the plan, one entry per text prop that matters to the reader (titles, chips, kicker,
    keyword), with the zone by role."""
    cards = []
    for s in scenes:
        for c in s.get("components", []):
            p = c.get("props", {})
            role = c.get("role", "support")
            zone = "hero" if role in ("hero", "cta", "set-piece") else "label"
            for prop in ("title", "text", "kicker", "keyword", "label", "unit"):
                v = p.get(prop)
                if isinstance(v, str) and v.strip() and not (prop == "unit" and c["component"] != "stat-number"):
                    cards.append({"scene": s["id"], "component": c["id"], "prop": prop, "text": v, "zone": zone, "words": len(common.words_of(v))})
            if c["component"] == "headline":
                lines = common._lines(p.get("lines_json"))
                text = " ".join(str(ln).replace("*", "") for ln in lines)
                cards.append({"scene": s["id"], "component": c["id"], "prop": "lines_json", "text": text, "zone": "hero", "words": len(common.words_of(text))})
    return cards


def derive_labels(scenes: list[dict], toks: dict) -> list[dict]:
    texts = (toks.get("honesty_labels") or {}).get("texts") or {"mock": "illustrative", "sourced": "real"}
    labels = []
    for s in scenes:
        for c in s.get("components", []):
            h = c.get("props", {}).get("honesty")
            if h in ("mock", "sourced"):
                labels.append({"scene": s["id"], "component": c["id"], "text": texts.get(h, h), "kind": "honesty"})
            if c["component"] == "headline" and c.get("props", {}).get("kicker"):
                labels.append({"scene": s["id"], "component": c["id"], "text": str(c["props"]["kicker"]), "kind": "kicker"})
    return labels


def merge(plan_a: dict, plan_b: dict | None = None, plan_c: dict | None = None, toks: dict | None = None) -> dict:
    toks = toks or common.tokens()
    out = {k: copy.deepcopy(v) for k, v in plan_a.items() if k not in ("pass",)}
    out["plan_version"] = 1
    out.setdefault("style", toks.get("style", "paper-cards"))
    out.setdefault("fps", common.FPS)
    out.setdefault("tracker", {"enabled": bool((toks.get("tracker") or {}).get("enabled", False))})
    scenes = out.get("scenes", [])
    source = "09a-animations"
    if plan_b:
        apply_overrides(scenes, plan_b.get("overrides", []))
        out["captions"] = copy.deepcopy(plan_b.get("captions", []))
        labels = derive_labels(scenes, toks)
        for l in plan_b.get("labels", []):
            if l.get("kind") in ("tag", "kicker") and not any(x.get("scene") == l.get("scene") and x.get("text") == l.get("text") for x in labels):
                labels.append({"scene": l.get("scene"), "text": str(l.get("text", "")), "kind": l.get("kind")})
        out["labels"] = labels
        out["cards"] = derive_cards(scenes)
        source = "09a+09b"
        if plan_b.get("notes"):
            out["notes"] = (out.get("notes", "") + " | text: " + str(plan_b["notes"])).strip(" |")
    else:
        out.setdefault("captions", [])
        out.setdefault("cards", derive_cards(scenes))
        out.setdefault("labels", derive_labels(scenes, toks))
    if plan_c:
        out["transitions"] = copy.deepcopy(plan_c.get("transitions", []))
        source = "09a+09b+09c" if plan_b else "09a+09c"
        if plan_c.get("notes"):
            out["notes"] = (out.get("notes", "") + " | transitions: " + str(plan_c["notes"])).strip(" |")
    else:
        out.setdefault("transitions", [])
    out["source"] = source
    return out


def merge_run(run_dir: str, toks: dict | None = None) -> dict:
    def opt(rel):
        p = os.path.join(run_dir, rel)
        return common.load_json(p) if os.path.isfile(p) else None
    a = opt("09a-animations/plan.json")
    if not a:
        raise common.PlanError("09a-animations/plan.json is missing")
    return merge(a, opt("09b-text/plan.json"), opt("09c-transitions/plan.json"), toks)


def run(args) -> int:
    plan = merge_run(args.run_dir)
    if args.out:
        common.write_json(args.out, plan)
        print(f"merged plan: {len(plan['scenes'])} scenes, {len(plan.get('captions', []))} caption chunks, {len(plan.get('transitions', []))} transitions -> {args.out}")
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=1))
    return 0
