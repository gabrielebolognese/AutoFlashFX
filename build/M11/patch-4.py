#!/usr/bin/env python
"""build/M11/patch-4.py: the sound verification made robust after the cap loop's round 4 (a record).

verify.accuracy: each sound is measured on an envelope aligned to its own start (the map measured the file from its
first sample on the same 5 ms grid, so an untouched placement reproduces the map's peak and onset exactly); a whoosh's
peak is searched only within sfx.peak_search_ms (500) of its event, so a neighbor's tail at the span's edge cannot win.
mixsfx: a correction never moves a sound by more than sfx.max_shift_ms (150); a larger disagreement means the file
cannot be read on the stem the way the map read it, so the sound swaps to the next unused file of its pool (placed and
levelled again) and, when that fails too, is left out with a NEEDS REVIEW flag instead of failing the stage.
config.json: sfx.verify_passes 5, sfx.max_shift_ms 150, sfx.peak_search_ms 500.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(ROOT)


def read(p):
    return open(p, encoding="utf-8").read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def replace_once(p, old, new, label):
    s = read(p)
    if old not in s:
        if new in s:
            print(f"{p}: already patched ({label})")
            return
        raise SystemExit(f"{p}: anchor not found ({label}): {old[:90]!r}")
    write(p, s.replace(old, new, 1))
    print(f"{p}: patched ({label})")


# 1. verify.py: the per-sound aligned envelope and the bounded peak search
p = "pipeline/lib/sfx/verify.py"
s = read(p)
old_start = s.index("def accuracy(")
old_end = s.index("    active = env >= FLOOR_DBFS")
new_body = '''def accuracy(cues: list[dict], stem: np.ndarray, sr: int, tol_ms: float, duration_ms: float, peak_search_ms: float = 500.0) -> dict:
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
        # the sound's own envelope, aligned to its first played sample: the map measured the file from its first sample
        # on the same 5 ms grid, so an untouched placement reads the same frames the map read
        s0 = int(round(start * sr / 1000.0))
        s1 = min(len(stem), int(round(end * sr / 1000.0)))
        local = envelope_db(stem[s0:s1], sr, HOP_MS) if s1 - s0 >= 48 else np.array([])
        t_of = lambda i: start + (i + 0.5) * HOP_MS  # noqa: E731  (the frame's center in reel ms)
        if len(local):
            if method == "peak":
                # the loudest frame near the event (a neighbor's tail at the span's edge cannot win); a plateau (frames
                # within 1 dB of the maximum) counts as the peak where the event falls inside it
                lo = max(0, int((expected - peak_search_ms - start) / HOP_MS))
                hi = min(len(local), int((expected + peak_search_ms - start) / HOP_MS) + 1)
                if hi <= lo:
                    lo, hi = 0, len(local)
                seg = local[lo:hi]
                mx = float(seg.max())
                top = np.where(seg >= mx - PEAK_PLATEAU_DB)[0] + lo
                centers = np.array([t_of(i) for i in top])
                j = int(np.argmin(np.abs(centers - expected)))
                measured = float(centers[j])
                if len(top) > 1:
                    note = f"plateau {round(float(centers[0]))}..{round(float(centers[-1]))} ms"
            else:
                w0 = max(0, int((expected - 40 - start) / HOP_MS))
                w1 = min(len(local), int((expected + 150 - start) / HOP_MS) + 1)
                thr = max(float(c.get("peak_dbfs", -20)) - ONSET_UNDER_PEAK_DB, FLOOR_DBFS)
                if w1 > w0:
                    if local[w0] >= thr:
                        # something already sounds at the window's start (a bed, a tail): the onset is the strongest rise
                        best, best_rise = None, 0.0
                        for i in range(max(w0, 1), w1):
                            prev = local[max(0, i - 4): i]
                            rise = float(local[i] - prev.min()) if len(prev) else 0.0
                            if local[i] >= thr and rise >= ONSET_RISE_DB and rise > best_rise:
                                best, best_rise = i, rise
                        if best is not None:
                            measured = start + best * HOP_MS
                            note = f"over a bed, rise {best_rise:.1f} dB"
                    else:
                        for i in range(w0, w1):
                            if local[i] >= thr:
                                measured = start + i * HOP_MS
                                break
                    if measured is None:
                        i = int(np.argmax(local[w0:w1])) + w0
                        measured = start + i * HOP_MS
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
'''
s = s[:old_start] + new_body + s[old_end:]
s = s.replace("""Accuracy is measured on the stem the way the map measured the files: a 5 ms RMS envelope. For a whoosh the loudest
frame inside its played span must land on the event (the peak); for every other sound the onset, the first""",
              """Accuracy is measured on the stem the way the map measured the files: a 5 ms RMS envelope aligned to each sound's own
