"""validate.py: the S15 validator (BUILD_SPEC.md S15 step 6, M21), used when the manifest has no cli.validate.

It mirrors the rules of the editor's validate.ts and the fields of its types.ts as INTEROP.md states them: types, required fields,
no unknown fields (the field sets grow with the schema version the manifest announces), sorted non-overlapping clips on a track,
every clip on exactly the track it names, media in and out points inside the media, the caption track rules (at most one, above
the video tracks, cues with ordered words), integer frames and microseconds, unique ids and files present.

  validate(project: dict, folder: str, manifest) -> {"ok": bool, "errors": [{"path", "message"}], "warnings": [...]}
  python pipeline/lib/s15 validate <folder> [--manifest file]
"""
from __future__ import annotations

import os

BASE = {"id", "trackId", "kind", "name", "start", "duration", "color", "linkGroup", "group", "enabled", "fallbackOf", "parentId", "autoOrient", "backfaceHidden", "blend",
        "matte", "matteOnly", "masks", "effects"}
MEDIA_CLIP = {"mediaId", "in", "out", "speed", "transform", "opacity", "crop", "volume", "fades", "keyframes", "transitionIn", "transitionOut", "timeRemap", "reverse",
              "frameBlend", "loop", "colorOverrides", "cornerRadius", "stroke", "shadow"}
KIND_FIELDS = {
    "video": BASE | MEDIA_CLIP,
    "audio": BASE | MEDIA_CLIP,
    "image": BASE | MEDIA_CLIP,
    "text": BASE | {"text", "style", "animIn", "animOut", "transform", "opacity", "fades", "keyframes", "transitionIn", "transitionOut", "spans", "counter", "animators"},
    "solid": BASE | {"fill", "shape", "size", "cornerRadius", "cornerRadii", "stroke", "shadow", "transform", "opacity", "fades", "keyframes", "transitionIn", "transitionOut"},
    "caption": BASE | {"text", "words", "styleOverride"},
}
PROJECT_FIELDS = {"schemaVersion", "id", "name", "settings", "media", "bins", "tracks", "clips", "markers", "captionTracks", "textPresetsLocal", "sequences", "meta"}
TRACK_FIELDS = {"id", "kind", "name", "clipIds", "locked", "muted", "solo", "hidden", "targeted", "height", "gainDb", "pan"}
MEDIA_FIELDS = {"id", "kind", "name", "file", "durationUs", "width", "height", "rotation", "fps", "hasAudio", "codec", "audioCodec", "proxy", "analysis", "binId", "addedAt", "size",
                "alpha", "sequence"}
