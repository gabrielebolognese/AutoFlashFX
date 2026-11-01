#!/usr/bin/env python
"""build/M11/patch-1.py: the M11 patches to earlier files, applied once (kept as a record, like build/M10/patch-events.py).

1. motion-lib/compositions/caption-line.html: the chunk width is the words' own extent, not the 1080 px block's
   scrollWidth (every chunk was scaled to 60 percent; found by S12's mechanical check).
2. pipeline/lib/review/mechanical.py: ancestor-aware overlaps, the background sampled around the glyphs, one issue
   per element, the display contrast threshold from config.
3. config.json: the sfx and review settings of M11, the timeouts, the visual_director_escalation role.
4. pipeline/lib/state.py: a stage may reopen itself through reopen.txt (the review loop).
5. pipeline/lib/visual.sh and the three director prompts: the {{REVIEW}} notes of the edit review and the escalated
   director after the opus rounds.
6. pipeline/tests/lib.sh: --with-review copies the reference analysis summaries and stills into the sandbox.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(ROOT)


def read(p):
    return open(p, encoding="utf-8").read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def replace_once(p, old, new, label=""):
    s = read(p)
    if old not in s:
        if new in s:
            print(f"{p}: already patched ({label})")
            return
        raise SystemExit(f"{p}: anchor not found ({label}): {old[:80]!r}")
    write(p, s.replace(old, new, 1))
    print(f"{p}: patched ({label})")


# 1. caption-line.html
replace_once("motion-lib/compositions/caption-line.html",
             "        // fit: a chunk wider than max_w scales down (the text plan should have split it; this keeps it inside the zone)\n        var width = div.scrollWidth;",
             "        // fit: a chunk wider than max_w scales down (the text plan should have split it; this keeps it inside the zone).\n"
             "        // The width is the words' own extent (a Range over the chunk's content): the chunk's block spans the whole\n"
             "        // 1080 px line, so its scrollWidth would scale every chunk (found by S12's mechanical check, M11).\n"
             "        var width = 0;\n"
             "        try { var rg = document.createRange(); rg.selectNodeContents(div); width = rg.getBoundingClientRect().width; } catch (e) { width = div.scrollWidth; }",
             "chunk width")

# 2. mechanical.py
p = "pipeline/lib/review/mechanical.py"
s = read(p)
if "data-rv-idx" not in s:
    s = s.replace('''  const rows = [];
  for (const t of args.times) {
    seekTo(t);
    const texts = [], images = [];
    const all = document.querySelectorAll("#stage *");
    for (const el of all) {
      if (el.closest("#paper-root")) continue;''', '''  const rows = [];
  const allOnce = document.querySelectorAll("#stage *");
  let idx = 0;
  for (const el of allOnce) { el.setAttribute("data-rv-idx", String(idx++)); }
  const ancestorsOf = (el) => { const out = []; let node = el.parentElement; while (node && node.id !== "stage" && node !== document.body) { const v = node.getAttribute("data-rv-idx"); if (v !== null) out.push(parseInt(v, 10)); node = node.parentElement; } return out; };
  for (const t of args.times) {
    seekTo(t);
    const texts = [], images = [];
    const all = document.querySelectorAll("#stage *");
    for (const el of all) {
      if (el.closest("#paper-root")) continue;''')
    s = s.replace('''      texts.push({ id: el.id || "", cls: String(el.className || ""), parent_cls: String((el.parentElement && el.parentElement.className) || ""),''',
                  '''      texts.push({ id: el.id || "", cls: String(el.className || ""), parent_cls: String((el.parentElement && el.parentElement.className) || ""), idx: parseInt(el.getAttribute("data-rv-idx") || "-1", 10), anc: ancestorsOf(el),''')
    s = s.replace('''def ring_rgb(img, box: dict, inner: int = 2, outer: int = 7):''', '''def bg_rgb_for_text(img, box: dict, text_rgb, pad: int = 5):
    """The background behind a text: the median of the pixels around and between the glyphs (the box grown by pad),
    the pixels near the text's own color left out (the glyphs and their anti-aliased edges). Falls back to the ring."""
    import numpy as np
    W, H = img.size
    x0, y0 = max(0, int(math.floor(box["x"])) - pad), max(0, int(math.floor(box["y"])) - pad)
    x1, y1 = min(W, int(math.ceil(box["x"] + box["w"])) + pad), min(H, int(math.ceil(box["y"] + box["h"])) + pad)
    if x1 <= x0 or y1 <= y0:
        return None
    arr = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB")).astype(int)
    tr = np.array(text_rgb[:3], dtype=int)
    dist = np.abs(arr - tr).max(axis=2)
    keep = arr[dist >= 90]
    if len(keep) < max(20, 0.12 * arr.shape[0] * arr.shape[1]):
        return ring_rgb(img, box)
    med = np.median(keep, axis=0)
    return (float(med[0]), float(med[1]), float(med[2]))


