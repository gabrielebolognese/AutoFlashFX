"""pipeline/lib/review/energy.py: the energy meter of the Motion and energy rules, E0 (BUILD_SPEC.md section 5, M14).

A video (a draft, a final render, a reference reel) is read at 30 fps as a 108x192 grayscale copy (ffmpeg, raw
frames), and for every frame the mean absolute change against the previous frame is measured (0 to 255). A frame is
frozen below 0.05, subtle from 0.05 to 0.6, medium from 0.6 to 4, big from 4. The measures, for the whole video and
scene by scene (the scene times from a merged plan):

  moving_share_pct         the share of frames that are medium or big
  middle_moving_share_pct  the same on the middle third of the screen (rows 64 to 127 of 192: y 640 to 1280 at 1080x1920,
                           where the hero content sits)
  pixels_changing_pct      the mean share of pixels that change by more than 8 from one frame to the next
  still_share_pct          the share of time inside still stretches of 1 s or more (a still frame is below medium motion:
                           frozen or subtle; the M13 reel's 29 percent and 2.8 s of the spec come out this way)
  longest_still_s          the longest still stretch

The targets live in tokens.json `energy.targets` (70 percent of the look references' median for the three lower
bounds, the median rounded up to the next 5 percent and 0.5 s for the two upper bounds, or the spec's paper-cards
numbers when the style was not calibrated; pipeline/lib/tokens.py derives them); `calibrate` measures the style's reference videos (styles/<style>/refs/look and refs/motion) and writes
styles/<style>/analysis/energy.json with every video's numbers and the medians.

  python pipeline/lib/review energy <video> [--plan merged.json] [--out energy.json] [--tokens tokens.json]
  python pipeline/lib/review energy calibrate --refs styles/paper-cards/refs --out styles/paper-cards/analysis/energy.json
  energy.measure_frames(frames) also serves the gallery: `frames` is a uint8 array [n, 192, 108] of a component rendered
  alone (motion/gallery.py), measured with the same thresholds.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess

FPS = 30
W, H = 108, 192
FROZEN_MAX = 0.05
SUBTLE_MAX = 0.6
MEDIUM_MAX = 4.0
PIXEL_CHANGE_MIN = 8
STILL_MAX = SUBTLE_MAX        # a still frame: below medium motion, frozen or subtle (DECISIONS.md M14)
STILL_STRETCH_S = 1.0
TARGET_SHARE = 0.7            # the targets are 70 percent of the look references' median (E0)
# the measure, its direction (a lower bound rises with the energy, an upper bound falls) and its rounding
MEASURES = [("moving_share_pct", "min", 0), ("middle_moving_share_pct", "min", 0), ("pixels_changing_pct", "min", 1),
            ("still_share_pct", "max", 0), ("longest_still_s", "max", 1)]
# BUILD_SPEC.md E0, the paper-cards targets when the style has no calibration file
SPEC_TARGETS = {"moving_share_pct": 42, "middle_moving_share_pct": 46, "pixels_changing_pct": 3.3, "still_share_pct": 15, "longest_still_s": 2}
LABELS = {"moving_share_pct": "moving share", "middle_moving_share_pct": "middle band", "pixels_changing_pct": "pixels changing",
          "still_share_pct": "still stretches", "longest_still_s": "longest still"}


# ------------------------------------------------------------------------------------------------ frames

def decode(video: str, fps: int = FPS, size: tuple[int, int] = (W, H), timeout: int = 900):
    """The video as a uint8 array [n, H, W] of grayscale frames at `fps` (ffmpeg scales with the area filter)."""
    import numpy as np
    w, h = size
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", video, "-vf", f"fps={fps},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read {video}: {proc.stderr.decode('utf-8', 'replace')[-400:]}")
    raw = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = len(raw) // (w * h)
    if n < 2:
        raise RuntimeError(f"{video}: fewer than 2 frames decoded")
    return raw[: n * w * h].reshape(n, h, w)


def frame_changes(frames) -> dict:
    """Per frame (from the second one): the mean absolute change, the middle band's, the share of pixels changing by
    more than PIXEL_CHANGE_MIN. Frame 0 counts as a change of 0 (nothing before it)."""
    import numpy as np
    n = frames.shape[0]
    h = frames.shape[1]
    y0, y1 = h // 3, 2 * h // 3
    mean = np.zeros(n, dtype=np.float64)
    mid = np.zeros(n, dtype=np.float64)
    pix = np.zeros(n, dtype=np.float64)
    step = 256  # frames per batch: keeps the int16 difference small in memory
    for a in range(1, n, step):
        b = min(n, a + step)
        d = np.abs(frames[a:b].astype(np.int16) - frames[a - 1:b - 1].astype(np.int16))
        mean[a:b] = d.mean(axis=(1, 2))
        mid[a:b] = d[:, y0:y1, :].mean(axis=(1, 2))
        pix[a:b] = (d > PIXEL_CHANGE_MIN).mean(axis=(1, 2))
    return {"mean": mean, "middle": mid, "pixels": pix}


def classify(value: float) -> str:
    if value < FROZEN_MAX:
        return "frozen"
    if value < SUBTLE_MAX:
        return "subtle"
    if value < MEDIUM_MAX:
        return "medium"
    return "big"


def still_runs(mean, still_max: float = STILL_MAX) -> list[tuple[int, int]]:
    """[(start index, length)] of the runs of consecutive still frames."""
    runs = []
    start = None
    for i, v in enumerate(mean):
        if v < still_max:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i - start))
            start = None
    if start is not None:
        runs.append((start, len(mean) - start))
    return runs


def measures_of(changes: dict, i0: int = 0, i1: int | None = None, fps: int = FPS, still_max: float = STILL_MAX) -> dict:
    """The five measures over the frames [i0, i1) (frame 0 of the video is left out: it has no change)."""
    import numpy as np
    mean, mid, pix = changes["mean"], changes["middle"], changes["pixels"]
    i1 = len(mean) if i1 is None else min(len(mean), i1)
    i0 = max(1, i0)
    n = max(0, i1 - i0)
    if n == 0:
        return {"frames": 0}
    m = mean[i0:i1]
    classes = {"frozen": int(np.sum(m < FROZEN_MAX)), "subtle": int(np.sum((m >= FROZEN_MAX) & (m < SUBTLE_MAX))),
               "medium": int(np.sum((m >= SUBTLE_MAX) & (m < MEDIUM_MAX))), "big": int(np.sum(m >= MEDIUM_MAX))}
    runs = still_runs(m, still_max)
    long_runs = [r for r in runs if r[1] >= STILL_STRETCH_S * fps]
    longest = max([r[1] for r in runs], default=0)
    return {
        "frames": n,
        "seconds": round(n / fps, 2),
        "moving_share_pct": round(100.0 * (classes["medium"] + classes["big"]) / n, 1),
        "middle_moving_share_pct": round(100.0 * float(np.sum(mid[i0:i1] >= SUBTLE_MAX)) / n, 1),
        "pixels_changing_pct": round(100.0 * float(np.mean(pix[i0:i1])), 2),
        "still_share_pct": round(100.0 * sum(r[1] for r in long_runs) / n, 1),
        "longest_still_s": round(longest / fps, 2),
        "still_stretches": len(long_runs),
        "mean_change": round(float(np.mean(m)), 3),
        "classes": classes,
        "classes_pct": {k: round(100.0 * v / n, 1) for k, v in classes.items()},
    }


def measure_frames(frames, fps: int = FPS, still_max: float = STILL_MAX) -> dict:
    """The measures of a frame array (uint8 [n, H, W]); the gallery's per-component energy."""
    ch = frame_changes(frames)
    out = measures_of(ch, 0, None, fps, still_max)
    out["per_frame"] = {"mean": [round(float(v), 3) for v in ch["mean"]]}
    return out


