p = "motion-lib/assets/pc-motion.js"
s = open(p, encoding="utf-8").read()
old = '''    if (type === "cut") { tl.set(el, { opacity: 0 }, at); PC.event("exit", at, { el: name, type: type }); return at; }'''
new = '''    if (type === "cut") { tl.set(el, { opacity: 0 }, at); PC.event("exit", at, { el: name, type: type }); return at; }
    if (type === "fade") {  // a plain fade (the caption chunk replace: 2 frames out)
      var df = o.frames || 2;
      tl.to(el, { opacity: 0, duration: F(df), ease: "none" }, at);
      PC.event("exit", at, { el: name, type: type }); return at + F(df);
    }'''
assert old in s
s = s.replace(old, new)
old2 = '''  // a slow deterministic wobble (the end card, v02)'''
new2 = '''  // a bar or a line growing (chart bars over 12 frames, the progress fill over 6, a strike line over 4): scaleX or scaleY
  // from 0 to `to` (1) with an ease-out
  PCM.grow = function (tl, el, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 12 : o.frames;
    var prop = (o.axis || "y") === "x" ? "scaleX" : "scaleY";
    var fromV = {}, toV = {};
    fromV[prop] = 0; fromV.transformOrigin = o.origin || ((o.axis || "y") === "x" ? "0% 50%" : "50% 100%");
    toV[prop] = o.to === undefined ? 1 : o.to; toV.duration = F(frames); toV.ease = o.ease || "power3.out";
    tl.fromTo(el, fromV, toV, at);
    PC.event(o.event || "grow", at, { el: el.id, end: at + F(frames) });
    return at + F(frames);
  };
  // a stroke drawing itself (a gauge arc, a hand-drawn arrow): strokeDashoffset from the path's length to `to`
  PCM.draw = function (tl, pathEl, at, o) {
    o = o || {};
    var len = o.length === undefined ? pathEl.getTotalLength() : o.length;
    pathEl.style.strokeDasharray = len + " " + len;
    var frames = o.frames === undefined ? 8 : o.frames;
    tl.fromTo(pathEl, { strokeDashoffset: len }, { strokeDashoffset: o.to === undefined ? 0 : o.to, duration: F(frames), ease: o.ease || "power1.inOut" }, at);
    return at + F(frames);
  };
  // a slow deterministic wobble (the end card, v02)'''
assert old2 in s
s = s.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("pcm2 ok")
