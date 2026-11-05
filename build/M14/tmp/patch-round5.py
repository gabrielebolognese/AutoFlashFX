"""Round 5: the last curves move out of the components (PCM.dim, PCM.recolor, PCM.spin), so no composition file holds an
ease or a tween of its own; the icon-3d fallback's entrance and turn come from pc-motion.js."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("motion-lib/assets/pc-motion.js", [
    ('''  // a slow deterministic wobble (the end card, v02)''',
     '''  // a change of state that is not a move: an element dims (the struck text), a button recolors (the chat's send button)
  PCM.dim = function (tl, el, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 3 : o.frames;
    tl.to(el, { opacity: o.to === undefined ? 0.55 : o.to, duration: F(frames), ease: "none" }, at);
    return at + F(frames);
  };
  PCM.recolor = function (tl, el, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 2 : o.frames;
    var vars = { duration: F(frames), ease: "none" };
    if (o.backgroundColor) vars.backgroundColor = o.backgroundColor;
    if (o.color) vars.color = o.color;
    tl.to(el, vars, at);
    return at + F(frames);
  };
  // a steady turn (the CSS-extruded icon): rotationY at degPerSecond for seconds, linear
  PCM.spin = function (tl, el, at, o) {
    o = o || {};
    var seconds = o.seconds || PCM.numbers().horizon, speed = o.degPerSecond === undefined ? 24 : o.degPerSecond;
    var prop = o.prop || "rotationY";
    var fromV = {}, toV = {};
    fromV[prop] = o.from || 0; toV[prop] = (o.from || 0) + speed * seconds; toV.duration = seconds; toV.ease = "none"; toV.immediateRender = false;
    tl.fromTo(el, fromV, toV, at);
    return at + seconds;
  };
  // a slow deterministic wobble (the end card, v02)'''),
])

patch("motion-lib/compositions/strike-through.html", [
    ('''      tl.to(text, { opacity: 0.55, duration: PC.f(3), ease: "none" }, t);''', '''      PCM.dim(tl, text, t, { to: 0.55, frames: 3 });'''),
])
patch("motion-lib/compositions/chat-card.html", [
    ('''      tl.to(send, { backgroundColor: accent, duration: PC.f(v.send_frames), ease: "none" }, sendAt);''',
     '''      PCM.recolor(tl, send, sendAt, { backgroundColor: accent, frames: v.send_frames });'''),
])
patch("motion-lib/compositions/icon-3d.html", [
    ('''        tl.fromTo(css, { scale: 0.01, opacity: 0 }, { scale: 1, opacity: 1, duration: enterDur, ease: "back.out(1.3)" }, v.enter_at);
        tl.fromTo(css, { rotationY: 0 }, { rotationY: v.spin * T, duration: T, ease: "none", immediateRender: false }, v.enter_at);
        PCM.sway(tl, css, "y", 0, size * 0.03, 3.9, 0.1, T, v.enter_at);
        PCM.sway(tl, css, "rotationZ", 0, 3, 9, 0.3, T, v.enter_at);''',
     '''        PCM.life(tl, css, { at: v.enter_at, main: { kind: "pop", from: 0.01, overshoot: 0.1, frames: v.enter_frames, rotate: false }, hold: { kind: "none" }, inertia: { move: 0, scale: 0, rotate: 0 }, until: v.enter_at + enterDur + PC.f(1), events: { enter: "css_enter", land: "css_peak" } });
        PCM.spin(tl, css, v.enter_at, { degPerSecond: v.spin, seconds: T });
        PCM.sway(tl, css, "y", 0, size * 0.03, 3.9, 0.1, T, v.enter_at);
        PCM.sway(tl, css, "rotationZ", 0, 3, 9, 0.3, T, v.enter_at);'''),
])
print("round 5 done")
