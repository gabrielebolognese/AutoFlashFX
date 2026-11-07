import re
p = "pipeline/lib/review/mechanical.py"
s = open(p, encoding="utf-8").read()


def rep(old, new, count=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, count)


# 1. the JS: the full length of every text leaf (the text field is cut at 60 characters)
rep('text: (el.textContent || "").trim().slice(0, 60), x: tb.left,', 'text: (el.textContent || "").trim().slice(0, 60), n: (el.textContent || "").trim().length, x: tb.left,')

# 2. docstring: the M15 rules
rep('''  branding      the CTA has the FlashFX lockup (300 px or wider)''', '''  caption_mode  (M15, E3 and E4) a caption group (group mode) is judged in the group caption zone, not the caption band; no
                group word is on screen while any other text is (captions are in word mode under text); no caption
                word or group stands still (sampled twice inside its life: it must have moved)              [text]
  text_budget   (M15, E4) at most 100 characters of non-caption text visible at any check time (the CTA's text is the
                ask and is left out)                                                                         [text]
  text_size     (M15, E4) no graphic text under the caption size: the sizes the library bakes in are listed as
                warnings (review.text_size_baked: error makes them issues)                                   [animation]
  branding      the CTA has the FlashFX lockup (300 px or wider)''')

# 3. thresholds
rep('''    cap_min_share = float(ctx.c("review.caption_min_size_share", 0.9))''', '''    cap_min_share = float(ctx.c("review.caption_min_size_share", 0.9))
    grammar = ((toks.get("motion") or {}).get("grammar") or {})
    gz = ((grammar.get("captions") or {}).get("group_zone")) or {"x0": margin_x, "y0": safe_top, "x1": rc.CANVAS_W - margin_x, "y1": float((z.get("hero") or {}).get("bottom_max", 1176))}
    budget = int((grammar.get("text_budget") or {}).get("max_chars_on_screen", 100))
    min_text_px = float((grammar.get("text_budget") or {}).get("min_text_px", cap_font))
    baked_error = str(ctx.c("review.text_size_baked", "warn")) == "error"
    min_move_px = float(ctx.c("review.caption_min_move_px", 0.25))''')

# 4. the static sampling for caption hosts: after the main evaluate of a caption host
rep('''            if host.get("captions"):
                for e in res.get("events", []):
                    if e.get("type") in ("caption_word", "caption_chunk", "caption_overflow"):
                        caption_events.append({**e, "abs_ms": host["start_ms"] + float(e.get("t", 0)) * 1000.0})''', '''            if host.get("captions"):
                for e in res.get("events", []):
                    if e.get("type") in ("caption_word", "caption_chunk", "caption_overflow", "caption_group"):
                        caption_events.append({**e, "abs_ms": host["start_ms"] + float(e.get("t", 0)) * 1000.0})
                # E3 and E1: nothing of the captions stands still: every word and group is read twice inside its life
                pairs = caption_motion_pairs(host)
                if pairs:
                    extra = sorted({t for a, b, _lbl in pairs for t in (a, b)})
                    res2 = h.page.evaluate(REVIEW_JS, {"id": comp["id"], "times": extra})
                    by_t = {r["t"]: r for r in res2.get("rows", [])}
                    for a, b, lbl in pairs:
                        ra, rb = by_t.get(a), by_t.get(b)
                        if not ra or not rb:
                            continue
                        counts["caption_pairs"] = counts.get("caption_pairs", 0) + 1
                        ta = {t["idx"]: t for t in ra["texts"] if t["opacity"] >= VISIBLE}
                        for t2 in rb["texts"]:
                            t1 = ta.get(t2["idx"])
                            if t1 is None or t2["opacity"] < VISIBLE:
                                continue
                            moved = max(abs(t1["x"] - t2["x"]), abs(t1["y"] - t2["y"]), abs(t1["w"] - t2["w"]), abs(t1["h"] - t2["h"]))
                            if moved < min_move_px:
                                still_captions.append({"instance": host["id"], "scene": host["scene"], "text": t2["text"], "ms": int(host["start_ms"] + b * 1000), "label": lbl, "moved_px": round(moved, 3)})''')
rep('''    caption_events: list[dict] = []
    harness_errors: list[str] = []''', '''    caption_events: list[dict] = []
    still_captions: list[dict] = []
    harness_errors: list[str] = []''')

