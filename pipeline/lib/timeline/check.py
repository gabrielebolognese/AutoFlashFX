"""check.py: the timeline against what it describes (BUILD_SPEC.md 14.8, M20).

The timeline is a record, not a decision: nothing in it may contradict the plans, words.json, cues.json or the composition it came
from. check(run_dir) compares them:

  schema         timeline.json validates against pipeline/schemas/timeline.schema.json
  duration       the length in frames is within 1 frame of the rendered video (the source of role `final`; else the one the format renders)
  sources        every source file exists, with its recorded size and sha256 (a source of base run, channel or abs)
  layers         every layer lies inside the timeline, names a source that exists and, when it is a composition layer, an element of the composition
  composition    every host of 10-build/project/index.html has a layer, and every composition layer's selector is a host (generated formats)
  words          every word of 08-voiceover/words.json is in the voice's words at the same time (generated formats with a voiceover)
  captions       every word of every caption chunk starts within 1 frame of a spoken word (the text may differ: a warning)
  cues           every sound of 11-sfx/cues.json is in audio.sfx at its time with its file
  footage        footage audio and layers agree: a footage audio entry names a footage layer; trims lie inside the source
  markers        in range and in order

Command line (through `python pipeline/lib/timeline check --run-dir DIR [--timeline FILE] [--json OUT]`): exit 0 when every check passes.
"""
from __future__ import annotations

import os
import re

from timeline import common as tc
from timeline import compose

TOL_FRAMES = 1


class Report:
    def __init__(self):
        self.checks: list[dict] = []

    def add(self, name: str, ok: bool, detail: str = "", warn: bool = False, skipped: bool = False) -> None:
        self.checks.append({"check": name, "ok": bool(ok), "detail": detail, "warning": warn, "skipped": skipped})

    @property
    def failures(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"] and not c["warning"]]

    def as_dict(self) -> dict:
        return {"pass": not self.failures, "checks": self.checks, "failing": [c["check"] for c in self.failures]}


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(word).lower())


