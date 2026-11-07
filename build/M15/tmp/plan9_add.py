

# ------------------------------------------------------------------------------------------------ M15: caption modes (E3, E4)

def importance_by_scene(inp: common.Inputs, plan_a: dict) -> dict:
    """script.json's importance of each beat, by scene id (a script from before M15 has none: normal)."""
    imp = {b["id"]: (b.get("importance") or "normal") for b in (inp.script or {}).get("beats", [])}
    return {s["id"]: imp.get(s["beat"], "normal") for s in plan_a["scenes"]}


def scene_state(plan: dict, scene: dict, toks: dict) -> dict:
    """What the scene's hero zone holds: its text (characters, from the instances) and the graphics that block a group."""
    texts = []
    for c in scene["components"]:
        for it in common.text_items(c["component"], c.get("props", {}), toks):
            texts.append((c["id"], it["chars"]))
    zone = kinetic.group_zone(toks)
    blockers = []
    for b in common.visible_boxes(plan, int(scene["start_ms"]), int(scene["end_ms"]), toks):
        ox = min(b["x"] + b["w"], zone["x1"]) - max(b["x"], zone["x0"])
        oy = min(b["y"] + b["h"], zone["y1"]) - max(b["y"], zone["y0"])
        if ox > 8 and oy > 8:
            blockers.append(b["id"])
    return {"text_chars": sum(n for _i, n in texts), "text_instances": sorted({i for i, _n in texts}), "blockers": blockers}


def captions_guidance(inp: common.Inputs, plan_a: dict, toks: dict) -> str:
    """The caption-mode part of the 9b digest: per scene its importance, whether text or a graphic sits in the hero zone,
    and the mode the pipeline would pick on its own (the director may override it where the rules allow)."""
    imp = importance_by_scene(inp, plan_a)
    g = kinetic.grammar(toks)
    lo, hi = (g.get("group_words") or [2, 6])[:2]
    lines = ["", "## Caption modes per scene (Motion and energy rules E3 and E4)", "",
             f"Word mode: one word at a time on its spoken time, the emphasis words larger in the serif italic on the accent box, every word rising a little. "
             f"Group mode: {lo} to {hi} words fill the hero zone as kinetic typography (the pipeline lays the words out: you only choose the words and the anchor, "
             f"the most important word); it needs a hero zone with no text and no graphic under it, and it is the choice where the voice says something important "
             f"or the scene has no graphic to show. Whenever any other text is on screen the captions are in word mode. At most "
             f"{((toks.get('motion') or {}).get('grammar') or {}).get('text_budget', {}).get('max_chars_on_screen', 100)} characters of card, chip and code text on screen at once.", ""]
    for s in plan_a["scenes"]:
        if s.get("beat_type") in ("hook", "ask"):
            continue
        st = scene_state(plan_a, s, toks)
        auto = "word"
        if st["text_chars"] == 0 and (imp[s["id"]] != "normal" or not st["blockers"]):
            auto = "group"
        lines.append(f"- {s['id']} ({s['beat']}, {s['beat_type']}): importance {imp[s['id']]}; text on screen {st['text_chars']} characters"
                     + (f" ({', '.join(st['text_instances'])})" if st["text_instances"] else "")
                     + (f"; graphics in the hero zone: {', '.join(st['blockers'])}" if st["blockers"] else "; hero zone free")
                     + f"; the pipeline's own choice: {auto} mode")
    return "\n".join(lines) + "\n"


def _anchor_index(words: list[dict], hint) -> int | None:
    if isinstance(hint, int) and 0 <= hint < len(words):
        return hint
    if isinstance(hint, str) and hint.strip():
        want = common.norm(hint)
        for i, w in enumerate(words):
            if common.norm(w["word"]) == want:
                return i
    return None


