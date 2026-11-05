p = "motion-lib/assets/pc-motion.js"
s = open(p, encoding="utf-8").read()

# 1. the hold may start from a known state (the camera move's end): o.from = {x, y, scale}
old = '''    var A = inert.move === undefined ? (hadMove ? N.inertiaMove : (kind === "pop" ? N.inertiaMove * 0.5 : 0)) : inert.move;
    if (!hadMove && kind !== "pop") dir = holdSpec.dir || { x: 0, y: -1 };
    if (holdSpec.dir) dir = holdSpec.dir;
    var end = { x: 0, y: 0 };
    var T = until - land;
    var total = A + drift * T;
    if (T > 0 && total > 0 && (A > 0 || drift > 0)) {
      end = { x: dir.x * total, y: dir.y * total };
      tl.fromTo(el, { x: 0, y: 0 }, { x: end.x, y: end.y, duration: T, ease: PCM.glide(A, drift, D, T), immediateRender: false }, land);
    }
    var sA = inert.scale === undefined ? (zoom || kind === "pop" ? (kind === "pop" ? N.inertiaScale * 0.5 : N.inertiaScale) : 0) : inert.scale;
    var Ts = until - scaleLand;
    if (Ts > 0 && (sA > 0 || creep > 0)) {
      var sTotal = sA + creep * Ts;
      tl.fromTo(el, { scale: 1 }, { scale: 1 + sTotal, duration: Ts, ease: PCM.glide(sA, creep, D, Ts), immediateRender: false }, scaleLand);
    }'''
new = '''    var A = inert.move === undefined ? (hadMove ? N.inertiaMove : (kind === "pop" ? N.inertiaMove * 0.5 : 0)) : inert.move;
    if (!hadMove && kind !== "pop") dir = holdSpec.dir || { x: 0, y: -1 };
    if (holdSpec.dir) dir = holdSpec.dir;
    var from = o.from || {};
    var fx = from.x || 0, fy = from.y || 0, fs = from.scale || 1;
    var end = { x: fx, y: fy };
    var T = until - land;
    var total = A + drift * T;
    if (T > 0 && total > 0 && (A > 0 || drift > 0)) {
      end = { x: fx + dir.x * total, y: fy + dir.y * total };
      tl.fromTo(el, { x: fx, y: fy }, { x: end.x, y: end.y, duration: T, ease: PCM.glide(A, drift, D, T), immediateRender: false }, land);
    }
    var sA = inert.scale === undefined ? (zoom || kind === "pop" ? (kind === "pop" ? N.inertiaScale * 0.5 : N.inertiaScale) : 0) : inert.scale;
    var Ts = until - scaleLand;
    if (Ts > 0 && (sA > 0 || creep > 0)) {
      var sTotal = sA + creep * Ts;
      tl.fromTo(el, { scale: fs }, { scale: fs * (1 + sTotal), duration: Ts, ease: PCM.glide(sA, creep, D, Ts), immediateRender: false }, scaleLand);
    }'''
assert old in s
s = s.replace(old, new)

# 2. the camera move (vocabulary.md 19): the stage shrinks into a window (pull-back, 8 frames ease-out) or grows out of it
#    (zoom, 20 frames ease-in-out), then holds from where it ended
old2 = '''  // a bar or a line growing'''
new2 = '''  // the camera move (vocabulary.md 19): the whole stage shrinks into a window over frames (8, power2.out: v02) or grows
  // out of it (zoom, 20 frames, power2.inOut: v05), then holds from where it ended (a drift and a parallax rotation)
  PCM.camera = function (tl, el, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 8 : o.frames;
    var s = o.scale === undefined ? 0.5 : o.scale, ex = o.x || 0, ey = o.y || 0;
    var pull = o.kind !== "zoom";
    PCM.prepare(el);
    if (pull) tl.fromTo(el, { scale: 1, x: 0, y: 0 }, { scale: s, x: ex, y: ey, duration: F(frames), ease: "power2.out" }, at);
    else tl.fromTo(el, { scale: s, x: ex, y: ey }, { scale: 1, x: 0, y: 0, duration: F(frames), ease: "power2.inOut" }, at);
    PC.event("camera", at, { el: el.id, kind: o.kind || "pullback", end: at + F(frames) });
    var endState = pull ? { x: ex, y: ey, scale: s } : { x: 0, y: 0, scale: 1 };
    var dir = o.dir || { x: 0, y: -1 };
    var h = PCM.life(tl, el, { at: at + F(frames), main: { kind: "none" }, hold: { level: o.hold || "normal", kind: "drift-rotate", dir: dir }, inertia: { move: 0, scale: 0, rotate: 0 },
      from: endState, exit: o.exit, until: o.until });
    return { until: h.until, dir: dir, end: endState, land: at + F(frames) };
  };
  // a bar or a line growing'''
assert old2 in s
s = s.replace(old2, new2)

# 3. the mascot walk takes its own distance and frames (the end card's row walks in bunched)
old3 = '''    if (kind === "walk") {
      tl.fromTo(m, { x: -260, opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      tl.to(m, { x: 0, duration: F(14), ease: "power2.out" }, at);
      PC.event("mascot", at, { el: m.id, move: "walk" });
      return PCM.hold(tl, m, at + F(14), o.until, { hold: o.hold, exit: o.exit });
    }'''
new3 = '''    if (kind === "walk") {
      var wf = o.walkFrames === undefined ? 14 : o.walkFrames;
      tl.fromTo(m, { opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      tl.fromTo(m, { x: o.dx === undefined ? -260 : o.dx }, { x: 0, duration: F(wf), ease: "power2.out" }, at);
      PC.event("mascot", at, { el: m.id, move: "walk" });
      return PCM.hold(tl, m, at + F(wf), o.until, { hold: o.hold, exit: o.exit });
    }'''
assert old3 in s
s = s.replace(old3, new3)
# PCM.hold passes o.hold through as the hold spec (a string or an object)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("pcm3 ok")
