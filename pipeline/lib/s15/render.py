"""render.py: sprites, overlays, baked captions and plates, rendered in the same browser harness as the capture
(BUILD_SPEC.md S15 step 3, M21).

A layer is rendered isolated: everything else on the page is hidden (visibility), the page is transparent, and the layer's own
ancestors keep their transforms and opacity (the layer looks exactly as in the composition at that frame; the sprite's keyframes
are relative to the pose it was rendered at). Pixels are cropped to the union of the visible ones.

  Renderer(project, media_dir, manifest, fps, W, H, cfg)  as a context manager
    .sprite(host, layer_index, frame)                      -> {"file", "x0", "y0", "x1", "y1", "dsf", "w", "h"}
    .overlay(host, layer_index, start, end, name)          -> [{"start", "end", "media": {...}, "x0", "y0", "x1", "y1"}...] (one per piece)
    .caption_states(host, start, end, name)                -> [{"start", "end", "file", "x0", "y0", "x1", "y1", "w", "h"}...]
    .plate(hosts, start, end, out_file)                    -> out_file (an opaque MP4 of the composition without the caption host)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from PIL import Image  # noqa: E402

from motion import common as mcommon  # noqa: E402
from motion import harness  # noqa: E402

from .capture import INIT_JS, ROOT_JS  # noqa: E402

ISOLATE_JS = """
(args) => {
  const els = window.__s15els;
  const target = els[args.i];
  els.forEach((e) => e.removeAttribute("data-s15"));
  target.setAttribute("data-s15", "t");
  els.forEach((e) => { if (e !== target && target.contains(e)) e.setAttribute("data-s15", "h"); });
  let st = document.getElementById("__s15iso");
  if (!st) { st = document.createElement("style"); st.id = "__s15iso"; document.head.appendChild(st); }
  st.textContent = 'html, body { background: transparent !important; } * { visibility: hidden !important; } [data-s15="t"], [data-s15="t"] * { visibility: visible !important; } [data-s15="h"], [data-s15="h"] * { visibility: hidden !important; }';
  return true;
}
"""

SHOW_ALL_JS = """
() => {
  let st = document.getElementById("__s15iso");
  if (st) st.textContent = 'html, body { background: transparent !important; }';
  return true;
}
"""


def run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-")[:80] or "layer"


def alpha_bbox(im: Image.Image) -> tuple[int, int, int, int] | None:
    return im.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()


def webp_durations(n: int, fps: float = 30.0) -> list[int]:
    """33, 33, 34 ms repeating: frame k starts at floor(k * 1000 / 30) ms."""
    return [int((k + 1) * 1000 / fps) - int(k * 1000 / fps) for k in range(n)]


def webp_frame_durations(data: bytes) -> list[int]:
    """The frame durations (ms) an animated WebP file carries: the 24-bit field of each ANMF chunk (read from the RIFF structure itself)."""
    out = []
    pos = 12
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        if tag == b"ANMF":
            out.append(int.from_bytes(data[pos + 8 + 12:pos + 8 + 15], "little"))
        pos += 8 + size + (size & 1)
    return out


def webp_frame_at(timeline_frame: int, n_frames: int, fps: float = 30.0) -> int:
    """The animation frame the editor shows at a timeline frame: the last frame whose start is at or before round(k * 1000000 / 30) microseconds
    (frame j starts at floor(j * 1000 / 30) ms). Loops when the clip is longer than the animation."""
    t_us = round(timeline_frame * 1_000_000 / fps)
    total_ms = int(n_frames * 1000 / fps)
    t_ms_us = t_us % (total_ms * 1000) if total_ms > 0 else t_us
    best = 0
    for j in range(n_frames):
        if int(j * 1000 / fps) * 1000 <= t_ms_us:
            best = j
    return best


class Renderer:
    def __init__(self, project: str, media_dir: str, manifest, fps: float, width: int, height: int, cfg: dict | None = None):
        self.project = project
        self.media_dir = media_dir
        self.m = manifest
        self.fps, self.W, self.H = fps, width, height
        self.cfg = cfg or {}
        self.h = None
        self.page = None
        self.cur = None
        self.pages: dict = {}
        self._cur = None

    def __enter__(self):
        self.h = harness.Harness(lib=self.project, gpu="auto").__enter__()
        return self

    def __exit__(self, *exc):
        self.release()
        if self.h:
            self.h.__exit__(*exc)

    # -------------------------------------------------------------------------------------------- pages
    def open(self, host: dict, dsf: float = 1.0, tag: str = ""):
        """A page with the host's component alone on a transparent background; returns (page, component id, has layers)."""
        comp = mcommon.parse_component(os.path.join(self.project, host["src"]))
        props = dict(host["props"])
        if host["component"] in mcommon.CLIP_START_COMPONENTS:
            props["clip_start"] = 0
        path = harness.write_page(comp, props, self.project, with_canvas=False, background=False, tag=tag or f"-s15-{host['id']}")
        page = self.h.browser.new_page(viewport={"width": self.W, "height": self.H}, device_scale_factor=dsf)
        page.goto("file:///" + mcommon.mixed(path).lstrip("/"), wait_until="load", timeout=60000)
        page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
        page.wait_for_timeout(120)
        n = page.evaluate("() => document.querySelectorAll('[data-ed-layer]').length")
        if n == 0:
            page.evaluate(ROOT_JS)
        page.evaluate(INIT_JS)
        return page, comp["id"]

    def page_for(self, host: dict, dsf: float = 1.0):
        """The harness page of a host, kept for the next layer of the same host (items come in host order); (page, component id)."""
        key = (host["id"], dsf)
        if self._cur is not None and self._cur[0] == key:
            return self._cur[1], self._cur[2]
        self.release()
        page, cid = self.open(host, dsf)
        self._cur = (key, page, cid)
        return page, cid

    def release(self) -> None:
        if self._cur is not None:
            try:
                self._cur[1].close()
            except Exception:  # noqa: BLE001
                pass
            self._cur = None

    def seek(self, page, cid: str, host: dict, frame: int) -> None:
        t = (frame * 1000.0 / self.fps - host["start_ms"]) / 1000.0
        page.evaluate(harness.SEEK_JS, {"id": cid, "t": round(max(0.0, t), 5)})

    def shot(self, page, region: tuple | None = None) -> Image.Image:
        """A transparent screenshot of the page, or of region (x0, y0, x1, y1) in page px (the image is then that part only)."""
        if region:
            x0, y0, x1, y1 = region
            data = page.screenshot(omit_background=True, type="png", clip={"x": x0, "y": y0, "width": max(1, x1 - x0), "height": max(1, y1 - y0)})
        else:
            data = page.screenshot(omit_background=True, type="png")
        return Image.open(io.BytesIO(data)).convert("RGBA")

    def region_of(self, quads: list | None, margin: int = 96) -> tuple | None:
        """The union of a layer's captured quads, grown by a margin (shadows, blur), clamped to the frame: what a screenshot needs to cover."""
        if not quads:
            return None
        xs = [q[i] for q in quads for i in (0, 2, 4, 6)]
        ys = [q[i] for q in quads for i in (1, 3, 5, 7)]
        x0, y0 = max(0, int(min(xs)) - margin), max(0, int(min(ys)) - margin)
        x1, y1 = min(self.W, int(max(xs)) + margin + 1), min(self.H, int(max(ys)) + margin + 1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        return (x0, y0, x1, y1)

    # -------------------------------------------------------------------------------------------- sprite
    def sprite(self, host: dict, li: int, frame: int, name: str, quads: list | None = None) -> dict:
        dsf = float(self.cfg.get("sprite_scale", 1.0))
        page, cid = self.page_for(host, dsf)
        try:
            page.evaluate(ISOLATE_JS, {"i": li})
            self.seek(page, cid, host, frame)
            page.wait_for_timeout(40)
            region = self.region_of(quads)
            im = self.shot(page, region)
            ox, oy = (region[0], region[1]) if region else (0, 0)
            bb = alpha_bbox(im)
            if bb is None:
                bb = (0, 0, 2, 2)
            crop = im.crop(bb)
            bb = (bb[0] + int(ox * dsf), bb[1] + int(oy * dsf), bb[2] + int(ox * dsf), bb[3] + int(oy * dsf))
            out_dir = os.path.join(self.media_dir, "sprites")
            os.makedirs(out_dir, exist_ok=True)
            rel = f"media/sprites/{safe(name)}.png"
            crop.save(os.path.join(os.path.dirname(self.media_dir), rel), optimize=True)
            return {"file": rel, "x0": bb[0] / dsf, "y0": bb[1] / dsf, "x1": bb[2] / dsf, "y1": bb[3] / dsf, "dsf": dsf, "w": crop.width, "h": crop.height}
        finally:
            pass

    # -------------------------------------------------------------------------------------------- overlay
    def overlay(self, host: dict, li: int, start: int, end: int, name: str, quads: list | None = None) -> list[dict]:
        page, cid = self.page_for(host, 1.0)
        tmp = os.path.join(self.media_dir, ".tmp-" + safe(name))
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        try:
            if li is None:   # the whole host (the caption host), nothing isolated
                page.evaluate(SHOW_ALL_JS)
            else:
                page.evaluate(ISOLATE_JS, {"i": li})
            frames: list[Image.Image] = []
            union = None
            region = self.region_of(quads)
            ox, oy = (region[0], region[1]) if region else (0, 0)
            for f in range(start, end):
                self.seek(page, cid, host, f)
                im = self.shot(page, region)
                frames.append(im)
                bb = alpha_bbox(im)
                if bb:
                    union = bb if union is None else (min(union[0], bb[0]), min(union[1], bb[1]), max(union[2], bb[2]), max(union[3], bb[3]))
            if union is None:
                union = (0, 0, 2, 2)
            x0, y0, x1, y1 = union
            if (x1 - x0) % 2:
                x1 = min(self.W, x1 + 1) if x1 < self.W else x1
                x0 = x0 - 1 if (x1 - x0) % 2 and x0 > 0 else x0
            if (y1 - y0) % 2:
                y1 = min(self.H, y1 + 1) if y1 < self.H else y1
                y0 = y0 - 1 if (y1 - y0) % 2 and y0 > 0 else y0
            cropped = [im.crop((x0, y0, x1, y1)) for im in frames]
            return self.encode_overlay(cropped, (x0 + ox, y0 + oy, x1 + ox, y1 + oy), start, end, name, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def encode_overlay(self, cropped: list[Image.Image], box: tuple, start: int, end: int, name: str, tmp: str) -> list[dict]:
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        root = os.path.dirname(self.media_dir)
        out_dir = os.path.join(self.media_dir, "overlays")
        os.makedirs(out_dir, exist_ok=True)
        base = safe(name)
        if self.m.has("media.videoAlpha"):
            for k, im in enumerate(cropped):
                im.save(os.path.join(tmp, f"{k + 1:05d}.png"))
            rel = f"media/overlays/{base}.webm"
            cmd = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", f"{self.fps:g}", "-i", os.path.join(tmp, "%05d.png").replace("\\", "/"), "-c:v", "libvpx-vp9",
                   "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", str(self.cfg.get("overlay_crf", 18)), "-auto-alt-ref", "0", "-deadline", "good", "-cpu-used", "4", "-row-mt", "1", "-an", os.path.join(root, rel).replace("\\", "/")]
            p = run(cmd)
            if p.returncode != 0:
                raise RuntimeError("ffmpeg could not write the alpha WebM: " + (p.stderr or "")[-300:])
            return [{"start": start, "end": end, "box": box, "media": {"type": "video-alpha", "file": rel, "width": w, "height": h, "frames": len(cropped)}}]
        if self.m.has("media.imageSequence"):
            seq_dir = os.path.join(out_dir, base)
            os.makedirs(seq_dir, exist_ok=True)
            for k, im in enumerate(cropped):
                im.save(os.path.join(seq_dir, f"frame_{k + 1:05d}.png"))
            return [{"start": start, "end": end, "box": box, "media": {"type": "sequence", "dir": f"media/overlays/{base}", "pattern": "frame_%05d.png", "first": 1,
                                                                        "file": f"media/overlays/{base}/frame_00001.png", "width": w, "height": h, "frames": len(cropped)}}]
        # animated WebP within the manifest's budget: several consecutive clips when it does not fit
        aim = self.m.get("media.animatedImage") or {}
        budget = int(aim.get("textureBudgetBytes", 134217728))
        max_side = int(aim.get("maxSide", 2048))
        if w > max_side or h > max_side:
            raise RuntimeError(f"an overlay of {w}x{h} px is over the editor's maxSide {max_side}")
        per = max(1, int(budget // (w * h * 4 * 4 / 3)))
        pieces = []
        for pi, a in enumerate(range(0, len(cropped), per)):
            chunk = cropped[a:a + per]
            rel = f"media/overlays/{base}-{pi + 1}.webp" if len(cropped) > per else f"media/overlays/{base}.webp"
            chunk[0].save(os.path.join(root, rel), format="WEBP", save_all=True, append_images=chunk[1:], duration=webp_durations(len(chunk), self.fps),
                          lossless=True, loop=0, exact=True)
            pieces.append({"start": start + a, "end": start + a + len(chunk), "box": box,
                           "media": {"type": "webp", "file": rel, "width": w, "height": h, "frames": len(chunk)}})
        return pieces

    # -------------------------------------------------------------------------------------------- baked captions
    def caption_states(self, host: dict, start: int, end: int, name: str) -> list[dict]:
        """One PNG per look of the caption host (a word state, a fade frame): consecutive identical frames are one image clip."""
        page, cid = self.page_for(host, 1.0)
        page.evaluate(SHOW_ALL_JS)
        out_dir = os.path.join(self.media_dir, "images")
        os.makedirs(out_dir, exist_ok=True)
        states: list[dict] = []
        prev_hash = None
        try:
            for f in range(start, end):
                self.seek(page, cid, host, f)
                im = self.shot(page)
                bb = alpha_bbox(im)
                if bb is None:
                    prev_hash = None
                    continue
                crop = im.crop(bb)
                hsh = hashlib.md5(crop.tobytes() + str(bb).encode()).hexdigest()
                if hsh == prev_hash and states:
                    states[-1]["end"] = f + 1
                    continue
                prev_hash = hsh
                idx = len(states) + 1
                rel = f"media/images/{safe(name)}-{idx:03d}.png"
                crop.save(os.path.join(os.path.dirname(self.media_dir), rel), optimize=True)
                states.append({"start": f, "end": f + 1, "file": rel, "x0": bb[0], "y0": bb[1], "x1": bb[2], "y1": bb[3], "w": crop.width, "h": crop.height, "hash": hsh})
        finally:
            pass
        return states

    # -------------------------------------------------------------------------------------------- plate
    def plate(self, hosts: list[dict], start: int, end: int, out_file: str, background: str, skip_captions: bool = True) -> str:
        """An opaque MP4 of the composition between two frames: every non-caption host composited over the paper color."""
        bg = tuple(int(background.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        tmp = out_file + ".frames"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        live: dict = {}
        try:
            order = [h for h in hosts if not (skip_captions and h.get("captions"))]
            for k, f in enumerate(range(start, end)):
                canvas = Image.new("RGBA", (self.W, self.H), bg)
                for hs in order:
                    a, b = hs["start_frame"], hs["end_frame"]
                    if not (a <= f < b):
                        if hs["id"] in live:
                            live.pop(hs["id"])[0].close()
                        continue
                    if hs["id"] not in live:
                        live[hs["id"]] = self.open(hs, 1.0, tag=f"-plate-{hs['id']}")
                    page, cid = live[hs["id"]]
                    self.seek(page, cid, hs, f)
                    canvas.alpha_composite(self.shot(page))
                canvas.convert("RGB").save(os.path.join(tmp, f"{k + 1:05d}.png"))
            cmd = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", f"{self.fps:g}", "-i", os.path.join(tmp, "%05d.png").replace("\\", "/"), "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "16", "-pix_fmt", "yuv420p", "-an", out_file.replace("\\", "/")]
            p = run(cmd, 3600)
            if p.returncode != 0:
                raise RuntimeError("ffmpeg could not write the plate: " + (p.stderr or "")[-300:])
            return out_file
        finally:
            for page, _ in live.values():
                try:
                    page.close()
                except Exception:
                    pass
            shutil.rmtree(tmp, ignore_errors=True)
