"""pipeline/lib/motion/demo_assets.py: the demo clips of the library (M16): *.mp4 is ignored by git, so the clips the video card
shows in the gallery, in frame-match and in the golden reel are built from the committed screenshots when they are missing.

  ensure(lib)            -> the list of clips that exist (builds assets/demo/plugin-scroll.mp4 and repo-scroll.mp4)
  scroll_clip(png, out)  one smooth scroll through a screenshot as a 1080x1350 clip, 30 fps, H.264, no sound (what the research stage's
                         page recording looks like: pipeline/lib/screenshot.py)
"""
from __future__ import annotations

import os
import shutil
import subprocess

from motion import common

CLIPS = {"plugin-page.png": "plugin-scroll.mp4", "repo.png": "repo-scroll.mp4"}


def scroll_clip(png: str, out: str, seconds: float = 6.2, width: int = 1080, height: int = 1350, fps: int = 30) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not os.path.isfile(png):
        return False
    s = f"{seconds:g}"
    expr = f"(ih-{height})*(3*pow(t/{s},2)-2*pow(t/{s},3))"
    vf = f"scale={width}:-2,crop={width}:{height}:0:'{expr}',format=yuv420p"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cmd = [ffmpeg, "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", s, "-i", png, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "24", "-g", "6", "-keyint_min", "6", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
    return proc.returncode == 0 and os.path.isfile(out)


def ensure(lib: str | None = None) -> list[str]:
    lib = lib or common.motion_lib_dir()
    demo = os.path.join(lib, "assets", "demo")
    have = []
    for png, clip in CLIPS.items():
        src, dst = os.path.join(demo, png), os.path.join(demo, clip)
        if os.path.isfile(dst) or scroll_clip(src, dst):
            have.append(clip)
    return have


def ensure_recordings(assets_dir: str) -> list[str]:
    """For a folder of research screenshots (NN-name.png) without recordings (the frozen test run's, or a run whose pages did not scroll
    when it was captured): build NN-name.mp4 next to each, the way pipeline/lib/screenshot.py records a page (a scroll through the
    page). The golden reel and the tests play these in the video card."""
    out = []
    if not assets_dir or not os.path.isdir(assets_dir):
        return out
    for f in sorted(os.listdir(assets_dir)):
        if f.lower().endswith(".png"):
            dst = os.path.join(assets_dir, f[:-4] + ".mp4")
            if os.path.isfile(dst) or scroll_clip(os.path.join(assets_dir, f), dst):
                out.append(os.path.basename(dst))
    return out


if __name__ == "__main__":
    common.setup_streams()
    print("demo clips: " + ", ".join(ensure()))