def finalize_captions(chunks: list[dict], inp: common.Inputs, plan_a: dict, base: dict, toks: dict) -> tuple[list[dict], list[str], list[str]]:
    """Mode, layout and motion of every caption entry (E3, E4). `chunks` are the word runs of the director's answer (or the
    baseline), optionally with "_mode" (word | group) and "_anchor" hints; `base` is the plan with the card texts as they
    are now. Without a hint the choice rule decides: word mode under any text, group mode where the hero zone holds no
    text and the beat is important or has no graphic there, word mode otherwise. Groups of the pipeline's own choosing are
    re-cut from the beat's words (group_runs); every group is laid out by kinetic.py, which splits one that does not fit."""
    errors: list[str] = []
    notes: list[str] = []
    imp = importance_by_scene(inp, plan_a)
    text_wins = common.text_windows(base, toks)
    zone = kinetic.group_zone(toks)
    scenes = {s["id"]: s for s in plan_a["scenes"]}
    max_w = float((toks.get("zones") or {}).get("caption", {}).get("max_width", 620))

    def text_over(a: int, b: int) -> str | None:
        for (s0, s1, inst) in text_wins:
            if a < s1 and s0 < b:
                return inst
        return None

    def blockers(a: int, b: int) -> list[dict]:
        out = []
        for bx in common.visible_boxes(base, a, b, toks):
            ox = min(bx["x"] + bx["w"], zone["x1"]) - max(bx["x"], zone["x0"])
            oy = min(bx["y"] + bx["h"], zone["y1"]) - max(bx["y"], zone["y0"])
            if ox > 8 and oy > 8:
                out.append(bx)
        return out

    # 1. a mode for every entry
    decided: list[dict] = []
    for i, ch in enumerate(chunks):
        hint = ch.pop("_mode", None)
        anchor_hint = ch.pop("_anchor", None)
        a, b = int(ch["start_ms"]), int(ch["end_ms"])
        label = "chunk " + str(i) + " (" + " ".join(w["word"] for w in ch["words"]) + ")"
        over = text_over(a, b)
        scene_imp = imp.get(ch.get("scene", ""), "normal")
        if hint == "group":
            if over:
                errors.append(f"{label} is a group caption but {over} shows text then: captions are in word mode whenever any other text is on screen (E4); use word mode for it, or take the text off the card")
                mode, origin = "word", "forced"
            elif len(ch["words"]) < 2 or len(ch["words"]) > 6:
                errors.append(f"{label} is a group caption of {len(ch['words'])} words; a group holds 2 to 6")
                mode, origin = "word", "forced"
            else:
                mode, origin = "group", "director"
        elif hint == "word":
            mode, origin = "word", "director"
        elif over:
            mode, origin = "word", "auto"
        else:
            free = not blockers(a, b)
            mode, origin = ("group", "auto") if (scene_imp != "normal" or free) else ("word", "auto")
        decided.append({"entry": ch, "mode": mode, "origin": origin, "anchor": anchor_hint, "importance": scene_imp})

    # 2. the groups: a director's group as written, the pipeline's own groups re-cut from the beat's words
    out: list[dict] = []
    group_index = 0
    i = 0
    while i < len(decided):
        d = decided[i]
        if d["mode"] != "group":
            out.append({**d["entry"], "mode": "word", "importance": d["importance"]})
            i += 1
            continue
        j = i + 1
        if d["origin"] == "auto":
            while j < len(decided) and decided[j]["mode"] == "group" and decided[j]["origin"] == "auto" and decided[j]["entry"].get("scene") == d["entry"].get("scene"):
                j += 1
            words = [w for k in range(i, j) for w in decided[k]["entry"]["words"]]
            runs = kinetic.group_runs(words, max_words=6, min_words=2)
        else:
            words = list(d["entry"]["words"])
            runs = [words]
        for run in runs:
            a, b = int(run[0]["start_ms"]), int(run[-1]["end_ms"])
            if len(run) < 2:
                out.append({"scene": d["entry"].get("scene", ""), "start_ms": a, "end_ms": b, "words": run, "mode": "word", "importance": d["importance"]})
                continue
            avoid = [{k: bx[k] for k in ("x", "y", "w", "h")} for bx in blockers(a, b)]
            anchor = _anchor_index(run, d["anchor"]) if d["origin"] == "director" else None
            if anchor is None:
                anchor = kinetic.choose_anchor(run, toks)
            lays = kinetic.layout_groups(run, toks, anchors=anchor, index=group_index, avoid=avoid)
            if any(not lay.get("ok") for lay in lays):
                if d["origin"] == "director":
                    errors.append(f"the group \"{' '.join(w['word'] for w in run)}\" cannot be laid out in the hero zone: {next(l['reason'] for l in lays if not l.get('ok'))}")
                else:
                    notes.append(f"the words \"{' '.join(w['word'] for w in run)}\" fit no group layout beside the graphics: word mode")
                for k in range(0, len(run), 4):
                    part = run[k:k + 4]
                    out.append({"scene": d["entry"].get("scene", ""), "start_ms": int(part[0]["start_ms"]), "end_ms": int(part[-1]["end_ms"]), "words": part, "mode": "word", "importance": d["importance"]})
                continue
            for lay in lays:
                lo, hi = lay["span"]
                part = run[lo:hi + 1]
                lay_clean = {k: v for k, v in lay.items() if k not in ("ok", "span")}
                out.append({"scene": d["entry"].get("scene", ""), "start_ms": int(part[0]["start_ms"]), "end_ms": int(part[-1]["end_ms"]), "words": part, "mode": "group",
                            "importance": d["importance"], "anchor": lay["anchor"], "layout": lay_clean, "motion": lay["motion"]})
                group_index += 1
        i = j

    # 3. times and motion
    out.sort(key=lambda e: int(e["start_ms"]))
    for k, (a, b) in enumerate(zip(out, out[1:])):
        gap = int(b["start_ms"]) - int(a["end_ms"])
        a["end_ms"] = int(b["start_ms"]) if gap <= 1500 else int(a["end_ms"]) + 600
    if out:
        out[-1]["end_ms"] = min(common_duration(inp), int(out[-1]["end_ms"]) + 400)
    for k, e in enumerate(out):
        if e["mode"] == "word":
            e["motion"] = kinetic.word_motion(k, toks)
    n_group = sum(1 for e in out if e["mode"] == "group")
    if n_group:
        notes.append(f"{n_group} caption groups, {len(out) - n_group} word runs")
    return out, notes, errors


def common_duration(inp: common.Inputs) -> int:
    tl = common.Timeline(inp.words)
    return int(tl.duration_ms)
