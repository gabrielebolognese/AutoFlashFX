"""pipeline/lib/visual/plan_validate.py: the validator of the visual plan (BUILD_SPEC.md S9, "A validator script checks
the merged plan against tokens.json"). Every rule has a name, reads its thresholds from tokens.json, catalog.json,
brand.json and config.json (never a hardcoded style number) and reports "rule=<name>: <message>" lines. The three
passes validate the parts they own (9a the scenes and the branding, 9b the captions, cards and labels, 9c the
transitions and the whole merged plan); S10 validates the merged plan once more before building.

  validate(plan, ctx, parts) -> {"ok", "errors": [{"rule", "message"}], "warnings": [...], "skipped": [rule names]}
  python pipeline/lib/visual validate <plan.json> [--run-dir DIR | --words W --script S --assets-json A --numbers N]
                                        [--parts scenes,captions,transitions] [--json]

Rules (the spec's list, in order): first_change, breath, max_gap, distinct, repeat, beat_map, captions, zones,
cards, assets, branding; plus the structural ones the spec implies: schema, components, times, three_d, set_pieces,
honesty, transitions, hook2.
"""
from __future__ import annotations

import json
import os
import re

from visual import common

SCHEMA = os.path.join(common.REPO, "pipeline", "stages", "09-plan", "schema.json")
PASS_SCHEMAS = {"animations": "09a-animations", "text": "09b-text", "transitions": "09c-transitions"}  # a pass file validates against its own schema
RULES = ["schema", "components", "times", "first_change", "breath", "max_gap", "distinct", "repeat", "beat_map", "three_d",
         "set_pieces", "zones", "captions", "cards", "assets", "honesty", "branding", "transitions", "hook2"]
SCENE_RULES = {"schema", "components", "times", "first_change", "breath", "max_gap", "distinct", "repeat", "beat_map", "three_d",
               "set_pieces", "zones", "assets", "branding", "hook2"}
CAPTION_RULES = {"captions", "cards", "honesty", "zones"}
TRANSITION_RULES = {"transitions"}
TIMING_PROPS = ("strike_at", "ticks_at", "fill_at", "type_at", "at")


class Context:
    """What the rules read besides the plan."""

    def __init__(self, toks: dict | None = None, cat: dict | None = None, brand: dict | None = None, config: dict | None = None,
                 words: dict | None = None, script: dict | None = None, assets: dict | None = None, numbers=None):
        self.toks = toks or common.tokens()
        self.cat = cat or common.catalog()
        self.by_id = common.catalog_by_id(self.cat)
        self.brand = brand or common.brand_json()
        self.brand_index = common.brand_index(self.brand)
        self.config = config or common.load_config()
        self.timeline = common.Timeline(words) if words else None
        self.script = script
        self.assets = assets  # {file name: entry} or None when unknown
        self.numbers = numbers

    @classmethod
    def from_run(cls, run_dir: str, config: dict | None = None, **kw) -> "Context":
        inp = common.Inputs(run_dir, config)
        return cls(config=inp.config, words=inp.words, script=inp.script, assets=inp.asset_files() if (inp.assets_json or os.path.isdir(inp.assets_dir)) else None,
                   numbers=inp.numbers, **kw)

    def v(self, key: str, default=None):
        return common.cfg(self.config, "visual." + key, default)


class Report:
    def __init__(self):
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.skipped: list[str] = []

    def err(self, rule: str, msg: str) -> None:
        self.errors.append({"rule": rule, "message": common.undash(msg)})

    def warn(self, rule: str, msg: str) -> None:
        self.warnings.append({"rule": rule, "message": common.undash(msg)})

    def skip(self, rule: str) -> None:
        if rule not in self.skipped:
            self.skipped.append(rule)

    def result(self) -> dict:
        return {"ok": not self.errors, "errors": self.errors, "warnings": self.warnings, "skipped": self.skipped}


# ------------------------------------------------------------------------------------------------ helpers

def ms_of_frames(n: float) -> float:
    return n * 1000.0 / common.FPS


def scene_hero(scene: dict) -> dict | None:
    comps = scene.get("components", [])
    for c in comps:
        if c.get("role") == "hero":
            return c
    for c in comps:
        if c.get("role") in ("set-piece", "cta"):
            return c
    return comps[0] if comps else None


