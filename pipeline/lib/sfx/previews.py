"""previews.py: styles/sfx/previews/<cue type>.wav and .txt (BUILD_SPEC.md 2.6, item 8).

Every pool's sounds, from the normalized cache copies, trimmed to their audible part (the silence padding under
-60 dBFS at both ends, 20 ms kept) and spaced preview_gap_s (1 s) apart, as one 48 kHz 16-bit WAV; the text file
lists them in order with the time each one starts. Previews of cue types whose pool is empty are removed.

  render_all(pack_dir, pools, files_by_id, previews_dir, gap_s) -> {cue: {"sounds": n, "duration_s": x}}
  preview_ok(previews_dir, pools) -> the cue types whose preview wav or txt is missing
"""
from __future__ import annotations

import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CUE_TYPES, save_text, winpath  # noqa: E402

SR = 48000


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(winpath(path), "rb") as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError(f"{path}: expected 16-bit PCM, got {width * 8}-bit")
    x = np.frombuffer(raw, dtype="<i2").reshape(-1, ch)
    return x, sr


def write_wav(path: str, x: np.ndarray, sr: int = SR) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.ascontiguousarray(x.astype("<i2")).tobytes())
    os.replace(tmp, path)


def trimmed(x: np.ndarray, sr: int, f: dict, margin_s: float = 0.02) -> np.ndarray:
    start = max(0.0, float(f.get("pad_start_s") or 0.0) - margin_s)
    end_pad = max(0.0, float(f.get("pad_end_s") or 0.0) - margin_s)
    a = int(start * sr)
    b = len(x) - int(end_pad * sr)
    if b - a < sr // 100:
        return x
    return x[a:b]


def render_preview(pack_dir: str, cue: str, pool: list[dict], files_by_id: dict, out_wav: str, out_txt: str,
                   gap_s: float = 1.0) -> dict:
    pieces: list[np.ndarray] = []
    lines: list[str] = []
    t = 0.0
    stereo = False
    chunks: list[tuple[np.ndarray, dict]] = []
    for entry in pool:
        f = files_by_id.get(entry["id"], {})
        cache = entry.get("cache")
        if not cache:
            continue
        try:
            x, sr = read_wav(os.path.join(pack_dir, cache))
        except (OSError, ValueError, wave.Error):
            continue
        x = trimmed(x, sr, f)
        stereo = stereo or x.shape[1] >= 2
        chunks.append((x, entry))
    gap = np.zeros((int(gap_s * SR), 2 if stereo else 1), dtype="<i2")
    for i, (x, entry) in enumerate(chunks, start=1):
        if stereo and x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        elif not stereo and x.shape[1] > 1:
            x = x[:, :1]
        if pieces:
            pieces.append(gap)
            t += gap_s
        pieces.append(x)
        extra = []
        if entry.get("pinned"):
            extra.append("pinned")
        if entry.get("whoosh_speed"):
            extra.append(f"{entry['whoosh_speed']} whoosh")
        if entry.get("source") == "model":
            extra.append(f"model, confidence {float(entry.get('confidence') or 0):.2f}")
        lines.append(f"{i}. at {t:6.2f} s  {entry['path']}  ({float(entry.get('effective_s') or 0):.2f} s of sound, "
                     f"fit {float(entry.get('fit') or 0):.2f}, gain {float(entry.get('gain_db') or 0):+.1f} dB"
                     + (", " + ", ".join(extra) if extra else "") + ")")
        t += len(x) / SR
    if not pieces:
        return {"sounds": 0, "duration_s": 0.0}
    audio = np.concatenate(pieces, axis=0)
    write_wav(out_wav, audio)
    header = (f"# previews/{cue}.wav: the {cue} pool ({len(chunks)} sounds, {gap_s:.0f} s apart), best fit first. "
              f"To ban or pin one, write a line in styles/sfx/overrides.txt and run bash pipeline/bin/build-sfx-map.\n"
              f"# {cue}: {CUE_TYPES.get(cue, '')}\n")
    save_text(out_txt, header + "\n".join(lines) + "\n")
    return {"sounds": len(chunks), "duration_s": round(len(audio) / SR, 2)}


def render_all(pack_dir: str, pools: dict, files_by_id: dict, previews_dir: str, gap_s: float = 1.0) -> dict:
    out = {}
    os.makedirs(winpath(previews_dir), exist_ok=True)
    for cue in CUE_TYPES:
        wav = os.path.join(previews_dir, f"{cue}.wav")
        txt = os.path.join(previews_dir, f"{cue}.txt")
        pool = pools.get(cue) or []
        if not pool:
            for p in (wav, txt):
                try:
                    os.remove(winpath(p))
                except OSError:
                    pass
            continue
        out[cue] = render_preview(pack_dir, cue, pool, files_by_id, wav, txt, gap_s)
    return out


def missing_previews(previews_dir: str, pools: dict) -> list[str]:
    missing = []
    for cue in CUE_TYPES:
        if not pools.get(cue):
            continue
        if not (os.path.isfile(winpath(os.path.join(previews_dir, f"{cue}.wav")))
                and os.path.isfile(winpath(os.path.join(previews_dir, f"{cue}.txt")))):
            missing.append(cue)
    return missing
