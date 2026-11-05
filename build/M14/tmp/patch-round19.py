"""Round 19: short-lived elements are judged once. The transients rule of round 17 left an element whose whole life is
shorter than the main animation window (a chip on a scene's last word: 630 ms) unjudged, so the M11 test's planted chip
above the safe top went uncaught. Such an element is judged at the last sample of its life that is not an exit (the
check times gain one 50 ms before its end, where the zoom and the rotation are nearly settled), for its geometry (the
zones, the rail, the canvas, the overlaps, the brand rules), not for its size (mid-zoom)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/review/common.py", [
    ('''    settle = int(ctx.c("review.settle_ms", 600))
    em_lead = int(ctx.c("review.emphasis_settle_ms", 150))
    grammar = ((ctx.toks.get("motion") or {}).get("grammar") or {}) if isinstance(getattr(ctx, "toks", None), dict) else {}
    main_frames = int((grammar.get("main") or {}).get("frames", 18)) + int((grammar.get("main") or {}).get("rotate_lag_frames", 3))
    main_ms = int(round(main_frames * 1000.0 / 30.0))
    times: dict = {}''',
     '''    settle = int(ctx.c("review.settle_ms", 600))
    em_lead = int(ctx.c("review.emphasis_settle_ms", 150))
    main_ms = main_window_ms(ctx)
    times: dict = {}'''),
    ('''        for c in s.get("components", []):
            land = c.get("land_ms")
            if land is None:
                continue
            last = min(b, int(c.get("end_ms", b)))
            settled = max(int(land), int(c.get("start_ms", land)) + main_ms) + 100
            for t in (settled, int(land) + 100):
                if t < last:
                    add(t, f"{c['id']} landed")
                    break''',
     '''        for c in s.get("components", []):
            land = c.get("land_ms")
            if land is None:
                continue
            start = int(c.get("start_ms", land))
            last = min(b, int(c.get("end_ms", b)))
            settled = max(int(land), start + main_ms) + 100
            if settled < last:
                add(settled, f"{c['id']} landed")
            else:
                # a life shorter than the main animation window: the element is judged once, at the last sample of its
                # life that is not an exit (mechanical.py), so the samples sit as late as they can
                if int(land) + 100 < last:
                    add(int(land) + 100, f"{c['id']} landed")
                if last - 50 > start + 100:
                    add(last - 50, f"{c['id']} last")'''),
    ('''# ------------------------------------------------------------------------------------------------ colors''',
     '''def main_window_ms(ctx: Ctx) -> int:
    """The combined main animation's window in ms (E2: the grammar's main frames plus the rotation's lag, 21 frames):
    an element is arriving until then (pc-motion.js data-pcm-main), tokens.json motion.grammar.main."""
    toks = getattr(ctx, "toks", None)
    grammar = ((toks.get("motion") or {}).get("grammar") or {}) if isinstance(toks, dict) else {}
    main = grammar.get("main") or {}
    return int(round((int(main.get("frames", 18)) + int(main.get("rotate_lag_frames", 3))) * 1000.0 / 30.0))


def short_lived(ctx: Ctx, start_ms: int, end_ms: int) -> bool:
    """True when the element's life holds no settled sample (its landed sample would fall at or after its end)."""
    return int(start_ms) + main_window_ms(ctx) + 100 >= int(end_ms)


# ------------------------------------------------------------------------------------------------ colors'''),
])

