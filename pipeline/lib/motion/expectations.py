"""pipeline/lib/motion/expectations.py: what frame-match measures for every component and the numbers it must hit.

Every number comes from styles/paper-cards/vocabulary.md (the item in brackets) and style.md Motion, through
tokens.json where the style keeps it. Tolerances: 1 frame on timings, 10 percent on distances and overshoots
(DECISIONS.md 29). Each entry:
  props      the props the component is mounted with for the measurement (the move starts at 0 unless noted)
  frames     how many frames the move's own checks need from 0 (frame-match measures at least 4 s for the life checks)
  selectors  the elements measured every frame
  checks     a list of checks; kinds:
     enter    {selector, at, opacity_frames, position_frames, rise}      the card move (1): fade frames, settle frames, rise px
     pop      {selector, at, frames, overshoot}                          the pop (8): peak overshoot and total frames
     count    {selector, at, frames, text}                               the count-up (2): first frame the text is final
     typing   {selector, at, frames_per_char, chars}                     typed text: frames per character
     fade     {selector, at, frames}                                     opacity 0 to 1 over frames
     fly      {selector, at, frames, distance, axis}                     the fly-in (16): distance and settle frames
     exit     {selector, at, frames, mode: gone|fade}                    an exit: frames until gone or faded
     grow     {selector, at, frames, axis}                               a bar or line growing (width or height)
     stagger  {selectors, gap_frames}                                    first visible frames, gap between neighbours
     after    {selector, ref_selector, delay_frames}                     one element appears N frames after another settles
     canvas   {}                                                         the paper canvas: renders without errors, its layers exist
     webgl    {}                                                         a 3D component: a WebGL context (a warning without one)
  strips     reference 30 fps strips (relative to styles/paper-cards/analysis) that show the same move, for the
             change-curve correlation (DECISIONS.md 29); missing files are skipped
  still_at   the time of the gallery still (s)
  life       the Motion and energy rules checks (M14, E1): {selector: the main element, at: when its life starts,
             pixels: True when the element draws itself (a canvas), skip: [selectors left out of the static check]}.
             frame-match adds, for every component: never static (no 0.5 s window without motion on any visible
             tracked element, and in the rendered pixels), the inertia lasting 2 to 4 s after the landing, and the
             hold at the calm speed or more.
"""
from __future__ import annotations

from motion import common


HOLD = {"hold": "normal"}


