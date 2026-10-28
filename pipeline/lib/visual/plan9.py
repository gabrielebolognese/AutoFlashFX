"""pipeline/lib/visual/plan9.py: the visual director's three passes (BUILD_SPEC.md S9). The model designs, this code
composes and decides (DECISIONS.md 95): it resolves every time to a spoken word of words.json, fills the defaults,
places the branding by the rules of tweaks.md, builds the caption chunks from the model's word groups and the
real word times, and validates the result (visual/plan_validate.py) so the stage can ask the model once more with
the exact problems.

  python pipeline/lib/visual digest --run-dir DIR --out FOLDER --pass animations|text|transitions
      the prompt digests: timeline.md (beats, words and times), catalog.md (the library), golden.md (the example reel),
      assets.md (the research screenshots), solution.md (the solution and the branding it implies), and for the later
      passes scenes.md (the 9a plan's instances) and chunks.md (the baseline caption chunks)
  python pipeline/lib/visual animations --run-dir DIR --answer answer.json --out 09a-animations/plan.json
  python pipeline/lib/visual text --run-dir DIR --answer answer.json --out 09b-text/plan.json
  python pipeline/lib/visual transitions --run-dir DIR --answer answer.json --out 09c-transitions/plan.json --merged merged.json
      each prints one JSON line {ok, errors, warnings, summary, ...}; exit 0 when the plan was written, 4 when the
      answer has problems the model must fix (the errors list), 1 on a code error
  python pipeline/lib/visual check-text --run-dir DIR
      the text pass's checks on the run's 09a and 09b plans as they are now: exit 0 ok, 4 errors (09c runs 09b again)
"""
from __future__ import annotations

import copy
import json
import os
import re

from motion import captions
from visual import common, plan_merge, plan_validate

ROLES = ["hero", "support", "label", "brand-slot", "logo", "set-piece", "cta", "notification", "text"]


# ------------------------------------------------------------------------------------------------ digests

def fmt_ms(ms: int) -> str:
    return f"{ms / 1000:.2f}s"


def timeline_md(inp: common.Inputs) -> str:
    tl = common.Timeline(inp.words)
    beats = {b["id"]: b for b in inp.script.get("beats", [])}
    lines = [f"Voice: {tl.duration_ms} ms ({tl.duration_ms / 1000:.2f} s), {len(tl.words)} spoken words, {len(tl.order)} beats. Times are ms from the start of the reel."]
    if tl.breath:
        lines.append(f"The hook breath (silence after the hook beat, BUILD_SPEC.md S8): {tl.breath['start_ms']} to {tl.breath['end_ms']} ms. It is never a static frame: the hook's set piece lands inside it.")
    lines.append("")
    for bid in tl.order:
        st, en = tl.scene_span(bid)
        sb = beats.get(bid, {})
        lines.append(f"## {bid} ({sb.get('type', '?')}): scene window {st} to {en} ms ({(en - st) / 1000:.2f} s)")
        lines.append(f"- display: {sb.get('display', '')}")
        if sb.get("spoken") and sb.get("spoken") != sb.get("display"):
            lines.append(f"- spoken: {sb.get('spoken', '')}")
        lines.append(f"- card (the script's on-screen text, 6 words or fewer): {sb.get('card', '')}")
        lines.append(f"- emphasis: {', '.join(sb.get('emphasis', [])) or 'none'}; facts: {', '.join(sb.get('facts', [])) or 'none'}")
        lines.append("- words (start ms): " + " ".join(f"{w['word']}({w['start_ms']})" for w in tl.beat_words(bid)))
        lines.append("")
    if inp.words_hook2:
        tl2 = common.Timeline(inp.words_hook2)
        h2 = inp.script.get("hook2", {})
        lines.append(f"## hook 2 (the alternate clip, {tl2.duration_ms} ms): display \"{h2.get('display', '')}\", card \"{h2.get('card', '')}\"")
        lines.append("- words (start ms): " + " ".join(f"{w['word']}({w['start_ms']})" for w in tl2.words))
    return "\n".join(lines) + "\n"


def catalog_md(cat: dict, include_demo: bool = True) -> str:
    lines = [f"motion-lib/catalog.json: {len([c for c in cat['components'] if c.get('status') == 'approved'])} approved components. Props are the declared variables: id: type (default) [options]. "
             "IMAGE marks an image prop: it takes brand/<path from brand.json> or research/<file> (never another path, never drawn). "
             "Times in props are seconds local to the component's own start. Every component also takes exit and exit_at, which the transitions pass sets: never set them yourself.", ""]
    for c in cat["components"]:
        if c.get("status") != "approved" or c["id"] in ("paper-canvas", "caption-line"):
            continue
        lines.append(f"### {c['id']} (item {c.get('item') or 'extra'}, kind {c.get('kind')}): {c.get('name')}")
        lines.append(f"- does: {c.get('does', '')}")
        lines.append(f"- beats: {', '.join(c.get('beat_types', []))}")
        props = []
        for p in c.get("props", []):
            if p["id"] in ("exit", "exit_at", "clip_start"):
                continue
            d = json.dumps(p.get("default"), ensure_ascii=False)
            if len(d) > 60:
                d = d[:57] + "..."
            s = f"{p['id']}: {p.get('type', 'string')} ({d})"
            if p.get("options"):
                s += " [" + "|".join(str(o) for o in p["options"]) + "]"
            if p.get("image"):
                s += " IMAGE"
            if p.get("label") and p["id"] not in ("x", "y", "w", "h"):
                s += f" {{{p['label'][:70]}}}"
            props.append(s)
        lines.append("- props: " + "; ".join(props))
        ev = ", ".join(f"{e.get('event')}@{e.get('frame')}" + (f" ({e['cue']})" if e.get("cue") else "") for e in c.get("sound_events", []))
        if ev:
            lines.append(f"- sound events (frame offsets, the cue S11 gives them): {ev}")
        if include_demo and c.get("demo"):
            lines.append(f"- demo props: {json.dumps(c['demo'], ensure_ascii=False)}")
        lines.append(f"- still: motion-lib/{c.get('still')}")
        lines.append("")
    return "\n".join(lines) + "\n"


