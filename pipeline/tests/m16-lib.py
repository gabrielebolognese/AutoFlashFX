#!/usr/bin/env python
"""m16-lib.py: what each new component of M16 does, measured in the browser harness (test-m16 section 1). Prints `<name> ok` or `<name> FAIL <why>`.

  python pipeline/tests/m16-lib.py

Per component, the behavior its catalog entry promises, at the times its demo props give (the spoken words of the real reels are the
`at` of the props: the harness seeks the component's own timeline, the same one a render uses).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))

from motion import common, demo_assets, harness  # noqa: E402

NINE = ["screenshot-zoom", "video-card", "card-fan", "card-grid", "timeline-scrubber", "cursor", "mock-site-card", "swatch-row", "swatch-card"]
LIB = common.motion_lib_dir()
results: list[tuple[str, bool, str]] = []


def say(name: str, ok: bool, detail="") -> None:
    results.append((name, bool(ok), str(detail)))
    print(name, "ok" if ok else f"FAIL {detail}")


def comp(cid: str) -> dict:
    return common.parse_component(os.path.join(LIB, "compositions", cid + ".html"))


def measure(h, cid: str, props: dict, times: list[float], sels: list[str]) -> list[dict]:
    res = h.measure(comp(cid), props, times, sels)
    if res.get("errors"):
        print(f"  ({cid} page errors: {'; '.join(res['errors'])[:200]})")
    return res["rows"]


def main() -> int:
    common.setup_streams()
    demo_assets.ensure(LIB)
    cat = {c["id"]: c for c in common.load_catalog(LIB)["components"]}
    for cid in NINE:
        c = cat.get(cid)
        say(f"catalog-{cid}", bool(c) and c["status"] == "approved" and c["beat_types"] and c["sound_events"] and os.path.isfile(os.path.join(LIB, c["still"])),
            None if not c else (c["status"], c["beat_types"], c["still"]))
        if c:
            declared = {p["id"] for p in c["props"]}
            say(f"props-{cid}", {"exit", "exit_at"} <= declared and "hold" in declared, sorted(declared))
    with harness.Harness(lib=LIB) as h:
        # screenshot-zoom: the camera travels to each focus box, and a highlight box draws itself there
        props = cat["screenshot-zoom"]["demo"]
        rows = measure(h, "screenshot-zoom", props, [0.4, 1.0, 1.6, 2.6, 3.4], ["#sz-stage", "#sz-box-0", "#sz-box-1"])
        sc = [r["#sz-stage"]["scale"] for r in rows]
        say("zoom-camera-travels", sc[2] > 1.1 and sc[4] > sc[2] + 0.1 and abs(sc[3] - sc[2]) > 0.005, sc)  # focus 1 fills 0.8 of the width of a 0.7 box (1.14), focus 2 of a 0.6 box (1.33)
        say("zoom-highlight-draws", rows[2]["#sz-box-0"]["opacity"] > 0.9 and rows[0]["#sz-box-0"]["opacity"] < 0.05 and rows[4]["#sz-box-1"]["opacity"] > 0.9, [r["#sz-box-0"]["opacity"] for r in rows])
        say("zoom-never-empty", all(r["#sz-stage"]["w"] >= 800 for r in rows), [r["#sz-stage"]["w"] for r in rows])
        # video-card: the clip plays: the frames differ, and a loop restarts it
        comp_v = comp("video-card")
        h.open(comp_v, {"video": "assets/demo/plugin-scroll.mp4", "kind": "frame", "title": ""})
        from PIL import Image, ImageChops
        shots = []
        for t in (1.0, 2.5, 4.5):
            h.page.evaluate(harness.SEEK_JS, {"id": "video-card", "t": t})
            path = os.path.join(LIB, ".harness", f"m16-vc-{t}.png")
            h.page.screenshot(path=path)
            shots.append(Image.open(path).convert("L").resize((270, 480)))
        diffs = [sum(ImageChops.difference(shots[i], shots[i + 1]).getdata()) / (270 * 480) for i in range(2)]
        say("video-plays", min(diffs) > 1.0, diffs)
        state = h.page.evaluate("() => { const v = document.getElementById('vc-video'); return { dur: v.duration, t: v.currentTime, rs: v.readyState, muted: v.muted, paused: v.paused }; }")
        say("video-muted-never-played", state["muted"] and state["paused"] and state["dur"] > 5, state)
        h.page.evaluate(harness.SEEK_JS, {"id": "video-card", "t": 7.0})
        t_loop = h.page.evaluate("() => document.getElementById('vc-video').currentTime")
        say("video-loops", 0.0 <= t_loop <= 1.6, t_loop)
        h.open(comp_v, {"video": "assets/demo/plugin-scroll.mp4", "kind": "frame", "loop": False})
        h.page.evaluate(harness.SEEK_JS, {"id": "video-card", "t": 9.0})
        t_hold = h.page.evaluate("() => document.getElementById('vc-video').currentTime")
        say("video-holds-last-frame", 5.5 <= t_hold <= 6.2, t_hold)
        h.open(comp_v, {"video": "", "image": "assets/demo/plugin-page.png", "kind": "frame"})
        say("video-falls-back-to-still", h.page.evaluate("() => getComputedStyle(document.getElementById('vc-still')).display") == "block")
        # card-fan: the cards leave the deck and fan out, the last ones the furthest
        rows = measure(h, "card-fan", {}, [0.1, 0.5, 1.0, 2.5], ["#cf-card-0", "#cf-card-2", "#cf-card-4"])
        say("fan-opens", abs(rows[2]["#cf-card-0"]["rotation"]) > 12 and abs(rows[2]["#cf-card-4"]["rotation"]) > 12 and rows[2]["#cf-card-0"]["rotation"] < 0 < rows[2]["#cf-card-4"]["rotation"]
            and abs(rows[0]["#cf-card-0"]["rotation"]) < 4, [(r["#cf-card-0"]["rotation"], r["#cf-card-4"]["rotation"]) for r in rows])
        say("fan-glides-on", abs(rows[3]["#cf-card-4"]["rotation"]) > abs(rows[2]["#cf-card-4"]["rotation"]), [r["#cf-card-4"]["rotation"] for r in rows])
        # card-grid: a wave from the top left: the far corner arrives last
        rows = measure(h, "card-grid", {}, [i / 30 for i in range(0, 20)], ["#cg-card-0", "#cg-card-1", "#cg-card-3"])
        first = {s: next((i for i, r in enumerate(rows) if r[s] and r[s]["opacity"] > 0.05), None) for s in ("#cg-card-0", "#cg-card-1", "#cg-card-3")}
        say("grid-wave", first["#cg-card-0"] is not None and first["#cg-card-1"] == first["#cg-card-0"] + 3 and first["#cg-card-3"] == first["#cg-card-0"] + 6, first)
        # timeline-scrubber: the playhead runs at a constant speed from end to end
        rows = measure(h, "timeline-scrubber", {}, [0.8, 1.8, 2.8, 3.8], ["#ts-head"])
        xs = [r["#ts-head"]["cx"] for r in rows]
        steps = [b - a for a, b in zip(xs, xs[1:])]
        say("scrubber-runs-linearly", all(s > 100 for s in steps) and max(steps) - min(steps) < 25, xs)
        # cursor: it arrives at each point on its second and presses on the click points
        pts = [{"x": 300, "y": 900, "at": 0}, {"x": 600, "y": 1100, "at": 1.2, "click": True}, {"x": 400, "y": 700, "at": 2.4}]
        rows = measure(h, "cursor", {"points_json": pts, "hold": "calm"}, [0.5, 1.2, 1.27, 1.45, 2.4], ["#cu", "#cu-arrow", "#cu-ripple-0"])
        say("cursor-arrives", abs(rows[1]["#cu-arrow"]["x"] - 600) < 14 and abs(rows[1]["#cu-arrow"]["y"] - 1100) < 14, [(r["#cu-arrow"]["x"], r["#cu-arrow"]["y"]) for r in rows])
        say("cursor-presses-and-rings", rows[2]["#cu-arrow"]["scale"] < 0.97 and rows[2]["#cu-ripple-0"]["opacity"] > 0.2, [(r["#cu-arrow"]["scale"], r["#cu-ripple-0"]["opacity"]) for r in rows])
        # mock-site-card: the headline, the button and the cards build, and the page scrolls on
        rows = measure(h, "mock-site-card", {"cta_at": 0.9}, [0.3, 1.5, 3.0], ["#ms-cta", "#ms-page", "#ms-headline"])
        say("mock-site-builds", rows[0]["#ms-cta"]["opacity"] < 0.05 and rows[1]["#ms-cta"]["opacity"] > 0.9, [r["#ms-cta"]["opacity"] for r in rows])
        say("mock-site-scrolls", rows[2]["#ms-page"]["y"] < rows[1]["#ms-page"]["y"] - 20, [r["#ms-page"]["y"] for r in rows])
        # swatch-row: each swatch fills on its second, in its own color
        props = {"colors_json": [{"color": "#DC6532", "at": 0.8}, {"color": "#1C110F", "at": 1.5}, {"color": "#289C5C", "at": 2.2}]}
        rows = measure(h, "swatch-row", props, [0.6, 1.2, 1.9, 2.8], ["#sr-fill-0", "#sr-fill-1", "#sr-fill-2"])
        say("swatches-fill-on-their-words", rows[0]["#sr-fill-0"]["h"] < 30 and rows[1]["#sr-fill-0"]["h"] > 380 and rows[1]["#sr-fill-1"]["h"] < 30 and rows[2]["#sr-fill-1"]["h"] > 380 and rows[3]["#sr-fill-2"]["h"] > 380,
            [(r["#sr-fill-0"]["h"], r["#sr-fill-1"]["h"], r["#sr-fill-2"]["h"]) for r in rows])
        # swatch-card: the color fills, the hex types in
        rows = measure(h, "swatch-card", {"color": "#DC6532", "name": "Burnt orange"}, [0.3, 1.5, 2.5], ["#sc-fill", "#sc-hex"])
        say("swatch-card-fills-and-types", rows[0]["#sc-fill"]["h"] < 520 and rows[2]["#sc-fill"]["h"] > 500 and rows[0]["#sc-hex"]["text"] == "" and rows[2]["#sc-hex"]["text"] == "#DC6532", [(r["#sc-fill"]["h"], r["#sc-hex"]["text"]) for r in rows])
    return 0 if all(ok for _n, ok, _d in results) else 1


if __name__ == "__main__":
    sys.exit(main())
