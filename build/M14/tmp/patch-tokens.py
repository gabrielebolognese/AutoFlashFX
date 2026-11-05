p = "pipeline/lib/tokens.py"
s = open(p, encoding="utf-8").read()

s = s.replace("TOKENS_VERSION = 1\n", "TOKENS_VERSION = 2  # M14: motion.grammar and energy\n")
s = s.replace('''    "beat_map", "style_beat_map",
    "components",
}''', '''    "beat_map", "style_beat_map",
    "components",
    # M14: the motion grammar's values come from BUILD_SPEC.md section 5 (Motion and energy rules), the energy targets
    # from the calibration on the reference videos (styles/<style>/analysis/energy.json) or the spec; neither is a
    # number of style.md or tweaks.md (DECISIONS.md M14)
    "motion.grammar", "energy",
}''')

grammar_code = '''

# ----------------------------------------------------------------------------------------------- M14: motion grammar and energy

# The Motion and energy rules of BUILD_SPEC.md section 5 (E1, E2, E5 to E8), as values. They hold for every style; the
# style supplies the look through the other tokens. pc-motion.js reads them from tokens.css (--m-*).
GRAMMAR = {
    "main": {"min_s": 0.3, "max_s": 0.6, "frames": 12, "ease": "power3.inOut", "zoom_from": 0.85, "zoom_from_small": 0.92, "zoom_from_close": 1.15,
             "rotate_from_deg": 12, "rotate_from_range_deg": [8, 15], "rotate_to_deg": 1, "rotate_to_range_deg": [0, 2], "rotate_lag_frames": 3,
             "rotate_lag_range_frames": [2, 4], "move_short_px": 24, "perspective_px": 1400, "perspective_range_px": [1200, 1600],
             "note": "the opacity and position frames of the main animation stay the style's measured enters (motion.enter, motion.pop)"},
    "inertia": {"seconds": 3, "range_s": [2, 4], "ease": "power3.out", "move_px": 12, "scale": 0.03, "scale_example": [1.0, 1.04], "rotate_deg": 2,
                "note": "a decelerating cubic ease-out on top of the hold's constant speed, so the speed never reaches zero"},
    "hold": {"default": "normal",
             "calm": {"drift_px_s": 2, "rotate_deg_s": 0.2, "scale_pct_s": 0.2},
             "normal": {"drift_px_s": 4, "rotate_deg_s": 0.4, "scale_pct_s": 0.35},
             "lively": {"drift_px_s": 8, "rotate_deg_s": 0.6, "scale_pct_s": 0.5},
             "drift_range_px_s": [2, 8], "rotate_range_deg_s": [0.2, 0.6], "scale_range_pct_s": [0.2, 0.5]},
    "exit": {"min_s": 0.2, "max_s": 0.4, "ease": "power2.in", "note": "the style's exits (transitions.*) stay the reference"},
    "static_max_s": 0.5,
    "horizon_s": 90,
    "edges": {"outside_share": [0.3, 0.7], "max_speed_px_s": 20, "count": 6, "inside_max_px": 180, "no_text": True},
    "ambient": {"count": 16, "max_speed_px_s": 10, "twinkle_s": [2, 4], "kinds": ["star", "dot", "cloud"]},
    "camera": {"rotate_deg_s": 0.3, "perspective_px": 1400, "depth_step_px": 24},
    "mascot_idle": {"bob_px": 3, "blink_every_s": [2.6, 3.8], "prop_wiggle_deg": 6},
    "captions": {"fonts": ["grotesk", "serif-italic", "handwritten", "kicker"], "emphasis_size_ratio": [1.25, 1.5], "anchor_size_ratio": [2, 3],
                 "min_fonts_in_group": 3, "group_words": [2, 6], "word_rise_px": [8, 16], "word_rotate_deg": [2, 4], "group_rise_px": [20, 40],
                 "group_rotate_deg": [3, 6], "note": "E3, built in M15"},
    "text_budget": {"max_chars_on_screen": 100, "note": "E4, built in M15; the minimum text size is the caption font size"},
    "composition": {"hero_width_share": [0.7, 0.85], "min_layers_per_scene": 2, "empty_hero_max_s": 1, "camera_every_scenes": 3, "transition_type_max": 3,
                    "hook_moving_by_frame": 4, "note": "E8, built in M16"},
}

# The energy targets of E0 when the style has no calibration file (BUILD_SPEC.md, paper-cards)
ENERGY_SPEC_TARGETS = {"moving_share_pct": 42, "middle_moving_share_pct": 46, "pixels_changing_pct": 3.3, "still_share_pct": 15, "longest_still_s": 2}
ENERGY_LABELS = {"moving_share_pct": "moving share", "middle_moving_share_pct": "middle band", "pixels_changing_pct": "pixels changing",
                 "still_share_pct": "still stretches", "longest_still_s": "longest still"}


def text_zones(zones: dict, canvas: dict) -> dict:
    """The zones the edge and ambient layers must stay out of (E5, E7): the caption band, the hook header, the end card's
    text, as boxes at 1080x1920, derived from the zones."""
    cap = zones["caption"]
    margin = zones["margin_x"]
    ec = zones["end_card"]
    return {
        "caption": {"x": cap["x0"] - 30, "y": cap["center_y"] - 180, "w": (cap["x1"] - cap["x0"]) + 60, "h": 260},
        "hook": {"x": margin + 30, "y": zones["kicker_top"] - 20, "w": canvas["width"] - 2 * (margin + 30), "h": 470},
        "endcard": {"x": ec["x"] + 95, "y": ec["top"], "w": 680, "h": 640},
    }


def grammar_tokens(zones: dict, canvas: dict, type_scale: dict) -> dict:
    g = json.loads(json.dumps(GRAMMAR))
    g["text_zones"] = text_zones(zones, canvas)
    g["text_budget"]["min_text_px"] = type_scale["caption"]["font_px"]
    g["captions"]["caption_px"] = type_scale["caption"]["font_px"]
    return g


def energy_override(tweaks: str) -> dict:
    """An `- **Energy:** ...` line in tweaks.md overrides the targets: `moving 45`, `middle 50`, `pixels 3.5`, `still 12`,
    `longest 1.5` (any subset, any order, a percent sign or s allowed)."""
    m = re.search(r"^- \\*\\*Energy:\\*\\*(.*)$", tweaks, re.M)
    if not m:
        return {}
    line = m.group(1)
    out = {}
    pats = {"moving_share_pct": r"moving(?: share)?\\s+(\\d+(?:\\.\\d+)?)", "middle_moving_share_pct": r"middle(?: band)?\\s+(\\d+(?:\\.\\d+)?)",
            "pixels_changing_pct": r"pixels?(?: changing)?\\s+(\\d+(?:\\.\\d+)?)", "still_share_pct": r"still(?: stretches)?\\s+(\\d+(?:\\.\\d+)?)",
            "longest_still_s": r"longest(?: still)?\\s+(\\d+(?:\\.\\d+)?)"}
    for key, pat in pats.items():
        mm = re.search(pat, line, re.I)
        if mm:
            out[key] = num(mm.group(1))
    return out


def energy_targets_from_medians(look: dict) -> dict:
    """The lower bounds (moving share, middle band, pixels changing) at 70 percent of the look references' median; the
    upper bounds (still stretches, the longest still) at the median rounded up to the next 5 percent and 0.5 s."""
    out = dict(ENERGY_SPEC_TARGETS)
    if look.get("moving_share_pct") is not None:
        out["moving_share_pct"] = int(round(look["moving_share_pct"] * 0.7))
    if look.get("middle_moving_share_pct") is not None:
        out["middle_moving_share_pct"] = int(round(look["middle_moving_share_pct"] * 0.7))
    if look.get("pixels_changing_pct") is not None:
        out["pixels_changing_pct"] = round(look["pixels_changing_pct"] * 0.7, 1)
    if look.get("still_share_pct") is not None:
        out["still_share_pct"] = int(math.ceil(look["still_share_pct"] / 5.0 - 1e-9) * 5)
    if look.get("longest_still_s") is not None:
        out["longest_still_s"] = round(math.ceil(look["longest_still_s"] / 0.5 - 1e-9) * 0.5, 1)
    return out


def energy_tokens(energy_json: dict | None, tweaks: str) -> dict:
    """tokens.json `energy`: the targets (the calibration's, the spec's, then tweaks.md's Energy line), the thresholds of
    the meter and where the numbers came from."""
    if energy_json and isinstance(energy_json.get("medians"), dict) and energy_json["medians"].get("look"):
        look = energy_json["medians"]["look"]
        targets = energy_targets_from_medians(look)
        calibration = {"source": "analysis/energy.json", "run": energy_json.get("run"), "look_medians": look, "motion_medians": energy_json["medians"].get("motion"),
                       "videos": sorted(energy_json.get("videos", {}).keys())}
    else:
        targets = dict(ENERGY_SPEC_TARGETS)
        calibration = {"source": "spec", "note": "no styles/<style>/analysis/energy.json: the targets of BUILD_SPEC.md E0 for paper-cards"}
    override = energy_override(tweaks)
    targets.update(override)
    return {
        "targets": targets,
        "directions": {"moving_share_pct": "min", "middle_moving_share_pct": "min", "pixels_changing_pct": "min", "still_share_pct": "max", "longest_still_s": "max"},
        "labels": ENERGY_LABELS,
        "override": override,
        "override_format": "a line `- **Energy:** moving 45, middle 50, pixels 3.5, still 12, longest 1.5` in tweaks.md (any subset)",
        "calibration": calibration,
        "meter": {"fps": 30, "size": [108, 192], "frozen_max": 0.05, "subtle_max": 0.6, "medium_max": 4, "pixel_change_min": 8, "still_is": "below medium (frozen or subtle)",
                  "still_stretch_s": 1, "command": "python pipeline/lib/review energy <video> [--plan merged.json]"},
        "target_rule": "lower bounds at 70 percent of the look references' median; upper bounds at the median rounded up to 5 percent and 0.5 s",
    }

'''
s = s.replace('''

# ----------------------------------------------------------------------------------------------- the build
''', grammar_code + '''
# ----------------------------------------------------------------------------------------------- the build
''')
s = s.replace("import json\nimport os\nimport re\nimport sys\n", "import json\nimport math\nimport os\nimport re\nimport sys\n")

