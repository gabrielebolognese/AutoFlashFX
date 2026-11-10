"""compose.py: the timeline of a generated format (BUILD_SPEC.md 14.8, M20): a record of the HyperFrames composition that S13 rendered.

The composition stays the render source; this module describes it: one layer per host of 10-build/project/index.html (the paper canvas,
every component instance of the plan, the caption host), the caption chunks and their words from the plan (09c merged.json), the voice
with the words of 08-voiceover/words.json, every sound of 11-sfx/cues.json, the scene, beat, hook, keyword and end-card markers, and the
sources (final.mp4, the composition, the voice, the sounds, the brand assets), each with its size and sha256. Nothing is decided here:
every value comes from a file a stage wrote.

    compose.build(run_dir, out_path=None, config=None) -> the timeline dict (written to <run>/timeline/timeline.json when out_path is given)
"""
from __future__ import annotations

import os
import re
import sys

from timeline import common as tc

HOST_RE = re.compile(r"<div\s+id=\"([^\"]+)\"\s+class=\"clip\"([^>]*)>")
ATTR_RE = re.compile(r"([\w-]+)=\"([^\"]*)\"")


class BuildError(Exception):
    """An input of the timeline is missing or unreadable (exit 2)."""


def _need(path: str, what: str) -> str:
    if not os.path.isfile(tc.winpath(path)):
        raise BuildError(f"{what} is missing: {path}")
    return path


def read_hosts(index_html: str) -> list[dict]:
    """The hosts of the composition in document order: id, component (from data-composition-src), start and duration in seconds, track."""
    try:
        text = open(tc.winpath(index_html), encoding="utf-8").read()
    except OSError as exc:
        raise BuildError(f"cannot read the composition {index_html}: {exc}") from exc
    hosts = []
    for m in HOST_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(2)))
        src = attrs.get("data-composition-src", "")
        comp = os.path.splitext(os.path.basename(src))[0] if src else ""
        try:
            start, dur = float(attrs.get("data-start", "0")), float(attrs.get("data-duration", "0"))
        except ValueError:
            start, dur = 0.0, 0.0
        hosts.append({"id": m.group(1), "component": comp, "start_s": start, "duration_s": dur,
                      "track": int(attrs.get("data-track-index", "0") or 0), "kind": attrs.get("data-track-kind", "")})
    return hosts


def background_of(index_html: str) -> str:
    try:
        text = open(tc.winpath(index_html), encoding="utf-8").read()
    except OSError:
        return "#000000"
    m = re.search(r"html,\s*body\s*\{[^}]*background:\s*(#[0-9A-Fa-f]{6})", text)
    return m.group(1) if m else "#000000"


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(word).lower())


def sfx_dir(config: dict | None) -> str:
    env = os.environ.get("REELS_SFX_DIR")
    if env:
        return tc.winpath(env).rstrip("/")
    if config:
        try:
            return tc.winpath(paths_cfg(config)).rstrip("/")
        except Exception:  # noqa: BLE001
            pass
    return ""


def paths_cfg(config: dict) -> str:
    return tc.paths.cfg_path(config, "paths.sfx_dir")


