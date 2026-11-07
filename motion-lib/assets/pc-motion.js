/* pc-motion.js: the shared motion grammar of the motion library (BUILD_SPEC.md section 5, Motion and energy rules
   E1, E2, E5, E6, E7; M14). Every component takes its phases, curves, edges, background life and depth from here;
   no component hand-rolls a phase or a curve (E9). Loaded after paper-cards.js; the numbers come from tokens.css
   (--m-* custom properties, generated from tokens.json motion.grammar), with the spec's values as defaults.

   E1, the life of every element: main animation (0.3 to 0.6 s: the style's measured enter frames for opacity and
   position, the pops' overshoot), then 2 to 4 s of inertia (the move carries on in the same direction and slows down
   on a decelerating ease-out whose speed never reaches zero), then the hold (a steady drift of 2 to 8 px per second,
   a parallax rotation of 0.2 to 0.6 degrees per second or a scale creep of 0.2 to 0.5 percent per second; three
   levels: calm, normal, lively), then the exit (0.2 to 0.4 s, ease-in) or the scene change.
   E2, combined main animations: a zoom (scale 0.85 to 1, or 1.15 to 1 from a close start) with a 3D parallax
   rotation (rotateY or rotateX from 8 to 15 degrees down to 0 to 2, inside a perspective of 1200 to 1600 px) and a
   short move; power3.inOut for the combined properties, the rotation 2 to 4 frames late, settling last.
   E5 and E7, the canvas: the edge filler layer (elements 30 to 70 percent outside the frame, at most 20 px per
   second, no text) and the ambient layer (stars, dots, small clouds, a slow drift and twinkle), seeded per reel.
   E6, depth: an element becomes a small 2.5D scene (preserve-3d, its parts at their own depths) under the slowly
   turning hold rotation, which is the camera.

   Everything is a GSAP tween on a real property (position, scale, rotation, opacity, or an accessor property whose
   setter renders text): HyperFrames seeks timelines with events suppressed, so onUpdate callbacks never fire in a
   render (DECISIONS.md M14). Every number is a pure function of timeline time; nothing is random (PC.prng is seeded).
   30 fps. */