def golden_md(golden_dir: str) -> str:
    plan_path = os.path.join(golden_dir, "plan.json")
    if not os.path.isfile(plan_path):
        return "(no golden reel on this machine)\n"
    plan = common.load_json(plan_path)
    lines = [f"golden/test-idea/plan.json: {len(plan['scenes'])} scenes, {plan['duration_ms']} ms, solution {plan.get('solution', {}).get('type')}; "
             f"contact sheet: {common.mixed(os.path.join(golden_dir, 'contact-sheet.png'))} (one still per scene; read it to see the look).", ""]
    for s in plan["scenes"]:
        lines.append(f"### {s['id']} {s['beat']} ({s['beat_type']}) {s['start_ms']} to {s['end_ms']} ms" + (" set piece" if s.get("set_piece") else "") + (f", honesty {s['honesty_label']}" if s.get("honesty_label") else ""))
        for c in s["components"]:
            props = {k: v for k, v in c["props"].items() if k not in ("exit", "exit_at", "words_json", "clip_start")}
            lines.append(f"- {c['component']} ({c.get('role')}) at {c['start_ms']} ms: {json.dumps(props, ensure_ascii=False)}")
        if s.get("emphasis_hits"):
            lines.append("- emphasis hits: " + ", ".join(f"{h['word']}@{h['ms']}" for h in s["emphasis_hits"]))
        lines.append("")
    lines.append("Transitions: " + ", ".join(f"{t['from']}>{t['to']} {t['type']} {t['duration_ms']}ms" for t in plan.get("transitions", [])))
    if plan.get("notes"):
        lines.append("Notes: " + str(plan["notes"]))
    return "\n".join(lines) + "\n"


def assets_md(inp: common.Inputs) -> str:
    files = inp.asset_files()
    if not files:
        return "(no research assets: no real screenshot can be shown; use cards, chips, numbers and typed text, never a mock screenshot of a real page)\n"
    lines = [f"01-research/assets/ ({len(files)} screenshots captured by the research stage at 1080 px wide; write them as research/<file>; a component showing one takes honesty sourced):", ""]
    for name, a in files.items():
        lines.append(f"- research/{name}: {a.get('what', '')} (url {a.get('url', '')}; file {common.mixed(os.path.join(inp.assets_dir, name))})")
    return "\n".join(lines) + "\n"


def solution_md(inp: common.Inputs, brand: dict, toks: dict) -> str:
    sol = inp.solution_info()
    bt = toks.get("branding") or {}
    slot = brand_slot_for(sol, brand)
    lines = [f"Solution of this reel: {sol['type']}" + (f" ({sol['name']})" if sol.get("name") else "") + (f", {sol['url']}" if sol.get("url") else "") + "."]
    if sol["type"] == "none":
        lines.append("(no 02-expansion/solution.json: the reel counts as not FlashFX)")
    lines += ["", "Branding (tweaks.md \"Branding (FlashFX account)\", BUILD_SPEC.md 2.7), applied by the pipeline, so write exactly this:",
              f"- The ask scene (the CTA) always has the dm-card with avatar {common.BRAND_PREFIX}{bt.get('cta', {}).get('dm_avatar', 'mark/avatar-dark.png')}, sender {bt.get('cta', {}).get('dm_sender', 'FlashFX')}, and the end-card with lockup {common.brand_default(brand, 'lockup', 'light')} (lockup_w at least {bt.get('lockup_min_width', 300)}). Write them; the pipeline adds them when you forget.",
              f"- The brand slot (the headline's kicker_mark, a logo-tile's image): write \"{common.BRAND_SLOT_TOKEN}\" and the pipeline puts "
              + ("the FlashFX bolt there (the solution is FlashFX)." if sol["type"] == "flashfx" else (f"the tool's logo there ({slot})." if slot else "a neutral accent dot there (no FlashFX asset outside the CTA: the solution is not FlashFX, and the research has no logo of the tool).")),
              ("- FlashFX logos (brand/mark/..., brand/lockup/...) may appear in body beats too: the solution is FlashFX. Light surfaces take gradient or black versions; ink surfaces gradient or white." if sol["type"] == "flashfx"
               else "- No FlashFX logo anywhere but the CTA: the pipeline removes one and the validator rejects it."),
              "- Logos are image files placed as they are (object-fit contain, aspect ratio locked); never retype, redraw, recolor or tilt a logo; hero-3d never shows a logo."]
    return "\n".join(lines) + "\n"


