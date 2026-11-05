p = "motion-lib/assets/pc-motion.js"
s = open(p, encoding="utf-8").read()
old_osc = s[s.index("  function oscillate(tl, el, prop, amp, period, phase, seconds, from0) {"):s.index("  // PCM.canvas(tl, root, o)")]
new_osc = '''  // a sine swing as one tween: value = center + amp * sin(2 pi (t / period + phase)); the ease returns the sine, so the
  // swing is already under way at 0 (no negative positions, no repeats) and the peak speed is 2 pi amp / period
  PCM.sway = function (tl, el, prop, center, amp, period, phase, seconds, at) {
    var fromV = {}, toV = {};
    fromV[prop] = center; toV[prop] = center + amp; toV.duration = seconds; toV.immediateRender = false;
    toV.ease = function (p) { return Math.sin(2 * Math.PI * (p * seconds / period + phase)); };
    tl.fromTo(el, fromV, toV, at || 0);
  };
'''
s = s.replace(old_osc, new_osc)
s = s.replace('''      var ampX = 14 + rnd() * 10, ampY = 22 + rnd() * 16;
      oscillate(tl, el, "x", ampX, PCM.periodFor(ampX, N.edgeMaxSpeed * 0.55), rnd(), seconds);
      oscillate(tl, el, "y", ampY, PCM.periodFor(ampY, N.edgeMaxSpeed * 0.8), rnd(), seconds);
      var rotAmp = 1.5 + rnd() * 1.5;
      tl.fromTo(el, { rotation: tilt - rotAmp }, { rotation: tilt + rotAmp, duration: 7 + rnd() * 5, ease: "sine.inOut", yoyo: true, repeat: Math.ceil(seconds / 7) * 2 + 2, immediateRender: false }, -rnd() * 6);''',
'''      var ampX = 14 + rnd() * 10, ampY = 22 + rnd() * 16;
      PCM.sway(tl, el, "x", 0, ampX, PCM.periodFor(ampX, N.edgeMaxSpeed * 0.55), rnd(), seconds);
      PCM.sway(tl, el, "y", 0, ampY, PCM.periodFor(ampY, N.edgeMaxSpeed * 0.8), rnd(), seconds);
      PCM.sway(tl, el, "rotation", tilt, 1.5 + rnd() * 1.5, 9 + rnd() * 6, rnd(), seconds);''')
s = s.replace('''      gsap.set(ael, { opacity: lo + (hi - lo) * 0.5, transformOrigin: "50% 50%", force3D: true });
      var dAmp = 8 + rnd() * 10;
      oscillate(tl, ael, "y", dAmp, PCM.periodFor(dAmp, N.ambientMaxSpeed * 0.7), rnd(), seconds);
      oscillate(tl, ael, "x", dAmp * 0.6, PCM.periodFor(dAmp * 0.6, N.ambientMaxSpeed * 0.5), rnd(), seconds);
      var tw = 2 + rnd() * 2;
      tl.fromTo(ael, { opacity: lo }, { opacity: hi, duration: tw / 2, ease: "sine.inOut", yoyo: true, repeat: Math.ceil(seconds / tw) * 2 + 2, immediateRender: false }, -rnd() * tw);
      if (akind === "star") tl.fromTo(ael, { rotation: -12 }, { rotation: 12, duration: 3 + rnd() * 3, ease: "sine.inOut", yoyo: true, repeat: Math.ceil(seconds / 3) * 2 + 2, immediateRender: false }, -rnd() * 3);''',
'''      gsap.set(ael, { opacity: lo + (hi - lo) * 0.5, transformOrigin: "50% 50%", force3D: true });
      var dAmp = 8 + rnd() * 10;
      PCM.sway(tl, ael, "y", 0, dAmp, PCM.periodFor(dAmp, N.ambientMaxSpeed * 0.7), rnd(), seconds);
      PCM.sway(tl, ael, "x", 0, dAmp * 0.6, PCM.periodFor(dAmp * 0.6, N.ambientMaxSpeed * 0.5), rnd(), seconds);
      PCM.sway(tl, ael, "opacity", (lo + hi) / 2, (hi - lo) / 2, 2 + rnd() * 2, rnd(), seconds);
      if (akind === "star") PCM.sway(tl, ael, "rotation", 0, 12, 6 + rnd() * 6, rnd(), seconds);''')