# 5. the zone rule: a group word lives in the group caption zone
rep('''            if tx.get("captions"):
                if not in_band or x0 < cap_x0 - tol or x1 > cap_x1 + tol:''', '''            is_group = "pc-gw" in (tx.get("cls") or "").split()
            if tx.get("captions") and is_group:
                if x0 < gz["x0"] - tol or x1 > gz["x1"] + tol or y0 < gz["y0"] - tol or y1 > gz["y1"] + tol:
                    add(rc.issue("text", "zone", f"caption group word {where} is outside the group caption zone (x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f}; the zone is x {gz['x0']:.0f}..{gz['x1']:.0f}, y {gz['y0']:.0f}..{gz['y1']:.0f})", tx["scene"], tx["instance"], T), ("zone",) + k)
            elif tx.get("captions"):
                if not in_band or x0 < cap_x0 - tol or x1 > cap_x1 + tol:''')
rep('''            if tx.get("captions") and eff < cap_font * cap_min_share - 0.5:
                add(rc.issue("text", "caption_scaled", f"caption {where} was scaled to {eff:.0f} px (the chunk is wider than the {cap_x1 - cap_x0:.0f} px line): split it", tx["scene"], tx["instance"], T), ("caption_scaled",) + k)''', '''            if tx.get("captions") and eff < cap_font * cap_min_share - 0.5:
                add(rc.issue("text", "caption_scaled", f"caption {where} was scaled to {eff:.0f} px (the word is wider than the {cap_x1 - cap_x0:.0f} px line, or a group word is under the caption size {cap_font:.0f} px): fix the caption plan", tx["scene"], tx["instance"], T), ("caption_scaled",) + k)''')

# 6. E4 at every check time: the budget, the mode under text, the sizes
rep('''        # overlaps between different elements (the arriving and leaving ones left out)''', '''        # E4 and E3 (M15): the characters of non-caption text on screen, group captions under text, graphic text sizes
        shown = [t for t in texts if not t.get("captions") and not t.get("ignore") and t["scene"] != cta_id]
        chars = sum(int(t.get("n") or len(t["text"])) for t in shown)
        if chars > budget:
            add(rc.issue("text", "text_budget", f"{chars} characters of non-caption text are on screen at {rc.fmt_ms(T)} ({label}); at most {budget} (E4: graphics first, cut the text a graphic can carry)", "", "", T), ("text_budget",))
        counts["max_chars_on_screen"] = max(counts.get("max_chars_on_screen", 0), chars)
        group_words = [t for t in texts if t.get("captions") and "pc-gw" in (t.get("cls") or "").split() and not t.get("transient")]
        other_text = [t for t in shown if not t.get("transient")]
        if group_words and other_text:
            add(rc.issue("text", "caption_mode", f"a caption group (\\"{group_words[0]['text']}\\") is on screen with the text of {other_text[0]['instance']} (\\"{other_text[0]['text'][:30]}\\") at {rc.fmt_ms(T)}: captions are in word mode whenever any other text is on screen (E4)", group_words[0]["scene"], group_words[0]["instance"], T), ("caption_mode", group_words[0]["instance"], other_text[0]["instance"]))
        for t in shown:
            if t.get("transient"):
                continue
            eff_px = float(t["size"]) * float(t.get("scale") or 1)
            if eff_px < min_text_px - 0.5:
                key = (t["component"], first_family(t["font"]), round(float(t["size"])))
                small_text.setdefault(key, [0, t["instance"], t["text"][:30]])[0] += 1
        # overlaps between different elements (the arriving and leaving ones left out)''')
rep('''    n_checked_texts = 0
    for T in check_ms:''', '''    n_checked_texts = 0
    small_text: dict = {}
    for T in check_ms:''')

