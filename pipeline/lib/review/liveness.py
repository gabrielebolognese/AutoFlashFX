"""pipeline/lib/review/liveness.py: two mechanical checks of the Motion and energy rules (BUILD_SPEC.md S12 mechanical checks, E1 and E5, M16).

  static_check: no element is static for more than 0.5 s. Every top-level element of every component instance (the children of its #root,
      each one a thing that lives through the four phases of E1) is measured twice, half a second apart, at several moments of its life
      after the main animation has landed and before its exit, in the browser harness with the composition's own timeline (the transforms
      are read from the composition, not guessed from pixels). Between the two samples it must have moved by at least the calm hold
      speed's share of half a second (frame-match's own thresholds: motion/framematch.py calm_thresholds and window_moved): its center,
      its parallax angles, its scale, its opacity, its size or its text. An element that is hidden or leaving is not judged.
  edge_check: the edge layer is present (E5): the paper canvas holds at least review.min_edge_elements elements of #paper-edges, partly
      outside the frame, and no text.

Both return issues for review/mechanical.py in its own shape: rc.issue(tag "animation", kind, text, scene, instance, ms).
"""
from __future__ import annotations

import os

from motion import common as mcommon, framematch, harness
from review import common as rc

HALF_S = 0.5
VISIBLE = 0.3
LIST_JS = "() => [...document.querySelectorAll('#root > *')].filter(e => e.id && !e.hasAttribute('data-layout-ignore')).map(e => '#' + e.id)"


def sample_pairs(start_ms: int, end_ms: int, every_s: float = 2.0, settle_s: float = 0.9, leave_s: float = 0.45) -> list[tuple[float, float]]:
    """(t, t + 0.5 s) local times inside the instance's life: after the settle time, before the leave time, every `every_s`."""
    life = (end_ms - start_ms) / 1000.0
    t = settle_s
    out = []
    while t + HALF_S <= life - leave_s + 1e-9:
        out.append((round(t, 3), round(t + HALF_S, 3)))
        t += every_s
    if not out and life - leave_s - HALF_S >= 0.4:
        out.append((round(life - leave_s - HALF_S, 3), round(life - leave_s, 3)))
    return out


def static_check(ctx: rc.Ctx, hosts: list[dict], h: harness.Harness) -> dict:
    thr = framematch.calm_thresholds(ctx.toks)
    issues: list[dict] = []
    checked = 0
    for host in hosts:
        if host.get("no_timeline") or host.get("captions") or host["component"] in ("paper-canvas", "camera-move", "exit-move"):
            continue
        pairs = sample_pairs(int(host["start_ms"]), int(host["end_ms"]))
        if not pairs:
            continue
        comp_file = os.path.join(ctx.project, host["src"])
        if not os.path.isfile(comp_file):
            continue
        comp = mcommon.parse_component(comp_file)
        props = dict(host["props"])
        if host["component"] in mcommon.CLIP_START_COMPONENTS:
            props["clip_start"] = 0
        h.open(comp, props)
        sels = h.page.evaluate(LIST_JS)
        if not sels:
            continue
        times = sorted({t for pair in pairs for t in pair})
        res = h.page.evaluate(harness.MEASURE_JS, {"id": comp["id"], "times": times, "selectors": sels})
        by_t = {round(r["t"], 3): r for r in res.get("rows", [])}
        for sel in sels:
            worst = None
            for a, b in pairs:
                ma, mb = (by_t.get(a) or {}).get(sel), (by_t.get(b) or {}).get(sel)
                if not (framematch.visible_at(ma) and framematch.visible_at(mb)) or ma["opacity"] < VISIBLE or mb["opacity"] < VISIBLE:
                    continue
                checked += 1
                if not framematch.window_moved(ma, mb, thr):
                    worst = (a, b)
                    break
            if worst:
                ms = int(host["start_ms"] + worst[0] * 1000)
                issues.append(rc.issue("animation", "element_static",
                                       f"{host['id']} ({host['component']}) element {sel} does not move between {rc.fmt_ms(ms)} and {rc.fmt_ms(ms + 500)}: every element keeps moving at least at the calm hold speed (E1): give the component a hold level and no hold of kind none",
                                       host["scene"], host["id"], ms))
    return {"issues": issues, "checked": checked}


def edge_check(ctx: rc.Ctx, hosts: list[dict], h: harness.Harness) -> dict:
    need = int(ctx.c("review.min_edge_elements", 4))
    canvases = [x for x in hosts if x["component"] == "paper-canvas"]
    if not canvases:
        return {"issues": [rc.issue("animation", "edge_layer", "the composition has no paper canvas, so no edge layer (E5: the frame is a window, not a box)")], "edges": 0, "outside": 0}
    host = canvases[0]
    comp = mcommon.parse_component(os.path.join(ctx.project, host["src"]))
    h.open(comp, dict(host["props"]))
    h.page.evaluate(harness.SEEK_JS, {"id": comp["id"], "t": 1.0})
    info = h.page.evaluate("""() => {
      const els = [...document.querySelectorAll('#paper-edges > *')];
      const rects = els.map(e => e.getBoundingClientRect());
      return { n: els.length, outside: rects.filter(r => r.left < 0 || r.right > 1080).length, withText: els.filter(e => (e.textContent || '').trim().length > 0).length };
    }""")
    issues = []
    if info["n"] < need or info["outside"] < max(1, need // 2):
        issues.append(rc.issue("animation", "edge_layer", f"the edge layer is missing or too thin: {info['n']} elements of #paper-edges, {info['outside']} of them partly outside the frame (at least {need} and {max(1, need // 2)} are wanted, E5): "
                               f"the paper canvas needs its edges prop at its default (6)"))
    if info["withText"]:
        issues.append(rc.issue("animation", "edge_layer", f"{info['withText']} elements of the edge layer carry text; the edge layer holds no text (E5)"))
    return {"issues": issues, "edges": info["n"], "outside": info["outside"]}
