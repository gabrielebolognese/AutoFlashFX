"""place.py: where each sound starts and how much of it plays (BUILD_SPEC.md S11 step 3, M11).

A whoosh (transition_slow, transition_fast, attention, hook_hit) is placed so its peak lands on the event; everything
else so its onset lands on it. The map measured both on the cache copy's timeline (onset_s, peak_s, end_s,
duration_s). A file whose anchor comes later than the event allows (a pop with a second of silence before it, an event
in the first frames) starts inside the file (offset_ms). A sound plays until its audible end (end_s plus 60 ms, inside
the file), a typing bed until its segment ends (end_ms; a shorter file plays once, never looped), and a tail that runs
into the next sound's audible start is cut config sfx.tail_guard_ms (50) before it, so the next onset has a clean
lead-in; every cut inside the file gets a config sfx.fade_ms (30) fade-out.

  place(cues, duration_ms, config) -> the cues with anchor, reel_start_ms, offset_ms, play_ms, fade_out_ms, trim
  audible_start_ms(cue) -> when the sound becomes audible in the reel
"""
from __future__ import annotations

from assign import WHOOSH_CUES, cfg

TAIL_ALLOWANCE_S = 0.06


def audible_start_ms(c: dict) -> float:
    e = c["pool_entry"]
    return c["ms"] - (float(c["anchor_s"]) - float(e.get("onset_s") or 0.0)) * 1000.0


def place(cues: list[dict], duration_ms: int, config: dict) -> list[dict]:
    fade_ms = float(cfg(config, "sfx.fade_ms", 30))
    guard_ms = float(cfg(config, "sfx.tail_guard_ms", 50))
    cues = sorted(cues, key=lambda c: c["ms"])
    for c in cues:
        e = c["pool_entry"]
        onset = float(e.get("onset_s") or 0.0)
        peak = float(e.get("peak_s") or onset)
        c["anchor"] = "peak" if c["cue_type"] in WHOOSH_CUES else "onset"
        c["anchor_s"] = peak if c["anchor"] == "peak" else onset
        reel_start = c["ms"] - c["anchor_s"] * 1000.0
        offset_s = 0.0
        if reel_start < 0:
            offset_s = -reel_start / 1000.0
            reel_start = 0.0
        file_len = float(e.get("duration_s") or 0.0)
        audible_end_file = min(file_len, float(e.get("end_s") or file_len) + TAIL_ALLOWANCE_S)
        natural_end = reel_start + max(0.0, audible_end_file - offset_s) * 1000.0
        trim = ""
        end = natural_end
        if c["cue_type"] == "typing" and c.get("end_ms"):
            seg_end = float(c["end_ms"])
            if seg_end < end:
                end, trim = seg_end, "the typing segment"
        c["reel_start_ms"] = round(reel_start, 3)
        c["offset_ms"] = round(offset_s * 1000.0, 3)
        c["_end_ms"] = end
        c["trim"] = trim
    for i, c in enumerate(cues):
        nxt = cues[i + 1] if i + 1 < len(cues) else None
        end = c["_end_ms"]
        if nxt is not None:
            nxt_start = audible_start_ms(nxt) - guard_ms   # the next onset gets a short clean lead-in
            if end > nxt_start and nxt_start > c["reel_start_ms"]:
                end, c["trim"] = nxt_start, f"the next sound ({nxt['cue_type']} at {nxt['ms']} ms)"
        if end > duration_ms:
            end, c["trim"] = float(duration_ms), "the end of the reel"
        c["play_ms"] = round(max(0.0, end - c["reel_start_ms"]), 3)
        file_len_ms = float(c["pool_entry"].get("duration_s") or 0.0) * 1000.0
        cut_inside = (c["offset_ms"] + c["play_ms"]) < file_len_ms - 1.0
        c["fade_out_ms"] = round(min(fade_ms, c["play_ms"] / 2.0), 3) if cut_inside else 0.0
        del c["_end_ms"]
    return cues