def scenes_md(plan: dict) -> str:
    lines = [f"09a-animations/plan.json: {len(plan['scenes'])} scenes. Instance ids are what the cards refer to.", ""]
    for s in plan["scenes"]:
        lines.append(f"### {s['id']} {s['beat']} ({s['beat_type']}) {s['start_ms']} to {s['end_ms']} ms")
        for c in s["components"]:
            texts = {k: v for k, v in c["props"].items() if (k in common.TITLE_PROPS or k in common.BODY_PROPS or k in ("lines_json", "items_json")) and v not in ("", None, [])}
            lines.append(f"- {c['id']}: {c['component']} ({c.get('role')}) at {c['start_ms']} ms; text props: {json.dumps(texts, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def chunks_md(chunks: list[dict]) -> str:
    lines = ["The baseline caption chunks (from words.json: a break at a sentence end, a clause end, a pause of 150 ms or more, the 4-word limit and the 620 px line width). Keep them, merge or split them: the words and their order never change.", ""]
    for i, ch in enumerate(chunks):
        lines.append(f"{i}. [{ch['scene']}] " + " ".join(("*" + w["word"] + "*") if w.get("emphasis") else w["word"] for w in ch["words"]) + f"  ({ch['start_ms']} ms)")
    return "\n".join(lines) + "\n"


def transitions_md(plan: dict, toks: dict) -> str:
    tr = toks.get("transitions") or {}
    lines = [f"The scenes in order (from 09a and 09b). Scene change rule of the style: {tr.get('scene_change')} (an animated exit of the leaving scene, then the next scene's elements enter); default {tr.get('default')}; allowed types: {', '.join(tr.get('allowed', []))}; "
             f"durations fixed by the style: fade-blur {tr.get('fade_blur_frames')} frames, fall {tr.get('fall_frames')} frames (tilting {tr.get('fall_tilt_deg')} degrees), push {tr.get('push_out_frames')} frames out plus {tr.get('push_gap_frames')} empty frames, cut 0.", ""]
    for s in plan["scenes"]:
        hero = plan_validate.scene_hero(s)
        lines.append(f"- {s['id']} {s['beat']} ({s['beat_type']}), {(s['end_ms'] - s['start_ms']) / 1000:.2f} s, hero {hero['component'] if hero else 'none'}, {len(s['components'])} components" + (", set piece" if s.get("set_piece") else ""))
    return "\n".join(lines) + "\n"


def baseline_chunks(inp: common.Inputs, plan_a: dict, toks: dict) -> list[dict]:
    tl = common.Timeline(inp.words)
    skip = {s["beat"] for s in plan_a["scenes"] if s.get("beat_type") in ("hook", "ask")}
    body = [w for w in tl.words if w.get("beat") not in skip]
    terms = {b["id"]: list(b.get("emphasis", [])) for b in inp.script.get("beats", [])}
    lim = (toks.get("limits") or {}).get("caption") or {}
    max_words = int((lim.get("words_per_chunk") or [1, 4])[1])
    max_em = int((lim.get("emphasis_per_chunk") or [1, 3])[1])
    max_w = float((toks.get("zones") or {}).get("caption", {}).get("max_width", 620))
    chunks = captions.chunk_words(body, terms, max_words=max_words, max_emphasis=max_em, max_width=max_w, width_fn=lambda ws: common.caption_chunk_width(ws, toks))
    scene_of = {s["beat"]: s["id"] for s in plan_a["scenes"]}
    for ch in chunks:
        ch["scene"] = scene_of.get(ch["scene"], ch["scene"])
    return chunks


def run_digest(args) -> int:
    inp = common.Inputs(args.run_dir)
    if not inp.script or not inp.words:
        print(json.dumps({"ok": False, "error": "07-script/script.json or 08-voiceover/words.json is missing"}))
        return 1
    toks = common.tokens()
    cat = common.catalog()
    brand = common.brand_json()
    os.makedirs(args.out, exist_ok=True)
    out = {}
    if args.which == "animations":
        out["timeline"] = timeline_md(inp)
        out["catalog"] = catalog_md(cat)
        out["golden"] = golden_md(os.path.join(common.REPO, str(common.cfg(inp.config, "paths.golden", "golden")), "test-idea"))
        out["assets"] = assets_md(inp)
        out["solution"] = solution_md(inp, brand, toks)
    else:
        plan_a_path = os.path.join(args.run_dir, "09a-animations", "plan.json")
        if not os.path.isfile(plan_a_path):
            print(json.dumps({"ok": False, "error": "09a-animations/plan.json is missing"}))
            return 1
        plan_a = common.load_json(plan_a_path)
        out["timeline"] = timeline_md(inp)
        out["scenes"] = scenes_md(plan_a)
        if args.which == "text":
            out["chunks"] = chunks_md(baseline_chunks(inp, plan_a, toks))
        else:
            plan_b_path = os.path.join(args.run_dir, "09b-text", "plan.json")
            merged = plan_merge.merge(plan_a, common.load_json(plan_b_path) if os.path.isfile(plan_b_path) else None, None, toks)
            out["transitions"] = transitions_md(merged, toks)
            out["golden"] = golden_md(os.path.join(common.REPO, str(common.cfg(inp.config, "paths.golden", "golden")), "test-idea"))
    for name, text in out.items():
        common.write_text(os.path.join(args.out, name + ".md"), common.undash(text))
    print(json.dumps({"ok": True, "files": sorted(out), "solution": inp.solution_info(), "idea_id": inp.idea_id}))
    return 0


# ------------------------------------------------------------------------------------------------ branding

def brand_slot_for(sol: dict, brand: dict) -> str | None:
    """What the brand slots show: the FlashFX bolt when the solution is FlashFX, the tool's logo from the research
    assets when there is one, else None (the component's neutral icon)."""
    if sol.get("type") == "flashfx":
        return common.brand_default(brand, "mark", "light") or common.BRAND_PREFIX + "mark/mark-gradient.png"
    if sol.get("logo"):
        return str(sol["logo"])
    return None


def apply_branding(plan: dict, sol: dict, brand: dict, toks: dict, script: dict, tl: common.Timeline, notes: list[str]) -> None:
    bt = toks.get("branding") or {}
    cta_bt = bt.get("cta") or {}
    flashfx = sol.get("type") == "flashfx"
    slot = brand_slot_for(sol, brand)
    avatar = common.BRAND_PREFIX + str(cta_bt.get("dm_avatar", "mark/avatar-dark.png"))
    lockup = common.brand_default(brand, "lockup", "light") or (common.BRAND_PREFIX + "lockup/" + str(cta_bt.get("lockup_on_light", "lockup-gradient-on-light.png")))
    keyword = str((script.get("ask") or {}).get("keyword") or script.get("hook", {}).get("keyword") or "LINK").upper()
    # the brand slot token and the FlashFX assets outside the CTA
    ask = next((s for s in plan["scenes"] if s.get("beat_type") == "ask"), None)
    for s in plan["scenes"]:
        for c in s["components"]:
            for k, v in list(c["props"].items()):
                if v == common.BRAND_SLOT_TOKEN:
                    c["props"][k] = slot or ""
                    if not slot:
                        notes.append(f"{c['id']}: the brand slot shows the neutral icon (no logo for a {sol.get('type')} solution)")
                elif isinstance(v, str) and v.startswith(common.BRAND_PREFIX) and not flashfx and (not ask or s["id"] != ask["id"]):
                    c["props"][k] = ""
                    notes.append(f"{c['id']}: removed the FlashFX asset {v} outside the CTA (the solution is {sol.get('type')})")
    if not ask:
        return
    comps = ask["components"]
    ec = next((c for c in comps if c["component"] == "end-card"), None)
    dm = next((c for c in comps if c["component"] == "dm-card"), None)
    if not ec:
        ec = {"id": f"{ask['id']}-end-card-{len(comps) + 1}", "component": "end-card", "start_ms": ask["start_ms"], "end_ms": ask["end_ms"], "role": "cta",
              "props": {"verb": "Comment", "keyword": keyword, "line1": "and I send it to you", "line2": "", "lockup_w": 300, "lockup_y": 1146}}
        comps.insert(0, ec)
        notes.append("the CTA had no end-card: added")
    ec["props"].setdefault("keyword", keyword)
    ec["props"]["lockup"] = lockup
    if common._num(ec["props"], "lockup_w", 360) < float(bt.get("lockup_min_width", 300)):
        ec["props"]["lockup_w"] = float(bt.get("lockup_min_width", 300))
    if not dm:
        at = ask["start_ms"]
        try:
            at = tl.word_ms(ask["beat"], keyword)
        except common.PlanError:
            pass
        dm = {"id": f"{ask['id']}-dm-card-{len(comps) + 1}", "component": "dm-card", "start_ms": at, "end_ms": ask["end_ms"], "role": "notification",
              "props": {"sender": str(cta_bt.get("dm_sender", "FlashFX")), "message": f"Comment {keyword} and I send it to you", "time_label": "", "app_label": "Instagram",
                        "x": 110, "y": 1266, "w": 740, "enter": "drop"}}  # ends above the safe bottom (1440) now that the captions sit at 1332 (M14)
        comps.append(dm)
        notes.append("the CTA had no dm-card: added, landing on the keyword")
    dm["props"]["avatar"] = avatar
    dm["props"]["sender"] = str(cta_bt.get("dm_sender", "FlashFX"))
    if common._num(dm["props"], "avatar_size", 120) < 112:
        dm["props"]["avatar_size"] = 120
    for c in (ec, dm):
        c["assets"] = [v for v in c["props"].values() if isinstance(v, str) and (v.startswith(common.BRAND_PREFIX) or v.startswith(common.RESEARCH_PREFIX))]
        c["honesty_label"] = None
    plan["branding"] = {"cta_scene": ask["id"], "dm_avatar": avatar, "lockup": lockup, "brand_slot": slot, "flashfx_allowed_outside_cta": flashfx}


# ------------------------------------------------------------------------------------------------ 9a animations

def coerce_props(comp: dict, props: dict, errors: list[str], iid: str) -> dict:
    """The props with the declared types: numbers as numbers, JSON strings of *_json props parsed, unknown keys kept
    for the validator to name."""
    decl = {p["id"]: p for p in comp.get("props", [])}
    out = {}
    for k, v in (props or {}).items():
        d = decl.get(k)
        if d and d.get("type") == "number":
            try:
                v = float(v)
                v = int(v) if float(v).is_integer() else v
            except (TypeError, ValueError):
                errors.append(f"{iid}: prop {k} must be a number, got {v!r}")
        elif d and d.get("type") == "boolean":
            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")
        elif k.endswith("_json") and isinstance(v, str) and v.strip().startswith(("[", "{")):
            try:
                v = json.loads(v)
            except ValueError:
                pass
        elif d and d.get("type") in ("string", "enum") and not isinstance(v, str) and v is not None:
            v = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)
        out[k] = v
    return out