def change_times(plan: dict, ctx: Context) -> list[int]:
    """The visual changes in the hero zone a viewer sees: every component's start and landing, its timed props, the
    headline's words and the typing's start and end. Captions do not count (they sit in their own band)."""
    out = set()
    for s in plan.get("scenes", []):
        out.add(int(s["start_ms"]))
        for c in s.get("components", []):
            cid = c["component"]
            if cid in ("paper-canvas", "caption-line"):
                continue
            p = c.get("props", {})
            start = int(c["start_ms"])
            out.add(start)
            out.add(start + int(ms_of_frames(common.enter_frames(cid, p))))
            for k in TIMING_PROPS:
                if k in p:
                    try:
                        out.add(start + int(float(p[k]) * 1000))
                    except (TypeError, ValueError):
                        pass
            if cid == "headline":
                for w in common._lines(p.get("words_json")):
                    if isinstance(w, dict) and "t" in w:
                        try:
                            out.add(start + int(float(w["t"]) * 1000))
                        except (TypeError, ValueError):
                            pass
            if cid == "terminal-card":
                lines = common._lines(p.get("lines_json"))
                cpf = max(0.5, common._num(p, "chars_per_frame", 2))
                t = start + int(ms_of_frames(8 + common._num(p, "start_delay_frames", 8)))
                out.add(t)
                for ln in lines:
                    txt = ln.get("text", "") if isinstance(ln, dict) else str(ln)
                    t += int(ms_of_frames(len(txt) / cpf + common._num(p, "line_gap_frames", 6)))
                    out.add(min(t, int(c["end_ms"])))
            if cid == "chat-card":
                t = start + int(float(p.get("type_at", 0.4)) * 1000)
                out.add(t)
                out.add(min(int(c["end_ms"]), t + int(ms_of_frames(len(str(p.get("prompt", ""))) * common._num(p, "frames_per_char", 1.15)))))
            if cid == "check-badge" and p.get("mode") == "list":
                items = common._lines(p.get("items_json"))
                t = start + int(float(p.get("ticks_at", 0.4)) * 1000)
                for i in range(len(items)):
                    out.add(t + int(ms_of_frames(i * common._num(p, "tick_gap_frames", 4))))
            if cid == "end-card":
                stagger = common._num(p, "stagger_frames", 6)
                for i in range(5):
                    out.add(start + int(ms_of_frames(i * stagger)))
                kw = str(p.get("keyword", ""))
                t0 = start + int(ms_of_frames(2 * stagger + common._num(p, "fade_frames", 6)))
                out.add(t0 + int(ms_of_frames(len(kw) * common._num(p, "type_frames", 2))))
            if cid == "stat-number":
                t0 = start + int(ms_of_frames(8 + common._num(p, "count_delay_frames", 0)))
                out.add(t0)
                out.add(t0 + int(ms_of_frames(common._num(p, "count_frames", 27.5))))
    dur = int(plan.get("duration_ms", 0))
    return sorted(t for t in out if 0 <= t <= dur)


def is_text_component(cid: str, props: dict) -> bool:
    if cid in ("hero-3d", "icon-3d", "mascot", "logo-tile", "paper-canvas", "caption-line", "camera-move", "exit-move", "thumb-grid"):
        return bool(props.get("label")) if cid in ("hero-3d", "icon-3d") else False
    if cid == "check-badge":
        return props.get("mode") == "list"
    if cid == "pop":
        return props.get("kind") == "pill"
    return True


def logo_spots(c: dict) -> list[tuple[str, str]]:
    """(prop, path) for every brand/ or research/ image a component instance uses."""
    out = []
    for k, v in c.get("props", {}).items():
        if isinstance(v, str) and (v.startswith(common.BRAND_PREFIX) or v.startswith(common.RESEARCH_PREFIX)):
            out.append((k, v))
        elif k in common.CODE_PROPS:
            for item in common._lines(v):
                if isinstance(item, dict):
                    for kk in ("image", "logo"):
                        vv = item.get(kk)
                        if isinstance(vv, str) and (vv.startswith(common.BRAND_PREFIX) or vv.startswith(common.RESEARCH_PREFIX)):
                            out.append((k, vv))
    return out


def known_numbers(ctx: Context) -> set[str]:
    """Every number the reel may show: the digits of script.json's display and card texts and of numbers.json."""
    out = set()

    def add_text(t):
        for m in re.findall(r"\d[\d,.]*", str(t)):
            m2 = m.replace(",", "").rstrip(".")
            if m2:
                out.add(m2)
                try:
                    out.add(str(int(float(m2))))
                except ValueError:
                    pass

    if ctx.script:
        for b in ctx.script.get("beats", []):
            add_text(b.get("display", "")); add_text(b.get("card", "")); add_text(b.get("spoken", ""))
        add_text(json.dumps(ctx.script.get("hook2", {}), ensure_ascii=False))
    if ctx.numbers:
        add_text(json.dumps(ctx.numbers, ensure_ascii=False))
    return out


# ------------------------------------------------------------------------------------------------ the rules

def rule_schema(plan: dict, ctx: Context, rep: Report) -> None:
    try:
        import jsonschema
    except ImportError:
        rep.skip("schema")
        return
    path = SCHEMA
    if plan.get("pass") in PASS_SCHEMAS:
        path = os.path.join(common.REPO, "pipeline", "stages", PASS_SCHEMAS[plan["pass"]], "schema.json")
    schema = common.load_json(path)
    v = jsonschema.validators.validator_for(schema)(schema)
    for e in sorted(v.iter_errors(plan), key=lambda e: [str(p) for p in e.absolute_path])[:12]:
        rep.err("schema", ("/".join(str(p) for p in e.absolute_path) or "$") + ": " + e.message[:160])


