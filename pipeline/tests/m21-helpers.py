#!/usr/bin/env python
"""m21-helpers.py: the checks of test-m21.sh that are easier in Python (BUILD_SPEC.md S15, M21).

  python m21-helpers.py unit                         pure-code checks: manifest, ease fits and keyframe reduction, the animated WebP frame rule, the validator's
                                                     planted faults, gaps, CAPABILITIES.md covers every manifest key, cues.json's new fields
  python m21-helpers.py project <run> <mode>         assertions on <run>/s15-project of a baseline run (mode baseline) or a manifest-plus run (mode plus)
  python m21-helpers.py mixcheck <run>               the project lasts as long as final.mp4 within 1 frame and its mix is within 0.5 LU of it
  python m21-helpers.py compare-plus <run> <golden>  the manifest-plus project's JSON (ids, times, captions, solids) against the golden file (or write it with --write)
Each line it prints starts with PASS or FAIL; exit 1 when any FAIL.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "lib")
sys.path.insert(0, LIB)
sys.stdout.reconfigure(newline="\n")

FAILS = 0


def check(ok: bool, msg: str) -> None:
    global FAILS
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        FAILS += 1


def read_json(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


# ---------------------------------------------------------------------------------------------------- unit


def unit() -> None:
    from s15 import capdoc, geom, manifest as sm, render, validate, gaps
    base, plus = sm.load(None, None), sm.load(None, sm.PLUS)
    check(base.schema_version == 3 and plus.schema_version == 6, "the baseline manifest is schema 3 and manifest-plus.json schema 6")
    check(base.hash != plus.hash and base.hash == sm.load(None, None).hash, "the capability hash differs between manifests and is stable")
    bumped = dict(base.data)
    bumped["lastBatch"] = 99
    bumped["appVersion"] = "9.9.9"
    check(sm.capability_hash(bumped) == base.hash, "lastBatch and appVersion do not change the capability hash")
    added = sm.added_keys(base.data, plus.data)
    for k in ("solid.stroke", "solid.shadow", "captions.wordEmphasis", "captions.highlightModes:progressive", "text.background.stroke"):
        check(k in added, f"added_keys(baseline, plus) lists {k}")
    check(base.solid_missing(True, True, False, False) == ["solid.stroke", "solid.shadow"] and plus.solid_missing(True, True, True, False) == [], "the solid style questions: baseline lacks stroke and shadow, plus has them")
    check(bool(base.captions_missing(False, True, False, False, True)) and not plus.captions_missing(False, True, False, False, True), "native captions need wordEmphasis and cue fades: baseline no, plus yes")
    # eases and keyframe reduction
    import math
    frames = list(range(0, 15))
    vals = [100 * geom.EASES["expoOut"](f / 14.0) for f in frames]
    keys = geom.reduce_scalar(frames, vals, 0.25, ["expoOut", "quadOut"])
    check(len(keys) == 2 and keys[0]["ease"] == "expoOut", f"an expo.out move reduces to 2 keys with the ease expoOut (got {len(keys)} keys, {keys[0]['ease']})")
    check(geom.check_keys(keys, frames, vals, 0.25) <= 0.25 + 1e-9, "the reduced keys reproduce every frame within 0.25")
    keys_lin = geom.reduce_scalar(frames, vals, 0.25, None)
    check(all(k["ease"] == "linear" for k in keys_lin) and geom.check_keys(keys_lin, frames, vals, 0.25) <= 0.25 + 1e-9, "with no named ease allowed the keys are linear and still within tolerance")
    check(geom.reduce_scalar([0, 1, 2], [5.0, 5.0, 5.0], 0.25) == [{"frame": 0, "value": 5.0, "ease": "linear"}], "a constant value is one key")
    q = [10, 10, 110, 10, 110, 60, 10, 60]
    p = geom.pose_from_quad(q, 100, 50)
    check(abs(p["cx"] - 60) < 1e-9 and abs(p["sx"] - 1) < 1e-9 and abs(p["rot"]) < 1e-9 and p["err"] < 1e-9, "pose_from_quad: an untransformed box is scale 1, rotation 0, no error")
    rot = [(60 + (x - 60) * math.cos(0.5) - (y - 35) * math.sin(0.5), 35 + (x - 60) * math.sin(0.5) + (y - 35) * math.cos(0.5)) for x, y in ((10, 10), (110, 10), (110, 60), (10, 60))]
    p = geom.pose_from_quad([c for pt in rot for c in pt], 100, 50)
    check(abs(p["rot"] - math.degrees(0.5)) < 1e-6 and p["err"] < 1e-6, "pose_from_quad: a rotated box gives its rotation")
    trap = [10, 10, 110, 10, 100, 60, 20, 60]
    check(geom.pose_from_quad(trap, 100, 50)["err"] > 1.0, "pose_from_quad: a trapezoid (a 3D tilt) shows as an affine fit error")
    # the animated WebP frame rule: 90 frames, 33/33/34 ms
    from PIL import Image
    n = 90
    ims = []
    for k in range(n):
        im = Image.new("RGBA", (8, 8), (k * 2 % 256, (k * 5) % 256, (k * 11) % 256, 255))
        ims.append(im)
    buf = io.BytesIO()
    durs = render.webp_durations(n)
    ims[0].save(buf, format="WEBP", save_all=True, append_images=ims[1:], duration=durs, lossless=True, loop=0, exact=True)
    check(durs[:6] == [33, 33, 34, 33, 33, 34] and sum(durs) == 3000, "the WebP frame durations are 33, 33, 34 ms repeating (90 frames last 3000 ms)")
    wd = render.webp_frame_durations(buf.getvalue())
    t = 0
    got = []
    for k, d in enumerate(wd):
        got.append((t, d, (k * 2 % 256,)))
        t += d
    check(len(wd) == n and wd == durs, f"the written animated WebP has {n} frames carrying their own durations (33, 33, 34 ms)")
    # every timeline frame shows its own animation frame under the editor's rule (round(k * 1000000 / 30) microseconds)
    bad = []
    for k in range(n):
        j = render.webp_frame_at(k, n)
        t_us = round(k * 1_000_000 / 30)
        starts = [g[0] * 1000 for g in got]
        want = max(i for i, s0 in enumerate(starts) if s0 <= t_us)
        if j != want:
            bad.append((k, j, want))
    check(not bad, f"every timeline frame of a 90-frame overlay shows its own WebP frame under the editor's frame rule ({bad[:3]})")
    # the validator on planted faults
    folder = tempfile.mkdtemp()
    os.makedirs(os.path.join(folder, "media"))
    doc = {"schemaVersion": 3, "id": "t", "name": "t", "settings": {"width": 1080, "height": 1920, "fps": {"num": 30, "den": 1}, "background": {"r": 0, "g": 0, "b": 0, "a": 1}, "sampleRate": 48000},
           "media": {}, "bins": [], "tracks": [{"id": "v1", "kind": "video", "name": "V1", "clipIds": ["a", "b"], "locked": False, "muted": False, "solo": False, "hidden": False, "targeted": True, "height": "M"}],
           "clips": {}, "markers": [], "captionTracks": {}, "textPresetsLocal": [], "meta": {"createdAt": "x", "modifiedAt": "x", "appVersion": "1.1.0"}}
    solid = lambda cid, start: {"id": cid, "trackId": "v1", "kind": "solid", "name": cid, "start": start, "duration": 30, "enabled": True, "fill": {"r": 1, "g": 1, "b": 1, "a": 1}, "shape": "rect",
                                "size": {"w": 10, "h": 10}, "cornerRadius": 0, "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}, "opacity": 1}
    doc["clips"] = {"a": solid("a", 0), "b": solid("b", 30)}
    r = validate.validate(doc, folder, base)
    check(r["ok"], f"the validator accepts a small valid project ({r['errors'][:2]})")

    def planted(name, mutate, want):
        d = json.loads(json.dumps(doc))
        mutate(d)
        res = validate.validate(d, folder, base)
        check((not res["ok"]) and any(want in e["message"] or want in e["path"] for e in res["errors"]), f"the validator refuses {name} ({want})")

    planted("overlapping clips", lambda d: d["clips"]["b"].update(start=10), "overlaps")
    planted("an unknown field", lambda d: d["clips"]["a"].update(bogus=1), "unknown field")
    planted("a fractional frame", lambda d: d["clips"]["a"].update(duration=30.5), "integer")
    planted("a clip on a missing track", lambda d: d["clips"]["a"].update(trackId="v9"), "names no track")
    planted("a missing media file", lambda d: (d["media"].update({"m": {"id": "m", "kind": "image", "name": "x", "file": {"relPath": "media/none.png"}, "durationUs": 0, "analysis": {"thumbs": "none", "peaks": "none"}}})), "file not found")
    planted("a wrong schemaVersion", lambda d: d.update(schemaVersion=4), "manifest's schemaVersion")
    planted("two caption tracks", lambda d: d["tracks"].extend([{"id": "c1", "kind": "caption", "name": "c", "clipIds": [], "locked": False, "muted": False, "solo": False, "hidden": False, "targeted": False, "height": "S"},
                                                                {"id": "c2", "kind": "caption", "name": "c", "clipIds": [], "locked": False, "muted": False, "solo": False, "hidden": False, "targeted": False, "height": "S"}]), "at most one caption track")
    planted("a keyframe property the manifest does not list", lambda d: d["clips"]["a"].update(keyframes={"fill": [{"frame": 0, "value": [1, 1, 1, 1], "ease": "linear"}]}), "does not list")
    # gaps log
    g = gaps.collect([{"name": "Card", "missing": ["solid.stroke", "solid.shadow"]}, {"name": "Chip", "missing": ["solid.shadow"]}, {"name": "Dot", "missing": []}])
    check(g["solid.shadow"]["count"] == 2 and g["solid.stroke"]["elements"] == ["Card"], "gaps.collect counts the layers each missing key kept from being native")
    state = gaps.merge({}, g, "run-1")
    state = gaps.merge(state, g, "run-2")
    md = gaps.render_md(state, "t")
    check(md.index("solid.shadow") < md.index("solid.stroke") and "latest run-2" in md and ": 4 layers" in md, "the gaps file is sorted by running count and names the latest reel")
    # CAPABILITIES.md covers every key of the manifests
    doc_text = open(os.path.join(sm.STAGE_DIR, "CAPABILITIES.md"), encoding="utf-8").read()
    missing = []
    manifests = [("baseline", sm.baseline()), ("plus", sm.load_file(sm.PLUS))]
    real = os.environ.get("EDITOR_REPO", "/c/Users/there/OneDrive/Desktop/editor") + "/capabilities.json"
    if os.path.isfile(real):
        manifests.append(("editor", sm.load_file(real)))
    for _n, m in manifests:
        for k in capdoc.keys_of(m):
            if f"`{k}`" not in doc_text:
                missing.append(k)
    check(not missing, f"CAPABILITIES.md lists every key of the baseline, plus and the editor's own manifest ({missing[:4]})")
    # cues.json fields: S11's strip_for_json restates trims, fade and gain
    sys.path.insert(0, os.path.join(LIB, "sfx"))
    import mixsfx
    c = mixsfx.strip_for_json({"id": "c1", "reel_start_ms": 1000.0, "offset_ms": 40.0, "play_ms": 500.0, "fade_out_ms": 30.0, "gain_db": -7.5, "_tmp": 1})
    check(c["start_ms"] == 1000.0 and c["trim_in_ms"] == 40.0 and c["trim_out_ms"] == 540.0 and c["final_gain_db"] == -7.5 and "_tmp" not in c, "cues.json gains start_ms, trim_in_ms, trim_out_ms, fade_out_ms and final_gain_db")


# ---------------------------------------------------------------------------------------------------- project assertions


def project_checks(run: str, mode: str) -> None:
    from s15 import manifest as sm, validate
    out = os.path.join(run, "s15-project")
    proj = os.path.join(out, "project")
    ed = read_json(os.path.join(out, "editor.json"))
    doc = read_json(os.path.join(proj, "project.json"))
    man = sm.load(None, sm.PLUS if mode == "plus" else None)
    tl = read_json(os.path.join(run, "timeline", "timeline.json"))
    fps = tl["settings"]["fps"]["num"] / tl["settings"]["fps"]["den"]
    check(ed["level"] == "full", f"S15 built the full project (level {ed['level']}, needs_review {ed['needs_review'][:2]})")
    res = validate.validate(doc, proj, man)
    check(res["ok"], f"the project passes validation ({res['errors'][:2]})")
    check(doc["schemaVersion"] == man.schema_version, f"project.json is at the manifest's schemaVersion {man.schema_version}")
    for f in ("FALLBACKS.md", "OPEN.txt", "layers.json", "fonts/fonts.json"):
        check(os.path.isfile(os.path.join(proj, f)), f"project/{f} exists")
    clips = doc["clips"]
    tracks = {t["id"]: t for t in doc["tracks"]}
    audio = [c for c in clips.values() if c["kind"] == "audio"]
    voice = [c for c in audio if c["name"] == "Voice"]
    check(len(voice) == 1 and voice[0]["start"] == 0 and voice[0]["duration"] >= int(tl["settings"]["duration_frames"]) - 2, "the voice is one native audio clip from frame 0 to the end")
    sfx = tl["audio"]["sfx"]
    got = {c["id"]: c for c in audio if c["id"].startswith("c-sfx-")}
    bad = [s["id"] for s in sfx if f"c-sfx-{s['id']}" not in got or abs(got[f"c-sfx-{s['id']}"]["start"] - s["start_ms"] * fps / 1000.0) > 1.0]
    check(len(got) == len(sfx) and not bad, f"every one of the {len(sfx)} sound effects is a native audio clip at its time within 1 frame ({bad[:3]})")
    atracks = sorted({tracks[c["trackId"]]["name"] for c in audio})
    check(atracks[0] in ("SFX 1", "Voice") and "Voice" in atracks, f"the voice and the sounds are on audio tracks ({atracks})")
    bg = [c for c in clips.values() if c["kind"] in ("solid", "image") and c["start"] == 0 and c["duration"] >= int(tl["settings"]["duration_frames"]) - 1]
    check(bool(bg), "the background (the paper) is a clip of the whole reel's length")
    texts = [c for c in clips.values() if c["kind"] == "text"]
    check(len(texts) > 0, f"native text clips exist ({len(texts)}); each has a family from fonts/fonts.json")
    fonts = {f["family"] for f in read_json(os.path.join(proj, "fonts", "fonts.json"))["faces"]}
    check(all(t["style"]["fontFamily"] in fonts for t in texts), "every native text's font is listed in fonts/fonts.json")
    cap_tracks = [t for t in doc["tracks"] if t["kind"] == "caption"]
    cues = [c for c in clips.values() if c["kind"] == "caption"]
    baked = [t for t in doc["tracks"] if t["name"] == "Captions (baked)"]
    if mode == "baseline":
        check(len(cap_tracks) == 1 and cap_tracks[0]["hidden"] is True and len(cues) > 10, f"the hidden native caption track holds the cues ({len(cues)})")
        check(len(baked) == 1 and len(baked[0]["clipIds"]) >= 1, f"the captions are baked: a 'Captions (baked)' track with {len(baked[0]['clipIds']) if baked else 0} clips (animated WebP pieces within the editor's texture budget)")
        check(not ed["captions_native"], "editor.json says the captions are not native")
        check(any("solid.shadow" in (g or "") for g in ed.get("gaps", {})) or "solid.shadow" in json.dumps(ed.get("gaps")), "the gaps name solid.shadow (the cards' hard shadow)")
        check(not any(c["kind"] == "solid" and c.get("shadow") for c in clips.values()), "no native solid carries a shadow (the baseline has none)")
        check(any(c["name"].endswith("(sprite)") for c in clips.values()), "the cards are sprites with the baseline")
    else:
        check(len(cap_tracks) == 1 and cap_tracks[0]["hidden"] is False and len(cues) > 20, f"the captions are native cues on a visible caption track ({len(cues)})")
        check(not baked, "no baked caption track with manifest-plus")
        check(ed["captions_native"], "editor.json says the captions are native")
        cards = [c for c in clips.values() if c["kind"] == "solid" and c.get("shadow") and c.get("stroke")]
        check(len(cards) >= 3, f"the paper cards are native solids with a stroke and a hard shadow ({len(cards)})")
        emph = [c for c in cues if c.get("styleOverride")]
        check(len(emph) >= 1 and all(c["styleOverride"]["text"]["italic"] for c in emph), f"the emphasis words are cues that restyle (serif italic): {len(emph)}")
        check(cap_tracks[0] and doc["captionTracks"][cap_tracks[0]["id"]]["style"].get("anim", {}).get("in", {}).get("kind") == "fade", "the caption style fades each cue in")
    lay = [c for c in ed["checks"] if c["check"] == "layout"]
    check(bool(lay) and lay[0]["ok"], f"the layout check passes ({lay[0] if lay else 'missing'})".replace("\n", " ")[:300])
    for name in ("validate", "duration"):
        c = [x for x in ed["checks"] if x["check"] == name]
        check(bool(c) and c[0]["ok"], f"the {name} check passes")
    fb = open(os.path.join(proj, "FALLBACKS.md"), encoding="utf-8").read()
    check("| scene | frames | layer | level | missing manifest key | why |" in fb, "FALLBACKS.md has the table of baked layers")
    mk = doc["markers"]
    check(len(mk) >= len([m for m in tl["markers"] if m.get("kind") == "scene"]), f"markers: one per scene start and the keyword ({len(mk)})")
    check(doc["meta"].get("generator", {}).get("name") == "instagramReels" or not man.has("interop.generatorMeta"), "meta.generator names instagramReels (when the manifest has generatorMeta)")
    check("em-dash-free" and b"\xe2\x80\x94" not in open(os.path.join(proj, "project.json"), "rb").read(), "project.json has no em dash")


def mixcheck(run: str) -> None:
    ed = read_json(os.path.join(run, "s15-project", "editor.json"))
    d = [c for c in ed["checks"] if c["check"] == "duration"]
    m = [c for c in ed["checks"] if c["check"] == "mix"]
    check(bool(d) and d[0]["ok"], f"the project lasts as long as the video within 1 frame ({d[0] if d else None})")
    check(bool(m) and m[0]["ok"], f"the project's mix is within 0.5 LU of the video's ({m[0] if m else None})")
    s = [c for c in ed["checks"] if c["check"] == "sound_times"]
    check(bool(s) and s[0]["ok"], "the voice and sounds sit at their times within 1 frame")


def normalize_doc(doc: dict) -> dict:
    """The golden form: ids, times, names and styles, without the times of the run, media sizes or sprite pictures."""
    out = {"schemaVersion": doc["schemaVersion"], "settings": doc["settings"], "tracks": [{"name": t["name"], "kind": t["kind"], "hidden": t["hidden"], "clips": len(t["clipIds"])} for t in doc["tracks"]],
           "captionTracks": doc["captionTracks"], "solids": [], "texts": [], "cues": [], "audio": []}
    for c in sorted(doc["clips"].values(), key=lambda c: (c["kind"], c["start"], c["name"])):
        if c["kind"] == "solid":
            out["solids"].append({k: c[k] for k in ("name", "start", "duration", "fill", "shape", "size", "cornerRadius", "stroke", "shadow") if k in c})
        elif c["kind"] == "text":
            out["texts"].append({"name": c["name"], "start": c["start"], "duration": c["duration"], "text": c["text"]["value"], "family": c["style"]["fontFamily"], "size": c["style"]["fontSize"]})
        elif c["kind"] == "caption":
            out["cues"].append({"text": c["text"], "start": c["start"], "duration": c["duration"], "styleOverride": c.get("styleOverride")})
        elif c["kind"] == "audio":
            out["audio"].append({"name": c["name"], "start": c["start"], "duration": c["duration"], "gainDb": c["volume"]["gainDb"], "fadeOut": c["fades"]["out"]})
    return out


def compare_plus(run: str, golden: str, write: bool) -> None:
    doc = read_json(os.path.join(run, "s15-project", "project", "project.json"))
    got = normalize_doc(doc)
    if write:
        with open(golden, "w", encoding="utf-8", newline="\n") as f:
            json.dump(got, f, indent=1, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        print(f"wrote {golden}")
        return
    want = read_json(golden)
    same = json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True)
    check(same, "the manifest-plus project's JSON matches the golden file" + ("" if same else " (first difference: " + first_diff(got, want) + ")"))


def first_diff(a, b, path="") -> str:
    if type(a) != type(b):
        return f"{path}: type"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}/{k}: missing on one side"
            d = first_diff(a[k], b[k], f"{path}/{k}")
            if d:
                return d
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} against {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    return "" if a == b else f"{path}: {a!r} against {b!r}"


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "unit":
        unit()
    elif cmd == "project":
        project_checks(argv[1], argv[2])
    elif cmd == "mixcheck":
        mixcheck(argv[1])
    elif cmd == "compare-plus":
        compare_plus(argv[1], argv[2], "--write" in argv)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