def ring_rgb(img, box: dict, inner: int = 2, outer: int = 7):''')
    s = s.replace('''                    if shot is not None:
                        tx["bg_rgb"] = ring_rgb(shot, {"x": tx["x"], "y": tx["y"], "w": tx["w"], "h": tx["h"]})''', '''                    if shot is not None:
                        fr, fg, fb, _ = rc.parse_css_color(tx["color"])
                        tx["bg_rgb"] = bg_rgb_for_text(shot, {"x": tx["x"], "y": tx["y"], "w": tx["w"], "h": tx["h"]}, (fr, fg, fb))''')
    s = s.replace('''    def add(iss: dict) -> None:
        key = (iss["kind"], iss.get("instance"), iss.get("text")[:60])
        if key in seen_issue:
            return
        seen_issue.add(key)
        issues.append(iss)''', '''    def add(iss: dict, key=None) -> None:
        key = key or (iss["kind"], iss.get("instance"), iss.get("text")[:60])
        if key in seen_issue:
            return
        seen_issue.add(key)
        issues.append(iss)''')
    s = s.replace('''            where = f"\\"{tx['text']}\\" ({tx['component']} {tx['instance']}, scene {tx['scene']}, {rc.fmt_ms(T)})"''',
                  '''            where = f"\\"{tx['text']}\\" ({tx['component']} {tx['instance']}, scene {tx['scene']}, {rc.fmt_ms(T)})"
            k = (tx["instance"], tx["text"])''')
    a = s.index("            # zones\n")
    b = s.index("        # overlaps between different elements", a)
    seg = s[a:b]
    seg = re.sub(r'add\(rc\.issue\((?P<tag>"[a-z]+"|tag_place\(tx\)), (?P<kind>"[a-z_]+"), (?P<rest>.*?)\)\)\n',
                 lambda m: f'add(rc.issue({m.group("tag")}, {m.group("kind")}, {m.group("rest")}), ({m.group("kind")},) + k)\n', seg)
    s = s[:a] + seg + s[b:]
    s = s.replace('''        vis = [t for t in texts if not t.get("ignore")]
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, b = vis[i], vis[j]
                area = rc.boxes_intersect({"x": a["x"], "y": a["y"], "w": a["w"], "h": a["h"]}, {"x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]}, inset=2.0)
                if area > 0:
                    add(rc.issue("animation", "overlap", f"\\"{a['text']}\\" ({a['instance']}) and \\"{b['text']}\\" ({b['instance']}) overlap at {rc.fmt_ms(T)} ({label})", a["scene"], a["instance"], T))''',
                  '''        vis = [t for t in texts if not t.get("ignore")]
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, b = vis[i], vis[j]
                if a["instance"] == b["instance"] and (a.get("idx") in (b.get("anc") or []) or b.get("idx") in (a.get("anc") or [])):
                    continue  # a word span inside its own line's text (the chip's accent word)
                # the glyphs sit in the middle of the line box: an inset of a sixth of the smaller box keeps adjacent
                # lines of one headline (113 px apart, 122 px line boxes) from counting as an overlap
                inset = max(2.0, 0.17 * min(a["h"], b["h"]))
                area = rc.boxes_intersect({"x": a["x"], "y": a["y"], "w": a["w"], "h": a["h"]}, {"x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]}, inset=inset)
                if area > 0:
                    add(rc.issue("animation", "overlap", f"\\"{a['text']}\\" ({a['instance']}) and \\"{b['text']}\\" ({b['instance']}) overlap at {rc.fmt_ms(T)} ({label})", a["scene"], a["instance"], T),
                        ("overlap", a["instance"], a["text"], b["instance"], b["text"]))''')
    s = s.replace('''    c_min, c_large = float(ctx.c("review.contrast_min", 4.5)), float(ctx.c("review.contrast_large_min", 3.0))''',
                  '''    c_min, c_large = float(ctx.c("review.contrast_min", 4.5)), float(ctx.c("review.contrast_display_min", 2.7))''')
    s = s.replace('''({'the accent family, 3:1 allowed' if display else '4.5:1 needed'})''', '''({f'the accent family, {c_large:g}:1 allowed' if display else f'{c_min:g}:1 needed'})''')
    s = s.replace("""  contrast      text against the pixels around it: 4.5:1, or 3:1 for the style's display colors (the accent family,
                white on an accent box or pill, the success green), WCAG's large-text ratio                  [text]""",
                  """  contrast      text against the pixels around it: 4.5:1, or review.contrast_display_min (2.7) for the style's display
                colors (the accent family on paper, white on an accent box or pill, the success green): the look's
                own kicker and serif phrase measure 2.8 to 3.0 (DECISIONS.md M11)                            [text]""")
    write(p, s)
    print(f"{p}: patched")
    assert "+ k)" in s and s.count("+ k)") >= 6, "the text rules did not get their keys"
else:
    print(f"{p}: already patched")

# 3. config.json
p = "config.json"
s = read(p)
cfg = json.loads(s)
changed = False
if "visual_director_escalation" not in cfg["models"]:
    cfg["models"]["visual_director_escalation"] = {"model": "fable", "effort": "xhigh"}
    changed = True
sfx_add = {"calm_beats": ["stake", "pain-payoff"], "attention_gap_s": 6, "attention_min_start_ms": 2000, "series_gap_ms": 2000, "fade_ms": 30, "tail_guard_ms": 50,
           "voice_window_ms": 600, "voice_floor_under_peak_db": 12, "verify_passes": 3, "recent_reels": 2}
for k, v in sfx_add.items():
    if k not in cfg["sfx"]:
        cfg["sfx"][k] = v
        changed = True
if "review" not in cfg or "min_font_px" not in cfg.get("review", {}):
    rev = cfg.setdefault("review", {})
    rev.update({"settle_ms": 600, "emphasis_settle_ms": 150, "zone_tolerance_px": 4, "caption_band_above_px": 180, "caption_band_below_px": 80, "min_font_px": 24,
                "caption_min_size_share": 0.9, "contrast_min": 4.5, "contrast_display_min": 2.7, "emphasis_tolerance_ms": 80, "avatar_min_px": 112,
                "cadence_tolerance_pct": 20, "palette_delta_e": 5, "palette_min_share_pct": 90, "aac_peak_tolerance_db": 0.5, "wer_max_pct": 5,
                "qa_tools": "Read Glob"})
    changed = True
for k, v in {"sfx_seconds": 1200, "mechanical_seconds": 1800, "style_seconds": 1200, "edit_review_seconds": 1800}.items():
    if k not in cfg["timeouts"]:
        cfg["timeouts"][k] = v
        changed = True
if changed:
    # keep the file's hand layout where it matters: rewrite with 2-space indent (the file is read by json only)
    write(p, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    print("config.json: patched")
else:
    print("config.json: already patched")

# 4. state.py: self reopen
replace_once("pipeline/lib/state.py",
             '''        if key not in state["stages"] or key == stage:
            print(f"state.py: {stage}/reopen.txt names {key!r}, which is not another stage; ignored", file=sys.stderr)
            continue''',
             '''        if key not in state["stages"]:
            print(f"state.py: {stage}/reopen.txt names {key!r}, which is not a stage; ignored", file=sys.stderr)
            continue
        # a stage may name itself (the review loop of M11 reopens 12-review with the steps it routes to): it is
        # marked done first, then pending again for the next round, in the same write''',
             "self reopen")
replace_once("pipeline/lib/state.py",
             '''names 04-angle, the angle stage names 03-gate, M4; the review loop of
M11 will use it for its fix routing). "stage-start" removes a reopen.txt left by an earlier attempt.''',
             '''names 04-angle, the angle stage names 03-gate, M4; the review loop of
M11 names the owner of each issue, every stage after it and itself). "stage-start" removes a reopen.txt left by an earlier attempt.''',
             "doc")

# 5. visual.sh: the REVIEW notes and the escalated director
p = "pipeline/lib/visual.sh"
s = read(p)
if "REVIEW=" not in s:
    s = s.replace('''  local -a ctx=("IDEA=$IDEA_TEXT" "@STYLE=$style_dir/style.md" "@TWEAKS=$style_dir/tweaks.md" "@VOCABULARY=$style_dir/vocabulary.md" "@TOKENS=$tokens" "NOTE=$(stage_note_section)")''',
                  '''  local review_notes
  review_notes="$($REELS_PY "$REELS_PIPELINE/lib/review" feedback --run-dir "$RUN_DIR" --stage "$stage" 2>/dev/null || true)"
  local -a ctx=("IDEA=$IDEA_TEXT" "@STYLE=$style_dir/style.md" "@TWEAKS=$style_dir/tweaks.md" "@VOCABULARY=$style_dir/vocabulary.md" "@TOKENS=$tokens" "NOTE=$(stage_note_section)" "REVIEW=$review_notes")''')
    s = s.replace('''  local tools timeout_s try=1 res rc sid=""
  tools="$(cfg visual.director_tools "Read Glob")"
  timeout_s="$(cfg timeouts.plan_seconds 1800)"
  say INFO "S9: $act for $(json_field "$dres" idea_id "$IDEA_ID") (solution $sol): asking the visual director"''',
                  '''  local tools timeout_s try=1 res rc sid="" role=visual_director review_round
  tools="$(cfg visual.director_tools "Read Glob")"
  timeout_s="$(cfg timeouts.plan_seconds 1800)"
  # the review loop (M11): after caps.review_rounds_opus failed rounds the escalated director (fable) plans the fix
  review_round="$(state_get "$RUN_DIR" rounds.review 0 2>/dev/null)"; case "$review_round" in ''|*[!0-9]*) review_round=0 ;; esac
  if [ "$review_round" -ge "$(cfg caps.review_rounds_opus 3)" ] && cfg models.visual_director_escalation.model >/dev/null 2>&1; then role=visual_director_escalation; fi
  say INFO "S9: $act for $(json_field "$dres" idea_id "$IDEA_ID") (solution $sol): asking the visual director$([ "$role" = visual_director_escalation ] && echo " ($(cfg models.visual_director_escalation.model), review round $review_round)")$([ -n "$review_notes" ] && echo " with the edit review's notes")"''')
    s = s.replace('''      ai visual_director "$OUT" "$prompt" --resume "$sid" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try" --activity "$act"; rc=$?''',
                  '''      ai "$role" "$OUT" "$prompt" --resume "$sid" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try" --activity "$act"; rc=$?''')
    s = s.replace('''        ai visual_director "$OUT" "$prompt" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try-fresh" --activity "$act"; rc=$?''',
                  '''        ai "$role" "$OUT" "$prompt" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try-fresh" --activity "$act"; rc=$?''')
    s = s.replace('''      ai visual_director "$OUT" "$prompt" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try" --activity "$act"; rc=$?''',
                  '''      ai "$role" "$OUT" "$prompt" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try" --activity "$act"; rc=$?''')
    s = s.replace('''#       inline the style files, {{IDEA}} the idea, {{NOTE}} the runner's restart note.''',
                  '''#       inline the style files, {{IDEA}} the idea, {{NOTE}} the runner's restart note, {{REVIEW}} the edit review's notes
#       for this pass when the review loop (M11) sent the reel back (python pipeline/lib/review feedback; empty otherwise).
#       After caps.review_rounds_opus failed review rounds the call goes to models.visual_director_escalation.''')
    write(p, s)
    print(f"{p}: patched")
else:
    print(f"{p}: already patched")
for st in ("09a-animations", "09b-text", "09c-transitions"):
    p = f"pipeline/stages/{st}/prompt.md"
    s = read(p)
    if "{{REVIEW}}" not in s:
        if "{{NOTE}}\n" not in s:
            raise SystemExit(f"{p}: no NOTE placeholder")
        s = s.replace("{{NOTE}}\n", "{{NOTE}}\n{{REVIEW}}\n", 1)
        write(p, s)
        print(f"{p}: patched")
    else:
        print(f"{p}: already patched")

# 6. tests/lib.sh: --with-review
p = "pipeline/tests/lib.sh"
s = read(p)
if "with_review" not in s:
    s = s.replace('''  local with_pipeline=0 with_visual=0 a
  for a in "$@"; do
    case "$a" in --with-pipeline) with_pipeline=1 ;; --with-visual) with_pipeline=1; with_visual=1 ;; esac
  done''', '''  local with_pipeline=0 with_visual=0 with_review=0 a
  for a in "$@"; do
    case "$a" in --with-pipeline) with_pipeline=1 ;; --with-visual) with_pipeline=1; with_visual=1 ;; --with-review) with_pipeline=1; with_visual=1; with_review=1 ;; esac
  done''')
    s = s.replace('''      export REELS_NODE_PREFIX="$(mixed "$REPO_DIR")"
    fi''', '''      export REELS_NODE_PREFIX="$(mixed "$REPO_DIR")"
    fi
    if [ "$with_review" = 1 ]; then
      # what the review stage reads (M11): the reference analysis summaries and a few look stills (the folder is not
      # in git: the real one is copied when it exists), tools/analyze_refs.py is already in tools/
      local v
      for v in "$REPO_DIR"/styles/paper-cards/analysis/v*/; do
        [ -f "$v/summary.json" ] || continue
        mkdir -p "$SANDBOX/styles/paper-cards/analysis/$(basename "$v")"
        cp "$v/summary.json" "$SANDBOX/styles/paper-cards/analysis/$(basename "$v")/"
        case "$(basename "$v")" in v01|v02) cp "$v"/full_*.png "$SANDBOX/styles/paper-cards/analysis/$(basename "$v")/" 2>/dev/null || true ;; esac
      done
      cp "$REPO_DIR/styles/paper-cards/analysis/accent_share.txt" "$SANDBOX/styles/paper-cards/analysis/" 2>/dev/null || true
    fi''')
    s = s.replace('''#                                    README.md}; the Node packages stay in the real repo (REELS_NODE_PREFIX).''',
                  '''#                                    README.md}; the Node packages stay in the real repo (REELS_NODE_PREFIX).
#                                    --with-review (M11) also copies the reference analysis summaries and the look
#                                    stills of styles/paper-cards/analysis (the sound pack stays in the real repo:
#                                    REELS_SFX_DIR points at it).''')
    write(p, s)
    print(f"{p}: patched")
else:
    print(f"{p}: already patched")
print("done")