def rule_components(plan: dict, ctx: Context, rep: Report) -> None:
    seen: set[str] = set()
    for s in plan.get("scenes", []):
        if not s.get("components"):
            rep.err("components", f"scene {s.get('id')} has no component")
        for c in s.get("components", []):
            iid = c.get("id", "?")
            if iid in seen:
                rep.err("components", f"component id {iid} is used twice")
            seen.add(iid)
            comp = ctx.by_id.get(c.get("component"))
            if not comp:
                rep.err("components", f"{iid}: unknown component {c.get('component')} (motion-lib/catalog.json)")
                continue
            if comp.get("status") != "approved":
                rep.err("components", f"{iid}: {c['component']} is a candidate, not an approved component")
            declared = {p["id"] for p in comp.get("props", [])}
            for k, v in c.get("props", {}).items():
                if k not in declared and not (c["component"] in ("hero-3d", "icon-3d") and k == "clip_start"):
                    rep.err("components", f"{iid}: prop {k} is not a declared variable of {c['component']} (declared: {', '.join(sorted(declared))})")
                    continue
                decl = next((p for p in comp.get("props", []) if p["id"] == k), None)
                if decl and decl.get("options") and v not in decl["options"]:
                    rep.err("components", f"{iid}: prop {k} must be one of {decl['options']}, not {v!r}")
                if decl and decl.get("type") == "number":
                    try:
                        float(v)
                    except (TypeError, ValueError):
                        rep.err("components", f"{iid}: prop {k} must be a number, not {v!r}")
                if k in common.IMAGE_PROPS and isinstance(v, str) and v and not (v.startswith(common.BRAND_PREFIX) or v.startswith(common.RESEARCH_PREFIX) or v == common.BRAND_SLOT_TOKEN):
                    rep.err("components", f"{iid}: image prop {k} must be brand/<path from brand.json> or research/<file>, not {v!r}")
            if "exit" in c.get("props", {}) and plan.get("source", "").startswith("09a"):
                rep.warn("components", f"{iid}: the exit props are the transitions pass's job (9c), ignored")


def rule_times(plan: dict, ctx: Context, rep: Report) -> None:
    dur = int(plan.get("duration_ms", 0))
    scenes = plan.get("scenes", [])
    tol = int(ctx.v("snap_tolerance_ms", 34))
    if ctx.timeline and abs(ctx.timeline.duration_ms - dur) > tol:
        rep.err("times", f"duration_ms {dur} is not the voice's length {ctx.timeline.duration_ms} (words.json)")
    prev_end = 0
    for i, s in enumerate(scenes):
        st, en = int(s["start_ms"]), int(s["end_ms"])
        if st >= en:
            rep.err("times", f"scene {s['id']}: start {st} is not before end {en}")
        if i == 0 and st != 0:
            rep.err("times", f"the first scene starts at {st} ms, not at 0")
        if i > 0 and st != prev_end:
            rep.err("times", f"scene {s['id']} starts at {st} ms but the previous scene ends at {prev_end} (scenes must be contiguous)")
        prev_end = en
        for c in s.get("components", []):
            cs, ce = int(c["start_ms"]), int(c["end_ms"])
            if not (st <= cs < ce <= en + tol):
                rep.err("times", f"{c['id']}: {cs}..{ce} ms is outside its scene {s['id']} ({st}..{en})")
            if ce > dur + tol:
                rep.err("times", f"{c['id']}: ends at {ce} ms, after the reel ({dur})")
    if scenes and abs(prev_end - dur) > tol:
        rep.err("times", f"the last scene ends at {prev_end} ms, not at the reel's end {dur}")
    if ctx.script:
        beats = [b["id"] for b in ctx.script.get("beats", [])]
        got = [s.get("beat") for s in scenes]
        if got != beats:
            rep.err("times", f"the scenes must follow the script's beats one by one ({', '.join(beats)}); got {', '.join(str(g) for g in got)}")
        types = {b["id"]: b.get("type") for b in ctx.script.get("beats", [])}
        for s in scenes:
            if s.get("beat") in types and s.get("beat_type") != types[s["beat"]]:
                rep.err("times", f"scene {s['id']}: beat_type {s.get('beat_type')} but the script's beat {s['beat']} is a {types[s['beat']]}")
    if ctx.timeline:
        tl = ctx.timeline
        bounds = tl.boundaries()
        lead = int(ctx.v("breath_set_piece_lead_ms", 60))
        for s in scenes:
            if s.get("beat") in tl.beats:
                want_st, want_en = tl.scene_span(s["beat"])
                if abs(int(s["start_ms"]) - want_st) > tol or abs(int(s["end_ms"]) - want_en) > tol:
                    rep.err("times", f"scene {s['id']}: {s['start_ms']}..{s['end_ms']} ms is not the beat {s['beat']} window {want_st}..{want_en} of words.json")
            for c in s.get("components", []):
                cs = int(c["start_ms"])
                near = any(abs(cs - b) <= tol for b in bounds) or cs == int(s["start_ms"])
                in_breath_lead = bool(tl.breath) and (int(tl.breath["start_ms"]) - lead - tol <= cs <= int(tl.breath["end_ms"]))
                if not (near or in_breath_lead):
                    rep.err("times", f"{c['id']}: start {cs} ms is not snapped to a word boundary of words.json")


def rule_first_change(plan: dict, ctx: Context, rep: Report) -> None:
    limit = ms_of_frames(float((ctx.toks.get("pacing") or {}).get("first_change_max_frames", 4)))
    starts = [int(c["start_ms"]) for s in plan.get("scenes", []) for c in s.get("components", []) if c["component"] != "paper-canvas"]
    if not starts:
        rep.err("first_change", "no component at all")
        return
    if min(starts) > limit + 1:
        rep.err("first_change", f"the first visual change is at {min(starts)} ms; the style wants one within {limit:.0f} ms (pacing.first_change_max_frames)")


