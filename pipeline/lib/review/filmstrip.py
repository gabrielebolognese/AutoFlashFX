"""pipeline/lib/review/filmstrip.py: 10 fps filmstrips of a video (BUILD_SPEC.md S12: the hook, the transitions).

A strip is a sheet of frames, 8 per row, each with its time stamped above it (the analyzer's format, so the edit
review reads both alike).

  strip(video, start_s, seconds, out_png, fps=10, width=200) -> out_png
  run_all(ctx) -> {"hook": path, "transitions": [{"from", "to", "type", "ms", "png"}]}
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from review import common as rc


def strip(video: str, start_s: float, seconds: float, out_png: str, fps: int = 10, width: int = 200, cols: int = 8) -> str:
    from PIL import Image, ImageDraw
    tmp = tempfile.mkdtemp(prefix="strip-")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(0.0, start_s):.3f}", "-t", f"{seconds:.3f}", "-i", video, "-vf", f"fps={fps},scale={width}:-1",
                        os.path.join(tmp, "%03d.png")], capture_output=True, timeout=300)
        frames = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        if not frames:
            raise RuntimeError(f"no frames from {video} at {start_s:.2f} s")
        ims = [Image.open(os.path.join(tmp, f)).convert("RGB") for f in frames]
        w, h = ims[0].size
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * (h + 18)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, im in enumerate(ims):
            x, y = (i % cols) * w, (i // cols) * (h + 18)
            sheet.paste(im, (x, y + 18))
            t = max(0.0, start_s) + i / fps
            draw.text((x + 4, y + 3), f"{int(t // 60)}:{t % 60:04.1f}", fill="black")
        os.makedirs(os.path.dirname(os.path.abspath(out_png)) or ".", exist_ok=True)
        sheet.save(out_png)
        for im in ims:
            im.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_png


def run_all(ctx: rc.Ctx, video: str | None = None) -> dict:
    video = video or (ctx.draft_mixed if os.path.isfile(ctx.draft_mixed) else ctx.draft)
    out_dir = os.path.join(ctx.stage_dir, "filmstrips")
    os.makedirs(out_dir, exist_ok=True)
    hook = next((s for s in ctx.plan.get("scenes", []) if s.get("beat_type") == "hook"), None)
    hook_s = (int(hook["end_ms"]) / 1000.0 if hook else 3.5)
    out = {"hook": strip(video, 0.0, min(4.0, hook_s + 0.3), os.path.join(out_dir, "hook.png")), "transitions": []}
    changes = [e for e in ctx.events.get("events", []) if e.get("scene_change")]
    for i, e in enumerate(changes, 1):
        ms = int(e["ms"])
        tr = int(e.get("transition_ms", 0) or 0)
        start = max(0.0, (ms - tr - 300) / 1000.0)
        png = os.path.join(out_dir, f"transition-{i:02d}.png")
        strip(video, start, (ms + 700) / 1000.0 - start, png)
        out["transitions"].append({"n": i, "from": e.get("from_scene"), "to": e.get("scene"), "type": e.get("transition_type"), "ms": ms, "transition_ms": tr, "png": png})
    return out
