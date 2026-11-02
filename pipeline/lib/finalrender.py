#!/usr/bin/env python
"""finalrender.py: the final render (BUILD_SPEC.md section 5, S13), run by pipeline/stages/13-render/run.sh.

HyperFrames renders the built composition (10-build/project/) at its own size, 1080x1920 at 30 fps, as a silent
video; ffmpeg then muxes the approved mix (11-sfx/mix.wav: the voice and the sound effects, verified at -14 LUFS)
into final.mp4 as AAC 48 kHz without touching the video (-c:v copy). The audio is not routed through HyperFrames'
own audio path: on the golden reel that path duplicated the mono voice to two channels and measured 3 LU louder
than the mix (DECISIONS.md). The hook 2 clip takes the same path (10-build/hook2/ with 11-sfx/mix_hook2.wav).

Then ffprobe and loudnorm check each file: 1080x1920, 30 fps, h264 High, yuv420p, AAC at 48 kHz, audio present,
the duration equal to the voice within config render.duration_tolerance_s (0.2 s), the loudness at
voice.loudness_lufs plus or minus render.loudness_tolerance_lu with the true peak under voice.true_peak_dbtp plus
render.true_peak_tolerance_db (room for the AAC encode); the hook 2 clip at most render.hook2_max_s (3.5 s) and
within the tolerance of its own timeline. A failed check gets one ffmpeg post-pass that fixes only what differs
(the video re-encoded for a wrong profile, pixel format, size or rate; the audio re-encoded or muxed again; the
duration trimmed; the mix brought to the loudness target), then the checks run again; still failing is a code
error (exit 3: the review and fix path of BUILD_SPEC.md 4.2).

  finalrender.py run --run-dir RUN --stage-dir DIR        the stage: final.mp4, hook2.mp4, video.mp4, render.json
  finalrender.py check --file MP4 [--voice WAV] [--hook2] the checks alone, as JSON (tests)

Progress lines for the stage script: "@@ACTIVITY <text>", "@@SAY <TAG> <text>", "@@FLAG <text>", "@@ERROR <text>".
Exit 0 done, 2 an input is missing, 3 a check still fails after the post-pass, 1 a render or ffmpeg failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from errors import undash  # noqa: E402
from motion import golden  # noqa: E402
from visual import common as vcommon  # noqa: E402

STAGE = "13-render"
WANT_W, WANT_H, WANT_FPS = 1080, 1920, 30.0


def say(tag: str, text: str) -> None:
    print(f"@@SAY {tag} {undash(text)}", flush=True)


def activity(text: str) -> None:
    print(f"@@ACTIVITY {undash(text)}", flush=True)


def flag(text: str) -> None:
    print(f"@@FLAG {undash(text)}", flush=True)


def error(text: str) -> None:
    print(f"@@ERROR {undash(text)}", flush=True)


def clean(s: str) -> str:
    return undash(" ".join(str(s or "").split()))


def run_ffmpeg(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-y"] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)


def ffprobe_duration(path: str) -> float:
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", vcommon.mixed(path)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float((proc.stdout or "").strip())
    except ValueError:
        return 0.0


def measure_loudness(path: str, target_i: float, target_tp: float, timeout: int = 600) -> dict:
    """ffmpeg loudnorm's measurement pass on the file's audio: integrated LUFS and true peak."""
    cmd = ["-i", vcommon.mixed(path), "-vn", "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:print_format=json", "-f", "null", "-"]
    r = run_ffmpeg(cmd, timeout)
    m = re.search(r"\{.*\}", r.stderr or "", re.S)
    if not m:
        return {"lufs": None, "true_peak_dbtp": None, "error": clean((r.stderr or "")[-300:])}
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return {"lufs": None, "true_peak_dbtp": None, "error": "loudnorm printed no JSON"}

    def num(key):
        try:
            v = float(d[key])
        except (KeyError, ValueError, TypeError):
            return None
        return None if math.isinf(v) or math.isnan(v) else v
    return {"lufs": num("input_i"), "true_peak_dbtp": num("input_tp"), "lra": num("input_lra")}


# ------------------------------------------------------------------------------------------------ the checks

def check_file(path: str, want_duration: float | None, cfg: dict, hook2: bool = False) -> dict:
    """Every check of spec S13 on one rendered file; checks[name] = {want, got, ok}; pass = every hard check ok."""
    r = cfg["render"]
    pr = golden.probe(vcommon.mixed(path))
    vid = pr.get("video") or {}
    aud = pr.get("audio")
    dur = float(pr.get("duration") or 0)
    tol = float(r.get("duration_tolerance_s", 0.2))
    checks = {
        "width": {"want": WANT_W, "got": vid.get("width"), "ok": vid.get("width") == WANT_W},
        "height": {"want": WANT_H, "got": vid.get("height"), "ok": vid.get("height") == WANT_H},
        "fps": {"want": WANT_FPS, "got": vid.get("fps"), "ok": abs(float(vid.get("fps") or 0) - WANT_FPS) < 0.01},
        "video_codec": {"want": "h264", "got": vid.get("codec"), "ok": vid.get("codec") == "h264"},
        "profile": {"want": "High", "got": vid.get("profile"), "ok": str(vid.get("profile") or "").lower() == "high"},
        "pix_fmt": {"want": "yuv420p", "got": vid.get("pix_fmt"), "ok": vid.get("pix_fmt") == "yuv420p"},
        "audio_present": {"want": True, "got": bool(aud), "ok": bool(aud)},
        "audio_codec": {"want": "aac", "got": (aud or {}).get("codec"), "ok": (aud or {}).get("codec") == "aac"},
        "sample_rate": {"want": 48000, "got": (aud or {}).get("sample_rate"), "ok": (aud or {}).get("sample_rate") == 48000},
    }
    if want_duration is not None:
        diff = dur - want_duration
        checks["duration"] = {"want": round(want_duration, 3), "got": round(dur, 3), "diff_s": round(diff, 3), "tolerance_s": tol, "ok": abs(diff) <= tol}
    else:
        checks["duration"] = {"want": None, "got": round(dur, 3), "ok": dur > 0}
    if hook2:
        max_s = float(r.get("hook2_max_s", 3.5))
        checks["max_seconds"] = {"want": max_s, "got": round(dur, 3), "ok": 0 < dur <= max_s + 0.034}
    target_i = float(cfg["voice"].get("loudness_lufs", -14))
    target_tp = float(cfg["voice"].get("true_peak_dbtp", -1.5))
    tol_lu = float(r.get("loudness_tolerance_lu", 1.0))
    tol_tp = float(r.get("true_peak_tolerance_db", 0.5))
    loud = measure_loudness(path, target_i, target_tp) if aud else {"lufs": None, "true_peak_dbtp": None}
    lufs, tp = loud.get("lufs"), loud.get("true_peak_dbtp")
    lufs_ok = lufs is not None and abs(lufs - target_i) <= tol_lu
    tp_ok = tp is not None and tp <= target_tp + tol_tp
    checks["loudness"] = {"lufs": lufs, "target_lufs": target_i, "tolerance_lu": tol_lu, "true_peak_dbtp": tp, "target_true_peak_dbtp": target_tp,
                          "true_peak_tolerance_db": tol_tp, "lufs_ok": lufs_ok, "true_peak_ok": tp_ok, "ok": lufs_ok and tp_ok,
                          "hard": not hook2, "error": loud.get("error")}
    hard_fail = [k for k, v in checks.items() if not v["ok"] and v.get("hard", True)]
    return {"file": os.path.basename(path), "probe": pr, "checks": checks, "failing": hard_fail, "pass": not hard_fail,
            "soft_failing": [k for k, v in checks.items() if not v["ok"] and not v.get("hard", True)]}


def failing_text(res: dict) -> str:
    parts = []
    for k in res["failing"]:
        c = res["checks"][k]
        if k == "loudness":
            parts.append(f"loudness {c['lufs']} LUFS, true peak {c['true_peak_dbtp']} dBTP (want {c['target_lufs']} plus or minus {c['tolerance_lu']}, at most {c['target_true_peak_dbtp']})")
        elif k == "duration":
            parts.append(f"duration {c['got']} s against {c['want']} s")
        else:
            parts.append(f"{k} {c.get('got')!r} (want {c.get('want')!r})")
    return "; ".join(parts)


# ------------------------------------------------------------------------------------------------ render, mux, post-pass

def render_video(project: str, out_mp4: str, quality: str, gpu_flag: str, timeout: int) -> dict:
    t0 = dt.datetime.now()
    info = golden.render(project, out_mp4, quality, gpu_flag, timeout=timeout)
    info["seconds"] = round((dt.datetime.now() - t0).total_seconds(), 1)
    info["ok"] = info.get("rc") == 0 and os.path.isfile(out_mp4) and os.path.getsize(out_mp4) > 0
    return info


def mux(video: str, audio: str | None, out: str, cfg: dict, timeout: int, duration: float | None = None, reencode_video: bool = False,
        scale: bool = False, audio_filter: str = "") -> None:
    """The mix into the video as AAC 48 kHz; the video copied, or re-encoded to H.264 High yuv420p 30 fps when asked."""
    r = cfg["render"]
    args = ["-i", vcommon.mixed(video)]
    if audio:
        args += ["-i", vcommon.mixed(audio), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        args += ["-map", "0:v:0", "-map", "0:a:0?"]
    if reencode_video:
        args += ["-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "16", "-preset", "medium"]
        if scale:
            args += ["-vf", f"scale={WANT_W}:{WANT_H}:flags=lanczos"]
    else:
        args += ["-c:v", "copy"]
    args += ["-c:a", "aac", "-b:a", f"{int(r.get('audio_bitrate_k', 160))}k", "-ar", "48000", "-ac", str(int(r.get("audio_channels", 1)))]
    # the audio is padded with silence (apad) so -shortest ends at the video: a mix shorter than its composition (the
    # hook 2 clip's voice ends before the clip's tail) must not cut the video short
    filters = [f for f in (audio_filter, "apad" if audio else "") if f]
    if filters:
        args += ["-af", ",".join(filters)]
    if duration:
        args += ["-t", f"{duration:.3f}"]
    args += ["-shortest", "-movflags", "+faststart", vcommon.mixed(out)]
    p = run_ffmpeg(args, timeout)
    if p.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"ffmpeg could not write {os.path.basename(out)}: {clean((p.stderr or '')[-400:])}")


def loudness_fix(audio: str, out: str, measured: dict, cfg: dict, timeout: int) -> str:
    """One correction of the mix: a gain to the target, then a limiter at the true peak ceiling (DECISIONS.md 260: alimiter with latency=1)."""
    target_i = float(cfg["voice"].get("loudness_lufs", -14))
    target_tp = float(cfg["voice"].get("true_peak_dbtp", -1.5))
    lufs = measured.get("lufs")
    gain = (target_i - lufs) if lufs is not None else 0.0
    gain = max(-12.0, min(12.0, gain))
    ceiling = 10 ** ((target_tp - 0.2) / 20)
    af = f"volume={gain:.2f}dB,alimiter=limit={ceiling:.4f}:attack=5:release=50:latency=1"
    p = run_ffmpeg(["-i", vcommon.mixed(audio), "-af", af, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", vcommon.mixed(out)], timeout)
    if p.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"ffmpeg could not correct the loudness of {os.path.basename(audio)}: {clean((p.stderr or '')[-300:])}")
    return f"gain {gain:+.2f} dB, limiter at {target_tp - 0.2:.1f} dBTP"


def post_pass(video: str, audio: str | None, out: str, res: dict, cfg: dict, timeout: int, want_duration: float | None) -> list[str]:
    """Fix only what the checks found different, in one ffmpeg pass (plus one on the mix for the loudness)."""
    ch = res["checks"]
    done: list[str] = []
    reencode = not all(ch[k]["ok"] for k in ("video_codec", "profile", "pix_fmt", "fps"))
    scale = not (ch["width"]["ok"] and ch["height"]["ok"])
    if scale:
        reencode = True
    audio_src = audio
    af = ""
    if not ch["loudness"]["ok"] and audio and ch["loudness"].get("hard", True):
        fixed = os.path.join(os.path.dirname(out), os.path.basename(out)[:-4] + ".mix-fixed.wav")
        done.append("loudness: " + loudness_fix(audio, fixed, ch["loudness"], cfg, timeout))
        audio_src = fixed
    duration = None
    if not ch["duration"]["ok"] and want_duration and ch["duration"].get("got", 0) > want_duration:
        duration = want_duration
        done.append(f"duration trimmed to {want_duration:.3f} s")
    if "max_seconds" in ch and not ch["max_seconds"]["ok"]:
        duration = min(duration or float("inf"), ch["max_seconds"]["want"])
        done.append(f"hook 2 cut to {duration:.3f} s")
    if reencode:
        done.append("video re-encoded to H.264 High yuv420p 30 fps" + (" at 1080x1920" if scale else ""))
    if not (ch["audio_present"]["ok"] and ch["audio_codec"]["ok"] and ch["sample_rate"]["ok"]):
        done.append("audio muxed again as AAC 48 kHz")
    tmp = out[:-4] + ".post.mp4"
    mux(video, audio_src, tmp, cfg, timeout, duration=duration, reencode_video=reencode, scale=scale, audio_filter=af)
    os.replace(tmp, out)
    return done


# ------------------------------------------------------------------------------------------------ the stage

def one_file(label: str, project: str | None, audio: str | None, out: str, video_tmp: str, cfg: dict, timeouts: dict,
             gpu_flag: str, want_duration: float | None, hook2: bool, fallback_src: str | None = None) -> dict:
    """Render, mux, check and post-pass one output. Returns {render, checks..., pass, post_pass, audio}."""
    quality = str(cfg["render"].get("quality", "looks"))
    t_render = int(timeouts.get("render_hook2_seconds" if hook2 else "render_final_seconds", 1200 if hook2 else 5400))
    t_mux = int(timeouts.get("mux_seconds", 900))
    info: dict = {"label": label, "audio": os.path.relpath(audio, os.path.dirname(os.path.dirname(out))).replace("\\", "/") if audio else None,
                  "post_pass": [], "fallback": None}
    if project and os.path.isfile(os.path.join(project, "index.html")):
        activity("rendering hook 2 clip" if hook2 else "rendering final video")
        rinfo = render_video(project, video_tmp, quality, gpu_flag, t_render)
        info["render"] = {k: rinfo.get(k) for k in ("rc", "seconds", "ok")}
        if not rinfo["ok"]:
            raise RuntimeError(f"the HyperFrames render of {label} failed (exit {rinfo.get('rc')}): {clean((rinfo.get('stderr') or rinfo.get('stdout') or '')[-300:])}")
        say("INFO", f"S13: {label} rendered at 1080x1920 in {rinfo['seconds']} s ({quality}{', ' + gpu_flag if gpu_flag else ''}); muxing the mix")
        mux(video_tmp, audio, out, cfg, t_mux)
    elif fallback_src and os.path.isfile(fallback_src):
        # no hook 2 project (S10 could not build the alternate clip): the reel's own first seconds, flagged
        info["fallback"] = "the first seconds of the reel"
        mux(fallback_src, None, out, cfg, t_mux, duration=float(cfg["render"].get("hook2_max_s", 3.5)), reencode_video=True)
        flag(f"no hook 2 clip was built by the visual stage: {os.path.basename(out)} is the reel's first {cfg['render'].get('hook2_max_s', 3.5)} s")
    else:
        raise FileNotFoundError(f"{label}: no project to render ({project})")
    res = check_file(out, want_duration, cfg, hook2=hook2)
    if not res["pass"]:
        say("WARN", f"S13: {label} differs from the target ({failing_text(res)}): one ffmpeg post-pass")
        src_video = video_tmp if os.path.isfile(video_tmp) else out
        info["post_pass"] = post_pass(src_video, audio, out, res, cfg, t_mux, want_duration)
        res = check_file(out, want_duration, cfg, hook2=hook2)
    info.update(res)
    return info


def run(args) -> int:
    vcommon.setup_streams()
    run_dir = vcommon.mixed(args.run_dir)
    stage_dir = vcommon.mixed(args.stage_dir)
    os.makedirs(stage_dir, exist_ok=True)
    cfg = vcommon.load_config() if not args.config else vcommon.load_json(args.config)
    cfg.setdefault("render", {})
    cfg.setdefault("voice", {})
    timeouts = cfg.get("timeouts") or {}
    build_dir = os.path.join(run_dir, "10-build")
    project = os.path.join(build_dir, "project")
    hook2_project = os.path.join(build_dir, "hook2")
    voice = os.path.join(run_dir, "08-voiceover", "vo.wav")
    voice_hook2 = os.path.join(run_dir, "08-voiceover", "vo_hook2.wav")
    mix = os.path.join(run_dir, "11-sfx", "mix.wav")
    mix_hook2 = os.path.join(run_dir, "11-sfx", "mix_hook2.wav")
    for p, what in ((os.path.join(project, "index.html"), "10-build/project/index.html"), (voice, "08-voiceover/vo.wav")):
        if not os.path.isfile(p):
            error(f"{what} is missing: the stage that writes it did not run")
            return 2
    if not os.path.isfile(mix):
        flag("no 11-sfx/mix.wav from the sound stage: the final render carries the voice alone")
        mix = voice
    build = vcommon.load_json(os.path.join(build_dir, "build.json")) if os.path.isfile(os.path.join(build_dir, "build.json")) else {}
    gpu_flag = str(build.get("render_flag") or "")
    plan = vcommon.load_json(os.path.join(build_dir, "plan.json")) if os.path.isfile(os.path.join(build_dir, "plan.json")) else {}
    voice_dur = ffprobe_duration(voice)
    plan_dur = float(plan.get("duration_ms", 0) or 0) / 1000
    if plan_dur and abs(plan_dur - voice_dur) > 0.05:
        say("WARN", f"S13: the plan runs {plan_dur:.3f} s and the voice {voice_dur:.3f} s; the voice is the reference")
    final = os.path.join(stage_dir, "final.mp4")
    video_tmp = os.path.join(stage_dir, "video.mp4")
    hook2_out = os.path.join(stage_dir, "hook2.mp4")
    hook2_video = os.path.join(stage_dir, "video_hook2.mp4")
    render = {"written_by": STAGE, "checked": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "files": {"reel": "final.mp4", "hook2": "hook2.mp4", "video": "video.mp4"},
              "render_flag": gpu_flag, "quality": cfg["render"].get("quality", "looks"), "voice_seconds": round(voice_dur, 3),
              "checks": {}, "pass": False, "post_pass": {}}
    try:
        reel = one_file("the reel", project, mix, final, video_tmp, cfg, timeouts, gpu_flag, voice_dur, hook2=False)
        render["checks"]["reel"] = reel["checks"]
        render["post_pass"]["reel"] = reel["post_pass"]
        render["reel"] = {k: reel.get(k) for k in ("render", "audio", "failing", "soft_failing", "pass", "probe")}
        # hook 2: its own voice and sounds on the clip's timeline (10-build/hook2/plan.json), 3.5 s at most
        h2_audio = mix_hook2 if os.path.isfile(mix_hook2) else (voice_hook2 if os.path.isfile(voice_hook2) else None)
        if h2_audio == voice_hook2:
            flag("no 11-sfx/mix_hook2.wav: the hook 2 clip carries its voice alone")
        h2_plan = vcommon.load_json(os.path.join(hook2_project, "plan.json")) if os.path.isfile(os.path.join(hook2_project, "plan.json")) else {}
        h2_want = (float(h2_plan.get("duration_ms", 0) or 0) / 1000) or (ffprobe_duration(h2_audio) if h2_audio else None) or None
        h2_project = hook2_project if (h2_audio and os.path.isfile(os.path.join(hook2_project, "index.html"))) else None
        h2 = one_file("the hook 2 clip", h2_project, h2_audio if h2_project else None, hook2_out, hook2_video, cfg, timeouts, gpu_flag,
                      h2_want if h2_project else None, hook2=True, fallback_src=final)
        render["checks"]["hook2"] = h2["checks"]
        render["post_pass"]["hook2"] = h2["post_pass"]
        render["hook2"] = {k: h2.get(k) for k in ("render", "audio", "failing", "soft_failing", "pass", "probe", "fallback")}
        if h2.get("soft_failing"):
            c = h2["checks"]["loudness"]
            flag(f"hook 2 clip loudness {c['lufs']} LUFS, true peak {c['true_peak_dbtp']} dBTP (the reel's target is {c['target_lufs']} LUFS); the clip is short, listen once")
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        vcommon.write_json(os.path.join(stage_dir, "render.json"), render)
        error(f"S13: {exc}")
        return 1
    render["pass"] = bool(render["reel"]["pass"] and render["hook2"]["pass"])
    vcommon.write_json(os.path.join(stage_dir, "render.json"), render)
    for tmp in (hook2_video,):
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    rc = render["reel"]
    ch = rc["probe"]
    lo = render["checks"]["reel"]["loudness"]
    say("INFO", f"S13: final.mp4 {ch.get('video', {}).get('width')}x{ch.get('video', {}).get('height')} {ch.get('video', {}).get('fps')} fps {ch.get('video', {}).get('profile')} {ch.get('video', {}).get('pix_fmt')}, "
                f"{(ch.get('audio') or {}).get('codec')} {(ch.get('audio') or {}).get('sample_rate')} Hz, {float(ch.get('duration', 0)):.2f} s (voice {voice_dur:.2f} s), "
                f"{lo['lufs']} LUFS, {lo['true_peak_dbtp']} dBTP: {'every check passes' if rc['pass'] else 'FAILS ' + ', '.join(rc['failing'])}")
    h = render["hook2"]
    say("INFO", f"S13: hook2.mp4 {float(h['probe'].get('duration', 0)):.2f} s" + (f" ({h['fallback']})" if h.get("fallback") else "")
                + f", {(h['probe'].get('audio') or {}).get('codec')} audio: {'every check passes' if h['pass'] else 'FAILS ' + ', '.join(h['failing'])}")
    if not render["pass"]:
        error("S13: a check still fails after the post-pass: " + "; ".join(
            [f"reel: {failing_text(reel)}"] if not reel["pass"] else []) + ("; " if (not reel["pass"] and not h2["pass"]) else "") + ("hook 2: " + failing_text(h2) if not h2["pass"] else ""))
        return 3
    return 0


def check_cmd(args) -> int:
    vcommon.setup_streams()
    cfg = vcommon.load_config() if not args.config else vcommon.load_json(args.config)
    cfg.setdefault("render", {})
    cfg.setdefault("voice", {})
    want = ffprobe_duration(args.voice) if args.voice else None
    res = check_file(vcommon.mixed(args.file), want, cfg, hook2=args.hook2)
    res.pop("probe", None)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["pass"] else 3


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("run"); sp.add_argument("--run-dir", required=True); sp.add_argument("--stage-dir", required=True)
    sp.add_argument("--config", default=""); sp.set_defaults(func=run)
    sp = sub.add_parser("check"); sp.add_argument("--file", required=True); sp.add_argument("--voice", default="")
    sp.add_argument("--hook2", action="store_true"); sp.add_argument("--config", default=""); sp.set_defaults(func=check_cmd)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
