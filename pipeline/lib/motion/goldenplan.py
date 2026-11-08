"""pipeline/lib/motion/goldenplan.py: the golden reel's plan (BUILD_SPEC.md M9), planned by hand for the test idea from
the frozen script.json and words.json: which component tells each beat, where it sits, which spoken word it lands
on. The word times come from words.json, so the plan is regenerated when the voice changes; the design (DESIGN
below) is the hand-made part. It follows the branding rules of tweaks.md: the CTA scene has the FlashFX DM card and
the end card's lockup; the solution is an external tool with no logo asset, so the brand slot (the hook's kicker
mark) shows the neutral accent dot and no FlashFX asset appears outside the CTA.

  python pipeline/lib/motion golden-plan --script 07-script/script.json --words 08-voiceover/words.json --out plan.json
"""
from __future__ import annotations

import re

from motion import captions, common

BREATH_SET_PIECE_LEAD_MS = 60   # the 3D object starts this long before the breath so its landing sits inside it


def norm(word: str) -> str:
    return re.sub(r"[^a-z0-9#'.@/-]", "", word.lower()).strip(".")


class Timeline:
    def __init__(self, words: dict):
        self.words = words["words"]
        self.beats = {b["id"]: b for b in words["beats"]}
        self.order = [b["id"] for b in words["beats"]]
        self.breath = words.get("breath") or {}
        self.duration_ms = int(words["duration_ms"])

    def beat_words(self, beat: str) -> list[dict]:
        return [w for w in self.words if w.get("beat") == beat]

    def word_ms(self, beat: str, token: str, which: str = "start") -> int:
        t = norm(token)
        for w in self.beat_words(beat):
            if norm(w["word"]).startswith(t):
                return int(w["start_ms" if which == "start" else "end_ms"])
        raise KeyError(f"word {token!r} not in beat {beat}")

    def scene_span(self, beat: str) -> tuple[int, int]:
        i = self.order.index(beat)
        start = int(self.beats[beat]["start_ms"])
        end = int(self.beats[self.order[i + 1]]["start_ms"]) if i + 1 < len(self.order) else self.duration_ms
        return start, end