def _schema_errors(timeline: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["the jsonschema package is missing: run bash pipeline/bin/setup-python"]
    schema = tc.read_json(tc.SCHEMA)
    cls = jsonschema.validators.validator_for(schema)
    errs = []
    for e in sorted(cls(schema).iter_errors(timeline), key=lambda e: [str(p) for p in e.absolute_path])[:20]:
        errs.append("/".join(str(p) for p in e.absolute_path) + ": " + e.message)
    return errs


def check(run_dir: str, timeline: dict | None = None, timeline_path: str = "", verify_hash: bool = True) -> dict:
    run_dir = tc.winpath(run_dir).rstrip("/")
    timeline_path = timeline_path or f"{run_dir}/{tc.TIMELINE_DIR}/{tc.TIMELINE_FILE}"
    rep = Report()
    if timeline is None:
        timeline = tc.read_json(timeline_path)
    if not isinstance(timeline, dict):
        rep.add("schema", False, f"{timeline_path} is missing or not JSON")
        return rep.as_dict()
    errs = _schema_errors(timeline)
    rep.add("schema", not errs, "; ".join(errs[:5]) if errs else "timeline.json validates")
    if errs:
        return rep.as_dict()

    fps = tc.fps_of(timeline)
    total = timeline["settings"]["duration_frames"]
    channel = timeline.get("channel") or os.environ.get("REELS_CHANNEL", "")
    channel_root = tc.paths.channel_root(channel) if channel else ""
    src = tc.Sources(run_dir, channel_root)
    by_id = {s["id"]: s for s in timeline["sources"]}

    # ---- sources
    problems = []
    for s in timeline["sources"]:
        full = src.resolve(s["base"], s["path"])
        if not os.path.isfile(tc.winpath(full)):
            problems.append(f"{s['id']}: {s['path']} does not exist")
            continue
        if s.get("size") is not None and os.path.getsize(tc.winpath(full)) != s["size"]:
            problems.append(f"{s['id']}: {s['path']} has {os.path.getsize(tc.winpath(full))} bytes, the timeline says {s['size']}")
        elif verify_hash and s.get("sha256") and tc.sha256_of(full) != s["sha256"]:
            problems.append(f"{s['id']}: {s['path']} changed since the timeline was written (sha256)")
    rep.add("sources", not problems, "; ".join(problems[:6]) if problems else f"{len(timeline['sources'])} sources exist with their size and checksum")

    # ---- duration against the rendered video
    final = next((s for s in timeline["sources"] if s.get("role") == "final"), None)
    if final:
        full = src.resolve(final["base"], final["path"])
        p = tc.probe(full)
        if not p.get("duration"):
            rep.add("duration", False, f"ffprobe cannot read {final['path']}")
        else:
            got = p["duration"] * fps
            ok = abs(got - total) <= TOL_FRAMES + 1e-6
            rep.add("duration", ok, f"the timeline has {total} frames ({total / fps:.3f} s), {final['path']} lasts {p['duration']:.3f} s ({got:.1f} frames)")
    else:
        rep.add("duration", True, "no rendered video among the sources yet (a cut format renders from the timeline)", skipped=True)

    # ---- layers
    problems = []
    for L in timeline["layers"]:
        if L["start"] >= L["end"]:
            problems.append(f"{L['id']}: starts at {L['start']} and ends at {L['end']}")
        if L["end"] > total + TOL_FRAMES:
            problems.append(f"{L['id']}: ends at frame {L['end']}, after the timeline ({total})")
        s = L.get("source")
        if s and s["id"] not in by_id:
            problems.append(f"{L['id']}: source {s['id']} is not in sources")
        if s and s["id"] in by_id and by_id[s["id"]].get("duration_s") and L["kind"] in ("footage",):
            if s["out"] > by_id[s["id"]]["duration_s"] + 0.05:
                problems.append(f"{L['id']}: takes the source to {s['out']} s, the file lasts {by_id[s['id']]['duration_s']} s")
        if L["kind"] == "footage" and L["end"] - L["start"] > 0 and s:
            span = (s["out"] - s["in"]) * fps
            if abs(span - (L["end"] - L["start"])) > TOL_FRAMES + 1e-6:
                problems.append(f"{L['id']}: the source span ({s['out'] - s['in']:.3f} s) and the layer ({(L['end'] - L['start']) / fps:.3f} s) differ")
    ids = [L["id"] for L in timeline["layers"]]
    for i in set(ids):
        if ids.count(i) > 1:
            problems.append(f"layer id {i} appears twice")
    rep.add("layers", not problems, "; ".join(problems[:6]) if problems else f"{len(timeline['layers'])} layers inside the timeline")

    # ---- the composition (generated formats)
    comp = next((s for s in timeline["sources"] if s.get("kind") == "composition"), None)
    if comp:
        try:
            hosts = compose.read_hosts(src.resolve(comp["base"], comp["path"]))
        except compose.BuildError as exc:
            rep.add("composition", False, str(exc))
            hosts = []
        host_ids = {h["id"] for h in hosts}
        comp_layers = [L for L in timeline["layers"] if L.get("selector")]
        miss_layer = sorted(host_ids - {L["selector"].lstrip("#") for L in comp_layers})
        miss_host = sorted(L["selector"] for L in comp_layers if L["selector"].lstrip("#") not in host_ids)
        bad_comp = [L["id"] for L in comp_layers if L["selector"].lstrip("#") in host_ids and L.get("component") not in
                    ({h["component"] for h in hosts if h["id"] == L["selector"].lstrip("#")} | {None})]
        problems = []
        if miss_layer:
            problems.append("composition hosts without a layer: " + ", ".join(miss_layer[:6]))
        if miss_host:
            problems.append("layers whose selector is not in the composition: " + ", ".join(miss_host[:6]))
        if bad_comp:
            problems.append("layers whose component differs from the host's: " + ", ".join(bad_comp[:6]))
        rep.add("composition", not problems, "; ".join(problems) if problems else f"{len(comp_layers)} composition layers, every host found")
        # the plan's component instances are all hosts and layers
        merged = tc.read_json(f"{run_dir}/09c-transitions/merged.json", None)
        if merged:
            plan_ids = [c["id"] for s in merged.get("scenes") or [] for c in s.get("components") or []]
            lost = [i for i in plan_ids if f"#{i}" not in {L["selector"] for L in comp_layers}]
            rep.add("plan_components", not lost, f"plan components without a layer: {', '.join(lost[:6])}" if lost else f"all {len(plan_ids)} plan components have a layer")
    else:
        rep.add("composition", True, "no composition source (a cut format)", skipped=True)

    # ---- words.json
    voice = timeline["audio"].get("voice")
    words_json = tc.read_json(f"{run_dir}/08-voiceover/words.json", None)
    spoken = []
    if voice and voice.get("words") is not None:
        spoken = voice["words"]
    if words_json and voice is not None:
        want = words_json.get("words") or []
        have = {(w["text"], w["start_ms"], w["end_ms"]) for w in spoken}
        lost = [w for w in want if (str(w["word"]), int(round(w["start_ms"])), int(round(w["end_ms"]))) not in have]
        rep.add("words", not lost and len(spoken) == len(want),
                f"{len(lost)} of {len(want)} words of words.json are not in the timeline (first: {lost[0]['word']!r} at {lost[0]['start_ms']} ms)" if lost
                else (f"all {len(want)} words of words.json are in the timeline at their times" if len(spoken) == len(want) else f"the timeline has {len(spoken)} words, words.json {len(want)}"))
    else:
        rep.add("words", True, "no words.json or no voice", skipped=True)

    # ---- captions against the spoken words (and against the footage formats' own words)
    chunks = timeline["captions"]["chunks"]
    tol_ms = TOL_FRAMES * 1000.0 / fps
    if chunks:
        if spoken:
            starts = sorted((w["start_ms"], _norm(w["text"])) for w in spoken)
            lost, differ = [], []
            for ch in chunks:
                if not (0 <= ch["start_ms"] < ch["end_ms"] <= total * 1000 / fps + tol_ms):
                    lost.append(f"{ch['id']} lies outside the timeline")
                for w in ch["words"]:
                    near = [t for s, t in starts if abs(s - w["start_ms"]) <= tol_ms]
                    if not near:
                        lost.append(f"{ch['id']}: {w['text']!r} at {w['start_ms']} ms matches no spoken word")
                    elif _norm(w["text"]) not in near and _norm(w["text"]):
                        differ.append(f"{ch['id']}: {w['text']!r} vs {near[0]!r}")
            rep.add("captions", not lost, "; ".join(lost[:5]) if lost else f"{len(chunks)} caption chunks, every word starts on a spoken word")
            if differ:
                rep.add("caption_text", True, f"{len(differ)} caption words are spelled differently from the spoken word (first: {differ[0]})", warn=True)
        else:
            bad = [ch["id"] for ch in chunks if not (0 <= ch["start_ms"] < ch["end_ms"] <= total * 1000 / fps + tol_ms)
                   or any(not (ch["start_ms"] - tol_ms <= w["start_ms"] <= w["end_ms"] <= ch["end_ms"] + tol_ms) for w in ch["words"])]
            rep.add("captions", not bad, f"chunks outside the timeline or words outside their chunk: {', '.join(bad[:6])}" if bad else f"{len(chunks)} caption chunks inside the timeline")
    else:
        rep.add("captions", True, "no caption chunks", skipped=True)

    # ---- cues.json
    cues = tc.read_json(f"{run_dir}/11-sfx/cues.json", None)
    sfx = timeline["audio"]["sfx"]
    if cues:
        by_cue = {s["id"]: s for s in sfx}
        lost = []
        for c in cues.get("cues") or []:
            s = by_cue.get(str(c.get("id")))
            start = float(c.get("reel_start_ms", c.get("ms", 0)) or 0)
            if not s:
                lost.append(f"{c.get('id')} ({c.get('cue_type')}) is missing")
            elif abs(s["start_ms"] - start) > tol_ms:
                lost.append(f"{c.get('id')} is at {s['start_ms']} ms, cues.json says {start:.0f}")
            elif s["source"] not in by_id or os.path.basename(by_id[s["source"]]["path"]) != os.path.basename(c.get("file") or ""):
                lost.append(f"{c.get('id')} names another file than cues.json ({c.get('file')})")
        extra = len(sfx) - len(cues.get("cues") or [])
        if extra:
            lost.append(f"{extra} sounds in the timeline are not in cues.json")
        rep.add("cues", not lost, "; ".join(lost[:5]) if lost else f"all {len(sfx)} sounds of cues.json are in the timeline at their times")
    else:
        bad = [s["id"] for s in sfx if s["source"] not in by_id or s["start_ms"] > total * 1000 / fps + tol_ms]
        rep.add("cues", not bad, f"sounds with an unknown source or after the end: {', '.join(bad[:6])}" if bad else f"{len(sfx)} sounds with known sources inside the timeline", skipped=not sfx)

    # ---- footage audio
    footage_layers = {L["id"]: L for L in timeline["layers"] if L["kind"] == "footage"}
    problems = []
    for a in timeline["audio"]["footage"]:
        L = footage_layers.get(a["layer"])
        if not L:
            problems.append(f"footage audio of {a['layer']}: no such footage layer")
            continue
        if a["source"] not in by_id:
            problems.append(f"footage audio of {a['layer']}: source {a['source']} is not in sources")
        if a["out_ms"] <= a["in_ms"]:
            problems.append(f"footage audio of {a['layer']}: out before in")
        if abs((a["out_ms"] - a["in_ms"]) - (L["end"] - L["start"]) * 1000.0 / fps) > tol_ms + 1:
            problems.append(f"footage audio of {a['layer']} lasts {a['out_ms'] - a['in_ms']} ms, the layer {(L['end'] - L['start']) * 1000.0 / fps:.0f} ms")
    rep.add("footage", not problems, "; ".join(problems[:5]) if problems else f"{len(footage_layers)} footage layers, {len(timeline['audio']['footage'])} footage audio entries agree",
            skipped=not footage_layers)

    # ---- markers
    marks = timeline["markers"]
    bad = [m["id"] for m in marks if m["frame"] > total]
    ordered = all(marks[i]["frame"] <= marks[i + 1]["frame"] for i in range(len(marks) - 1))
    rep.add("markers", not bad and ordered, f"markers after the end: {bad}" if bad else ("markers are in order" if ordered else "markers are not in time order"))
    return rep.as_dict()


def main_check(args) -> int:
    rep = check(args.run_dir, timeline_path=args.timeline or "", verify_hash=not args.no_hash)
    for c in rep["checks"]:
        mark = "ok  " if c["ok"] else ("warn" if c["warning"] else "FAIL")
        print(f"{mark} {c['check']}: {c['detail']}")
    if args.json:
        tc.write_json(args.json, rep)
    print("timeline check: " + ("pass" if rep["pass"] else "FAIL (" + ", ".join(rep["failing"]) + ")"))
    return 0 if rep["pass"] else 1