s = s.replace("def build_tokens(style_raw: str, tweaks_raw: str, fonts_dir: str | None) -> dict:",
              "def build_tokens(style_raw: str, tweaks_raw: str, fonts_dir: str | None, energy_json: dict | None = None) -> dict:")
s = s.replace('''    open_questions = {
        "1":''', '''    motion["grammar"] = grammar_tokens(zones, canvas, type_scale)
    energy = energy_tokens(energy_json, tweaks)

    open_questions = {
        "1":''')
s = s.replace('''        "branding": branding,
        "tracker": {"enabled": False},''', '''        "branding": branding,
        "energy": energy,
        "tracker": {"enabled": False},''')

# CSS: the --m-* variables
s = s.replace('''        f"  --end-card-tilt: {z['end_card']['tilt_deg']}deg;",
        "}",
        "",
    ]
    return "\\n".join(lines)''', '''        f"  --end-card-tilt: {z['end_card']['tilt_deg']}deg;",
    ]
    g = tokens["motion"].get("grammar") or {}
    if g:
        m, i, h = g["main"], g["inertia"], g["hold"]
        lines += [
            "  /* the motion grammar (BUILD_SPEC.md section 5, Motion and energy rules; tokens.json motion.grammar): read by pc-motion.js */",
            f"  --m-perspective: {m['perspective_px']};",
            f"  --m-main-frames: {m['frames']};",
            f"  --m-zoom-from: {m['zoom_from']};",
            f"  --m-zoom-from-small: {m['zoom_from_small']};",
            f"  --m-zoom-from-close: {m['zoom_from_close']};",
            f"  --m-rotate-from: {m['rotate_from_deg']};",
            f"  --m-rotate-to: {m['rotate_to_deg']};",
            f"  --m-rotate-lag: {m['rotate_lag_frames']};",
            f"  --m-move-short: {m['move_short_px']};",
            f"  --m-inertia-s: {i['seconds']};",
            f"  --m-inertia-move: {i['move_px']};",
            f"  --m-inertia-scale: {i['scale']};",
            f"  --m-inertia-rotate: {i['rotate_deg']};",
        ]
        for level in ("calm", "normal", "lively"):
            lines += [f"  --m-hold-{level}-drift: {h[level]['drift_px_s']};", f"  --m-hold-{level}-rotate: {h[level]['rotate_deg_s']};", f"  --m-hold-{level}-scale: {h[level]['scale_pct_s']};"]
        lines += [
            f"  --m-horizon-s: {g['horizon_s']};",
            f"  --m-static-max-s: {g['static_max_s']};",
            f"  --m-edge-max-speed: {g['edges']['max_speed_px_s']};",
            f"  --m-edge-outside-min: {g['edges']['outside_share'][0]};",
            f"  --m-edge-outside-max: {g['edges']['outside_share'][1]};",
            f"  --m-edge-count: {g['edges']['count']};",
            f"  --m-ambient-max-speed: {g['ambient']['max_speed_px_s']};",
            f"  --m-ambient-count: {g['ambient']['count']};",
            f"  --m-camera-deg-s: {g['camera']['rotate_deg_s']};",
            f"  --m-depth-step: {g['camera']['depth_step_px']};",
        ]
        for name, zb in g.get("text_zones", {}).items():
            lines.append(f"  --m-zone-{name}: {zb['x']:g} {zb['y']:g} {zb['w']:g} {zb['h']:g};")
    lines += ["}", ""]
    return "\\n".join(lines)''')

