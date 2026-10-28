"""pipeline/lib/motion/catalog.py: motion-lib/catalog.json, the library's index for the visual director (S9), the
builder (S10) and the sound pass (S11): per component its name, the vocabulary item, what it does, the props (read
from the file's declared variables), the beat types that may use it (tokens.json beat_map), the sound events with
their frame offsets and cue types (pipeline/lib/sfx/common.py CUE_TYPES), the demo props of the showreel and the
gallery, the preview still and the frame-match result.

  python pipeline/lib/motion catalog            check: every component file has an entry and the other way round,
                                                 the props match the declarations, the demo props and sound cues are known
  python pipeline/lib/motion catalog --write    regenerate catalog.json from the files and META (keeps frame_match)
"""
from __future__ import annotations

import datetime as dt
import os

from motion import common

CUE_TYPES = ["transition_slow", "transition_fast", "attention", "hero_enter", "ui_click", "stamp", "number", "success", "typing",
             "negative", "hook_hit", "notification"]

# What the files cannot say about themselves. Frame offsets are from the component's start with its default timing props
# (enter_at 0); a string is a formula over the props. `cue` is the sound the event takes in S11 when the rules of
# BUILD_SPEC.md S11 agree (null: a visual change with no sound of its own, an attention candidate).
META = {
    "paper-canvas": dict(item=None, name="Paper canvas", kind="canvas", z=0, demo={"seed": 7, "duration": 90}, demo_duration=None, measure="#paper-edges",
                         does="The background of every reel: paper, a warm glow top left, a warm glow lower right, darker bottom corners, a dot grid, and from M14 the life of Motion and energy rules E5 and E7: an edge filler layer (soft cards, chips, thumbnails, shapes and stars 30 to 70 percent outside the left and right borders, at most 20 px per second, no text) and an ambient layer (stars, dots and small clouds drifting and twinkling), both seeded per reel (the seed and duration props) and kept out of every text zone. Mounted for the whole reel at z 0.",
                         events=[]),
    "card": dict(item=1, name="Card enter", kind="card", z=2, demo={"mascot": "star", "exit": "fade-blur", "exit_at": 2.6}, demo_duration=3, measure="#card-box",
                 does="A surface card with an optional title, body and image. The default move for anything new: opacity 0 to 1 over 5 frames, y +38 to 0 over 8 frames, expo.out.",
                 events=[{"event": "enter", "frame": 0, "cue": "hero_enter", "note": "only when the card is the scene's hero"}, {"event": "land", "frame": 8, "cue": None},
                         {"event": "mascot", "frame": 12, "cue": None, "note": "when the mascot prop is set"}, {"event": "exit", "frame": "exit_at x 30", "cue": "transition", "note": "when exit is set"}]),
    "stat-number": dict(item=2, name="Stat number with count-up", kind="card", z=2, demo={"icon": "download"}, demo_duration=3, measure="#stat-wrap",
                        does="A number that proves the point, counting from 0 with ease-out over 27.5 frames after its pill (168 tall, icon, unit in accent) or chip (141 tall, serif unit, sub-label) entered.",
                        events=[{"event": "enter", "frame": 0, "cue": "hero_enter", "note": "a giant number is a hero"}, {"event": "land", "frame": 8, "cue": None},
                                {"event": "count_start", "frame": "8 + count_delay_frames", "cue": "number"}, {"event": "count_end", "frame": "8 + count_delay_frames + count_frames", "cue": None}]),
    "end-card": dict(item=3, name="Keyword end card", kind="cta", z=2, demo={"lockup": "assets/brand/lockup/lockup-gradient-on-light.png"}, demo_duration=5, measure="#ec-card",
                     does="The CTA: a tilted surface card with the verb and the keyword pill (typed, 2 frames per letter), two handwritten lines, five mascots walking in, the FlashFX lockup under them (at least 300 px wide). Elements fade in over 6 frames, 6 apart, top to bottom; the card wobbles slightly.",
                     events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "land", "frame": 6, "cue": None},
                             {"event": "typing", "frame": "2 x stagger_frames + fade_frames (18)", "duration_frames": "len(keyword) x type_frames", "cue": "typing"},
                             {"event": "mascots", "frame": "4 x stagger_frames (24)", "cue": None}, {"event": "lockup", "frame": "after the typing", "cue": None}]),
    "mascot": dict(item=4, name="Mascot", kind="support", z=3, demo={"x": 500, "y": 900, "scale": 3, "move": "hop", "enter_at": 0.3}, demo_duration=3, measure="#ms-wrap",
                   does="The recurring pixel creature (85 x 58) with one prop, perched on a corner of the scene's main element; enters 4 frames after the card lands, rising over 4 frames; hops, pops or walks on the end card.",
                   events=[{"event": "mascot", "frame": 0, "cue": None}]),
    "dark-chip": dict(item=5, name="Dark chip or tag", kind="label", z=3, demo={"enter_at": 0.3, "icon": "clock"}, demo_duration=3, measure="#chip",
                      does="A short fact or label attached to a card: ink-chip fill, white text with one accent word, 55 tall; pops in over 3 frames.",
                      events=[{"event": "pop", "frame": 0, "cue": "ui_click"}]),
    "light-chip": dict(item=6, name="Light pill or chip", kind="label", z=3, demo={"enter_at": 0.3}, demo_duration=3, measure="#lchip",
                       does="A label inside or above a card: surface fill, ink text, 67 tall; fades in over 4 frames with a small drift.",
                       events=[{"event": "enter", "frame": 0, "cue": "ui_click"}]),
    "caption-line": dict(item=7, name="Caption line", kind="captions", z=5, demo={}, demo_duration=3, measure="#cap-layer",
                         does="The spoken words, one chunk of 1 to 4 words at a time, bare ink words centered at cap center y 1480, at most 620 px wide; each word fades in over 4 frames when spoken, emphasis words on accent boxes rising 9 px; the old chunk fades out over 2 frames, the next word on the following frame. Mounted once per reel over the body beats.",
                         events=[{"event": "caption_word", "frame": "each word's time", "cue": None}, {"event": "caption_chunk", "frame": "each chunk's start", "cue": None}]),
    "dm-card": dict(item=None, name="DM notification card", kind="branding", z=3, demo={"avatar": "assets/brand/mark/avatar-dark.png", "enter_at": 0.3, "y": 700}, demo_duration=3, measure="#dm",
                    does="The CTA's DM notification in the style's look: a surface card with the round FlashFX avatar image (at least 112 px across), the sender name and one message line. Enters with the card move; its landing is the notification sound.",
                    events=[{"event": "enter", "frame": 0, "cue": None}, {"event": "notification", "frame": 8, "cue": "notification"}]),
    "pop": dict(item=8, name="Pop", kind="move", z=3, demo={"enter_at": 0.3}, demo_duration=3, measure="#pop-el",
                does="Brings small things in with a little spring: a keyword pill, a badge, a tile, a chip. Scale from 0.5 to a peak (13 to 16 percent for icons and badges, 1 to 3 percent for pills and cards) then back to 1 over 3 to 15 frames; opacity reaches 1 within 4 frames.",
                events=[{"event": "pop", "frame": 0, "cue": "ui_click"}, {"event": "pop_peak", "frame": "round(frames x 0.55)", "cue": None}]),
    "check-badge": dict(item=9, name="Check badge and checklist ticks", kind="support", z=3, demo={"enter_at": 0.3, "size": 120, "x": 480}, demo_duration=3, measure="#cb-badge",
                        does="Marks done or yes: a success circle with a white check and a white ring that pops (16 percent, 12 frames), or a checklist card whose ticks pop 3 frames each, 4 frames apart.",
                        events=[{"event": "check", "frame": 0, "cue": "success", "note": "list mode: one per tick, ticks_at then 4 frames apart"}]),
    "window-card": dict(item=10, name="Window card", kind="card", z=2, demo={"image": "assets/demo/plugin-page.png", "mascot": "play", "honesty": "sourced"}, demo_duration=3, measure="#wc",
                        does="Shows the tool or a site: a card with a surface-chrome title bar and 3 dots, the content a real screenshot (research assets) or text lines; light or dark. Card enter, or a fly-in from below.",
                        events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "land", "frame": "8 (rise) or 16 (fly-in)", "cue": None}, {"event": "mascot", "frame": "land + 4", "cue": None}]),
    "terminal-card": dict(item=11, name="Terminal or code card that types", kind="card", z=2, demo={}, demo_duration=4, measure="#tc",
                          does="The prompt or the code being written: a dark window card with colored mono text; lines appear one by one, typed at 2 characters per frame or whole.",
                          events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "land", "frame": 8, "cue": None},
                                  {"event": "typing", "frame": "8 + start_delay_frames, then line by line", "duration_frames": "chars / chars_per_frame", "cue": "typing"}]),
    "chart-card": dict(item=12, name="Chart card", kind="card", z=2, demo={}, demo_duration=3, measure="#cc",
                       does="Data as bars (grow over 12 frames, 2 apart, the value fades in as its bar ends; the highlight bar in accent) or a gauge (arc and number over 23 frames). Mock data carries the honesty label.",
                       events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "bar", "frame": "8 + 2 x i", "duration_frames": 12, "cue": None}, {"event": "gauge", "frame": 8, "duration_frames": 23, "cue": "number"}]),
    "thumb-grid": dict(item=13, name="Thumbnail grid, fan or deck", kind="card", z=2, demo={}, demo_duration=3, measure="#tg-wrap",
                       does="Many examples at once: a grid of thumbnail cards (images or placeholders) with small count chips; cards build 4 frames each, 1 frame apart in a row, rows 7 frames apart.",
                       events=[{"event": "card", "frame": "row x 7 + col", "cue": None}]),
    "logo-tile": dict(item=14, name="Logo tile or logo badge", kind="brand-slot", z=3, demo={"image": "assets/brand/mark/mark-gradient.png", "second_image": "assets/brand/mark/mark-black.png", "x": 366, "enter_at": 0.2}, demo_duration=3, measure="#lt-main",
                      does="Names the tool or brand: a surface rounded square or circle badge holding a logo image file with its aspect ratio locked (brand.json or a research asset; a neutral icon when there is none). Pops with 13 percent overshoot over 14 frames; a second tile slides in from the left over 9 frames with a 6 px overshoot.",
                      events=[{"event": "pop", "frame": 0, "cue": "hero_enter"}, {"event": "slide", "frame": 17, "cue": "ui_click", "note": "when second_image is set"}]),
    "strike-through": dict(item=15, name="Strike-through", kind="support", z=3, demo={}, demo_duration=3, measure="#st-text",
                           does="Not X, before and after: a line drawn across a chip or text over 4 frames, or an X as two strokes of 6 frames, 6 apart; a replacement types in after it.",
                           events=[{"event": "enter", "frame": 0, "cue": None}, {"event": "strike", "frame": "strike_at x 30", "cue": "negative"}, {"event": "typing", "frame": "strike + line_frames + 2", "cue": "typing", "note": "when a replacement is set"}]),
    "fly-in": dict(item=16, name="Fly-in from a parked spot", kind="move", z=2, demo={"mascot": "film", "enter_at": 0.2}, demo_duration=3, measure="#fi",
                   does="A big entrance for a hero card: travels 414 to 930 px from below, half below or a side over 11 to 16 frames, expo.out, the start tilt easing to 0, no overshoot.",
                   events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "land", "frame": "frames (14)", "cue": None}, {"event": "mascot", "frame": "frames + 4", "cue": None}]),
    "chat-card": dict(item=17, name="Chat card", kind="card", z=2, demo={}, demo_duration=4, measure="#chat",
                      does="A prompt being sent: a surface card with an input bar and a send button. The text types at 1.15 frames per character; the button turns from gray to accent over 2 frames, 3 frames after the last character; an optional reply bubble follows.",
                      events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "typing", "frame": "type_at x 30", "duration_frames": "chars x 1.15", "cue": "typing"},
                              {"event": "send", "frame": "typing end + 3", "cue": "ui_click"}, {"event": "reply", "frame": "send + 10", "cue": None}]),
    "progress-bar": dict(item=18, name="Progress or meter bar", kind="support", z=3, demo={}, demo_duration=3, measure="#pb",
                         does="Something finishing or a usage value: the bar fills over 6 frames (the percent counts with it), then a check badge pops over 3 frames.",
                         events=[{"event": "enter", "frame": 0, "cue": None}, {"event": "fill", "frame": "fill_at x 30", "duration_frames": 6, "cue": "number"}, {"event": "check", "frame": "fill + 5", "cue": "success"}]),
    "camera-move": dict(item=19, name="Camera pull-back or zoom", kind="move", z=2, demo={"image": "assets/demo/repo.png"}, demo_duration=3, measure="#cm-stage",
                        does="Reveals context or dives in: the whole scene content shrinks into an app window over 8 frames ease-out (pull-back), or grows out of it over 20 frames ease-in-out (zoom). The caption layer does not move.",
                        events=[{"event": "camera", "frame": "at x 30", "duration_frames": "frames", "cue": "transition_slow"}]),
    "headline": dict(item=20, name="Headline reveal (the hook)", kind="hook", z=2, demo={"kicker_mark": "assets/brand/mark/mark-gradient.png"}, demo_duration=4, measure="#hl-lines",
                     does="The hook: frame 0 shows the accent mark (the brand slot: the bolt, the tool's logo or an accent dot) where the kicker starts; the kicker words fade in one by one, then the headline builds word by word as spoken (3 frames per word) over 2 to 3 lines with one serif-italic phrase.",
                     events=[{"event": "word", "frame": "each word's time", "cue": None, "note": "the hook set piece elsewhere takes hook_hit"}]),
    "exit-move": dict(item=21, name="Exit fall or push", kind="move", z=2, demo={}, demo_duration=3, measure="#xm-leaving",
                      does="Clears a scene with motion: fall off the bottom over 10 frames ease-in tilting 2 degrees (the next card rises at once), push 6 frames out to the left then 2 empty frames and a 12-frame entrance, or the look refs' fade with blur over 4 frames. The same moves are the exit props of every component.",
                      events=[{"event": "scene_change", "frame": "exit_at x 30", "cue": "transition_fast or transition_slow by duration"}, {"event": "enter", "frame": "after the exit", "cue": None}]),
    "handwritten-callout": dict(item=22, name="Handwritten callout", kind="support", z=3, demo={"enter_at": 0.3}, demo_duration=3, measure="#hc-wrap",
                                does="A hand-drawn aside in the script color with an arrow pointing at something: the text fades in over 6 frames and the arrow draws itself over 8.",
                                events=[{"event": "enter", "frame": 0, "cue": None}, {"event": "draw", "frame": 4, "duration_frames": 10, "cue": None}]),
    "speech-bubble": dict(item=23, name="Speech bubble and confetti", kind="cta", z=3, demo={"keyword": "TELLS", "enter_at": 0.3}, demo_duration=3, measure="#sb",
                          does="On the end card: the bubble scales from 0.5 to 1 over 7 frames with a 40 px overshoot in y settling over 9 more, a keyword pill pops under it, seeded confetti drifts down behind.",
                          events=[{"event": "pop", "frame": 0, "cue": "ui_click"}, {"event": "confetti", "frame": 0, "cue": None}, {"event": "pop", "frame": 11, "cue": "ui_click", "note": "the keyword pill, when set"}]),
    "table-card": dict(item=24, name="Table card", kind="card", z=2, demo={}, demo_duration=3, measure="#tb",
                       does="A comparison: a surface card with a logo row (image files) and a small pill, label and value rows with hairline dividers, values right-aligned, good values in success. Enters over 7 frames with a 28 px rise; rows follow 3 frames apart.",
                       events=[{"event": "enter", "frame": 0, "cue": "hero_enter"}, {"event": "row", "frame": "4 + 3 x i", "cue": None}]),
    "icon-3d": dict(item=None, name="3D icon (Three.js, CSS-extruded fallback)", kind="3d", z=2, fallback="css", demo={"enter_at": 0.2, "icon": "bolt"}, demo_duration=4, measure="#i3-stage",
                    does="A low-poly 3D icon turning slowly at the center of a scene (Motion and energy rules E6): a Three.js extrusion of an SVG path (bolt, star, play, check, cursor, heart) or a primitive (a rounded slab, a torus, a low-poly sphere) in a palette color, drawn from the hf-seek time on the WebGL backend of motion-lib/webgl.json, with a CSS-extruded fallback (the SVG in 8 to 16 depth layers under a turning stage) when WebGL is missing or mode is css. Needs the clip_start prop (its data-start). Never a logo. The style allows 3D objects in the hook and the end card (tweaks.md 3D).",
                    events=[{"event": "enter", "frame": "enter_at x 30", "cue": "hook_hit", "note": "when it is the hook's set piece"}, {"event": "land", "frame": "enter_at x 30 + 12", "cue": None}]),
    "hero-3d": dict(item=None, name="3D hero object (Three.js)", kind="3d", z=2, demo={"enter_at": 0.2, "label": "the skill file"}, demo_duration=4, measure="#h3-canvas",
                    does="The one 3D component (hook and end card only, at most 2 objects): a low-poly card, box or icosahedron turning under a warm key light, drawn from the hf-seek time, with a soft contact shadow; scales in with a back-out over 12 frames. Needs the clip_start prop (its data-start). Without WebGL it shows a flat card and reports data-webgl=0.",
                    events=[{"event": "enter", "frame": "enter_at x 30", "cue": "hook_hit", "note": "when it is the hook's set piece"}, {"event": "land", "frame": "enter_at x 30 + 12", "cue": None}]),
}

