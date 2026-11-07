

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
        if [kinetic._text(w) for w in lay.get("words", [])] != [w["word"] for w in words]:
            rep.err("caption_modes", f"{label}: the layout's words are not the caption's words in order")
        for p in kinetic.check_layout(lay, toks):
            rep.err("caption_modes", f"{label}: {p}")
        if ch.get("anchor") is not None and lay.get("anchor") != ch.get("anchor"):
            rep.err("caption_modes", f"{label}: the anchor of the entry ({ch.get('anchor')}) is not the layout's ({lay.get('anchor')})")
        box = lay.get("box") or {}
        for s in plan.get("scenes", []):
            if int(s["start_ms"]) >= end or int(s["end_ms"]) <= start:
                continue
            for c in s.get("components", []):
                if c["component"] in ("paper-canvas", "camera-move", "exit-move", "mascot") or int(c["start_ms"]) >= end or int(c["end_ms"]) <= start:
                    continue
                fp = common.footprint(c["component"], c.get("props", {}), toks)
                if not fp or not box:
                    continue
                ox = min(fp["x"] + fp["w"], box["x"] + box["w"]) - max(fp["x"], box["x"])
                oy = min(fp["y"] + fp["h"], box["y"] + box["h"]) - max(fp["y"], box["y"])
                if ox > 8 and oy > 8:
                    rep.err("caption_modes", f"{label} covers {c['id']} ({c['component']}): a group fills the hero zone, so it needs a beat whose hero zone shows no graphic (E3)")
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
