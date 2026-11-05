"""Round 14: the window card's screenshot scrolls by its object-position, not by a transform: the image box stays inside
the window (the review's off-canvas rule reads the box), the page is not enlarged, and the whole screenshot height is
the room to scroll."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("motion-lib/assets/pc-motion.js", [
    ('''  // a screenshot scrolling inside its window: the image is enlarged by scrollScale (the extra height is the slack) and
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
  };''',
     '''  // a screenshot scrolling inside its window (object-fit cover, taller than the window): its object-position moves from
  // the top toward the bottom at scrollSpeed px per second for the element's life, never past the bottom. The image box
  // itself never moves or grows (the review's off-canvas rule reads the box); the page itself is the room to scroll.
  PCM.scroll = function (tl, img, at, seconds, o) {
    o = o || {};
    var N = PCM.numbers();
    var speed = o.speed === undefined ? N.scrollSpeed : o.speed;
    var boxW = o.width || img.getBoundingClientRect().width || 900, boxH = o.height || img.getBoundingClientRect().height || 700;
    var nw = img.naturalWidth || 1080, nh = img.naturalHeight || 1920;  // a page screenshot is portrait when not yet loaded
    var drawnH = Math.max(boxH, boxW * nh / nw);
    var slack = drawnH - boxH;
    if (!(seconds > 0) || slack <= 1 || speed <= 0) return at;
    var dist = Math.min(slack, speed * seconds);
    var pct = Math.round(dist / slack * 10000) / 100;
    tl.fromTo(img, { objectPosition: "50% 0%" }, { objectPosition: "50% " + pct + "%", duration: dist / speed, ease: "none", immediateRender: false }, at);
    PC.event("scroll", at, { el: img.id, end: at + dist / speed, px: dist });
    return at + dist / speed;
  };'''),
    ('''      scrollSpeed: cssNum("--m-scroll-px-s", 24),
      scrollScale: cssNum("--m-scroll-scale", 1.25),''', '''      scrollSpeed: cssNum("--m-scroll-px-s", 24),'''),
])

patch("motion-lib/compositions/window-card.html", [
    ('''      // the screenshot scrolls slowly inside the window (the page reads on: content motion, E1)
      if (v.image && v.image_fit !== "contain" && v.scroll_px_s > 0) {
        PCM.scroll(tl, img, life.land, life.until - life.land, { speed: v.scroll_px_s, height: v.h - 72 });
      }''',
     '''      // the screenshot scrolls slowly inside the window (the page reads on: content motion, E1); object-fit cover with
      // object-position moving down, so the image box never leaves the window
      if (v.image && v.image_fit !== "contain" && v.scroll_px_s > 0) {
        PCM.scroll(tl, img, life.land, life.until - life.land, { speed: v.scroll_px_s, width: v.w, height: v.h - 72 });
      }'''),
    ('''       inside scrolls slowly (24 px per second by default, scroll_px_s), enlarged a quarter so it has room: the content
       itself keeps moving, as in the references' window cards (E1, E8). */''',
     '''       inside scrolls slowly (24 px per second by default, scroll_px_s) through its own height (object-fit cover, the
       object-position moving down): the content itself keeps moving, as in the references' window cards (E1, E8). */'''),
])

patch("pipeline/lib/tokens.py", [
    ('''    "content": {"scroll_px_s": 24, "scroll_scale": 1.25, "note": "a screenshot inside a window card scrolls slowly (content motion, E1: the content itself keeps moving)"},''',
     '''    "content": {"scroll_px_s": 24, "note": "a screenshot inside a window card scrolls slowly through its own height (content motion, E1: the content itself keeps moving)"},'''),
    ('''            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 24)};",
            f"  --m-scroll-scale: {g.get('content', {}).get('scroll_scale', 1.25)};",''',
     '''            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 24)};",'''),
])
print("round 14 done")