def build(tokens: dict) -> dict:
    m = tokens["motion"]
    enter = m["enter"]
    pop = m["pop"]
    count_frames = m["count_up"]["frames"]
    cap = m["caption"]
    ec = m["end_card"]
    tr = tokens["transitions"]
    type_letter = m["typing_frames_per_letter"]
    mascot = m["mascot"]
    headline_wf = m["headline"]["word_frames"]
    E = {}

    E["paper-canvas"] = dict(props={"seed": 7, "duration": 90}, frames=6, selectors=["#paper-edges", "#paper-edge-0", "#paper-edge-1", "#paper-edge-2", "#paper-edge-3", "#paper-ambient-0", "#paper-ambient-1", "#paper-ambient-2"],
                             checks=[{"kind": "canvas"}], strips=[], still_at=1.0,
                             life={"selector": "#paper-edge-0", "at": 0, "skip": ["#paper-edges"], "no_inertia": True})

    E["card"] = dict(
        props={"mascot": "star"}, frames=24, selectors=["#card-box", "#card-mascot"],
        checks=[{"kind": "enter", "selector": "#card-box", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "after", "selector": "#card-mascot", "ref_selector": "#card-box", "delay_frames": mascot["delay_frames"]},
                {"kind": "fade", "selector": "#card-mascot", "at": common.frames(enter["position_frames"] + mascot["delay_frames"]), "frames": mascot["frames"]}],
        strips=["v03/extra/s30_hook_000.0.png", "v06/extra/s30_001.0_card.png", "v07/extra/s30_000.0_hook.png"], still_at=1.2,
        life={"selector": "#card-box", "at": 0})

    E["stat-number"] = dict(
        props={"icon": "download"}, frames=48, selectors=["#stat-wrap", "#stat-num"],
        checks=[{"kind": "enter", "selector": "#stat-wrap", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "count", "selector": "#stat-num", "at": common.frames(enter["position_frames"]), "frames": count_frames, "text": "1,134,112"}],
        strips=["v08/extra/s30_007.8_countup.png", "v03/extra/s30_count_044.9.png", "v04/extra/s30_count_f925.png"], still_at=1.4,
        life={"selector": "#stat-wrap", "at": 0})

    E["end-card"] = dict(
        props={"lockup": "assets/brand/lockup/lockup-gradient-on-light.png"}, frames=70, selectors=["#ec-card", "#ec-verb", "#ec-pill", "#ec-keyword", "#ec-lines", "#ec-row", "#ec-lockup", "#ec-mascot-0"],
        checks=[{"kind": "fade", "selector": "#ec-card", "at": 0, "frames": ec["fade_frames"]},
                {"kind": "stagger", "selectors": ["#ec-card", "#ec-verb", "#ec-pill", "#ec-lines"], "gap_frames": ec["stagger_frames"]},
                {"kind": "typing", "selector": "#ec-keyword", "at": common.frames(2 * ec["stagger_frames"] + ec["fade_frames"]), "frames_per_char": type_letter, "chars": 5}],
        strips=["v02/extra/s30_cta43.png", "v07/extra/s30_041.0_end.png", "v08/extra/s30_038.9_end.png", "v09/extra/s30_049.7_end.png"], still_at=2.4,
        life={"selector": "#ec-card", "at": 0, "skip": ["#ec-row", "#ec-keyword"]})

    E["mascot"] = dict(
        props={"x": 500, "y": 900, "scale": 3, "move": "rise"}, frames=12, selectors=["#ms-wrap"],
        checks=[{"kind": "fade", "selector": "#ms-wrap", "at": 0, "frames": mascot["frames"]}],
        strips=["v02/extra/s30_hook.png", "v08/extra/s30_000.8_mascot_title.png"], still_at=0.6,
        life={"selector": "#ms-wrap", "at": 0})

    E["dark-chip"] = dict(
        props={"icon": "clock"}, frames=12, selectors=["#chip"],
        checks=[{"kind": "pop", "selector": "#chip", "at": 0, "frames": 3, "overshoot": pop["overshoot_pill_pct"][1] / 100, "overshoot_range": [pop["overshoot_pill_pct"][0] / 100, pop["overshoot_pill_pct"][1] / 100]}],
        strips=["v01/extra/s30_sc05.png", "v07/extra/s30_004.4_caption_tag.png"], still_at=0.5,
        life={"selector": "#chip", "at": 0})

    E["light-chip"] = dict(
        props={}, frames=12, selectors=["#lchip"],
        checks=[{"kind": "fade", "selector": "#lchip", "at": 0, "frames": 4}],
        strips=["v03/extra/s30_label_042.4.png"], still_at=0.5,
        life={"selector": "#lchip", "at": 0})

    E["caption-line"] = dict(
        props={}, frames=90, selectors=["#cap-c0", "#cap-c0-w0", "#cap-c0-w2", "#cap-c0-w2-box", "#cap-c1", "#cap-c1-w0"],
        checks=[{"kind": "fade", "selector": "#cap-c0-w0", "at": 0.2, "frames": cap["word_frames"]},
                {"kind": "fade", "selector": "#cap-c0-w2", "at": 0.7, "frames": cap["word_frames"]},
                {"kind": "exit", "selector": "#cap-c0", "at": 1.4 - common.frames(cap["replace_out_frames"] + 1), "frames": cap["replace_out_frames"], "mode": "fade"},
                {"kind": "after", "selector": "#cap-c1-w0", "ref_selector": "#cap-c0", "delay_frames": 1, "ref_mode": "gone"}],
        strips=["v03/extra/s30_capswap_008.0.png", "v01/extra/s30_sc18.png", "v06/extra/s30_031.0_highlight.png"], still_at=1.1,
        life={"selector": "#cap-c0", "at": 0.2, "no_inertia": True, "skip": ["#cap-c1", "#cap-c0-w0", "#cap-c0-w2", "#cap-c0-w2-box", "#cap-c1-w0"]})

    E["dm-card"] = dict(
        props={"avatar": "assets/brand/mark/avatar-dark.png", "y": 700}, frames=20, selectors=["#dm"],
        checks=[{"kind": "enter", "selector": "#dm", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]}],
        strips=["v03/extra/s30_hook_000.0.png", "v06/extra/s30_001.0_card.png"], still_at=0.8,
        life={"selector": "#dm", "at": 0})

    E["pop"] = dict(
        props={"kind": "tile", "icon": "bolt", "overshoot": pop["overshoot_icon_pct"][0] / 100, "frames": 14}, frames=24, selectors=["#pop-el"],
        checks=[{"kind": "pop", "selector": "#pop-el", "at": 0, "frames": 14, "overshoot": pop["overshoot_icon_pct"][0] / 100, "overshoot_range": [pop["overshoot_icon_pct"][0] / 100, pop["overshoot_icon_pct"][1] / 100]}],
        strips=["v08/extra/s30_003.8_logo_chain.png", "v03/extra/s30_cta_058.0.png", "v09/extra/s30_002.3_stickers.png"], still_at=0.8,
        life={"selector": "#pop-el", "at": 0})

    E["check-badge"] = dict(
        props={"size": 120, "x": 480}, frames=24, selectors=["#cb-badge"],
        checks=[{"kind": "pop", "selector": "#cb-badge", "at": 0, "frames": 12, "overshoot": pop["overshoot_icon_pct"][1] / 100, "overshoot_range": [pop["overshoot_icon_pct"][0] / 100, pop["overshoot_icon_pct"][1] / 100]}],
        strips=["v07/extra/s30_035.6_checks.png", "v06/extra/s30_065.6_ticks.png", "v04/extra/s30_check_f1200.png", "v03/extra/s30_cta_058.0.png"], still_at=0.7,
        life={"selector": "#cb-badge", "at": 0})

    E["window-card"] = dict(
        props={"image": "assets/demo/plugin-page.png", "mascot": "play", "honesty": "sourced"}, frames=24, selectors=["#wc", "#wc-mascot"],
        checks=[{"kind": "enter", "selector": "#wc", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "after", "selector": "#wc-mascot", "ref_selector": "#wc", "delay_frames": mascot["delay_frames"]}],
        strips=["v07/extra/s30_011.4_window_rise.png", "v01/extra/s30_hook.png", "v03/extra/s30_hook_000.0.png"], still_at=1.2,
        life={"selector": "#wc", "at": 0})

    E["terminal-card"] = dict(
        props={}, frames=120, selectors=["#tc", "#tc-line-0", "#tc-line-1"],
        checks=[{"kind": "enter", "selector": "#tc", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "typing", "selector": "#tc-line-0", "at": common.frames(enter["position_frames"] + 8), "frames_per_char": 0.5, "chars": 58}],
        strips=["v04/extra/s30_rewrite_f982.png", "v06/extra/s30_070.9_typing_tail.png"], still_at=2.2,
        life={"selector": "#tc", "at": 0, "skip": ["#tc-line-1"]})

    E["chart-card"] = dict(
        props={}, frames=40, selectors=["#cc", "#cc-bar-0", "#cc-bar-1", "#cc-bar-3", "#cc-val-3"],
        checks=[{"kind": "enter", "selector": "#cc", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "grow", "selector": "#cc-bar-0", "at": common.frames(enter["position_frames"]), "frames": 12, "axis": "h"},
                {"kind": "stagger", "selectors": ["#cc-bar-0", "#cc-bar-1"], "gap_frames": 2, "mode": "grow"}],
        strips=["v04/extra/s30_bars_f1426.png", "v06/extra/s30_048.0_bars.png"], still_at=1.3,
        life={"selector": "#cc", "at": 0})

    E["thumb-grid"] = dict(
        props={}, frames=30, selectors=["#tg-wrap", "#tg-card-0", "#tg-card-1", "#tg-card-2", "#tg-card-3"],
        checks=[{"kind": "fade", "selector": "#tg-card-0", "at": 0, "frames": 4},
                {"kind": "stagger", "selectors": ["#tg-card-0", "#tg-card-1", "#tg-card-2"], "gap_frames": 1},
                {"kind": "stagger", "selectors": ["#tg-card-0", "#tg-card-3"], "gap_frames": 7}],
        strips=["v02/extra/s30_grid34.png", "v04/extra/s30_deckgrid_f420.png", "v04/extra/s30_gridsettle_f444.png"], still_at=0.9,
        life={"selector": "#tg-card-0", "at": 0, "no_inertia": True})

    E["logo-tile"] = dict(
        props={"image": "assets/brand/mark/mark-gradient.png", "second_image": "assets/brand/mark/mark-black.png", "x": 366}, frames=40, selectors=["#lt-main", "#lt-second"],
        checks=[{"kind": "pop", "selector": "#lt-main", "at": 0, "frames": 14, "overshoot": pop["overshoot_icon_pct"][0] / 100, "overshoot_range": [pop["overshoot_icon_pct"][0] / 100, pop["overshoot_icon_pct"][1] / 100]},
                {"kind": "fly", "selector": "#lt-second", "at": common.frames(17), "frames": 9, "distance": 188, "axis": "x", "overshoot": 6}],
        strips=["v08/extra/s30_003.8_logo_chain.png", "v02/extra/s30_hook.png"], still_at=1.2,
        life={"selector": "#lt-main", "at": 0})

    E["strike-through"] = dict(
        props={}, frames=70, selectors=["#st-text", "#st-line", "#st-replacement"],
        checks=[{"kind": "grow", "selector": "#st-line", "at": 0.5, "frames": 4, "axis": "w"},
                {"kind": "typing", "selector": "#st-replacement", "at": 0.5 + common.frames(4 + 2), "frames_per_char": 2, "chars": 15}],
        strips=["v04/extra/s30_strike_f1007.png", "v06/extra/s30_062.3_xstamp.png"], still_at=1.6,
        life={"selector": "#st-text", "at": 0, "skip": ["#st-replacement", "#st-line"]})

    E["fly-in"] = dict(
        props={"mascot": "film"}, frames=30, selectors=["#fi", "#fi-mascot"],
        checks=[{"kind": "fly", "selector": "#fi", "at": 0, "frames": 14, "distance": 930, "axis": "y"},
                {"kind": "after", "selector": "#fi-mascot", "ref_selector": "#fi", "delay_frames": mascot["delay_frames"], "ref_frames": 14}],
        strips=["v08/extra/s30_000.0_hook.png", "v07/extra/s30_011.4_window_rise.png", "v01/extra/s30_hook.png"], still_at=0.8,
        life={"selector": "#fi", "at": 0})

    E["chat-card"] = dict(
        props={}, frames=110, selectors=["#chat", "#chat-input", "#chat-send", "#chat-reply"],
        checks=[{"kind": "enter", "selector": "#chat", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "typing", "selector": "#chat-input", "at": 0.4, "frames_per_char": 1.15, "chars": 53}],
        strips=["v07/extra/s30_004.4_caption_tag.png", "v06/extra/s30_070.9_typing_tail.png"], still_at=2.6,
        life={"selector": "#chat", "at": 0, "skip": ["#chat-reply"]})

    E["progress-bar"] = dict(
        props={}, frames=40, selectors=["#pb", "#pb-fill", "#pb-check"],
        checks=[{"kind": "enter", "selector": "#pb", "at": 0, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]},
                {"kind": "grow", "selector": "#pb-fill", "at": 0.5, "frames": 6, "axis": "w"},
                {"kind": "pop", "selector": "#pb-check", "at": 0.5 + common.frames(5), "frames": 3, "overshoot": pop["overshoot_icon_pct"][1] / 100}],
        strips=["v01/extra/s30_card33.png"], still_at=1.0,
        life={"selector": "#pb", "at": 0})

    E["camera-move"] = dict(
        props={"image": "assets/demo/repo.png"}, frames=40, selectors=["#cm-stage", "#cm-window"],
        checks=[{"kind": "shrink", "selector": "#cm-stage", "at": 0.6, "frames": 8, "scale": min(780 / 1080, 880 / 1920)}],
        strips=["v02/extra/s30_zoom27.png", "v05/extra/s30_windowshrink_f520.png"], still_at=1.2,
        life={"selector": "#cm-stage", "at": 0.6, "land_frames": 8, "no_inertia": True, "skip": ["#cm-stage"]})

    E["exit-move"] = dict(
        props={}, frames=50, selectors=["#xm-leaving", "#xm-next"],
        checks=[{"kind": "exit", "selector": "#xm-leaving", "at": 0.8, "frames": tr["fall_frames"], "mode": "gone"},
                {"kind": "enter", "selector": "#xm-next", "at": 0.8, "opacity_frames": enter["opacity_frames"], "position_frames": enter["position_frames"], "rise": enter["rise_px"]}],
        strips=["v07/extra/s30_003.2_badge_exit.png", "v07/extra/s30_034.7_exit_counter.png", "v08/extra/s30_010.6_scatter.png"], still_at=0.5,
        life={"selector": "#xm-next", "at": 0.8})

    E["headline"] = dict(
        props={"kicker_mark": "assets/brand/mark/mark-gradient.png"}, frames=60, selectors=["#hl-mark", "#hl-kicker", "#hl-lines"] + [f"#hl-lines .pc-word:nth-child({i})" for i in (1, 2, 3)],
        checks=[{"kind": "visible_at_zero", "selector": "#hl-mark"},
                {"kind": "stagger", "selectors": ["#hl-lines .pc-word:nth-child(1)", "#hl-lines .pc-word:nth-child(2)", "#hl-lines .pc-word:nth-child(3)"], "gap_frames": headline_wf},
                {"kind": "fade", "selector": "#hl-lines .pc-word:nth-child(1)", "at": 0.5, "frames": headline_wf}],
        strips=["v02/extra/s30_hook.png", "v01/extra/s30_hook.png", "v03/extra/s30_hook_000.0.png"], still_at=2.2,
        life={"selector": "#hl-lines", "at": 0, "no_inertia": True, "skip": ["#hl-mark"] + [f"#hl-lines .pc-word:nth-child({i})" for i in (1, 2, 3)]})

    E["handwritten-callout"] = dict(
        props={}, frames=24, selectors=["#hc-wrap", "#hc-arrow"],
        checks=[{"kind": "fade", "selector": "#hc-wrap", "at": 0, "frames": 6}],
        strips=[], still_at=0.8,
        life={"selector": "#hc-wrap", "at": 0})

    E["speech-bubble"] = dict(
        props={"keyword": "TELLS"}, frames=40, selectors=["#sb", "#sb-pill"],
        checks=[{"kind": "bubble", "selector": "#sb", "at": 0, "frames": 7, "overshoot_y": 40, "settle_frames": 9},
                {"kind": "pop", "selector": "#sb-pill", "at": common.frames(7 + 4), "frames": 7, "overshoot": pop["overshoot_pill_pct"][1] / 100, "overshoot_range": [pop["overshoot_pill_pct"][0] / 100, pop["overshoot_pill_pct"][1] / 100]}],
        strips=["v07/extra/s30_041.0_end.png", "v08/extra/s30_038.9_end.png"], still_at=0.9,
        life={"selector": "#sb", "at": 0, "land_frames": 16, "no_inertia": True})

    E["table-card"] = dict(
        props={}, frames=24, selectors=["#tb", "#tb-row-0", "#tb-row-1"],
        checks=[{"kind": "enter", "selector": "#tb", "at": 0, "opacity_frames": 5, "position_frames": 7, "rise": 28},
                {"kind": "stagger", "selectors": ["#tb-row-0", "#tb-row-1"], "gap_frames": 3}],
        strips=["v04/extra/s30_scene_f184.png"], still_at=0.9,
        life={"selector": "#tb", "at": 0})

    E["hero-3d"] = dict(
        props={"label": "the skill file", "enter_at": 0.2}, frames=40, selectors=["#h3-shadow", "#h3-canvas", "#h3-label"],
        checks=[{"kind": "fade", "selector": "#h3-shadow", "at": 0.2, "frames": 12}, {"kind": "webgl"}],
        strips=[], still_at=1.5,
        life={"selector": "#h3-shadow", "at": 0.2, "pixels": True, "no_inertia": True})

    E["icon-3d"] = dict(
        props={"icon": "bolt", "enter_at": 0.2}, frames=40, selectors=["#i3-shadow", "#i3-canvas", "#i3-stage"],
        checks=[{"kind": "fade", "selector": "#i3-shadow", "at": 0.2, "frames": 12}, {"kind": "webgl"}],
        strips=[], still_at=1.5,
        life={"selector": "#i3-shadow", "at": 0.2, "pixels": True, "no_inertia": True, "skip": ["#i3-stage"]})

    return E