patch("pipeline/lib/review/mechanical.py", [
    ('''    # ---------------------------------------------------------------- the rules, at the check times
    seen_issue: set = set()''',
     '''    # a short-lived instance (its life shorter than the main animation window: a chip on a last word) never settles,
    # so it is judged once, at the last check time of its life that is not an exit, for its geometry
    for host in hosts:
        if host.get("no_timeline") or host["component"] == "paper-canvas" or not rc.short_lived(ctx, host["start_ms"], host["end_ms"]):
            continue
        cands = [T for T in check_ms if any(t["instance"] == host["id"] and t.get("transient") != "exit" for t in per_time[T]["texts"] + per_time[T]["images"])]
        if cands:
            T_last = max(cands)
            for t in per_time[T_last]["texts"] + per_time[T_last]["images"]:
                if t["instance"] == host["id"] and t.get("transient") != "exit":
                    t["judge_anyway"] = True

    # ---------------------------------------------------------------- the rules, at the check times
    seen_issue: set = set()'''),
    ('''            if tx.get("transient"):
                # arriving or leaving (E1's main animation with E2's zoom and rotation, or the exit): a transient by
                # design, judged at the next sample of its life
                counts["transient"] += 1
                continue''',
     '''            if tx.get("transient") and not tx.get("judge_anyway"):
                # arriving or leaving (E1's main animation with E2's zoom and rotation, or the exit): a transient by
                # design, judged at the next sample of its life (a short-lived instance once, at its last sample)
                counts["transient"] += 1
                continue'''),
    ('''            eff = float(tx["size"]) * float(tx.get("scale") or 1)
            if not tx.get("ignore") and eff < min_font - 0.5:
                add(rc.issue("text", "font_size", f"text {where} is {eff:.0f} px, under the {min_font:.0f} px floor", tx["scene"], tx["instance"], T), ("font_size",) + k)
            if tx.get("captions") and eff < cap_font * cap_min_share - 0.5:
                add(rc.issue("text", "caption_scaled", f"caption {where} was scaled to {eff:.0f} px (the chunk is wider than the {cap_x1 - cap_x0:.0f} px line): split it", tx["scene"], tx["instance"], T), ("caption_scaled",) + k)''',
     '''            eff = float(tx["size"]) * float(tx.get("scale") or 1)
            if tx.get("transient"):
                eff = float(tx["size"])  # a short-lived element judged mid-zoom: its size is the designed one
            if not tx.get("ignore") and eff < min_font - 0.5:
                add(rc.issue("text", "font_size", f"text {where} is {eff:.0f} px, under the {min_font:.0f} px floor", tx["scene"], tx["instance"], T), ("font_size",) + k)
            if tx.get("captions") and eff < cap_font * cap_min_share - 0.5:
                add(rc.issue("text", "caption_scaled", f"caption {where} was scaled to {eff:.0f} px (the chunk is wider than the {cap_x1 - cap_x0:.0f} px line): split it", tx["scene"], tx["instance"], T), ("caption_scaled",) + k)'''),
    ('''        # overlaps between different elements (the arriving and leaving ones left out)
        vis = [t for t in texts if not t.get("ignore") and not t.get("transient")]''',
     '''        # overlaps between different elements (the arriving and leaving ones left out)
        vis = [t for t in texts if not t.get("ignore") and (not t.get("transient") or t.get("judge_anyway"))]'''),
    ('''        for im in images:
            counts["images"] += 1
            if im.get("transient"):
                counts["transient"] += 1
                continue''',
     '''        for im in images:
            counts["images"] += 1
            if im.get("transient") and not im.get("judge_anyway"):
                counts["transient"] += 1
                continue'''),
    ('''            if im["src"].startswith("assets/brand/") and not im.get("transient"):
                logo_rows.append((T, im))''',
     '''            if im["src"].startswith("assets/brand/") and (not im.get("transient") or im.get("judge_anyway")):
                logo_rows.append((T, im))'''),
])

patch("DECISIONS.md", [
    ('''    its entrance: the 24 px floor stays a rule about the design. test-m14 section 3 checks the three states on the DM
    card.
''',
     '''    its entrance: the 24 px floor stays a rule about the design. test-m14 section 3 checks the three states on the DM
    card. An element whose whole life is shorter than that window (a chip on a scene's last word, 630 ms in the test
    idea) would never be judged, so it is judged once, at the last sample of its life that is not an exit (check_times
    adds one 50 ms before its end, where the zoom and the rotation are nearly settled), for its geometry and with its
    designed size; the M11 test's planted chip above the safe top found this.
'''),
])
print("round 19 done")