KINDS_NOTE = ("canvas: the background; card: a hero or support card; label: chips; support: badges, bars, strikes, callouts; move: a move "
              "demo that is also usable on its own; hook, cta, captions, branding, brand-slot, 3d as named")


def beat_types_for(tokens: dict, cid: str) -> list[str]:
    bm = tokens.get("beat_map", {})
    out = [bt for bt, ids in bm.items() if bt != "any" and cid in ids]
    if cid in bm.get("any", []):
        out = ["any"] + out
    return out


def build(lib: str, tokens: dict, previous: dict | None) -> dict:
    prev_by_id = {c["id"]: c for c in (previous or {}).get("components", [])}
    files = common.component_files(lib)
    comps = []
    for folder, paths in (("compositions", files["compositions"]), ("candidates", files["candidates"])):
        for path in paths:
            comp = common.parse_component(path)
            cid = comp["id"]
            meta = META.get(cid)
            if not meta:
                raise common.ComponentError(f"{path}: no META entry in motion/catalog.py")
            props = []
            for d in comp["declaration"]:
                p = {"id": d["id"], "type": d.get("type", "string"), "default": d.get("default"), "label": d.get("label", "")}
                if d.get("options"):
                    p["options"] = [o.get("value") for o in d["options"]]
                if d["id"] in ("image", "avatar", "lockup", "kicker_mark", "second_image") or (d["id"].endswith("_json") and "image" in d.get("label", "")):
                    p["image"] = True
                props.append(p)
            entry = {
                "id": cid, "item": meta["item"], "name": meta["name"], "kind": meta["kind"], "does": meta["does"],
                "file": f"{folder}/{cid}.html", "status": "approved" if folder == "compositions" else "candidate",
                "still": f"gallery/stills/{cid}.png", "z": meta["z"], "measure": meta["measure"],
                "props": props, "beat_types": beat_types_for(tokens, cid), "sound_events": meta["events"],
                "demo": meta["demo"], "demo_duration": meta["demo_duration"],
                "fallback": meta.get("fallback"),
                "frame_match": prev_by_id.get(cid, {}).get("frame_match") or {"result": "not run"},
                "energy": prev_by_id.get(cid, {}).get("energy"),
            }
            comps.append(entry)
    comps.sort(key=lambda c: (c["item"] is None, c["item"] or 0, c["id"]))
    return {
        "style": tokens.get("style", "paper-cards"), "generated": dt.date.today().isoformat(), "fps": common.FPS,
        "canvas": {"width": 1080, "height": 1920},
        "placement": "Every component is a full-frame 1080x1920 layer mounted as a HyperFrames sub-composition (data-composition-src) with its props as data-variable-values; x, y and w props place the element; the host order and z-index give the stacking; the canvas is mounted first for the whole reel, the caption line once over the body beats.",
        "conventions": {"times": "props in seconds local to the clip (enter_at, exit_at); hero-3d and icon-3d also need clip_start = its data-start",
                        "hold": "every element component has hold (calm, normal, lively): the steady motion after its entrance (Motion and energy rules E1); the canvas takes seed and duration",
                        "images": "image props take a path relative to the project (assets/brand/... from library/brand per brand.json, assets/research/... from the run's research assets); aspect ratio locked, never redrawn",
                        "exit": "every element component has exit (none, fade-blur, fall, push, cut) and exit_at: the scene change of 9c",
                        "honesty": "card-like components take honesty (none, mock, sourced) and show the light chip of tokens.json honesty_labels",
                        "kinds": KINDS_NOTE},
        "cue_types": CUE_TYPES,
        "components": comps,
    }