def build(run_dir: str, out_path: str | None = None, config: dict | None = None, fmt_id: str = "", channel: str = "") -> dict:
    run_dir = tc.winpath(run_dir).rstrip("/")
    channel = channel or os.environ.get("REELS_CHANNEL", "")
    channel_root = tc.paths.channel_root(channel) if channel else ""
    merged = tc.read_json(_need(f"{run_dir}/09c-transitions/merged.json", "the merged plan (09c-transitions/merged.json)"))
    words = tc.read_json(_need(f"{run_dir}/08-voiceover/words.json", "words.json (08-voiceover)"))
    index_html = _need(f"{run_dir}/10-build/project/index.html", "the composition (10-build/project/index.html)")
    final = _need(f"{run_dir}/13-render/final.mp4", "the final render (13-render/final.mp4)")
    cues = tc.read_json(f"{run_dir}/11-sfx/cues.json", None) or {}
    script = tc.read_json(f"{run_dir}/07-script/script.json", None) or {}
    instances = (tc.read_json(f"{run_dir}/10-build/project/instances.json", None) or {}).get("instances") or []
    by_instance = {i.get("instance"): i for i in instances}
    comp_of_plan = {c["id"]: (s, c) for s in merged.get("scenes", []) for c in s.get("components", [])}

    pf = tc.probe(final)
    if not pf.get("duration"):
        raise BuildError(f"ffprobe cannot read {final}")
    fps_f = pf.get("fps") or float(merged.get("fps") or 30)
    fps_num, fps_den = (int(round(fps_f)), 1) if abs(fps_f - round(fps_f)) < 0.01 else (int(round(fps_f * 1001)), 1001)
    fps = fps_num / fps_den
    duration_frames = max(1, int(round(pf["duration"] * fps)))
    bg = background_of(index_html)

    src = tc.Sources(run_dir, channel_root)
    src.add(final, "video", role="final")
    src.add(index_html, "composition", role="composition", hash_it=True, media=False)
    vo = f"{run_dir}/08-voiceover/vo.wav"
    voice_id = src.add(vo, "audio", role="voice") if os.path.isfile(vo) else ""
    mix = f"{run_dir}/11-sfx/mix.wav"
    if os.path.isfile(mix):
        src.add(mix, "audio", role="mix")

    # ---- layers: bottom to top = the composition's track order, then document order
    layers = []
    hosts = read_hosts(index_html)
    for order, h in sorted(enumerate(hosts), key=lambda p: (p[1]["track"], p[0])):
        start = tc.ms_to_frame(h["start_s"] * 1000, fps)
        end = min(duration_frames, tc.ms_to_frame((h["start_s"] + h["duration_s"]) * 1000, fps))
        layer = {"id": f"L-{h['id']}", "name": h["id"], "start": start, "end": max(start + 1, end), "selector": f"#{h['id']}",
                 "component": h["component"], "source": {"id": "composition", "in": h["start_s"], "out": round(h["start_s"] + h["duration_s"], 3)}}
        if h["kind"] == "captions" or h["component"].startswith("caption-"):
            layer.update(kind="caption-burn", provenance="09b-text")
        else:
            layer.update(kind="composition-scene", provenance="09a-animations" if h["id"] in comp_of_plan else "10-build")
            if h["id"] in comp_of_plan:
                layer["scene"] = comp_of_plan[h["id"]][0]["id"]
            elif by_instance.get(h["id"], {}).get("scene"):
                layer["scene"] = by_instance[h["id"]]["scene"]
        layers.append(layer)

    # ---- the assets the composition uses (images of the brand and of the research)
    assets_root = f"{run_dir}/10-build/project"
    for a in (tc.read_json(f"{assets_root}/instances.json", None) or {}).get("assets") or []:
        full = f"{assets_root}/assets/{a}"
        if os.path.isfile(full):
            src.add(full, "image", role="", prefix="asset", media=True)

    # ---- captions (the plan's chunks, the words as the plan timed them)
    chunks = []
    for n, c in enumerate(merged.get("captions") or [], 1):
        ws = [{"text": str(w["word"]), "start_ms": int(round(w["start_ms"])), "end_ms": int(round(w["end_ms"])), "emphasis": bool(w.get("emphasis"))} for w in c.get("words") or []]
        chunks.append({"id": f"c{n:03d}", "text": tc.undash(" ".join(w["text"] for w in ws)), "start_ms": int(round(c["start_ms"])), "end_ms": int(round(c["end_ms"])),
                       "scene": c.get("scene", ""), "words": ws})
    for ch in chunks:
        for w in ch["words"]:
            w["text"] = tc.undash(w["text"])
    cap_mode = ""
    for h in hosts:
        if h["component"].startswith("caption-"):
            cap_mode = h["component"].split("-", 1)[1]
    captions = {"style": str(merged.get("style") or ""), "mode": cap_mode, "chunks": chunks}

    # ---- audio
    voice = None
    if voice_id:
        voice = {"source": voice_id, "gain_db": 0.0, "start_ms": 0,
                 "words": [{"text": str(w["word"]), "start_ms": int(round(w["start_ms"])), "end_ms": int(round(w["end_ms"])), **({"beat": w["beat"]} if w.get("beat") else {})}
                           for w in words.get("words") or []]}
    sdir = sfx_dir(config)
    sfx = []
    for cue in cues.get("cues") or []:
        fname = cue.get("file") or ""
        full = f"{sdir}/{fname}" if sdir else fname
        sid = src.add(full, "audio", role="", prefix="sfx", hash_it=True) if fname else ""
        ev = cue.get("event") or {}
        start = float(cue.get("reel_start_ms", cue.get("ms", 0)) or 0)
        play = cue.get("play_ms")
        sfx.append({"id": str(cue.get("id")), "source": sid, "start_ms": int(round(start)), "trim_in_ms": 0,
                    "trim_out_ms": int(round(play)) if play else None, "fade_in_ms": int(round(cue.get("fade_in_ms", 0) or 0)),
                    "fade_out_ms": int(round(cue.get("fade_out_ms", 0) or 0)), "gain_db": round(float(cue.get("gain_db", 0.0) or 0.0), 2),
                    "cue_type": str(cue.get("cue_type") or ""),
                    "event": f"{ev.get('instance', '')}:{ev.get('type', '')}@{int(round(float(cue.get('ms', 0) or 0)))}"})
    loud = ((words.get("loudness") or {}) if isinstance(words.get("loudness"), dict) else {})
    audio = {"voice": voice, "sfx": sfx, "footage": [], "music": [],
             "loudness": {"target_lufs": -14.0, "true_peak_dbtp": -1.5}}
    _ = loud

    # ---- markers
    markers = []
    for s in merged.get("scenes") or []:
        markers.append({"id": f"scene-{s['id']}", "kind": "scene", "frame": tc.ms_to_frame(s["start_ms"], fps), "label": f"{s['id']} ({s.get('beat_type', '')})"})
    hook_end = None
    for b in words.get("beats") or []:
        markers.append({"id": f"beat-{b['id']}", "kind": "beat", "frame": tc.ms_to_frame(b["start_ms"], fps), "label": f"{b['id']} {b.get('type', '')}"})
        if b.get("type") == "hook" and hook_end is None:
            hook_end = b
    if hook_end:
        markers.append({"id": "hook-end", "kind": "hook-end", "frame": tc.ms_to_frame(hook_end["end_ms"], fps), "label": "the hook ends"})
    cta = (merged.get("branding") or {}).get("cta_scene")
    for s in merged.get("scenes") or []:
        if cta and s["id"] == cta:
            markers.append({"id": "end-card", "kind": "end-card", "frame": tc.ms_to_frame(s["start_ms"], fps), "label": f"the end card ({s['id']})"})
    keyword = str((script.get("ask") or {}).get("keyword") or "")
    if keyword:
        kw_ms = None
        for b in words.get("beats") or []:
            if b.get("type") == "ask":
                kw_ms = b["start_ms"]
        for w in words.get("words") or []:
            if _norm(w["word"]) == _norm(keyword) and (kw_ms is None or w["start_ms"] >= kw_ms):
                kw_ms = w["start_ms"]
                break
        if kw_ms is not None:
            markers.append({"id": "keyword", "kind": "keyword", "frame": tc.ms_to_frame(kw_ms, fps), "label": f"the comment keyword {keyword}"})
    markers.sort(key=lambda m: (m["frame"], m["id"]))

    transitions = [{"from": t["from"], "to": t["to"], "type": str(t["type"]), "duration_ms": int(round(t["duration_ms"]))} for t in merged.get("transitions") or []]

    timeline = {
        "version": 1,
        "format": fmt_id or os.environ.get("REELS_FORMAT", ""),
        "channel": channel,
        "run": os.path.basename(run_dir),
        "settings": {"width": int(pf.get("width") or 1080), "height": int(pf.get("height") or 1920), "fps": {"num": fps_num, "den": fps_den},
                     "duration_frames": duration_frames, "sample_rate": int(pf.get("sample_rate") or 48000), "background": bg},
        "sources": src.items,
        "layers": layers,
        "captions": captions,
        "audio": audio,
        "transitions": transitions,
        "markers": markers,
        "provenance": {"written_by": "timeline", "render_source": "composition",
                       "inputs": {"plan": "09c-transitions/merged.json", "words": "08-voiceover/words.json", "cues": "11-sfx/cues.json",
                                  "composition": "10-build/project/index.html", "render": "13-render/final.mp4"}},
    }
    if out_path:
        tc.write_json(out_path, timeline)
    return timeline


def main_build(args) -> int:
    cfg = None
    try:
        import config as cfgmod
        cfg = cfgmod.load()
    except Exception:  # noqa: BLE001
        cfg = None
    try:
        t = build(args.run_dir, args.out, cfg, fmt_id=args.format or "", channel=args.channel or "")
    except BuildError as exc:
        print(f"@@ERROR {exc}")
        return 2
    s = t["settings"]
    print(f"@@SAY INFO timeline: {len(t['layers'])} layers, {len(t['captions']['chunks'])} caption chunks, "
          f"{len(t['audio']['sfx'])} sounds, {len(t['markers'])} markers, {s['duration_frames']} frames at {s['fps']['num']}/{s['fps']['den']} fps")
    return 0