# The hand-made design of the test idea's reel: per beat, the components, their props and the word they land on
# (at_word) or their start in ms from the scene start (at_ms). Texts quote the script; nothing is claimed that the
# script does not say. Positions are px at 1080x1920 inside the hero zone of tokens.json (top 180 to 363, bottom
# above 1176; the end card and the DM card follow their own measured spots).
DESIGN = [
    {"beat": "b1", "beat_type": "hook", "hook_set_piece": True, "honesty": "mock", "components": [
        {"component": "headline", "role": "hero", "from_scene_start": True, "props": {
            "kicker": "CLAUDE CODE SITES", "kicker_mark": "", "lines_json": ["Why your Claude Code", "cards all look", "*identical.*"],
            "kicker_at": 0.05, "x": 90, "w": 900, "align": "center", "hold": "lively"}, "words_from_beat": True},
        {"component": "mock-site-card", "role": "support", "from_scene_start": True, "props": {
            "x": 90, "y": 700, "w": 900, "h": 470, "title": "", "headline": "Same look", "cta": "Go", "tone": "ink", "cta_at": 0.5, "scroll_px_s": 220, "honesty": "mock", "hold": "lively", "enter": "rise"}},
        {"component": "hero-3d", "role": "set-piece", "at": "breath", "props": {
            "x": 620, "y": 620, "w": 330, "h": 330, "object": "card", "spin": 40, "tilt": 18, "enter_at": 0.0, "enter_frames": 12, "label": ""}},
    ]},
    {"beat": "b2", "beat_type": "stake", "honesty": "mock", "components": [
        {"component": "mock-site-card", "role": "hero", "props": {"x": 90, "y": 420, "w": 900, "h": 760, "title": "client-site.com", "headline": "Same look", "cta": "Get started",
                                                                  "tone": "warm", "cta_at": 0.8, "scroll_px_s": 60, "honesty": "mock", "hold": "lively", "enter": "rise"}},
        {"component": "pop", "role": "support", "from_scene_start": True, "props": {"kind": "badge", "icon": "star", "size": 130, "x": 830, "y": 340}},
        {"component": "cursor", "role": "support", "at_word": "ship", "props": {"points_json": [{"x": 820, "y": 1100, "at": 0}, {"x": 250, "y": 905, "at": 1.6, "click": True}, {"x": 700, "y": 700, "at": 2.6}], "hold": "lively"}},
        {"component": "dark-chip", "role": "label", "at_word": "instantly", "props": {"x": 440, "y": 1120, "text": "same look, every site", "accent_word": "every site", "icon": "dot"}},
    ]},
    {"beat": "b3", "beat_type": "comparison", "honesty": "sourced", "components": [
        {"component": "screenshot-zoom", "role": "hero", "props": {"x": 90, "y": 380, "w": 900, "h": 780, "image": "research/03-skill-md.png", "honesty": "sourced", "hold": "lively", "enter": "rise", "zoom_to": 0.85},
         "timed": {"focus_json": [{"word": "skill", "plus_ms": -200, "x": 0.33, "y": 0.30, "w": 0.4, "h": 0.04}, {"word": "rounded", "plus_ms": -250, "x": 0.34, "y": 0.215, "w": 0.6, "h": 0.1},
                                  {"word": "radius", "plus_ms": -300, "x": 0.33, "y": 0.575, "w": 0.6, "h": 0.1}, {"word": "shadow", "plus_ms": -300, "x": 0.34, "y": 0.66, "w": 0.6, "h": 0.1}]}},
        {"component": "pop", "role": "support", "from_scene_start": True, "props": {"kind": "badge", "icon": "bolt", "size": 130, "x": 830, "y": 340}},
        {"component": "dark-chip", "role": "label", "at_word": "shadow", "props": {"x": 440, "y": 1120, "text": "rgba(0,0,0,.1)", "accent_word": ".1", "icon": "file"}},
    ]},
    {"beat": "b4", "beat_type": "mechanism", "honesty": "sourced", "components": [
        {"component": "video-card", "role": "hero", "props": {"x": 90, "y": 420, "w": 900, "h": 760, "video": "research/04-blog.mp4", "title": "claude.com/blog", "kind": "window", "honesty": "sourced", "hold": "lively", "enter": "rise"}},
        {"component": "handwritten-callout", "role": "support", "at_word": "calls", "props": {"x": 560, "y": 1030, "text": "Anthropic's|own words", "arrow": "up-left", "arrow_len": 140}},
    ]},
    {"beat": "b5", "beat_type": "comparison", "honesty": "mock", "components": [
        {"component": "mock-site-card", "role": "hero", "props": {"x": 90, "y": 600, "w": 900, "h": 340, "title": "", "headline": "Terracotta", "cta": "Go", "tone": "warm", "cta_at": 0.7, "scroll_px_s": 140, "honesty": "mock", "hold": "lively", "enter": "rise"}},
        {"component": "swatch-row", "role": "support", "props": {"x": 90, "y": 965, "w": 900, "h": 120, "gap": 20, "honesty": "none", "hold": "lively"},
         "timed": {"colors_json": [{"word": "terracotta", "plus_ms": -100, "color": "#D97757"}, {"word": "cream", "plus_ms": -100, "color": "#FAF5EC"}]}},
        {"component": "strike-through", "role": "support", "at_word": "flagged", "strike_word": "flagged", "props": {"x": 200, "y": 1100, "text": "#D97757 on cream", "chip": True, "style": "line", "replacement": "AI look"}},
    ]},
    {"beat": "b6", "beat_type": "number", "components": [
        {"component": "video-card", "role": "hero", "props": {"x": 90, "y": 860, "w": 900, "h": 300, "video": "research/01-repo.mp4", "kind": "frame", "honesty": "none", "hold": "lively", "enter": "rise", "video_start": 1.2}},
        {"component": "pop", "role": "support", "props": {"kind": "badge", "icon": "star", "size": 150, "x": 800, "y": 330}},
    ]},
    {"beat": "b7", "beat_type": "mechanism", "honesty": "sourced", "components": [
        {"component": "video-card", "role": "hero", "props": {"x": 90, "y": 540, "w": 900, "h": 400, "video": "research/01-repo.mp4", "kind": "frame", "honesty": "sourced", "hold": "lively", "enter": "rise", "video_start": 1.0}},
        {"component": "swatch-row", "role": "support", "props": {"x": 90, "y": 970, "w": 900, "h": 170, "gap": 14, "honesty": "none", "hold": "lively"},
         "timed": {"colors_json": [{"word": "four", "plus_ms": -100, "color": "#DC6532"}, {"word": "four", "plus_ms": 500, "color": "#1C110F"}, {"word": "six", "plus_ms": -100, "color": "#F5EEE3"},
                                   {"word": "hex", "plus_ms": 150, "color": "#289C5C"}, {"word": "colors,", "plus_ms": 0, "color": "#C9623C"}]}},
    ]},
    {"beat": "b8", "beat_type": "proof", "honesty": "sourced", "components": [
        {"component": "screenshot-zoom", "role": "hero", "props": {"x": 90, "y": 380, "w": 900, "h": 760, "image": "research/02-plugin-page.png", "honesty": "sourced", "hold": "lively", "enter": "rise", "zoom_to": 0.8},
         "timed": {"focus_json": [{"word": "Anthropic", "plus_ms": 0, "x": 0.27, "y": 0.165, "w": 0.5, "h": 0.05}, {"word": "verified", "plus_ms": -100, "x": 0.27, "y": 0.215, "w": 0.5, "h": 0.035},
                                  {"word": "Over", "plus_ms": 0, "x": 0.76, "y": 0.2, "w": 0.22, "h": 0.07}, {"word": "installs", "plus_ms": -500, "x": 0.76, "y": 0.15, "w": 0.22, "h": 0.12},
                                  {"word": "November", "plus_ms": -100, "x": 0.27, "y": 0.165, "w": 0.5, "h": 0.05}]}},
        {"component": "stat-number", "role": "support", "at_word": "Over", "props": {"x": 120, "y": 1190, "value": 1134112, "unit": "installs", "icon": "download", "container": "pill", "honesty": "sourced"}},
    ]},
    {"beat": "b9", "beat_type": "step", "honesty": "sourced", "components": [
        {"component": "terminal-card", "role": "support", "from_scene_start": True, "props": {"x": 90, "y": 380, "w": 900, "title": "Claude Code", "mode": "type", "chars_per_frame": 2, "start_delay_frames": 8, "prompt": "", "hold": "lively",
                                                                  "lines_json": [{"text": "/plugin install frontend-design@claude-plugins-official", "color": "accent"}, {"text": "Pick a scope: user or project", "color": "muted"}]}},
        {"component": "video-card", "role": "hero", "from_scene_start": True, "props": {"x": 90, "y": 700, "w": 900, "h": 470, "video": "research/05-install-docs.mp4", "kind": "frame", "honesty": "sourced", "hold": "lively", "enter": "rise", "video_start": 0.8}},
    ]},
    {"beat": "b10", "beat_type": "payoff", "components": [
        {"component": "video-card", "role": "hero", "props": {"x": 90, "y": 840, "w": 900, "h": 340, "video": "research/02-plugin-page.mp4", "kind": "frame", "honesty": "none", "hold": "lively", "enter": "rise", "video_start": 0.6}},
        {"component": "check-badge", "role": "support", "props": {"mode": "badge", "x": 800, "y": 330, "size": 160}},
    ]},
    {"beat": "b11", "beat_type": "ask", "cta": True, "components": [
        {"component": "end-card", "role": "cta", "props": {"verb": "Comment", "keyword": "TELLS", "line1": "and I send you the checklist", "line2": "ditch the identical cards",
                                                           "lockup": "brand/lockup/lockup-gradient-on-light.png", "lockup_w": 300, "lockup_y": 1146,
                                                           "confetti_count": 130, "confetti_at": 1.1, "confetti_seconds": 2.4, "hold": "lively"}},
        {"component": "dm-card", "role": "notification", "at_word": "TELLS", "props": {"avatar": "brand/mark/avatar-dark.png", "sender": "FlashFX", "message": "Comment TELLS and I send the checklist",
                                                                                      "time_label": "", "app_label": "Instagram", "x": 110, "y": 1266, "w": 740, "enter": "drop"}},
    ]},
]

