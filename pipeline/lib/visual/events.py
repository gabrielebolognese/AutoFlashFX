"""pipeline/lib/visual/events.py: 10-build/events.json, every sound event of the built visuals in absolute ms
(BUILD_SPEC.md S10). The components register what they do and when on their mount (window.__pcEvents, local
seconds: paper-cards.js PC.event), so the events are read from the real component files mounted with the plan's
resolved props in the Playwright harness (pipeline/lib/motion/harness.py), not computed from the catalog's frame
formulas: what the timeline does is what the file reports. Each event's absolute time is the host's data-start plus
the local time; the scene changes come from the plan's transitions. With verify, every event that names an element
is checked on screen: the harness seeks one frame before and one frame after the event and the element's state
(opacity, position, scale, rotation or text) must differ. `npx hyperframes timeline --json` cross-checks that every
host starts where the plan says.

  events.json: {written_by, duration_ms, fps, composition, counts, verified: {checked, changed, failed}, timeline_check,
                events: [{ms, frame, type, cue, component, instance, scene, beat, el, scene_change, transition_ms, verified}]}
  python pipeline/lib/visual events --project DIR --plan plan.json --out events.json [--no-verify]
"""
from __future__ import annotations

import json
import os
import subprocess

from motion import common as mcommon, harness
from visual import common

FRAME_S = 1.0 / common.FPS
# the events that start a visible change (verified on screen); a landing, a peak or an end of a move is the moment a
# change stops and shows no difference between the frame before and the frame after
VERIFY_TYPES = {"enter", "pop", "exit", "typing", "count_start", "strike", "check", "fill", "send", "row", "card", "bar", "gauge", "word",
                "slide", "lockup", "camera", "line"}
EXIT_TYPES = {"fade-blur", "fall", "push", "cut"}  # PC.exit registers the exit under its move's name (the extra `type` key wins)
STATE_KEYS = ("opacity", "x", "y", "w", "h", "scale", "rotation", "text")


def cue_map(cat_by_id: dict) -> dict:
    """{(component id, event name): cue} from the catalog's declared sound events."""
    out = {}
    for cid, c in cat_by_id.items():
        for e in c.get("sound_events", []):
            key = (cid, e.get("event"))
            if key not in out:
                out[key] = e.get("cue")
    return out


def changed(a: dict | None, b: dict | None) -> bool:
    if a is None and b is None:
        return False
    if (a is None) != (b is None):
        return True
    for k in STATE_KEYS:
        va, vb = a.get(k), b.get(k)
        if k == "text":
            if (va or "") != (vb or ""):
                return True
        elif k in ("opacity",):
            if abs(float(va or 0) - float(vb or 0)) > 0.01:  # a cubic ease-in moves 0.016 in its first of 4 frames
                return True
        elif k == "scale":
            if abs(float(va or 1) - float(vb or 1)) > 0.002:
                return True
        elif k == "rotation":
            if abs(float(va or 0) - float(vb or 0)) > 0.1:
                return True
        else:
            if abs(float(va or 0) - float(vb or 0)) > 0.5:
                return True
    return False


def canvas_changed(h: harness.Harness, comp_id: str, t_before: float, t_after: float, box: dict) -> bool:
    """A canvas draws from the hf-seek time (hero-3d): compare its pixels one frame before and after the event."""
    from PIL import Image, ImageChops
    clip = {"x": max(0, box["x"]), "y": max(0, box["y"]), "width": max(1, min(1080 - box["x"], box["w"])), "height": max(1, min(1920 - box["y"], box["h"]))}
    shots = []
    paths = []
    for t in (t_before, t_after):
        h.page.evaluate(harness.SEEK_JS, {"id": comp_id, "t": t})
        h.page.wait_for_timeout(40)
        png = os.path.join(h.lib, ".harness", f"ev-{round(t * 1000)}.png")
        h.page.screenshot(path=png, clip=clip)
        shots.append(Image.open(png).convert("L"))
        paths.append(png)
    diff = ImageChops.difference(shots[0], shots[1])
    moved = sum(1 for v in diff.getdata() if v > 16)  # pixels that really changed (a small object at frame 1 is a few hundred)
    for im in shots:
        im.close()
    for png in paths:
        try:
            os.remove(png)
        except OSError:
            pass
    return moved > 30