def rule_breath(plan: dict, ctx: Context, rep: Report) -> None:
    if not ctx.timeline or not ctx.timeline.breath:
        rep.skip("breath")
        return
    br = ctx.timeline.breath
    b0, b1 = int(br["start_ms"]), int(br["end_ms"])
    hit = []
    for s in plan.get("scenes", []):
        if int(s["start_ms"]) in range(b0, b1):
            hit.append("scene " + s["id"])
        for c in s.get("components", []):
            if c["component"] == "paper-canvas":
                continue
            st = int(c["start_ms"])
            land = st + int(ms_of_frames(common.enter_frames(c["component"], c.get("props", {}))))
            if b0 <= st <= b1 - 100 or b0 <= land <= b1:
                hit.append(c["id"])
    if not hit:
        rep.err("breath", f"no visual change lands inside the hook breath ({b0} to {b1} ms): the hook's set piece or the first scene change must land there (BUILD_SPEC.md S9 9a)")
    hook = next((s for s in plan.get("scenes", []) if s.get("beat_type") == "hook"), None)
    if hook and not hook.get("hook_set_piece") and not any(h.startswith("scene") for h in hit):
        rep.warn("breath", "the hook scene is not marked hook_set_piece although something lands in the breath")


def rule_max_gap(plan: dict, ctx: Context, rep: Report) -> None:
    limit = float((ctx.toks.get("pacing") or {}).get("gap_max_s", 6.5)) * 1000
    times = change_times(plan, ctx)
    for a, b in zip(times, times[1:]):
        if b - a > limit:
            rep.err("max_gap", f"{(b - a) / 1000:.1f} s pass with no visual change between {a} and {b} ms; the style's longest gap is {limit / 1000:.1f} s (pacing.gap_max_s)")
            return


def rule_distinct(plan: dict, ctx: Context, rep: Report) -> None:
    scenes = plan.get("scenes", [])
    used = {c["component"] for s in scenes for c in s.get("components", []) if c["component"] not in ("paper-canvas", "caption-line")}
    want = min(int(ctx.v("min_distinct_components", 5)), max(1, len(scenes)))
    if len(used) < want:
        rep.err("distinct", f"only {len(used)} distinct components ({', '.join(sorted(used))}); at least {want} are wanted (config visual.min_distinct_components)")


def rule_repeat(plan: dict, ctx: Context, rep: Report) -> None:
    limit = int(ctx.v("max_same_in_a_row", 2))
    heroes = []
    for s in plan.get("scenes", []):
        h = scene_hero(s)
        heroes.append((s["id"], h["component"] if h else None))
    run = 1
    for (sid_prev, prev), (sid, cur) in zip(heroes, heroes[1:]):
        run = run + 1 if cur == prev and cur else 1
        if run > limit:
            rep.err("repeat", f"{cur} is the hero component of {run} scenes in a row (up to {sid}); the limit is {limit} (config visual.max_same_in_a_row)")
            return


def rule_beat_map(plan: dict, ctx: Context, rep: Report) -> None:
    bm = ctx.toks.get("beat_map") or {}
    anyc = set(bm.get("any", []))
    for s in plan.get("scenes", []):
        allowed = set(bm.get(s.get("beat_type"), [])) | anyc
        if not bm.get(s.get("beat_type")):
            rep.err("beat_map", f"scene {s['id']}: beat type {s.get('beat_type')} is not in tokens.json beat_map")
            continue
        for c in s.get("components", []):
            if c["component"] not in allowed:
                rep.err("beat_map", f"{c['id']}: {c['component']} is not allowed for a {s['beat_type']} beat (tokens.json beat_map: {', '.join(sorted(allowed - anyc))})")


def rule_three_d(plan: dict, ctx: Context, rep: Report) -> None:
    lim = (ctx.toks.get("limits") or {}).get("three_d") or {}
    scenes_ok = set()
    for name in lim.get("scenes", ["hook", "end"]):
        scenes_ok.add({"end": "ask", "cta": "ask"}.get(name, name))
    max_objects = int(lim.get("max_objects", 2))
    for s in plan.get("scenes", []):
        objs = [c for c in s.get("components", []) if ctx.by_id.get(c["component"], {}).get("kind") == "3d"]
        if objs and s.get("beat_type") not in scenes_ok:
            rep.err("three_d", f"scene {s['id']} ({s.get('beat_type')}) uses 3D ({objs[0]['id']}); the style allows 3D only in {', '.join(sorted(scenes_ok))} scenes (tweaks.md 3D)")
        if len(objs) > max_objects:
            rep.err("three_d", f"scene {s['id']} has {len(objs)} 3D objects; at most {max_objects} on screen (tokens.json limits.three_d)")


def rule_set_pieces(plan: dict, ctx: Context, rep: Report) -> None:
    lo, hi = ((ctx.toks.get("limits") or {}).get("set_pieces_per_reel") or [1, 2])[:2]
    n = sum(1 for s in plan.get("scenes", []) if s.get("set_piece"))
    if n < int(lo) or n > int(hi):
        rep.err("set_pieces", f"{n} set pieces; the style wants {lo} to {hi} per reel (tokens.json limits.set_pieces_per_reel)")
    hook = next((s for s in plan.get("scenes", []) if s.get("beat_type") == "hook"), None)
    if hook and not hook.get("hook_set_piece"):
        rep.err("set_pieces", "the hook scene has no set piece landing in the breath (hook_set_piece)")


