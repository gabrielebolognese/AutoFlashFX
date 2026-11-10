"""Shared helpers of the timeline package (BUILD_SPEC.md 14.8, M20): reading JSON, frames and milliseconds, ffprobe, checksums,
the source registry and the Windows path forms."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import paths  # noqa: E402

REPO = paths.REPO
SCHEMA = REPO + "/pipeline/schemas/timeline.schema.json"
TIMELINE_DIR = "timeline"
TIMELINE_FILE = "timeline.json"
EM_DASH = chr(0x2014)


def winpath(path: str) -> str:
    """/c/Users/... from Git Bash to C:/Users/... for Windows Python and ffmpeg."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    if m and os.name == "nt":
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return (path or "").replace("\\", "/")


def read_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, data) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def ms_to_frame(ms: float, fps: float) -> int:
    return int(round(float(ms) * fps / 1000.0))


def frame_to_ms(frame: float, fps: float) -> int:
    return int(round(float(frame) * 1000.0 / fps))


def fps_of(timeline: dict) -> float:
    f = timeline["settings"]["fps"]
    return f["num"] / f["den"]


def sha256_of(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(winpath(path), "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def probe(path: str) -> dict:
    """ffprobe of a media file: {duration, width, height, fps, sample_rate, has_audio, has_video}; empty when it fails."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", winpath(path)],
                             capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        data = json.loads(out.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    info: dict = {"duration": None, "width": None, "height": None, "fps": None, "sample_rate": None, "has_audio": False, "has_video": False}
    try:
        info["duration"] = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        pass
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video" and not info["has_video"] and s.get("codec_name") not in ("png", "mjpeg"):
            info.update(has_video=True, width=s.get("width"), height=s.get("height"))
            rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
            try:
                a, b = rate.split("/")
                info["fps"] = float(a) / float(b) if float(b) else None
            except (ValueError, ZeroDivisionError):
                pass
            if info["duration"] is None:
                try:
                    info["duration"] = float(s.get("duration"))
                except (TypeError, ValueError):
                    pass
        elif s.get("codec_type") == "audio" and not info["has_audio"]:
            info["has_audio"] = True
            try:
                info["sample_rate"] = int(s.get("sample_rate"))
            except (TypeError, ValueError):
                pass
    return info


class Sources:
    """The source registry of a timeline: add(path, kind, ...) gives a stable id, one entry per file."""

    def __init__(self, run_dir: str, channel_root: str = ""):
        self.run_dir = winpath(run_dir).rstrip("/")
        self.channel_root = winpath(channel_root).rstrip("/")
        self.items: list[dict] = []
        self.by_path: dict[str, str] = {}

    def locate(self, path: str) -> tuple[str, str]:
        """(base, relative path) of a file: inside the run folder, inside the channel folder, else absolute."""
        full = winpath(path)
        if not os.path.isabs(full) and not re.match(r"^[A-Za-z]:/", full):
            return "run", full
        norm = os.path.normcase(os.path.abspath(full)).replace("\\", "/")
        for base, root in (("run", self.run_dir), ("channel", self.channel_root)):
            if root and norm.startswith(os.path.normcase(os.path.abspath(root)).replace("\\", "/") + "/"):
                return base, os.path.relpath(full, root).replace("\\", "/")
        return "abs", full

    def resolve(self, base: str, rel: str) -> str:
        if base == "run":
            return f"{self.run_dir}/{rel}"
        if base == "channel":
            return f"{self.channel_root}/{rel}"
        return rel

    def add(self, path: str, kind: str, role: str = "", prefix: str = "src", hash_it: bool = True, media: bool = True) -> str:
        base, rel = self.locate(path)
        key = f"{base}:{rel}"
        if key in self.by_path:
            return self.by_path[key]
        used = {i["id"] for i in self.items}
        sid = role if (role and role not in used) else f"{prefix}{len(self.items) + 1}"
        full = self.resolve(base, rel)
        entry: dict = {"id": sid, "path": rel, "base": base, "kind": kind}
        if role:
            entry["role"] = role
        exists = os.path.isfile(full)
        entry["size"] = os.path.getsize(full) if exists else None
        entry["sha256"] = sha256_of(full) if (exists and hash_it) else None
        dur = w = h = None
        if exists and media and kind in ("video", "audio", "image"):
            p = probe(full)
            dur, w, h = p.get("duration"), p.get("width"), p.get("height")
            if kind == "image":
                dur = None
        entry["duration_s"] = round(dur, 3) if dur else None
        entry["width"], entry["height"] = w, h
        self.items.append(entry)
        self.by_path[key] = sid
        return sid

    def path_of(self, sid: str) -> str:
        for it in self.items:
            if it["id"] == sid:
                return self.resolve(it["base"], it["path"])
        raise KeyError(sid)


def undash(text: str) -> str:
    return str(text).replace(EM_DASH, ", ").replace(chr(0x2013), "-")