def timeline_check(project: str, instances: list[dict]) -> dict:
    """Every host of the project starts where the plan says (npx hyperframes timeline --json)."""
    npx = "npx.cmd" if os.name == "nt" else "npx"
    try:
        proc = subprocess.run([npx, "--prefix", os.environ.get("REELS_NODE_PREFIX") or common.REPO, "hyperframes", "timeline", "--json"], cwd=project, capture_output=True, text=True, timeout=300,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": None, "error": str(exc), "mismatches": []}
    raw = proc.stdout or ""
    i = raw.find("{")
    try:
        d = json.loads(raw[i:]) if i >= 0 else {}
    except ValueError:
        return {"ok": None, "error": "no JSON from hyperframes timeline", "mismatches": []}
    rows = {}
    for track in (d.get("timeline") or {}).get("tracks", []):
        for r in track.get("rows", []):
            rows[r.get("id")] = r
    mismatches = []
    for inst in instances:
        r = rows.get(inst["instance"])
        if not r:
            mismatches.append(f"{inst['instance']}: no clip in the project's timeline")
            continue
        if abs(float(r.get("absStart", r.get("start", 0))) - inst["start_ms"] / 1000) > 0.002:
            mismatches.append(f"{inst['instance']}: clip starts at {r.get('absStart')} s, the plan says {inst['start_ms'] / 1000:.3f}")
    return {"ok": not mismatches, "clips": len(rows), "mismatches": mismatches}


def build_events(project: str, plan: dict, verify: bool = True, gpu: str = "auto") -> dict:
    project = common.mixed(project)
    inst_path = os.path.join(project, "instances.json")
    instances = common.load_json(inst_path)["instances"] if os.path.isfile(inst_path) else []
    cat = common.catalog()
    by_id = common.catalog_by_id(cat)
    cues = cue_map(by_id)
    scene_of = {}
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            scene_of[c["id"]] = (s["id"], s["beat"])
    events: list[dict] = []
    checked = changed_n = 0
    failed: list[str] = []
    errors: list[str] = []
    if instances:
        with harness.Harness(lib=project, gpu=gpu) as h:
            for inst in instances:
                comp_file = os.path.join(project, "compositions", inst["component"] + ".html")
                if not os.path.isfile(comp_file):
                    errors.append(f"{inst['instance']}: {comp_file} is missing")
                    continue
                comp = mcommon.parse_component(comp_file)
                # the shim registers the timeline under the component's id (the file's data-composition-id)
                props = dict(inst.get("props", {}))
                if inst["component"] in ("hero-3d", "icon-3d"):
                    props["clip_start"] = 0  # the harness seeks local times; in the reel the host's data-start is added by the runtime
                res = h.measure(comp, props, [], [])
                local = []
                for e in res.get("events", []):
                    e = dict(e)
                    if e.get("type") in EXIT_TYPES:
                        e["transition_type"] = e["type"]
                        e["type"] = "exit"
                    local.append(e)
                sid, beat = scene_of.get(inst["instance"], ("", ""))
                rows_by_el: dict[str, list[float]] = {}
                for e in local:
                    if e.get("el") and e.get("type") in VERIFY_TYPES:
                        rows_by_el.setdefault(e["el"], []).append(float(e["t"]))
                measured: dict = {}
                if verify and rows_by_el:
                    times = sorted({t for ts in rows_by_el.values() for t0 in ts for t in (max(0.0, t0 - FRAME_S), t0 + FRAME_S, t0 + 2 * FRAME_S)})
                    sels = ["#" + el for el in rows_by_el]
                    m = h.page.evaluate(harness.MEASURE_JS, {"id": comp["id"], "times": times, "selectors": sels})
                    for row in m.get("rows", []):
                        measured[round(row["t"], 4)] = row
                for e in local:
                    ms = int(round(inst["start_ms"] + float(e["t"]) * 1000))
                    ev = {"ms": ms, "frame": int(round(ms * common.FPS / 1000)), "type": e.get("type"), "cue": cues.get((inst["component"], e.get("type"))),
                          "component": inst["component"], "instance": inst["instance"], "scene": sid, "beat": beat, "el": e.get("el"),
                          "scene_change": False, "transition_ms": 0}
                    for k in ("end", "chars", "move", "kind", "chunk", "em", "width", "transition_type"):
                        if k in e:
                            ev[k] = e[k] if k != "end" else int(round(inst["start_ms"] + float(e["end"]) * 1000))
                    if e.get("type") == "exit":
                        ev["cue"] = "transition"
                    if verify and e.get("el") and e.get("type") in VERIFY_TYPES:
                        t0 = float(e["t"])
                        before = measured.get(round(max(0.0, t0 - FRAME_S), 4), {}).get("#" + e["el"])
                        after = measured.get(round(t0 + FRAME_S, 4), {}).get("#" + e["el"])
                        if e.get("type") == "exit" and before and float(before.get("opacity") or 0) == 0:
                            continue  # an element that was never shown (an empty label) has no exit to see
                        ok = changed(before, after)
                        if not ok and e.get("type") == "typing":  # 2 frames per character: the first letter shows on the second frame
                            ok = changed(before, measured.get(round(t0 + 2 * FRAME_S, 4), {}).get("#" + e["el"]))
                        if not ok and before and str(before.get("tag", "")).upper() == "CANVAS":
                            ok = canvas_changed(h, comp["id"], max(0.0, t0 - FRAME_S), t0 + FRAME_S, before)
                        ev["verified"] = ok
                        checked += 1
                        if ok:
                            changed_n += 1
                        else:
                            failed.append(f"{inst['instance']}:{e.get('type')}@{ms}")
                    events.append(ev)
                if res.get("errors"):
                    errors += [f"{inst['instance']}: {x}" for x in res["errors"] if "Failed to load resource" not in x][:3]
    # the scene changes, from the plan's transitions: the moment the next scene begins; the exit started transition_ms earlier
    scenes = {s["id"]: s for s in plan.get("scenes", [])}
    for t in plan.get("transitions", []):
        nxt = scenes.get(t.get("to"))
        prev = scenes.get(t.get("from"))
        if not nxt or not prev:
            continue
        ms = int(nxt["start_ms"])
        leaving = [e for e in events if e["scene"] == prev["id"] and e["type"] == "exit"]
        ver = None
        if verify:
            ver = all(e.get("verified", False) for e in leaving) if leaving else (t.get("type") == "cut")
        events.append({"ms": ms, "frame": int(round(ms * common.FPS / 1000)), "type": "scene_change", "cue": "transition", "component": "scene", "instance": None,
                       "scene": nxt["id"], "beat": nxt["beat"], "from_scene": prev["id"], "el": None, "scene_change": True, "transition_ms": int(t.get("duration_ms", 0)),
                       "transition_type": t.get("type"), "next_beat_type": nxt.get("beat_type"), "verified": ver})
    events.sort(key=lambda e: (e["ms"], 0 if e["scene_change"] else 1, str(e["instance"])))
    counts: dict = {}
    for e in events:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    out = {"written_by": "10-build", "duration_ms": int(plan["duration_ms"]), "fps": common.FPS, "composition": "project/index.html",
           "counts": counts, "verified": {"checked": checked, "changed": changed_n, "failed": failed} if verify else None,
           "harness_errors": errors[:20], "timeline_check": timeline_check(project, instances), "events": events}
    return out


def run(args) -> int:
    plan = common.load_json(args.plan)
    ev = build_events(args.project, plan, verify=not args.no_verify, gpu=args.gpu)
    common.write_json(args.out, ev)
    v = ev.get("verified") or {}
    print(f"events.json: {len(ev['events'])} events, {ev['counts'].get('scene_change', 0)} scene changes" + (f", verified {v.get('changed')}/{v.get('checked')}" if v else "") + f" -> {args.out}")
    if v.get("failed"):
        print("not verified: " + ", ".join(v["failed"][:10]))
    tc = ev.get("timeline_check") or {}
    if tc.get("mismatches"):
        print("timeline mismatches: " + "; ".join(tc["mismatches"][:5]))
    return 0 if not v.get("failed") and not tc.get("mismatches") else 1