s = s.replace('''    var bands = [[40, 230], [720, 1150], [1420, 1880]];  // y bands that never cross the hook header or the caption band
    for (var i = 0; i < nEdges; i++) {
      var side = i % 2 === 0 ? "left" : "right";
      var kind = kinds[i % kinds.length];
      var w = kind === "card" ? 200 + rnd() * 120 : kind === "thumb" ? 150 + rnd() * 60 : kind === "chip" ? 150 + rnd() * 60 : kind === "shape" ? 120 + rnd() * 80 : 70 + rnd() * 40;
      var h = kind === "card" ? w * (1.25 + rnd() * 0.3) : kind === "thumb" ? w * 1.35 : kind === "chip" ? 46 : w;
      var band = bands[Math.floor(i / 2) % bands.length];
      var y = band[0] + rnd() * Math.max(1, band[1] - band[0] - h);
      var outside = N.edgeOutsideMin + rnd() * (N.edgeOutsideMax - N.edgeOutsideMin);
      var x = side === "left" ? -w * outside : 1080 - w * (1 - outside);
      var box = { x: x, y: y, w: w, h: h };
      var tries = 0;
      while (!clearOfZones(box, zones, 10) && tries < 12) { box.y = band[0] + rnd() * Math.max(1, band[1] - band[0] - h); tries++; }''',
'''    // y bands beside the hook header (y 233 to 703) and the caption band; the inside part stays under 180 px, so an
    // edge element never reaches a text zone that starts at x 200 (the caption band, the end card's text)
    var bands = [[36, 222], [716, 1140], [1424, 1884]];
    for (var i = 0; i < nEdges; i++) {
      var side = i % 2 === 0 ? "left" : "right";
      var kind = kinds[i % kinds.length];
      var band = bands[Math.floor(i / 2) % bands.length];
      var room = band[1] - band[0] - 8;
      var w = kind === "card" ? 200 + rnd() * 120 : kind === "thumb" ? 150 + rnd() * 60 : kind === "chip" ? 150 + rnd() * 60 : kind === "shape" ? 120 + rnd() * 80 : 70 + rnd() * 40;
      var h = kind === "card" ? w * (1.25 + rnd() * 0.3) : kind === "thumb" ? w * 1.35 : kind === "chip" ? 46 : w;
      if (h > room) { h = room; if (kind === "shape" || kind === "star") w = h; }
      var y = band[0] + rnd() * Math.max(1, band[1] - band[0] - h);
      var outside = N.edgeOutsideMin + rnd() * (N.edgeOutsideMax - N.edgeOutsideMin);
      outside = Math.max(outside, 1 - 180 / w);
      var x = side === "left" ? -w * outside : 1080 - w * (1 - outside);
      var box = { x: x, y: y, w: w, h: h };
      var tries = 0;
      while (!clearOfZones(box, zones, 10) && tries < 12) { box.y = band[0] + rnd() * Math.max(1, band[1] - band[0] - h); tries++; }''')
s = s.replace('''      var r = rnd() * 9, ri = r < 3 ? 0 : r < 7 ? 1 : r < 8 ? 2 : 3;
      var region = regions[ri];
      var akind = j % 5 === 0 ? "cloud" : (j % 2 === 0 ? "star" : "dot");
      var aw = akind === "cloud" ? 90 + rnd() * 50 : akind === "star" ? 26 + rnd() * 30 : 10 + rnd() * 10;
      var ah = akind === "cloud" ? aw * 0.53 : aw;''',
'''      var akind = j % 5 === 0 ? "cloud" : (j % 2 === 0 ? "star" : "dot");
      var aw = akind === "cloud" ? 90 + rnd() * 50 : akind === "star" ? 26 + rnd() * 30 : 10 + rnd() * 10;
      var ah = akind === "cloud" ? aw * 0.53 : aw;
      var r = rnd() * 9, ri = r < 3 ? 0 : r < 7 ? 1 : r < 8 ? 2 : 3;
      if (regions[ri].w < aw + 4 || regions[ri].h < ah + 4) ri = r < 4.5 ? 0 : 1;
      var region = regions[ri];''')
s = s.replace('''    var weights = [3, 4, 1, 1];
''', '')
s = s.replace('''      gsap.set(prop, { transformOrigin: "20% 80%", svgOrigin: null });''', '''      gsap.set(prop, { transformOrigin: "20% 80%" });''')
s = s.replace('''      tl.fromTo(el, { x: sdx, opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      tl.to(el, { x: -sign(sdx) * sover, duration: F(s1), ease: "power2.out" }, at);
      tl.to(el, { x: 0, duration: F(sf - s1), ease: "power1.inOut" }, at + F(s1));''',
'''      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: F(3), ease: "none" }, at);
      tl.fromTo(el, { x: sdx }, { x: -sign(sdx) * sover, duration: F(s1), ease: "power2.out" }, at);
      tl.to(el, { x: 0, duration: F(sf - s1), ease: "power1.inOut" }, at + F(s1));''')
s = s.replace('''    var repsY = Math.max(1, Math.ceil(seconds / py));
    var wrap = o.yTarget || el;
    tl.fromTo(wrap, { y: -dy }, { y: dy, duration: py / 2, ease: "sine.inOut", yoyo: true, repeat: repsY * 2, immediateRender: false }, at);
    return at + seconds;''',
'''    if (dy > 0 && o.yTarget) {
      var repsY = Math.max(1, Math.ceil(seconds / py));
      tl.fromTo(o.yTarget, { y: -dy }, { y: dy, duration: py / 2, ease: "sine.inOut", yoyo: true, repeat: repsY * 2, immediateRender: false }, at);
    }
    return at + seconds;''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
assert "oscillate(" not in s, "oscillate still used"
assert "weights" not in s
print("ok", len(s))