# the energy calibration file is a third source: its hash triggers a rebuild
s = s.replace('''def current(tokens_path: str, style: str, tweaks: str) -> tuple[bool, str]:
    if not os.path.isfile(tokens_path):''', '''def energy_json_path(style_dir: str) -> str:
    return os.path.join(style_dir, "analysis", "energy.json")


def load_energy_json(style_dir: str) -> dict | None:
    p = energy_json_path(style_dir)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def energy_hash(energy_json: dict | None) -> str:
    return sha1(json.dumps(energy_json.get("medians", {}), sort_keys=True)) if energy_json else ""


def current(tokens_path: str, style: str, tweaks: str, energy_json: dict | None = None) -> tuple[bool, str]:
    if not os.path.isfile(tokens_path):''')
s = s.replace('''    if src.get("tweaks.md") != sha1(tweaks):
        return False, "tweaks.md changed"
    return True, "unchanged"''', '''    if src.get("tweaks.md") != sha1(tweaks):
        return False, "tweaks.md changed"
    if (src.get("energy.json") or "") != energy_hash(energy_json):
        return False, "the energy calibration changed"
    return True, "unchanged"''')
s = s.replace('''        "sources": {"style.md": sha1(style_raw), "tweaks.md": sha1(tweaks_raw)},''',
              '''        "sources": {"style.md": sha1(style_raw), "tweaks.md": sha1(tweaks_raw), "energy.json": energy_hash(energy_json)},''')
