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
honesty, transitions, hook2; and from M15 (Motion and energy rules E3 and E4): caption_modes (word or group mode, word
mode under any text, the group's layout), text_budget (100 characters of non-caption text at any moment), text_size
(no graphic text under the caption size).
"""
from __future__ import annotations

import json
import os
import re

from visual import common, kinetic

SCHEMA = os.path.join(common.REPO, "pipeline", "stages", "09-plan", "schema.json")
PASS_SCHEMAS = {"animations": "09a-animations", "text": "09b-text", "transitions": "09c-transitions"}  # a pass file validates against its own schema
RULES = ["schema", "components", "times", "first_change", "breath", "max_gap", "distinct", "repeat", "beat_map", "three_d",
         "set_pieces", "zones", "hero_motion", "hero_fill", "layers", "camera", "hook_frame0", "empty_paper", "list_entry", "real_motion",
         "captions", "caption_modes", "cards", "text_budget", "text_size", "assets", "honesty", "branding", "transitions", "transition_variety", "hook2"]
SCENE_RULES = {"schema", "components", "times", "first_change", "breath", "max_gap", "distinct", "repeat", "beat_map", "three_d",
               "set_pieces", "zones", "assets", "branding", "hook2", "text_size", "hero_motion", "hero_fill", "layers", "camera", "hook_frame0", "empty_paper", "list_entry", "real_motion"}
CAPTION_RULES = {"captions", "caption_modes", "cards", "text_budget", "text_size", "honesty", "zones"}
TRANSITION_RULES = {"transitions", "transition_variety"}
# E9 (M16): the rules that enforce the Motion and energy rules E8, one failing fixture plan each (pipeline/tests/test-m16.sh)
ENERGY_RULES = ("hero_motion", "hero_fill", "layers", "camera", "hook_frame0", "empty_paper", "list_entry", "transition_variety")
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
        return cls(config=inp.config, words=inp.words, script=inp.script, assets=({**inp.asset_files(), **inp.recording_files()}) if (inp.assets_json or os.path.isdir(inp.assets_dir)) else None,
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
            if cid in ("paper-canvas", "caption-line", "caption-word", "caption-group"):
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
            for key in ("focus_json", "points_json", "colors_json"):
                for item in common._lines(p.get(key)):
                    if isinstance(item, dict) and "at" in item:
                        try:
                            out.add(start + int(float(item["at"]) * 1000))
                        except (TypeError, ValueError):
                            pass
            for key in ("cta_at", "fan_at"):
                if key in p:
                    try:
                        out.add(start + int(float(p[key]) * 1000))
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
    if cid in ("hero-3d", "icon-3d", "mascot", "logo-tile", "paper-canvas", "caption-line", "caption-word", "caption-group", "camera-move", "exit-move", "thumb-grid"):
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
                if k not in declared and not (c["component"] in common.CLIP_START and k == "clip_start"):
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
    used = {c["component"] for s in scenes for c in s.get("components", []) if c["component"] not in ("paper-canvas", "caption-line", "caption-word", "caption-group")}
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
    band_exception = bool(((ctx.toks.get("zones") or {}).get("caption") or {}).get("safe_zone_exception", False))
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
            elif s["id"] == cta and y1 > safe_bottom + tol and not (cid in ("dm-card", "end-card") and band_exception):
                # the DM card and the end card may sit in the caption band only while that band lies below the safe bottom
                # (tweaks.md's old caption box at y 1480); with the captions inside the safe zone (y 1332 since
                # 2026-11-07) they keep the safe bottom like everything else (M14)
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
    g_lo, g_hi = ((kinetic.grammar(ctx.toks).get("group_words")) or [2, 6])[:2]
    for i, ch in enumerate(chunks):
        words = ch.get("words", [])
        mode = caption_mode(ch)
        explicit = "mode" in ch   # M15: a word-mode entry shows its words one at a time, a group is laid out by kinetic.py
        if mode == "group":
            if len(words) < 1 or len(words) > int(g_hi):
                rep.err("captions", f"caption group {i} has {len(words)} words; groups hold {g_lo} to {g_hi} (tokens.json motion.grammar.captions)")
        elif not (int(lo) <= len(words) <= int(hi)):
            rep.err("captions", f"caption chunk {i} has {len(words)} words; chunks hold {lo} to {hi} (tokens.json limits.caption)")
        em = sum(1 for w in words if w.get("emphasis"))
        if em > int(em_hi):
            rep.err("captions", f"caption chunk {i} has {em} emphasis words; at most {em_hi}")
        width = common.caption_chunk_width(words, ctx.toks) if not explicit else 0.0
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
            if cid == "mock-site-card" and p.get("honesty", "mock") == "none":
                rep.err("assets", f"{c['id']}: a mock website is a mock UI; it needs honesty mock")
            if cid in ("screenshot-zoom", "video-card") and p.get("honesty", "sourced") == "none" and (p.get("image") or p.get("video")):
                rep.warn("assets", f"{c['id']}: shows a real page ({p.get('image') or p.get('video')}) without honesty sourced")
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


# ------------------------------------------------------------------------------------------------ M15: the caption modes and E4

def caption_mode(ch: dict) -> str:
    """word or group; a chunk of a plan written before M15 has no mode and is read as word mode."""
    return str(ch.get("mode") or "word")


def cta_scene_ids(plan: dict) -> set:
    cta = (plan.get("branding") or {}).get("cta_scene")
    ids = {cta} if cta else set()
    ids |= {s["id"] for s in plan.get("scenes", []) if s.get("beat_type") == "ask"}
    return ids


def rule_caption_modes(plan: dict, ctx: Context, rep: Report) -> None:
    """E3 and E4 for the captions: every entry is word mode or group mode, word mode whenever any other text is on screen,
    a group only where it covers no graphic, a group laid out by kinetic.py (fonts, sizes, zone, rail, asymmetry), and every
    caption moving while it is on screen."""
    toks = ctx.toks
    g = kinetic.grammar(toks)
    chunks = plan.get("captions", [])
    if not chunks:
        return
    text_wins = common.text_windows(plan, toks)
    scene_by_id = {s["id"]: s for s in plan.get("scenes", [])}
    max_w = float((toks.get("zones") or {}).get("caption", {}).get("max_width", 620))
    caption_px = kinetic.caption_px(toks)
    em_ratio = (g.get("emphasis_size_ratio") or [1.25, 1.5])[1]
    for i, ch in enumerate(chunks):
        mode = caption_mode(ch)
        legacy = "mode" not in ch
        words = ch.get("words", [])
        label = f"caption {i} (\"{' '.join(w['word'] for w in words)}\")"
        if mode not in ("word", "group"):
            rep.err("caption_modes", f"{label}: the mode is {mode!r}; word or group (E3)")
            continue
        start, end = int(ch["start_ms"]), int(ch["end_ms"])
        if ch.get("importance") not in (None, "hook", "key-claim", "number", "payoff", "pre-ask", "normal"):
            rep.err("caption_modes", f"{label}: importance {ch.get('importance')!r} is not one of script.json's (hook, key-claim, number, payoff, pre-ask, normal)")
        if mode == "word":
            if not legacy:
                for w in words:
                    px = caption_px * (em_ratio if w.get("emphasis") else 1.0)
                    wid = common.text_width(w["word"], px, toks, "serif-italic" if w.get("emphasis") else "grotesk") + 28
                    if wid > max_w + 1:
                        rep.err("caption_modes", f"{label}: the word \"{w['word']}\" is about {wid:.0f} px wide at {px:.0f} px; the caption line is at most {max_w:.0f} px (word mode shows one word at a time)")
                for p in kinetic.check_motion(ch, toks):
                    rep.err("caption_modes", f"{label}: {p}")
            continue
        # group mode ---------------------------------------------------------------------------------------------
        lo_g, hi_g = (g.get("group_words") or [2, 6])[:2]
        if not (int(lo_g) <= len(words) <= int(hi_g)) and not (len(words) == 1 and ch.get("layout")):
            rep.err("caption_modes", f"{label}: a group holds {lo_g} to {hi_g} words, this one has {len(words)} (tokens.json motion.grammar.captions.group_words)")
        for (a, b, inst) in text_wins:
            if start < b and a < end:
                rep.err("caption_modes", f"{label} runs {start} to {end} ms over the text of {inst} ({a} to {b} ms): captions are in word mode whenever any other text is on screen (E4, E3 one mode at a time)")
                break
        lay = ch.get("layout")
        if not lay:
            rep.err("caption_modes", f"{label}: a group needs its layout (kinetic.py places every word; no model positions words by hand)")
            continue
        if [w.get("text") for w in lay.get("words", [])] != [w["word"] for w in words]:
            rep.err("caption_modes", f"{label}: the layout's words are not the caption's words in order")
        for p in kinetic.check_layout(lay, toks):
            rep.err("caption_modes", f"{label}: {p}")
        if ch.get("anchor") is not None and lay.get("anchor") != ch.get("anchor"):
            rep.err("caption_modes", f"{label}: the anchor of the entry ({ch.get('anchor')}) is not the layout's ({lay.get('anchor')})")
        box = lay.get("box") or {}
        for fp in common.visible_boxes(plan, start, end, toks):
            if not box:
                break
            ox = min(fp["x"] + fp["w"], box["x"] + box["w"]) - max(fp["x"], box["x"])
            oy = min(fp["y"] + fp["h"], box["y"] + box["h"]) - max(fp["y"], box["y"])
            if ox > 8 and oy > 8:
                rep.err("caption_modes", f"{label} covers {fp['id']} ({fp['component']}): a group fills the hero zone, so it needs a beat whose hero zone shows no graphic there (E3)")
                break
    # one mode at a time: entries that overlap in time share a mode
    for a, b in zip(chunks, chunks[1:]):
        if caption_mode(a) != caption_mode(b) and int(a["end_ms"]) > int(b["start_ms"]) + 40:
            rep.err("caption_modes", f"a {caption_mode(a)} caption ends at {a['end_ms']} ms but the {caption_mode(b)} caption after it starts at {b['start_ms']} ms: one mode at a time (E3)")


def rule_text_budget(plan: dict, ctx: Context, rep: Report) -> None:
    """E4: at most max_chars_on_screen characters of non-caption text on screen at any moment (the CTA's text is the ask,
    which the style fixes, so that scene is left out)."""
    limit = int(((ctx.toks.get("motion") or {}).get("grammar") or {}).get("text_budget", {}).get("max_chars_on_screen", 100))
    rows = common.text_chars_at(plan, ctx.toks, cta_scene_ids(plan))
    over = [r for r in rows if r["chars"] > limit]
    if over:
        worst = max(over, key=lambda r: r["chars"])
        parts = ", ".join(f"{inst} {prop} {n}" for inst, prop, n in worst["items"][:6])
        rep.err("text_budget", f"{worst['chars']} characters of non-caption text are on screen between {worst['from_ms']} and {worst['to_ms']} ms ({parts}); at most {limit} at any moment (E4: graphics first, cut text where a graphic can carry the meaning)"
                + (f"; {len(over)} stretches are over" if len(over) > 1 else ""))


def rule_text_size(plan: dict, ctx: Context, rep: Report) -> None:
    """E4: no text on a graphic is smaller than the caption size. A size the plan chose (terminal-card or strike-through
    font_px) under it is an error; a size the component bakes in is a warning until the library is resized (config
    visual.text_size_baked: error makes it an error)."""
    min_px = float(((ctx.toks.get("motion") or {}).get("grammar") or {}).get("text_budget", {}).get("min_text_px", 67))
    baked_error = str(ctx.v("text_size_baked", "warn")) == "error"
    seen_baked: dict = {}
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            for it in common.text_items(c["component"], c.get("props", {}), ctx.toks):
                px = it.get("px")
                if px is None or px >= min_px - 0.01:
                    continue
                if it.get("explicit") or baked_error:
                    rep.err("text_size", f"{c['id']}: {it['prop']} \"{it['text'][:40]}\" is {px:g} px; no text on a graphic is smaller than the caption size {min_px:g} px (E4): a graphic that needs smaller text needs less text")
                else:
                    seen_baked.setdefault((c["component"], it["prop"]), [px, 0])[1] += 1
    if seen_baked:
        rep.warn("text_size", "text under the caption size, baked into the components: " + ", ".join(f"{cid} {prop} {px:g} px" for (cid, prop), (px, _n) in sorted(seen_baked.items())[:8])
                 + f" (E4 wants {min_px:g} px or more: the library's sizes are the style's own, resizing them is open)")


# ------------------------------------------------------------------------------------------------ E8 and E9 (M16)

def composition(ctx: Context) -> dict:
    return ((ctx.toks.get("motion") or {}).get("grammar") or {}).get("composition") or {}


def energy_level(ctx: Context) -> str:
    """config visual.energy_rules: error (the default: the rules fail the plan), warn (they report only), off (the test sandboxes of
    the milestones before M16 run their frozen low-energy plans with it off: pipeline/tests/lib.sh SANDBOX_ENERGY; the environment
    variable REELS_ENERGY_RULES overrides the config for a direct call, test-m10 sets it to off)."""
    return str(os.environ.get("REELS_ENERGY_RULES") or ctx.v("energy_rules", "error")).lower()


def energy_report(ctx: Context, rep: Report, rule: str, msg: str) -> None:
    lvl = energy_level(ctx)
    if lvl == "off":
        return
    (rep.warn if lvl == "warn" else rep.err)(rule, msg)


def content_components(scene: dict, ctx: Context) -> list[dict]:
    """The components of a scene that are content (not the canvas, the captions, the camera and exit moves, the cursor, the mascot)."""
    exempt = set(composition(ctx).get("layer_exempt") or ["paper-canvas", "caption-word", "caption-group", "camera-move", "exit-move", "cursor", "mascot"])
    return [c for c in scene.get("components", []) if c["component"] not in exempt and c["component"] != "caption-line"]


def band_overlap_area(fp: dict, y0: float, y1: float) -> float:
    return max(0.0, fp["w"]) * max(0.0, min(y1, fp["y"] + fp["h"]) - max(y0, fp["y"]))


def union_ms(intervals: list[tuple[float, float]]) -> float:
    total, end = 0.0, None
    for a, b in sorted(intervals):
        if b <= a:
            continue
        if end is None or a > end:
            total += b - a
            end = b
        elif b > end:
            total += b - end
            end = b
    return total


def hero_band(ctx: Context) -> tuple[float, float]:
    band = composition(ctx).get("hero_band_y") or [640, 1280]
    return float(band[0]), float(band[1])


def rule_hero_motion(plan: dict, ctx: Context, rep: Report) -> None:
    """E9: every scene keeps a moving element in the hero zone. Every library component lives on pc-motion.js (E1: nothing is
    ever static), so the plan-level proxy is substance: a component with at least hero_min_area_px of its footprint inside the
    hero band (the middle third, where E0 measures the middle-band energy) for at least 70 percent of the scene."""
    g = composition(ctx)
    y0, y1 = hero_band(ctx)
    min_area = float(g.get("hero_min_area_px", 120000))
    share = float(ctx.v("hero_motion_share", 0.7))
    for s in plan.get("scenes", []):
        a, b = int(s["start_ms"]), int(s["end_ms"])
        if b <= a:
            continue
        spans = []
        for c in content_components(s, ctx):
            fp = common.footprint(c["component"], c.get("props", {}), ctx.toks)
            if fp and band_overlap_area(fp, y0, y1) >= min_area:
                spans.append((max(a, int(c["start_ms"])), min(b, int(c["end_ms"]))))
        got = union_ms(spans) / (b - a)
        if got + 1e-9 < share:
            energy_report(ctx, rep, "hero_motion", f"scene {s['id']} ({s.get('beat_type')}): a moving element of substance sits in the hero zone (y {y0:g} to {y1:g}) for only {got * 100:.0f} percent of the scene; "
                          f"at least {share * 100:.0f} percent is wanted (E9): make the hero card, recording or stack fill the middle of the screen from the scene's start to its end")


def rule_hero_fill(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: the hero content fills 70 to 85 percent of the frame width: the widest stretch of the scene's content, as the union of
    the footprints on screen together, spans at least the lower share of 1080 px."""
    lo, hi = (composition(ctx).get("hero_width_share") or [0.7, 0.85])[:2]
    W = 1080.0
    for s in plan.get("scenes", []):
        comps = [c for c in content_components(s, ctx) if c["component"] != "logo-tile"]
        if not comps:
            energy_report(ctx, rep, "hero_fill", f"scene {s['id']} has no content component at all (the hero content fills {lo * 100:.0f} to {hi * 100:.0f} percent of the frame width, E8)")
            continue
        times = sorted({int(c["start_ms"]) + 1 for c in comps} | {int(s["start_ms"]) + 1})
        best = 0.0
        for t in times:
            live = [c for c in comps if int(c["start_ms"]) <= t < int(c["end_ms"])]
            boxes = [common.footprint(c["component"], c.get("props", {}), ctx.toks) for c in live]
            boxes = [fp for fp in boxes if fp and fp["w"] > 0]
            if boxes:
                best = max(best, max(fp["x"] + fp["w"] for fp in boxes) - min(fp["x"] for fp in boxes))
        if best + 1 < lo * W:
            energy_report(ctx, rep, "hero_fill", f"scene {s['id']} ({s.get('beat_type')}): the hero content spans {best:.0f} px ({best / W * 100:.0f} percent of the width); E8 wants {lo * 100:.0f} to {hi * 100:.0f} percent "
                          f"({lo * W:.0f} to {hi * W:.0f} px): widen the hero (w {hi * W:.0f} for a card, or a stack, fan or grid that spans the width)")


def layer_weight(cid: str, ctx: Context) -> int:
    return 2 if cid in set(composition(ctx).get("stack_kinds") or ["card-fan", "card-grid", "thumb-grid", "swatch-row"]) else 1


def rule_layers(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: every scene layers at least 2 elements (the hero plus a supporting chip, badge, stack or number): at least 2 content
    components on screen together for most of the scene (a stack, fan or grid counts as 2)."""
    need = int(composition(ctx).get("min_layers_per_scene", 2))
    share = float(ctx.v("layers_share", 0.6))
    for s in plan.get("scenes", []):
        a, b = int(s["start_ms"]), int(s["end_ms"])
        if b <= a:
            continue
        comps = content_components(s, ctx)
        cuts = sorted({a, b} | {min(b, max(a, int(c["start_ms"]))) for c in comps} | {min(b, max(a, int(c["end_ms"]))) for c in comps})
        ok_ms = 0.0
        for t0, t1 in zip(cuts, cuts[1:]):
            mid = (t0 + t1) / 2
            n = sum(layer_weight(c["component"], ctx) for c in comps if int(c["start_ms"]) <= mid < int(c["end_ms"]))
            if n >= need:
                ok_ms += t1 - t0
        if ok_ms / (b - a) + 1e-9 < share:
            energy_report(ctx, rep, "layers", f"scene {s['id']} ({s.get('beat_type')}): {need} or more elements are on screen together for only {ok_ms / (b - a) * 100:.0f} percent of the scene; "
                          f"at least {share * 100:.0f} percent is wanted (E8: the hero plus a supporting chip, badge, stack or number, a fan or a grid counts as two)")


def camera_scene(scene: dict, ctx: Context) -> bool:
    kinds = set(composition(ctx).get("camera_kinds") or ["camera-move", "screenshot-zoom", "hero-3d", "icon-3d"])
    for c in scene.get("components", []):
        if c["component"] in kinds:
            if c["component"] == "screenshot-zoom" and not common._lines(c.get("props", {}).get("focus_json")):
                continue
            if c["component"] == "camera-move" and not c.get("props", {}).get("image"):
                continue   # without a screenshot it shrinks an empty placeholder (its "the scene" label hides under the cards: a layout error)
            return True
    return False


def rule_camera(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: a camera move (a push-in, a pull-back, a pan, a slow orbit of the 2.5D scene) in at least 1 of every 3 scenes."""
    every = max(1, int(composition(ctx).get("camera_every_scenes", 3)))
    scenes = plan.get("scenes", [])
    if len(scenes) < every:
        return
    cams = [s["id"] for s in scenes if camera_scene(s, ctx)]
    want = len(scenes) // every
    if len(cams) < want:
        energy_report(ctx, rep, "camera", f"{len(cams)} of {len(scenes)} scenes have a camera move ({', '.join(cams) or 'none'}); E8 wants at least 1 of every {every}, so {want}: add camera-move (a push-in or pull-back), "
                      f"screenshot-zoom with focus points (a pan and zoom over a page) or a turning 3D object to scenes that have none")


def rule_hook_frame0(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: the hook moves from frame 0: its hero element is moving by frame 4, never empty paper waiting for it."""
    n = float(composition(ctx).get("hook_moving_by_frame", 4))
    limit = int(round(n * 1000.0 / common.FPS))
    hook = next((s for s in plan.get("scenes", []) if s.get("beat_type") == "hook"), None)
    if not hook:
        return
    t0 = int(hook["start_ms"])
    comps = content_components(hook, ctx)
    early = [c for c in comps if int(c["start_ms"]) - t0 <= limit and common._num(c.get("props", {}), "enter_at", 0) * 1000.0 <= limit]
    if t0 > limit:
        energy_report(ctx, rep, "hook_frame0", f"the hook scene starts at {t0} ms; the reel moves from frame 0 (E8)")
    elif not early:
        first = min((int(c["start_ms"]) for c in comps), default=None)
        energy_report(ctx, rep, "hook_frame0", f"the hook has no element that starts moving by frame {n:g} ({limit} ms): its first component starts at {first} ms; the hero element enters at the scene's start (start_ms {t0}, enter_at 0)")


def rule_empty_paper(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: empty paper in the hero zone lasts at most 1 s: no stretch of the reel longer than empty_hero_max_s has no content
    component with at least 20000 px2 of its footprint in the hero band."""
    limit = float(composition(ctx).get("empty_hero_max_s", 1)) * 1000.0
    y0, y1 = hero_band(ctx)
    dur = int(plan.get("duration_ms", 0))
    if dur <= 0:
        return
    spans = []
    for s in plan.get("scenes", []):
        for c in content_components(s, ctx):
            fp = common.footprint(c["component"], c.get("props", {}), ctx.toks)
            if fp and band_overlap_area(fp, y0, y1) >= 20000:
                spans.append((max(0, int(c["start_ms"])), min(dur, int(c["end_ms"]))))
    spans.sort()
    cursor = 0
    worst = (0, 0, 0)
    for a, b in spans + [(dur, dur)]:
        if a - cursor > worst[0]:
            worst = (a - cursor, cursor, a)
        cursor = max(cursor, b)
    if worst[0] > limit + 1:
        energy_report(ctx, rep, "empty_paper", f"the hero zone is empty paper from {worst[1]} to {worst[2]} ms ({worst[0] / 1000:.1f} s); at most {limit / 1000:g} s (E8): start the next hero earlier or keep the last one on screen")


def rule_list_entry(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: lists and groups enter as stacks, fans or grids with staggers, not one card after another in the same spot: more than
    list_same_spot_max components of one kind that start one after another at about the same position are an error."""
    g = composition(ctx)
    most = int(g.get("list_same_spot_max", 2))
    tol = float(g.get("list_same_spot_px", 40))
    for s in plan.get("scenes", []):
        groups: list[list[dict]] = []
        for c in content_components(s, ctx):
            p = c.get("props", {})
            if c["component"] in ("headline", "end-card", "dm-card", "logo-tile", "pop", "check-badge", "hero-3d", "icon-3d"):
                continue
            x, y = common._num(p, "x", 90), common._num(p, "y", 560)
            for grp in groups:
                f = grp[0]
                if f["component"] == c["component"] and abs(common._num(f["props"], "x", 90) - x) <= tol and abs(common._num(f["props"], "y", 560) - y) <= tol:
                    grp.append({"component": c["component"], "props": p, "id": c["id"], "start_ms": int(c["start_ms"])})
                    break
            else:
                groups.append([{"component": c["component"], "props": p, "id": c["id"], "start_ms": int(c["start_ms"])}])
        for grp in groups:
            starts = sorted({m["start_ms"] // 200 for m in grp})
            if len(grp) > most and len(starts) > most:
                energy_report(ctx, rep, "list_entry", f"scene {s['id']}: {len(grp)} {grp[0]['component']} components ({', '.join(m['id'] for m in grp[:5])}) enter one after another in the same spot; a list enters as a stack, a fan "
                              f"or a grid with staggers (card-fan, card-grid, thumb-grid, swatch-row), not one card after another (E8)")


def rule_real_motion(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: real motion inside the content wherever it exists: a warning when the research stage recorded pages and the plan plays none
    of them (no video-card with a research video) and shows no screenshot-zoom."""
    if not ctx.assets:
        return
    recs = [k for k in ctx.assets if str(k).lower().endswith(".mp4")]
    if not recs:
        return
    comps = [c for s in plan.get("scenes", []) for c in s.get("components", [])]
    played = any(c["component"] == "video-card" and str(c.get("props", {}).get("video", "")).startswith(common.RESEARCH_PREFIX) for c in comps)
    if not played:
        rep.warn("real_motion", f"the research stage recorded {len(recs)} page(s) ({', '.join(sorted(recs)[:3])}) but no video-card plays one: real motion inside the content (a recording playing in a card) beats a still screenshot (E8)")


def rule_transition_variety(plan: dict, ctx: Context, rep: Report) -> None:
    """E8: scene changes vary: no transition type more than transition_type_max times in a reel."""
    most = int(composition(ctx).get("transition_type_max", 3))
    counts: dict = {}
    for t in plan.get("transitions", []):
        counts[t.get("type")] = counts.get(t.get("type"), 0) + 1
    for typ, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n > most:
            energy_report(ctx, rep, "transition_variety", f"the transition {typ} is used {n} times; E8 allows a type at most {most} times in a reel: vary the scene changes ({', '.join(sorted(counts))} so far)")


RULE_FUNCS = {
    "schema": rule_schema, "components": rule_components, "times": rule_times, "first_change": rule_first_change, "breath": rule_breath,
    "max_gap": rule_max_gap, "distinct": rule_distinct, "repeat": rule_repeat, "beat_map": rule_beat_map, "three_d": rule_three_d,
    "set_pieces": rule_set_pieces, "zones": rule_zones, "captions": rule_captions, "caption_modes": rule_caption_modes, "cards": rule_cards,
    "text_budget": rule_text_budget, "text_size": rule_text_size, "assets": rule_assets,
    "honesty": rule_honesty, "branding": rule_branding, "transitions": rule_transitions, "hook2": rule_hook2,
    "hero_motion": rule_hero_motion, "hero_fill": rule_hero_fill, "layers": rule_layers, "camera": rule_camera, "hook_frame0": rule_hook_frame0,
    "empty_paper": rule_empty_paper, "list_entry": rule_list_entry, "real_motion": rule_real_motion, "transition_variety": rule_transition_variety,
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
                rec = os.path.basename(str(a.get("recording") or ""))
                if rec and (os.path.isfile(os.path.join(folder, "assets", rec)) or args.assets_exist):
                    assets[rec] = a
            adir = os.path.join(folder, "assets")
            for f in (os.listdir(adir) if os.path.isdir(adir) else []):
                if f.lower().endswith(".mp4") and f not in assets:
                    assets[f] = {"file": "assets/" + f, "name": os.path.splitext(f)[0]}
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