def rule_zones(plan: dict, ctx: Context, rep: Report) -> None:
    z = ctx.toks.get("zones") or {}
    tol = float(ctx.v("zone_tolerance_px", 24))
    margin = float(z.get("margin_x", 60))
    hero = z.get("hero") or {}
    rail = z.get("right_rail") or {}
    rail_x = 1080 - float(rail.get("width", 230))
    rail_y = float(rail.get("from_y", 960))
    safe_bottom = float(z.get("safe_bottom", 1440))
    cta = plan.get("branding", {}).get("cta_scene")
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            cid = c["component"]
            p = c.get("props", {})
            fp = common.footprint(cid, p, ctx.toks)
            if not fp:
                continue
            x0, y0, x1, y1 = fp["x"], fp["y"], fp["x"] + fp["w"], fp["y"] + fp["h"]
            if x0 < margin - tol or x1 > 1080 - margin + tol:
                rep.err("zones", f"{c['id']}: spans x {x0:.0f} to {x1:.0f}; the side margins are {margin:.0f} px (tokens.json zones.margin_x)")
            if y0 < float(hero.get("top_min", 180)) - tol and cid not in ("headline",):
                rep.err("zones", f"{c['id']}: top at y {y0:.0f}, above the hero zone's top {hero.get('top_min')} (tokens.json zones.hero)")
            if s["id"] != cta and y1 > safe_bottom + tol:
                rep.err("zones", f"{c['id']}: bottom at y {y1:.0f}, below the safe zone's bottom {safe_bottom:.0f} (tokens.json zones.safe_bottom)")
            elif s["id"] == cta and y1 > safe_bottom + tol and cid not in ("dm-card", "end-card"):
                rep.err("zones", f"{c['id']}: bottom at y {y1:.0f}, below the safe zone's bottom {safe_bottom:.0f}")
            if c.get("role") == "hero" and s["id"] != cta and y1 > float(hero.get("bottom_max", 1176)) + tol:
                rep.warn("zones", f"{c['id']}: the hero's bottom at y {y1:.0f} is under the style's hero zone ({hero.get('bottom_max')}); fine as long as it stays off the caption band")
            for tb in fp.get("text_boxes", []):
                tx1 = tb["x"] + tb["w"]
                if tb["y"] + tb["h"] > rail_y and tx1 > rail_x + tol:
                    rep.err("zones", f"{c['id']}: text ({tb['prop']}) reaches x {tx1:.0f} in the lower half; no text in the right {rail.get('width', 230)} px below y {rail_y:.0f} (tweaks.md Right side)")


def rule_captions(plan: dict, ctx: Context, rep: Report) -> None:
    lim = (ctx.toks.get("limits") or {}).get("caption") or {}
    lo, hi = (lim.get("words_per_chunk") or [1, 4])[:2]
    em_hi = (lim.get("emphasis_per_chunk") or [1, 3])[1]
    max_w = float((ctx.toks.get("zones") or {}).get("caption", {}).get("max_width", 620))
    chunks = plan.get("captions", [])
    hook = next((s for s in plan.get("scenes", []) if s.get("beat_type") == "hook"), None)
    ask = next((s for s in plan.get("scenes", []) if s.get("beat_type") == "ask"), None)
    starts = {}
    if ctx.timeline:
        for w in ctx.timeline.words:
            starts.setdefault(int(w["start_ms"]), []).append(common.norm(w["word"]))
    prev_start = -1
    covered = set()
    for i, ch in enumerate(chunks):
        words = ch.get("words", [])
        if not (int(lo) <= len(words) <= int(hi)):
            rep.err("captions", f"caption chunk {i} has {len(words)} words; chunks hold {lo} to {hi} (tokens.json limits.caption)")
        em = sum(1 for w in words if w.get("emphasis"))
        if em > int(em_hi):
            rep.err("captions", f"caption chunk {i} has {em} emphasis words; at most {em_hi}")
        width = common.caption_chunk_width(words, ctx.toks)
        if width > max_w + 1:
            rep.err("captions", f"caption chunk {i} (\"{' '.join(w['word'] for w in words)}\") is about {width:.0f} px wide at the caption size; the line is at most {max_w:.0f} px (tokens.json zones.caption.max_width): split it")
        if int(ch["start_ms"]) >= int(ch["end_ms"]):
            rep.err("captions", f"caption chunk {i}: start {ch['start_ms']} is not before end {ch['end_ms']}")
        if int(ch["start_ms"]) < prev_start:
            rep.err("captions", f"caption chunk {i} starts before the previous chunk")
        prev_start = int(ch["start_ms"])
        if hook and int(ch["start_ms"]) < int(hook["end_ms"]) - 1:
            rep.err("captions", f"caption chunk {i} starts at {ch['start_ms']} ms, during the hook headline; the style shows no captions there (style.md Captions)")
        if ask and int(ch["start_ms"]) >= int(ask["start_ms"]):
            rep.err("captions", f"caption chunk {i} starts at {ch['start_ms']} ms, on the end card; the style shows no captions there (style.md Captions)")
        if ctx.timeline:
            for w in words:
                st = int(w["start_ms"])
                if st not in starts or common.norm(w["word"]) not in starts[st]:
                    rep.err("captions", f"caption word \"{w['word']}\" at {st} ms is not a spoken word of words.json at that time")
                covered.add(st)
    if ctx.timeline and chunks:
        body = [w for w in ctx.timeline.words if not (hook and int(w["start_ms"]) < int(hook["end_ms"])) and not (ask and int(w["start_ms"]) >= int(ask["start_ms"]))]
        missing = [w["word"] for w in body if int(w["start_ms"]) not in covered]
        if missing:
            rep.warn("captions", f"{len(missing)} spoken body words have no caption ({', '.join(missing[:6])})")
    if not chunks and plan.get("source", "").startswith(("09b", "09a+09b")):
        rep.err("captions", "no caption chunks at all")


