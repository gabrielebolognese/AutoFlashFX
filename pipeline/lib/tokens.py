#!/usr/bin/env python
"""tokens.py: derive styles/paper-cards/tokens.json from style.md plus tweaks.md (BUILD_SPEC.md 2.4, PLAN.md M9).

Every number and color in tokens.json is read from the two source files with an explicit rule (the regexes in
RULES below), never typed in by hand: `verify` checks that every value appears in the sources. The in-force lines
of tweaks.md win over style.md; PROPOSED lines are ignored until the user removes the word PROPOSED (tweaks.md says
so; DECISIONS.md 31). The 15 open questions of style.md are decided with the rule of DECISIONS.md 32: what 5 of
the 7 motion references do; otherwise what both look references agree on; otherwise v02 (the decisions are
written to tokens.json under open_questions and recorded in DECISIONS.md under M9).

Commands (run as `python pipeline/lib/tokens.py <command> ...`; the bash wrapper is pipeline/bin/build-tokens):
  build  --style-dir DIR --out tokens.json [--css FILE] [--fonts-dir DIR] [--force]
         Rebuild when the source hashes or TOKENS_VERSION changed (a no-op otherwise); also write the CSS
         variables file when --css is given. Prints one JSON line: {"rebuilt": bool, "reason": ..., "out": ...}.
         Exit 0, or 2 when a rule finds nothing in the sources (the message names the field and the pattern).
  check  --style-dir DIR --tokens tokens.json        exit 0 when current, 1 when a rebuild is needed
  verify --style-dir DIR --tokens tokens.json        every number and hex of tokens.json appears in the sources
                                                      (the exempt keys are listed in EXEMPT); exit 1 on a problem
  css    --tokens tokens.json --out tokens.css       the CSS custom properties alone
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys

TOKENS_VERSION = 2  # M14: motion.grammar and energy
STYLE_NAME = "paper-cards"

# Keys whose values are not style numbers from the source files: hashes, dates, font metrics measured from the
# font files (cap height ratios), file names and the version numbers of this builder.
EXEMPT = {
    "sources", "generated", "tokens_version", "style_version", "style", "in_force", "open_questions",
    "fonts.*.cap_ratio", "fonts.*.file", "fonts.*.license", "fonts.*.family", "fonts.*.weight", "fonts.*.style",
    "beat_map", "style_beat_map",
    "components",
    # M14: the motion grammar's values come from BUILD_SPEC.md section 5 (Motion and energy rules), the energy targets
    # from the calibration on the reference videos (styles/<style>/analysis/energy.json) or the spec; neither is a
    # number of style.md or tweaks.md (DECISIONS.md M14)
    "motion.grammar", "energy",
}


class TokenError(Exception):
    pass


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def read(path: str) -> str:
    with open(path, encoding="utf-8-sig") as f:
        return f.read().replace("\r\n", "\n")


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def num(s: str) -> float | int:
    v = float(s)
    return int(v) if v.is_integer() else v


def grab(field: str, pattern: str, text: str, group: int = 1, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    if not m:
        raise TokenError(f"{field}: nothing in the sources matches /{pattern}/")
    return m.group(group)


def grab_num(field: str, pattern: str, text: str, group: int = 1) -> float | int:
    return num(grab(field, pattern, text, group))


def grab_nums(field: str, pattern: str, text: str, groups: tuple[int, ...]) -> list[float | int]:
    m = re.search(pattern, text)
    if not m:
        raise TokenError(f"{field}: nothing in the sources matches /{pattern}/")
    return [num(m.group(g)) for g in groups]


HEX = r"#[0-9A-Fa-f]{6}"


# ----------------------------------------------------------------------------------------------- tweaks.md

PROPOSED_TITLES = {
    "caption_position": "Caption position",
    "right_side_captions": "Right side, captions",
    "hook_header": "Hook header",
    "length": "Length",
    "accent_cards": "Accent-filled cards",
    "three_d_cards": "3D",
}


def tweaks_state(tweaks: str) -> dict:
    """Which PROPOSED lines are accepted (the word PROPOSED removed) and the in-force decision lines."""
    in_force = {}
    for key, title in PROPOSED_TITLES.items():
        accepted = re.search(r"^- \*\*" + re.escape(title) + r":\*\*", tweaks, re.M) is not None
        proposed = re.search(r"^- PROPOSED \*\*" + re.escape(title) + r":\*\*", tweaks, re.M) is not None
        in_force[key] = bool(accepted and not proposed)
    return in_force


def proposed_block(tweaks: str, title: str) -> str:
    """The text of one PROPOSED (or accepted) bullet, up to the next bullet. Length and 3D also have an earlier
    decision bullet with the same title, so the bullet that holds a "Proposal:" wins (else the last one)."""
    pat = r"^- (?:PROPOSED )?\*\*" + re.escape(title) + r":\*\*(.*?)(?=^- |\Z)"
    blocks = [m.group(1) for m in re.finditer(pat, tweaks, re.M | re.S)]
    with_proposal = [b for b in blocks if "Proposal:" in b]
    return (with_proposal or blocks or [""])[-1]


# ----------------------------------------------------------------------------------------------- M14: motion grammar and energy

# The Motion and energy rules of BUILD_SPEC.md section 5 (E1, E2, E5 to E8), as values. They hold for every style; the
# style supplies the look through the other tokens. pc-motion.js reads them from tokens.css (--m-*).
GRAMMAR = {
    "main": {"min_s": 0.3, "max_s": 0.6, "frames": 18, "ease": "power3.inOut", "zoom_from": 0.85, "zoom_from_small": 0.92, "zoom_from_close": 1.15,
             "rotate_from_deg": 12, "rotate_from_range_deg": [8, 15], "rotate_to_deg": 1, "rotate_to_range_deg": [0, 2], "rotate_lag_frames": 3,
             "rotate_lag_range_frames": [2, 4], "move_short_px": 24, "perspective_px": 1400, "perspective_range_px": [1200, 1600],
             "note": "the opacity and position frames of the main animation stay the style's measured enters (motion.enter, motion.pop)"},
    "inertia": {"seconds": 3, "range_s": [2, 4], "ease": "power3.out", "move_px": 16, "scale": 0.04, "scale_example": [1.0, 1.04], "rotate_deg": 2,
                "note": "a decelerating cubic ease-out on top of the hold's constant speed, so the speed never reaches zero"},
    "hold": {"default": "normal",
             "calm": {"drift_px_s": 2, "rotate_deg_s": 0.2, "scale_pct_s": 0.2},
             "normal": {"drift_px_s": 4, "rotate_deg_s": 0.4, "scale_pct_s": 0.35},
             "lively": {"drift_px_s": 8, "rotate_deg_s": 0.6, "scale_pct_s": 0.5},
             "drift_range_px_s": [2, 8], "rotate_range_deg_s": [0.2, 0.6], "scale_range_pct_s": [0.2, 0.5],
             "room_life_s": 8,
             "room_note": "the inertia and the drift fit the room between the element's rest box and the safe edges (zones: safe_top, safe_bottom, margin_x, the right rail in the lower half) in their direction over the element's life (its until or exit_at, else room_life_s): near an edge the hold turns and creeps instead of drifting (E1: a drift, a rotation or a creep)"},
    "exit": {"min_s": 0.2, "max_s": 0.4, "ease": "power2.in", "note": "the style's exits (transitions.*) stay the reference"},
    "static_max_s": 0.5,
    "horizon_s": 90,
    "edges": {"outside_share": [0.3, 0.7], "max_speed_px_s": 20, "count": 6, "inside_max_px": 180, "no_text": True},
    "ambient": {"count": 16, "max_speed_px_s": 10, "twinkle_s": [2, 4], "kinds": ["star", "dot", "cloud"]},
    "camera": {"rotate_deg_s": 0.3, "perspective_px": 1400, "depth_step_px": 24},
    "content": {"scroll_px_s": 30, "note": "a screenshot inside a window card scrolls slowly through its own height (content motion, E1: the content itself keeps moving)"},
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
    m = re.search(r"^- \*\*Energy:\*\*(.*)$", tweaks, re.M)
    if not m:
        return {}
    line = m.group(1)
    out = {}
    pats = {"moving_share_pct": r"moving(?: share)?\s+(\d+(?:\.\d+)?)", "middle_moving_share_pct": r"middle(?: band)?\s+(\d+(?:\.\d+)?)",
            "pixels_changing_pct": r"pixels?(?: changing)?\s+(\d+(?:\.\d+)?)", "still_share_pct": r"still(?: stretches)?\s+(\d+(?:\.\d+)?)",
            "longest_still_s": r"longest(?: still)?\s+(\d+(?:\.\d+)?)"}
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


# ----------------------------------------------------------------------------------------------- the build

def color_table(style: str) -> dict:
    colors = {}
    for m in re.finditer(r"^\| ([a-z-]+) \| `(" + HEX + r")` \|", style, re.M):
        colors[m.group(1)] = m.group(2).upper()
    for required in ("paper", "glow-warm", "dot", "surface", "surface-chrome", "ink", "ink-chip", "accent",
                     "accent-deep", "script", "success", "mascot"):
        if required not in colors:
            raise TokenError(f"colors.{required}: missing from the Color table of style.md")
    return colors


def beat_table(style: str) -> list[dict]:
    rows = []
    section = grab("beat_map", r"## Beat map\n(.*?)\n## ", style, 1, re.S)
    for line in section.splitlines():
        m = re.match(r"^\| (.+?) \| (.+?) \| (.+?) \|$", line)
        if not m or m.group(1) in ("beat", "---"):
            continue
        rows.append({"beat": m.group(1).strip(), "component": m.group(2).strip(), "videos": m.group(3).strip()})
    if len(rows) < 10:
        raise TokenError("beat_map: fewer than 10 rows found in the Beat map table of style.md")
    return rows


# The script's beat types (07-script/schema.json) to the library components they may use. Derived from the style's
# beat map (style.md, Beat map) by judgment: the style names beats by content (proof / number, the tool, how it
# works, data, options) and the script by function; recorded in DECISIONS.md M9. "any" lists what every beat may
# use (the canvas, the captions, the mascot and the moves).
BEAT_TYPES = {
    "hook": ["headline", "window-card", "logo-tile", "hero-3d", "icon-3d", "card", "fly-in", "stat-number"],
    "stake": ["card", "dark-chip", "light-chip", "window-card", "strike-through", "handwritten-callout", "thumb-grid"],
    "number": ["stat-number", "chart-card", "progress-bar", "dark-chip", "card", "light-chip"],
    "tool": ["window-card", "logo-tile", "card", "light-chip", "dark-chip", "thumb-grid", "camera-move"],
    "step": ["terminal-card", "chat-card", "check-badge", "light-chip", "window-card", "card", "progress-bar", "dark-chip"],
    "comparison": ["table-card", "strike-through", "thumb-grid", "card", "chart-card", "dark-chip", "light-chip", "window-card"],
    "proof": ["stat-number", "window-card", "chart-card", "check-badge", "dark-chip", "card", "table-card"],
    "mechanism": ["card", "light-chip", "dark-chip", "chart-card", "terminal-card", "check-badge", "handwritten-callout", "thumb-grid", "window-card"],
    "before-after": ["strike-through", "table-card", "thumb-grid", "card", "chart-card", "light-chip", "window-card"],
    "pain-payoff": ["card", "check-badge", "strike-through", "dark-chip", "light-chip", "window-card"],
    "payoff": ["card", "check-badge", "window-card", "light-chip", "stat-number", "progress-bar", "dark-chip"],
    "ask": ["end-card", "dm-card", "speech-bubble", "icon-3d"],
    "any": ["paper-canvas", "caption-line", "mascot", "pop", "exit-move", "fly-in", "camera-move"],
}


def font_metrics(fonts_dir: str | None) -> dict:
    """Cap height ratios measured from the font files (PIL renders an H), so a cap height in px becomes a font size."""
    spec = {
        "grotesk": {"family": "Inter Tight", "file": "InterTight-Variable.ttf", "license": "InterTight-OFL.txt", "weight": 800, "style": "normal"},
        "serif-italic": {"family": "Instrument Serif", "file": "InstrumentSerif-Italic.ttf", "license": "InstrumentSerif-OFL.txt", "weight": 400, "style": "italic"},
        "kicker": {"family": "Space Grotesk", "file": "SpaceGrotesk-Variable.ttf", "license": "SpaceGrotesk-OFL.txt", "weight": 600, "style": "normal"},
        "mono": {"family": "JetBrains Mono", "file": "JetBrainsMono-Variable.ttf", "license": "JetBrainsMono-OFL.txt", "weight": 500, "style": "normal"},
        "handwritten": {"family": "Caveat", "file": "Caveat-Variable.ttf", "license": "Caveat-OFL.txt", "weight": 500, "style": "normal"},
    }
    for key, font in spec.items():
        ratio = None
        if fonts_dir:
            path = os.path.join(fonts_dir, font["file"])
            if os.path.isfile(path):
                try:
                    from PIL import ImageFont  # pillow is installed with playwright's dependencies on this PC
                    f = ImageFont.truetype(path, 1000)
                    box = f.getbbox("H")
                    ratio = round((box[3] - box[1]) / 1000, 3)
                except Exception:  # noqa: BLE001 (any PIL problem: keep the default below)
                    ratio = None
        font["cap_ratio"] = ratio if ratio else 0.72  # 0.72: the ratio style.md used ("48 / 0.72 = 66.7")
    return spec


def flatten(text: str) -> str:
    """Join the wrapped continuation lines of the markdown bullets (two or more leading spaces) so a rule can match a
    sentence that the source wraps at 120 columns."""
    return re.sub(r"\n[ \t]+(?=\S)", " ", text)


def build_tokens(style_raw: str, tweaks_raw: str, fonts_dir: str | None, energy_json: dict | None = None) -> dict:
    style, tweaks = flatten(style_raw), flatten(tweaks_raw)
    in_force = tweaks_state(tweaks)
    colors = color_table(style)
    colors["media-frame"] = grab("colors.media-frame", r"media frames are `(" + HEX + r")`", style).upper()
    colors["unit-serif"] = grab("colors.unit-serif", r"serif-italic unit \((" + HEX + r")\)", style).upper()
    colors["emphasis-text"] = grab("colors.emphasis-text", r"text near-white \((" + HEX + r") to " + HEX + r"\)", style).upper()
    colors["keyword-pill"] = grab("colors.keyword-pill", r"v02 measures (" + HEX + r")", style).upper()  # open question: v02 wins
    edge_lo, edge_hi = re.search(r"faint darker edge, (" + HEX + r") to (" + HEX + r")\)", style).groups() if re.search(r"faint darker edge, (" + HEX + r") to (" + HEX + r")\)", style) else (None, None)
    if not edge_lo:
        raise TokenError("colors.card-edge: 'faint darker edge, #... to #...' not found in style.md")
    colors["card-edge"] = edge_lo.upper()  # the v02 end of the range (DECISIONS.md 32: v02 breaks a tie)
    colors["shadow-dark"] = grab("colors.shadow-dark", r"darkest right under the bottom edge \((" + HEX + r") to " + HEX + r" on paper\)", style).upper()
    m = re.search(r"Lower-right glow\.\*\* Cool (" + HEX + r") \(v01\) or warm (" + HEX + r") \(v02\)", style)
    if not m:
        raise TokenError("colors.glow-lower: open question 8 line not found in style.md")
    colors["glow-lower"] = m.group(2).upper()  # open question 8: v02 (warm)
    m = re.search(r"Bottom corners darker than the center: " + HEX + r" \(v01\), (" + HEX + r") to (" + HEX + r") \(v02\)", style)
    if not m:
        raise TokenError("colors.corner: 'Bottom corners darker than the center' line not found in style.md")
    colors["corner"] = m.group(1).upper()  # v02, the darker end

    canvas = {
        "width": grab_num("canvas.width", r"## Canvas \((\d+)x\d+, \d+fps\)", style),
        "height": grab_num("canvas.height", r"## Canvas \(\d+x(\d+), \d+fps\)", style),
        "fps": grab_num("canvas.fps", r"## Canvas \(\d+x\d+, (\d+)fps\)", style),
    }

    fonts = font_metrics(fonts_dir)

    type_scale = {
        "caption": {"cap_px": grab_num("type.caption.cap_px", r"\| caption \|.*?\| cap (\d+(?:\.\d+)?)px, font about (\d+)px", style, 1),
                    "font_px": grab_num("type.caption.font_px", r"\| caption \|.*?\| cap \d+(?:\.\d+)?px, font about (\d+)px", style),
                    "font": "grotesk", "case": "sentence"},
        "headline": {"cap_px": grab_num("type.headline.cap_px", r"\| hook headline \|.*?\(median (\d+(?:\.\d+)?)\), font about (\d+)px, lines (\d+)px apart", style, 1),
                     "font_px": grab_num("type.headline.font_px", r"\| hook headline \|.*?\(median \d+(?:\.\d+)?\), font about (\d+)px", style),
                     "line_px": grab_num("type.headline.line_px", r"\| hook headline \|.*?lines (\d+)px apart", style),
                     "font": "grotesk", "case": "sentence"},
        "headline_phrase": {"font": "serif-italic", "color": "accent-deep", "words": [1, 2]},
        "kicker": {"cap_px": grab_num("type.kicker.cap_px", r"\| kicker \|.*?\| cap (\d+)px \(v02\) or (\d+)px \(v01\)", style, 1),
                   "font": "kicker", "case": "upper", "color": "accent"},  # open question 6: v02
        "stat": {"digit_px": grab_num("type.stat.digit_px", r"\| stat number \|.*?\| digit height (\d+(?:\.\d+)?)px, font about (\d+)px", style, 1),
                 "font_px": grab_num("type.stat.font_px", r"\| stat number \|.*?digit height \d+(?:\.\d+)?px, font about (\d+)px", style),
                 "font": "grotesk"},
        "end_verb": {"cap_px": grab_num("type.end_verb.cap_px", r"\| end card \"Comment\" \|.*?\(median (\d+(?:\.\d+)?)\), font about (\d+)px", style, 1),
                     "font_px": grab_num("type.end_verb.font_px", r"\| end card \"Comment\" \|.*?font about (\d+)px", style),
                     "font": "grotesk", "case": "title"},
        "end_keyword": {"cap_px": grab_num("type.end_keyword.cap_px", r"\| end card keyword \|.*?\| cap (\d+(?:\.\d+)?)px, font about (\d+)px", style, 1),
                        "font_px": grab_num("type.end_keyword.font_px", r"\| end card keyword \|.*?font about (\d+)px", style),
                        "font": "grotesk", "case": "upper"},
        "handwritten": {"line_px": grab_num("type.handwritten.line_px", r"\| handwritten \|.*?lines (\d+) to (\d+(?:\.\d+)?)px apart, font about (\d+)px", style, 1),
                        "font_px": grab_num("type.handwritten.font_px", r"\| handwritten \|.*?font about (\d+)px", style),
                        "font": "handwritten", "color": "script", "case": "lower"},
        "mono": {"font": "mono"},
    }

    # zones: the in-force tweaks lines, then style.md
    caption_y = grab_num("zones.caption.center_y", r"\*\*Caption box:\*\* stays at y (\d+)", tweaks)
    caption_exception = True
    if in_force["caption_position"]:
        caption_y = grab_num("zones.caption.center_y (accepted proposal)", r"Proposal: captions at y (\d+)", proposed_block(tweaks, "Caption position"))
        caption_exception = False
    right_rail = grab_num("zones.right_rail.width", r"no text in the\s+right (\d+)px of the lower half", tweaks)
    caption_x1 = canvas["width"] - right_rail
    caption_max_w = grab_num("zones.caption.max_width", r"a centered caption line is at most (\d+)px wide \(x (\d+) to (\d+)\)", style, 1)
    caption_x0 = grab_num("zones.caption.x0", r"at most \d+px wide \(x (\d+) to (\d+)\)", style, 1)
    kicker_top = grab_num("zones.kicker_top", r"kicker top (\d+) \(v01\) or (\d+) \(v02\)", style, 2)  # open question 5: v02
    if in_force["hook_header"]:
        kicker_top = grab_num("zones.kicker_top (accepted proposal)", r"Proposal: use v02's y (\d+)", proposed_block(tweaks, "Hook header"))
    hero_top_min, hero_top_max = grab_nums("zones.hero.top", r"top edge between y (\d+) and (\d+), bottom edge at or above y (\d+)", style, (1, 2))
    hero_bottom = grab_num("zones.hero.bottom_max", r"bottom edge at or above y (\d+)", style)
    zones = {
        "safe_top": grab_num("zones.safe_top", r"above the safe line at (\d+)", style),
        "safe_bottom": grab_num("zones.safe_bottom", r"safe zone stops at y (\d+)", tweaks),
        "margin_x": grab_num("zones.margin_x", r"Side margins: at least (\d+)px", style),
        "kicker_top": kicker_top,
        "hero": {"top_min": hero_top_min, "top_max": hero_top_max, "bottom_max": hero_bottom},
        "caption": {"center_y": caption_y, "max_width": caption_max_w, "x0": caption_x0, "x1": caption_x1,
                    "safe_zone_exception": caption_exception},
        "right_rail": {"width": right_rail, "from_y": canvas["height"] / 2},
        "end_card": {
            "width": grab_num("zones.end_card.width", r"a `surface` card (\d+)px wide, (\d+) to (\d+)px tall, x (\d+) to (\d+), top edge at y (\d+) \(v02\) to (\d+) \(v01\)", style, 1),
            "height": grab_nums("zones.end_card.height", r"card (\d+)px wide, (\d+) to (\d+)px tall", style, (2, 3)),
            "x": grab_num("zones.end_card.x", r"px tall, x (\d+) to (\d+), top edge", style, 1),
            "x1": grab_num("zones.end_card.x1", r"px tall, x (\d+) to (\d+), top edge", style, 2),
            "top": grab_num("zones.end_card.top", r"top edge at y (\d+) \(v02\) to (\d+) \(v01\)", style, 1),  # v02
            "top_range": grab_nums("zones.end_card.top_range", r"top edge at y (\d+) \(v02\) to (\d+) \(v01\)", style, (1, 2)),
            "tilt_deg": grab_num("zones.end_card.tilt_deg", r"\(v01 (-?\d+(?:\.\d+)?) degrees, rising to the right; v02 tilts and wobbles\)", style),
            "wobble": True,
            "mascot_row_y": grab_nums("zones.end_card.mascot_row_y", r"about (\d+)px apart \(y (\d+) to (\d+)\)", style, (2, 3)),
            "mascot_gap": grab_num("zones.end_card.mascot_gap", r"5 mascots with props\s+about (\d+)px apart", style),
            "mascots": grab_num("zones.end_card.mascots", r"a row of (\d+) mascots", style),
        },
    }

    shapes = {
        "card": {
            "radius": grab_num("shapes.card.radius", r"\*\*Card:\*\* `surface`, corner radius (\d+)px", style),
            "edge_px": grab_nums("shapes.card.edge_px", r"only a (\d+) to (\d+)px faint darker edge", style, (1, 2)),
            "shadow": {
                "above": grab_num("shapes.card.shadow.above", r"soft drop shadow: about (\d+)px above", style),
                "side": grab_nums("shapes.card.shadow.side", r"(\d+) to (\d+)px at the sides", style, (1, 2)),
                "below": grab_nums("shapes.card.shadow.below", r"(\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)px below \(median (\d+)\)", style, (1, 2)),
                "below_median": grab_num("shapes.card.shadow.below_median", r"px below \(median (\d+)\)", style),
                "css_offset_y": grab_num("shapes.card.shadow.css_offset_y", r"`box-shadow: 0 (\d+)px (\d+)px`", style, 1),
                "css_blur": grab_num("shapes.card.shadow.css_blur", r"`box-shadow: 0 (\d+)px (\d+)px`", style, 2),
            },
        },
        "window_dots": grab_num("shapes.window_dots", r"(\d+) traffic-light dots", style),
        "media_frame_px": grab_num("shapes.media_frame_px", r"the image inside a (\d+(?:\.\d+)?)px `" + HEX + r"` frame", style),
        "stat_pill_h": grab_num("shapes.stat_pill_h", r"white pill, fully round, (\d+)px tall", style),
        "stat_chip_h": grab_num("shapes.stat_chip_h", r"or a rounded chip (\d+)px tall", style),
        "dark_chip_h": grab_num("shapes.dark_chip_h", r"\*\*Dark chip:\*\*.*?(\d+)px tall", style),
        "light_chip_h": grab_num("shapes.light_chip_h", r"\*\*Light chip:\*\*.*?(\d+)px tall", style),
        "emphasis_box": {
            "height": grab_num("shapes.emphasis_box.height", r"Box: (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)px tall \(median (\d+(?:\.\d+)?)\)", style, 3),
            "radius": grab_num("shapes.emphasis_box.radius", r"\*\*Emphasis box:\*\* `accent` fill, near-white text, corner radius (\d+)px", style),
            "above_cap": grab_num("shapes.emphasis_box.above_cap", r"(\d+(?:\.\d+)?)px above the cap height", style),
            "below_baseline": grab_nums("shapes.emphasis_box.below_baseline", r"(\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)px below the baseline", style, (1, 2)),
            "gap": grab_num("shapes.emphasis_box.gap", r"(\d+)px gap to the\s+previous word", style),
        },
        "mascot": {"w": grab_num("shapes.mascot.w", r"about (\d+) x (\d+)px", style, 1), "h": grab_num("shapes.mascot.h", r"about (\d+) x (\d+)px", style, 2)},
        "dots": {"size_px": grab_num("shapes.dots.size_px", r"dots about (\d+) to (\d+) px", style, 2),
                 "spacing_px": grab_num("shapes.dots.spacing_px", r"Spacing: Open question 7 \((\d+)px in v01, (\d+(?:\.\d+)?)px in v02\)", style, 2)},  # open question 7: v02
        "glow": {"tinted_x": grab_num("shapes.glow.tinted_x", r"still tinted at x (\d+) and y (\d+)", style, 1),
                 "tinted_y": grab_num("shapes.glow.tinted_y", r"still tinted at x (\d+) and y (\d+)", style, 2),
                 "plain_x": grab_num("shapes.glow.plain_x", r"plain paper by about\s+x (\d+) and y (\d+)", style, 1),
                 "plain_y": grab_num("shapes.glow.plain_y", r"plain paper by about\s+x (\d+) and y (\d+)", style, 2)},
    }

    motion = {
        "enter": {
            "opacity_frames": grab_num("motion.enter.opacity_frames", r"\*\*Enter\*\*.*?opacity 0 to 1 over (\d+) frames and y \+(\d+)px to 0 over (\d+) frames", style, 1),
            "rise_px": grab_num("motion.enter.rise_px", r"\*\*Enter\*\*.*?y \+(\d+)px to 0 over (\d+) frames", style, 1),
            "position_frames": grab_num("motion.enter.position_frames", r"\*\*Enter\*\*.*?y \+\d+px to 0 over (\d+) frames", style),
            "rise_range_px": grab_nums("motion.enter.rise_range_px", r"Rise per video (\d+) to (\d+)px", style, (1, 2)),
            "ease": "expo.out",
        },
        "exit": {"frames": grab_nums("motion.exit.frames", r"\*\*Exit:\*\* a cut, or a move faster than the enter that accelerates \(ease-in\), (\d+) to (\d+) frames", style, (1, 2)), "ease": "power2.in"},
        "pop": {
            "from_scale": grab_num("motion.pop.from_scale", r"\*\*Pop\*\*.*?scale up from about (\d+(?:\.\d+)?) with a back-out overshoot, (\d+) to (\d+) frames", style, 1),
            "frames": grab_nums("motion.pop.frames", r"back-out overshoot, (\d+) to (\d+) frames", style, (1, 2)),
            "overshoot_icon_pct": grab_nums("motion.pop.overshoot_icon_pct", r"icons and badges overshoot (\d+) to (\d+)%, pills and cards (\d+) to (\d+)%", style, (1, 2)),
            "overshoot_pill_pct": grab_nums("motion.pop.overshoot_pill_pct", r"icons and badges overshoot (\d+) to (\d+)%, pills and cards (\d+) to (\d+)%", style, (3, 4)),
        },
        "count_up": {
            "frames": grab_num("motion.count_up.frames", r"\*\*Count-up:\*\*.*?median (\d+(?:\.\d+)?) frames \((\d+) to (\d+)\)", style, 1),
            "frames_range": grab_nums("motion.count_up.frames_range", r"\*\*Count-up:\*\*.*?median \d+(?:\.\d+)? frames \((\d+) to (\d+)\)", style, (1, 2)),
            "ease": "power3.out",
        },
        "caption": {
            "word_frames": grab_num("motion.caption.word_frames", r"Word enter: opacity 0 to 1 over (\d+) frames", style),
            "box_frames": grab_num("motion.caption.box_frames", r"Each word's box fades in with the word\s+over (\d+) frames, rising (\d+) to (\d+)px", style, 1),
            "box_rise_px": grab_num("motion.caption.box_rise_px", r"Each word's box fades in with the word\s+over \d+ frames, rising (\d+) to (\d+)px", style, 1),
            "box_rise_range_px": grab_nums("motion.caption.box_rise_range_px", r"over \d+ frames, rising (\d+) to (\d+)px", style, (1, 2)),
            "replace_out_frames": grab_num("motion.caption.replace_out_frames", r"Replace: the old chunk fades out over (\d+) to (\d+) frames", style, 1),
            "replace_out_range": grab_nums("motion.caption.replace_out_range", r"Replace: the old chunk fades out over (\d+) to (\d+) frames", style, (1, 2)),
        },
        "end_card": {
            "fade_frames": grab_num("motion.end_card.fade_frames", r"\*\*End card build:\*\* elements fade in over (\d+) frames \((\d+) to (\d+)\), top to bottom, (\d+) to (\d+) frames apart", style, 1),
            "fade_range": grab_nums("motion.end_card.fade_range", r"\*\*End card build:\*\* elements fade in over \d+ frames \((\d+) to (\d+)\)", style, (1, 2)),
            "stagger_frames": grab_num("motion.end_card.stagger_frames", r"top to bottom, (\d+) to (\d+) frames apart", style, 2),
            "stagger_range": grab_nums("motion.end_card.stagger_range", r"top to bottom, (\d+) to (\d+) frames apart", style, (1, 2)),
            "hold_s": grab_nums("motion.end_card.hold_s", r"The end card holds\s+(\d+(?:\.\d+)?)s \(v02\) to (\d+(?:\.\d+)?)s \(v01\)", style, (1, 2)),
            "keyword": "typed",  # open question 4: both look refs type it
        },
        "typing_frames_per_letter": grab_num("motion.typing_frames_per_letter", r"\*\*Typing\*\*.*?(\d+) frames per letter for keywords", style),
        "mascot": {
            "delay_frames": grab_num("motion.mascot.delay_frames", r"Enters (\d+) to (\d+) frames after its card lands, fading or rising in over (\d+) to (\d+) frames", style, 1),
            "delay_range": grab_nums("motion.mascot.delay_range", r"Enters (\d+) to (\d+) frames after its card lands", style, (1, 2)),
            "frames": grab_num("motion.mascot.frames", r"fading or rising in over (\d+) to (\d+) frames", style, 2),
            "frames_range": grab_nums("motion.mascot.frames_range", r"fading or rising in over (\d+) to (\d+) frames", style, (1, 2)),
        },
        "hook": {
            "hero_enter_within_frames": grab_num("motion.hook.hero_enter_within_frames", r"The hero element enters within the first\s+(\d+) frames", style),
            "scene_s": grab_nums("motion.hook.scene_s", r"The hook scene runs (\d+(?:\.\d+)?)s\s+\(v02\) to (\d+(?:\.\d+)?)s \(v01\)", style, (1, 2)),
        },
        "headline": {"mode": "word", "word_frames": grab_num("motion.headline.word_frames", r"Word by word as spoken \(v01, v02, v03, v05; (\d+) to (\d+) frames per word", style, 1)},  # open question 11: look refs agree
        "caption_word_style": "fade",  # open question 12: look refs agree on a plain fade
    }

    transitions = {
        "scene_change": "exit-then-enter",  # open question 3: both look refs (B)
        "default": "fade-blur",
        "allowed": ["fade-blur", "fall", "push", "cut"],
        "fade_blur_frames": grab_num("transitions.fade_blur_frames", r"fade with blur over (\d+) to (\d+) frames, then fly-ins", style, 2),  # v02's 4
        "fall_frames": grab_num("transitions.fall_frames", r"v07 \(falls over (\d+) frames, ease-in, tilting about (\d+) degrees", style, 1),
        "fall_tilt_deg": grab_num("transitions.fall_tilt_deg", r"v07 \(falls over (\d+) frames, ease-in, tilting about (\d+) degrees", style, 2),
        "push_out_frames": grab_num("transitions.push_out_frames", r"push: (\d+) frames out ease-in, (\d+) empty frames, (\d+) frames in expo-out", style, 1),
        "push_gap_frames": grab_num("transitions.push_gap_frames", r"push: (\d+) frames out ease-in, (\d+) empty frames, (\d+) frames in expo-out", style, 2),
        "push_in_frames": grab_num("transitions.push_in_frames", r"push: (\d+) frames out ease-in, (\d+) empty frames, (\d+) frames in expo-out", style, 3),
    }

    pacing = {
        "changes_per_10s_median": grab_num("pacing.changes_per_10s_median", r"median (\d+(?:\.\d+)?) per 10s, median gap (\d+(?:\.\d+)?)s, p90 (\d+(?:\.\d+)?)s, longest (\d+(?:\.\d+)?)s", style, 1),
        "gap_median_s": grab_num("pacing.gap_median_s", r"median gap (\d+(?:\.\d+)?)s, p90", style),
        "gap_p90_s": grab_num("pacing.gap_p90_s", r"p90 (\d+(?:\.\d+)?)s, longest", style),
        "gap_max_s": grab_num("pacing.gap_max_s", r"longest (\d+(?:\.\d+)?)s", style),
        "scene_s": {"min": grab_num("pacing.scene_s.min", r"mean scene length per motion ref (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)s, median (\d+(?:\.\d+)?)s", style, 1),
                    "max": grab_num("pacing.scene_s.max", r"mean scene length per motion ref \d+(?:\.\d+)? to (\d+(?:\.\d+)?)s", style),
                    "median": grab_num("pacing.scene_s.median", r"per motion ref \d+(?:\.\d+)? to \d+(?:\.\d+)?s, median (\d+(?:\.\d+)?)s", style)},
        "first_change_max_frames": motion["hook"]["hero_enter_within_frames"],
        "reference_length_s": grab_nums("pacing.reference_length_s", r"Length: look refs (\d+(?:\.\d+)?)s and (\d+(?:\.\d+)?)s", style, (1, 2)),
    }

    length_default = grab_nums("limits.length_s.default", r"Everything else stays (\d+) to (\d+)s", tweaks, (1, 2))
    length_list = grab_nums("limits.length_s.list", r"list and explainer videos may run (\d+) to (\d+)s", tweaks, (1, 2))
    if in_force["length"]:
        length_list = grab_nums("limits.length_s.list (accepted proposal)", r"Proposal: list and explainer\s+videos (\d+) to (\d+)s", proposed_block(tweaks, "Length"), (1, 2))
    limits = {
        "accent_share_max_pct": grab_num("limits.accent_share_max_pct", r"\*\*Accent:\*\* under (\d+)% of any frame", tweaks),
        "accent_share_median_pct": grab_nums("limits.accent_share_median_pct", r"covers a median (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)% of a frame", style, (1, 2)),
        "accent_card_area_max_px": (grab_num("limits.accent_card_area_max_px", r"to ([\d,]+) px of area", proposed_block(tweaks, "Accent-filled cards").replace(",", "")) if in_force["accent_cards"] else None),
        "length_s": {"default": length_default, "list": length_list},
        "three_d": {"scenes": ["hook", "end"],
                    "max_objects": grab_num("limits.three_d.max_objects", r"\*\*3D:\*\* hook and end card only, at most (\d+) objects on screen", tweaks),
                    "flat_cards_in_perspective_everywhere": in_force["three_d_cards"]},
        "caption": {"words_per_chunk": grab_nums("limits.caption.words_per_chunk", r"(\d+) to (\d+) words per chunk", style, (1, 2)),
                    "emphasis_per_chunk": grab_nums("limits.caption.emphasis_per_chunk", r"Emphasis: (\d+) to (\d+) key words per chunk", style, (1, 2))},
    }
    grab("limits.set_pieces_per_reel", r"\*\*Set pieces:\*\* one or two per reel", style, 0)
    limits["set_pieces_per_reel"] = [1, 2]

    branding = {
        "lockup_min_width": grab_num("branding.lockup_min_width", r"at least (\d+)px wide, with clear space around it", tweaks),
        "bolt_min_height": grab_num("branding.bolt_min_height", r"Bolt at least (\d+)px tall", tweaks),
        "light_variants": "gradient or black", "dark_variants": "gradient or white",
        "cta": {"dm_sender": "FlashFX", "dm_avatar": "mark/avatar-dark.png", "lockup_on_light": "lockup-gradient-on-light.png",
                "lockup_on_dark": "lockup-gradient-on-dark.png"},
    }

    motion["grammar"] = grammar_tokens(zones, canvas, type_scale)
    energy = energy_tokens(energy_json, tweaks)

    open_questions = {
        "1": f"caption center y {caption_y}: tweaks.md Caption box line in force" + ("" if not in_force["caption_position"] else " (the accepted proposal)"),
        "2": f"caption line at most {caption_max_w}px wide (x {caption_x0} to {caption_x1}): tweaks.md Right side line in force",
        "3": "scene change B: an animated exit (fade with blur, 4 frames, or a fall or push) then the next scene enters: both look refs",
        "4": "end-card keyword typed, 2 frames per letter: both look refs",
        "5": f"kicker top y {kicker_top}: v02",
        "6": f"kicker cap {type_scale['kicker']['cap_px']}px: v02",
        "7": f"dot spacing {shapes['dots']['spacing_px']}px: v02 (54 in v01, v03, v07, v08 is 4 videos, under the 5 of 7)",
        "8": f"lower-right glow warm {colors['glow-lower']}: v02",
        "9": "no doodles: v02",
        "10": "hero cards straight; only fans, stacks and the end card tilt: v02",
        "11": "headline word by word, 3 frames per word, plain fade: both look refs",
        "12": "caption words plain fade, 4 frames: both look refs",
        "13": "honesty labels kept, a small light chip: DECISIONS.md 33",
        "14": "no second color: v02",
        "15": "true peak ceiling -1.5 dBTP: BUILD_SPEC.md S8 and S11",
    }

    tokens = {
        "style": STYLE_NAME,
        "style_version": 2,
        "tokens_version": TOKENS_VERSION,
        "generated": dt.date.today().isoformat(),
        "sources": {"style.md": sha1(style_raw), "tweaks.md": sha1(tweaks_raw), "energy.json": energy_hash(energy_json)},
        "in_force": in_force,
        "canvas": canvas,
        "colors": colors,
        "fonts": fonts,
        "type": type_scale,
        "zones": zones,
        "shapes": shapes,
        "motion": motion,
        "transitions": transitions,
        "pacing": pacing,
        "limits": limits,
        "branding": branding,
        "energy": energy,
        "tracker": {"enabled": False},
        "honesty_labels": {"enabled": True, "look": "light chip", "texts": {"mock": "illustrative", "sourced": "real"}},
        "doodles": False,
        "hero_tilt": False,
        "second_color": None,
        "beat_map": BEAT_TYPES,
        "style_beat_map": beat_table(style),
        "open_questions": open_questions,
    }
    return tokens


# ----------------------------------------------------------------------------------------------- CSS

def css_text(tokens: dict) -> str:
    """The tokens as CSS custom properties (motion-lib/assets/tokens.css), generated: do not edit."""
    lines = ["/* tokens.css: generated by pipeline/bin/build-tokens from styles/paper-cards/tokens.json. Do not edit. */",
             ":root {"]
    for name, hexv in tokens["colors"].items():
        lines.append(f"  --c-{name}: {hexv};")
    for key, font in tokens["fonts"].items():
        lines.append(f"  --font-{key}: \"{font['family']}\";")
        lines.append(f"  --font-{key}-weight: {font['weight']};")
        lines.append(f"  --font-{key}-cap: {font['cap_ratio']};")
    t = tokens["type"]
    lines += [
        f"  --caption-font: {t['caption']['font_px']}px;",
        f"  --caption-cap: {t['caption']['cap_px']}px;",
        f"  --headline-font: {t['headline']['font_px']}px;",
        f"  --headline-line: {t['headline']['line_px']}px;",
        f"  --kicker-cap: {t['kicker']['cap_px']}px;",
        f"  --stat-font: {t['stat']['font_px']}px;",
        f"  --end-verb-font: {t['end_verb']['font_px']}px;",
        f"  --end-keyword-font: {t['end_keyword']['font_px']}px;",
        f"  --handwritten-font: {t['handwritten']['font_px']}px;",
        f"  --handwritten-line: {t['handwritten']['line_px']}px;",
    ]
    s = tokens["shapes"]
    z = tokens["zones"]
    lines += [
        f"  --card-radius: {s['card']['radius']}px;",
        f"  --card-edge: {s['card']['edge_px'][1]}px;",
        f"  --card-shadow: 0 {s['card']['shadow']['css_offset_y']}px {s['card']['shadow']['css_blur']}px var(--c-shadow-dark);",
        f"  --media-frame: {s['media_frame_px']}px;",
        f"  --stat-pill-h: {s['stat_pill_h']}px;",
        f"  --stat-chip-h: {s['stat_chip_h']}px;",
        f"  --dark-chip-h: {s['dark_chip_h']}px;",
        f"  --light-chip-h: {s['light_chip_h']}px;",
        f"  --emphasis-h: {s['emphasis_box']['height']}px;",
        f"  --emphasis-radius: {s['emphasis_box']['radius']}px;",
        f"  --emphasis-gap: {s['emphasis_box']['gap']}px;",
        f"  --mascot-w: {s['mascot']['w']}px;",
        f"  --mascot-h: {s['mascot']['h']}px;",
        f"  --dot-size: {s['dots']['size_px']}px;",
        f"  --dot-spacing: {s['dots']['spacing_px']}px;",
        f"  --margin-x: {z['margin_x']}px;",
        f"  --safe-top: {z['safe_top']}px;",
        f"  --kicker-top: {z['kicker_top']}px;",
        f"  --caption-y: {z['caption']['center_y']}px;",
        f"  --caption-max-w: {z['caption']['max_width']}px;",
        f"  --end-card-w: {z['end_card']['width']}px;",
        f"  --end-card-x: {z['end_card']['x']}px;",
        f"  --end-card-top: {z['end_card']['top']}px;",
        f"  --end-card-tilt: {z['end_card']['tilt_deg']}deg;",
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
            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 30)};",
            f"  --m-room-life-s: {h.get('room_life_s', 8)};",
        ]
        zn = tokens.get("zones") or {}
        rail = zn.get("right_rail") or {}
        lines += [  # the safe edges, for the hold's room (pc-motion.js PCM.room)
            f"  --m-safe-top: {zn.get('safe_top', 230):g};",
            f"  --m-safe-bottom: {zn.get('safe_bottom', 1440):g};",
            f"  --m-margin-x: {zn.get('margin_x', 60):g};",
            f"  --m-rail-x: {1080 - float(rail.get('width', 230)):g};",
            f"  --m-rail-from-y: {float(rail.get('from_y', 960)):g};",
        ]
        for name, zb in g.get("text_zones", {}).items():
            lines.append(f"  --m-zone-{name}: {zb['x']:g} {zb['y']:g} {zb['w']:g} {zb['h']:g};")
    lines += ["}", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------- verify

def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}.{i}")
    else:
        yield path, obj


def exempt(path: str) -> bool:
    for pat in EXEMPT:
        parts = pat.split(".")
        got = path.split(".")
        if len(got) < len(parts):
            continue
        if all(p == "*" or p == g for p, g in zip(parts, got)):
            return True
    return False


def number_variants(v: float | int) -> set[str]:
    out = set()
    if isinstance(v, bool):
        return out
    f = float(v)
    s = f"{f:.3f}".rstrip("0").rstrip(".")
    out.add(s)
    if f.is_integer():
        out.add(str(int(f)))
        out.add(f"{int(f):,}")
    return out


def verify_tokens(tokens: dict, style: str, tweaks: str) -> list[str]:
    both = style + "\n" + tweaks
    found = re.findall(r"\d+(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", both)
    numbers = {n.replace(",", "") for n in found}
    numbers |= {n.rstrip("0").rstrip(".") if "." in n else n for n in numbers}
    hexes = {h.upper() for h in re.findall(HEX, both)}
    problems = []
    for path, value in walk(tokens):
        if exempt(path) or value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            if not (number_variants(abs(value)) & numbers):
                problems.append(f"{path} = {value}: not in style.md or tweaks.md")
        elif isinstance(value, str) and re.fullmatch(HEX, value):
            if value.upper() not in hexes:
                problems.append(f"{path} = {value}: not in style.md or tweaks.md")
    return problems


# ----------------------------------------------------------------------------------------------- commands

def load_sources(style_dir: str) -> tuple[str, str]:
    style_path = os.path.join(style_dir, "style.md")
    tweaks_path = os.path.join(style_dir, "tweaks.md")
    for p in (style_path, tweaks_path):
        if not os.path.isfile(p):
            raise TokenError(f"missing source file {p}")
    return read(style_path), read(tweaks_path)


def energy_json_path(style_dir: str) -> str:
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
    if not os.path.isfile(tokens_path):
        return False, "tokens.json is missing"
    try:
        with open(tokens_path, encoding="utf-8-sig") as f:
            old = json.load(f)
    except (OSError, ValueError):
        return False, "tokens.json cannot be read"
    if old.get("tokens_version") != TOKENS_VERSION:
        return False, f"the builder changed (tokens_version {old.get('tokens_version')} to {TOKENS_VERSION})"
    src = old.get("sources", {})
    if src.get("style.md") != sha1(style):
        return False, "style.md changed"
    if src.get("tweaks.md") != sha1(tweaks):
        return False, "tweaks.md changed"
    if (src.get("energy.json") or "") != energy_hash(energy_json):
        return False, "the energy calibration changed"
    return True, "unchanged"


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def cmd_build(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    energy_json = load_energy_json(a.style_dir)
    ok, reason = current(a.out, style, tweaks, energy_json)
    css_missing = bool(a.css) and not os.path.isfile(a.css)
    if ok and not a.force and not css_missing:
        print(json.dumps({"rebuilt": False, "reason": reason, "out": a.out}))
        return 0
    tokens = build_tokens(style, tweaks, a.fonts_dir, energy_json)
    problems = verify_tokens(tokens, style, tweaks)
    if problems:
        for p in problems:
            print(f"tokens: {p}", file=sys.stderr)
        return 2
    if ok and not a.force:
        # only the CSS was missing: keep the file's generated date
        with open(a.out, encoding="utf-8-sig") as f:
            tokens = json.load(f)
    else:
        write_json(a.out, tokens)
    if a.css:
        write_text(a.css, css_text(tokens))
    print(json.dumps({"rebuilt": not (ok and not a.force), "reason": "forced" if a.force else reason if not ok else "css missing",
                      "out": a.out, "css": a.css or ""}))
    return 0


def cmd_check(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    ok, reason = current(a.tokens, style, tweaks, load_energy_json(a.style_dir))
    print(("tokens.json is current" if ok else "tokens.json needs a rebuild") + f" ({reason})")
    return 0 if ok else 1


def cmd_verify(a) -> int:
    style, tweaks = load_sources(a.style_dir)
    with open(a.tokens, encoding="utf-8-sig") as f:
        tokens = json.load(f)
    problems = verify_tokens(tokens, style, tweaks)
    for p in problems:
        print(p)
    if not problems:
        print("tokens.json: every number and color appears in style.md or tweaks.md")
    return 1 if problems else 0


def cmd_css(a) -> int:
    with open(a.tokens, encoding="utf-8-sig") as f:
        tokens = json.load(f)
    write_text(a.out, css_text(tokens))
    print(a.out)
    return 0


def main(argv: list[str]) -> int:
    setup_streams()
    ap = argparse.ArgumentParser(prog="tokens.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--style-dir", required=True); b.add_argument("--out", required=True)
    b.add_argument("--css"); b.add_argument("--fonts-dir"); b.add_argument("--force", action="store_true"); b.set_defaults(fn=cmd_build)
    c = sub.add_parser("check"); c.add_argument("--style-dir", required=True); c.add_argument("--tokens", required=True); c.set_defaults(fn=cmd_check)
    v = sub.add_parser("verify"); v.add_argument("--style-dir", required=True); v.add_argument("--tokens", required=True); v.set_defaults(fn=cmd_verify)
    s = sub.add_parser("css"); s.add_argument("--tokens", required=True); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_css)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except TokenError as exc:
        print(f"tokens: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
