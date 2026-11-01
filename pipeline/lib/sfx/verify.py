"""verify.py: accuracy and loudness of the rendered stem and mix (BUILD_SPEC.md S11 step 5, M11).

Accuracy is measured on the stem the way the map measured the files: a 5 ms RMS envelope. For a whoosh the loudest
frame inside its played span must land on the event (the peak); for every other sound the onset, the first frame of
its window (40 ms before the event to 150 ms after) that reaches 30 dB under the sound's expected peak and rises
6 dB over the 20 ms before it (so a click over a typing bed is still found at its own attack). Both within config
sfx.sync_tolerance_ms (33 ms, one frame). Unplanned sound: any stretch of the stem above -55 dBFS that no planned sound
covers (its span plus 40 ms). The voice rule: the stem's peak inside each sound's span against that sound's cap
(the voice reference minus 8 dB). Loudness: the mix's integrated LUFS within -14 plus or minus 1 and its true peak at
most -1.5 dBTP (measured by the orchestrator with ffmpeg loudnorm and passed in).

  accuracy(cues, stem, sr, tol_ms) -> {"pass", "checked", "max_error_ms", "results": [...], "unplanned": [...]}
  voice_rule(cues, stem, sr, under_db) -> {"pass", "min_margin_db", "results": [...]}
  loudness(measured, target_i, target_tp) -> {"pass", "lufs", "true_peak_dbtp", ...}
"""
from __future__ import annotations

import numpy as np

from assign import WHOOSH_CUES
from audioio import envelope_db, to_db

HOP_MS = 5.0
FLOOR_DBFS = -55.0
ONSET_UNDER_PEAK_DB = 30.0
ONSET_RISE_DB = 6.0
PEAK_PLATEAU_DB = 1.0


def _frame(ms: float) -> int:
    return int(ms / HOP_MS)


def accuracy(cues: list[dict], stem: np.ndarray, sr: int, tol_ms: float, duration_ms: float) -> dict:
    env = envelope_db(stem, sr, HOP_MS)
    results = []
    max_err = 0.0
    covered = np.zeros(len(env), dtype=bool)
    for c in sorted(cues, key=lambda c: c["ms"]):
        start = float(c["reel_start_ms"])
        end = start + float(c.get("play_ms", 0))
        a, b = max(0, _frame(start)), min(len(env), _frame(end) + 1)
        covered[max(0, a - _frame(40)): min(len(env), b + _frame(40))] = True
        expected = float(c["ms"])
        method = "peak" if c["cue_type"] in WHOOSH_CUES else "onset"
        measured = None
        note = ""
        if b > a:
            if method == "peak":
                # the loudest frame of the span; a whoosh whose loudest stretch is a plateau (frames within 1 dB of the
                # maximum) lands when the event falls inside that stretch: the nearest plateau frame is the measurement
                seg = env[a:b]
                mx = float(seg.max())
                top = np.where(seg >= mx - PEAK_PLATEAU_DB)[0] + a
                centers = (top + 0.5) * HOP_MS
                j = int(np.argmin(np.abs(centers - expected)))
                measured = float(centers[j])
                if len(top) > 1:
                    note = f"plateau {round(float(centers[0]))}..{round(float(centers[-1]))} ms"
            else:
                w0, w1 = max(a, _frame(expected - 40)), min(b, _frame(expected + 150) + 1)
                thr = max(float(c.get("peak_dbfs", -20)) - ONSET_UNDER_PEAK_DB, FLOOR_DBFS)
                if w1 > w0:
                    if env[w0] >= thr:
                        # something already sounds at the window's start (a bed, a tail): the onset is the strongest rise
                        best, best_rise = None, 0.0
                        for i in range(max(w0, 1), w1):
                            prev = env[max(0, i - 4): i]
                            rise = float(env[i] - prev.min()) if len(prev) else 0.0
                            if env[i] >= thr and rise >= ONSET_RISE_DB and rise > best_rise:
                                best, best_rise = i, rise
                        if best is not None:
                            measured = best * HOP_MS
                            note = f"over a bed, rise {best_rise:.1f} dB"
                    else:
                        for i in range(w0, w1):
                            if env[i] >= thr:
                                measured = i * HOP_MS
                                break
                    if measured is None:
                        i = int(np.argmax(env[w0:w1])) + w0
                        measured = i * HOP_MS
                        note = "no clear onset: the loudest frame of the window"
        err = None if measured is None else round(measured - expected, 1)
        ok = err is not None and abs(err) <= tol_ms
        if err is not None:
            max_err = max(max_err, abs(err))
        r = {"id": c["id"], "cue_type": c["cue_type"], "expected_ms": expected, "measured_ms": None if measured is None else round(measured, 1),
             "error_ms": err, "method": method, "ok": bool(ok)}
        if note:
            r["note"] = note
        results.append(r)
    active = env >= FLOOR_DBFS
    stray = active & ~covered
    unplanned = []
    i = 0
    n = len(env)
    while i < n:
        if stray[i]:
            j = i
            while j < n and stray[j]:
                j += 1
            if (j - i) * HOP_MS >= 30:
                unplanned.append({"start_ms": round(i * HOP_MS, 1), "end_ms": round(j * HOP_MS, 1), "peak_dbfs": round(float(env[i:j].max()), 1)})
            i = j
        else:
            i += 1
    return {"pass": all(r["ok"] for r in results) and not unplanned, "checked": len(results), "max_error_ms": round(max_err, 1),
            "tolerance_ms": tol_ms, "results": results, "unplanned": unplanned}


def voice_rule(cues: list[dict], stem: np.ndarray, sr: int, under_db: float, tolerance_db: float = 0.5) -> dict:
    results = []
    margins = []
    for c in cues:
        a = int(float(c["reel_start_ms"]) * sr / 1000.0)
        b = min(len(stem), a + int(float(c.get("play_ms", 0)) * sr / 1000.0))
        pk = to_db(float(np.abs(stem[a:b]).max()) if b > a else 0.0)
        cap = float(c.get("voice_ref_dbfs", 0.0)) - under_db
        margin = cap - pk
        margins.append(margin)
        results.append({"id": c["id"], "cue_type": c["cue_type"], "stem_peak_dbfs": round(pk, 2), "voice_ref_dbfs": c.get("voice_ref_dbfs"), "cap_dbfs": round(cap, 2),
                        "margin_db": round(margin, 2), "ok": bool(margin >= -tolerance_db)})
    return {"pass": all(r["ok"] for r in results), "min_margin_db": round(min(margins), 2) if margins else None, "under_db": under_db, "results": results}


def loudness(measured: dict, target_i: float, target_tp: float, tol_i: float = 1.0, tol_tp: float = 0.05) -> dict:
    lufs = measured.get("lufs")
    tp = measured.get("true_peak_dbtp")
    ok_i = lufs is not None and abs(lufs - target_i) <= tol_i
    ok_tp = tp is not None and tp <= target_tp + tol_tp
    return {"pass": bool(ok_i and ok_tp), "lufs": lufs, "true_peak_dbtp": tp, "target_lufs": target_i, "target_true_peak_dbtp": target_tp,
            "lufs_ok": bool(ok_i), "true_peak_ok": bool(ok_tp)}