def check(lib: str, tokens: dict, cat: dict) -> list[str]:
    problems = []
    files = common.component_files(lib)
    on_disk = {os.path.splitext(os.path.basename(p))[0]: ("compositions" if p in files["compositions"] else "candidates") for p in files["compositions"] + files["candidates"]}
    listed = {c["id"]: c for c in cat.get("components", [])}
    for cid in on_disk:
        if cid not in listed:
            problems.append(f"{cid}: file without a catalog entry")
    for cid, c in listed.items():
        if cid not in on_disk:
            problems.append(f"{cid}: catalog entry without a file")
            continue
        if c.get("file") != f"{on_disk[cid]}/{cid}.html":
            problems.append(f"{cid}: file {c.get('file')} but the file is under {on_disk[cid]}/")
        comp = common.parse_component(os.path.join(lib, on_disk[cid], cid + ".html"))
        declared = {d["id"] for d in comp["declaration"]}
        catalog_props = {p["id"] for p in c.get("props", [])}
        if declared != catalog_props:
            problems.append(f"{cid}: props differ from the declaration: missing {sorted(declared - catalog_props)}, extra {sorted(catalog_props - declared)}")
        for k in c.get("demo", {}):
            if k not in declared:
                problems.append(f"{cid}: demo prop {k} is not declared")
        for e in c.get("sound_events", []):
            cue = e.get("cue")
            if cue and cue not in CUE_TYPES and cue not in ("transition", "transition_fast or transition_slow by duration"):
                problems.append(f"{cid}: unknown cue type {cue}")
        if not c.get("beat_types"):
            problems.append(f"{cid}: no beat type allows it (tokens.json beat_map)")
        if not comp["registers"]:
            problems.append(f"{cid}: the file never registers window.__timelines[\"{cid}\"]")
    for item in range(1, 25):
        if not any(c.get("item") == item for c in listed.values()):
            problems.append(f"vocabulary item {item} has no component")
    if "dm-card" not in listed:
        problems.append("the DM notification card (branding) is missing")
    return problems


def run(args) -> int:
    lib = common.motion_lib_dir()
    toks = common.tokens()
    path = common.catalog_path(lib)
    previous = common.load_json(path) if os.path.isfile(path) else None
    if args.write:
        cat = build(lib, toks, previous)
        common.write_json(path, cat)
        print(f"catalog written: {len(cat['components'])} components -> {path}")
    if not os.path.isfile(path):
        print("catalog.json is missing: run with --write")
        return 1
    cat = common.load_json(path)
    problems = check(lib, toks, cat)
    for p in problems:
        print("catalog: " + p)
    if not problems:
        print(f"catalog ok: {len(cat['components'])} components, items 1 to 24 covered, the DM card present")
    return 1 if problems else 0