first played sample (an untouched placement reads the frames the map read). For a whoosh the loudest frame within
sfx.peak_search_ms (500) of the event must land on it (the peak); for every other sound the onset, the first""")
write(p, s)
print(f"{p}: patched (aligned envelope, bounded peak search)")

# 2. mixsfx.py: bounded shifts, the swap and the drop
p = "pipeline/lib/sfx/mixsfx.py"
replace_once(p, '''def correct(cues: list[dict], res: dict, target_i: float, target_tp: float, corrections: list[str]) -> bool:
    """Apply the corrections a failed verification asks for. Returns True when something changed."""
    changed = False
    by_id = {c["id"]: c for c in cues}
    for r in res["accuracy"]["results"]:
        if r["ok"] or r["error_ms"] is None:
            continue
        c = by_id[r["id"]]
        shift = -float(r["error_ms"])''', '''def correct(cues: list[dict], res: dict, target_i: float, target_tp: float, corrections: list[str], max_shift_ms: float = 150.0) -> bool:
    """Apply the corrections a failed verification asks for. Returns True when something changed. A sound that misses
    by more than max_shift_ms, or misses again after a shift, is marked for a swap (run_clip picks it another file):
    a disagreement that large means the file cannot be read on the stem the way the map read it."""
    changed = False
    by_id = {c["id"]: c for c in cues}
    for r in res["accuracy"]["results"]:
        if r["ok"] or r["error_ms"] is None:
            continue
        c = by_id[r["id"]]
        if abs(float(r["error_ms"])) > max_shift_ms or c.get("_shifted"):
            c["_swap"] = True
            corrections.append(f"{c['id']} {c['cue_type']}: measured {r['error_ms']:+.0f} ms off{' again' if c.get('_shifted') else ''}: another file")
            changed = True
            continue
        c["_shifted"] = True
        shift = -float(r["error_ms"])''', "bounded shift")
replace_once(p, '''    passes = int(ctx.cfg("sfx.verify_passes", 3))
    corrections: list[str] = []
    res = None
    activity("verifying sound sync and loudness")
    mix_filter = ""
    for p in range(1, passes + 1):
        for c in cues:
            if c.pop("_reload", False):
                segments[c["id"]] = render_stem.load_segment(c, ctx.sfx_dir, segcache)
        res, stem, mix = verify_round(ctx, cues, voice, segments, stem_path, mix_path, duration_ms, target_i, target_tp)
        res["passes"] = p
        acc, vr, ld = res["accuracy"], res["voice_rule"], res["loudness"]
        log(f"{label}: pass {p}: sync {'ok' if acc['pass'] else 'NOT ok'} (max error {acc['max_error_ms']} ms, {len(acc['unplanned'])} unplanned), "
            f"voice rule {'ok' if vr['pass'] else 'NOT ok'} (closest margin {vr['min_margin_db']} dB), mix {ld['lufs']} LUFS, {ld['true_peak_dbtp']} dBTP {'ok' if ld['pass'] else 'NOT ok'}")
        if res["pass"]:
            break
        if p == passes:
            break
        if not correct(cues, res, target_i, target_tp, corrections):
            break''', '''    passes = int(ctx.cfg("sfx.verify_passes", 5))
    max_shift = float(ctx.cfg("sfx.max_shift_ms", 150))
    corrections: list[str] = []
    res = None
    activity("verifying sound sync and loudness")
    mix_filter = ""
    used_files = {c["file"] for c in cues}
    gain_offset = float(a["settings"].get("gain_offset_db", 0.0))

    def replace_or_drop(c: dict) -> str:
        """The next unused file of the cue's pool; the sound is left out when the pool has no other."""
        pool = [p for p in (pools.get(c["cue_type"]) or []) if p.get("cache") and p["path"] not in used_files and p["path"] != c["file"]]
        if not pool or c.get("_swapped"):
            return ""
        entry = pool[0]
        used_files.add(entry["path"])
        c.update({"file": entry["path"], "cache": entry["cache"], "pick_note": "swapped: the first file could not be verified",
                  "pool_entry": {k: entry.get(k) for k in ("id", "path", "cache", "gain_db", "duration_s", "onset_s", "peak_s", "end_s", "effective_s", "attack_s", "pad_start_s", "pad_end_s", "whoosh_speed", "fit", "pinned")},
                  "_swapped": True})
        c.pop("_shifted", None)
        return entry["path"]

    for p in range(1, passes + 1):
        for c in cues:
            if c.pop("_reload", False):
                segments[c["id"]] = render_stem.load_segment(c, ctx.sfx_dir, segcache)
        res, stem, mix = verify_round(ctx, cues, voice, segments, stem_path, mix_path, duration_ms, target_i, target_tp)
        res["passes"] = p
        acc, vr, ld = res["accuracy"], res["voice_rule"], res["loudness"]
        log(f"{label}: pass {p}: sync {'ok' if acc['pass'] else 'NOT ok'} (max error {acc['max_error_ms']} ms, {len(acc['unplanned'])} unplanned), "
            f"voice rule {'ok' if vr['pass'] else 'NOT ok'} (closest margin {vr['min_margin_db']} dB), mix {ld['lufs']} LUFS, {ld['true_peak_dbtp']} dBTP {'ok' if ld['pass'] else 'NOT ok'}")
        if res["pass"]:
            break
        if p == passes:
            break
        if not correct(cues, res, target_i, target_tp, corrections, max_shift):
            break
        swaps = [c for c in cues if c.pop("_swap", False)]
        if swaps:
            keep = []
            for c in swaps:
                new_file = replace_or_drop(c)
                if new_file:
                    corrections.append(f"{c['id']} {c['cue_type']}: now {os.path.basename(new_file)}")
                else:
                    dropped.append({**{k: v for k, v in c.items() if not k.startswith('_')}, "reason": "could not be verified in sync with two files of its pool"})
                    flag(f"sound: the {c['cue_type']} at {c['ms'] / 1000:.2f} s could not be placed within {ctx.cfg('sfx.sync_tolerance_ms', 33)} ms with two files and was left out")
                    corrections.append(f"{c['id']} {c['cue_type']}: left out")
                    cues = [x for x in cues if x["id"] != c["id"]]
                    segments.pop(c["id"], None)
            # the swapped sound is placed and levelled again; the neighbors' trims follow
            kept_starts = {c["id"]: (c["reel_start_ms"], c["offset_ms"]) for c in cues if not c.get("_swapped") or c in keep}
            cues = place.place(cues, int(duration_ms), ctx.config)
            for c in cues:
                if c["id"] in kept_starts and not c.get("_swapped"):
                    c["reel_start_ms"], c["offset_ms"] = kept_starts[c["id"]]   # earlier corrections of the others stay
            segments = {c["id"]: render_stem.load_segment(c, ctx.sfx_dir, segcache) for c in cues}
            cues = level.levels(cues, {cid: peak_db(seg) for cid, seg in segments.items()}, profile, ctx.config, gain_offset)''', "swap and drop")

# 3. config.json
p = "config.json"
cfg = json.loads(read(p))
changed = False
for k, v in (("verify_passes", 5), ("max_shift_ms", 150), ("peak_search_ms", 500)):
    if cfg["sfx"].get(k) != v:
        cfg["sfx"][k] = v
        changed = True
if changed:
    write(p, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    print("config.json: patched")
else:
    print("config.json: already patched")

# verify.accuracy takes the search window from the caller: mixsfx passes it
replace_once("pipeline/lib/sfx/mixsfx.py", '''    acc = verify.accuracy(cues, stem, SR, float(ctx.cfg("sfx.sync_tolerance_ms", 33)), duration_ms)''',
             '''    acc = verify.accuracy(cues, stem, SR, float(ctx.cfg("sfx.sync_tolerance_ms", 33)), duration_ms, float(ctx.cfg("sfx.peak_search_ms", 500)))''', "search window")
import subprocess
for f in ("pipeline/lib/sfx/verify.py", "pipeline/lib/sfx/mixsfx.py"):
    subprocess.run(["python", "-c", f"import ast; ast.parse(open('{f}', encoding='utf-8').read())"], check=True)
print("syntax ok")