# ------------------------------------------------------------------------------------------------ targets

def targets_from_tokens(tokens: dict | None) -> dict:
    t = ((tokens or {}).get("energy") or {}).get("targets") or {}
    out = dict(SPEC_TARGETS)
    for k in out:
        if k in t and t[k] is not None:
            out[k] = t[k]
    return out


def check_targets(measures: dict, targets: dict) -> dict:
    """{measure: {want, got, ok, direction}} and the pass flag."""
    out = {}
    ok_all = True
    for name, direction, _nd in MEASURES:
        want = targets.get(name)
        got = measures.get(name)
        if want is None or got is None:
            continue
        ok = (got >= want - 1e-9) if direction == "min" else (got <= want + 1e-9)
        ok_all = ok_all and ok
        out[name] = {"want": want, "got": got, "ok": bool(ok), "direction": "at least" if direction == "min" else "at most"}
    return {"pass": bool(ok_all), "checks": out}


def derive_targets(look_medians: dict, share: float = TARGET_SHARE) -> dict:
    """The same rule as tokens.py energy_targets_from_medians: the lower bounds at 70 percent of the look median, the
    upper bounds at the median rounded up to the next 5 percent and 0.5 s."""
    import math
    out = dict(SPEC_TARGETS)
    for name, direction, nd in MEASURES:
        v = look_medians.get(name)
        if v is None:
            continue
        if direction == "min":
            out[name] = round(v * share, nd) if nd else int(round(v * share))
        elif name == "still_share_pct":
            out[name] = int(math.ceil(v / 5.0 - 1e-9) * 5)
        else:
            out[name] = round(math.ceil(v / 0.5 - 1e-9) * 0.5, 1)
    return out


