"""audioio.py: the audio helpers of the sound pass (M11): WAV in and out, envelopes, loudness through ffmpeg.

  read_audio(path) -> (mono float32 array at 48 kHz, sample rate)   the wave module for PCM WAV, ffmpeg otherwise
  write_wav16(path, x, sr)                                           16-bit PCM mono, LF-free binary, atomic
  envelope_db(x, sr, hop_ms=5) -> np.ndarray                         the RMS level of each hop in dBFS (floor -120)
  peak_db(x) -> float                                                the sample peak in dBFS
  measure_loudness(path, target_i, target_tp, timeout) -> {lufs, true_peak_dbtp, lra, threshold}   ffmpeg loudnorm
  ffmpeg_filter(src, dst, af, timeout)                               run one audio filter chain (mono 48 kHz 16-bit out)
  mux(video, audio, out, timeout)                                    the video stream copied, the audio as AAC 48 kHz
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import clean, winpath  # noqa: E402

SR = 48000


def to_db(x: float, floor: float = -120.0) -> float:
    if x <= 0:
        return floor
    return max(floor, float(20.0 * math.log10(x)))


def peak_db(x: np.ndarray) -> float:
    return to_db(float(np.abs(x).max()) if len(x) else 0.0)


def _decode_ffmpeg(path: str, timeout: int) -> tuple[np.ndarray, int]:
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", winpath(path), "-map", "0:a:0", "-vn", "-f", "f32le", "-acodec", "pcm_f32le",
           "-ar", str(SR), "-ac", "1", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg cannot decode " + path + ": " + clean(r.stderr.decode("utf-8", "replace")[-200:]))
    n = len(r.stdout) // 4
    return np.frombuffer(r.stdout[: n * 4], dtype="<f4").astype(np.float32), SR


def read_audio(path: str, timeout: int = 120) -> tuple[np.ndarray, int]:
    """Mono float32 at 48 kHz (stereo averaged; another rate goes through ffmpeg)."""
    p = winpath(path)
    try:
        with wave.open(p, "rb") as w:
            ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
        if width == 2:
            x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif width == 4:
            x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        elif width == 3:
            b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
            v = np.where(v >= 1 << 23, v - (1 << 24), v)
            x = v.astype(np.float32) / 8388608.0
        elif width == 1:
            x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            raise ValueError("unsupported sample width")
        if ch > 1:
            x = x.reshape(-1, ch).mean(axis=1)
        if sr != SR:
            raise ValueError("other sample rate")
        return np.ascontiguousarray(x, dtype=np.float32), SR
    except (wave.Error, ValueError, EOFError):
        return _decode_ffmpeg(path, timeout)


def write_wav16(path: str, x: np.ndarray, sr: int = SR) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    y = np.clip(np.round(np.asarray(x, dtype=np.float64) * 32767.0), -32768, 32767).astype("<i2")
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())
    os.replace(tmp, path)


def envelope_db(x: np.ndarray, sr: int = SR, hop_ms: float = 5.0) -> np.ndarray:
    hop = max(1, int(round(sr * hop_ms / 1000.0)))
    n = len(x)
    nf = max(1, int(math.ceil(n / hop)))
    padded = np.zeros(nf * hop, dtype=np.float64)
    padded[:n] = x
    rms = np.sqrt((padded.reshape(nf, hop) ** 2).mean(axis=1))
    with np.errstate(divide="ignore"):
        env = 20.0 * np.log10(rms + 1e-12)
    return np.maximum(env, -120.0)


def measure_loudness(path: str, target_i: float = -14.0, target_tp: float = -1.5, timeout: int = 300) -> dict:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", winpath(path), "-af",
           f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:print_format=json", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    m = re.search(r"\{.*\}", r.stderr or "", re.S)
    if not m:
        raise RuntimeError(f"ffmpeg loudnorm gave no measurement for {path}: {clean((r.stderr or '')[-300:])}")
    d = json.loads(m.group(0))

    def num(key):
        try:
            v = float(d[key])
        except (KeyError, ValueError, TypeError):
            return None
        return None if math.isinf(v) or math.isnan(v) else v
    return {"lufs": num("input_i"), "true_peak_dbtp": num("input_tp"), "lra": num("input_lra"), "threshold": num("input_thresh")}


def ffmpeg_filter(src: str, dst: str, af: str, timeout: int = 300) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-y", "-i", winpath(src), "-af", af, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", winpath(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on {src}: {clean((r.stderr or '')[-300:])}")


def mux(video: str, audio: str, out: str, timeout: int = 600) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-y", "-i", winpath(video), "-i", winpath(audio), "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest", "-movflags", "+faststart", winpath(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not os.path.isfile(winpath(out)):
        raise RuntimeError(f"ffmpeg could not mux {os.path.basename(out)}: {clean((r.stderr or '')[-300:])}")
