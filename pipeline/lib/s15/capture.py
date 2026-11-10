"""capture.py: the layers of the final composition, frame by frame (BUILD_SPEC.md S15 step 2, M21).

Every host of the composition (timeline.json: a layer with a selector and a component) is opened alone in the browser harness
S12's mechanical checks use (pipeline/lib/motion/harness.py, Playwright and Chromium), the way the review opens it, and its GSAP
timeline is sought frame by frame. Nothing is inserted into the page. For every element with `data-ed-layer` (an element inside
another annotated one is its child layer; an unannotated component is one layer, its root) the capture records per frame:
  - the border quad from the DevTools protocol (DOM.getBoxModel: it includes every CSS transform on the element and its ancestors),
  - the product of the computed opacities from the element up, and whether it is displayed,
  - a signature of its look (computed colors, borders, radii, shadows, filters, clip path, box size, text, svg markup),
and once per visible run its description: the kind, the text with its font and style, the lines the browser broke it into, the
background, border, radius, shadow, image source. The result is 15-project/layers.json:
  {"fps", "width", "height", "hosts": [{"id", "component", "start", "end", "layers": [layer...]}]}
  layer: {"id", "name", "kind", "parent", "tag", "annotated", "w", "h", "runs": [{"start", "end", "pose": [[cx, cy, sx, sy, rot, skew, err]...],
          "opacity": [...], "sig": [...], "info": {...}, "info_frame": f}]}
(frames are timeline frames; a run is a stretch of consecutive visible frames).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from motion import common as mcommon  # noqa: E402
from motion import harness  # noqa: E402

from . import geom  # noqa: E402

VISIBLE = 0.004

FRAME_JS = """
(args) => {
  const out = [];
  const nodes = window.__s15els;
  for (let i = 0; i < nodes.length; i++) {
    const el = nodes[i];
    let op = 1, shown = true, node = el;
    while (node && node !== document.documentElement) {
      const cs = getComputedStyle(node);
      if (cs.display === "none" || cs.visibility === "hidden") { if (node === el || cs.display === "none") shown = false; }
      op *= parseFloat(cs.opacity);
      node = node.parentElement;
    }
    const cs = getComputedStyle(el);
    const tag = el.tagName.toLowerCase();
    let own = "";
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.nodeValue;
    const parts = [cs.color, cs.backgroundColor, cs.backgroundImage, cs.borderTopWidth, cs.borderTopColor, cs.borderRightWidth, cs.borderBottomWidth,
      cs.borderLeftWidth, cs.borderTopLeftRadius, cs.borderTopRightRadius, cs.borderBottomRightRadius, cs.borderBottomLeftRadius, cs.boxShadow,
      cs.filter, cs.clipPath, cs.textShadow, cs.fontSize, cs.letterSpacing, el.offsetWidth, el.offsetHeight, own.trim(), cs.webkitTextStroke];
    if (tag === "svg" || tag === "canvas" || el.querySelector && el.querySelector("svg")) parts.push(el.innerHTML ? el.innerHTML.length : 0);
    if (tag === "svg") parts.push(el.outerHTML);
    if (tag === "img") parts.push(el.currentSrc);
    out.push([shown ? 1 : 0, Math.round(op * 10000) / 10000, parts.join("|")]);
  }
  return out;
}
"""

DESCRIBE_JS = """
(args) => {
  const el = window.__s15els[args.i];
  const all = window.__s15els;
  const cs = getComputedStyle(el);
  const tag = el.tagName.toLowerCase();
  const nearest = (n) => { let p = n; while (p) { if (p.getAttribute && p.hasAttribute("data-ed-layer")) return p; p = p.parentElement; } return null; };
  const owner = (n) => { const p = nearest(n); return p; };
  const chars = [];
  const lines = [];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let tn;
  while ((tn = walker.nextNode())) {
    const par = tn.parentElement;
    if (!par) continue;
    const own = owner(par);
    if (own !== el && !(args.root && own === null)) continue;
    const v = tn.nodeValue;
    if (!v.replace(/\\s+/g, "")) continue;
    const pcs = getComputedStyle(par);
    if (pcs.display === "none" || pcs.visibility === "hidden") continue;
    const tt = pcs.textTransform;
    for (let k = 0; k < v.length; k++) {
      const r = document.createRange();
      r.setStart(tn, k); r.setEnd(tn, k + 1);
      const rects = r.getClientRects();
      if (!rects.length) continue;
      const rc = rects[0];
      let ch = v[k];
      if (tt === "uppercase") ch = ch.toUpperCase(); else if (tt === "lowercase") ch = ch.toLowerCase();
      chars.push([ch, rc.left, rc.top, rc.right, rc.bottom]);
    }
  }
  const fam = cs.fontFamily;
  const info = {
    tag: tag, kind: el.getAttribute("data-ed-kind") || "", name: el.getAttribute("data-ed-name") || "",
    w: el.offsetWidth, h: el.offsetHeight,
    chars: chars,
    font: { family: fam, size: parseFloat(cs.fontSize), weight: cs.fontWeight, style: cs.fontStyle, color: cs.color, letterSpacing: cs.letterSpacing,
            lineHeight: cs.lineHeight, align: cs.textAlign, transform: cs.textTransform, shadow: cs.textShadow, stroke: cs.webkitTextStroke,
            strokeWidth: cs.webkitTextStrokeWidth, strokeColor: cs.webkitTextStrokeColor },
    bg: { color: cs.backgroundColor, image: cs.backgroundImage },
    border: { top: [cs.borderTopWidth, cs.borderTopStyle, cs.borderTopColor], right: [cs.borderRightWidth, cs.borderRightStyle, cs.borderRightColor],
              bottom: [cs.borderBottomWidth, cs.borderBottomStyle, cs.borderBottomColor], left: [cs.borderLeftWidth, cs.borderLeftStyle, cs.borderLeftColor] },
    radius: [cs.borderTopLeftRadius, cs.borderTopRightRadius, cs.borderBottomRightRadius, cs.borderBottomLeftRadius],
    shadow: cs.boxShadow, filter: cs.filter, clipPath: cs.clipPath, mask: cs.webkitMaskImage || cs.maskImage, blend: cs.mixBlendMode,
    backdrop: cs.backdropFilter, overflow: cs.overflow, fit: cs.objectFit,
    padding: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft],
    children: Array.from(el.children).filter(c => c.hasAttribute && c.hasAttribute("data-ed-layer")).length,
    src: tag === "img" ? el.currentSrc : "", nw: tag === "img" ? el.naturalWidth : 0, nh: tag === "img" ? el.naturalHeight : 0,
    hasSvg: tag === "svg" || !!el.querySelector("svg"), hasCanvas: tag === "canvas" || !!el.querySelector("canvas"), hasVideo: tag === "video" || !!el.querySelector("video"),
    bgImageUrl: (cs.backgroundImage.match(/url\\(["']?([^"')]+)["']?\\)/) || [null, ""])[1],
  };
  return info;
}
"""

INIT_JS = """
() => {
  window.__s15els = Array.from(document.querySelectorAll("[data-ed-layer]"));
  return window.__s15els.map((el) => {
    let parent = -1, p = el.parentElement;
    while (p) { const k = window.__s15els.indexOf(p); if (k >= 0) { parent = k; break; } p = p.parentElement; }
    return { id: el.getAttribute("data-ed-layer"), name: el.getAttribute("data-ed-name") || "", kind: el.getAttribute("data-ed-kind") || "", parent: parent,
             tag: el.tagName.toLowerCase(), w: el.offsetWidth, h: el.offsetHeight };
  });
}
"""

ROOT_JS = """
() => {
  const root = document.querySelector("#root") || document.body;
  root.setAttribute("data-ed-layer", "root");
  root.setAttribute("data-ed-name", "Component");
  root.setAttribute("data-ed-kind", "group");
  window.__s15synthetic = true;
}
"""


def sig_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


class HostCapture:
    """One harness page, opened per host."""

    def __init__(self, h: "harness.Harness", cdp):
        self.h = h
        self.cdp = cdp

    def open(self, host: dict, project: str) -> list[dict]:
        comp_file = os.path.join(project, host["src"])
        comp = mcommon.parse_component(comp_file)
        props = dict(host["props"])
        if host["component"] in mcommon.CLIP_START_COMPONENTS:
            props["clip_start"] = 0
        # transparent page without the paper canvas: the layers alone (the paper is its own layer, the paper-canvas host)
        self.comp = comp
        if host["component"] == "paper-canvas":
            self.h.open(comp, props, with_canvas=False, background=False)
        else:
            self.h.open(comp, props, with_canvas=False, background=False)
        n = self.h.page.evaluate("() => document.querySelectorAll('[data-ed-layer]').length")
        self.synthetic = n == 0
        if self.synthetic:
            self.h.page.evaluate(ROOT_JS)
        meta = self.h.page.evaluate(INIT_JS)
        self.meta = meta
        self.cdp.send("DOM.enable")
        doc = self.cdp.send("DOM.getDocument", {"depth": 0})
        res = self.cdp.send("DOM.querySelectorAll", {"nodeId": doc["root"]["nodeId"], "selector": "[data-ed-layer]"})
        self.node_ids = res["nodeIds"]
        return meta

    def seek(self, t: float) -> None:
        self.h.page.evaluate(harness.SEEK_JS, {"id": self.comp["id"], "t": round(t, 5)})

    def frame(self) -> list:
        return self.h.page.evaluate(FRAME_JS, {})

    def quad(self, i: int):
        try:
            bm = self.cdp.send("DOM.getBoxModel", {"nodeId": self.node_ids[i]})
        except Exception:
            return None
        return bm["model"]["border"]

    def describe(self, i: int) -> dict:
        return self.h.page.evaluate(DESCRIBE_JS, {"i": i, "root": self.synthetic})


STABLE_AFTER = 3     # a stretch is static when its look holds (and its transform fits an affine map) for at least this many frames
NUM_RE = re.compile(r"-?\d+\.\d+")


def quantize(sig: str) -> str:
    """Numbers of a look signature rounded to 0.1, so sub-pixel noise (blur(0.0009px)) is not a look change."""
    return NUM_RE.sub(lambda m: f"{float(m.group()):.1f}", sig)


def segment_run(run: dict, tol_px: float = 2.0) -> list[dict]:
    """Split a visible run into static segments (the look holds for STABLE_AFTER frames or more and the box fits an affine map within tol_px:
    a native or sprite clip) and continuous ones (the look changes frame by frame, or the box is in a 3D move: an overlay). A run that never
    changes is one static segment. Instant changes (the signature jumps, then holds) just start a new static segment."""
    sig, pose = run["sig"], run["pose"]
    n = len(sig)
    label = ["S" if (pose[k][6] > tol_px or abs(pose[k][5]) > 0.02) else sig[k] for k in range(n)]
    stretches = []
    a = 0
    for k in range(1, n + 1):
        if k == n or label[k] != label[a]:
            stretches.append((a, k, label[a] != "S" and k - a >= STABLE_AFTER))
            a = k
    segs: list[tuple[int, int, bool]] = []
    for a, b, static in stretches:
        if segs and not static and not segs[-1][2]:
            segs[-1] = (segs[-1][0], b, False)
        else:
            segs.append((a, b, static))
    out = []
    for a, b, static in segs:
        out.append({"start": run["start"] + a, "end": run["start"] + b, "pose": pose[a:b], "opacity": run["opacity"][a:b], "sig": sig[a:b], "quad": run["quad"][a:b],
                    "info": None, "info_frame": run["start"] + a, "mode": "static" if static else "continuous"})
    return out


def capture_host(h: "harness.Harness", cdp, host: dict, project: str, fps: float, start_f: int, end_f: int, log=None, tol_px: float = 2.0) -> dict:
    cap = HostCapture(h, cdp)
    meta = cap.open(host, project)
    n = len(meta)
    layers = []
    for i, m in enumerate(meta):
        layers.append({"id": m["id"], "name": m["name"] or m["id"], "kind": m["kind"], "parent": (meta[m["parent"]]["id"] if m["parent"] >= 0 else None),
                       "parent_index": m["parent"], "tag": m["tag"], "annotated": not cap.synthetic, "w": m["w"], "h": m["h"], "runs": []})
    open_run: list = [None] * n
    host_start_ms = host["start_ms"]
    for f in range(start_f, end_f):
        t = (f * 1000.0 / fps - host_start_ms) / 1000.0
        cap.seek(max(0.0, t))
        rows = cap.frame()
        for i in range(n):
            shown, op, sig = rows[i]
            quad = None
            if shown and op >= VISIBLE:
                quad = cap.quad(i)
            run = open_run[i]
            if quad is None:
                if run is not None:
                    run["end"] = f
                    layers[i]["runs"].append(run)
                    open_run[i] = None
                continue
            lay = layers[i]
            w, hh = float(lay["w"]), float(lay["h"])
            if w <= 0 or hh <= 0:
                # a box with no layout size (an svg group, an inline element): use the quad's own sides
                w = max(1.0, ((quad[2] - quad[0]) ** 2 + (quad[3] - quad[1]) ** 2) ** 0.5)
                hh = max(1.0, ((quad[6] - quad[0]) ** 2 + (quad[7] - quad[1]) ** 2) ** 0.5)
                lay["w"], lay["h"] = round(w, 2), round(hh, 2)
            p = geom.pose_from_quad(quad, w, hh)
            if run is None:
                run = {"start": f, "end": f + 1, "pose": [], "opacity": [], "sig": [], "quad": [], "info": None, "info_frame": f}
                open_run[i] = run
            run["pose"].append([round(p["cx"], 3), round(p["cy"], 3), round(p["sx"], 5), round(p["sy"], 5), round(p["rot"], 4), round(p["skew"], 5), round(p["err"], 3), 1 if p["flip"] else 0])
            run["opacity"].append(op)
            run["sig"].append(sig_hash(quantize(sig)))
            run["quad"].append([round(q, 2) for q in quad])
    for i in range(n):
        if open_run[i] is not None:
            open_run[i]["end"] = end_f
            layers[i]["runs"].append(open_run[i])
    for lay in layers:
        lay["runs"] = [seg for run in lay["runs"] for seg in segment_run(run, tol_px)]
    # the description of each run: at the frame of its largest opacity nearest its middle (the look it holds)
    for i, lay in enumerate(layers):
        for run in lay["runs"]:
            ops = run["opacity"]
            top = max(ops)
            mid = len(ops) // 2
            best = min((k for k, v in enumerate(ops) if v >= top - 0.01), key=lambda k: abs(k - mid))
            f = run["start"] + best
            cap.seek(max(0.0, (f * 1000.0 / fps - host_start_ms) / 1000.0))
            info = cap.describe(i)
            run["info"] = info
            run["info_frame"] = f
    return {"id": host["id"], "component": host["component"], "scene": host.get("scene", ""), "start": start_f, "end": end_f,
            "synthetic": cap.synthetic, "layers": layers}


def capture(run_dir: str, timeline: dict, project: str, out_path: str, only: list[str] | None = None, log=None, tol_px: float = 2.0) -> dict:
    """Capture every composition host of the timeline into layers.json (written at out_path)."""
    from review import common as rc
    st = timeline["settings"]
    fps = st["fps"]["num"] / st["fps"]["den"]
    hosts_by_id = {h["id"]: h for h in rc.read_hosts(project)}
    todo = []
    for lay in timeline["layers"]:
        if lay["kind"] != "composition-scene" or not lay.get("selector"):
            continue
        hid = lay["selector"].lstrip("#")
        host = hosts_by_id.get(hid)
        if host is None or host.get("no_timeline"):
            continue
        if only and hid not in only:
            continue
        host = dict(host)
        host["component"] = lay.get("component") or host["component"]
        todo.append((host, int(lay["start"]), int(lay["end"])))
    result = {"fps": fps, "width": 1080, "height": 1920, "tolerance_px": tol_px, "hosts": [], "host_frames": 0}
    with harness.Harness(lib=project, gpu="auto") as h:
        cdp = h.page.context.new_cdp_session(h.page)
        for host, a, b in todo:
            if host["captions"]:
                result["hosts"].append({"id": host["id"], "component": host["component"], "scene": host.get("scene", ""), "start": a, "end": b,
                                        "synthetic": False, "layers": [], "captions": True})
                continue
            if log:
                log(f"capture {host['id']} ({host['component']}) frames {a}..{b}")
            res = capture_host(h, cdp, host, project, fps, a, b, log, tol_px)
            result["hosts"].append(res)
            result["host_frames"] += b - a
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, separators=(",", ":"))
    return result
