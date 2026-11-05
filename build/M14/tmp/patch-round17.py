"""Round 17: the review and the grammar's transients. The M11 fake test's rerun flagged 28 px texts as 23 px: at a sample
time inside an element's combined entrance (E2: scale 0.85 for the first frames) the review multiplied the font size by
a 2D reading of the transform (hypot(a, b) is cos 12 degrees under the parallax rotation). Now the grammar marks every
element's main animation window (data-pcm-main) and its exit window (data-pcm-exit) in local seconds, the review reads
the scale as the length of the 3D basis vectors and does not judge an element while it arrives or leaves, and the
"landed" sample sits after the combined animation and its lagging rotation (start plus 18 plus 3 frames plus 100 ms)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


# 1. the grammar marks the transients ................................................................................
patch("motion-lib/assets/pc-motion.js", [
    ('''    // 3. the inertia and the hold ............................................................................
    var until = o.until !== undefined && o.until !== null ? o.until : (hasExit ? exitAt : at + N.horizon);''',
     '''    // the main animation's window, for the review (S12 does not judge an element while it arrives: the zoom and the
    // rotation are transients by design, E2)
    if (kind !== "none") PCM.mark(el, "data-pcm-main", at, Math.max(land, scaleLand, rotLand));
    // 3. the inertia and the hold ............................................................................
    var until = o.until !== undefined && o.until !== null ? o.until : (hasExit ? exitAt : at + N.horizon);'''),
    ('''    if (type === "cut") { tl.set(el, { opacity: 0 }, at); PC.event("exit", at, { el: name, type: type }); return at; }
    if (type === "fade") {  // a plain fade (the caption chunk replace: 2 frames out)
      var df = o.frames || 2;
      tl.to(el, { opacity: 0, duration: F(df), ease: "none" }, at);
      PC.event("exit", at, { el: name, type: type }); return at + F(df);
    }
    if (type === "fall") {
      var ff = o.frames || 10;
      tl.to(el, { y: from.y + (o.distance || 1700), rotation: o.tilt === undefined ? 2 : o.tilt, duration: F(ff), ease: "power2.in" }, at);
      PC.event("exit", at, { el: name, type: type }); return at + F(ff);
    }
    if (type === "push") {
      var pf = o.frames || 6;
      tl.to(el, { x: from.x - (o.distance || 1300), duration: F(pf), ease: "power2.in" }, at);
      PC.event("exit", at, { el: name, type: type }); return at + F(pf);
    }
    var bf = o.frames || 4;  // fade-blur
    tl.to(el, { opacity: 0, filter: "blur(8px)", duration: F(bf), ease: "power2.in" }, at);
    PC.event("exit", at, { el: name, type: "fade-blur" }); return at + F(bf);
  };''',
     '''    if (type === "cut") { tl.set(el, { opacity: 0 }, at); PC.event("exit", at, { el: name, type: type }); return at; }
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
  };'''),
])

# 2. the review reads the 3D scale and the transients .................................................................
patch("pipeline/lib/review/mechanical.py", [
    ('''  const scaleOf = (el) => {
    let s = 1, node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      const cs = getComputedStyle(node);
      try { const m = new DOMMatrixReadOnly(cs.transform); const k = Math.hypot(m.a, m.b); if (k > 0) s *= k; } catch (e) {}
      node = node.parentElement;
    }
    return s;
  };''',
     '''  const scaleOf = (el) => {
    // the length of the transformed basis vectors (the 3D matrix's first two columns): a parallax rotation (E2) does
    // not read as a smaller scale the way hypot(a, b) did (cos 12 degrees)
    let s = 1, node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      const cs = getComputedStyle(node);
      try { const m = new DOMMatrixReadOnly(cs.transform); const k = Math.max(Math.hypot(m.m11, m.m12, m.m13), Math.hypot(m.m21, m.m22, m.m23)); if (k > 0) s *= k; } catch (e) {}
      node = node.parentElement;
    }
    return s;
  };
  // the grammar marks every element's main animation (data-pcm-main) and exit (data-pcm-exit) windows in local
  // seconds (pc-motion.js PCM.mark): an element inside one of them, or inside an ancestor's, is arriving or leaving
  const transientAt = (el, t) => {
    let node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      for (const name of ["data-pcm-main", "data-pcm-exit"]) {
        const v = node.getAttribute(name);
        if (!v) continue;
        const parts = v.split(",");
        const a = parseFloat(parts[0]), b = parseFloat(parts[1]);
        if (isFinite(a) && isFinite(b) && t >= a - 1e-4 && t < b - 1e-4) return name === "data-pcm-main" ? "main" : "exit";
      }
      node = node.parentElement;
    }
    return "";
  };'''),
    ('''        images.push({ id: el.id || "", cls: String(el.className || ""), src: el.getAttribute("src") || "", x: r.left, y: r.top, w: r.width, h: r.height,
                      opacity: effOpacity(el), nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, bg: bgOf(el.parentElement), idx: parseInt(el.getAttribute("data-rv-idx") || "-1", 10) });''',
     '''        images.push({ id: el.id || "", cls: String(el.className || ""), src: el.getAttribute("src") || "", x: r.left, y: r.top, w: r.width, h: r.height,
                      opacity: effOpacity(el), nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, bg: bgOf(el.parentElement), idx: parseInt(el.getAttribute("data-rv-idx") || "-1", 10),
                      transient: transientAt(el, t) });'''),
    ('''                   opacity: effOpacity(el), font: cs.fontFamily, size: parseFloat(cs.fontSize), weight: cs.fontWeight, color: cs.color, scale: scaleOf(el),
                   bg: bgOf(el), ignore: el.hasAttribute("data-layout-ignore") || !!el.closest("[data-layout-ignore]") });''',
     '''                   opacity: effOpacity(el), font: cs.fontFamily, size: parseFloat(cs.fontSize), weight: cs.fontWeight, color: cs.color, scale: scaleOf(el),
                   bg: bgOf(el), ignore: el.hasAttribute("data-layout-ignore") || !!el.closest("[data-layout-ignore]"), transient: transientAt(el, t) });'''),
    ('''    counts = {"hosts": 0, "texts": 0, "images": 0, "times": len(check_ms), "screenshots": 0}''',
     '''    counts = {"hosts": 0, "texts": 0, "images": 0, "times": len(check_ms), "screenshots": 0, "transient": 0}'''),
    ('''        for tx in texts:
            counts["texts"] += 1
            x0, y0, x1, y1 = tx["x"], tx["y"], tx["x"] + tx["w"], tx["y"] + tx["h"]''',
     '''        for tx in texts:
            counts["texts"] += 1
            if tx.get("transient"):
                # arriving or leaving (E1's main animation with E2's zoom and rotation, or the exit): a transient by
                # design, judged at the next sample of its life
                counts["transient"] += 1
                continue
            x0, y0, x1, y1 = tx["x"], tx["y"], tx["x"] + tx["w"], tx["y"] + tx["h"]'''),
    ('''        # overlaps between different elements
        vis = [t for t in texts if not t.get("ignore")]''',
     '''        # overlaps between different elements (the arriving and leaving ones left out)
        vis = [t for t in texts if not t.get("ignore") and not t.get("transient")]'''),
    ('''        for im in images:
            counts["images"] += 1
            x0, y0, x1, y1 = im["x"], im["y"], im["x"] + im["w"], im["y"] + im["h"]''',
     '''        for im in images:
            counts["images"] += 1
            if im.get("transient"):
                counts["transient"] += 1
                continue
            x0, y0, x1, y1 = im["x"], im["y"], im["x"] + im["w"], im["y"] + im["h"]'''),
    ('''    for T in check_ms:
        for im in per_time[T]["images"]:
            if im["src"].startswith("assets/brand/"):
                logo_rows.append((T, im))''',
     '''    for T in check_ms:
        for im in per_time[T]["images"]:
            if im["src"].startswith("assets/brand/") and not im.get("transient"):
                logo_rows.append((T, im))'''),
])

# 3. the landed sample after the combined animation ....................................................................
patch("pipeline/lib/review/common.py", [
    ('''    """{ms: [labels]}: every beat (the scene start plus settle_ms, or its middle when short, and its middle), every
    emphasis hit (plus the box's fade), every instance's landing, the CTA's built state."""
    settle = int(ctx.c("review.settle_ms", 600))
    em_lead = int(ctx.c("review.emphasis_settle_ms", 150))
    times: dict = {}''',
     '''    """{ms: [labels]}: every beat (the scene start plus settle_ms, or its middle when short, and its middle), every
    emphasis hit (plus the box's fade), every instance's landing (after the combined main animation and its lagging
    rotation, E2: the grammar's main frames plus the lag, from tokens.json motion.grammar), the CTA's built state."""
    settle = int(ctx.c("review.settle_ms", 600))
    em_lead = int(ctx.c("review.emphasis_settle_ms", 150))
    grammar = ((ctx.toks.get("motion") or {}).get("grammar") or {}) if isinstance(getattr(ctx, "toks", None), dict) else {}
    main_frames = int((grammar.get("main") or {}).get("frames", 18)) + int((grammar.get("rotation") or {}).get("lag_frames", 3))
    main_ms = int(round(main_frames * 1000.0 / 30.0))
    times: dict = {}'''),
    ('''        for c in s.get("components", []):
            land = c.get("land_ms")
            if land is not None and int(land) + 100 < b:
                add(int(land) + 100, f"{c['id']} landed")''',
     '''        for c in s.get("components", []):
            land = c.get("land_ms")
            if land is None:
                continue
            last = min(b, int(c.get("end_ms", b)))
            settled = max(int(land), int(c.get("start_ms", land)) + main_ms) + 100
            for t in (settled, int(land) + 100):
                if t < last:
                    add(t, f"{c['id']} landed")
                    break'''),
])
print("round 17 done")
