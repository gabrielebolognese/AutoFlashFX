"""Round 8: more energy inside the spec's ranges: the combined main animation lasts 15 frames (0.5 s), the inertia carries
16 px and a scale of 1.04 (the spec's own example), and a window card's screenshot scrolls slowly inside its frame
(content motion, the strongest lever the meter sees at 108x192)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/tokens.py", [
    ('''    "main": {"min_s": 0.3, "max_s": 0.6, "frames": 12, "ease": "power3.inOut",''', '''    "main": {"min_s": 0.3, "max_s": 0.6, "frames": 15, "ease": "power3.inOut",'''),
    ('''    "inertia": {"seconds": 3, "range_s": [2, 4], "ease": "power3.out", "move_px": 12, "scale": 0.03, "scale_example": [1.0, 1.04], "rotate_deg": 2,''',
     '''    "inertia": {"seconds": 3, "range_s": [2, 4], "ease": "power3.out", "move_px": 16, "scale": 0.04, "scale_example": [1.0, 1.04], "rotate_deg": 2,'''),
    ('''    "camera": {"rotate_deg_s": 0.3, "perspective_px": 1400, "depth_step_px": 24},''',
     '''    "camera": {"rotate_deg_s": 0.3, "perspective_px": 1400, "depth_step_px": 24},
    "content": {"scroll_px_s": 24, "scroll_scale": 1.25, "note": "a screenshot inside a window card scrolls slowly (content motion, E1: the content itself keeps moving)"},'''),
])

patch("motion-lib/assets/pc-motion.js", [
    ('''      mainFrames: cssNum("--m-main-frames", 12),''', '''      mainFrames: cssNum("--m-main-frames", 15),'''),
    ('''      inertiaMove: cssNum("--m-inertia-move", 12),
      inertiaScale: cssNum("--m-inertia-scale", 0.03),''', '''      inertiaMove: cssNum("--m-inertia-move", 16),
      inertiaScale: cssNum("--m-inertia-scale", 0.04),'''),
    ('''      depthStep: cssNum("--m-depth-step", 24),''', '''      depthStep: cssNum("--m-depth-step", 24),
      scrollSpeed: cssNum("--m-scroll-px-s", 24),
      scrollScale: cssNum("--m-scroll-scale", 1.25),'''),
    ('''  // a slow pan of content inside a frame (a screenshot in a window card): a steady move, linear
  PCM.pan = function (tl, el, at, o) {
    o = o || {};
    var seconds = Math.max(0.5, o.seconds || 1);
    tl.fromTo(el, { x: 0, y: 0 }, { x: o.dx || 0, y: o.dy || 0, duration: seconds, ease: "none", immediateRender: false }, at);
    return at + seconds;
  };''',
     '''  // a slow pan of content inside a frame (a screenshot in a window card): a steady move, linear
  PCM.pan = function (tl, el, at, o) {
    o = o || {};
    var seconds = Math.max(0.5, o.seconds || 1);
    tl.fromTo(el, { x: 0, y: 0 }, { x: o.dx || 0, y: o.dy || 0, duration: seconds, ease: "none", immediateRender: false }, at);
    return at + seconds;
  };
  // a screenshot scrolling inside its window: the image is enlarged by scrollScale (the extra height is the slack) and
  // moves up at scrollSpeed px per second for the element's life, never past its slack (E1: the content keeps moving)
  PCM.scroll = function (tl, img, at, seconds, o) {
    o = o || {};
    var N = PCM.numbers();
    var scale = o.scale || N.scrollScale, speed = o.speed === undefined ? N.scrollSpeed : o.speed;
    var h = o.height || img.getBoundingClientRect().height || 700;
    var slack = Math.max(0, h * (scale - 1));
    gsap.set(img, { scale: scale, transformOrigin: "50% 0%" });
    if (!(seconds > 0) || slack <= 0 || speed <= 0) return at;
    var dist = Math.min(slack, speed * seconds);
    tl.fromTo(img, { y: 0 }, { y: -dist, duration: dist / speed, ease: "none", immediateRender: false }, at);
    PC.event("scroll", at, { el: img.id, end: at + dist / speed, px: dist });
    return at + dist / speed;
  };'''),
])

patch("motion-lib/compositions/window-card.html", [
    ('''  {"id":"honesty","type":"enum","label":"Honesty label","default":"none","options":[{"value":"none","label":"none"},{"value":"mock","label":"mock"},{"value":"sourced","label":"sourced"}]},
  {"id":"hold","type":"enum","label":"Hold level (the steady motion after the entrance)","default":"normal","options":[{"value":"calm","label":"calm"},{"value":"normal","label":"normal"},{"value":"lively","label":"lively"}]},''',
     '''  {"id":"honesty","type":"enum","label":"Honesty label","default":"none","options":[{"value":"none","label":"none"},{"value":"mock","label":"mock"},{"value":"sourced","label":"sourced"}]},
  {"id":"scroll_px_s","type":"number","label":"The screenshot scrolls inside the window at this speed (px per second; 0 = still)","default":24},
  {"id":"hold","type":"enum","label":"Hold level (the steady motion after the entrance)","default":"normal","options":[{"value":"calm","label":"calm"},{"value":"normal","label":"normal"},{"value":"lively","label":"lively"}]},'''),
    ('''        mascot: "", honesty: "none", hold: "normal", exit: "none", exit_at: -1 }, window.__hyperframes.getVariables());''',
     '''        mascot: "", honesty: "none", scroll_px_s: 24, hold: "normal", exit: "none", exit_at: -1 }, window.__hyperframes.getVariables());'''),
    ('''      // the content inside the window pans slowly (a screenshot taller than the window shows more of itself)
      if (v.image && v.image_fit !== "contain") {
        var inner = PCM.holdLevel(v.hold);
        gsap.set(img, { scale: 1.04, transformOrigin: "50% 0%" });
        PCM.pan(tl, img, life.land, { dy: -Math.min(80, inner.drift * 2 * Math.max(1, life.until - life.land)), seconds: life.until - life.land });
      }''',
     '''      // the screenshot scrolls slowly inside the window (the page reads on: content motion, E1)
      if (v.image && v.image_fit !== "contain" && v.scroll_px_s > 0) {
        PCM.scroll(tl, img, life.land, life.until - life.land, { speed: v.scroll_px_s, height: v.h - 72 });
      }'''),
    ('''       combined with E2's zoom and parallax rotation, then the inertia and the hold of E1 (pc-motion.js). The image
       inside drifts slowly against the frame (a slow pan: the content keeps moving, E1). */''',
     '''       combined with E2's zoom and parallax rotation, then the inertia and the hold of E1 (pc-motion.js). The screenshot
       inside scrolls slowly (24 px per second by default, scroll_px_s), enlarged a quarter so it has room: the content
       itself keeps moving, as in the references' window cards (E1, E8). */'''),
])
print("round 8 done")
