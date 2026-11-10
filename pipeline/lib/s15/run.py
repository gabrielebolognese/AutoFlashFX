"""run.py: the S15 stage (BUILD_SPEC.md S15 and 14.9, M21): timeline.json in, a Shorts Editor project folder out.

  run_stage(run_dir, opts) -> summary dict (also written as <run>/s15-project/editor.json)

Order: manifest, capture (composition formats) or footage layers, mapping, rendering of the sprites and overlays, audio, captions,
the project folder, validation (the editor's CLI when the manifest has it, else the S15 validator), the layout and duration and mix
checks (a layer that fails drops one level and the project is written again, at most twice), the editor.json summary, logs/editor-gaps.md.
At the cap (editor.cap_minutes) or on an error it writes the minimal project: the visuals without captions as one plate, the sounds, the
baked captions and the hidden caption track; if even that fails, project/FAILED.md. The export goes on in every case.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from . import audio as saudio  # noqa: E402
from . import capture as scapture  # noqa: E402
from . import checks, gaps, geom, mapper, validate, writer  # noqa: E402
from . import manifest as smanifest  # noqa: E402
from .render import Renderer  # noqa: E402

STAGE = "s15-project"


def say(msg: str) -> None:
    print(f"@@SAY INFO {msg}", flush=True)


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


class Cap(Exception):
    pass


class Opts:
    def __init__(self, **kw):
        self.run_dir = kw["run_dir"]
        self.out_dir = kw.get("out_dir") or os.path.join(self.run_dir, STAGE)
        self.manifest_file = kw.get("manifest")
        self.stable_dir = kw.get("stable_dir")
        self.editor = kw.get("editor") or {}
        self.channel_root = kw.get("channel_root") or ""
        self.tokens_file = kw.get("tokens") or ""
        self.tokens_dict = kw.get("tokens_dict") or None
        self.own_fonts = kw.get("own_fonts") or ""
        self.sfx_dir = kw.get("sfx_dir") or ""
        self.cap_seconds = float(kw.get("cap_seconds") or float(self.editor.get("cap_minutes", 25)) * 60)
        self.reuse_capture = bool(kw.get("reuse_capture"))
        self.force_fail = kw.get("force_fail") or os.environ.get("REELS_S15_FAIL") or ""
        self.no_parity = bool(kw.get("no_parity")) or str(self.editor.get("parity", "true")).lower() == "false"
        self.channel = kw.get("channel") or ""
        self.git_hash = kw.get("git_hash") or ""


def resolve_sources(timeline: dict, run_dir: str, channel_root: str) -> dict:
    out = {}
    for s in timeline.get("sources", []):
        if s["base"] == "run":
            out[s["id"]] = f"{run_dir}/{s['path']}"
        elif s["base"] == "channel":
            out[s["id"]] = f"{channel_root}/{s['path']}"
        else:
            out[s["id"]] = s["path"]
    return out


def hosts_of(timeline: dict, project: str) -> list[dict]:
    from review import common as rc
    by_id = {h["id"]: h for h in rc.read_hosts(project)}
    fps = timeline["settings"]["fps"]["num"] / timeline["settings"]["fps"]["den"]
    out = []
    for lay in timeline["layers"]:
        if lay["kind"] not in ("composition-scene", "caption-burn") or not lay.get("selector"):
            continue
        h = by_id.get(lay["selector"].lstrip("#"))
        if h is None:
            continue
        h = dict(h)
        h["component"] = lay.get("component") or h["component"]
        h["start_frame"], h["end_frame"] = int(lay["start"]), int(lay["end"])
        h["start_ms"] = int(round(h["start_frame"] * 1000.0 / fps)) if False else h["start_ms"]
        out.append(h)
    return out


# ---------------------------------------------------------------------------------------------------- captions


def caption_cues(timeline: dict, fps: float, word_hosts: list[dict], native: bool) -> list[dict]:
    """The cues of the caption track: a cue per spoken word inside the word-mode caption hosts (native, one word at a time with the emphasis
    words restyled), or a cue per chunk with its word timings (the hidden track that goes with baked captions)."""
    cues = []
    chunks = (timeline.get("captions") or {}).get("chunks", [])
    if native:
        spans = [(h["start_ms"], h["end_ms"]) for h in word_hosts]
        for ch in chunks:
            words = ch.get("words") or []
            for i, w in enumerate(words):
                if spans and not any(a - 5 <= w["start_ms"] < b for a, b in spans):
                    continue
                start = max(0, int(round(w["start_ms"] * fps / 1000.0)))
                end_ms = w["end_ms"]
                nxt = words[i + 1]["start_ms"] if i + 1 < len(words) else None
                end = max(start + 1, int(round((nxt if nxt is not None and nxt < end_ms + 80 else end_ms) * fps / 1000.0)))
                cue = {"name": f"Caption {w['text']}", "text": w["text"], "start": start, "duration": end - start}
                if w.get("emphasis"):
                    cue["styleOverride"] = {"text": {"fontFamily": "Instrument Serif", "fontWeight": 400, "italic": True,
                                                     "background": {"enabled": True, "color": {"r": 0.8627, "g": 0.3961, "b": 0.1961, "a": 1}, "paddingX": 22, "paddingY": 8, "radius": 6, "mode": "block"}}}
                cues.append(cue)
        return cues
    for ch in chunks:
        a = int(round(ch["start_ms"] * fps / 1000.0))
        b = max(a + 1, int(round(ch["end_ms"] * fps / 1000.0)))
        words = []
        for w in ch.get("words") or []:
            ws = int(round(w["start_ms"] * fps / 1000.0)) - a
            we = max(ws + 1, int(round(w["end_ms"] * fps / 1000.0)) - a)
            words.append({"text": w["text"], "start": ws, "end": we})
        cues.append({"name": f"Caption {ch['id']}", "text": ch["text"], "start": a, "duration": b - a, "words": words})
    return cues


def caption_style(tokens: dict, native: bool, manifest, fonts: "writer.Fonts") -> dict:
    colors = (tokens or {}).get("colors") or {}
    cap = ((tokens or {}).get("type") or {}).get("caption") or {}
    zone = ((tokens or {}).get("zones") or {}).get("caption") or {}
    ink = mapper.parse_color("#100904") if not colors.get("ink") else hex_color(colors["ink"])
    accent = hex_color(colors.get("accent", "#DC6532"))
    font = (((tokens or {}).get("fonts") or {}).get(cap.get("font", "grotesk")) or {})
    family = font.get("family", "Inter Tight")
    fonts.face(family, 800, False)
    fonts.face("Instrument Serif", 400, True)
    size = float(cap.get("font_px", 67))
    style_text = {"fontFamily": family, "fontWeight": 800, "italic": False, "fontSize": size, "fill": ink,
                  "stroke": {"enabled": False, "width": 0, "color": {"r": 0, "g": 0, "b": 0, "a": 1}},
                  "shadow": {"enabled": False, "x": 0, "y": 6, "blur": 16, "color": {"r": 0, "g": 0, "b": 0, "a": 0.6}},
                  "background": {"enabled": False, "color": accent, "paddingX": 22, "paddingY": 8, "radius": 6, "mode": "block"},
                  "textCase": "none", "letterSpacing": round(-0.02 * size, 3), "lineHeight": 1.0, "align": "center", "verticalAnchor": "middle"}
    style = {"text": style_text, "position": "custom", "x": 0, "y": round(float(zone.get("center_y", 1332)) - 960.0, 2), "maxWidth": float(zone.get("max_width", 620)), "maxLines": 1,
             "highlight": {"mode": "none", "color": accent, "inactiveColor": ink}}
    if native and manifest.lists("captions.cueAnims", "fade"):
        style["anim"] = {"in": {"kind": "fade", "frames": 4}, "out": {"kind": "fade", "frames": 2}}
    return style


def footage_caption_style() -> dict:
    """The caption style of a footage format: white text with a black outline near the bottom (the cut stage's burned captions)."""
    white, black = {"r": 1, "g": 1, "b": 1, "a": 1}, {"r": 0, "g": 0, "b": 0, "a": 1}
    text = {"fontFamily": "Inter", "fontWeight": 800, "italic": False, "fontSize": 64, "fill": white, "stroke": {"enabled": True, "width": 6, "color": black},
            "shadow": {"enabled": False, "x": 0, "y": 6, "blur": 16, "color": {"r": 0, "g": 0, "b": 0, "a": 0.6}},
            "background": {"enabled": False, "color": {"r": 0, "g": 0, "b": 0, "a": 0.7}, "paddingX": 28, "paddingY": 12, "radius": 16, "mode": "block"},
            "textCase": "none", "letterSpacing": 0, "lineHeight": 1.2, "align": "center", "verticalAnchor": "middle"}
    return {"text": text, "position": "bottom", "x": 0, "y": 0, "maxWidth": 900, "maxLines": 2, "highlight": {"mode": "color", "color": {"r": 1, "g": 0.85, "b": 0.2, "a": 1}, "inactiveColor": white}}


def hex_color(h: str) -> dict:
    h = h.lstrip("#")
    return {"r": round(int(h[0:2], 16) / 255.0, 4), "g": round(int(h[2:4], 16) / 255.0, 4), "b": round(int(h[4:6], 16) / 255.0, 4), "a": 1}


# ---------------------------------------------------------------------------------------------------- the stage


def deadline(opts: Opts, t0: float) -> None:
    if time.time() - t0 > opts.cap_seconds:
        raise Cap(f"the {opts.cap_seconds / 60:.0f}-minute cap of S15 was reached")


def build_once(opts: Opts, tl: dict, manifest, fonts: "writer.Fonts", tokens: dict, layers_json: dict | None, downgrades: dict, raster_cache: dict, t0: float,
               renderer: Renderer | None, hosts: list[dict]) -> tuple[dict, "writer.Builder", list[dict]]:
    st = tl["settings"]
    fps = st["fps"]["num"] / st["fps"]["den"]
    total = int(st["duration_frames"])
    cfg = dict(opts.editor)
    if layers_json and layers_json.get("tolerance_px") is not None:
        cfg["affine_tolerance_px"] = float(layers_json["tolerance_px"]) + 0.01
    ctx = mapper.Ctx(manifest, fonts.lookup(), fps, st["width"], st["height"], cfg, downgrades)
    name = f"{os.path.basename(opts.run_dir)}"
    b = writer.Builder(ctx, manifest, os.path.join(opts.out_dir, "project"), name, fonts, st["background"], total)
    items: list[dict] = []
    sources = resolve_sources(tl, opts.run_dir, opts.channel_root)
    host_by_id = {h["id"]: h for h in hosts}
    if layers_json:
        items = mapper.analyze(ctx, layers_json)
    scene_index = {}
    for lay in tl["layers"]:
        if lay.get("scene") and lay["scene"] not in scene_index:
            scene_index[lay["scene"]] = len(scene_index) + 1
    t_items = time.time()
    for n_item, it in enumerate(items):
        deadline(opts, t0)
        if n_item and n_item % 40 == 0:
            say(f"S15: {n_item}/{len(items)} layers built ({time.time() - t_items:.0f}s)")
        label = f"S{scene_index.get(it['scene'], 0):02d}"
        if it["level"] == "native":
            b.add_native(it, label)
            continue
        host = host_by_id[it["host"]]
        key = (it["key"], it["level"], it.get("f_star"))
        if it["level"] == "sprite":
            if key not in raster_cache:
                raster_cache[key] = renderer.sprite(host, it["li"], it["f_star"], it["key"], it.get("quads"))
            b.add_sprite(it, raster_cache[key], label)
        else:
            if key not in raster_cache:
                raster_cache[key] = renderer.overlay(host, it["li"], it["start"], it["end"], it["key"], it.get("quads"))
            b.add_overlay(it, raster_cache[key], label)
    say(f"S15: {len(items)} layers done in {time.time() - t_items:.0f}s")
    # footage layers (the footage family: clips and stills as native clips)
    for lay in tl["layers"]:
        if lay["kind"] in ("footage", "still"):
            add_footage_layer(b, tl, lay, sources, fps, opts)
    # captions
    cap_hosts = [h for h in hosts if h.get("captions")]
    word_hosts = [h for h in cap_hosts if h["component"] == "caption-word"]
    group_hosts = [h for h in cap_hosts if h["component"] != "caption-word"]
    words_all = [w for ch in (tl.get("captions") or {}).get("chunks", []) for w in ch.get("words", [])]
    needs_emph = any(w.get("emphasis") for w in words_all)
    miss = manifest.captions_missing(False, needs_emph, False, False, True)
    native_caps = not miss and bool(word_hosts) and bool(words_all)
    if native_caps:
        for h in word_hosts:
            pass
    baked_hosts = (group_hosts if native_caps else cap_hosts)
    cap_count = 0
    for h in baked_hosts:
        if renderer is None:
            break
        deadline(opts, t0)
        key = ("captions", h["id"])
        if manifest.has("media.videoAlpha") or manifest.has("media.imageSequence") or manifest.has("media.animatedImage"):
            # the caption words move every frame (they rise while they live): one alpha video of the host is exact, a PNG per frame is not editable either
            if key not in raster_cache:
                raster_cache[key] = renderer.overlay(h, None, h["start_frame"], h["end_frame"], f"caption-{h['id']}", None)
            fake = {"scene": "", "host": h["id"], "layer": "captions", "layer_name": "captions", "start": h["start_frame"], "end": h["end_frame"], "missing": list(miss), "why": [], "z": 0}
            b.add_overlay(fake, raster_cache[key], "", to_captions=True)
            cap_count += 1
            continue
        if key not in raster_cache:
            raster_cache[key] = renderer.caption_states(h, h["start_frame"], h["end_frame"], f"caption-{h['id']}")
        b.add_baked_captions(raster_cache[key])
        cap_count += len(raster_cache[key])
    say(f"S15: captions done at {time.time() - t0:.0f}s")
    chunks = (tl.get("captions") or {}).get("chunks", [])
    footage_mode = not hosts and any(l["kind"] in ("footage", "still") for l in tl["layers"])
    if footage_mode and chunks and manifest.clip_kind("caption"):
        # the footage family burns its captions in; in the project they are a visible native caption track, one cue per chunk with word timings
        b.add_caption_track(caption_cues(tl, fps, [], False), footage_caption_style(), hidden=False)
        fonts.face("Inter", 800, False)
        native_caps = True
    elif chunks:
        cues = caption_cues(tl, fps, word_hosts, native_caps)
        if cues:
            b.add_caption_track(cues, caption_style(tokens, native_caps, manifest, fonts), hidden=not native_caps)
    b.caption_native = native_caps
    b.caption_missing = miss
    if not native_caps and miss and cap_hosts:
        for m_key in miss:
            b.fallbacks.append({"scene": "", "from": 0, "to": total, "layer": "captions", "name": "captions", "level": "sprite", "missing": [m_key], "why": ["captions baked as images"]})
    # audio
    cues_json = read_json(os.path.join(opts.run_dir, "11-sfx", "cues.json"), {})
    voice_src = sources.get("voice") or os.path.join(opts.run_dir, "08-voiceover", "vo.wav")
    master = saudio.master_gain_db(opts.run_dir, cues_json)
    if (tl.get("audio") or {}).get("voice") and os.path.isfile(voice_src):
        aud = saudio.build(opts.run_dir, b.dir, tl, cues_json, voice_src, opts.sfx_dir or None, sources, fps, total, master,
                           tuple(manifest.get("audio.clipGainDb", [-60.0, 12.0])))
        b.add_audio(aud)
        b.audio_notes = aud["notes"]
    else:
        b.audio_clip_ids = {}
        b.audio_notes = []
    # markers
    for mk in tl.get("markers", []):
        if mk.get("kind") in ("scene", "keyword", "comment-keyword", "cta", "hook-end"):
            color = {"scene": "blue", "keyword": "orange", "comment-keyword": "orange", "cta": "red", "hook-end": "green"}.get(mk["kind"], "grey")
            b.markers.append({"id": f"mk-{len(b.markers) + 1:03d}", "frame": int(mk["frame"]), "color": color, "label": mk.get("label") or mk["kind"]})
    return {}, b, items


def add_footage_layer(b: "writer.Builder", tl: dict, lay: dict, sources: dict, fps: float, opts: Opts) -> None:
    src_id = (lay.get("source") or {}).get("id")
    src = sources.get(src_id)
    if not src or not os.path.isfile(src):
        return
    ext = os.path.splitext(src)[1].lower()
    rel = f"media/video/{os.path.basename(src)}" if lay["kind"] == "footage" else f"media/images/{os.path.basename(src)}"
    dst = os.path.join(b.dir, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.isfile(dst):
        shutil.copyfile(src, dst)
    meta = next((s for s in tl["sources"] if s["id"] == src_id), {})
    dur_frames = max(1, int(lay["end"]) - int(lay["start"]))
    if lay["kind"] == "footage":
        mid = b.file_media(rel, "video", os.path.basename(rel), width=meta.get("width") or b.ctx.W, height=meta.get("height") or b.ctx.H, codec="h264",
                           durationUs=int(round(float(meta.get("duration_s") or 0) * 1_000_000)), hasAudio=any(a["layer"] == lay["id"] for a in tl["audio"].get("footage", [])),
                           fps={"num": int(fps), "den": 1})
    else:
        mid = b.file_media(rel, "image", os.path.basename(rel), width=meta.get("width") or b.ctx.W, height=meta.get("height") or b.ctx.H, codec=ext[1:])
    c = b.base_clip("clip", "video" if lay["kind"] == "footage" else "image", lay["name"], int(lay["start"]), dur_frames)
    gain = next((a["gain_db"] for a in tl["audio"].get("footage", []) if a["layer"] == lay["id"]), 0.0)
    has_audio = any(a["layer"] == lay["id"] for a in tl["audio"].get("footage", []))
    in_us = int(round(float(lay["source"]["in"]) * 1_000_000))
    mw, mh = (meta.get("width") or b.ctx.W), (meta.get("height") or b.ctx.H)
    scale = min(b.ctx.W / mw, b.ctx.H / mh) if lay["kind"] == "footage" else min(b.ctx.W / mw, b.ctx.H / mh)
    c.update({"mediaId": mid, "in": in_us if lay["kind"] == "footage" else 0, "out": (in_us if lay["kind"] == "footage" else 0) + int(round(dur_frames * 1_000_000 / fps)), "speed": 1,
              "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "volume": {"gainDb": gain, "muted": not has_audio}, "fades": {"in": 0, "out": 0},
              "transform": {"x": 0, "y": 0, "scale": round(scale, 5), "rotation": 0, "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}, "opacity": 1})
    b.place(c, len(b.clips) + 1)
    b.counts["native"] += 1


def find_layers_json(opts: Opts) -> str:
    return os.path.join(opts.out_dir, "layers.json")


def finish_files(opts: Opts, b: "writer.Builder", doc: dict, manifest, fonts: "writer.Fonts", layers_src: str | None) -> None:
    proj = b.dir
    os.makedirs(proj, exist_ok=True)
    nfonts = fonts.write(proj)
    write_json(os.path.join(proj, "project.json"), doc)
    if layers_src and os.path.isfile(layers_src):
        shutil.copyfile(layers_src, os.path.join(proj, "layers.json"))
    else:
        write_json(os.path.join(proj, "layers.json"), {"hosts": []})
    with open(os.path.join(proj, "FALLBACKS.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(writer.fallbacks_md(b.fallbacks, b.counts, os.path.basename(manifest.source) or "baseline", manifest.schema_version))
    url = str(opts.editor.get("url", "http://localhost:5310/"))
    with open(os.path.join(proj, "OPEN.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(writer.open_txt(url, "exports/<id>-N/project", "exports/<id>-N/project"))


def run_stage(opts: Opts) -> dict:
    t0 = time.time()
    run_dir = opts.run_dir.replace("\\", "/")
    out_dir = opts.out_dir
    os.makedirs(out_dir, exist_ok=True)
    tl = read_json(os.path.join(run_dir, "timeline", "timeline.json"))
    if tl is None:
        raise RuntimeError("timeline/timeline.json is missing: the timeline stage did not run")
    manifest = smanifest.load(opts.stable_dir, opts.manifest_file)
    cli = checks.cli_available(opts.stable_dir) and manifest.has("cli.validate") and not opts.manifest_file
    summary: dict = {"written_by": STAGE, "manifest": {"source": manifest.source, "hash": manifest.hash, "schemaVersion": manifest.schema_version,
                                                         "appVersion": manifest.get("appVersion")}, "needs_review": [], "checks": [], "level": "full", "seconds": 0}
    fps = tl["settings"]["fps"]["num"] / tl["settings"]["fps"]["den"]
    total = int(tl["settings"]["duration_frames"])
    tokens = opts.tokens_dict if opts.tokens_dict is not None else (read_json(opts.tokens_file, {}) if opts.tokens_file else {})
    fonts = writer.Fonts(opts.stable_dir, opts.own_fonts or None, tokens)
    comp = next((s for s in tl["sources"] if s["kind"] == "composition"), None)
    project_src = os.path.dirname(f"{run_dir}/{comp['path']}") if comp else ""
    hosts = hosts_of(tl, project_src) if project_src and os.path.isdir(project_src) else []
    layers_json = None
    renderer = None
    try:
        if opts.force_fail == "full":
            raise RuntimeError("forced failure (REELS_S15_FAIL=full)")
        if hosts:
            lp = find_layers_json(opts)
            if opts.reuse_capture and os.path.isfile(lp):
                layers_json = read_json(lp)
            else:
                say("S15: capturing the layers of the composition")
                layers_json = scapture.capture(run_dir, tl, project_src, lp, log=None, tol_px=float(opts.editor.get("affine_tolerance_px", 2.0)))
        downgrades: dict = {}
        raster_cache: dict = {}
        renderer = Renderer(project_src, os.path.join(out_dir, "project", "media"), manifest, fps, tl["settings"]["width"], tl["settings"]["height"], opts.editor) if hosts else None
        if renderer:
            renderer.__enter__()
        doc = b = items = None
        max_passes = int(os.environ.get("REELS_S15_MAX_PASSES", "3"))
        for attempt in range(max_passes):
            if attempt == 0:
                shutil.rmtree(os.path.join(out_dir, "project"), ignore_errors=True)
            else:   # the rendered sprites, overlays and caption images are kept for the next pass (raster_cache points at them)
                for name in os.listdir(os.path.join(out_dir, "project")):
                    if name != "media":
                        full = os.path.join(out_dir, "project", name)
                        shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)
                shutil.rmtree(os.path.join(out_dir, "project", "media", "audio"), ignore_errors=True)
            os.makedirs(os.path.join(out_dir, "project", "media"), exist_ok=True)
            say(f"S15: building the project (pass {attempt + 1})")
            _, b, items = build_once(opts, tl, manifest, fonts, tokens, layers_json, downgrades, raster_cache, t0, renderer, hosts)
            gen = {"name": "instagramReels", "version": opts.git_hash or "dev", "source": f"runs/{os.path.basename(run_dir)}"}
            doc = b.project(generator=gen)
            finish_files(opts, b, doc, manifest, fonts, find_layers_json(opts))
            bad = layout_failures(opts, b, doc, items, layers_json, renderer, tl, hosts, summary)
            say(f"S15: layout check at {time.time() - t0:.0f}s: " + json.dumps([c for c in summary["checks"] if c.get("check") == "layout"])[:900])
            if not bad or attempt == max_passes - 1:
                summary["layout_remaining"] = sorted(bad)
                break
            for key in bad:
                prev = downgrades.get(key, "native")
                nxt = {"native": "sprite", "sprite": "overlay", "overlay": "plate"}.get(prev, "plate")
                downgrades[key] = nxt
            say(f"S15: {len(bad)} layers drop one level after the layout check")
        summary["downgrades"] = downgrades
        prune_media(doc, os.path.join(out_dir, "project"))
        # the editor's own checks
        if cli:
            ok, msg = checks.cli_normalize(opts.stable_dir, os.path.join(out_dir, "project"))
            if not ok:
                summary["needs_review"].append(f"the editor's normalize failed: {msg[:160]}")
            doc = read_json(os.path.join(out_dir, "project", "project.json"))
            res = checks.cli_validate(opts.stable_dir, os.path.join(out_dir, "project"))
        else:
            res = validate.validate(doc, os.path.join(out_dir, "project"), manifest)
        summary["checks"].append({"check": "validate", "ok": res["ok"], "by": "editor cli" if cli else "S15 validator", "errors": res["errors"][:20], "warnings": len(res.get("warnings", []))})
        if not res["ok"]:
            raise RuntimeError("the project does not validate: " + "; ".join(f"{e['path']}: {e['message']}" for e in res["errors"][:4]))
        summary["checks"].append(checks.duration_check(doc, total))
        final = f"{run_dir}/13-render/final.mp4"
        if os.path.isfile(final) and (tl.get("audio") or {}).get("voice"):
            summary["checks"].append(checks.mix_check(doc, os.path.join(out_dir, "project"), final, total, float(opts.editor.get("mix_tolerance_lu", 0.5)), os.path.join(out_dir, ".work")))
            summary["checks"].append(checks.sound_times_check(doc, tl, fps))
        if cli and not opts.no_parity and manifest.has("cli.render") and manifest.has("cli.compare") and os.path.isfile(final):
            par = checks.cli_parity(opts.stable_dir, os.path.join(out_dir, "project"), final, os.path.join(out_dir, ".work", "parity.mp4"), float(opts.editor.get("parity_ssim", 0.97)),
                                    int(opts.cap_seconds))
            summary["checks"].append({"check": "parity", **{k: v for k, v in par.items() if k != "data"}})
            if not par["ok"]:
                summary["needs_review"].append("the editor's render of the project differs from the video (see editor.json checks.parity)")
        for c in summary["checks"]:
            if not c.get("ok", True):
                summary["needs_review"].append(f"S15 check failed: {c['check']}")
        summary.update({"native": b.counts["native"], "sprites": b.counts["sprite"], "overlays": b.counts["overlay"], "plates": b.counts["plate"],
                        "baked_captions": b.counts["baked_captions"], "captions_native": bool(getattr(b, "caption_native", False)),
                        "layers": b.counts["native"] + b.counts["sprite"] + b.counts["overlay"] + b.counts["plate"], "duration_frames": total})
        summary["baked"] = b.counts["sprite"] + b.counts["overlay"] + b.counts["plate"] + b.counts["baked_captions"]
        gaps_list = gaps.collect(b.fallbacks)
        summary["gaps"] = gaps_list
    except Cap as exc:
        summary["needs_review"].append(str(exc))
        summary = minimal_project(opts, tl, manifest, fonts, tokens, hosts, renderer, summary, str(exc))
    except Exception as exc:  # noqa: BLE001
        say(f"S15: {exc}")
        summary["needs_review"].append(f"S15 failed: {exc}")
        summary = minimal_project(opts, tl, manifest, fonts, tokens, hosts, renderer, summary, traceback.format_exc())
    finally:
        if renderer:
            try:
                renderer.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
    shutil.rmtree(os.path.join(out_dir, ".work"), ignore_errors=True)
    summary["seconds"] = round(time.time() - t0, 1)
    write_json(os.path.join(out_dir, "editor.json"), summary)
    return summary


def prune_media(doc: dict, proj: str) -> None:
    """Remove the files of media/ that no media item uses (what an earlier pass rendered for a layer that dropped a level)."""
    keep = set()
    for m in doc["media"].values():
        keep.add(m["file"]["relPath"])
        seq = m.get("sequence")
        if seq:
            keep.add(seq["dir"].rstrip("/") + "/")
    root = os.path.join(proj, "media")
    for dp, dn, fn in os.walk(root, topdown=False):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), proj).replace("\\", "/")
            if rel in keep or any(rel.startswith(k) for k in keep if k.endswith("/")):
                continue
            try:
                os.remove(os.path.join(dp, f))
            except OSError:
                pass
        try:
            os.rmdir(dp)
        except OSError:
            pass


MEASURE_TEXT_JS = """
async (a) => {
  try { await document.fonts.load((a.italic ? "italic " : "") + a.weight + " " + a.size + "px \\"" + a.family + "\\""); } catch (e) {}
  const c = document.createElement("canvas").getContext("2d");
  c.font = (a.italic ? "italic " : "") + a.weight + " " + a.size + "px \\"" + a.family + "\\"";
  try { c.letterSpacing = a.spacing + "px"; } catch (e) {}
  return a.lines.map((l) => c.measureText(l).width);
}
"""


def layout_failures(opts: Opts, b: "writer.Builder", doc: dict, items: list[dict], layers_json, renderer, tl: dict, hosts: list[dict], summary: dict) -> set:
    """The layer keys whose clips fail the layout check at the middle frame of their scene (native boxes within 2 px, sprites SSIM >= 0.95)."""
    bad: set = set()
    if not items or layers_json is None:
        summary["checks"] = [c for c in summary["checks"] if c.get("check") != "layout"]
        return bad
    ctx = b.ctx
    W, H = ctx.W, ctx.H
    ssim_min = float(opts.editor.get("layout_ssim", 0.95))
    px_tol = float(opts.editor.get("layout_px", 2.0))
    clip_of: dict[str, dict] = {}
    for c in doc["clips"].values():
        clip_of[c["name"]] = c
    host_by_id = {h["id"]: h for h in hosts}
    # each item to its clip by the order the builder created them (names are not unique: match by start, track-agnostic)
    by_start: dict = {}
    for c in doc["clips"].values():
        if c["kind"] in ("solid", "text", "image", "video"):
            by_start.setdefault((c["start"], c["name"].split(" ", 1)[1] if " " in c["name"] else c["name"]), []).append(c)
    checked = failed = 0
    details = []
    scene_mid: dict[str, int] = {}
    for lay in tl["layers"]:
        if lay.get("scene") and lay["kind"] == "composition-scene" and lay["component"] != "paper-canvas":
            a, e = scene_mid.get(lay["scene"], (10 ** 9, 0)) if isinstance(scene_mid.get(lay["scene"]), tuple) else (10 ** 9, 0)
            scene_mid[lay["scene"]] = (min(a, int(lay["start"])), max(e, int(lay["end"])))
    for it in items:
        if it["level"] == "native" and it["part"] == "text" and renderer is not None:
            # native text: Canvas2D in the same font and size as the editor measures it, against the composition's own text box (within 2 px)
            st = it["native"]["style"]
            lines = it["native"]["text"]["value"].split(chr(10))
            x0, y0, x1, y1 = it["native"]["bounds"]
            page, _cid = renderer.page_for(host_by_id[it["host"]], 1.0)
            widths = page.evaluate(MEASURE_TEXT_JS, {"lines": lines, "family": st["fontFamily"], "weight": st["fontWeight"], "italic": st["italic"], "size": st["fontSize"],
                                                     "spacing": st["letterSpacing"]})
            checked += 1
            want_w = x1 - x0
            got_w = max(widths) if widths else 0.0
            if abs(got_w - want_w) > float(opts.editor.get("text_px", 2.0)) + 0.01 * want_w:   # 2 px plus 1 percent: the browser and Canvas2D round a variable font's advances a little apart
                failed += 1
                bad.add(it["layer_key"])
                details.append({"layer": it["key"], "check": "text", "canvas_px": round(got_w, 2), "box_px": round(want_w, 2)})
            continue
        if it["level"] not in ("native", "sprite") or it["part"] == "text":
            continue
        s0, e0 = scene_mid.get(it["scene"], (it["start"], it["end"]))
        mid = (s0 + e0) // 2
        f = min(max(mid, it["start"]), it["end"] - 1)
        k = f - it["start"]
        clip = doc["clips"].get(it.get("clip_id"))
        if clip is None:
            continue
        checked += 1
        if it["level"] == "native" and it["kind"] in ("solid", "image"):
            pose = checks.clip_pose_at(clip, k)
            w, h = (it["native"]["size"]["w"], it["native"]["size"]["h"]) if it["kind"] == "solid" else it["box"]
            if it["kind"] == "image":
                # an image clip's box is the cropped media at its scale; compare the visible box against the captured quad
                cw = it["native"]["nw"] * (1 - it["native"]["crop"]["left"] - it["native"]["crop"]["right"])
                ch = it["native"]["nh"] * (1 - it["native"]["crop"]["top"] - it["native"]["crop"]["bottom"])
                w, h = cw, ch
            quad = checks.box_quad(pose, w, h, W, H)
            want = it["_quad"][k] if "_quad" in it else None
            run_quad = quad_of(layers_json, it, k)
            if run_quad is not None:
                err = max(((quad[i] - run_quad[i]) ** 2 + (quad[i + 1] - run_quad[i + 1]) ** 2) ** 0.5 for i in (0, 2, 4, 6))
                # the corners may be listed from a different corner when the box is rotated by 90 degrees: take the best of the four starts
                best = min(max(((quad[(2 * (i + s)) % 8] - run_quad[(2 * i) % 8]) ** 2 + (quad[(2 * (i + s) + 1) % 8] - run_quad[(2 * i + 1) % 8]) ** 2) ** 0.5 for i in range(4)) for s in range(4))
                err = min(err, best)
                if err > px_tol:
                    failed += 1
                    bad.add(it["layer_key"])
                    details.append({"layer": it["key"], "check": "box", "err_px": round(err, 2)})
        elif it["level"] == "sprite" and renderer is not None:
            host = host_by_id[it["host"]]
            media = doc["media"][clip["mediaId"]]
            exp = renderer_layer_shot(renderer, host, it["li"], f)
            got = checks.composite_sprite(clip, media, b.dir, k, W, H)
            bb = None
            for im in (exp, got):
                bbx = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
                if bbx:
                    bb = bbx if bb is None else (min(bb[0], bbx[0]), min(bb[1], bbx[1]), max(bb[2], bbx[2]), max(bb[3], bbx[3]))
            if bb is None:
                continue
            pad = 8
            bb = (max(0, bb[0] - pad), max(0, bb[1] - pad), min(W, bb[2] + pad), min(H, bb[3] + pad))
            sc = checks.ssim(checks.over_white(exp).crop(bb), checks.over_white(got).crop(bb))
            if sc < ssim_min:
                failed += 1
                bad.add(it["layer_key"])
                details.append({"layer": it["key"], "check": "sprite", "ssim": round(sc, 4)})
    summary["checks"] = [c for c in summary["checks"] if c.get("check") != "layout"]
    summary["checks"].append({"check": "layout", "ok": failed == 0, "checked": checked, "failed": failed, "details": details[:30]})
    return bad


def quad_of(layers_json: dict, it: dict, k: int):
    for h in layers_json["hosts"]:
        if h["id"] != it["host"]:
            continue
        for lay in h["layers"]:
            if lay["id"] != it["layer"]:
                continue
            for run in lay["runs"]:
                if run["start"] == it["start"] and run["end"] == it["end"]:
                    return run["quad"][k] if k < len(run["quad"]) else None
    return None


def renderer_layer_shot(renderer: Renderer, host: dict, li: int, frame: int):
    from .render import ISOLATE_JS
    page, cid = renderer.page_for(host, 1.0)
    page.evaluate(ISOLATE_JS, {"i": li})
    renderer.seek(page, cid, host, frame)
    page.wait_for_timeout(30)
    return renderer.shot(page)


def minimal_project(opts: Opts, tl: dict, manifest, fonts, tokens, hosts, renderer, summary: dict, why: str) -> dict:
    """The fallback: the visuals without captions as one plate, the sound clips, the baked captions and the hidden caption track."""
    out_dir = opts.out_dir
    proj = os.path.join(out_dir, "project")
    shutil.rmtree(proj, ignore_errors=True)
    os.makedirs(os.path.join(proj, "media"), exist_ok=True)
    st = tl["settings"]
    fps = st["fps"]["num"] / st["fps"]["den"]
    total = int(st["duration_frames"])
    try:
        ctx = mapper.Ctx(manifest, fonts.lookup(), fps, st["width"], st["height"], dict(opts.editor), {})
        b = writer.Builder(ctx, manifest, proj, os.path.basename(opts.run_dir), fonts, st["background"], total)
        run_dir = opts.run_dir.replace("\\", "/")
        comp = next((s for s in tl["sources"] if s["kind"] == "composition"), None)
        project_src = os.path.dirname(f"{run_dir}/{comp['path']}") if comp else ""
        cap_hosts = [h for h in hosts if h.get("captions")]
        r2 = renderer
        own = False
        if hosts:
            if r2 is None:
                r2 = Renderer(project_src, os.path.join(proj, "media"), manifest, fps, st["width"], st["height"], opts.editor)
                r2.__enter__()
                own = True
            r2.media_dir = os.path.join(proj, "media")
            plate_rel = "media/plates/visuals.mp4"
            os.makedirs(os.path.join(proj, "media", "plates"), exist_ok=True)
            r2.plate(hosts, 0, total, os.path.join(proj, plate_rel), st["background"])
            b.add_plate(plate_rel, 0, total, "Visuals (plate)")
            for h in cap_hosts:
                b.add_baked_captions(r2.caption_states(h, h["start_frame"], h["end_frame"], f"caption-{h['id']}"))
            if own:
                r2.__exit__(None, None, None)
        sources = resolve_sources(tl, run_dir, opts.channel_root)
        cues_json = read_json(os.path.join(run_dir, "11-sfx", "cues.json"), {})
        voice_src = sources.get("voice") or os.path.join(run_dir, "08-voiceover", "vo.wav")
        if (tl.get("audio") or {}).get("voice") and os.path.isfile(voice_src):
            aud = saudio.build(run_dir, proj, tl, cues_json, voice_src, opts.sfx_dir or None, sources, fps, total, saudio.master_gain_db(run_dir, cues_json))
            b.add_audio(aud)
        chunks = (tl.get("captions") or {}).get("chunks", [])
        if chunks:
            b.add_caption_track(caption_cues(tl, fps, [], False), caption_style(tokens, False, manifest, fonts), hidden=True)
        doc = b.project(generator={"name": "instagramReels", "version": opts.git_hash or "dev", "source": f"runs/{os.path.basename(run_dir)}"})
        finish_files(opts, b, doc, manifest, fonts, None)
        res = validate.validate(doc, proj, manifest)
        if not res["ok"]:
            raise RuntimeError("the minimal project does not validate: " + str(res["errors"][:3]))
        summary.update({"level": "minimal", "native": 0, "sprites": 0, "overlays": 0, "plates": 1, "baked_captions": b.counts["baked_captions"], "layers": 1,
                        "baked": 1 + b.counts["baked_captions"], "captions_native": False, "duration_frames": total, "gaps": []})
        summary["checks"].append({"check": "validate", "ok": True, "by": "S15 validator", "errors": []})
        summary["needs_review"].append("the editable project is the minimal one (a plate, the sounds, baked captions): see editor.json")
        with open(os.path.join(proj, "FALLBACKS.md"), "a", encoding="utf-8", newline="\n") as f:
            f.write("\nThe full mapping failed; this is the minimal project.\n\n" + why[-1500:].replace(chr(0x2014), "-") + "\n")
        return summary
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(proj, ignore_errors=True)
        os.makedirs(proj, exist_ok=True)
        text = f"# S15 failed\n\nNo editable project could be written for this reel. The video, hook clip and captions are fine.\n\n{exc}\n\n{why[-1500:]}\n"
        with open(os.path.join(proj, "FAILED.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace(chr(0x2014), "-"))
        summary.update({"level": "failed", "native": 0, "sprites": 0, "overlays": 0, "plates": 0, "baked_captions": 0, "layers": 0, "baked": 0, "captions_native": False, "gaps": []})
        summary["needs_review"].append("S15 failed completely: project/FAILED.md has the error")
        return summary