# 7. emphasis inside a caption group
rep('''            cands = [e for e in em_events if rc.vcommon.norm(str(e.get("text", ""))) == word]
            best = min(cands, key=lambda e: abs(e["abs_ms"] - ms)) if cands else None''', '''            cands = [e for e in em_events if rc.vcommon.norm(str(e.get("text", ""))) == word]
            best = min(cands, key=lambda e: abs(e["abs_ms"] - ms)) if cands else None
            grp = [e for e in caption_events if e.get("type") == "caption_word" and e.get("mode") == "group" and rc.vcommon.norm(str(e.get("text", ""))) == word]
            if grp and (best is None or abs(best["abs_ms"] - ms) > em_tol):
                gbest = min(grp, key=lambda e: abs(e["abs_ms"] - ms))
                gerr = gbest["abs_ms"] - ms
                emphasis["results"].append({"word": hit.get("word"), "ms": ms, "box_ms": round(gbest["abs_ms"]), "error_ms": round(gerr), "on_screen": True, "ok": abs(gerr) <= em_tol, "note": "a word of a caption group (the anchor and the fonts carry it, no accent box)"})
                if abs(gerr) <= em_tol:
                    emphasis["ok"] += 1
                else:
                    add(rc.issue("text", "emphasis_timing", f"the emphasis on \\"{hit.get('word')}\\" lands {gerr:+.0f} ms from its word at {rc.fmt_ms(ms)} (caption group)", s["id"], "captions", ms))
                continue''')

# 8. after the emphasis block: the static captions and the baked small texts
rep('''    # ---------------------------------------------------------------- branding
    branding = {''', '''    # ---------------------------------------------------------------- M15: static captions, graphic text sizes
    seen_static: set = set()
    for sc in still_captions:
        key = (sc["instance"], sc["text"], sc["label"])
        if key in seen_static:
            continue
        seen_static.add(key)
        add(rc.issue("text", "caption_static", f"the caption \\"{sc['text']}\\" ({sc['instance']}) does not move between two samples of its life ({sc['moved_px']} px at {rc.fmt_ms(sc['ms'])}): every caption word or group rises or turns while it is on screen (E3, E1)", sc["scene"], sc["instance"], sc["ms"]), ("caption_static", sc["instance"], sc["text"]))
    warnings: list[str] = []
    for (comp_id, fam, px), (n_seen, inst, sample) in sorted(small_text.items()):
        msg = f"{comp_id} text \\"{sample}\\" in {fam} is {px} px, under the caption size {min_text_px:.0f} px (E4: {n_seen} samples)"
        if baked_error:
            add(rc.issue("animation", "text_size", f"{msg}; a graphic that needs smaller text needs less text", "", inst), ("text_size", comp_id, px))
        else:
            warnings.append(msg)

    # ---------------------------------------------------------------- branding
    branding = {''')
rep('''    report = {"written_by": "12-review", "pass": not issues, "issues": issues, "counts": counts,''', '''    report = {"written_by": "12-review", "pass": not issues, "issues": issues, "warnings": warnings, "counts": counts,''')

# 9. the helper that picks the motion sample pairs of a caption host
rep('''def first_family(font: str) -> str:''', '''def caption_motion_pairs(host: dict) -> list[tuple[float, float, str]]:
    """Two sample times (seconds local to the caption host) inside each word's or group's life, far enough apart for a rising
    or turning caption to have moved: [(t1, t2, label)]. A life shorter than 0.25 s is not sampled."""
    props = host.get("props") or {}
    out: list[tuple[float, float, str]] = []
    raw = props.get("words_json")
    words = raw if isinstance(raw, list) else (json_loads(raw) if isinstance(raw, str) else [])
    for k, w in enumerate(words or []):
        try:
            t, e = float(w["t"]), float(w.get("end", float(w["t"]) + 0.3))
        except (KeyError, TypeError, ValueError):
            continue
        life = e - t
        if life >= 0.25:
            out.append((round(t + 0.35 * life, 4), round(t + 0.7 * life, 4), f"word {k}"))
    raw = props.get("groups_json")
    groups = raw if isinstance(raw, list) else (json_loads(raw) if isinstance(raw, str) else [])
    for k, g in enumerate(groups or []):
        try:
            t, e = float(g["start"]), float(g["end"])
        except (KeyError, TypeError, ValueError):
            continue
        life = e - t
        if life >= 0.5:
            out.append((round(t + 0.4 * life, 4), round(t + 0.8 * life, 4), f"group {k}"))
    return out


def json_loads(text: str):
    import json
    try:
        return json.loads(text)
    except ValueError:
        return []


def first_family(font: str) -> str:''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched")
