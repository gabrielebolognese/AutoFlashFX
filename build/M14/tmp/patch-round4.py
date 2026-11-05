"""Round 4 patches: camera-move's pre-move drift, catalog META (icon-3d, the canvas, the fallback field, the energy field),
the beat map, S10's replace_3d, golden.py's canvas host and pc-motion.js copy, gallery.py's showreel host."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


# camera-move: the content inside the stage drifts before the camera moves (nothing is static, E1)
patch("motion-lib/compositions/camera-move.html", [
    ('''      var cam = PCM.camera(tl, stage, v.at, { kind: v.kind, frames: v.frames, scale: s, x: endX, y: endY, hold: v.hold, exit: exit });''',
     '''      // before the camera moves, the scene content drifts inside the stage (E1: nothing waits still)
      if (v.at > 0) PCM.life(tl, document.getElementById("cm-content"), { at: 0, main: { kind: "none" }, hold: { level: v.hold, kind: "drift", dir: { x: 0, y: -1 } }, inertia: { move: 0, scale: 0, rotate: 0 }, until: v.at + PC.f(v.frames) });
      var cam = PCM.camera(tl, stage, v.at, { kind: v.kind, frames: v.frames, scale: s, x: endX, y: endY, hold: v.hold, exit: exit });'''),
])

# catalog.py: META for the canvas (its props), icon-3d, the fallback and energy fields
patch("pipeline/lib/motion/catalog.py", [
    ('''    "paper-canvas": dict(item=None, name="Paper canvas", kind="canvas", z=0, demo={}, demo_duration=None, measure="#paper-root",
                         does="The background of every reel: paper, a warm glow top left, a warm glow lower right, darker bottom corners, a dot grid. Static, mounted for the whole reel at z 0.",
                         events=[]),''',
     '''    "paper-canvas": dict(item=None, name="Paper canvas", kind="canvas", z=0, demo={"seed": 7, "duration": 90}, demo_duration=None, measure="#paper-edges",
                         does="The background of every reel: paper, a warm glow top left, a warm glow lower right, darker bottom corners, a dot grid, and from M14 the life of Motion and energy rules E5 and E7: an edge filler layer (soft cards, chips, thumbnails, shapes and stars 30 to 70 percent outside the left and right borders, at most 20 px per second, no text) and an ambient layer (stars, dots and small clouds drifting and twinkling), both seeded per reel (the seed and duration props) and kept out of every text zone. Mounted for the whole reel at z 0.",
                         events=[]),'''),
    ('''    "hero-3d": dict(item=None, name="3D hero object (Three.js)", kind="3d", z=2, demo={"enter_at": 0.2, "label": "the skill file"}, demo_duration=4, measure="#h3-canvas",''',
     '''    "icon-3d": dict(item=None, name="3D icon (Three.js, CSS-extruded fallback)", kind="3d", z=2, fallback="css", demo={"enter_at": 0.2, "icon": "bolt"}, demo_duration=4, measure="#i3-stage",
                    does="A low-poly 3D icon turning slowly at the center of a scene (Motion and energy rules E6): a Three.js extrusion of an SVG path (bolt, star, play, check, cursor, heart) or a primitive (a rounded slab, a torus, a low-poly sphere) in a palette color, drawn from the hf-seek time on the WebGL backend of motion-lib/webgl.json, with a CSS-extruded fallback (the SVG in 8 to 16 depth layers under a turning stage) when WebGL is missing or mode is css. Needs the clip_start prop (its data-start). Never a logo. The style allows 3D objects in the hook and the end card (tweaks.md 3D).",
                    events=[{"event": "enter", "frame": "enter_at x 30", "cue": "hook_hit", "note": "when it is the hook's set piece"}, {"event": "land", "frame": "enter_at x 30 + 12", "cue": None}]),
    "hero-3d": dict(item=None, name="3D hero object (Three.js)", kind="3d", z=2, demo={"enter_at": 0.2, "label": "the skill file"}, demo_duration=4, measure="#h3-canvas",'''),
    ('''                "demo": meta["demo"], "demo_duration": meta["demo_duration"],
                "frame_match": prev_by_id.get(cid, {}).get("frame_match") or {"result": "not run"},
            }''',
     '''                "demo": meta["demo"], "demo_duration": meta["demo_duration"],
                "fallback": meta.get("fallback"),
                "frame_match": prev_by_id.get(cid, {}).get("frame_match") or {"result": "not run"},
                "energy": prev_by_id.get(cid, {}).get("energy"),
            }'''),
    ('''        "conventions": {"times": "props in seconds local to the clip (enter_at, exit_at); hero-3d also needs clip_start = its data-start",''',
     '''        "conventions": {"times": "props in seconds local to the clip (enter_at, exit_at); hero-3d and icon-3d also need clip_start = its data-start",
                        "hold": "every element component has hold (calm, normal, lively): the steady motion after its entrance (Motion and energy rules E1); the canvas takes seed and duration",'''),
    ('''        if cid != "paper-canvas" and not comp["registers"]:''', '''        if not comp["registers"]:'''),
])

# the beat map: icon-3d where the style allows 3D (the hook and the end card)
patch("pipeline/lib/tokens.py", [
    ('''    "hook": ["headline", "window-card", "logo-tile", "hero-3d", "card", "fly-in", "stat-number"],''',
     '''    "hook": ["headline", "window-card", "logo-tile", "hero-3d", "icon-3d", "card", "fly-in", "stat-number"],'''),
    ('''    "ask": ["end-card", "dm-card", "speech-bubble"],''', '''    "ask": ["end-card", "dm-card", "speech-bubble", "icon-3d"],'''),
])

# S10: a 3D component with its own CSS fallback is never replaced by a card
patch("pipeline/lib/visual/project.py", [
    ('''            if cat_by_id.get(c["component"], {}).get("kind") != "3d":
                continue''', '''            entry = cat_by_id.get(c["component"], {})
            if entry.get("kind") != "3d" or entry.get("fallback") == "css":
                continue  # icon-3d draws its CSS-extruded fallback itself (M14)'''),
])

# golden.py: the canvas is seeded per reel and runs for the reel's length; pc-motion.js travels with the project
patch("pipeline/lib/motion/golden.py", [
    ('''    for name in ("paper-cards.css", "paper-cards.js", "tokens.css"):
        shutil.copy2(os.path.join(lib, "assets", name), os.path.join(project, "assets", name))''',
     '''    for name in ("paper-cards.css", "paper-cards.js", "pc-motion.js", "tokens.css"):
        shutil.copy2(os.path.join(lib, "assets", name), os.path.join(project, "assets", name))'''),
    ('''    canvas_file = by_id["paper-canvas"]["file"]
    hosts.append(f'      <div id="paper-canvas" class="clip" data-composition-id="paper-canvas" data-composition-src="{canvas_file}" data-start="0" data-duration="{dur_s:.3f}" '
                 f'data-track-index="0" data-width="1080" data-height="1920" data-no-timeline data-scene="all" style="z-index: 0"></div>')''',
     '''    canvas_file = by_id["paper-canvas"]["file"]
    canvas_props = {"seed": canvas_seed(plan), "duration": round(dur_s + 1, 3)}  # M14: the edge and ambient layers, seeded per reel
    hosts.append(f'      <div id="paper-canvas" class="clip" data-composition-id="paper-canvas" data-composition-src="{canvas_file}" data-start="0" data-duration="{dur_s:.3f}" '
                 f'data-track-index="0" data-width="1080" data-height="1920" data-scene="all" style="z-index: 0" data-variable-values=\\'{attr_json(canvas_props)}\\'></div>')'''),
    ('''def reset_dir(path: str) -> None:''', '''def canvas_seed(plan: dict) -> int:
    """A stable seed per reel for the canvas layers (M14): from the idea id, else from the plan's duration."""
    import hashlib
    key = str(plan.get("idea_id") or plan.get("duration_ms") or "reel")
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:6], 16) % 1000000 + 1


