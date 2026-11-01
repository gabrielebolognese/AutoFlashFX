"""level.py: the gain of each sound (BUILD_SPEC.md S11 step 4, M11).

The cache copies already carry the map's normalization (every file peaks at config sfx.normalize_peak_dbfs, -12 dBFS),
so a sound's level is that reference plus the cue type's base gain (config sfx.base_gain_db) plus the round's offset
(an edit review that found the sounds loud or soft, assign.apply_feedback), capped so that its peak sits at least
config sfx.min_db_under_voice (8) dB under the voice's peak around that moment: the voice's sample peak within
config sfx.voice_window_ms (600) of the event, never taken lower than the reel's overall voice peak minus
sfx.voice_floor_under_peak_db (12), so a sound in a pause or in the hook breath is not pushed into silence. The gain
is computed from the played segment's own peak (a typing bed cut from the middle of a file peaks lower than the file).

  voice_profile(x, sr) -> {"overall_peak_dbfs", "frame_peaks" (5 ms sample peaks in dBFS), "hop"}
  voice_ref_dbfs(profile, ms, window_ms, floor_under_db) -> the reference level for an event
  levels(cues, seg_peaks, profile, config, gain_offset_db=0.0) -> the cues with the gain fields
"""
from __future__ import annotations

import math

import numpy as np

from assign import cfg
from audioio import to_db


def voice_profile(x: np.ndarray, sr: int, hop_ms: float = 5.0) -> dict:
    hop = max(1, int(round(sr * hop_ms / 1000.0)))
    n = len(x)
    nf = max(1, int(math.ceil(n / hop)))
    padded = np.zeros(nf * hop, dtype=np.float32)
    padded[:n] = np.abs(x)
    peaks = padded.reshape(nf, hop).max(axis=1)
    with np.errstate(divide="ignore"):
        peaks_db = np.maximum(20.0 * np.log10(peaks + 1e-12), -120.0)
    overall = float(peaks_db.max()) if nf else -120.0
    return {"overall_peak_dbfs": round(overall, 2), "frame_peaks": peaks_db, "hop": hop, "sr": sr, "duration_ms": n * 1000.0 / sr}


def voice_ref_dbfs(profile: dict, ms: float, window_ms: float, floor_under_db: float) -> tuple[float, str]:
    peaks = profile["frame_peaks"]
    hop_ms = profile["hop"] * 1000.0 / profile["sr"]
    a = max(0, int((ms - window_ms) / hop_ms))
    b = min(len(peaks), int((ms + window_ms) / hop_ms) + 1)
    local = float(peaks[a:b].max()) if b > a else -120.0
    floor = profile["overall_peak_dbfs"] - floor_under_db
    if local < floor:
        return round(floor, 2), "the voice is quiet there: the overall peak minus the floor"
    return round(local, 2), "the voice peak within the window"


def levels(cues: list[dict], seg_peaks: dict, profile: dict, config: dict, gain_offset_db: float = 0.0) -> list[dict]:
    base = cfg(config, "sfx.base_gain_db", {}) or {}
    norm_peak = float(cfg(config, "sfx.normalize_peak_dbfs", -12))
    under = float(cfg(config, "sfx.min_db_under_voice", 8))
    window = float(cfg(config, "sfx.voice_window_ms", 600))
    floor_under = float(cfg(config, "sfx.voice_floor_under_peak_db", 12))
    for c in cues:
        b = float(base.get(c["cue_type"], -10))
        ref, how = voice_ref_dbfs(profile, c["ms"], window, floor_under)
        cap = ref - under
        wanted = norm_peak + b + gain_offset_db
        target = min(wanted, cap)
        seg_peak = float(seg_peaks.get(c["id"], norm_peak))
        gain = target - seg_peak if seg_peak > -119 else 0.0
        c.update({"base_gain_db": b, "gain_offset_db": round(gain_offset_db, 2), "voice_ref_dbfs": ref, "voice_ref_how": how,
                  "voice_cap_dbfs": round(cap, 2), "seg_peak_dbfs": round(seg_peak, 2), "target_peak_dbfs": round(target, 2),
                  "capped_by_voice": bool(wanted > cap + 1e-9), "gain_db": round(gain, 2), "peak_dbfs": round(seg_peak + gain, 2)})
    return cues


def db_to_lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def lin_to_db(v: float) -> float:
    return to_db(v)
