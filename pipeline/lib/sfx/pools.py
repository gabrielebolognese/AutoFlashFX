"""pools.py: the quality filter and the pools (BUILD_SPEC.md 2.6, items 5 and 6).

Exclusions, in this order (the first reason wins; a pinned file is excluded only for a decode error):
  decode error; silent (peak under -60 dBFS); clipped (config sfx.build.quality.clip_runs or more runs of 3 or
  more full-scale samples); high noise floor (the 5th percentile of the 20 ms frame RMS within min_snr_db of the
  peak, files of min_snr_duration_s or longer); no cue type fits (the model said so); far too long for any cue type
  (effective sound over max_effective_s, unless it is typing); far too long for its candidates (over
  too_long_factor times the upper window of every candidate cue type).

Fit of a file for a cue type = category fit (1.0 for the natural use, less for a secondary one; the model's ranked
answer gives 1.0, 0.8, 0.6) x duration fit (1 inside the cue type's window, falling to 0 at twice the upper bound
and at zero length) x attack fit (sharp cue types want the peak within 30 ms of the onset, swells want it 200 ms
or more after) x quality (small penalties for full-scale runs and a noise floor within 45 dB) x the confidence.
A pool keeps the files with fit at or over min_fit, best first, pinned files first of all, at most pool_size[1];
a pool under min_pool sounds is short (HUMAN_TODO). Low-confidence files (under min_confidence, model answers
only) wait for a pin.

  settings_from_config(sfx_cfg) -> the merged settings
  exclusion_reason(f, settings, pinned) -> str | None
  file_fit(f, cue, settings) -> float
  build_pools(files, settings, resolved_overrides) -> (pools, waiting, unclassified, short)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import DEFAULT_WHOOSH  # noqa: E402
from common import CUE_ATTACK, CUE_TYPES, CUE_WINDOWS, clean  # noqa: E402

DEFAULT_BUILD = {
    "pool_size": [5, 8],
    "min_pool": 3,
    "min_confidence": 0.6,
    "min_fit": 0.25,
    "preview_gap_s": 1.0,
    "whoosh": dict(DEFAULT_WHOOSH),
    "quality": {"clip_runs": 10, "min_snr_db": 30.0, "min_snr_duration_s": 0.5, "too_long_factor": 2.0,
                "max_effective_s": 5.0, "silent_dbfs": -60.0},
    "cue_windows": {k: list(v) for k, v in CUE_WINDOWS.items()},
}


def settings_from_config(sfx_cfg: dict | None) -> dict:
    sfx_cfg = sfx_cfg or {}
    build = sfx_cfg.get("build") or {}
    s = {
        "normalize_peak_dbfs": float(sfx_cfg.get("normalize_peak_dbfs", -12.0)),
        "pool_size": list(build.get("pool_size", DEFAULT_BUILD["pool_size"])),
        "min_pool": int(build.get("min_pool", DEFAULT_BUILD["min_pool"])),
        "min_confidence": float(build.get("min_confidence", DEFAULT_BUILD["min_confidence"])),
        "min_fit": float(build.get("min_fit", DEFAULT_BUILD["min_fit"])),
        "preview_gap_s": float(build.get("preview_gap_s", DEFAULT_BUILD["preview_gap_s"])),
        "whoosh": dict(DEFAULT_BUILD["whoosh"]),
        "quality": dict(DEFAULT_BUILD["quality"]),
        "cue_windows": {k: list(v) for k, v in DEFAULT_BUILD["cue_windows"].items()},
    }
    s["whoosh"].update({k: float(v) for k, v in (build.get("whoosh") or {}).items()})
    s["quality"].update({k: float(v) for k, v in (build.get("quality") or {}).items()})
    for k, v in (build.get("cue_windows") or {}).items():
        if k in CUE_TYPES and isinstance(v, (list, tuple)) and len(v) == 2:
            s["cue_windows"][k] = [float(v[0]), float(v[1])]
    return s


def windows_of(settings: dict) -> dict[str, tuple[float, float]]:
    return {k: (float(v[0]), float(v[1])) for k, v in settings["cue_windows"].items()}


def hard_exclusion(f: dict, settings: dict) -> str | None:
    """The exclusions that follow from the measurements alone (no classification needed): a decode error, silence,
    clipping, a high noise floor, far too long for any cue type. A file with one of these is never sent to the
    model."""
    q = settings["quality"]
    if f.get("decode_error"):
        return f"cannot be decoded ({f['decode_error']})"
    peak = f.get("peak_dbfs")
    if peak is None or float(peak) < float(q["silent_dbfs"]):
        return "silent (peak under -60 dBFS)"
    if int(f.get("clip_runs") or 0) >= int(q["clip_runs"]):
        return f"clipped ({int(f['clip_runs'])} runs of full-scale samples)"
    snr = f.get("snr_db")
    dur = float(f.get("duration_s") or 0.0)
    if snr is not None and float(snr) < float(q["min_snr_db"]) and dur >= float(q["min_snr_duration_s"]):
        return f"high noise floor ({float(snr):.0f} dB under the peak)"
    eff = float(f.get("effective_s") or 0.0)
    if eff > float(q["max_effective_s"]) and "typing" not in (f.get("candidates") or {}):
        return f"far too long for any cue type (effective sound {eff:.1f} s)"
    return None


def exclusion_reason(f: dict, settings: dict, pinned: bool = False) -> str | None:
    q = settings["quality"]
    if f.get("decode_error"):
        return f"cannot be decoded ({f['decode_error']})"
    if pinned:
        return None
    hard = hard_exclusion(f, settings)
    if hard:
        return hard
    cands = f.get("candidates") or {}
    eff = float(f.get("effective_s") or 0.0)
    if f.get("source") == "model" and not cands:
        note = (f.get("model") or {}).get("note") or ""
        return "no cue type fits" + (f" (model: {clean(note)})" if note else "")
    if cands:
        windows = windows_of(settings)
        hi = max(windows.get(c, (0.0, 2.5))[1] for c in cands)
        if eff > float(q["too_long_factor"]) * hi:
            return f"far too long for {', '.join(cands)} (effective sound {eff:.1f} s, window up to {hi:.1f} s)"
    return None


def duration_fit(eff: float, lo: float, hi: float) -> float:
    if eff <= 0:
        return 0.0
    if eff < lo:
        return max(0.0, min(1.0, eff / lo))
    if eff > hi:
        return max(0.0, 1.0 - (eff - hi) / hi)
    return 1.0


def attack_fit(f: dict, cue: str) -> float:
    want = CUE_ATTACK.get(cue, "any")
    attack = float(f.get("attack_s") or 0.0)
    if want == "sharp":
        return 1.0 if attack <= 0.03 else (0.8 if attack <= 0.08 else 0.5)
    if want == "swell":
        return 1.0 if attack >= 0.2 else (0.8 if attack >= 0.1 else 0.6)
    return 1.0


def quality_factor(f: dict) -> float:
    q = 1.0 - min(0.15, 0.02 * int(f.get("clip_runs") or 0))
    snr = f.get("snr_db")
    if snr is not None and float(snr) < 45.0:
        q -= 0.1
    return max(0.1, q)


def file_fit(f: dict, cue: str, settings: dict) -> float:
    cat = float((f.get("candidates") or {}).get(cue, 0.0))
    if cat <= 0:
        return 0.0
    lo, hi = windows_of(settings).get(cue, (0.0, 2.5))
    conf = float(f.get("confidence", 1.0)) if f.get("source") == "model" else 1.0
    fit = cat * duration_fit(float(f.get("effective_s") or 0.0), lo, hi) * attack_fit(f, cue) * quality_factor(f) * conf
    return round(max(0.0, min(1.0, fit)), 3)


def pool_entry(f: dict, cue: str, fit: float, pinned: bool) -> dict:
    return {
        "id": f["id"], "path": f["path"], "cache": f.get("cache"), "gain_db": f.get("gain_db"),
        "duration_s": f.get("duration_s"), "onset_s": f.get("onset_s"), "peak_s": f.get("peak_s"),
        "end_s": f.get("end_s"), "effective_s": f.get("effective_s"), "attack_s": f.get("attack_s"),
        "pad_start_s": f.get("pad_start_s"), "pad_end_s": f.get("pad_end_s"),
        "whoosh_speed": f.get("whoosh_speed"), "fit": fit, "pinned": pinned, "source": f.get("source"),
        "confidence": f.get("confidence"),
    }


def build_pools(files: list[dict], settings: dict, resolved: dict) -> tuple[dict, list, list, list]:
    banned = resolved.get("banned", {})
    pinned = resolved.get("pinned", {})
    pins_by_id = resolved.get("pins_by_id", {})
    by_id = {f["id"]: f for f in files}
    pool_max = int(settings["pool_size"][1])
    min_conf = float(settings["min_confidence"])
    min_fit = float(settings["min_fit"])

    # the derived fields on every file
    for f in files:
        is_pinned = f["id"] in pins_by_id
        f["banned"] = f["id"] in banned
        f["pinned"] = list(pins_by_id.get(f["id"], []))
        f["excluded"] = exclusion_reason(f, settings, pinned=is_pinned and not f["banned"])
        f["unclassified"] = bool(f.get("unclear")) and not f.get("model") and not f["excluded"]
        f["waiting"] = (not f["excluded"] and not f["banned"] and f.get("source") == "model"
                        and bool(f.get("candidates")) and float(f.get("confidence", 0.0)) < min_conf
                        and not is_pinned)
        f["fit"] = {cue: file_fit(f, cue, settings) for cue in (f.get("candidates") or {})}
        notes = []
        runs = int(f.get("clip_runs") or 0)
        if 0 < runs < int(settings["quality"]["clip_runs"]):
            notes.append(f"{runs} short full-scale run{'s' if runs != 1 else ''}")
        if f.get("gain_db") is not None and float(f["gain_db"]) >= 8:
            notes.append(f"quiet master, gain +{float(f['gain_db']):.0f} dB")
        if f.get("true_peak_dbtp") is not None and float(f["true_peak_dbtp"]) > 0:
            notes.append(f"true peak +{float(f['true_peak_dbtp']):.1f} dBTP in the original")
        if is_pinned and f["excluded"] is None and not f.get("decode_error"):
            reason = exclusion_reason(f, settings, pinned=False)
            if reason:
                notes.append(f"pinned by overrides.txt despite: {reason}")
        f["notes"] = notes

    pools: dict[str, list[dict]] = {}
    for cue in CUE_TYPES:
        entries: list[dict] = []
        used: set[str] = set()
        for fid in pinned.get(cue, []):
            f = by_id.get(fid)
            if f is None or f["excluded"] or f["banned"] or fid in used:
                continue
            fit = f["fit"].get(cue) or file_fit(f, cue, settings) or 0.0
            entries.append(pool_entry(f, cue, fit, True))
            used.add(fid)
        candidates = []
        for f in files:
            if f["id"] in used or f["excluded"] or f["banned"] or f.get("waiting") or f.get("unclassified"):
                continue
            fit = f["fit"].get(cue, 0.0)
            if fit >= min_fit:
                candidates.append((fit, f["path"].lower(), f))
        candidates.sort(key=lambda t: (-t[0], t[1]))
        for fit, _, f in candidates:
            if len(entries) >= pool_max:
                break
            entries.append(pool_entry(f, cue, fit, False))
        pools[cue] = entries

    waiting = [{"id": f["id"], "path": f["path"], "cue_types": list((f.get("candidates") or {}).keys()),
                "confidence": f.get("confidence"), "note": (f.get("model") or {}).get("note", "")}
               for f in files if f.get("waiting")]
    unclassified = [{"id": f["id"], "path": f["path"]} for f in files if f.get("unclassified")]
    short = [cue for cue in CUE_TYPES if len(pools[cue]) < int(settings["min_pool"])]
    return pools, waiting, unclassified, short