# the durations are the style's frames (tokens.json transitions): fade-blur 4, fall 10, push 6 out plus 2 empty (M10 aligned the push);
# E8: no type more than 3 times in the reel
TRANSITIONS = [("s1", "s2", "fade-blur", 133), ("s2", "s3", "fall", 333), ("s3", "s4", "push", 267),
               ("s4", "s5", "fade-blur", 133), ("s5", "s6", "fall", 333), ("s6", "s7", "cut", 0), ("s7", "s8", "push", 267),
               ("s8", "s9", "fade-blur", 133), ("s9", "s10", "push", 267), ("s10", "s11", "fall", 333)]


def build_plan(script: dict, words: dict, idea_id: str = "") -> dict:
    tl = Timeline(words)
    beats_by_id = {b["id"]: b for b in script["beats"]}
    scenes = []
    cards = []
    labels = []
    emphasis_terms = {}
    for n, d in enumerate(DESIGN, start=1):
        beat = d["beat"]
        sid = f"s{n}"
        start, end = tl.scene_span(beat)
        if d.get("hook_set_piece"):
            start = 0
        comps = []
        for k, c in enumerate(d["components"], start=1):
            cid = f"{sid}-{c['component']}-{k}"
            props = dict(c["props"])
            at_ms = start
            if c.get("at") == "breath" and tl.breath:
                at_ms = max(start, int(tl.breath["start_ms"]) - BREATH_SET_PIECE_LEAD_MS)
            elif c.get("at_word"):
                at_ms = tl.word_ms(beat, c["at_word"])
            elif c.get("at_ms") is not None:
                at_ms = start + int(c["at_ms"])
            if c.get("words_from_beat"):
                props["words_json"] = [{"w": w["word"], "t": round((int(w["start_ms"]) - at_ms) / 1000, 3)} for w in tl.beat_words(beat)]
            if c.get("strike_word"):
                props["strike_at"] = round((tl.word_ms(beat, c["strike_word"]) - at_ms) / 1000, 3)
            if c.get("ticks_word"):
                props["ticks_at"] = round((tl.word_ms(beat, c["ticks_word"]) - at_ms) / 1000, 3)
            if c.get("from_scene_start"):
                at_ms = start
            for prop, items in (c.get("timed") or {}).items():
                timed_items = []
                for it in items:
                    it = dict(it)
                    ms = tl.word_ms(beat, it.pop("word")) + int(it.pop("plus_ms", 0))
                    it["at"] = round(max(0.0, (ms - at_ms) / 1000), 3)
                    timed_items.append(it)
                props[prop] = timed_items
            comps.append({"id": cid, "component": c["component"], "start_ms": int(at_ms), "end_ms": int(end), "props": props, "role": c.get("role", "support"),
                          "honesty_label": props.get("honesty") if props.get("honesty") in ("mock", "sourced") else None,
                          "assets": [v for v in props.values() if isinstance(v, str) and (v.startswith("brand/") or v.startswith("research/"))]})
            text = props.get("title") or props.get("text") or props.get("kicker") or props.get("keyword")
            if text and c.get("role") in ("hero", "label", "cta"):
                cards.append({"scene": sid, "component": cid, "text": text, "zone": "hero" if c.get("role") in ("hero", "cta") else "label"})
            if props.get("honesty") in ("mock", "sourced"):
                labels.append({"scene": sid, "text": "real" if props["honesty"] == "sourced" else "illustrative", "kind": "honesty"})
        sb = beats_by_id[beat]
        hits = []
        for term in sb.get("emphasis", []):
            first = str(term).split()[0] if str(term).split() else ""
            try:
                hits.append({"word": term, "ms": tl.word_ms(beat, first), "effect": "accent-box"})
            except KeyError:
                pass
        emphasis_terms[beat] = list(sb.get("emphasis", []))
        scenes.append({"id": sid, "beat": beat, "beat_type": d["beat_type"], "start_ms": int(start), "end_ms": int(end),
                       "set_piece": bool(d.get("hook_set_piece")), "hook_set_piece": bool(d.get("hook_set_piece")),
                       "honesty_label": d.get("honesty"), "emphasis_hits": hits, "components": comps})
    labels.append({"scene": "s1", "text": "CLAUDE CODE SITES", "kind": "kicker"})
    body_words = [w for w in tl.words if w.get("beat") not in ("b1", "b11")]
    toks = common.tokens()
    try:
        from visual.common import caption_chunk_width  # M10: chunks never wider than the caption line
        max_w = float(toks["zones"]["caption"]["max_width"])
        chunks = captions.chunk_words(body_words, emphasis_terms, max_width=max_w, width_fn=lambda ws: caption_chunk_width(ws, toks))
    except Exception:
        chunks = captions.chunk_words(body_words, emphasis_terms)
    scene_of_beat = {s["beat"]: s["id"] for s in scenes}
    for ch in chunks:
        ch["scene"] = scene_of_beat.get(ch["scene"], ch["scene"])
    # M15 (E3, E4): word mode in normal talk and under any text, groups where the hero zone holds no text (the same
    # choice rule and layout engine the text pass uses)
    from visual import plan9

    class _Inp:  # the two inputs finalize_captions reads
        pass
    inp = _Inp()
    inp.script, inp.words = script, words
    chunks, _notes, _errors = plan9.finalize_captions(chunks, inp, {"scenes": scenes}, {"scenes": scenes}, toks)
    if _errors:
        raise RuntimeError("golden plan captions: " + "; ".join(_errors))
    plan = {
        "plan_version": 1, "style": "paper-cards", "idea_id": idea_id or script.get("idea_id", ""), "source": "golden-plan (pipeline/lib/motion/goldenplan.py)",
        "fps": 30, "duration_ms": tl.duration_ms, "voice": "08-voiceover/vo.wav",
        "solution": {"type": "external", "name": "frontend-design, the Claude Code plugin", "url": "https://claude.com/plugins/frontend-design", "logo": None},
        "tracker": {"enabled": False},
        "branding": {"cta_scene": [s["id"] for s in scenes if s["beat_type"] == "ask"][0], "dm_avatar": "brand/mark/avatar-dark.png",
                     "lockup": "brand/lockup/lockup-gradient-on-light.png", "brand_slot": None, "flashfx_allowed_outside_cta": False},
        "scenes": scenes, "captions": chunks, "cards": cards, "labels": labels,
        "transitions": [{"from": a, "to": b, "type": t, "duration_ms": ms} for a, b, t, ms in TRANSITIONS],
        "notes": ("Planned by hand for the test idea (goldenplan.py DESIGN): the hook headline builds word by word on the spoken words and the 3D card lands in "
                  "the breath; every body beat has one hero component and one element landing on its key word; the screenshots are real research assets "
                  "(labelled real); the CTA follows tweaks.md Branding: the FlashFX DM card lands on the word TELLS and the lockup sits under the mascot row. "
                  "Scene changes: fade-blur by default, a fall or a push where the beat turns (open question 3: B)."),
    }
    return plan


def run(args) -> int:
    script = common.load_json(args.script)
    words = common.load_json(args.words)
    plan = build_plan(script, words, getattr(args, "idea_id", "") or "")
    common.write_json(args.out, plan)
    print(f"golden plan: {len(plan['scenes'])} scenes, {sum(len(s['components']) for s in plan['scenes'])} components, {len(plan['captions'])} caption chunks, {plan['duration_ms']} ms -> {args.out}")
    return 0
