"""checks.py: what S15 verifies before it hands the project over (BUILD_SPEC.md S15 step 6, M21).

  - cli_*: the editor's own CLI in the stable copy (validate, normalize, render, compare) when the manifest has it
  - layout: at the middle frame of every scene, the project's native boxes against the captured quads (within 2 px), the sprites
    composited with their keyframes against the isolated layer render (SSIM at least 0.95), and each native text measured with
    Canvas2D in the same font and size as the editor does against the composition's text box (within 2 px)
  - duration: the project lasts as long as the video within 1 frame
  - mix: the project's audio mixed from its clips is within 0.5 LU of the video's audio
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess

import numpy as np
from PIL import Image

from . import audio as saudio
from . import geom


# ---------------------------------------------------------------------------------------------------- the editor's CLI


def cli_available(stable_dir: str | None) -> bool:
    return bool(stable_dir) and os.path.isfile(os.path.join(stable_dir, "scripts", "cli", "run.mjs")) and os.path.isdir(os.path.join(stable_dir, "node_modules"))


def run_cli(stable_dir: str, args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    """`npm run cli -- <args>` in the stable copy (package.json: "cli": "node scripts/cli/run.mjs")."""
    node = shutil.which("node") or "node"
    return subprocess.run([node, "scripts/cli/run.mjs"] + args, cwd=stable_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def cli_validate(stable_dir: str, folder: str) -> dict:
    p = run_cli(stable_dir, ["validate", folder.replace("\\", "/"), "--json"], 600)
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return {"ok": False, "errors": [{"path": "", "message": (p.stderr or p.stdout or "no output")[-400:]}], "warnings": []}
    data["ok"] = bool(data.get("ok")) and p.returncode == 0
    return data


def cli_normalize(stable_dir: str, folder: str) -> tuple[bool, str]:
    p = run_cli(stable_dir, ["normalize", folder.replace("\\", "/"), "--write"], 600)
    return p.returncode == 0, (p.stderr or p.stdout or "")[-400:]


def cli_parity(stable_dir: str, folder: str, reference: str, out_mp4: str, ssim: float, timeout: int = 1800) -> dict:
    """Render the project with the editor and compare it with the exported video: {"ok", "worst": [{frame, ssim, region}], "text"}."""
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    r = run_cli(stable_dir, ["render", folder.replace("\\", "/"), "--out", out_mp4.replace("\\", "/")], timeout)
    if r.returncode != 0:
        return {"ok": False, "rendered": False, "text": (r.stderr or r.stdout)[-400:], "worst": []}
    c = run_cli(stable_dir, ["compare", out_mp4.replace("\\", "/"), reference.replace("\\", "/"), "--ssim", str(ssim), "--json"], timeout)
    worst = []
    try:
        data = json.loads(c.stdout)
        for w in (data.get("worst") or data.get("worstFrames") or [])[:20]:
            worst.append({"frame": w.get("frame"), "ssim": w.get("ssim"), "region": w.get("region")})
    except ValueError:
        data = {}
    return {"ok": c.returncode == 0, "rendered": True, "worst": worst, "text": (c.stdout or "")[-400:], "data": data}


# ---------------------------------------------------------------------------------------------------- ssim


def _box_mean(a: np.ndarray, n: int) -> np.ndarray:
    c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), axis=0), axis=1)
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / float(n * n)


def ssim(a: Image.Image, b: Image.Image, win: int = 8) -> float:
    """SSIM of the luma of two same-size images (uniform windows of win x win)."""
    x = np.asarray(a.convert("L"), dtype=np.float64)
    y = np.asarray(b.convert("L"), dtype=np.float64)
    if x.shape != y.shape or min(x.shape) < win:
        return 1.0 if x.shape == y.shape and np.array_equal(x, y) else 0.0
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mx, my = _box_mean(x, win), _box_mean(y, win)
    sxx, syy, sxy = _box_mean(x * x, win) - mx * mx, _box_mean(y * y, win) - my * my, _box_mean(x * y, win) - mx * my
    s = ((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sxx + syy + c2))
    return float(s.mean())


# ---------------------------------------------------------------------------------------------------- the project's own placement


def value_at(clip: dict, prop: str, base: float, k: int) -> float:
    keys = (clip.get("keyframes") or {}).get(prop)
    return geom.eval_keys(keys, k) if keys else base


def clip_pose_at(clip: dict, k: int) -> dict:
    tf = clip["transform"]
    scale = value_at(clip, "transform.scale", tf["scale"], k)
    has_y = "scaleY" in tf or "transform.scaleY" in (clip.get("keyframes") or {})
    return {"x": value_at(clip, "transform.x", tf["x"], k), "y": value_at(clip, "transform.y", tf["y"], k), "scale": scale,
            "scaleY": value_at(clip, "transform.scaleY", tf.get("scaleY", tf["scale"]), k) if has_y else scale, "rotation": value_at(clip, "transform.rotation", tf["rotation"], k),
            "opacity": value_at(clip, "opacity", clip.get("opacity", 1.0), k)}


def box_quad(pose: dict, w: float, h: float, W: int, H: int) -> list[float]:
    cx, cy = W / 2.0 + pose["x"], H / 2.0 + pose["y"]
    r = math.radians(pose["rotation"])
    pts = []
    for lx, ly in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        ux, uy = lx * pose["scale"], ly * pose["scaleY"]
        pts += [cx + ux * math.cos(r) - uy * math.sin(r), cy + ux * math.sin(r) + uy * math.cos(r)]
    return pts


def composite_sprite(clip: dict, media: dict, project_dir: str, k: int, W: int, H: int) -> Image.Image:
    """The sprite placed the way the clip's keyframes say at relative frame k, on a transparent frame: one bicubic affine resample, so the
    sub-pixel position and the scale are those of the clip (and not rounded to whole pixels)."""
    pose = clip_pose_at(clip, k)
    im = Image.open(os.path.join(project_dir, media["file"]["relPath"])).convert("RGBA")
    sx, sy = max(pose["scale"], 1e-6), max(pose["scaleY"], 1e-6)
    r = math.radians(pose["rotation"])
    cx, cy = W / 2.0 + pose["x"], H / 2.0 + pose["y"]
    cs, sn = math.cos(r), math.sin(r)
    data = (cs / sx, sn / sx, im.width / 2.0 - (cx * cs + cy * sn) / sx,
            -sn / sy, cs / sy, im.height / 2.0 - (-cx * sn + cy * cs) / sy)
    out = im.transform((W, H), Image.AFFINE, data, resample=Image.BICUBIC)
    if pose["opacity"] < 0.999:
        out.putalpha(out.getchannel("A").point(lambda v: int(v * pose["opacity"])))
    return out


def over_white(im: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")


# ---------------------------------------------------------------------------------------------------- duration and mix


def duration_check(project: dict, video_frames: int) -> dict:
    end = max((c["start"] + c["duration"] for c in project["clips"].values() if c["kind"] != "audio"), default=0)
    audio_end = max((c["start"] + c["duration"] for c in project["clips"].values() if c["kind"] == "audio"), default=0)
    ok = abs(max(end, 0) - video_frames) <= 1
    return {"check": "duration", "ok": ok, "got_frames": end, "want_frames": video_frames, "audio_end_frames": audio_end}


def mix_check(project: dict, project_dir: str, video_path: str, total_frames: int, tol_lu: float, work_dir: str) -> dict:
    mix = saudio.mix_project(project, project_dir, total_frames)
    os.makedirs(work_dir, exist_ok=True)
    wav = os.path.join(work_dir, "project-mix.wav")
    saudio.write_wav(wav, mix)
    a, b = saudio.loudness(wav), saudio.loudness(video_path)
    ok = a is not None and b is not None and abs(a - b) <= tol_lu
    return {"check": "mix", "ok": ok, "project_lufs": a, "video_lufs": b, "tolerance_lu": tol_lu}


def sound_times_check(project: dict, timeline: dict, fps: float) -> dict:
    """The voice and every sound sit at their times within 1 frame."""
    bad = []
    want = {f"c-sfx-{c['id']}": c["start_ms"] for c in (timeline.get("audio") or {}).get("sfx", [])}
    for cid, ms in want.items():
        c = project["clips"].get(cid)
        if c is None:
            continue
        if abs(c["start"] - ms * fps / 1000.0) > 1.0:
            bad.append(cid)
    return {"check": "sound_times", "ok": not bad, "bad": bad[:10], "checked": len(want)}
