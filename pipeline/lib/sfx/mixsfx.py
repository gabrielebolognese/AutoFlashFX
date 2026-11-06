"""mixsfx.py: the sound effects pass, S11 (BUILD_SPEC.md S11, M11). No model.

  python pipeline/lib/sfx/mixsfx.py run --run-dir DIR [--stage-dir DIR/11-sfx] [--seed N] [--no-hook2]

Steps: the cue types from 10-build/events.json with the rules of assign.py (seeded per reel: the idea id, plus the
review round when the edit review asked for other sounds), the files from the map's pools with pick.py (rotation,
never twice in a row, the last 2 reels avoided through logs/sfx-usage.json), placement (place.py: whooshes by their
peak, the rest by their onset, typing trimmed, tails cut with a 30 ms fade), levels (level.py: the map's
normalization plus the cue type's base gain, at least 8 dB under the voice around the moment), the stem and the mix
(render_stem.py, numpy), then the verification (verify.py) on the rendered files: every sound within 33 ms of its
event and no unplanned sound, the voice rule, the mix at -14 LUFS plus or minus 1 and at most -1.5 dBTP. A failure
is corrected (an offset, a gain, the stem's level, a true-peak limiter on the mix) and verified again, up to config
sfx.verify_passes times; still failing is exit 3 (the stage turns it into a code error, the review path).
Outputs in the stage folder: cues.json, sfx_stem.wav, mix.wav, draft_mixed.mp4, sound-map.txt, and for the hook 2
clip cues_hook2.json, sfx_stem_hook2.wav, mix_hook2.wav (S13 muxes them). A missing or empty map means the voice
alone and a NEEDS REVIEW flag (BUILD_SPEC.md S11).
Progress lines for the stage script: "@@ACTIVITY text", "@@SAY TAG text", "@@FLAG text", "@@ERROR text".
Exit 0 done, 1 a code error (an input missing, a tool failing), 3 the verification still failing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)
from common import clean, load_json, save_json, save_text, setup_streams, winpath  # noqa: E402
import assign  # noqa: E402
import paths  # noqa: E402
import level  # noqa: E402
import pick  # noqa: E402
import place  # noqa: E402
import render_stem  # noqa: E402
import verify  # noqa: E402
from audioio import SR, measure_loudness, mux, peak_db, read_audio, write_wav16  # noqa: E402

REPO = os.path.abspath(os.path.join(LIB, "..", ".."))


def say(tag: str, text: str) -> None:
    print(f"@@SAY {tag} {clean(text)}", flush=True)


def activity(text: str) -> None:
    print(f"@@ACTIVITY {text}", flush=True)


def flag(text: str) -> None:
    print(f"@@FLAG {clean(text)}", flush=True)


def error(text: str) -> None:
    print(f"@@ERROR {clean(text)}", flush=True)


def log(text: str) -> None:
    print(clean(text, one_line=False), flush=True)


class Ctx:
    def __init__(self, run_dir: str, stage_dir: str):
        self.repo = (os.environ.get("REELS_REPO") or REPO).replace("\\", "/")
        self.root = (os.environ.get("REELS_CHANNEL_ROOT") or os.environ.get("REELS_ROOT") or self.repo).replace("\\", "/")
        self.run_dir = winpath(run_dir).replace("\\", "/")
        self.stage_dir = winpath(stage_dir or os.path.join(self.run_dir, "11-sfx")).replace("\\", "/")
        cfg_path = os.environ.get("REELS_CONFIG") or f"{self.repo}/config.json"
        self.config = load_json(cfg_path, {}) or {}
        sfx_rel = str(self.cfg("paths.sfx_dir"))
        self.sfx_dir = (os.environ.get("REELS_SFX_DIR") or f"{self.root}/{sfx_rel}").replace("\\", "/")
        self.map_path = f"{self.sfx_dir}/sfx-map.json"
        self.logs = (os.environ.get("REELS_LOGS") or f"{self.root}/{paths.LOGS_DIR}").replace("\\", "/")
        state = load_json(f"{self.run_dir}/state.json", {}) or {}
        self.run_id = str(state.get("run_id") or os.path.basename(self.run_dir.rstrip("/")))
        self.idea_id = str((state.get("idea") or {}).get("id") or self.run_id)
        self.round = int((state.get("rounds") or {}).get("review", 0) or 0)

    def cfg(self, key: str, default=None):
        return assign.cfg(self.config, key, default)

    def path(self, rel: str) -> str:
        return f"{self.run_dir}/{rel}"


# ------------------------------------------------------------------------------------------------ pieces

def feedback_for(ctx: Ctx) -> tuple[list[dict], int]:
    fb = load_json(ctx.path("12-review/feedback.json"), None)
    if not isinstance(fb, dict):
        return [], 0
    issues = [i for i in (fb.get("issues") or []) if isinstance(i, dict) and str(i.get("tag", "")).strip("[]") == "sfx"]
    return issues, int(fb.get("round", 0) or 0)


def sound_map_lines(cues: list[dict], voice_only_reason: str = "") -> str:
    lines = ["# sound-map.txt: one line per sound: time, cue type, file, the visual event it sits on (gain, trims). Written by 11-sfx."]
    if voice_only_reason:
        lines.append(f"# no sounds: {voice_only_reason}")
    for c in sorted(cues, key=lambda c: c["ms"]):
        extra = f"{c.get('gain_db', 0):+.1f} dB"
        if c.get("capped_by_voice"):
            extra += ", capped by the voice"
        if c.get("trim"):
            extra += f", cut at {c['trim']}"
        if c.get("end_ms"):
            extra += f", to {c['end_ms'] / 1000:.3f}s"
        lines.append(f"{c['ms'] / 1000:7.3f}s  {c['cue_type']:<16s} {os.path.basename(c.get('file') or '')[:44]:<44s} {assign.describe(c['event'])}  ({extra})")
    return "\n".join(lines) + "\n"


def strip_for_json(c: dict) -> dict:
    out = {k: v for k, v in c.items() if not k.startswith("_")}
    return out


def verify_round(ctx: Ctx, cues: list[dict], voice: np.ndarray, segments: dict, stem_path: str, mix_path: str, duration_ms: float,
                 target_i: float, target_tp: float) -> tuple[dict, np.ndarray, np.ndarray]:
    stem = render_stem.render(cues, segments, len(voice), SR)
    mix = voice + stem
    write_wav16(stem_path, stem, SR)
    write_wav16(mix_path, mix, SR)
    measured = measure_loudness(mix_path, target_i, target_tp, int(ctx.cfg("timeouts.loudness_seconds", 300)))
    acc = verify.accuracy(cues, stem, SR, float(ctx.cfg("sfx.sync_tolerance_ms", 33)), duration_ms, float(ctx.cfg("sfx.peak_search_ms", 500)))
    vr = verify.voice_rule(cues, stem, SR, float(ctx.cfg("sfx.min_db_under_voice", 8)))
    ld = verify.loudness(measured, target_i, target_tp)
    res = {"pass": bool(acc["pass"] and vr["pass"] and ld["pass"]), "accuracy": acc, "voice_rule": vr, "loudness": ld,
           "mix_peak_dbfs": round(peak_db(mix), 2), "stem_peak_dbfs": round(peak_db(stem), 2)}
    return res, stem, mix


def correct(cues: list[dict], res: dict, target_i: float, target_tp: float, corrections: list[str], max_shift_ms: float = 150.0) -> bool:
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
        shift = -float(r["error_ms"])
        new_start = float(c["reel_start_ms"]) + shift
        if new_start < 0:
            c["offset_ms"] = round(float(c["offset_ms"]) - new_start, 3)
            new_start = 0.0
        c["reel_start_ms"] = round(new_start, 3)
        c["_reload"] = True
        corrections.append(f"{c['id']} {c['cue_type']}: measured {r['error_ms']:+.0f} ms off, moved by {shift:+.0f} ms")
        changed = True
    for r in res["voice_rule"]["results"]:
        if r["ok"]:
            continue
        c = by_id[r["id"]]
        drop = -float(r["margin_db"]) + 0.5
        c["gain_db"] = round(float(c["gain_db"]) - drop, 2)
        c["peak_dbfs"] = round(float(c["peak_dbfs"]) - drop, 2)
        corrections.append(f"{c['id']} {c['cue_type']}: {-float(r['margin_db']):.1f} dB over its voice cap, lowered by {drop:.1f} dB")
        changed = True
    ld = res["loudness"]
    if not ld["true_peak_ok"] and ld["true_peak_dbtp"] is not None and cues:
        excess = float(ld["true_peak_dbtp"]) - target_tp + 0.5
        for c in cues:
            c["gain_db"] = round(float(c["gain_db"]) - excess, 2)
            c["peak_dbfs"] = round(float(c["peak_dbfs"]) - excess, 2)
        corrections.append(f"true peak {ld['true_peak_dbtp']:.2f} dBTP over {target_tp}: every sound lowered by {excess:.1f} dB")
        changed = True
    if not ld["lufs_ok"] and ld["lufs"] is not None and cues and ld["lufs"] > target_i:
        excess = float(ld["lufs"]) - target_i
        drop = min(6.0, excess * 2.0 + 1.0)
        for c in cues:
            c["gain_db"] = round(float(c["gain_db"]) - drop, 2)
            c["peak_dbfs"] = round(float(c["peak_dbfs"]) - drop, 2)
        corrections.append(f"mix {ld['lufs']:.1f} LUFS over the target: every sound lowered by {drop:.1f} dB")
        changed = True
    return changed


def run_clip(ctx: Ctx, label: str, events: list[dict], plan: dict, words: dict, voice_path: str, pools: dict, usage: dict, seed: int,
             feedback_issues: list[dict], last_files: dict, out_names: dict, draft_mp4: str | None, pick_seed_offset: int = 0) -> dict:
    """The whole pass for one clip (the reel or the hook 2 clip). Returns the cues.json content."""
    target_i = float(ctx.cfg("voice.loudness_lufs", -14))
    target_tp = float(ctx.cfg("voice.true_peak_dbtp", -1.5))
    voice, sr = read_audio(voice_path)
    duration_ms = float(plan.get("duration_ms") or len(voice) * 1000.0 / SR)
    a = assign.assign(events, plan, words, ctx.config, seed, feedback_issues)
    cues = a["cues"]
    counts = a["counts"]
    activity(f"adding sound effects ({len(cues)} {'sound' if len(cues) == 1 else 'sounds'})")
    recent = pick.recent_files(usage, ctx.run_id, int(ctx.cfg("sfx.recent_reels", 2)))
    cues, pick_notes = pick.pick(cues, pools, recent, seed + pick_seed_offset, a["settings"].get("avoid_last"), last_files)
    dropped = list(a["dropped"])
    kept = []
    for c in cues:
        if c.get("file"):
            kept.append(c)
        else:
            dropped.append({**c, "reason": "no file: the pool is empty"})
    cues = kept
    profile = level.voice_profile(voice, sr)
    cues = place.place(cues, int(duration_ms), ctx.config)
    segcache: dict = {}
    segments = {c["id"]: render_stem.load_segment(c, ctx.sfx_dir, segcache) for c in cues}
    seg_peaks = {cid: peak_db(seg) for cid, seg in segments.items()}
    cues = level.levels(cues, seg_peaks, profile, ctx.config, float(a["settings"].get("gain_offset_db", 0.0)))
    log(f"{label}: {len(cues)} sounds from {a['candidates']} candidates (" + ", ".join(f"{k} {v}" for k, v in counts.items() if v) + f"); {len(dropped)} dropped; seed {seed}")
    for n in pick_notes + a["feedback_applied"]:
        log(f"{label}: note: {n}")
    stem_path = f"{ctx.stage_dir}/{out_names['stem']}"
    mix_path = f"{ctx.stage_dir}/{out_names['mix']}"
    passes = int(ctx.cfg("sfx.verify_passes", 5))
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
            kept_starts = {c["id"]: (c["reel_start_ms"], c["offset_ms"]) for c in cues if not c.get("_swapped")}
            cues = place.place(cues, int(duration_ms), ctx.config)
            for c in cues:
                if c["id"] in kept_starts and not c.get("_swapped"):
                    c["reel_start_ms"], c["offset_ms"] = kept_starts[c["id"]]   # earlier corrections of the others stay
            segments = {c["id"]: render_stem.load_segment(c, ctx.sfx_dir, segcache) for c in cues}
            cues = level.levels(cues, {cid: peak_db(seg) for cid, seg in segments.items()}, profile, ctx.config, gain_offset)
    # the last resort for the mix's loudness: a limiter or a gain on the mix itself (the voice alone can sit over
    # the ceiling by the width of the encoder's rounding, or under the target)
    if res is not None and not res["loudness"]["pass"]:
        ld = res["loudness"]
        gain = 0.0
        if ld["lufs"] is not None and not ld["lufs_ok"]:
            gain = target_i - float(ld["lufs"])
        fixed = mix_path[:-4] + ".fixed.wav"
        mix_filter = render_stem.fix_mix(mix_path, fixed, gain, target_tp, int(ctx.cfg("timeouts.loudness_seconds", 300)))
        os.replace(winpath(fixed), winpath(mix_path))
        measured = measure_loudness(mix_path, target_i, target_tp)
        res["loudness"] = verify.loudness(measured, target_i, target_tp)
        res["mix_filter"] = mix_filter
        corrections.append(f"the mix itself: {mix_filter}")
        res["pass"] = bool(res["accuracy"]["pass"] and res["voice_rule"]["pass"] and res["loudness"]["pass"])
        log(f"{label}: mix corrected ({mix_filter}): {res['loudness']['lufs']} LUFS, {res['loudness']['true_peak_dbtp']} dBTP {'ok' if res['loudness']['pass'] else 'NOT ok'}")
    res["corrections"] = corrections
    if draft_mp4 and out_names.get("draft_mixed"):
        mux(draft_mp4, mix_path, f"{ctx.stage_dir}/{out_names['draft_mixed']}", int(ctx.cfg("timeouts.render_draft_seconds", 3600)))
    sound_map = sound_map_lines(cues)
    if out_names.get("sound_map"):
        save_text(f"{ctx.stage_dir}/{out_names['sound_map']}", sound_map)
    return {"written_by": "11-sfx", "label": label, "round": ctx.round, "seed": seed, "duration_ms": duration_ms,
            "voice": {"file": os.path.relpath(voice_path, ctx.run_dir).replace("\\", "/"), "overall_peak_dbfs": profile["overall_peak_dbfs"]},
            "counts": counts, "candidates": a["candidates"], "settings": a["settings"], "feedback_applied": a["feedback_applied"], "notes": pick_notes,
            "cues": [strip_for_json(c) for c in cues], "dropped": [strip_for_json(d) for d in dropped], "verification": res,
            "files": {k: v for k, v in out_names.items() if v}}


def voice_only(ctx: Ctx, reason: str, voice_path: str, draft_mp4: str, hook2_voice: str | None) -> int:
    voice, sr = read_audio(voice_path)
    write_wav16(f"{ctx.stage_dir}/sfx_stem.wav", np.zeros(len(voice), dtype=np.float32), SR)
    write_wav16(f"{ctx.stage_dir}/mix.wav", voice, SR)
    measured = measure_loudness(f"{ctx.stage_dir}/mix.wav")
    mux(draft_mp4, f"{ctx.stage_dir}/mix.wav", f"{ctx.stage_dir}/draft_mixed.mp4")
    save_text(f"{ctx.stage_dir}/sound-map.txt", sound_map_lines([], reason))
    out = {"written_by": "11-sfx", "round": ctx.round, "seed": 0, "voice_only": True, "reason": reason, "duration_ms": len(voice) * 1000.0 / SR,
           "counts": {}, "cues": [], "dropped": [],
           "verification": {"pass": True, "note": "no sounds to verify (voice only)", "accuracy": {"pass": True, "checked": 0, "results": [], "unplanned": []},
                            "voice_rule": {"pass": True, "results": []}, "loudness": verify.loudness(measured, float(ctx.cfg("voice.loudness_lufs", -14)), float(ctx.cfg("voice.true_peak_dbtp", -1.5))), "passes": 1},
           "files": {"stem": "sfx_stem.wav", "mix": "mix.wav", "draft_mixed": "draft_mixed.mp4", "sound_map": "sound-map.txt"}, "hook2": None}
    if hook2_voice and os.path.isfile(winpath(hook2_voice)):
        v2, _ = read_audio(hook2_voice)
        write_wav16(f"{ctx.stage_dir}/sfx_stem_hook2.wav", np.zeros(len(v2), dtype=np.float32), SR)
        write_wav16(f"{ctx.stage_dir}/mix_hook2.wav", v2, SR)
        out["hook2"] = {"voice_only": True, "cues": [], "files": {"stem": "sfx_stem_hook2.wav", "mix": "mix_hook2.wav"}}
    save_json(f"{ctx.stage_dir}/cues.json", out)
    flag(f"no sound effects: {reason}; the reel has the voice alone (bash pipeline/bin/build-sfx-map builds the map)")
    say("INFO", f"S11: voice only ({reason}); mix {measured.get('lufs')} LUFS")
    return 0


def hook2_events(ctx: Ctx, plan2: dict) -> list[dict] | None:
    project = ctx.path("10-build/hook2")
    if not os.path.isdir(winpath(os.path.join(project, "compositions"))) or not os.path.isfile(winpath(os.path.join(project, "instances.json"))):
        return None
    try:
        from visual import events as events_mod
    except ImportError as exc:
        log(f"hook 2: cannot import the events reader ({exc})")
        return None
    os.environ.setdefault("REELS_MOTION_LIB", f"{ctx.root}/{ctx.cfg('paths.motion_lib')}")
    ev = events_mod.build_events(project, plan2, verify=False)
    return ev.get("events", [])


def cmd_run(args) -> int:
    ctx = Ctx(args.run_dir, args.stage_dir)
    os.makedirs(winpath(ctx.stage_dir), exist_ok=True)
    needed = {"events": "10-build/events.json", "plan": "10-build/plan.json", "draft": "10-build/draft.mp4", "voice": "08-voiceover/vo.wav", "words": "08-voiceover/words.json"}
    paths = {k: ctx.path(v) for k, v in needed.items()}
    for k, p in paths.items():
        if not os.path.isfile(winpath(p)):
            error(f"{needed[k]} is missing: the {'build' if k in ('events', 'plan', 'draft') else 'voiceover'} stage did not run")
            return 1
    events = (load_json(paths["events"], {}) or {}).get("events", [])
    plan = load_json(paths["plan"], {}) or {}
    words = load_json(paths["words"], {}) or {}
    hook2_voice = ctx.path("08-voiceover/vo_hook2.wav")
    m = load_json(ctx.map_path, None)
    pools = (m or {}).get("pools") or {}
    if not m:
        return voice_only(ctx, f"the sfx map {ctx.map_path} is missing", paths["voice"], paths["draft"], hook2_voice)
    if not any(pools.get(k) for k in pools):
        return voice_only(ctx, "the sfx map has no pool with files", paths["voice"], paths["draft"], hook2_voice)
    feedback_issues, fb_round = feedback_for(ctx)
    seed = int(args.seed) if args.seed is not None else assign.seed_for(ctx.idea_id, ctx.round if feedback_issues else 0)
    usage_path = f"{ctx.logs}/sfx-usage.json"
    usage = pick.load_usage(usage_path)
    prev = load_json(f"{ctx.stage_dir}/cues.json", None)
    last_files: dict = {}
    for c in ((prev or {}).get("cues") or []):
        if c.get("file"):
            last_files.setdefault(c["cue_type"], []).append(c["file"])
    t0 = time.time()
    main = run_clip(ctx, "reel", events, plan, words, paths["voice"], pools, usage, seed, feedback_issues, last_files,
                    {"stem": "sfx_stem.wav", "mix": "mix.wav", "draft_mixed": "draft_mixed.mp4", "sound_map": "sound-map.txt"}, paths["draft"])
    main["map"] = {"path": ctx.map_path, "built": (m or {}).get("built"), "files": len((m or {}).get("files") or []), "pools": {k: len(v or []) for k, v in pools.items()}}
    main["hook2"] = None
    if not args.no_hook2:
        plan2 = load_json(ctx.path("10-build/hook2/plan.json"), None)
        words2 = load_json(ctx.path("08-voiceover/words_hook2.json"), None)
        if plan2 and words2 and os.path.isfile(winpath(hook2_voice)):
            try:
                ev2 = hook2_events(ctx, plan2)
            except Exception as exc:  # the hook 2 clip is secondary: its sounds are skipped with a note, never a failed stage
                ev2 = None
                log(f"hook 2: the events could not be read ({type(exc).__name__}: {clean(str(exc))[:160]})")
            if ev2:
                h2 = run_clip(ctx, "hook 2", ev2, plan2, words2, hook2_voice, pools, usage, seed + 7, [], {},
                              {"stem": "sfx_stem_hook2.wav", "mix": "mix_hook2.wav", "sound_map": "sound-map-hook2.txt"}, None, pick_seed_offset=3)
                main["hook2"] = h2
            else:
                main["hook2"] = {"skipped": "no hook 2 project with its compositions (10-build/hook2) or no events"}
        else:
            main["hook2"] = {"skipped": "no hook 2 plan, words or voice"}
    main["seconds"] = round(time.time() - t0, 1)
    save_json(f"{ctx.stage_dir}/cues.json", main)
    all_cues = list(main["cues"]) + list(((main.get("hook2") or {}).get("cues")) or [])
    pick.update_usage(usage_path, usage, ctx.run_id, ctx.idea_id, all_cues)
    v = main["verification"]
    acc, vr, ld = v["accuracy"], v["voice_rule"], v["loudness"]
    say("INFO", f"S11: {len(main['cues'])} sounds placed ({', '.join(f'{k} {n}' for k, n in main['counts'].items() if n)}), {len(main['dropped'])} candidates dropped by the rules; "
                f"seed {seed}" + (f"; hook 2: {len(main['hook2'].get('cues', []))} sounds" if isinstance(main.get("hook2"), dict) and main["hook2"].get("cues") is not None else ""))
    say("INFO", f"S11: verified in {v.get('passes', 1)} {'pass' if v.get('passes', 1) == 1 else 'passes'}: every sound within {acc['max_error_ms']} ms of its event"
                f"{'' if not acc['unplanned'] else f', {len(acc[chr(117) + chr(110) + chr(112) + chr(108) + chr(97) + chr(110) + chr(110) + chr(101) + chr(100)])} unplanned'}; "
                f"closest to the voice {vr['min_margin_db']} dB under the cap; mix {ld['lufs']} LUFS, {ld['true_peak_dbtp']} dBTP" + ("" if v["pass"] else ": NOT ok"))
    if not v["pass"]:
        problems = []
        if not acc["pass"]:
            bad = [r for r in acc["results"] if not r["ok"]]
            problems.append(f"{len(bad)} sounds off by more than {acc['tolerance_ms']} ms" if bad else f"{len(acc['unplanned'])} unplanned sounds")
        if not vr["pass"]:
            problems.append("a sound louder than its voice cap")
        if not ld["pass"]:
            problems.append(f"mix {ld['lufs']} LUFS, {ld['true_peak_dbtp']} dBTP")
        error("the sound verification still fails after " + str(v.get("passes", 1)) + " passes: " + "; ".join(problems))
        return 3
    return 0


def main(argv: list[str]) -> int:
    setup_streams()
    ap = argparse.ArgumentParser(prog="python pipeline/lib/sfx/mixsfx.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--stage-dir", default="")
    r.add_argument("--seed", type=int, default=None)
    r.add_argument("--no-hook2", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