(function () {
  "use strict";
  var FPS = 30;
  var F = function (frames) { return frames / FPS; };
  var PCM = {};
  PCM.FPS = FPS;
  PCM.f = F;

  // ---------------------------------------------------------------- the numbers (tokens.css --m-*, spec defaults)
  var NUMS = null;
  function cssNum(name, dflt) {
    try {
      var v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
      return isFinite(v) ? v : dflt;
    } catch (e) { return dflt; }
  }
  function cssText(name, dflt) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      return v && v.trim() ? v.trim() : dflt;
    } catch (e) { return dflt; }
  }
  PCM.numbers = function () {
    if (NUMS) return NUMS;
    var level = function (name, d, r, s) {
      return { drift: cssNum("--m-hold-" + name + "-drift", d), rotate: cssNum("--m-hold-" + name + "-rotate", r), scale: cssNum("--m-hold-" + name + "-scale", s) };
    };
    NUMS = {
      perspective: cssNum("--m-perspective", 1400),
      mainFrames: cssNum("--m-main-frames", 18),
      zoomFrom: cssNum("--m-zoom-from", 0.85),
      zoomFromSmall: cssNum("--m-zoom-from-small", 0.92),
      zoomFromClose: cssNum("--m-zoom-from-close", 1.15),
      rotateFrom: cssNum("--m-rotate-from", 12),
      rotateTo: cssNum("--m-rotate-to", 1),
      rotateLag: cssNum("--m-rotate-lag", 3),
      moveShort: cssNum("--m-move-short", 24),
      inertiaS: cssNum("--m-inertia-s", 3),
      inertiaMove: cssNum("--m-inertia-move", 16),
      inertiaScale: cssNum("--m-inertia-scale", 0.04),
      inertiaRotate: cssNum("--m-inertia-rotate", 2),
      hold: { calm: level("calm", 2, 0.2, 0.2), normal: level("normal", 4, 0.4, 0.35), lively: level("lively", 8, 0.6, 0.5) },
      horizon: cssNum("--m-horizon-s", 90),
      edgeMaxSpeed: cssNum("--m-edge-max-speed", 20),
      edgeOutsideMin: cssNum("--m-edge-outside-min", 0.3),
      edgeOutsideMax: cssNum("--m-edge-outside-max", 0.7),
      ambientMaxSpeed: cssNum("--m-ambient-max-speed", 10),
      depthStep: cssNum("--m-depth-step", 24),
      scrollSpeed: cssNum("--m-scroll-px-s", 30),
      zones: ["caption", "hook", "endcard"].map(function (k) {
        var parts = cssText("--m-zone-" + k, "").split(/\s+/).map(parseFloat).filter(function (n) { return isFinite(n); });
        return parts.length === 4 ? { x: parts[0], y: parts[1], w: parts[2], h: parts[3] } : null;
      }).filter(Boolean)
    };
    if (!NUMS.zones.length) NUMS.zones = [{ x: 200, y: 1152, w: 680, h: 260 }, { x: 90, y: 233, w: 900, h: 470 }, { x: 200, y: 324, w: 680, h: 640 }];
    return NUMS;
  };
  PCM.holdLevel = function (name) {
    var N = PCM.numbers();
    return N.hold[name] || N.hold.normal;
  };

  // ---------------------------------------------------------------- curves
  // The inertia and the hold as one curve: d(t) = A (1 - (1 - min(t, D) / D)^3) + v t, a decelerating cubic ease-out
  // on top of a constant drift, so the speed falls from 3A/D + v to v and never reaches zero. As a GSAP ease over a
  // tween of duration T and distance A + v T.
  PCM.glide = function (A, v, D, T) {
    var total = A + v * T;
    if (!(total > 0) || !(T > 0)) return function (p) { return p; };
    return function (p) {
      var t = Math.max(0, Math.min(1, p)) * T;
      var td = D > 0 ? Math.min(t, D) / D : 1;
      return (A * (1 - Math.pow(1 - td, 3)) + v * t) / total;
    };
  };
  // the sine oscillation of the canvas layers: position = -a + 2a * sine.inOut(p), peak speed 2 pi a / period
  PCM.periodFor = function (amplitude, maxSpeed) { return Math.max(4, (2 * Math.PI * amplitude) / Math.max(0.5, maxSpeed)); };

  // ---------------------------------------------------------------- the root: a perspective for every element
  // Each element carries its own perspective (transformPerspective, the vanishing point at its center): a rotated
  // element projects symmetrically around its center, so its measured center is exact (frame-match, S12).
  PCM.prepare = function (el, o) {
    o = o || {};
    var N = PCM.numbers();
    gsap.set(el, { transformPerspective: o.perspective || N.perspective, transformOrigin: o.origin || "50% 50%", force3D: true });
    return el;
  };
  // E6: the element is a small 2.5D scene; its named parts sit at their own depths and the hold rotation is the camera.
  // Not for elements with overflow hidden or a filter (the browser flattens those).
  PCM.depth = function (el, parts, o) {
    o = o || {};
    var N = PCM.numbers();
    var step = o.step === undefined ? N.depthStep : o.step;
    gsap.set(el, { transformStyle: "preserve-3d" });
    (parts || []).forEach(function (p, i) {
      if (!p) return;
      gsap.set(p, { z: (o.from || 0) + step * (i + 1), force3D: true });
    });
    return el;
  };

  // ---------------------------------------------------------------- the four phases
  function sign(v) { return v < 0 ? -1 : 1; }
  function normMain(main) {
    if (!main) return { kind: "rise" };
    if (typeof main === "string") return { kind: main };
    var m = {}; Object.keys(main).forEach(function (k) { m[k] = main[k]; });
    if (!m.kind) m.kind = "rise";
    return m;
  }

  // PCM.life(tl, el, o): the whole life of one element on the timeline tl. Returns {land, rotLand, scaleLand, until,
  // exitEnd, end: {x, y}}. Options:
  //   at          the start (s, local), default 0
  //   main        a kind or {kind, ...}: rise (opacity 5 frames, y +rise over 8 frames expo.out: the card enter),
  //               drop (from above), fly-in (dx, dy, tilt, endTilt, frames: expo.out, the fly-in), pop (from, overshoot,
  //               frames: scale with a back-out), fade (frames, rise: a plain fade with a small drift), slide (dx, frames,
  //               overshoot: a slide that overshoots a few px and settles), none (visible from the start);
  //               zoom: false | "in" | "close" | "small" (the combined zoom, E2), rotate: false | degrees, axis: "y" | "x",
  //               rotateSign: 1 | -1, lag: frames, mainFrames: the combined properties' frames, opacityFrames, positionFrames
  //   hold        "calm" | "normal" | "lively" or {level, kind: "drift" | "rotate" | "scale" | "all" | "none", dir: {x, y}}
  //   inertia     {seconds, move, scale, rotate} (defaults from the tokens; move 0 when the main has no move)
  //   exit        {type: none | fade-blur | fall | push | cut, at, frames, distance}
  //   until       when the hold ends (default: the exit, else at + horizon)
  //   events      {enter, land, el}: the event names registered (default enter and land; pops register pop and pop_peak)
  PCM.life = function (tl, el, o) {
    o = o || {};
    var N = PCM.numbers();
    var at = o.at || 0;
    var main = normMain(o.main);
    var kind = main.kind;
    var holdSpec = (typeof o.hold === "string" || !o.hold) ? { level: o.hold || "normal", kind: "all" } : o.hold;
    var H = PCM.holdLevel(holdSpec.level || "normal");
    var holdKind = holdSpec.kind || "all";
    var drift = (holdKind === "all" || holdKind === "drift" || holdKind === "drift-rotate") ? H.drift : 0;
    var omega = (holdKind === "all" || holdKind === "rotate" || holdKind === "drift-rotate" || holdKind === "rotate-scale") ? H.rotate : 0;
    var creep = (holdKind === "all" || holdKind === "scale" || holdKind === "rotate-scale") ? H.scale / 100 : 0;
    if (holdKind === "none") { drift = 0; omega = 0; creep = 0; }
    var inert = o.inertia || {};
    var D = inert.seconds === undefined ? N.inertiaS : inert.seconds;
    var exitType = (o.exit && o.exit.type) || "none";
    var exitAt = o.exit ? o.exit.at : undefined;
    var hasExit = exitType !== "none" && exitAt !== undefined && exitAt !== null && exitAt >= 0;
    var mainFrames = main.mainFrames === undefined ? N.mainFrames : main.mainFrames;
    var lag = main.lag === undefined ? N.rotateLag : main.lag;
    var evName = (o.events && o.events.el) || el.id;
    var ev = o.events || {};
    PCM.prepare(el, o);

    // 1. the main animation (the style's measured move) ....................................................
    var land = at, dir = { x: 0, y: -1 }, hadMove = true, zoomDefault = "in";
    if (kind === "rise" || kind === "drop") {
      var of = main.opacityFrames === undefined ? 5 : main.opacityFrames;
      var pf = main.positionFrames === undefined ? 8 : main.positionFrames;
      var rise = main.rise === undefined ? 38 : main.rise;
      var from = kind === "drop" ? -Math.abs(rise) : rise;
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: F(of), ease: "power1.out" }, at);
      tl.fromTo(el, { y: from }, { y: 0, duration: F(pf), ease: main.ease || "expo.out" }, at);
      land = at + F(pf);
      dir = { x: 0, y: kind === "drop" ? 1 : -1 };
      PC.event(ev.enter || "enter", at, { el: evName }); PC.event(ev.land || "land", land, { el: evName });
    } else if (kind === "fly-in") {
      var ff = main.frames === undefined ? 14 : main.frames;
      var dx = main.dx || 0, dy = main.dy === undefined ? 930 : main.dy;
      tl.fromTo(el, { x: dx, y: dy, rotation: main.tilt === undefined ? 3.9 : main.tilt }, { x: 0, y: 0, rotation: main.endTilt || 0, duration: F(ff), ease: "expo.out" }, at);
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      land = at + F(ff);
      var len = Math.hypot(dx, dy) || 1;
      dir = { x: -dx / len, y: -dy / len };
      zoomDefault = "close";
      PC.event(ev.enter || "enter", at, { el: evName, move: "fly-in" }); PC.event(ev.land || "land", land, { el: evName });
    } else if (kind === "pop") {
      var frames = main.frames === undefined ? 7 : main.frames;
      var over = main.overshoot === undefined ? 0.02 : main.overshoot;
      var from0 = main.from === undefined ? 0.5 : main.from;
      var up = Math.max(1, Math.round(frames * 0.55)), down = Math.max(1, frames - up);
      tl.fromTo(el, { scale: from0 }, { scale: 1 + over, duration: F(up), ease: "power2.out" }, at);
      tl.to(el, { scale: 1, duration: F(down), ease: "power1.inOut" }, at + F(up));
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: F(Math.min(4, frames)), ease: "none" }, at);
      land = at + F(frames);
      hadMove = false;
      zoomDefault = false;  // the pop is the scale
      PC.event(ev.enter || "pop", at, { el: evName }); PC.event(ev.land || "pop_peak", at + F(up), { el: evName });
    } else if (kind === "fade") {
      var fr = main.frames === undefined ? 4 : main.frames;
      var fdrift = main.rise === undefined ? 10 : main.rise;
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: F(fr), ease: main.ease || "none" }, at);
      if (fdrift) tl.fromTo(el, { y: fdrift }, { y: 0, duration: F(fr), ease: "power2.out" }, at);
      land = at + F(fr);
      hadMove = !!fdrift;
      zoomDefault = "small";
      PC.event(ev.enter || "enter", at, { el: evName });
    } else if (kind === "slide") {
      var sf = main.frames === undefined ? 9 : main.frames;
      var sdx = main.dx === undefined ? -200 : main.dx;
      var sover = main.overshoot === undefined ? 6 : main.overshoot;
      var s1 = Math.max(2, sf - 2);
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      tl.fromTo(el, { x: sdx }, { x: -sign(sdx) * sover, duration: F(s1), ease: "power2.out" }, at);
      tl.to(el, { x: 0, duration: F(sf - s1), ease: "power1.inOut" }, at + F(s1));
      land = at + F(sf);
      dir = { x: -sign(sdx), y: 0 };
      zoomDefault = "small";
      PC.event(ev.enter || "slide", at, { el: evName });
    } else {  // none: visible from the start
      land = at;
      hadMove = false;
      zoomDefault = false;
    }
    // 2. the combined properties (E2): a zoom and a 3D parallax rotation, power3.inOut, the rotation lagging .....
    var zoom = main.zoom === undefined ? zoomDefault : main.zoom;
    var scaleLand = land;
    if (zoom && kind !== "pop" && kind !== "none") {
      var z0 = zoom === "close" ? N.zoomFromClose : (zoom === "small" ? N.zoomFromSmall : (typeof zoom === "number" ? zoom : N.zoomFrom));
      tl.fromTo(el, { scale: z0 }, { scale: 1, duration: F(mainFrames), ease: "power3.inOut" }, at);
      scaleLand = at + F(mainFrames);
    }
    var rotate = main.rotate === undefined ? (kind === "none" ? false : N.rotateFrom) : main.rotate;
    var rotProp = (main.axis || "y") === "x" ? "rotationX" : "rotationY";
    var rotSign = main.rotateSign || 1;
    var rotLand = land, rotEnd = 0;
    if (rotate) {
      var r0 = rotSign * rotate, r1 = rotSign * N.rotateTo;
      tl.fromTo(el, (function () { var s = {}; s[rotProp] = r0; return s; })(), (function () { var s = {}; s[rotProp] = r1; s.duration = F(mainFrames); s.ease = "power3.inOut"; return s; })(), at + F(lag));
      rotLand = at + F(lag) + F(mainFrames);
      rotEnd = r1;
    }
    // the main animation's window, for the review (S12 does not judge an element while it arrives: the zoom and the
    // rotation are transients by design, E2)
    if (kind !== "none") PCM.mark(el, "data-pcm-main", at, Math.max(land, scaleLand, rotLand));
    // 3. the inertia and the hold ............................................................................
    var until = o.until !== undefined && o.until !== null ? o.until : (hasExit ? exitAt : at + N.horizon);
    until = Math.max(until, land + F(1), scaleLand + F(1), rotLand + F(1));
    if (hasExit) until = Math.min(until, Math.max(exitAt, land + F(1)));
    var A = inert.move === undefined ? (hadMove ? N.inertiaMove : (kind === "pop" ? N.inertiaMove * 0.5 : 0)) : inert.move;
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
    }
    var rA = inert.rotate === undefined ? (rotate ? N.inertiaRotate : 0) : inert.rotate;
    var Tr = until - rotLand;
    if (Tr > 0 && (rA > 0 || omega > 0)) {
      var rTotal = rA + omega * Tr;
      var toRot = {}; toRot[rotProp] = rotEnd - rotSign * rTotal; toRot.duration = Tr; toRot.ease = PCM.glide(rA, omega, D, Tr); toRot.immediateRender = false;
      var fromRot = {}; fromRot[rotProp] = rotEnd;
      tl.fromTo(el, fromRot, toRot, rotLand);
    }
    // 4. the exit ...............................................................................................
    var exitEnd = null;
    if (hasExit) exitEnd = PCM.exit(tl, el, Math.max(exitAt, land), exitType, { frames: o.exit.frames, distance: o.exit.distance, from: end, el: evName });
    return { land: land, scaleLand: scaleLand, rotLand: rotLand, until: until, exitEnd: exitEnd, end: end, dir: dir };
  };

  // the exits (style.md Exit, open question 3): fade-blur 4 frames, fall 10 frames ease-in tilting 2 degrees, push 6
  // frames out to the left, cut. `from` is where the hold left the element (absolute targets: no relative values, so
  // the result does not depend on the order the frames are rendered in).
  PCM.exit = function (tl, el, at, type, o) {
    o = o || {};
    type = type || "none";
    if (type === "none" || at === undefined || at === null || at < 0) return at;
    var from = o.from || { x: 0, y: 0 };
    var name = o.el || el.id;
    if (type === "cut") { tl.set(el, { opacity: 0 }, at); PC.event("exit", at, { el: name, type: type }); return at; }
    var end;
    if (type === "fade") {  // a plain fade (the caption chunk replace: 2 frames out)
      var df = o.frames || 2;
      tl.to(el, { opacity: 0, duration: F(df), ease: "none" }, at);
      end = at + F(df);
    } else if (type === "fall") {
      var ff = o.frames || 10;
      tl.to(el, { y: from.y + (o.distance || 1700), rotation: o.tilt === undefined ? 2 : o.tilt, duration: F(ff), ease: "power2.in" }, at);
      end = at + F(ff);
    } else if (type === "push") {
      var pf = o.frames || 6;
      tl.to(el, { x: from.x - (o.distance || 1300), duration: F(pf), ease: "power2.in" }, at);
      end = at + F(pf);
    } else {
      type = "fade-blur";
      var bf = o.frames || 4;
      tl.to(el, { opacity: 0, filter: "blur(8px)", duration: F(bf), ease: "power2.in" }, at);
      end = at + F(bf);
    }
    PCM.mark(el, "data-pcm-exit", at, end);  // the leaving window, for the review (the element is not judged mid-exit)
    PC.event("exit", at, { el: name, type: type });
    return end;
  };

  // PCM.mark(el, name, from, to): a window of the element's life in local seconds, "from,to", read by the review (S12):
  // data-pcm-main is the main animation (E1 phase 1 with E2's zoom and rotation), data-pcm-exit the exit (phase 4)
  PCM.mark = function (el, name, from, to) {
    if (!el || !el.setAttribute || !(to > from)) return;
    el.setAttribute(name, from.toFixed(4) + "," + to.toFixed(4));
  };

  // a hold alone (an element that is already visible, a group container): the steady drift, rotation or creep
  PCM.hold = function (tl, el, at, until, o) {
    o = o || {};
    return PCM.life(tl, el, { at: at, main: { kind: "none" }, hold: o.hold || "normal", until: until, inertia: { move: 0, scale: 0, rotate: 0 }, exit: o.exit, events: o.events });
  };

  // ---------------------------------------------------------------- values rendered by a setter (count-ups, typing)
  // GSAP tweens the accessor property; its setter renders. No callback, so it works under suppressed events.
  PCM.driven = function (initial, render) {
    var state = { _v: initial };
    Object.defineProperty(state, "v", { get: function () { return this._v; }, set: function (x) { this._v = x; render(x); }, enumerable: true, configurable: true });
    render(initial);
    return state;
  };
  PCM.countUp = function (tl, el, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 27.5 : o.frames;
    var dec = o.decimals || 0, prefix = o.prefix || "", suffix = o.suffix || "";
    var state = PCM.driven(o.from || 0, function (x) { el.textContent = prefix + PC.fmt(x, dec) + suffix; });
    tl.to(state, { v: o.to, duration: F(frames), ease: o.ease || "power3.out" }, at);
    PC.event("count_start", at, { el: el.id }); PC.event("count_end", at + F(frames), { el: el.id });
    return at + F(frames);
  };
  PCM.typeInto = function (tl, el, text, at, o) {
    o = o || {};
    var fpc = o.framesPerChar === undefined ? 2 : o.framesPerChar;
    var str = String(text), len = str.length;
    var caret = o.caret ? "|" : "";
    var render = o.render || function (n) { el.textContent = str.slice(0, n) + (n < len ? caret : ""); };
    var state = PCM.driven(0, function (x) { render(Math.max(0, Math.min(len, Math.round(x)))); });
    if (len > 0) tl.to(state, { v: len, duration: F(fpc * len), ease: "none" }, at);
    PC.event("typing", at, { el: el.id, end: at + F(fpc * len), chars: len });
    return at + F(fpc * len);
  };
  // the camera move (vocabulary.md 19): the whole stage shrinks into a window over frames (8, power2.out: v02) or grows
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
  // a bar or a line growing (chart bars over 12 frames, the progress fill over 6, a strike line over 4): scaleX or scaleY
  // from 0 to `to` (1) with an ease-out
  PCM.grow = function (tl, el, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 12 : o.frames;
    var prop = (o.axis || "y") === "x" ? "scaleX" : "scaleY";
    var fromV = {}, toV = {};
    fromV[prop] = 0.001; fromV.transformOrigin = o.origin || ((o.axis || "y") === "x" ? "0% 50%" : "50% 100%");  // a hair, not zero: a flat plane in a 3D context reads a few px tall
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
  // a change of state that is not a move: an element dims (the struck text), a button recolors (the chat's send button)
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
  // a slow pan of content inside a frame (a screenshot in a window card): a steady move, linear
  PCM.pan = function (tl, el, at, o) {
    o = o || {};
    var seconds = Math.max(0.5, o.seconds || 1);
    tl.fromTo(el, { x: 0, y: 0 }, { x: o.dx || 0, y: o.dy || 0, duration: seconds, ease: "none", immediateRender: false }, at);
    return at + seconds;
  };
  // a screenshot scrolling inside its window (object-fit cover, taller than the window): its object-position moves from
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
  // a slow deterministic wobble (the end card, v02): rotation and y as sines of time, finite repeats
  PCM.wobble = function (tl, el, at, seconds, o) {
    o = o || {};
    var amp = o.rotate === undefined ? 0.35 : o.rotate, dy = o.y === undefined ? 2.5 : o.y, base = o.baseRotation || 0;
    var pr = o.periodRotate || 3.0, py = o.periodY || 4.1;
    var reps = Math.max(1, Math.ceil(seconds / pr));
    tl.fromTo(el, { rotation: base - amp }, { rotation: base + amp, duration: pr / 2, ease: "sine.inOut", yoyo: true, repeat: reps * 2, immediateRender: false }, at);
    if (dy > 0 && o.yTarget) {
      var repsY = Math.max(1, Math.ceil(seconds / py));
      tl.fromTo(o.yTarget, { y: -dy }, { y: dy, duration: py / 2, ease: "sine.inOut", yoyo: true, repeat: repsY * 2, immediateRender: false }, at);
    }
    return at + seconds;
  };

  // ---------------------------------------------------------------- the mascot: moves and the idle (E7)
  // the entrance: rise from below the element over 4 frames, 4 frames after its card lands (v02); pop (v01); hop (v09);
  // walk in from the left (v03). The idle runs on the inner svg (the life on the wrapper): a bob, a blink, a wiggle of
  // the prop.
  PCM.mascotMove = function (tl, m, kind, at, o) {
    o = o || {};
    var frames = o.frames === undefined ? 4 : o.frames;
    if (kind === "pop") {
      return PCM.life(tl, m, { at: at, main: { kind: "pop", overshoot: 0.16, frames: Math.max(3, frames), from: 0.4, rotate: 8 }, hold: o.hold, exit: o.exit, until: o.until, events: { enter: "mascot" } });
    }
    if (kind === "hop") {
      // hop 72 up and back over 11 frames, 5 up and 6 down (v09), then the life's hold
      tl.fromTo(m, { opacity: 0 }, { opacity: 1, duration: F(2), ease: "none" }, at);
      tl.fromTo(m, { y: 0 }, { y: -72, duration: F(5), ease: "power2.out" }, at);
      tl.to(m, { y: 0, duration: F(6), ease: "power2.in" }, at + F(5));
      PC.event("mascot", at, { el: m.id, move: "hop" });
      return PCM.hold(tl, m, at + F(11), o.until, { hold: o.hold, exit: o.exit });
    }
    if (kind === "walk") {
      var wf = o.walkFrames === undefined ? 14 : o.walkFrames;
      tl.fromTo(m, { opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      tl.fromTo(m, { x: o.dx === undefined ? -260 : o.dx }, { x: 0, duration: F(wf), ease: "power2.out" }, at);
      PC.event("mascot", at, { el: m.id, move: "walk" });
      return PCM.hold(tl, m, at + F(wf), o.until, { hold: o.hold, exit: o.exit });
    }
    return PCM.life(tl, m, { at: at, main: { kind: "fade", frames: frames, rise: 30, ease: "power2.out", zoom: "small", rotate: 10 }, hold: o.hold, exit: o.exit, until: o.until, events: { enter: "mascot" } });
  };
  PCM.mascotEnter = function (tl, m, landAt, o) {
    o = o || {};
    var delay = o.delayFrames === undefined ? 4 : o.delayFrames;
    var at = landAt + F(delay);
    var life = PCM.mascotMove(tl, m, "rise", at, { frames: o.frames === undefined ? 4 : o.frames, hold: o.hold, exit: o.exit, until: o.until });
    PCM.idle(tl, m, at, (o.until || (at + PCM.numbers().horizon)) - at, { seed: o.seed });
    return life;
  };
  PCM.idle = function (tl, m, at, seconds, o) {
    o = o || {};
    var svg = m.querySelector("svg");
    if (!svg || !(seconds > 0)) return at;
    var rnd = PC.prng((o.seed || 0) + 11);
    var bobP = 1.4 + rnd() * 0.5, bob = o.bob === undefined ? 3 : o.bob;
    var reps = Math.max(1, Math.ceil(seconds / bobP));
    gsap.set(svg, { transformOrigin: "50% 100%" });
    tl.fromTo(svg, { y: bob }, { y: -bob, duration: bobP / 2, ease: "sine.inOut", yoyo: true, repeat: reps * 2, immediateRender: false }, at);
    tl.fromTo(svg, { scaleY: 1 }, { scaleY: 1.045, duration: bobP / 2, ease: "sine.inOut", yoyo: true, repeat: reps * 2, immediateRender: false }, at + bobP * 0.25);
    var prop = svg.querySelector(".pc-prop");
    if (prop) {
      var wP = 1.9 + rnd() * 0.6;
      gsap.set(prop, { transformOrigin: "20% 80%" });
      tl.fromTo(prop, { rotation: -6 }, { rotation: 6, duration: wP / 2, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.ceil(seconds / wP)) * 2, immediateRender: false }, at + rnd() * 0.5);
    }
    var eyes = svg.querySelectorAll(".pc-eye");
    if (eyes.length) {
      var blinkEvery = 2.6 + rnd() * 1.2, t = at + 0.9 + rnd() * 0.8;
      while (t < at + seconds) {
        tl.fromTo(eyes, { scaleY: 1, transformOrigin: "50% 50%" }, { scaleY: 0.1, duration: F(2), ease: "none", yoyo: true, repeat: 1, immediateRender: false }, t);
        t += blinkEvery;
      }
    }
    return at + seconds;
  };

  // ---------------------------------------------------------------- the speech bubble and the confetti (end card)
  PCM.bubble = function (tl, el, at, o) {
    o = o || {};
    var bf = o.frames === undefined ? 7 : o.frames, over = o.overshootY === undefined ? 40 : o.overshootY, settle = o.settleFrames === undefined ? 9 : o.settleFrames;
    PCM.prepare(el, { origin: "20% 100%" });
    tl.fromTo(el, { scale: 0.5, opacity: 0 }, { scale: 1, opacity: 1, duration: F(bf), ease: "power2.out" }, at);
    tl.fromTo(el, { y: 0 }, { y: -over, duration: F(bf), ease: "power2.out" }, at);
    tl.to(el, { y: 0, duration: F(settle), ease: "power2.inOut" }, at + F(bf));
    tl.fromTo(el, { rotationY: 10 }, { rotationY: 1, duration: F(bf + settle), ease: "power3.inOut" }, at + F(2));
    PC.event("pop", at, { el: el.id });
    var land = at + F(bf + settle);
    var h = PCM.hold(tl, el, land, o.until, { hold: o.hold, exit: o.exit });
    return { land: land, until: h.until };
  };
  PCM.confetti = function (tl, layer, at, o) {
    o = o || {};
    var rnd = PC.prng(o.seed || 7), colors = o.colors || ["#DC6532", "#289C5C", "#FFFAF7", "#C9623C", "#D67354"];
    var count = o.count === undefined ? 18 : o.count, x0 = o.x || 300, y0 = o.y || 880;
    for (var i = 0; i < count; i++) {
      var p = PC.el("div", "sb-piece", layer); p.id = (o.idPrefix || "sb-p") + i;
      p.style.background = colors[i % colors.length];
      var px = x0 - 120 + rnd() * 520, py = y0 - 160 + rnd() * 120, delay = rnd() * 0.25, fall = 260 + rnd() * 240, rot = rnd() * 720 - 360;
      p.style.left = px + "px"; p.style.top = py + "px";
      var t = at + delay;
      tl.fromTo(p, { opacity: 0, y: 0, rotation: 0 }, { opacity: 1, duration: F(3), ease: "none" }, t);
      tl.to(p, { y: fall, rotation: rot, duration: 1.2 + rnd() * 0.5, ease: "power1.in" }, t);
      tl.to(p, { opacity: 0, duration: 0.25, ease: "none" }, t + 1.1 + rnd() * 0.3);
    }
    PC.event("confetti", at, { el: layer.id });
  };

  // ---------------------------------------------------------------- the canvas: edges (E5) and ambient life (E7)
  function intersects(a, b) { return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y; }
  function clearOfZones(box, zones, pad) {
    pad = pad || 0;
    var grown = { x: box.x - pad, y: box.y - pad, w: box.w + 2 * pad, h: box.h + 2 * pad };
    for (var i = 0; i < zones.length; i++) if (intersects(grown, zones[i])) return false;
    return true;
  }
  var STAR = '<svg viewBox="0 0 24 24"><path d="M12 1.5c.6 5.4 2.6 8.4 10.5 10.5C14.6 14.1 12.6 17.1 12 22.5 11.4 17.1 9.4 14.1 1.5 12 9.4 9.9 11.4 6.9 12 1.5z"/></svg>';
  var CLOUD = '<svg viewBox="0 0 120 64"><path d="M30 56h62a18 18 0 0 0 2-35.9A26 26 0 0 0 46 14 22 22 0 0 0 10 36a20 20 0 0 0 20 20z"/></svg>';
  function colorVar(name, dflt) { return cssText("--c-" + name, dflt); }
  // a sine swing as one tween: value = center + amp * sin(2 pi (t / period + phase)); the ease returns the sine, so the
  // swing is already under way at 0 (no negative positions, no repeats) and the peak speed is 2 pi amp / period
  PCM.sway = function (tl, el, prop, center, amp, period, phase, seconds, at) {
    var fromV = {}, toV = {};
    fromV[prop] = center; toV[prop] = center + amp; toV.duration = seconds; toV.immediateRender = false;
    toV.ease = function (p) { return Math.sin(2 * Math.PI * (p * seconds / period + phase)); };
    tl.fromTo(el, fromV, toV, at || 0);
  };
  // PCM.canvas(tl, root, o): o = {seed, duration, edges, ambient, hold}. Builds #paper-edges (behind the content, partly
  // outside the frame, no text) and #paper-ambient (stars, dots, clouds) inside root, both seeded; registers their
  // drifts on tl. Returns {edges: [...], ambient: [...]} with the elements for the tests.
  PCM.canvas = function (tl, root, o) {
    o = o || {};
    var N = PCM.numbers();
    var rnd = PC.prng((o.seed || 1) * 7919 + 13);
    var seconds = o.duration || N.horizon;
    var zones = N.zones;
    var edgeLayer = PC.el("div", "pc-edge-layer", root); edgeLayer.id = "paper-edges"; edgeLayer.setAttribute("data-layout-ignore", "");
    var ambLayer = PC.el("div", "pc-ambient-layer", root); ambLayer.id = "paper-ambient"; ambLayer.setAttribute("data-layout-ignore", "");
    var accent = colorVar("accent", "#DC6532"), surface = colorVar("surface", "#FFFAF7"), glow = colorVar("glow-warm", "#ECD2BE"), ink = colorVar("ink-chip", "#1C110F");
    var dot = colorVar("dot", "#D2CABE"), script = colorVar("script", "#B04924"), mascot = colorVar("mascot", "#D67354"), edgeC = colorVar("card-edge", "#D7C5BA");
    var out = { edges: [], ambient: [] };
    // E5: the edge filler, 3 kinds per side, 30 to 70 percent outside, slower than the content, quieter than it
    var nEdges = o.edges === undefined ? 6 : o.edges;
    var kinds = ["card", "thumb", "chip", "shape", "star", "card"];
    // y bands beside the hook header (y 233 to 703) and the caption band, each shrunk by the sway (36 px) so an element
    // never swings into a zone; the inside part stays under 180 px, so an edge element never reaches a text zone that
    // starts at x 200 (the caption band, the end card's text)
    var SWAY = 36;
    var bands = [[36 + SWAY, 222 - SWAY], [716 + SWAY, 1140 - SWAY], [1424 + SWAY, 1884 - SWAY]];
    for (var i = 0; i < nEdges; i++) {
      var side = i % 2 === 0 ? "left" : "right";
      var kind = kinds[i % kinds.length];
      var band = bands[Math.floor(i / 2) % bands.length];
      var room = band[1] - band[0] - 8;
      var w = kind === "card" ? 200 + rnd() * 120 : kind === "thumb" ? 150 + rnd() * 60 : kind === "chip" ? 150 + rnd() * 60 : kind === "shape" ? 120 + rnd() * 80 : 70 + rnd() * 40;
      var h = kind === "card" ? w * (1.25 + rnd() * 0.3) : kind === "thumb" ? w * 1.35 : kind === "chip" ? 46 : w;
      if (h > room) { h = room; if (kind === "shape" || kind === "star") w = h; }
      var y = band[0] + rnd() * Math.max(1, band[1] - band[0] - h);
      // the outside share at rest stays 5 percent inside the 30 to 70 range, so the x sway (at most 5 percent of the
      // width) keeps it there; the inside part never exceeds 180 px
      var lo = N.edgeOutsideMin + 0.05, hi = N.edgeOutsideMax - 0.05;
      var outside = lo + rnd() * (hi - lo);
      outside = Math.min(hi, Math.max(outside, 1 - 180 / w));
      var x = side === "left" ? -w * outside : 1080 - w * (1 - outside);
      var box = { x: x, y: y, w: w, h: h };
      var tries = 0;
      while (!clearOfZones(box, zones, 10) && tries < 12) { box.y = band[0] + rnd() * Math.max(1, band[1] - band[0] - h); tries++; }
      var el = PC.el("div", "pc-edge pc-edge-" + kind, edgeLayer);
      el.id = "paper-edge-" + i;
      el.style.left = box.x + "px"; el.style.top = box.y + "px"; el.style.width = w + "px"; el.style.height = h + "px";
      var tilt = (rnd() * 10 - 5) + (side === "left" ? -3 : 3);
      if (kind === "card") { el.style.background = surface; el.style.borderRadius = "30px"; el.style.boxShadow = "0 0 0 2px " + edgeC + ", 0 24px 30px -8px rgba(133, 112, 92, 0.22)"; el.style.opacity = 0.78; }
      else if (kind === "thumb") { el.style.background = "linear-gradient(160deg, " + surface + ", " + glow + ")"; el.style.borderRadius = "24px"; el.style.boxShadow = "0 0 0 2px " + edgeC; el.style.opacity = 0.7; }
      else if (kind === "chip") { el.style.background = ink; el.style.borderRadius = "999px"; el.style.opacity = 0.55; }
      else if (kind === "shape") { el.style.background = glow; el.style.borderRadius = "50%"; el.style.opacity = 0.6; }
      else { el.innerHTML = STAR; el.querySelector("svg").style.fill = accent; el.style.opacity = 0.5; }
      gsap.set(el, { rotation: tilt, transformOrigin: "50% 50%", force3D: true });
      var ampX = Math.min(14 + rnd() * 10, w * 0.05), ampY = Math.min(22 + rnd() * 14, SWAY);
      PCM.sway(tl, el, "x", 0, ampX, PCM.periodFor(ampX, N.edgeMaxSpeed * 0.55), rnd(), seconds);
      PCM.sway(tl, el, "y", 0, ampY, PCM.periodFor(ampY, N.edgeMaxSpeed * 0.8), rnd(), seconds);
      PCM.sway(tl, el, "rotation", tilt, 1.5 + rnd() * 1.5, 9 + rnd() * 6, rnd(), seconds);
      out.edges.push({ el: el, kind: kind, box: box, side: side });
    }
    // E7: the ambient layer: stars, dots and small clouds in the margins, a slow drift and twinkle
    var nAmb = o.ambient === undefined ? 16 : o.ambient;
    var regions = [{ x: 24, y: 24, w: 1032, h: 150 }, { x: 24, y: 1440, w: 1032, h: 440 }, { x: 4, y: 200, w: 64, h: 1240 }, { x: 1012, y: 200, w: 64, h: 1240 }];
    var placed = [];
    for (var j = 0; j < nAmb; j++) {
      var akind = j % 5 === 0 ? "cloud" : (j % 2 === 0 ? "star" : "dot");
      var aw = akind === "cloud" ? 90 + rnd() * 50 : akind === "star" ? 26 + rnd() * 30 : 10 + rnd() * 10;
      var ah = akind === "cloud" ? aw * 0.53 : aw;
      var r = rnd() * 9, ri = r < 3 ? 0 : r < 7 ? 1 : r < 8 ? 2 : 3;
      if (regions[ri].w < aw + 4 || regions[ri].h < ah + 4) ri = r < 4.5 ? 0 : 1;
      var region = regions[ri];
      var abox = null;
      for (var k = 0; k < 20; k++) {
        var cand = { x: region.x + rnd() * Math.max(1, region.w - aw), y: region.y + rnd() * Math.max(1, region.h - ah), w: aw, h: ah };
        var ok = clearOfZones(cand, zones, 14);
        for (var q = 0; ok && q < placed.length; q++) if (intersects({ x: cand.x - 18, y: cand.y - 18, w: aw + 36, h: ah + 36 }, placed[q])) ok = false;
        if (ok) { abox = cand; break; }
      }
      if (!abox) continue;
      placed.push(abox);
      var ael = PC.el("div", "pc-ambient pc-ambient-" + akind, ambLayer);
      ael.id = "paper-ambient-" + j;
      ael.style.left = abox.x + "px"; ael.style.top = abox.y + "px"; ael.style.width = aw + "px"; ael.style.height = ah + "px";
      var lo, hi;
      if (akind === "cloud") { ael.innerHTML = CLOUD; ael.querySelector("svg").style.fill = surface; ael.style.filter = "drop-shadow(0 2px 0 " + edgeC + ")"; lo = 0.55; hi = 0.85; }
      else if (akind === "star") { ael.innerHTML = STAR; ael.querySelector("svg").style.fill = [accent, mascot, script][j % 3]; lo = 0.25; hi = 0.65; }
      else { ael.style.background = [accent, dot, glow, mascot][j % 4]; ael.style.borderRadius = "50%"; lo = 0.35; hi = 0.8; }
      gsap.set(ael, { opacity: lo + (hi - lo) * 0.5, transformOrigin: "50% 50%", force3D: true });
      var dAmp = 8 + rnd() * 10;
      PCM.sway(tl, ael, "y", 0, dAmp, PCM.periodFor(dAmp, N.ambientMaxSpeed * 0.7), rnd(), seconds);
      PCM.sway(tl, ael, "x", 0, dAmp * 0.6, PCM.periodFor(dAmp * 0.6, N.ambientMaxSpeed * 0.5), rnd(), seconds);
      PCM.sway(tl, ael, "opacity", (lo + hi) / 2, (hi - lo) / 2, 2 + rnd() * 2, rnd(), seconds);
      if (akind === "star") PCM.sway(tl, ael, "rotation", 0, 12, 6 + rnd() * 6, rnd(), seconds);
      out.ambient.push({ el: ael, kind: akind, box: abox });
    }
    PC.event("canvas_life", 0, { el: root.id, edges: out.edges.length, ambient: out.ambient.length });
    return out;
  };

  window.PCM = PCM;
})();