def resolve_at(at: str, scene_start: int, scene_end: int, beat: str, tl: common.Timeline, lead_ms: int, errors: list[str], iid: str) -> int:
    at = (at or "scene").strip()
    if at in ("", "scene", "start"):
        return scene_start
    if at == "breath":
        if not tl.breath:
            errors.append(f"{iid}: at breath, but words.json has no breath window")
            return scene_start
        return max(scene_start, int(tl.breath["start_ms"]) - lead_ms)
    m = re.match(r"^word:(.+)$", at)
    if m:
        w = tl.find_word(beat, m.group(1).strip())
        if not w:
            errors.append(f"{iid}: at word:{m.group(1).strip()}, but that word is not spoken in beat {beat} (the words: {' '.join(x['word'] for x in tl.beat_words(beat))})")
            return scene_start
        return int(w["start_ms"])
    m = re.match(r"^ms:(-?\d+)$", at)
    if m:
        # an offset snaps to the nearest word boundary of the beat (BUILD_SPEC.md S9: starts snap to words)
        target = min(max(scene_start, scene_start + int(m.group(1))), scene_end - 100)
        bounds = {scene_start} | {int(w["start_ms"]) for w in tl.beat_words(beat)} | {int(w["end_ms"]) for w in tl.beat_words(beat)}
        return min(bounds, key=lambda b: abs(b - target))
    errors.append(f"{iid}: at must be scene, breath, word:<word> or ms:<offset>, got {at!r}")
    return scene_start