def reset_dir(path: str) -> None:'''),
])

# gallery.py: the showreel's canvas host gets a seed and the reel's length; the gallery shows each component's energy
patch("pipeline/lib/motion/gallery.py", [
    ('''        canvas_host = (f'      <div id="paper-canvas" class="clip" data-composition-id="paper-canvas" data-composition-src="{canvas["catalog"]["file"]}" data-start="0" '
                       f'data-duration="{total:g}" data-track-index="0" data-width="1080" data-height="1920" data-no-timeline style="z-index: 0"></div>')''',
     '''        canvas_host = (f'      <div id="paper-canvas" class="clip" data-composition-id="paper-canvas" data-composition-src="{canvas["catalog"]["file"]}" data-start="0" '
                       f'data-duration="{total:g}" data-track-index="0" data-width="1080" data-height="1920" style="z-index: 0" '
                       f'data-variable-values=\\'{json.dumps({"seed": 7, "duration": round(total + 1, 3)})}\\'></div>')'''),
    ('''def fm_text(c: dict) -> str:''', '''def energy_text(c: dict) -> str:
    """The component's energy measures (frame-match renders it alone for 4 s: motion/framematch.py, review/energy.py)."""
    e = c.get("energy") or {}
    if not e or e.get("moving_share_pct") is None:
        return "not measured"
    return (f"moving {e.get('moving_share_pct')} percent of frames, middle band {e.get('middle_moving_share_pct')} percent, pixels changing {e.get('pixels_changing_pct')} percent, "
            f"longest still {e.get('longest_still_s')} s, static windows {e.get('static_windows', 0)}")


def fm_text(c: dict) -> str:'''),
    ('''    <p><b>Frame match:</b> {esc(fm_text(c))}. <b>Beat types:</b> {esc(', '.join(c['beat_types']))}. <b>File:</b> <code>{esc(c['file'])}</code></p>''',
     '''    <p><b>Frame match:</b> {esc(fm_text(c))}. <b>Energy (alone, 4 s):</b> {esc(energy_text(c))}. <b>Beat types:</b> {esc(', '.join(c['beat_types']))}. <b>File:</b> <code>{esc(c['file'])}</code></p>'''),
    ('''  To change a look or a timing, edit the component in <code>motion-lib/compositions/</code>, then run <code>bash pipeline/bin/frame-match</code> and <code>bash pipeline/bin/gallery</code>.</p>''',
     '''  To change a look or a timing, edit the component in <code>motion-lib/compositions/</code>, then run <code>bash pipeline/bin/frame-match</code> and <code>bash pipeline/bin/gallery</code>.
  Since M14 every component lives through the four phases of the Motion and energy rules (main animation, inertia, hold, exit; <code>motion-lib/assets/pc-motion.js</code>) and the energy line shows what it measures rendered alone for 4 s (<code>python pipeline/lib/review energy</code> measures a whole reel).</p>'''),
])
print("round 4 done")
