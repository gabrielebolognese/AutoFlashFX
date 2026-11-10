"""audio.py: the voice and every sound effect as audio clips (BUILD_SPEC.md S15 step 4, M21), and the mix of a project's audio clips.

The voice (vo.wav) and each sound of cues.json become 48 kHz mono WAV files in media/audio/ and audio clips at their exact times
with the trims (trim_in_ms, trim_out_ms), fade-outs and gains of cues.json. The final render's master gain (the mix correction
S11 recorded as master_gain_db and S13's loudness post-pass) is folded into each clip's gain, so the project's playback matches
N.mp4 within 0.5 LU. The voice goes on the first audio track, the sounds on the second (and a third when two overlap).
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import wave

import numpy as np

SR = 48000


def db_to_lin(db: float) -> float:
    return 10 ** (db / 20.0)


def to_wav48(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src.replace("\\", "/"), "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", dst.replace("\\", "/")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError(f"ffmpeg could not convert {os.path.basename(src)}: {(p.stderr or '')[-300:]}")


def wav_info(path: str) -> dict:
    with wave.open(path, "rb") as w:
        return {"frames": w.getnframes(), "rate": w.getframerate(), "channels": w.getnchannels()}


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        n, ch = w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
        width = w.getsampwidth()
    dt = {2: np.int16, 4: np.int32}[width]
    x = np.frombuffer(raw, dtype=dt).astype(np.float32) / float(2 ** (8 * width - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x


def master_gain_db(run_dir: str, cues: dict) -> float:
    """The gain the final mix got after the stem: S11's mix correction plus the gain of S13's loudness post-pass."""
    g = float(cues.get("master_gain_db") or 0.0)
    rj = os.path.join(run_dir, "13-render", "render.json")
    if os.path.isfile(rj):
        try:
            text = json.dumps(json.load(open(rj, encoding="utf-8")))
        except (OSError, ValueError):
            text = ""
        for m in re.finditer(r"gain ([+-]\d+(?:\.\d+)?) dB", text):
            g += float(m.group(1))
    return g


def ms_to_frame(ms: float, fps: float) -> int:
    return int(round(ms * fps / 1000.0))


def build(run_dir: str, project_dir: str, timeline: dict, cues: dict, voice_src: str, sfx_pack: str | None, sources: dict, fps: float, total_frames: int,
          master_db: float, clip_gain_range: tuple[float, float] = (-60.0, 12.0)) -> dict:
    """The audio of the project, from timeline.json's audio block: {"media": {id: media record}, "clips": [...], "notes": [...]}.
    Each sound plays the file S11 cut (its cache copy in the sound pack, found through cues.json by the cue id; else the pack file the timeline
    names) between trim_in_ms and trim_out_ms. Clip dicts carry "lane" (0 voice, 1.. sound effects) so the writer can place them on tracks."""
    media_dir = os.path.join(project_dir, "media", "audio")
    os.makedirs(media_dir, exist_ok=True)
    out = {"media": {}, "clips": [], "notes": []}
    lo, hi = clip_gain_range
    cache_of = {c.get("id"): c.get("cache") for c in (cues or {}).get("cues", [])}

    def clamp(g: float) -> float:
        return max(lo, min(hi, g))

    def add_media(mid: str, name: str, rel: str, abs_path: str) -> dict:
        info = wav_info(abs_path)
        rec = {"id": mid, "kind": "audio", "name": name, "file": {"relPath": rel}, "durationUs": int(round(info["frames"] * 1_000_000 / info["rate"])),
               "hasAudio": True, "codec": "pcm_s16le", "audioCodec": "pcm_s16le", "analysis": {"thumbs": "none", "peaks": "none"}, "size": os.path.getsize(abs_path)}
        out["media"][mid] = rec
        return rec

    voice = (timeline.get("audio") or {}).get("voice") or {}
    vo_rel = "media/audio/voice.wav"
    to_wav48(voice_src, os.path.join(project_dir, vo_rel))
    vrec = add_media("m-voice", "Voice", vo_rel, os.path.join(project_dir, vo_rel))
    vstart = ms_to_frame(float(voice.get("start_ms", 0)), fps)
    vdur = min(int(vrec["durationUs"]), int(round((total_frames - vstart) * 1_000_000 / fps)))
    vframes = max(1, min(total_frames - vstart, int(round(vdur * fps / 1_000_000))))
    out["clips"].append({"id": "c-voice", "lane": 0, "kind": "audio", "name": "Voice", "start": vstart, "duration": vframes, "mediaId": "m-voice", "in": 0,
                         "out": min(int(vrec["durationUs"]), int(round(vframes * 1_000_000 / fps))), "gain_db": round(clamp(master_db + float(voice.get("gain_db", 0.0))), 3), "fade_out": 0, "label": "teal"})
    seen: dict[str, str] = {}
    for c in (timeline.get("audio") or {}).get("sfx", []):
        src = None
        if sfx_pack and cache_of.get(c.get("id")):
            cand = os.path.join(sfx_pack, cache_of[c["id"]])
            if os.path.isfile(cand):
                src = cand
        if src is None:
            s0 = sources.get(c.get("source"))
            if s0 and os.path.isfile(s0):
                src = s0
        if src is None:
            out["notes"].append(f"{c.get('id')}: the sound file is missing, skipped")
            continue
        if src not in seen:
            base = re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(os.path.basename(src))[0]).strip("-")[:60] or "sfx"
            rel = f"media/audio/sfx-{base}-{len(seen) + 1}.wav"
            to_wav48(src, os.path.join(project_dir, rel))
            mid = f"m-sfx-{len(seen) + 1}"
            add_media(mid, base, rel, os.path.join(project_dir, rel))
            seen[src] = mid
        mid = seen[src]
        start_ms = float(c.get("start_ms", 0))
        tin = float(c.get("trim_in_ms", 0.0))
        tout = float(c.get("trim_out_ms", tin))
        if tout <= tin:
            continue
        start = max(0, ms_to_frame(start_ms, fps))
        dur = max(1, ms_to_frame(tout - tin, fps))
        dur = min(dur, max(1, total_frames - start))
        gain = float(c.get("gain_db", 0.0)) + master_db
        mrec = out["media"][mid]
        in_us = int(round(tin * 1000))
        out_us = min(int(mrec["durationUs"]), in_us + int(round(dur * 1_000_000 / fps)))
        if out_us <= in_us:
            continue
        out["clips"].append({"id": f"c-sfx-{c['id']}", "lane": 1, "kind": "audio", "name": f"SFX {c.get('cue_type', 'sound')}", "start": start, "duration": dur, "mediaId": mid,
                             "in": in_us, "out": out_us, "gain_db": round(clamp(gain), 3), "fade_out": ms_to_frame(float(c.get("fade_out_ms", 0.0)), fps), "label": "green",
                             "cue_id": c.get("id"), "cue_type": c.get("cue_type")})
    return out


def pack_lanes(clips: list[dict]) -> int:
    """Put the sound effect clips on lanes 1.. so no two clips of a lane overlap; returns the number of lanes."""
    ends: list[int] = []
    for c in sorted((c for c in clips if c["lane"] >= 1), key=lambda c: (c["start"], c["id"])):
        for i, e in enumerate(ends):
            if c["start"] >= e:
                c["lane"] = i + 1
                ends[i] = c["start"] + c["duration"]
                break
        else:
            ends.append(c["start"] + c["duration"])
            c["lane"] = len(ends)
    return max(1, len(ends))


def mix_project(project: dict, project_dir: str, total_frames: int) -> np.ndarray:
    """The project's audio mixed the way the editor plays it: every enabled audio clip's file between in and out, speed 1, linear fades,
    the clip's gain, summed (mono, 48 kHz)."""
    fps = project["settings"]["fps"]["num"] / project["settings"]["fps"]["den"]
    n = int(round(total_frames * SR / fps))
    mix = np.zeros(n, dtype=np.float32)
    cache: dict = {}
    for c in project["clips"].values():
        if c.get("kind") != "audio" or not c.get("enabled", True):
            continue
        tr = next((t for t in project["tracks"] if t["id"] == c["trackId"]), {})
        if tr.get("muted") or tr.get("hidden"):
            continue
        item = project["media"][c["mediaId"]]
        path = os.path.join(project_dir, item["file"]["relPath"])
        if path not in cache:
            cache[path] = read_wav(path)
        x = cache[path]
        a = int(round(c["in"] * SR / 1_000_000))
        b = a + int(round(c["duration"] * SR / fps))
        seg = np.array(x[a:b], dtype=np.float32, copy=True)
        fo = int(round(((c.get("fades") or {}).get("out", 0)) * SR / fps))
        fi = int(round(((c.get("fades") or {}).get("in", 0)) * SR / fps))
        if fo > 1 and len(seg) > fo:
            seg[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
        if fi > 1 and len(seg) > fi:
            seg[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
        g = db_to_lin(float((c.get("volume") or {}).get("gainDb", 0.0)) + float(tr.get("gainDb", 0.0) or 0.0))
        s = int(round(c["start"] * SR / fps))
        e = min(n, s + len(seg))
        if s < n:
            mix[s:e] += seg[: e - s] * g
    return mix


def loudness(path_or_wav: str) -> float | None:
    """Integrated loudness in LUFS (ffmpeg's loudnorm measurement pass), of any file with audio."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path_or_wav.replace("\\", "/"), "-vn", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr or "", re.S)
    if not m:
        return None
    try:
        return float(json.loads(m.group(0))["input_i"])
    except (ValueError, KeyError):
        return None


def write_wav(path: str, x: np.ndarray) -> None:
    y = np.clip(x, -1.0, 1.0)
    data = (y * 32767.0).astype(np.int16).tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