def summary_line(m: dict, checks: dict | None = None) -> str:
    parts = []
    for name, _d, _nd in MEASURES:
        v = m.get(name)
        unit = " s" if name.endswith("_s") else "%"
        s = f"{LABELS[name]} {v}{unit}"
        if checks and name in checks.get("checks", {}):
            c = checks["checks"][name]
            s += f" ({'ok' if c['ok'] else 'FAIL'}, {c['direction']} {c['want']}{unit})"
        parts.append(s)
    return ", ".join(parts)


# ------------------------------------------------------------------------------------------------ a video

def scene_spans(plan: dict | None) -> list[dict]:
    if not plan:
        return []
    out = []
    for s in plan.get("scenes", []):
        try:
            out.append({"id": s.get("id"), "beat": s.get("beat"), "beat_type": s.get("beat_type"), "start_ms": int(s["start_ms"]), "end_ms": int(s["end_ms"])})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def measure_video(video: str, plan: dict | None = None, tokens: dict | None = None, targets: dict | None = None, still_max: float = STILL_MAX) -> dict:
    frames = decode(video)
    ch = frame_changes(frames)
    n = frames.shape[0]
    whole = measures_of(ch, 0, None, FPS, still_max)
    targets = targets or targets_from_tokens(tokens)
    rep = {"written_by": "review/energy.py", "video": video.replace("\\", "/"), "fps": FPS, "size": [W, H], "frames": n, "duration_s": round(n / FPS, 2),
           "thresholds": {"frozen_max": FROZEN_MAX, "subtle_max": SUBTLE_MAX, "medium_max": MEDIUM_MAX, "pixel_change_min": PIXEL_CHANGE_MIN,
                          "still_max": still_max, "still_stretch_s": STILL_STRETCH_S},
           "whole": whole, "targets": targets, "check": check_targets(whole, targets), "scenes": []}
    for s in scene_spans(plan):
        i0 = int(round(s["start_ms"] * FPS / 1000.0))
        i1 = int(round(s["end_ms"] * FPS / 1000.0))
        m = measures_of(ch, i0, i1, FPS, still_max)
        entry = dict(s)
        entry["measures"] = m
        entry["check"] = check_targets(m, targets) if m.get("frames") else {"pass": None, "checks": {}}
        rep["scenes"].append(entry)
    rep["pass"] = rep["check"]["pass"]
    rep["failing_scenes"] = [s["id"] for s in rep["scenes"] if s["check"].get("pass") is False]
    # the still stretches, for the report (whole video): start s, length s
    runs = [(a, l) for a, l in still_runs(ch["mean"][1:], still_max) if l >= STILL_STRETCH_S * FPS]
    rep["still_stretches"] = [{"start_s": round((a + 1) / FPS, 2), "seconds": round(l / FPS, 2)} for a, l in runs][:40]
    return rep


# ------------------------------------------------------------------------------------------------ calibration

def reference_videos(refs_dir: str, index_md: str = "") -> list[dict]:
    """[{nick, file, folder}] of refs/look and refs/motion, nicknamed as styles/<style>/analysis/index.md does (v01, v02,
    ... in case-insensitive alphabetical order per folder, look first)."""
    exts = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
    out = []
    named = {}
    if index_md and os.path.isfile(index_md):
        for line in open(index_md, encoding="utf-8-sig"):
            m = re.match(r"^\|\s*(v\d+)\s*\|\s*(.+?)\s*\|\s*(look|motion)\s*\|", line)
            if m:
                named[(m.group(3), m.group(2))] = m.group(1)
    n = 0
    for folder in ("look", "motion"):
        d = os.path.join(refs_dir, folder)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d), key=lambda s: s.lower()):
            if os.path.splitext(f)[1].lower() not in exts:
                continue
            n += 1
            out.append({"nick": named.get((folder, f)) or f"v{n:02d}", "file": os.path.join(d, f).replace("\\", "/"), "folder": folder})
    return out