TRANSFORM_FIELDS = {"x", "y", "scale", "scaleY", "rotation", "rotationX", "rotationY", "z", "anchor", "flipH", "flipV"}
LABEL_COLORS = {"red", "orange", "green", "teal", "blue", "violet", "pink", "grey"}
KEYFRAME_PROPS_BASE = {"transform.x", "transform.y", "transform.scale", "transform.scaleY", "transform.rotation", "opacity", "volume.gainDb"}


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(project: dict, folder: str, manifest=None) -> dict:
    errs: list[dict] = []
    warns: list[dict] = []

    def err(path: str, msg: str) -> None:
        errs.append({"path": path, "message": msg})

    def warn(path: str, msg: str) -> None:
        warns.append({"path": path, "message": msg})

    def unknown(path: str, obj: dict, allowed: set) -> None:
        for k in obj:
            if k not in allowed:
                err(f"{path}.{k}", "unknown field")

    sv = project.get("schemaVersion")
    if not is_int(sv) or sv < 1:
        err("schemaVersion", "must be an integer >= 1")
    elif manifest is not None and sv != manifest.schema_version:
        err("schemaVersion", f"the manifest's schemaVersion is {manifest.schema_version}, the project says {sv}")
    unknown("", project, PROJECT_FIELDS)
    for req in ("id", "name", "settings", "media", "bins", "tracks", "clips", "markers", "captionTracks", "textPresetsLocal", "meta"):
        if req not in project:
            err(req, "required field missing")
    if not isinstance(project.get("id"), str) or not project.get("id"):
        err("id", "must be a non-empty string")
    st = project.get("settings") or {}
    for k in ("width", "height"):
        if not is_int(st.get(k)) or st[k] < 1:
            err(f"settings.{k}", "must be an integer >= 1")
    fps = st.get("fps") or {}
    if not (is_int(fps.get("num")) and is_int(fps.get("den")) and fps["num"] > 0 and fps["den"] > 0):
        err("settings.fps", "must be {num, den} positive integers")
        fps_v = 30.0
    else:
        fps_v = fps["num"] / fps["den"]
    if st.get("sampleRate") != 48000:
        err("settings.sampleRate", "must be 48000")
    bg = st.get("background") or {}
    if not all(is_num(bg.get(c)) and 0 <= bg[c] <= 1 for c in "rgba"):
        err("settings.background", "must be an RGBA color with channels 0..1")

    media = project.get("media") or {}
    for mid, m in media.items():
        p = f"media.{mid}"
        if not isinstance(m, dict):
            err(p, "must be an object")
            continue
        unknown(p, m, MEDIA_FIELDS)
        if m.get("id") != mid:
            err(f"{p}.id", "must equal its key")
        if m.get("kind") not in ("video", "audio", "image", "lottie"):
            err(f"{p}.kind", "unknown kind")
        rel = (m.get("file") or {}).get("relPath")
        if not rel:
            err(f"{p}.file.relPath", "required")
        elif ".." in rel.split("/") or rel.startswith("/") or "\\" in rel:
            err(f"{p}.file.relPath", "must be a relative path with / and no ..")
        elif not os.path.isfile(os.path.join(folder, rel)):
            err(f"{p}.file.relPath", f"file not found: {rel}")
        if not is_int(m.get("durationUs")) or m["durationUs"] < 0:
            err(f"{p}.durationUs", "must be an integer >= 0 (microseconds)")
        if m.get("analysis") is None:
            err(f"{p}.analysis", "required")
        seq = m.get("sequence")
        if seq is not None:
            for k in ("dir", "pattern", "first", "count", "fps"):
                if k not in seq:
                    err(f"{p}.sequence.{k}", "required")

    tracks = project.get("tracks") or []
    clips = project.get("clips") or {}
    track_ids = set()
    kinds_order = []
    cc_count = 0
    listed: dict[str, str] = {}
    for ti, t in enumerate(tracks):
        p = f"tracks[{ti}]"
        unknown(p, t, TRACK_FIELDS)
        if not t.get("id"):
            err(f"{p}.id", "required")
        elif t["id"] in track_ids:
            err(f"{p}.id", "duplicate track id")
        track_ids.add(t.get("id"))
        if t.get("kind") not in ("video", "audio", "caption"):
            err(f"{p}.kind", "must be video, audio or caption")
        kinds_order.append(t.get("kind"))
        if t.get("kind") == "caption":
            cc_count += 1
            if t["id"] not in (project.get("captionTracks") or {}):
                err(f"captionTracks.{t['id']}", "a caption track needs its style in captionTracks")
        prev_end = 0
        ids = t.get("clipIds") or []
        for k, cid in enumerate(ids):
            if cid in listed:
                err(f"{p}.clipIds[{k}]", f"clip {cid} is listed on two tracks")
            listed[cid] = t["id"]
            c = clips.get(cid)
            if c is None:
                err(f"{p}.clipIds[{k}]", f"no clip {cid}")
                continue
            if c.get("trackId") != t["id"]:
                err(f"clips.{cid}.trackId", f"must be {t['id']}")
            if is_int(c.get("start")) and is_int(c.get("duration")):
                if c["start"] < prev_end:
                    err(f"{p}.clipIds[{k}]", f"clip {cid} overlaps or is out of order (starts at {c['start']}, the previous one ends at {prev_end})")
                prev_end = max(prev_end, c["start"] + c["duration"])
    if cc_count > 1:
        err("tracks", "at most one caption track")
    if "caption" in kinds_order:
        ci = kinds_order.index("caption")
        if "video" in kinds_order[ci:]:
            err("tracks", "the caption track goes above every video track")
        if "audio" in kinds_order[:ci]:
            err("tracks", "audio tracks come after the caption track")
    elif "audio" in kinds_order and "video" in kinds_order[kinds_order.index("audio"):]:
        err("tracks", "video tracks come before audio tracks")

    for cid, c in clips.items():
        p = f"clips.{cid}"
        k = c.get("kind")
        if k not in KIND_FIELDS:
            err(f"{p}.kind", f"unsupported kind {k}")
            continue
        unknown(p, c, KIND_FIELDS[k])
        if c.get("id") != cid:
            err(f"{p}.id", "must equal its key")
        if cid not in listed:
            err(p, "a clip no track lists")
        for f in ("start", "duration"):
            if not is_int(c.get(f)):
                err(f"{p}.{f}", "must be an integer (frames)")
        if is_int(c.get("start")) and c["start"] < 0:
            err(f"{p}.start", "must be >= 0")
        if is_int(c.get("duration")) and c["duration"] < 1:
            err(f"{p}.duration", "must be >= 1")
        if c.get("color") is not None and c["color"] not in LABEL_COLORS:
            err(f"{p}.color", "unknown label color")
        tr = next((t for t in tracks if t.get("id") == c.get("trackId")), None)
        if tr is None:
            err(f"{p}.trackId", "names no track")
        else:
            want = {"audio": "audio", "caption": "caption"}.get(k, "video")
            if tr.get("kind") != want:
                err(f"{p}.trackId", f"a {k} clip goes on a {want} track")
        if k in ("video", "audio", "image"):
            m = media.get(c.get("mediaId"))
            if m is None:
                err(f"{p}.mediaId", "names no media item")
            else:
                for f in ("in", "out"):
                    if not is_int(c.get(f)):
                        err(f"{p}.{f}", "must be an integer (microseconds)")
                if is_int(c.get("in")) and is_int(c.get("out")) and is_int(c.get("duration")):
                    sp = c.get("speed", 1)
                    want_us = c["duration"] * sp * 1_000_000 / fps_v
                    if abs((c["out"] - c["in"]) - want_us) > 1_000_000 / fps_v + 1:
                        err(f"{p}.out", f"out - in ({c['out'] - c['in']} us) is not duration * speed ({want_us:.0f} us) within one frame")
                    if m["kind"] != "image" or m.get("sequence"):
                        if c["out"] > m["durationUs"] + 1000:
                            err(f"{p}.out", f"passes the media's durationUs ({m['durationUs']})")
                    if c["in"] < 0 or c["out"] <= c["in"]:
                        err(f"{p}.in", "in must be >= 0 and below out")
                if k == "audio" and m["kind"] != "audio" and not m.get("hasAudio"):
                    err(f"{p}.mediaId", "an audio clip needs a media item with sound")
        if k in ("video", "audio", "image", "text", "solid"):
            tf = c.get("transform")
            if not isinstance(tf, dict):
                err(f"{p}.transform", "required")
            else:
                unknown(f"{p}.transform", tf, TRANSFORM_FIELDS)
                for f in ("x", "y", "scale", "rotation"):
                    if not is_num(tf.get(f)):
                        err(f"{p}.transform.{f}", "must be a number")
                if is_num(tf.get("scale")) and tf["scale"] <= 0:
                    err(f"{p}.transform.scale", "must be > 0")
            op = c.get("opacity")
            if not is_num(op) or not 0 <= op <= 1:
                err(f"{p}.opacity", "must be a number 0..1")
        if k == "solid":
            for f in ("fill", "shape", "size", "cornerRadius"):
                if f not in c:
                    err(f"{p}.{f}", "required")
            if c.get("shape") not in ("rect", "roundedRect", "ellipse", "line"):
                err(f"{p}.shape", "unknown shape")
            sz = c.get("size") or {}
            if not (is_num(sz.get("w")) and is_num(sz.get("h")) and sz["w"] > 0 and sz["h"] > 0):
                err(f"{p}.size", "w and h must be numbers > 0")
        if k == "text":
            tx = c.get("text") or {}
            if not isinstance(tx.get("value"), str):
                err(f"{p}.text.value", "must be a string")
            if not isinstance(c.get("style"), dict):
                err(f"{p}.style", "required")
            else:
                for f in ("fontFamily", "fontWeight", "italic", "fontSize", "fill", "stroke", "shadow", "background", "textCase", "letterSpacing", "lineHeight", "align", "verticalAnchor"):
                    if f not in c["style"]:
                        err(f"{p}.style.{f}", "required")
        if k == "caption":
            if not isinstance(c.get("text"), str):
                err(f"{p}.text", "must be a string")
            prev = None
            for wi, w in enumerate(c.get("words") or []):
                if not (is_int(w.get("start")) and is_int(w.get("end"))) or w["end"] <= w["start"]:
                    err(f"{p}.words[{wi}]", "start and end must be integers, end after start")
        for prop, keys in (c.get("keyframes") or {}).items():
            pk = f"{p}.keyframes.{prop}"
            allowed = KEYFRAME_PROPS_BASE if manifest is None else set(manifest.get("keyframes.props", []))
            if prop not in allowed:
                err(pk, "a property the manifest does not list")
            last = None
            for ki, key in enumerate(keys):
                if not is_int(key.get("frame")):
                    err(f"{pk}[{ki}].frame", "must be an integer")
                    continue
                if last is not None and key["frame"] <= last:
                    err(f"{pk}[{ki}].frame", "keys must be sorted, one per frame")
                last = key["frame"]
                if manifest is not None and not manifest.ease(key.get("ease", "")):
                    err(f"{pk}[{ki}].ease", f"ease {key.get('ease')} is not in the manifest")
        fb = c.get("fallbackOf")
        if fb is not None:
            for f in ("kind", "reason", "schemaVersion", "data"):
                if f not in fb:
                    err(f"{p}.fallbackOf.{f}", "required")

    seen_mk = set()
    last_frame = -1
    for mi, mk in enumerate(project.get("markers") or []):
        if mk.get("id") in seen_mk:
            err(f"markers[{mi}].id", "duplicate")
        seen_mk.add(mk.get("id"))
        if not is_int(mk.get("frame")) or mk["frame"] < 0:
            err(f"markers[{mi}].frame", "must be an integer >= 0")
        elif mk["frame"] < last_frame:
            err(f"markers[{mi}].frame", "markers are sorted by frame")
        else:
            last_frame = mk["frame"]
        if mk.get("color") not in LABEL_COLORS:
            err(f"markers[{mi}].color", "unknown label color")
    fonts_path = os.path.join(folder, "fonts", "fonts.json")
    if os.path.isfile(fonts_path):
        import json
        try:
            fj = json.load(open(fonts_path, encoding="utf-8"))
            for face in fj.get("faces", []):
                if not os.path.isfile(os.path.join(folder, "fonts", face.get("file", ""))):
                    err("fonts/fonts.json", f"font file {face.get('file')} is missing")
        except ValueError as exc:
            err("fonts/fonts.json", f"not JSON: {exc}")
    return {"ok": not errs, "errors": errs, "warnings": warns}