s = s.replace('''def cmd_build(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    ok, reason = current(a.out, style, tweaks)''', '''def cmd_build(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    energy_json = load_energy_json(a.style_dir)
    ok, reason = current(a.out, style, tweaks, energy_json)''')
s = s.replace('''    tokens = build_tokens(style, tweaks, a.fonts_dir)
    problems = verify_tokens(tokens, style, tweaks)''', '''    tokens = build_tokens(style, tweaks, a.fonts_dir, energy_json)
    problems = verify_tokens(tokens, style, tweaks)''')
s = s.replace('''def cmd_check(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    ok, reason = current(a.tokens, style, tweaks)''', '''def cmd_check(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    ok, reason = current(a.tokens, style, tweaks, load_energy_json(a.style_dir))''')
# energy_hash must exist before build_tokens uses it: it is defined later in the file but called at run time, fine
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("tokens.py patched")

# the schema
q = "pipeline/lib/tokens.schema.json"
t = open(q, encoding="utf-8").read()
t = t.replace('''"zones", "shapes", "motion", "transitions", "pacing", "limits", "branding", "tracker", "honesty_labels", "beat_map",
               "open_questions"],''', '''"zones", "shapes", "motion", "transitions", "pacing", "limits", "branding", "energy", "tracker", "honesty_labels", "beat_map",
               "open_questions"],''')
t = t.replace('''    "motion": {"type": "object", "required": ["enter", "exit", "pop", "count_up", "caption", "end_card", "typing_frames_per_letter", "mascot", "hook", "headline"],
               "properties": {''', '''    "motion": {"type": "object", "required": ["enter", "exit", "pop", "count_up", "caption", "end_card", "typing_frames_per_letter", "mascot", "hook", "headline", "grammar"],
               "properties": {
                 "grammar": {"type": "object", "required": ["main", "inertia", "hold", "exit", "edges", "ambient", "camera", "captions", "text_zones", "static_max_s"],
                             "properties": {"hold": {"type": "object", "required": ["calm", "normal", "lively", "default"]},
                                            "text_zones": {"type": "object", "required": ["caption", "hook", "endcard"]}}},''')
t = t.replace('''    "branding": {"type": "object", "required": ["lockup_min_width", "bolt_min_height", "cta"]},''', '''    "branding": {"type": "object", "required": ["lockup_min_width", "bolt_min_height", "cta"]},
    "energy": {"type": "object", "required": ["targets", "directions", "calibration", "meter"],
               "properties": {"targets": {"type": "object", "required": ["moving_share_pct", "middle_moving_share_pct", "pixels_changing_pct", "still_share_pct", "longest_still_s"],
                                          "additionalProperties": {"type": "number"}}}},''')
open(q, "w", encoding="utf-8", newline="\n").write(t)
print("schema patched")
