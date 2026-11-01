"""render_stem.py: the sfx stem and the mix (BUILD_SPEC.md S11 steps 3 to 5, M11).

The stem is rendered in numpy from the cache copies (48 kHz, mono: a stereo file is averaged; one voice, one
channel, the phone speaker the reels play on), each sound cut at its offset and play length with its fade-out and
its gain, summed on the voice's timeline; the mix is the voice plus the stem. Loudness and true peak come from
ffmpeg's loudnorm measurement; when the mix leaves -14 LUFS plus or minus 1 or the true peak passes -1.5 dBTP the
orchestrator (mixsfx.py) lowers the stem or runs the mix through a true-peak limiter (fix_mix) and measures again.

  load_segment(cue, pack_dir) -> mono float32 (the played part, faded, before the gain)
  render(cues, segments, n_samples, sr) -> the stem (float32)
  fix_mix(src, dst, gain_db, limit_dbtp, timeout) -> the corrected mix written with ffmpeg (volume plus alimiter)
"""
from __future__ import annotations

import os

import numpy as np

from audioio import SR, ffmpeg_filter, read_audio
from level import db_to_lin


def load_segment(cue: dict, pack_dir: str, cache: dict | None = None) -> np.ndarray:
    rel = cue.get("cache") or ""
    path = os.path.join(pack_dir, rel)
    if cache is not None and path in cache:
        x = cache[path]
    else:
        x, _ = read_audio(path)
        if cache is not None:
            cache[path] = x
    a = int(round(float(cue.get("offset_ms", 0)) * SR / 1000.0))
    n = int(round(float(cue.get("play_ms", 0)) * SR / 1000.0))
    seg = np.array(x[a:a + max(0, n)], dtype=np.float32, copy=True)
    fade = int(round(float(cue.get("fade_out_ms", 0)) * SR / 1000.0))
    if fade > 1 and len(seg) > fade:
        seg[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return seg


def render(cues: list[dict], segments: dict, n_samples: int, sr: int = SR) -> np.ndarray:
    stem = np.zeros(max(1, int(n_samples)), dtype=np.float32)
    for c in cues:
        seg = segments.get(c["id"])
        if seg is None or not len(seg):
            continue
        g = db_to_lin(float(c.get("gain_db", 0.0)))
        start = int(round(float(c["reel_start_ms"]) * sr / 1000.0))
        if start >= len(stem):
            continue
        end = min(len(stem), start + len(seg))
        stem[start:end] += seg[: end - start] * g
    return stem


def fix_mix(src: str, dst: str, gain_db: float, limit_dbtp: float, timeout: int = 300) -> str:
    """A volume change and a true-peak limiter on the mix (latency compensated so nothing shifts in time)."""
    limit = 10 ** ((limit_dbtp - 0.3) / 20.0)
    af = f"volume={gain_db:.2f}dB,alimiter=limit={limit:.4f}:attack=3:release=120:level=0:latency=1"
    ffmpeg_filter(src, dst, af, timeout)
    return af