def rule_cards(plan: dict, ctx: Context, rep: Report) -> None:
    title_max = int(ctx.v("title_max_words", common.cfg(ctx.config, "script.card_max_words", 6)))
    body_max = int(ctx.v("body_max_words", 14))
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            for k, v in c.get("props", {}).items():
                if not isinstance(v, str) or not v.strip():
                    continue
                n = len(common.words_of(v))
                if k in common.TITLE_PROPS and n > title_max:
                    rep.err("cards", f"{c['id']}: {k} \"{v[:60]}\" has {n} words; an on-screen card text holds {title_max} or fewer (BUILD_SPEC.md S9 9b)")
                elif k in common.BODY_PROPS and n > body_max:
                    rep.err("cards", f"{c['id']}: {k} \"{v[:60]}\" has {n} words; body text holds {body_max} or fewer (config visual.body_max_words)")
            if c["component"] == "headline":
                lines = common._lines(c.get("props", {}).get("lines_json"))
                total = sum(len(common.words_of(str(ln).replace("*", ""))) for ln in lines)
                if len(lines) > 3:
                    rep.err("cards", f"{c['id']}: the headline has {len(lines)} lines; 2 to 3 (style.md Hook)")
                if total > title_max + 4:
                    rep.err("cards", f"{c['id']}: the headline has {total} words; keep the hook's spoken line (8 words or fewer)")
    for card in plan.get("cards", []):
        n = len(common.words_of(card.get("text", "")))
        if card.get("prop") == "lines_json":
            continue  # the headline carries the hook's spoken line (8 words or fewer), checked above
        if card.get("zone") in ("hero", "label") and n > title_max and card.get("prop", "title") not in common.BODY_PROPS:
            rep.err("cards", f"card \"{card.get('text', '')[:60]}\" on {card.get('component')} has {n} words; {title_max} or fewer")


def rule_assets(plan: dict, ctx: Context, rep: Report) -> None:
    nums = known_numbers(ctx) if (ctx.script or ctx.numbers) else None
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            cid = c["component"]
            p = c.get("props", {})
            for k, v in logo_spots(c):
                if v.startswith(common.RESEARCH_PREFIX):
                    if ctx.assets is not None and v[len(common.RESEARCH_PREFIX):] not in ctx.assets:
                        rep.err("assets", f"{c['id']}: {k} names {v}, which is not among the run's research assets ({', '.join(sorted(ctx.assets)[:6]) or 'none'})")
                    if p.get("honesty") not in ("sourced",) and cid in ("card", "window-card", "fly-in", "camera-move", "thumb-grid"):
                        rep.warn("assets", f"{c['id']}: shows a real screenshot ({v}) without honesty sourced")
            if cid == "stat-number":
                val = str(int(common._num(p, "value", 0)))
                if nums is not None and val not in nums:
                    rep.err("assets", f"{c['id']}: the number {val} is not in the script or numbers.json: no invented UI values (BUILD_SPEC.md S9)")
            if cid == "chart-card" and p.get("honesty", "mock") == "none":
                rep.err("assets", f"{c['id']}: a chart needs an honesty label (mock, or sourced when every value comes from numbers.json)")
            if cid == "chart-card" and p.get("honesty") == "sourced" and nums is not None:
                for d in common._lines(p.get("values_json")):
                    if isinstance(d, dict) and "value" in d and str(int(float(d["value"]))) not in nums:
                        rep.err("assets", f"{c['id']}: chart value {d['value']} is not in the script or numbers.json but the chart says sourced")
            if cid in ("thumb-grid", "chat-card") and p.get("honesty", "mock") == "none":
                rep.err("assets", f"{c['id']}: {cid} shows mock UI; it needs honesty mock (or sourced with real assets)")
            if cid == "window-card" and common._lines(p.get("lines_json")) and not p.get("image") and p.get("honesty", "none") == "none":
                rep.err("assets", f"{c['id']}: a window card with typed lines is a mock UI; set honesty mock")
            if cid == "table-card" and p.get("honesty", "none") == "none" and nums is not None:
                for r in common._lines(p.get("rows_json")):
                    if isinstance(r, dict):
                        for v in r.values():
                            for m in re.findall(r"\d[\d,.]*", str(v)):
                                if m.replace(",", "").rstrip(".") not in nums:
                                    rep.err("assets", f"{c['id']}: table value {v} is not in the script or numbers.json; label the table mock or use known numbers")
                                    break


def rule_honesty(plan: dict, ctx: Context, rep: Report) -> None:
    texts = (ctx.toks.get("honesty_labels") or {}).get("texts") or {"mock": "illustrative", "sourced": "real"}
    labels = plan.get("labels", [])
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            h = c.get("props", {}).get("honesty")
            if h in ("mock", "sourced"):
                want = texts.get(h, h)
                if not any(l.get("scene") == s["id"] and l.get("kind") == "honesty" and l.get("text") == want for l in labels):
                    rep.err("honesty", f"{c['id']} shows {h} data but the scene {s['id']} has no honesty label \"{want}\" in labels")
                if c.get("honesty_label") != h:
                    rep.warn("honesty", f"{c['id']}: honesty_label {c.get('honesty_label')} differs from the honesty prop {h}")


