/* paper-cards.js: the shared helpers of the motion library (styles/paper-cards, version 2): props, layout, the
   seeded PRNG, the event registry, the mascot's pixel art, the honesty chip. The motion itself (the four phases of
   every element, the combined main animations, the exits, the count-ups and typing, the canvas layers) lives in
   pc-motion.js (PCM, Motion and energy rules E1, E2, E5 to E7; M14); the PC.* moves below delegate to it so that
   the old call sites keep working. Loaded by every component from inside its <template> (HyperFrames runs it once
   per mount, in that mount's own window). Everything is a pure function of timeline time: no clocks, no Math.random.
   Frame counts and distances are the style's numbers (style.md Motion, vocabulary.md). 30 fps. */
(function () {
  "use strict";
  var FPS = 30;
  var PC = {};
  PC.FPS = FPS;
  PC.f = function (frames) { return frames / FPS; };

  // ---------------------------------------------------------------- variables (props)
  // PC.vars(defaults, raw): the mount's variables merged over the defaults, each coerced to the default's type; a key
  // ending in _json is parsed when it is a string.
  // The caller passes window.__hyperframes.getVariables() from its own inline script: HyperFrames gives each mount
  // its variables through a scoped window that only the inline scene script sees (this file runs in the real one).
  PC.vars = function (defaults, raw) {
    if (raw === undefined) {
      raw = {};
      try {
        if (window.__hyperframes && typeof window.__hyperframes.getVariables === "function") raw = window.__hyperframes.getVariables() || {};
      } catch (e) { raw = {}; }
    }
    raw = raw || {};
    var out = {};
    Object.keys(defaults).forEach(function (k) {
      var d = defaults[k], v = raw[k];
      if (v === undefined || v === null || (v === "" && typeof d !== "string")) v = d;
      if (typeof d === "number") { v = Number(v); if (!isFinite(v)) v = d; }
      else if (typeof d === "boolean") { v = (v === true || v === "true" || v === 1 || v === "1"); }
      else if (typeof d === "string") { v = String(v); }
      if (/_json$/.test(k) && typeof v === "string") {
        try { v = v.trim() ? JSON.parse(v) : d; } catch (e) { v = d; }
      }
      out[k] = v;
    });
    return out;
  };

  // ---------------------------------------------------------------- layout
  PC.place = function (el, o) {
    if (!el) return el;
    if (o.x !== undefined) el.style.left = o.x + "px";
    if (o.y !== undefined) el.style.top = o.y + "px";
    if (o.w !== undefined && o.w > 0) el.style.width = o.w + "px";
    if (o.h !== undefined && o.h > 0) el.style.height = o.h + "px";
    return el;
  };
  PC.capFont = function (capPx, ratio) { return capPx / (ratio || 0.72); };
  PC.el = function (tag, cls, parent, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  };
  PC.splitWords = function (el, text, cls) {
    el.textContent = "";
    var words = String(text).split(/\s+/).filter(function (w) { return w.length; });
    return words.map(function (w, i) {
      var span = PC.el("span", cls || "pc-word", el, w);
      span.style.display = "inline-block";
      if (i < words.length - 1) el.appendChild(document.createTextNode(" "));
      return span;
    });
  };
  PC.fmt = function (v, decimals) {
    var n = Number(v).toFixed(decimals || 0).split(".");
    n[0] = n[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return n.join(".");
  };
  PC.prng = function (seed) {  // mulberry32
    var a = (seed >>> 0) || 1;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  // a stable small integer from a string (seeds per reel: the idea id)
  PC.hash = function (s) {
    var h = 2166136261;
    s = String(s || "");
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0) % 1000000;
  };

  // ---------------------------------------------------------------- the moves (delegated to pc-motion.js, E1 and E2)
  // enter: the card move (opacity 0 to 1 over 5 frames, y +38 to 0 over 8 frames, expo.out) with its inertia and hold
  PC.enter = function (tl, el, at, o) {
    o = o || {};
    return PCM.life(tl, el, { at: at, main: { kind: "rise", rise: o.rise, opacityFrames: o.opacityFrames, positionFrames: o.positionFrames, ease: o.ease, zoom: o.zoom, rotate: o.rotate, axis: o.axis },
      hold: o.hold, exit: o.exit, until: o.until, inertia: o.inertia }).land;
  };
  // pop: scale from 0.5 to a peak of 1 + overshoot, then 1 (back-out); opacity reaches 1 within the first 4 frames
  PC.pop = function (tl, el, at, o) {
    o = o || {};
    return PCM.life(tl, el, { at: at, main: { kind: "pop", frames: o.frames, overshoot: o.overshoot, from: o.from, rotate: o.rotate, axis: o.axis }, hold: o.hold, exit: o.exit, until: o.until, inertia: o.inertia }).land;
  };
  // fly-in from a parked spot: travels dx, dy over frames (14), expo.out, start tilt easing to 0
  PC.flyIn = function (tl, el, at, o) {
    o = o || {};
    return PCM.life(tl, el, { at: at, main: { kind: "fly-in", dx: o.dx, dy: o.dy, tilt: o.tilt, endTilt: o.endTilt, frames: o.frames, rotate: o.rotate, axis: o.axis }, hold: o.hold, exit: o.exit, until: o.until, inertia: o.inertia }).land;
  };
  // fade: a plain fade over frames (4) with a small drift (the light chip, the callout, a caption word)
  PC.fade = function (tl, el, at, o) {
    o = o || {};
    return PCM.life(tl, el, { at: at, main: { kind: "fade", frames: o.frames, rise: o.rise, ease: o.ease, zoom: o.zoom, rotate: o.rotate, axis: o.axis }, hold: o.hold, exit: o.exit, until: o.until, inertia: o.inertia }).land;
  };
  // exit: fade-blur (4 frames, both look refs), fall (10 frames, ease-in, tilts 2 degrees, v07), push (6 frames out to the
  // left, v03), cut. Returns the time the element is gone.
  PC.exit = function (tl, el, at, type, o) { return PCM.exit(tl, el, at, type, o); };
  // count-up: a number counting from `from` to `to` over frames (27.5), ease-out (cubic)
  PC.countUp = function (tl, el, at, o) { return PCM.countUp(tl, el, at, o); };
  // typing: the text grows one character per framesPerChar frames (2 for keywords, 1.15 for chat)
  PC.typeInto = function (tl, el, text, at, o) { return PCM.typeInto(tl, el, text, at, o); };
  // a line drawn across an element (strike-through): scaleX 0 to 1 over frames (4), ease-out
  PC.strike = function (tl, line, at, o) {
    o = o || {};
    tl.fromTo(line, { scaleX: 0, transformOrigin: "0% 50%" }, { scaleX: 1, duration: PC.f(o.frames || 4), ease: "power2.out" }, at);
    PC.event("strike", at, { el: line.id });
    return at + PC.f(o.frames || 4);
  };

  // ---------------------------------------------------------------- events (the sound events, local seconds)
  // Every move registers what happened and when, on this mount's window: window.__pcEvents = [{type, t, ...}].
  // M10's events.py reads them from the mounted component; frame-match and the tests check that the declared frame
  // offsets are the ones the timeline uses.
  window.__pcEvents = window.__pcEvents || [];
  PC.event = function (type, t, extra) {
    var e = { type: type, t: Math.round(t * 1000) / 1000 };
    if (extra) Object.keys(extra).forEach(function (k) { e[k] = extra[k]; });
    window.__pcEvents.push(e);
    return e;
  };

  // ---------------------------------------------------------------- shared pieces
  PC.checkSVG = function () {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  };
  PC.honesty = function (parent, mode, o) {
    if (!mode || mode === "none") return null;
    o = o || {};
    var chip = PC.el("div", "pc-honesty", parent, mode === "sourced" ? (o.sourced || "real") : (o.mock || "illustrative"));
    chip.setAttribute("data-layout-ignore", "");  // a small label, texture for the layout audit (HyperFrames check)
    chip.style.right = (o.right === undefined ? 24 : o.right) + "px";
    chip.style.top = (o.top === undefined ? 20 : o.top) + "px";
    return chip;
  };
  // the mascot: pixel art on a 17 x 12 grid (85 x 58 px), body in the mascot color, one prop. The eyes (.pc-eye) blink
  // and the prop (.pc-prop) wiggles in the idle of pc-motion.js (E7).
  PC.mascotSVG = function (prop, color) {
    color = color || "#D67354";
    var ink = "#100904", acc = "#DC6532", paper = "#FFFAF7", ok = "#289C5C";
    var px = function (x, y, c, w, h, cls) { return '<rect x="' + x + '" y="' + y + '" width="' + (w || 1) + '" height="' + (h || 1) + '" fill="' + c + '"' + (cls ? ' class="' + cls + '"' : "") + '/>'; };
    var s = '<svg viewBox="0 0 17 12" xmlns="http://www.w3.org/2000/svg">';
    // body: a rounded blob with two ears, two legs
    s += px(3, 3, color, 9, 7) + px(2, 4, color, 1, 5) + px(12, 4, color, 1, 5) + px(4, 2, color, 7, 1) + px(4, 1, color, 1, 1) + px(10, 1, color, 1, 1);
    s += px(4, 10, color, 2, 1) + px(9, 10, color, 2, 1) + px(4, 11, ink, 2, 1) + px(9, 11, ink, 2, 1);
    // face
    s += px(5, 5, paper, 2, 2) + px(9, 5, paper, 2, 2) + px(6, 6, ink, 1, 1, "pc-eye") + px(10, 6, ink, 1, 1, "pc-eye") + px(7, 8, ink, 2, 1);
    // the prop, held to the right
    s += '<g class="pc-prop">';
    if (prop === "star") s += px(14, 3, acc) + px(13, 4, acc, 3, 1) + px(14, 5, acc) + px(13, 6, acc) + px(15, 6, acc);
    else if (prop === "film") s += px(13, 3, ink, 3, 5) + px(14, 4, paper) + px(14, 6, paper) + px(13, 3, acc, 1, 1) + px(15, 7, acc, 1, 1);
    else if (prop === "play") s += px(13, 3, acc, 1, 5) + px(14, 4, acc, 1, 3) + px(15, 5, acc, 1, 1);
    else if (prop === "grid") s += px(13, 3, ink, 2, 2) + px(15, 3, acc, 2, 2) + px(13, 5, acc, 2, 2) + px(15, 5, ink, 2, 2);
    else if (prop === "check") s += px(13, 4, ok, 1, 1) + px(14, 5, ok, 1, 1) + px(15, 4, ok, 1, 1) + px(16, 3, ok, 1, 1);
    else s += px(13, 3, ink, 3, 1) + px(13, 4, paper, 3, 3) + px(13, 4, ink, 1, 3) + px(15, 4, ink, 1, 3) + px(14, 2, acc, 1, 1);  // clapperboard
    s += "</g></svg>";
    return s;
  };
  PC.mascot = function (parent, prop, cls) {
    var m = PC.el("div", "pc-mascot pc-el " + (cls || ""), parent);
    m.innerHTML = PC.mascotSVG(prop, getComputedStyle(document.documentElement).getPropertyValue("--c-mascot").trim() || "#D67354");
    return m;
  };
  // the mascot's entrance: 4 frames after its card lands, rising in from below the element over 4 frames (v02), then
  // its hold and idle (pc-motion.js)
  PC.mascotEnter = function (tl, m, landAt, o) { return PCM.mascotEnter(tl, m, landAt, o).land; };

  window.PC = PC;
})();
