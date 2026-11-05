"""Round 18: the hold fits the room. The M11 rerun's next finding: the CTA's DM card drops in, lands with its bottom 2 px
above the safe bottom, and E1's inertia (16 px) plus the normal hold (4 px per second, downward: the drop's direction)
carried its message to y 1449 by the end of the scene. E1 offers the hold as a drift, a rotation OR a creep: near a safe
edge the element turns and creeps instead of drifting. PCM.life measures the element's rest box (layout offsets, no
transforms), the room from it to the safe edges in the move's direction (safe top and bottom, the side margins, the
right rail in the lower half, from tokens.css --m-safe-*), and fits the planned travel (the inertia plus the drift over
the element's life: its until, its exit_at, else room_life_s 8 s) into that room: the drift slows, then the inertia
shrinks. tokens.css carries the safe edges; test-m14 section 3 checks the DM card at the CTA's y and at y 700."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


# 1. the tokens: the safe edges and the room life as --m-* variables ....................................................
patch("pipeline/lib/tokens.py", [
    ('''             "drift_range_px_s": [2, 8], "rotate_range_deg_s": [0.2, 0.6], "scale_range_pct_s": [0.2, 0.5]},''',
     '''             "drift_range_px_s": [2, 8], "rotate_range_deg_s": [0.2, 0.6], "scale_range_pct_s": [0.2, 0.5],
             "room_life_s": 8,
             "room_note": "the inertia and the drift fit the room between the element's rest box and the safe edges (zones: safe_top, safe_bottom, margin_x, the right rail in the lower half) in their direction over the element's life (its until or exit_at, else room_life_s): near an edge the hold turns and creeps instead of drifting (E1: a drift, a rotation or a creep)"},'''),
    ('''            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 30)};",
        ]''',
     '''            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 30)};",
            f"  --m-room-life-s: {h.get('room_life_s', 8)};",
        ]
        zn = tokens.get("zones") or {}
        rail = zn.get("right_rail") or {}
        lines += [  # the safe edges, for the hold's room (pc-motion.js PCM.room)
            f"  --m-safe-top: {zn.get('safe_top', 230):g};",
            f"  --m-safe-bottom: {zn.get('safe_bottom', 1440):g};",
            f"  --m-margin-x: {zn.get('margin_x', 60):g};",
            f"  --m-rail-x: {1080 - float(rail.get('width', 230)):g};",
            f"  --m-rail-from-y: {float(rail.get('from_y', 960)):g};",
        ]'''),
])

# 2. the grammar: the rest box, the room, the fit ......................................................................
patch("motion-lib/assets/pc-motion.js", [
    ('''      depthStep: cssNum("--m-depth-step", 24),''',
     '''      depthStep: cssNum("--m-depth-step", 24),
      roomLife: cssNum("--m-room-life-s", 8),
      safeTop: cssNum("--m-safe-top", 230),
      safeBottom: cssNum("--m-safe-bottom", 1440),
      marginX: cssNum("--m-margin-x", 60),
      railX: cssNum("--m-rail-x", 850),
      railFromY: cssNum("--m-rail-from-y", 960),'''),
    ('''  // PCM.life(tl, el, o): the whole life of one element on the timeline tl.''',
     '''  // PCM.restBox(el): the element's layout box in canvas px (offsets up to #stage: transforms do not count, so the box
  // is where the element rests, whatever its tweens have rendered). null when the element has no layout.
  PCM.restBox = function (el) {
    if (!el || el.offsetWidth === undefined) return null;
    var w = el.offsetWidth, h = el.offsetHeight;
    if (!(w > 0) || !(h > 0)) return null;
    var x = 0, y = 0, n = el, guard = 0;
    while (n && n !== document.body && n.id !== "stage" && guard++ < 64) { x += n.offsetLeft || 0; y += n.offsetTop || 0; n = n.offsetParent; }
    return { x: x, y: y, w: w, h: h };
  };

  // PCM.room(box, dir): the px the box can travel along the unit direction dir before a safe edge (the safe top and
  // bottom, the side margins, the right rail in the lower half: tokens.css --m-safe-*). Infinity when unknown; 0 when
  // the box already sits past the edge.
  PCM.room = function (box, dir) {
    if (!box || !dir) return Infinity;
    var N = PCM.numbers(), W = 1080;
    var right = (box.y + box.h > N.railFromY) ? Math.min(W - N.marginX, N.railX) : W - N.marginX;
    var rooms = [];
    if (dir.y < 0) rooms.push((box.y - N.safeTop) / -dir.y);
    if (dir.y > 0) rooms.push((N.safeBottom - (box.y + box.h)) / dir.y);
    if (dir.x < 0) rooms.push((box.x - N.marginX) / -dir.x);
    if (dir.x > 0) rooms.push((right - (box.x + box.w)) / dir.x);
    if (!rooms.length) return Infinity;
    return Math.max(0, Math.min.apply(null, rooms));
  };

  // PCM.life(tl, el, o): the whole life of one element on the timeline tl.'''),
    ('''  //   until       when the hold ends (default: the exit, else at + horizon)''',
     '''  //   until       when the hold ends (default: the exit, else at + horizon)
  //   room        false: the inertia and the drift ignore the safe edges (default: they fit the room, PCM.room)'''),
    ('''    var from = o.from || {};
    var fx = from.x || 0, fy = from.y || 0, fs = from.scale || 1;
    var end = { x: fx, y: fy };
    var T = until - land;
    var total = A + drift * T;''',
     '''    var from = o.from || {};
    var fx = from.x || 0, fy = from.y || 0, fs = from.scale || 1;
    var end = { x: fx, y: fy };
    var T = until - land;
    // the room (E1's "or": near a safe edge the hold turns and creeps instead of drifting): the inertia and the drift
    // in dir fit between the element's rest box and the safe edges over its life (until, exit_at, else room_life_s)
    if (o.room !== false && (A > 0 || drift > 0)) {
      var exitKnown = exitAt !== undefined && exitAt !== null && exitAt >= 0;
      var lifeEnd = (o.until !== undefined && o.until !== null) ? o.until : (exitKnown ? exitAt : at + N.roomLife);
      var Tlife = Math.max(F(1), lifeEnd - land);
      var room = PCM.room(PCM.restBox(el), dir);
      if (room < A + drift * Tlife) {
        if (room > A) drift = (room - A) / Tlife;
        else { A = Math.max(0, room); drift = 0; }
      }
    }
    var total = A + drift * T;'''),
])

# 3. the test ...........................................................................................................
patch("pipeline/tests/test-m14.sh", [
    ('''  assert_grep "m-zone-caption: [0-9]" "$CSS" "tokens.css exposes the text zones"''',
     '''  assert_grep "m-zone-caption: [0-9]" "$CSS" "tokens.css exposes the text zones"
  assert_grep "m-safe-bottom: 1440;" "$CSS" "tokens.css exposes the safe edges for the hold's room"'''),
    ('''    print("review-leaving", "ok" if leaving else "no")
    print("counts", counts)''',
     '''    print("review-leaving", "ok" if leaving else "no")
    # the room rule: the DM card at the CTA's y (its bottom 2 px above the safe bottom) keeps its message above the
    # safe bottom for 8 s (the drift fits the room), while the same card at y 700 drifts on
    h.open(dm, {"enter_at": 0.0, "y": 1266, "hold": "normal"})
    rv2 = h.page.evaluate(mechanical.REVIEW_JS, {"id": "dm-card", "times": [1.0, 4.0, 8.0]})
    bottoms = [max([t["y"] + t["h"] for t in row["texts"] if t["opacity"] >= 0.5] or [0]) for row in rv2["rows"]]
    h.open(dm, {"enter_at": 0.0, "y": 700, "hold": "normal"})
    mv = h.page.evaluate(harness.MEASURE_JS, {"id": "dm-card", "times": [1.0, 8.0], "selectors": ["#dm"]})
    ty = [r["#dm"]["ty"] for r in mv["rows"] if r.get("#dm")]
    print("room-rows", [round(b, 1) for b in bottoms], [round(v, 1) for v in ty])
    print("room-hold", "ok" if bottoms and 1380 <= max(bottoms) <= 1444 else "no")
    print("room-free", "ok" if len(ty) == 2 and ty[1] - ty[0] >= 20 else "no")
    print("counts", counts)'''),
    ('''  assert_grep "^review-leaving ok" /tmp/m14-i3.txt "the review sees the texts leaving during the exit (data-pcm-exit)"''',
     '''  assert_grep "^review-leaving ok" /tmp/m14-i3.txt "the review sees the texts leaving during the exit (data-pcm-exit)"
  assert_grep "^room-hold ok" /tmp/m14-i3.txt "the hold fits the room: the DM card at the CTA's y keeps its message above the safe bottom for 8 s"
  assert_grep "^room-free ok" /tmp/m14-i3.txt "the same card with room below drifts on (20 px or more between 1 and 8 s)"'''),
])
print("round 18 done")
