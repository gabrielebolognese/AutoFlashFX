"""pipeline/lib/motion/harness.py: a standalone page that mounts one library component with given props, driven by
Playwright (Chromium) frame by frame: it seeks the component's GSAP timeline, dispatches the hf-seek event the way
HyperFrames does, and measures the tracked elements (position, size, opacity, scale, text) at every frame, with an
optional screenshot per frame. frame-match (motion/framematch.py), the stills and the gallery use it.

The page shims what the HyperFrames runtime gives a mounted scene: window.__timelines (the registry the component
writes into), window.__hyperframes.getVariables() (the declared defaults merged with the props) and the paper canvas
behind the component. Everything else is the component's own file, unchanged: the same <link>s, <style>, markup and
scripts run here and in a render.

  with Harness(gpu="auto") as h:
      h.measure(component, props, times, selectors, shots_dir=None) -> {"rows": [...], "events": [...], "webgl": bool|None, "errors": [...], "shots": [...]}
          rows: [{"t": s, "<selector>": {x, y, w, h, cx, cy, opacity, scale, rotation, text} | None}, ...]
      h.still(component, props, t, out_png, size=(540, 960)) -> out_png
  build_page(component, props) -> the HTML text (what the harness writes under motion-lib/.harness/)
"""
from __future__ import annotations

import json
import os
import re

from motion import common


PAPER_INNER_CACHE: dict[str, str] = {}


def paper_canvas_inner(lib: str) -> str:
    """The paper canvas's markup with its ids renamed, so it can sit under another component's #root."""
    path = os.path.join(lib, "compositions", "paper-canvas.html")
    if path in PAPER_INNER_CACHE:
        return PAPER_INNER_CACHE[path]
    if not os.path.isfile(path):
        return '<div id="paper-root" style="position:absolute;inset:0;background:#F5EEE3"></div>'
    comp = common.parse_component(path)
    inner = comp["inner"]
    inner = inner.replace('id="root"', 'id="paper-root"').replace("#root", "#paper-root")
    inner = re.sub(r"<script[^>]*>.*?</script>", "", inner, flags=re.S)  # static: no script needed
    inner = re.sub(r"<link[^>]*>", "", inner)  # the links come from the component
    PAPER_INNER_CACHE[path] = inner
    return inner


def build_page(component: dict, props: dict | None, lib: str | None = None, with_canvas: bool = True, background: bool = True) -> str:
    lib = lib or common.motion_lib_dir()
    merged = dict(component["defaults"])
    merged.update(props or {})
    base = "file:///" + common.mixed(lib).lstrip("/") + "/"
    canvas = paper_canvas_inner(lib) if with_canvas else ""
    bg = "#F5EEE3" if background else "transparent"
    shim = (
        "window.__timelines = {}; window.__hfVars = " + json.dumps(merged, ensure_ascii=False) + ";\n"
        "window.__hyperframes = { getVariables: function () { return Object.assign({}, window.__hfVars); } };\n"
        "window.__pcEvents = [];\n"
    )
    return (
        "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        f"<base href=\"{base}\">\n"
        f"<style>html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: {bg}; }}"
        " #stage { position: relative; width: 1080px; height: 1920px; overflow: hidden; }</style>\n"
        "<script src=\"assets/vendor/gsap.min.js\"></script>\n"
        f"<script>{shim}</script>\n</head>\n<body>\n<div id=\"stage\">\n{canvas}\n{component['inner']}\n</div>\n</body>\n</html>\n"
    )


MEASURE_JS = """
(args) => {
  const tl = window.__timelines[args.id];
  const rows = [];
  const seekTo = (t) => {
    if (tl) tl.seek(t, false);
    try { window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t, waitUntil: () => {} } })); } catch (e) {}
  };
  for (const t of args.times) {
    seekTo(t);
    const row = { t: t };
    for (const sel of args.selectors) {
      const el = document.querySelector(sel);
      if (!el) { row[sel] = null; continue; }
      const r = el.getBoundingClientRect();
      let op = 1, node = el;
      while (node && node.id !== "stage" && node !== document.body) {
        const cs = getComputedStyle(node);
        op *= parseFloat(cs.opacity);
        if (cs.visibility === "hidden" || cs.display === "none") op = 0;
        node = node.parentElement;
      }
      const cs = getComputedStyle(el);
      // the element's own transform: the scale from the length of the x basis vector (m11, m12, m13: exact under a 3D
      // parallax rotation, which a 2D hypot(a, b) would read as a smaller scale), the 2D rotation, and the parallax
      // angles ry (rotateY) and rx (rotateX) for the hold checks (M14)
      let scale = 1, rotation = 0, ry = 0, rx = 0, tx = 0, ty = 0;
      try {
        const m = new DOMMatrixReadOnly(cs.transform);
        const sx = Math.hypot(m.m11, m.m12, m.m13), sy = Math.hypot(m.m21, m.m22, m.m23);
        scale = Math.max(sx, sy);
        rotation = Math.atan2(m.m12, m.m11) * 180 / Math.PI;
        ry = Math.atan2(-m.m13, Math.hypot(m.m11, m.m12)) * 180 / Math.PI;
        rx = Math.atan2(m.m23, Math.hypot(m.m21, m.m22)) * 180 / Math.PI;
        tx = m.m41; ty = m.m42;
      } catch (e) {}
      row[sel] = { x: r.left, y: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + r.height / 2,
                   opacity: Math.round(op * 1000) / 1000, scale: Math.round(scale * 10000) / 10000, rotation: Math.round(rotation * 100) / 100,
                   ry: Math.round(ry * 100) / 100, rx: Math.round(rx * 100) / 100, tx: Math.round(tx * 1000) / 1000, ty: Math.round(ty * 1000) / 1000,
                   text: (el.textContent || "").trim().slice(0, 80), tag: el.tagName };
      if (el.tagName === "IMG") { row[sel].fit = cs.objectFit; row[sel].nw = el.naturalWidth; row[sel].nh = el.naturalHeight; }
    }
    rows.push(row);
  }
  return { rows: rows, events: window.__pcEvents || [], webgl: window.__pcWebGL === undefined ? null : window.__pcWebGL };
}
"""