def rule_branding(plan: dict, ctx: Context, rep: Report) -> None:
    br = plan.get("branding") or {}
    bt = ctx.toks.get("branding") or {}
    cta_id = br.get("cta_scene")
    cta = next((s for s in plan.get("scenes", []) if s["id"] == cta_id), None)
    sol = (plan.get("solution") or {}).get("type", "none")
    flashfx = sol == "flashfx"
    if bool(br.get("flashfx_allowed_outside_cta", False)) != flashfx:
        rep.err("branding", f"branding.flashfx_allowed_outside_cta must be {str(flashfx).lower()} for a {sol} solution")
    if not cta:
        rep.err("branding", f"branding.cta_scene {cta_id} is not a scene")
    else:
        if cta.get("beat_type") != "ask":
            rep.err("branding", f"the CTA scene {cta_id} is a {cta.get('beat_type')} beat, not the ask")
        dm = [c for c in cta.get("components", []) if c["component"] == "dm-card"]
        ec = [c for c in cta.get("components", []) if c["component"] == "end-card"]
        want_avatar = common.BRAND_PREFIX + str(bt.get("cta", {}).get("dm_avatar", "mark/avatar-dark.png"))
        if not dm:
            rep.err("branding", "the CTA scene has no dm-card (the FlashFX DM notification card, tweaks.md Branding)")
        else:
            p = dm[0].get("props", {})
            if p.get("avatar") != want_avatar:
                rep.err("branding", f"the DM card's avatar must be {want_avatar}, not {p.get('avatar')!r}")
            if str(p.get("sender", "FlashFX")) != str(bt.get("cta", {}).get("dm_sender", "FlashFX")):
                rep.err("branding", f"the DM card's sender must be {bt.get('cta', {}).get('dm_sender', 'FlashFX')}")
            if common._num(p, "avatar_size", 120) < 112:
                rep.err("branding", f"the DM avatar is {p.get('avatar_size')} px across; at least 112 px keeps its bolt at 64 px (BRAND.md)")
        if not ec:
            rep.err("branding", "the CTA scene has no end-card (the keyword card with the FlashFX lockup)")
        else:
            p = ec[0].get("props", {})
            lockup = str(p.get("lockup", ""))
            rel = lockup[len(common.BRAND_PREFIX):] if lockup.startswith(common.BRAND_PREFIX) else ""
            asset = ctx.brand_index.get(rel)
            if not asset or asset.get("type") != "lockup":
                rep.err("branding", f"the end card's lockup must be a lockup from brand.json (brand/lockup/...), not {lockup!r}")
            elif asset.get("use_on") not in ("light", "both"):
                rep.err("branding", f"the end card's lockup {lockup} is for {asset.get('use_on')} surfaces; the end card sits on paper (light)")
            if common._num(p, "lockup_w", 360) < float(bt.get("lockup_min_width", 300)):
                rep.err("branding", f"the lockup is {p.get('lockup_w')} px wide; at least {bt.get('lockup_min_width', 300)} px (BRAND.md)")
        if br.get("dm_avatar") != want_avatar:
            rep.err("branding", f"branding.dm_avatar must be {want_avatar}")
        if not str(br.get("lockup", "")).startswith(common.BRAND_PREFIX + "lockup/"):
            rep.err("branding", "branding.lockup must name a brand/lockup/ file")
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            for k, v in logo_spots(c):
                if not v.startswith(common.BRAND_PREFIX):
                    continue
                rel = v[len(common.BRAND_PREFIX):]
                asset = ctx.brand_index.get(rel)
                if not asset:
                    rep.err("branding", f"{c['id']}: {k} names {v}, which is not listed in brand.json (logo files come only from brand.json)")
                    continue
                surface = common.LOGO_SURFACES.get((c["component"], k), "light")
                if c["component"] == "window-card" and c.get("props", {}).get("kind") == "dark":
                    surface = "dark"
                if asset.get("use_on") not in (surface, "both"):
                    rep.err("branding", f"{c['id']}: {v} is for {asset.get('use_on')} surfaces but the {c['component']}'s {k} sits on a {surface} surface (use_on must match)")
                if s["id"] != cta_id and not flashfx:
                    rep.err("branding", f"{c['id']}: a FlashFX asset ({v}) outside the CTA while the solution is {sol}: FlashFX logos elsewhere only when the solution is FlashFX")
                if asset.get("type") == "lockup" and float(c.get("props", {}).get("lockup_w", c.get("props", {}).get("size", 360)) or 0) < float(bt.get("lockup_min_width", 300)) and c["component"] != "end-card":
                    rep.err("branding", f"{c['id']}: a lockup narrower than {bt.get('lockup_min_width', 300)} px")
            if c["component"] in ("hero-3d", "icon-3d") and re.search(r"flashfx", str(c.get("props", {}).get("label", "")), re.I):
                rep.err("branding", f"{c['id']}: no 3D version of the FlashFX logo or name (BRAND.md)")
    slot = br.get("brand_slot")
    if flashfx:
        if not (isinstance(slot, str) and slot.startswith(common.BRAND_PREFIX + "mark/")):
            rep.err("branding", "the solution is FlashFX: branding.brand_slot must be the FlashFX bolt (brand/mark/...)")
    elif isinstance(slot, str) and slot.startswith(common.BRAND_PREFIX):
        rep.err("branding", f"the solution is {sol}: the brand slot shows the tool's logo or a neutral icon, never a FlashFX asset ({slot})")


