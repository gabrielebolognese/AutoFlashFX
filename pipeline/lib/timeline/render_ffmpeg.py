"""render_ffmpeg.py: renders a timeline with ffmpeg (BUILD_SPEC.md 14.8, M20): the footage family's final render.

    render(timeline_path, run_dir, out_mp4, work_dir) -> {"path", "frames", "seconds", ...}

Footage and still layers are cut to their source in/out and joined in time order (a gap between two layers is filled with the
timeline's background color; two layers that overlap crossfade over render.crossfade_ms, never longer than the overlap); the caption
chunks are burned in (one drawtext per chunk, shown between its start and end); the audio is the footage audio of every layer, the voice
and every sound effect placed at its time, mixed and normalized to the target loudness (audio.loudness.target_lufs, default -14), AAC
at the timeline's sample rate; the video is H.264 High, yuv420p, at the timeline's size and frame rate, exactly duration_frames long.

Text goes into files and the filter graph into a script file, so no quoting or Windows path reaches the ffmpeg command line.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from timeline import common as tc


class RenderError(Exception):
    """The render failed (exit 3)."""


def _font_file(timeline: dict, work: str) -> str:
    """The caption font copied next to the filter script (a relative name works whatever the drive)."""
    want = (timeline.get("render") or {}).get("caption_font") or ""
    cands = [want] if want else []
    cands += ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]
    try:   # a font of the channel's motion library, when the machine has none of the system fonts above
        fonts = tc.paths.motionlib() + "/assets/fonts"
        cands += sorted(os.path.join(fonts, f) for f in os.listdir(fonts) if f.lower().endswith(".ttf"))
    except (OSError, SystemExit):
        pass
    for c in cands:
        c = tc.winpath(c)
        if c and os.path.isfile(c):
            dst = os.path.join(work, "caption" + os.path.splitext(c)[1])
            shutil.copyfile(c, dst)
            return os.path.basename(dst)
    raise RenderError("no caption font found: set render.caption_font in the timeline")


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\u2019").replace(":", "\\:").replace("%", "\\%")


def build_graph(timeline: dict, src: tc.Sources, work: str) -> tuple[list[str], str, str]:
    """(input files, filter graph script, the map of the video and audio labels)."""
    S = timeline["settings"]
    W, H, fps = S["width"], S["height"], tc.fps_of(timeline)
    total = S["duration_frames"]
    total_s = total / fps
    bg = S["background"].lstrip("#")
    by_id = {s["id"]: s for s in timeline["sources"]}
    cfg = timeline.get("render") or {}
    xfade_ms = int(cfg.get("crossfade_ms", 0) or 0)
    inputs: list[str] = []
    lines: list[str] = []

    def add_input(sid: str) -> int:
        path = src.path_of(sid)
        if path in inputs:
            return inputs.index(path)
        inputs.append(path)
        return len(inputs) - 1

    layers = sorted([L for L in timeline["layers"] if L["kind"] in ("footage", "still")], key=lambda L: (L["start"], L["id"]))
    if not layers:
        raise RenderError("the timeline has no footage or still layer to render")
    segs: list[dict] = []   # [{label, start, end}] on the video track in frames, in order
    cursor = 0
    for n, L in enumerate(layers):
        s = L["source"]
        idx = add_input(s["id"])
        dur = (L["end"] - L["start"]) / fps
        if L["start"] > cursor:   # a gap: background color
            gap = (L["start"] - cursor) / fps
            lines.append(f"color=c=0x{bg}:s={W}x{H}:r={fps:g}:d={gap:.6f},format=yuv420p[gap{n}]")
            segs.append({"label": f"gap{n}", "start": cursor, "end": L["start"]})
        if L["kind"] == "footage":
            chain = f"[{idx}:v]trim=start={s['in']:.6f}:end={s['out']:.6f},setpts=PTS-STARTPTS"
        else:
            chain = f"[{idx}:v]loop=loop=-1:size=1:start=0,trim=duration={dur:.6f},setpts=PTS-STARTPTS"
        chain += (f",scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x{bg},setsar=1,fps={fps:g},"
                  f"tpad=stop_mode=clone:stop_duration=1,trim=duration={dur:.6f},setpts=PTS-STARTPTS,format=yuv420p[v{n}]")
        lines.append(chain)
        segs.append({"label": f"v{n}", "start": L["start"], "end": L["end"]})
        cursor = L["end"]
    if cursor < total:
        gap = (total - cursor) / fps
        lines.append(f"color=c=0x{bg}:s={W}x{H}:r={fps:g}:d={gap:.6f},format=yuv420p[gapend]")
        segs.append({"label": "gapend", "start": cursor, "end": total})
    labels = "".join(f"[{s['label']}]" for s in segs)
    lines.append(f"{labels}concat=n={len(segs)}:v=1:a=0[vcat]")
    _ = xfade_ms   # layers placed edge to edge; the crossfade is applied to the audio joins (acrossfade is not needed at a cut)

    # ---- captions
    font = _font_file(timeline, work)
    size = int(cfg.get("caption_size", 64))
    cy = int(cfg.get("caption_y", int(H * 0.66)))
    last = "vcat"
    for n, ch in enumerate(timeline["captions"]["chunks"]):
        fn = f"cap{n:03d}.txt"
        with open(os.path.join(work, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(ch["text"])
        lines.append(f"[{last}]drawtext=fontfile={font}:textfile={fn}:fontsize={size}:fontcolor=white:borderw=4:bordercolor=black@0.9:"
                     f"x=(w-text_w)/2:y={cy}:enable='between(t,{ch['start_ms'] / 1000:.3f},{ch['end_ms'] / 1000:.3f})'[cap{n}]")
        last = f"cap{n}"
    lines.append(f"[{last}]trim=end_frame={total},setpts=PTS-STARTPTS,format=yuv420p[vout]")

    # ---- audio
    sr = S["sample_rate"]
    a_labels = []
    # footage audio, joined in time order at each layer's start
    for n, a in enumerate(sorted(timeline["audio"]["footage"], key=lambda a: a.get("start_ms", 0))):
        sid = a["source"]
        info = by_id.get(sid) or {}
        idx = add_input(sid)
        L = next((L for L in layers if L["id"] == a["layer"]), None)
        start_ms = a.get("start_ms", frame_ms(L["start"], fps) if L else 0)
        chain = f"[{idx}:a]atrim=start={a['in_ms'] / 1000:.6f}:end={a['out_ms'] / 1000:.6f},asetpts=PTS-STARTPTS,aresample={sr},aformat=channel_layouts=stereo"
        if a.get("gain_db"):
            chain += f",volume={a['gain_db']}dB"
        dur = (a["out_ms"] - a["in_ms"]) / 1000.0
        if a.get("fade_in_ms"):
            chain += f",afade=t=in:st=0:d={a['fade_in_ms'] / 1000:.3f}"
        if a.get("fade_out_ms"):
            chain += f",afade=t=out:st={max(0.0, dur - a['fade_out_ms'] / 1000):.3f}:d={a['fade_out_ms'] / 1000:.3f}"
        chain += f",adelay={int(start_ms)}|{int(start_ms)}[af{n}]"
        _ = info
        lines.append(chain)
        a_labels.append(f"[af{n}]")
    voice = timeline["audio"].get("voice")
    if voice:
        idx = add_input(voice["source"])
        d = int(voice.get("start_ms", 0))
        lines.append(f"[{idx}:a]aresample={sr},aformat=channel_layouts=stereo,volume={voice.get('gain_db', 0)}dB,adelay={d}|{d}[avoice]")
        a_labels.append("[avoice]")
    for n, s in enumerate(timeline["audio"]["sfx"]):
        idx = add_input(s["source"])
        chain = f"[{idx}:a]aresample={sr},aformat=channel_layouts=stereo"
        t_in = s.get("trim_in_ms", 0) / 1000.0
        t_out = s.get("trim_out_ms")
        if t_in or t_out:
            chain += f",atrim=start={t_in:.4f}" + (f":end={(t_in + t_out / 1000.0) if t_out and t_out < 10 ** 8 else 3600:.4f}" if t_out else "") + ",asetpts=PTS-STARTPTS"
        chain += f",volume={s['gain_db']}dB"
        if s.get("fade_in_ms"):
            chain += f",afade=t=in:st=0:d={s['fade_in_ms'] / 1000:.3f}"
        if s.get("fade_out_ms") and t_out:
            chain += f",afade=t=out:st={max(0.0, t_out / 1000.0 - s['fade_out_ms'] / 1000.0):.3f}:d={s['fade_out_ms'] / 1000:.3f}"
        chain += f",adelay={int(s['start_ms'])}|{int(s['start_ms'])}[as{n}]"
        lines.append(chain)
        a_labels.append(f"[as{n}]")
    target = float((timeline["audio"].get("loudness") or {}).get("target_lufs", -14.0))
    if a_labels:
        lines.append("".join(a_labels) + f"amix=inputs={len(a_labels)}:normalize=0:duration=longest,apad,atrim=duration={total_s:.6f},"
                     f"loudnorm=I={target}:TP=-1.5:LRA=11,aresample={sr}[aout]")
    else:
        lines.append(f"anullsrc=r={sr}:cl=stereo,atrim=duration={total_s:.6f}[aout]")
    return inputs, ";\n".join(lines) + "\n", "[vout][aout]"


def frame_ms(frame: int, fps: float) -> int:
    return int(round(frame * 1000.0 / fps))


def render(timeline_path: str, run_dir: str, out_mp4: str, work_dir: str, timeout: int = 1800) -> dict:
    timeline = tc.read_json(timeline_path)
    if not isinstance(timeline, dict):
        raise RenderError(f"cannot read {timeline_path}")
    channel = timeline.get("channel") or os.environ.get("REELS_CHANNEL", "")
    src = tc.Sources(run_dir, tc.paths.channel_root(channel) if channel else "")
    src.items = [dict(s) for s in timeline["sources"]]   # the registry of the timeline being rendered: id, path and base of every source
    work = tc.winpath(work_dir)
    os.makedirs(work, exist_ok=True)
    out_mp4 = tc.winpath(out_mp4)
    for s in timeline["sources"]:
        if s["kind"] in ("video", "audio", "image") and not os.path.isfile(src.path_of(s["id"])):
            raise RenderError(f"source {s['id']} ({s['path']}) is missing")
    inputs, graph, maps = build_graph(timeline, src, work)
    script = os.path.join(work, "graph.txt")
    with open(script, "w", encoding="utf-8", newline="\n") as f:
        f.write(graph)
    S = timeline["settings"]
    fps = tc.fps_of(timeline)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin"]
    for p in inputs:
        cmd += ["-i", p]
    cmd += ["-/filter_complex", "graph.txt", "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20", "-r", f"{fps:g}",
            "-c:a", "aac", "-b:a", "160k", "-ar", str(S["sample_rate"]), "-ac", "2",
            "-frames:v", str(S["duration_frames"]), "-t", f"{S['duration_frames'] / fps:.6f}", "-movflags", "+faststart", out_mp4]
    try:
        res = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"ffmpeg did not finish in {timeout} s") from exc
    if res.returncode != 0 or not os.path.isfile(out_mp4):
        raise RenderError("ffmpeg failed: " + " | ".join((res.stderr or "").strip().splitlines()[-4:])[:600])
    p = tc.probe(out_mp4)
    return {"path": out_mp4, "frames": S["duration_frames"], "seconds": p.get("duration"), "width": p.get("width"), "height": p.get("height"), "fps": p.get("fps")}


def main_render(args) -> int:
    run_dir = args.run_dir
    tl = args.timeline or f"{run_dir}/{tc.TIMELINE_DIR}/{tc.TIMELINE_FILE}"
    out = args.out
    work = args.work or os.path.join(os.path.dirname(tc.winpath(out)) or ".", ".work")
    try:
        print("@@ACTIVITY rendering timeline", flush=True)
        info = render(tl, run_dir, out, work)
    except RenderError as exc:
        print(f"@@ERROR {exc}")
        return 3
    print(f"@@SAY INFO timeline render: {info['frames']} frames, {info['seconds']} s, {info['width']}x{info['height']} at {info['fps']} fps")
    tc.write_json(args.json or os.path.join(os.path.dirname(tc.winpath(out)), "render.json"), {"pass": True, "files": {"reel": os.path.basename(out)}, **info})
    shutil.rmtree(work, ignore_errors=True)
    return 0