def compose_animations(answer: dict, inp: common.Inputs, toks: dict, cat: dict, brand: dict) -> tuple[dict, list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    tl = common.Timeline(inp.words)
    by_id = common.catalog_by_id(cat)
    script = inp.script
    beats = {b["id"]: b for b in script.get("beats", [])}
    lead = int(common.cfg(inp.config, "visual.breath_set_piece_lead_ms", 60))
    sol = inp.solution_info()
    scenes_in = answer.get("scenes") or []
    got_beats = [s.get("beat") for s in scenes_in]
    want_beats = [b["id"] for b in script.get("beats", [])]
    if got_beats != want_beats:
        errors.append(f"scenes must follow the script's beats one by one: {', '.join(want_beats)} (got {', '.join(str(b) for b in got_beats)})")
    scenes = []
    for n, sc in enumerate(scenes_in, start=1):
        beat = str(sc.get("beat", ""))
        if beat not in beats or beat not in tl.beats:
            continue
        sid = f"s{n}"
        st, en = tl.scene_span(beat)
        btype = beats[beat].get("type")
        comps = []
        for k, c in enumerate(sc.get("components") or [], start=1):
            cid = str(c.get("component", ""))
            comp = by_id.get(cid)
            iid = f"{sid}-{cid or 'component'}-{k}"
            if not comp:
                errors.append(f"{iid}: unknown component {cid!r}: use the catalog ids")
                continue
            props = coerce_props(comp, c.get("props") or {}, errors, iid)
            for bad in ("exit", "exit_at", "clip_start"):
                if bad in props:
                    props.pop(bad)
                    notes.append(f"{iid}: {bad} is the transitions pass's job, dropped")
            start = resolve_at(str(c.get("at", "scene")), st, en, beat, tl, lead, errors, iid)
            for pk, word in (c.get("word_props") or {}).items():
                w = tl.find_word(beat, str(word))
                if not w:
                    errors.append(f"{iid}: word_props {pk} names {word!r}, not spoken in beat {beat}")
                    continue
                props[pk] = round(max(0.0, (int(w["start_ms"]) - start) / 1000), 3)
            if cid == "headline":
                if not props.get("lines_json"):
                    errors.append(f"{iid}: the headline needs lines_json (2 to 3 lines of the hook's display line, the serif phrase between asterisks)")
                if not props.get("words_json"):
                    props["words_json"] = [{"w": w["word"], "t": round(max(0.0, (int(w["start_ms"]) - start) / 1000), 3)} for w in tl.beat_words(beat)]
                props.setdefault("kicker_at", 0.05)
            if cid in ("hero-3d", "icon-3d"):
                props.pop("clip_start", None)  # the compiler sets it from the clip's start
            role = c.get("role") if c.get("role") in ROLES else ("hero" if k == 1 else "support")
            honesty = props.get("honesty") if props.get("honesty") in ("mock", "sourced") else None
            comps.append({"id": iid, "component": cid, "start_ms": int(start), "end_ms": int(en), "props": props, "z": comp.get("z", 2), "role": role,
                          "honesty_label": honesty, "at": str(c.get("at", "scene") or "scene"),
                          "land_ms": int(start) + common.frames_ms(common.enter_frames(cid, props)),
                          "assets": [v for v in props.values() if isinstance(v, str) and (v.startswith(common.BRAND_PREFIX) or v.startswith(common.RESEARCH_PREFIX))]})
        hits = []
        terms = sc.get("emphasis") or [{"word": t, "effect": "accent-box"} for t in beats[beat].get("emphasis", [])]
        for h in terms:
            term = str(h.get("word", "") if isinstance(h, dict) else h)
            first = term.split()[0] if term.split() else ""
            w = tl.find_word(beat, first) if first else None
            if w:
                hits.append({"word": term, "ms": int(w["start_ms"]), "effect": str((h.get("effect") if isinstance(h, dict) else None) or "accent-box")})
        scene_h = sc.get("honesty") if sc.get("honesty") in ("mock", "sourced") else next((c["honesty_label"] for c in comps if c["honesty_label"]), None)
        hook_sp = False
        if btype == "hook" and tl.breath:
            b0, b1 = int(tl.breath["start_ms"]), int(tl.breath["end_ms"])
            hook_sp = any(b0 <= c["start_ms"] <= b1 - 100 or b0 <= c["land_ms"] <= b1 for c in comps)
        scenes.append({"id": sid, "beat": beat, "beat_type": btype, "start_ms": int(st), "end_ms": int(en),
                       "set_piece": bool(sc.get("set_piece", False)) or hook_sp, "hook_set_piece": hook_sp, "honesty_label": scene_h, "emphasis_hits": hits, "components": comps})
    hook2 = None
    h2 = answer.get("hook2") or {}
    if script.get("hook2") and h2.get("lines"):
        hook2 = {"kicker": str(h2.get("kicker", "")), "lines": [str(x) for x in h2["lines"]][:3], "set_piece": bool(h2.get("set_piece", True))}
    elif script.get("hook2"):
        disp = str(script["hook2"].get("display", "")).split()
        if disp:
            cut = max(1, len(disp) // 2)
            hook2 = {"kicker": "", "lines": [" ".join(disp[:cut]), "*" + " ".join(disp[cut:]) + "*"], "set_piece": True}
            notes.append("hook 2's headline lines were not given: split the display line in two")
    plan = {"pass": "animations", "plan_version": 1, "style": toks.get("style", "paper-cards"), "idea_id": inp.idea_id, "source": "09a-animations", "fps": common.FPS,
            "duration_ms": tl.duration_ms, "voice": "08-voiceover/vo.wav", "solution": sol, "tracker": {"enabled": bool((toks.get("tracker") or {}).get("enabled", False))},
            "branding": {"cta_scene": "", "dm_avatar": "", "lockup": "", "brand_slot": None, "flashfx_allowed_outside_cta": sol.get("type") == "flashfx"},
            "scenes": scenes, "hook2": hook2, "wishlist": [w for w in (answer.get("wishlist") or []) if isinstance(w, dict) and w.get("name")],
            "notes": common.undash(str(answer.get("notes", "")))[:1500]}
    if scenes:
        apply_branding(plan, sol, brand, toks, script, tl, notes)
    if plan.get("hook2") is None:
        plan.pop("hook2", None)
    return plan, errors, notes


# ------------------------------------------------------------------------------------------------ 9b text

def compose_text(answer: dict, inp: common.Inputs, plan_a: dict, toks: dict, cat: dict) -> tuple[dict, list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    tl = common.Timeline(inp.words)
    by_id = common.catalog_by_id(cat)
    lim = (toks.get("limits") or {}).get("caption") or {}
    max_words = int((lim.get("words_per_chunk") or [1, 4])[1])
    max_em = int((lim.get("emphasis_per_chunk") or [1, 3])[1])
    max_w = float((toks.get("zones") or {}).get("caption", {}).get("max_width", 620))
    skip = {s["beat"] for s in plan_a["scenes"] if s.get("beat_type") in ("hook", "ask")}
    body = [w for w in tl.words if w.get("beat") not in skip]
    scene_of = {s["beat"]: s["id"] for s in plan_a["scenes"]}
    # the chunks: the model's word groups against the spoken words, in order
    groups = answer.get("chunks") or []
    flat = [str(w) for g in groups for w in (g.get("words") or [])]
    want = [w["word"] for w in body]
    chunks: list[dict] = []
    if not groups:
        chunks = baseline_chunks(inp, plan_a, toks)
        notes.append("no chunks in the answer: the baseline chunks are used")
    elif [common.norm(w) for w in flat] != [common.norm(w) for w in want]:
        i = next((i for i, (a, b) in enumerate(zip(flat, want)) if common.norm(a) != common.norm(b)), min(len(flat), len(want)))
        exp = want[i] if i < len(want) else "(end)"
        got = flat[i] if i < len(flat) else "(end)"
        errors.append(f"the chunks must contain every spoken body word in order (beats {', '.join(b for b in tl.order if b not in skip)}): {len(flat)} words given, {len(want)} spoken; first difference at word {i + 1}: expected \"{exp}\", got \"{got}\"")
    else:
        pos = 0
        for gi, g in enumerate(groups):
            ws = g.get("words") or []
            em_terms = [common.norm(str(e)) for e in (g.get("emphasis") or [])]
            entries = []
            for w in ws:
                src = body[pos]
                entries.append({"word": src["word"], "start_ms": int(src["start_ms"]), "end_ms": int(src["end_ms"]), "emphasis": common.norm(src["word"]) in em_terms})
                pos += 1
            if not ws:
                continue
            if len(ws) > max_words:
                errors.append(f"chunk {gi} has {len(ws)} words; at most {max_words}")
            n_em = sum(1 for e in entries if e["emphasis"])
            if n_em > max_em:
                errors.append(f"chunk {gi} has {n_em} emphasis words; at most {max_em}")
            chunks.append({"scene": scene_of.get(body[pos - 1].get("beat"), ""), "start_ms": entries[0]["start_ms"], "end_ms": entries[-1]["end_ms"], "words": entries})
        # a chunk wider than the caption line is split at word boundaries (the style's line is 620 px)
        split = []
        for ch in chunks:
            cur: list[dict] = []
            for w in ch["words"]:
                if cur and common.caption_chunk_width(cur + [w], toks) > max_w:
                    split.append({"scene": ch["scene"], "start_ms": cur[0]["start_ms"], "end_ms": cur[-1]["end_ms"], "words": cur})
                    cur = []
                cur.append(w)
            if cur:
                split.append({"scene": ch["scene"], "start_ms": cur[0]["start_ms"], "end_ms": cur[-1]["end_ms"], "words": cur})
        if len(split) != len(chunks):
            notes.append(f"{len(split) - len(chunks)} chunks were wider than {max_w:.0f} px and were split")
        chunks = split
        for a, b in zip(chunks, chunks[1:]):
            a["end_ms"] = max(a["end_ms"], b["start_ms"])
        if chunks:
            chunks[-1]["end_ms"] = min(tl.duration_ms, chunks[-1]["end_ms"] + 400)
    # the cards: text overrides on the 9a instances
    overrides = []
    inst = {c["id"]: (s, c) for s in plan_a["scenes"] for c in s["components"]}
    title_max = int(common.cfg(inp.config, "visual.title_max_words", 6))
    for o in answer.get("cards") or []:
        iid = str(o.get("component", ""))
        prop = str(o.get("prop") or "title")
        text = common.undash(str(o.get("text", "")))
        if iid not in inst:
            errors.append(f"card for unknown instance {iid!r} (the instance ids are in the scenes list)")
            continue
        s, c = inst[iid]
        declared = {p["id"] for p in by_id.get(c["component"], {}).get("props", [])}
        if prop not in declared:
            errors.append(f"{iid}: {c['component']} has no prop {prop!r}")
            continue
        if prop not in common.TITLE_PROPS and prop not in common.BODY_PROPS and prop not in ("lines_json", "items_json"):
            errors.append(f"{iid}: {prop} is not a text prop")
            continue
        if prop in common.TITLE_PROPS and len(common.words_of(text)) > title_max:
            errors.append(f"{iid}: {prop} \"{text[:50]}\" has {len(common.words_of(text))} words; a card text holds {title_max} or fewer")
        if "\u2014" in str(o.get("text", "")):
            notes.append(f"{iid}: an em dash in the text was replaced")
        overrides.append({"scene": s["id"], "component": iid, "prop": prop, "text": text})
    labels = []
    for l in answer.get("labels") or []:
        kind = l.get("kind") if l.get("kind") in ("tag", "kicker", "honesty") else "tag"
        if kind == "honesty":
            continue  # derived from the props
        text = common.undash(str(l.get("text", ""))).strip()
        if not text or str(l.get("scene", "")) not in {s["id"] for s in plan_a["scenes"]}:
            continue
        if len(common.words_of(text)) > title_max:
            errors.append(f"label \"{text[:50]}\" has {len(common.words_of(text))} words; {title_max} or fewer")
        labels.append({"scene": str(l.get("scene")), "kind": kind, "text": text})
    plan_b = {"pass": "text", "captions": chunks, "overrides": overrides, "cards": [], "labels": labels, "notes": common.undash(str(answer.get("notes", "")))[:1000]}
    merged = plan_merge.merge(plan_a, plan_b, None, toks)
    plan_b["cards"] = merged.get("cards", [])
    plan_b["labels"] = merged.get("labels", [])
    return plan_b, errors, notes


# ------------------------------------------------------------------------------------------------ 9c transitions

def compose_transitions(answer: dict, plan_a: dict, plan_b: dict | None, toks: dict) -> tuple[dict, list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    tr = toks.get("transitions") or {}
    durations = {"fade-blur": common.frames_ms(float(tr.get("fade_blur_frames", 4))), "fall": common.frames_ms(float(tr.get("fall_frames", 10))),
                 "push": common.frames_ms(float(tr.get("push_out_frames", 6)) + float(tr.get("push_gap_frames", 2))), "cut": 0}
    allowed = list(tr.get("allowed", list(durations)))
    scenes = plan_a["scenes"]
    pairs = [(a["id"], b["id"]) for a, b in zip(scenes, scenes[1:])]
    given = {(str(t.get("from")), str(t.get("to"))): t for t in (answer.get("transitions") or [])}
    out = []
    for a, b in pairs:
        t = given.get((a, b))
        if not t:
            errors.append(f"no transition from {a} to {b}: one per consecutive scene pair")
            continue
        ttype = str(t.get("type", tr.get("default", "fade-blur")))
        if ttype not in allowed:
            errors.append(f"transition {a} to {b}: {ttype} is not an allowed type ({', '.join(allowed)})")
            continue
        out.append({"from": a, "to": b, "type": ttype, "duration_ms": int(durations.get(ttype, 0))})
    for key in given:
        if key not in pairs:
            notes.append(f"transition {key[0]} to {key[1]} does not join consecutive scenes: dropped")
    plan_c = {"pass": "transitions", "transitions": out, "notes": common.undash(str(answer.get("notes", "")))[:1000]}
    return plan_c, errors, notes


def text_plan_errors(run_dir: str) -> list[str]:
    """The text pass's own checks (run_compose "text": the caption part of the validator on 09a merged with 09b) on
    the run's plan files as they are now. A 09b plan written before a fix to those checks fails them here; the
    transitions pass cannot change card texts or captions, so 09c runs the text pass again first (visual.sh)."""
    inp = common.Inputs(run_dir)
    toks = common.tokens()
    plan_a = common.load_json(os.path.join(run_dir, "09a-animations", "plan.json"))
    plan_b = common.load_json(os.path.join(run_dir, "09b-text", "plan.json"))
    ctx = plan_validate.Context(toks=toks, cat=common.catalog(), brand=common.brand_json(), config=inp.config, words=inp.words, script=inp.script, assets=inp.asset_files(), numbers=inp.numbers)
    res = plan_validate.validate(plan_merge.merge(plan_a, plan_b, None, toks), ctx, {"captions"}, skip_schema=True)
    return [common.undash(f"{e['rule']}: {e['message']}") for e in res["errors"]]


def run_check_text(args) -> int:
    for rel in ("09a-animations/plan.json", "09b-text/plan.json"):
        if not os.path.isfile(os.path.join(args.run_dir, rel)):
            print(json.dumps({"ok": False, "errors": [f"{rel} is missing"], "code_error": True}))
            return 1
    errors = text_plan_errors(args.run_dir)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 4 if errors else 0


# ------------------------------------------------------------------------------------------------ the CLI

def summary_of(plan: dict) -> str:
    n_scenes = len(plan.get("scenes", []))
    n_comp = sum(len(s.get("components", [])) for s in plan.get("scenes", []))
    used = sorted({c["component"] for s in plan.get("scenes", []) for c in s.get("components", [])})
    return f"{n_scenes} scenes, {n_comp} component instances, {len(used)} distinct ({', '.join(used)})"


def run_compose(args) -> int:
    inp = common.Inputs(args.run_dir)
    if not inp.script or not inp.words:
        print(json.dumps({"ok": False, "errors": ["07-script/script.json or 08-voiceover/words.json is missing"], "code_error": True}))
        return 1
    toks = common.tokens()
    cat = common.catalog()
    brand = common.brand_json()
    answer = common.load_json(args.answer)
    if not isinstance(answer, dict):
        print(json.dumps({"ok": False, "errors": ["the answer is not a JSON object"]}))
        return 4
    ctx = plan_validate.Context(toks=toks, cat=cat, brand=brand, config=inp.config, words=inp.words, script=inp.script, assets=inp.asset_files(), numbers=inp.numbers)
    if args.cmd == "animations":
        plan, errors, notes = compose_animations(answer, inp, toks, cat, brand)
        if not plan["scenes"] and not errors:
            errors.append("the answer has no scenes")
        res = plan_validate.validate(plan, ctx, {"scenes"}, skip_schema=True) if plan["scenes"] else {"errors": [], "warnings": []}
        errors += [f"{e['rule']}: {e['message']}" for e in res["errors"]]
        out = plan
        extra = {"summary": summary_of(plan), "brand_slot": plan.get("branding", {}).get("brand_slot"), "solution": plan.get("solution", {}).get("type"),
                 "wishlist": plan.get("wishlist", []), "hook_set_piece": any(s.get("hook_set_piece") for s in plan["scenes"])}
    elif args.cmd == "text":
        pa = os.path.join(args.run_dir, "09a-animations", "plan.json")
        if not os.path.isfile(pa):
            print(json.dumps({"ok": False, "errors": ["09a-animations/plan.json is missing"], "code_error": True}))
            return 1
        plan_a = common.load_json(pa)
        plan, errors, notes = compose_text(answer, inp, plan_a, toks, cat)
        merged = plan_merge.merge(plan_a, plan, None, toks)
        res = plan_validate.validate(merged, ctx, {"captions"}, skip_schema=True) if not errors else {"errors": [], "warnings": []}
        errors += [f"{e['rule']}: {e['message']}" for e in res["errors"]]
        out = plan
        extra = {"summary": f"{len(plan['captions'])} caption chunks, {len(plan['overrides'])} card texts changed, {len(plan['labels'])} labels",
                 "chunks": len(plan["captions"]), "overrides": len(plan["overrides"])}
    else:
        pa = os.path.join(args.run_dir, "09a-animations", "plan.json")
        pb = os.path.join(args.run_dir, "09b-text", "plan.json")
        if not os.path.isfile(pa) or not os.path.isfile(pb):
            print(json.dumps({"ok": False, "errors": ["09a-animations/plan.json or 09b-text/plan.json is missing"], "code_error": True}))
            return 1
        plan_a = common.load_json(pa)
        plan_b = common.load_json(pb)
        plan, errors, notes = compose_transitions(answer, plan_a, plan_b, toks)
        merged = plan_merge.merge(plan_a, plan_b, plan, toks)
        res = plan_validate.validate(merged, ctx) if not errors else {"errors": [], "warnings": []}
        errors += [f"{e['rule']}: {e['message']}" for e in res["errors"]]
        out = plan
        types = [t["type"] for t in plan["transitions"]]
        extra = {"summary": f"{len(types)} transitions (" + ", ".join(f"{types.count(k)} {k}" for k in sorted(set(types))) + ")", "merged": args.merged}
        if not errors and args.merged:
            common.write_json(args.merged, merged)
    result = {"ok": not errors, "errors": [common.undash(e) for e in errors], "warnings": [f"{w['rule']}: {w['message']}" for w in res.get("warnings", [])],
              "notes": notes, **extra}
    if errors:
        common.write_json(args.out.replace(".json", ".candidate.json"), out)
        print(json.dumps(result, ensure_ascii=False))
        return 4
    common.write_json(args.out, out)
    print(json.dumps(result, ensure_ascii=False))
    return 0