def rule_transitions(plan: dict, ctx: Context, rep: Report) -> None:
    tr = ctx.toks.get("transitions") or {}
    allowed = list(tr.get("allowed", ["fade-blur", "fall", "push", "cut"]))
    durations = {"fade-blur": ms_of_frames(float(tr.get("fade_blur_frames", 4))), "fall": ms_of_frames(float(tr.get("fall_frames", 10))),
                 "push": ms_of_frames(float(tr.get("push_out_frames", 6)) + float(tr.get("push_gap_frames", 2))), "cut": 0.0}
    scenes = plan.get("scenes", [])
    pairs = [(a["id"], b["id"]) for a, b in zip(scenes, scenes[1:])]
    got = plan.get("transitions", [])
    index = {(t.get("from"), t.get("to")): t for t in got}
    for pair in pairs:
        if pair not in index:
            rep.err("transitions", f"no transition from {pair[0]} to {pair[1]} (one per consecutive scene pair)")
    for t in got:
        if (t.get("from"), t.get("to")) not in pairs:
            rep.err("transitions", f"transition {t.get('from')} to {t.get('to')} does not join consecutive scenes")
        if t.get("type") not in allowed:
            rep.err("transitions", f"transition {t.get('from')} to {t.get('to')}: type {t.get('type')} is not allowed by the style ({', '.join(allowed)})")
            continue
        want = durations.get(t["type"], 0.0)
        if abs(float(t.get("duration_ms", 0)) - want) > ms_of_frames(1) + 0.5:
            rep.err("transitions", f"transition {t.get('from')} to {t.get('to')}: a {t['type']} lasts {want:.0f} ms in this style, not {t.get('duration_ms')}")
    if got:
        cuts = sum(1 for t in got if t.get("type") == "cut")
        if cuts / max(1, len(got)) > float(ctx.v("max_cut_share", 0.34)) + 1e-9 and cuts > 1:
            rep.err("transitions", f"{cuts} of {len(got)} scene changes are hard cuts; this look leaves a scene with motion (tokens.json transitions.scene_change exit-then-enter), at most a third may cut")
    if len(got) != len(set(index)):
        rep.err("transitions", "a scene pair has two transitions")


def rule_hook2(plan: dict, ctx: Context, rep: Report) -> None:
    h = plan.get("hook2")
    if not h:
        rep.skip("hook2")
        return
    lines = h.get("lines") or []
    if not (1 <= len(lines) <= 3):
        rep.err("hook2", f"hook 2 has {len(lines)} headline lines; 1 to 3")
    total = sum(len(common.words_of(str(ln).replace("*", ""))) for ln in lines)
    if total > 10:
        rep.err("hook2", f"hook 2's headline has {total} words; keep its spoken line")
    if ctx.script:
        want = common.words_of(ctx.script.get("hook2", {}).get("display", ""))
        got = [w for ln in lines for w in common.words_of(str(ln).replace("*", ""))]
        if want and [common.norm(w) for w in got] != [common.norm(w) for w in want]:
            rep.err("hook2", f"hook 2's headline must be its display line word for word (\"{' '.join(want)}\"), got \"{' '.join(got)}\"")


RULE_FUNCS = {
    "schema": rule_schema, "components": rule_components, "times": rule_times, "first_change": rule_first_change, "breath": rule_breath,
    "max_gap": rule_max_gap, "distinct": rule_distinct, "repeat": rule_repeat, "beat_map": rule_beat_map, "three_d": rule_three_d,
    "set_pieces": rule_set_pieces, "zones": rule_zones, "captions": rule_captions, "cards": rule_cards, "assets": rule_assets,
    "honesty": rule_honesty, "branding": rule_branding, "transitions": rule_transitions, "hook2": rule_hook2,
}


def validate(plan: dict, ctx: Context, parts: set[str] | None = None, skip_schema: bool = False) -> dict:
    parts = parts or {"scenes", "captions", "transitions"}
    rep = Report()
    wanted = set()
    if "scenes" in parts:
        wanted |= SCENE_RULES
    if "captions" in parts:
        wanted |= CAPTION_RULES | {"schema"}
    if "transitions" in parts:
        wanted |= TRANSITION_RULES | {"schema"}
    if skip_schema:
        wanted.discard("schema")
    for name in RULES:
        if name not in wanted:
            continue
        try:
            RULE_FUNCS[name](plan, ctx, rep)
        except Exception as exc:  # a rule that crashes is a validator bug: report it, never hide it
            rep.err(name, f"the validator's {name} rule failed: {type(exc).__name__}: {exc}")
    return rep.result()


def format_lines(result: dict) -> list[str]:
    lines = [f"rule={e['rule']}: {e['message']}" for e in result["errors"]]
    lines += [f"warning={w['rule']}: {w['message']}" for w in result["warnings"]]
    return lines


def run(args) -> int:
    plan = common.load_json(args.plan)
    if args.run_dir:
        ctx = Context.from_run(args.run_dir)
    else:
        assets = None
        if args.assets_json:
            aj = common.load_json(args.assets_json)
            folder = os.path.dirname(os.path.abspath(args.assets_json))
            assets = {}
            for a in aj:
                name = os.path.basename(str(a.get("file", "")))
                if os.path.isfile(os.path.join(folder, "assets", name)) or args.assets_exist:
                    assets[name] = a
        ctx = Context(words=common.load_json(args.words) if args.words else None, script=common.load_json(args.script) if args.script else None,
                      assets=assets, numbers=common.load_json(args.numbers) if args.numbers else None)
    parts = set(p.strip() for p in args.parts.split(",") if p.strip()) if args.parts else None
    result = validate(plan, ctx, parts)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for line in format_lines(result):
            print(line)
        print(f"plan {'ok' if result['ok'] else 'NOT ok'}: {len(result['errors'])} errors, {len(result['warnings'])} warnings" + (f", skipped {', '.join(result['skipped'])}" if result["skipped"] else ""))
    return 0 if result["ok"] else 1