def median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    k = len(vals)
    return vals[k // 2] if k % 2 else (vals[k // 2 - 1] + vals[k // 2]) / 2.0


def calibrate(refs_dir: str, out_path: str, index_md: str = "", still_max: float = STILL_MAX, log=print) -> dict:
    vids = reference_videos(refs_dir, index_md)
    if not vids:
        raise RuntimeError(f"no reference videos under {refs_dir} (look/ and motion/)")
    per: dict = {}
    for v in vids:
        frames = decode(v["file"])
        ch = frame_changes(frames)
        m = measures_of(ch, 0, None, FPS, still_max)
        per[v["nick"]] = {"file": os.path.basename(v["file"]), "folder": v["folder"], "frames": int(frames.shape[0]), "duration_s": round(frames.shape[0] / FPS, 2), **m}
        log(f"{v['nick']} ({v['folder']}): {summary_line(m)}")
    medians = {}
    for group in ("look", "motion", "all"):
        rows = [r for r in per.values() if group == "all" or r["folder"] == group]
        medians[group] = {name: (round(median([r[name] for r in rows]), 2) if rows else None) for name, _d, _nd in MEASURES}
    rep = {"written_by": "review/energy.py calibrate", "run": dt.datetime.now().isoformat(timespec="seconds"), "fps": FPS, "size": [W, H],
           "thresholds": {"frozen_max": FROZEN_MAX, "subtle_max": SUBTLE_MAX, "medium_max": MEDIUM_MAX, "pixel_change_min": PIXEL_CHANGE_MIN,
                          "still_max": still_max, "still_stretch_s": STILL_STRETCH_S},
           "videos": per, "medians": medians, "target_share": TARGET_SHARE, "targets": derive_targets(medians["look"]),
           "note": "targets: the lower bounds (moving share, middle band, pixels changing) are 70 percent of the look references' median; the upper bounds (still stretches, longest still) the median rounded up to the next 5 percent and 0.5 s; tokens.json energy.targets carries them unless an Energy line in tweaks.md overrides them"}
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=1, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, out_path)
    return rep


# ------------------------------------------------------------------------------------------------ CLI

def load_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def default_tokens_path() -> str:
    """The style's tokens.json (config paths.tokens under the repo, or styles/paper-cards/tokens.json)."""
    try:
        from motion import common as mcommon
        return mcommon.tokens_path()
    except Exception:  # noqa: BLE001
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(here))), "styles", "paper-cards", "tokens.json")


def run_cli(a) -> int:
    if a.video == "calibrate":
        index_md = a.index or (os.path.join(os.path.dirname(a.out), "index.md") if a.out else "")
        rep = calibrate(a.refs, a.out, index_md, still_max=a.still_threshold if a.still_threshold is not None else STILL_MAX)
        print("look medians: " + summary_line(rep["medians"]["look"]))
        print("motion medians: " + summary_line(rep["medians"]["motion"]))
        print("targets (the 70 percent rule): " + ", ".join(f"{LABELS[k]} {v}" for k, v in rep["targets"].items()) + (f" -> {a.out}" if a.out else ""))
        return 0
    plan = load_json(a.plan) if a.plan else None
    tokens_path = a.tokens or default_tokens_path()
    tokens = load_json(tokens_path) if tokens_path and os.path.isfile(tokens_path) else None
    targets = load_json(a.targets) if getattr(a, "targets", "") else None
    rep = measure_video(a.video, plan, tokens, targets, still_max=a.still_threshold if a.still_threshold is not None else STILL_MAX)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=1, ensure_ascii=False)
            f.write("\n")
    print(f"energy {os.path.basename(a.video)}: {rep['frames']} frames, {rep['duration_s']} s: " + summary_line(rep["whole"], rep["check"]) + f": {'pass' if rep['pass'] else 'FAIL'}")
    for s in rep["scenes"]:
        m = s["measures"]
        if not m.get("frames"):
            continue
        print(f"  scene {s['id']} ({s.get('beat_type')}, {s['start_ms'] / 1000:.2f} to {s['end_ms'] / 1000:.2f} s): " + summary_line(m) + f": {'pass' if s['check']['pass'] else 'FAIL'}")
    return 0 if rep["pass"] else 1