SEEK_JS = """
(args) => {
  const tl = window.__timelines[args.id];
  if (tl) tl.seek(args.t, false);
  try { window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: args.t, waitUntil: () => {} } })); } catch (e) {}
  return true;
}
"""


def write_page(component: dict, props: dict | None, lib: str, with_canvas: bool = True, background: bool = True, tag: str = "") -> str:
    """The harness page is written beside the library (under .harness/) so the <base> keeps asset paths simple; `tag`
    names the file apart when two harnesses run at once (a probe next to frame-match, M14)."""
    folder = os.path.join(lib, ".harness")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{component['id']}{tag}.html")
    common.write_text(path, build_page(component, props, lib, with_canvas, background))
    return path


def chromium_args(gpu: str = "auto") -> list[str]:
    args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--allow-file-access-from-files",
            "--font-render-hinting=none", "--hide-scrollbars"]
    if gpu == "software":
        args += ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
    elif gpu == "hardware":
        args += ["--use-gl=angle", "--use-angle=d3d11", "--ignore-gpu-blocklist"]
    else:
        args += ["--ignore-gpu-blocklist"]
    return args


class Harness:
    def __init__(self, lib: str | None = None, gpu: str = "auto", tag: str = "", dpr: float = 1.0):
        """dpr: the device scale factor of the page. The DOM measurements do not depend on it; frame-match uses 0.25 so its
        130 screenshots per component (the strip correlation and the energy measures need 180x320 and 108x192) cost a
        quarter of the time (M14). The stills and the review's pixel checks keep 1.0."""
        self.lib = lib or common.motion_lib_dir()
        self.gpu = gpu
        self.tag = tag
        self.dpr = dpr
        self._pw = None
        self.browser = None
        self.page = None
        self.errors: list[str] = []

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True, args=chromium_args(self.gpu))
        self.page = self.browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=self.dpr)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append("console." + m.type + ": " + m.text) if m.type == "error" else None)
        return self

    def __exit__(self, *exc):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def open(self, component: dict, props: dict | None, with_canvas: bool = True, background: bool = True, timeout_ms: int = 60000) -> None:
        path = write_page(component, props, self.lib, with_canvas, background, self.tag)
        self.errors = []
        self.page.goto("file:///" + common.mixed(path).lstrip("/"), wait_until="load", timeout=timeout_ms)
        self.page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
        self.page.wait_for_timeout(120)

    def measure(self, component: dict, props: dict | None, times: list[float], selectors: list[str], shots_dir: str | None = None,
                shot_size: tuple[int, int] = (180, 320)) -> dict:
        self.open(component, props)
        result = self.page.evaluate(MEASURE_JS, {"id": component["id"], "times": times, "selectors": selectors})
        result["errors"] = list(self.errors)
        result["shots"] = []
        if shots_dir:
            from PIL import Image
            os.makedirs(shots_dir, exist_ok=True)
            for old in os.listdir(shots_dir):
                if old.endswith(".png"):
                    os.remove(os.path.join(shots_dir, old))
            for i, t in enumerate(times):
                self.page.evaluate(SEEK_JS, {"id": component["id"], "t": t})
                png = os.path.join(shots_dir, f"f{i:03d}.png")
                self.page.screenshot(path=png)
                im = Image.open(png).convert("L")
                im.thumbnail(shot_size)
                im.save(png)
                result["shots"].append(png)
        return result

    def still(self, component: dict, props: dict | None, t: float, out_png: str, size: tuple[int, int] = (540, 960)) -> str:
        from PIL import Image
        self.open(component, props)
        self.page.evaluate(SEEK_JS, {"id": component["id"], "t": t})
        self.page.wait_for_timeout(60)
        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        tmp = out_png + ".full.png"
        self.page.screenshot(path=tmp)
        im = Image.open(tmp).convert("RGB").resize(size, Image.LANCZOS)
        im.save(out_png, optimize=True)
        os.remove(tmp)
        return out_png

    def webgl_info(self) -> dict:
        """What WebGL this Chromium gives: the renderer string and whether a context exists (motion/webgl.py)."""
        html = os.path.join(self.lib, ".harness", "webgl-probe.html")
        common.write_text(html, "<!doctype html><html><body><canvas id=c width=64 height=64></canvas></body></html>")
        self.page.goto("file:///" + common.mixed(html).lstrip("/"), wait_until="load")
        return self.page.evaluate("""() => {
          const c = document.getElementById("c");
          const gl = c.getContext("webgl2") || c.getContext("webgl");
          if (!gl) return { ok: false, renderer: null, vendor: null };
          const dbg = gl.getExtension("WEBGL_debug_renderer_info");
          const renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
          const vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
          gl.clearColor(1, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
          const px = new Uint8Array(4); gl.readPixels(1, 1, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
          return { ok: true, renderer: String(renderer), vendor: String(vendor), version: String(gl.getParameter(gl.VERSION)), pixel: Array.from(px) };
        }""")
