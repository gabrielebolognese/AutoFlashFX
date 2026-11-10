#!/usr/bin/env python
"""footage.py: the stage logic of the test-only footage-dummy format (BUILD_SPEC.md 14.7, M20). No model call.

  python footage.py ingest RUN_DIR     ingest (dummy): probe every clip of the channel's footage/ folder -> ingest/clips.json
  python footage.py cut RUN_DIR        cut (dummy): keep clip_len_s of every clip from clip_in_s on, write cut/cut.json (the decisions) and
                                       timeline/timeline.json (the footage family's timeline, BUILD_SPEC.md 14.8) with one footage layer per clip,
                                       one caption chunk per clip and the footage audio of every layer
  python footage.py export RUN_DIR     export: 14-export/export.json (what the runner's export step needs), the reel copied from the render
                                       and a hook 2 clip (the first 3 s)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")).replace("\\", "/")
sys.path.insert(0, REPO + "/pipeline/lib")
import config as cfgmod  # noqa: E402
import paths  # noqa: E402
from timeline import common as tc  # noqa: E402


def cfg(key: str, default):
    return cfgmod.get(cfgmod.load(), key, default)


def clips_dir() -> str:
    return paths.ch("footage")


def ingest(run: str) -> int:
    out = f"{run}/ingest"
    os.makedirs(out, exist_ok=True)
    files = sorted(f for f in os.listdir(clips_dir()) if f.lower().endswith((".mp4", ".mov", ".mkv")))
    if not files:
        print(f"ingest: no clip in {clips_dir()}", file=sys.stderr)
        return 1
    clips = []
    for f in files:
        p = tc.probe(f"{clips_dir()}/{f}")
        if not p.get("duration"):
            print(f"ingest: cannot probe {f}", file=sys.stderr)
            return 1
        clips.append({"file": f, "duration_s": round(p["duration"], 3), "width": p["width"], "height": p["height"], "fps": p["fps"], "has_audio": p["has_audio"]})
    tc.write_json(f"{out}/clips.json", {"written_by": "ingest", "clips": clips})
    print(f"ingest: {len(clips)} clips")
    return 0


def cut(run: str) -> int:
    clips = (tc.read_json(f"{run}/ingest/clips.json") or {}).get("clips") or []
    if not clips:
        print("cut: ingest/clips.json has no clips", file=sys.stderr)
        return 1
    clip_in = float(cfg("footage.clip_in_s", 0.2))
    clip_len = float(cfg("footage.clip_len_s", 1.5))
    fps_num, fps_den = 30, 1
    W, H = 1080, 1920
    ch = os.environ.get("REELS_CHANNEL", "")
    src = tc.Sources(run, paths.channel_root(ch))
    layers, chunks, audio_footage, decisions, markers = [], [], [], [], []
    cursor = 0
    for n, c in enumerate(clips, 1):
        sid = src.add(f"{clips_dir()}/{c['file']}", "video", prefix="clip")
        length = min(clip_len, max(0.2, c["duration_s"] - clip_in))
        frames = int(round(length * fps_num / fps_den))
        length = frames * fps_den / fps_num
        start, end = cursor, cursor + frames
        lid = f"clip{n}"
        layers.append({"id": lid, "name": c["file"], "kind": "footage", "source": {"id": sid, "in": round(clip_in, 6), "out": round(clip_in + length, 6)},
                       "start": start, "end": end, "provenance": "cut"})
        words = []
        label = f"clip number {n}".split()
        t0 = start * 1000 // fps_num
        t1 = end * 1000 // fps_num
        tc_end = t0 + int((t1 - t0) * 0.6)    # the caption shows over the first 60 percent of the clip: the rest is a stretch without one
        step = (tc_end - t0) // len(label)
        for k, w in enumerate(label):
            words.append({"text": w, "start_ms": int(t0 + k * step), "end_ms": int(t0 + (k + 1) * step if k < len(label) - 1 else tc_end), "emphasis": k == len(label) - 1})
        chunks.append({"id": f"c{n:03d}", "text": " ".join(label), "start_ms": int(t0), "end_ms": int(tc_end), "scene": lid, "words": words})
        if c.get("has_audio"):
            audio_footage.append({"layer": lid, "source": sid, "in_ms": int(round(clip_in * 1000)), "out_ms": int(round((clip_in + length) * 1000)),
                                  "start_ms": int(t0), "gain_db": 0.0})
        markers.append({"id": f"scene-{lid}", "kind": "scene", "frame": start, "label": c["file"]})
        decisions.append({"clip": c["file"], "keep": True, "in_s": clip_in, "out_s": round(clip_in + length, 3), "caption": " ".join(label)})
        cursor = end
    timeline = {
        "version": 1, "format": "footage-dummy", "channel": ch, "run": os.path.basename(run),
        "settings": {"width": W, "height": H, "fps": {"num": fps_num, "den": fps_den}, "duration_frames": cursor, "sample_rate": 48000, "background": "#101010"},
        "sources": src.items, "layers": layers, "captions": {"style": "plain", "mode": "line", "chunks": chunks},
        "audio": {"voice": None, "sfx": [], "footage": audio_footage, "music": [], "loudness": {"target_lufs": -14.0, "true_peak_dbtp": -1.5}},
        "transitions": [], "markers": markers,
        "provenance": {"written_by": "cut", "render_source": "cut", "inputs": {"clips": "ingest/clips.json"}},
        "render": {"caption_size": 72, "caption_y": 1300, "crossfade_ms": 0},
    }
    tc.write_json(f"{run}/timeline/timeline.json", timeline)
    tc.write_json(f"{run}/cut/cut.json", {"written_by": "cut", "decisions": decisions, "frames": cursor})
    print(f"cut: {len(layers)} layers, {cursor} frames")
    return 0


def export(run: str) -> int:
    out = f"{run}/14-export"
    os.makedirs(out, exist_ok=True)
    render = f"{run}/timeline-render"
    reel = f"{render}/final.mp4"
    if not os.path.isfile(reel):
        print("export: timeline-render/final.mp4 is missing", file=sys.stderr)
        return 1
    shutil.copyfile(reel, f"{out}/reel.mp4")
    res = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-i", reel, "-t", "3", "-c", "copy", f"{out}/hook2.mp4"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if res.returncode != 0:
        print("export: hook 2 clip failed: " + res.stderr[-300:], file=sys.stderr)
        return 1
    tl = tc.read_json(f"{run}/timeline/timeline.json") or {}
    first = (tl.get("captions", {}).get("chunks") or [{}])[0].get("text", "clip")
    tc.write_json(f"{out}/export.json", {
        "written_by": "export", "caption": f"A test cut of fixture clips. First caption: {first}.", "hashtags": ["#test", "#footage", "#dummy"],
        "keyword": "CLIP", "deliverable": "none (test format)", "deliverable_status": "existing",
        "hooks": {"hook1": first, "hook2": first}, "files": {"reel": "reel.mp4", "hook2": "hook2.mp4"},
        "timeline_frames": tl.get("settings", {}).get("duration_frames")})
    print("export: reel.mp4, hook2.mp4, export.json")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("ingest", "cut", "export"):
        print(__doc__)
        return 2
    run = tc.winpath(argv[1]).rstrip("/")
    return {"ingest": ingest, "cut": cut, "export": export}[argv[0]](run)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
