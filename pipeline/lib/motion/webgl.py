"""pipeline/lib/motion/webgl.py: the WebGL test for Three.js in headless Chrome on this PC (BUILD_SPEC.md M9): hardware
ANGLE first (the integrated GPU through D3D11), then SwiftShader software rendering. For each path it opens the
harness's Chromium with that GPU flag set, asks for a WebGL context (the renderer string), then mounts the hero-3d
component and checks that its canvas really drew something (pixels differing from the paper around it). Then it
renders the hero-3d composition through HyperFrames itself twice (`--browser-gpu`, `--no-browser-gpu`) and checks
the frame the same way. Writes motion-lib/webgl.json with what worked and the modes to use:

  harness_gpu   the Playwright mode frame-match and the gallery use (hardware, software or auto)
  render_flag   the HyperFrames render flag for 3D compositions (--browser-gpu, --no-browser-gpu or none)
  webgl         false when neither path works: S10 replaces 3D beats with 2D components and flags NEEDS REVIEW
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess

from motion import common, harness


def canvas_drew(h: harness.Harness, comp: dict) -> dict:
    """Mount hero-3d at 1.5 s and compare the canvas region's pixels with the paper beside it."""
    from PIL import Image
    h.open(comp, {"enter_at": 0.0})
    h.page.evaluate(harness.SEEK_JS, {"id": comp["id"], "t": 1.5})
    h.page.wait_for_timeout(80)
    tmp = os.path.join(h.lib, ".harness", "webgl-shot.png")
    h.page.screenshot(path=tmp)
    im = Image.open(tmp).convert("RGB")
    region = im.crop((240, 560, 840, 1160))  # the default 3D area
    paper = im.crop((60, 200, 260, 400))
    px = list(region.getdata())
    ref = list(paper.getdata())
    mean_paper = tuple(sum(c[i] for c in ref) / len(ref) for i in range(3))
    far = sum(1 for c in px if sum(abs(c[i] - mean_paper[i]) for i in range(3)) > 60)
    share = far / max(1, len(px))
    info = h.page.evaluate("() => ({ webgl: window.__pcWebGL === undefined ? null : window.__pcWebGL, attr: (document.getElementById('root') || {}).getAttribute ? document.getElementById('root').getAttribute('data-webgl') : null })")
    return {"drawn_share": round(share, 4), "drew": share > 0.03, "component_webgl": info.get("webgl"), "data_webgl": info.get("attr")}


def hyperframes_render(lib: str, flag: str, out_png_dir: str) -> dict:
    """Render the showreel's hero-3d slot to a PNG sequence of 2 frames with the given browser GPU flag."""
    repo = common.REPO
    npx = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [npx, "--prefix", repo, "hyperframes", "snapshot", "--at", "93.5", "--no-end", "--output", out_png_dir, "--json"]
    if flag:
        cmd.append(flag)
    try:
        proc = subprocess.run(cmd, cwd=lib, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    raw = proc.stdout or ""
    i = raw.find("{")
    frames = []
    try:
        d = json.loads(raw[i:]) if i >= 0 else {}
        frames = [f.get("path") for f in d.get("frames", [])]
    except ValueError:
        pass
    if not frames:
        return {"ok": False, "error": (proc.stderr or raw)[-400:]}
    from PIL import Image
    im = Image.open(frames[0]).convert("RGB")
    region = im.crop((240, 560, 840, 1160))
    paper = im.crop((60, 200, 260, 400))
    ref = list(paper.getdata())
    mean_paper = tuple(sum(c[i] for c in ref) / len(ref) for i in range(3))
    px = list(region.getdata())
    far = sum(1 for c in px if sum(abs(c[i] - mean_paper[i]) for i in range(3)) > 60)
    share = far / max(1, len(px))
    return {"ok": True, "frame": frames[0], "drawn_share": round(share, 4), "drew": share > 0.03}


def run(args) -> int:
    lib = common.motion_lib_dir()
    comp_path = os.path.join(lib, "compositions", "hero-3d.html")
    if not os.path.isfile(comp_path):
        comp_path = os.path.join(lib, "candidates", "hero-3d.html")
    comp = common.parse_component(comp_path)
    report = {"run": dt.datetime.now().isoformat(timespec="seconds"), "paths": {}}
    for mode in ("hardware", "software"):
        entry = {"mode": mode}
        try:
            with harness.Harness(lib=lib, gpu=mode) as h:
                entry["context"] = h.webgl_info()
                entry["hero"] = canvas_drew(h, comp)
                entry["ok"] = bool(entry["context"].get("ok")) and bool(entry["hero"]["drew"])
        except Exception as exc:  # noqa: BLE001
            entry["ok"] = False
            entry["error"] = str(exc)[:300]
        report["paths"][mode] = entry
        print(f"{mode}: {'ok' if entry.get('ok') else 'no'} renderer={entry.get('context', {}).get('renderer')} drew={entry.get('hero', {}).get('drawn_share')}")
    # HyperFrames' own render path
    out_dir = os.path.join(lib, ".harness", "webgl-hf")
    report["hyperframes"] = {}
    for label, flag in (("browser-gpu", "--browser-gpu"), ("no-browser-gpu", "--no-browser-gpu")):
        r = hyperframes_render(lib, flag, os.path.join(out_dir, label))
        report["hyperframes"][label] = r
        print(f"hyperframes {label}: {'drew' if r.get('drew') else 'no'} ({r.get('drawn_share', r.get('error'))})")
    hw = report["paths"]["hardware"].get("ok")
    sw = report["paths"]["software"].get("ok")
    hf_gpu = report["hyperframes"]["browser-gpu"].get("drew")
    hf_sw = report["hyperframes"]["no-browser-gpu"].get("drew")
    report["harness_gpu"] = "hardware" if hw else ("software" if sw else "auto")
    report["render_flag"] = "--browser-gpu" if hf_gpu else ("--no-browser-gpu" if hf_sw else "")
    report["webgl"] = bool(hw or sw) and bool(hf_gpu or hf_sw)
    renderer = (report["paths"]["hardware"].get("context") or {}).get("renderer") if hw else (report["paths"]["software"].get("context") or {}).get("renderer")
    report["summary"] = (f"WebGL works: harness {report['harness_gpu']} ({renderer}), HyperFrames renders 3D with {report['render_flag'] or 'the default flags'}"
                         if report["webgl"] else "WebGL unavailable: 3D beats fall back to 2D and S10 flags NEEDS REVIEW")
    out = args.out or os.path.join(lib, "webgl.json")
    common.write_json(out, report)
    print(report["summary"] + f" -> {out}")
    return 0
