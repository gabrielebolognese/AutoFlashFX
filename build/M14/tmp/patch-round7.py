"""Round 7: the canvas bands leave room for the sway (an edge element never swings into the hook header) and the outside
share stays between 30 and 70 percent through the sway; the test's grep patterns and the host check's place."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("motion-lib/assets/pc-motion.js", [
    ('''    // y bands beside the hook header (y 233 to 703) and the caption band; the inside part stays under 180 px, so an
    // edge element never reaches a text zone that starts at x 200 (the caption band, the end card's text)
    var bands = [[36, 222], [716, 1140], [1424, 1884]];''',
     '''    // y bands beside the hook header (y 233 to 703) and the caption band, each shrunk by the sway (36 px) so an element
    // never swings into a zone; the inside part stays under 180 px, so an edge element never reaches a text zone that
    // starts at x 200 (the caption band, the end card's text)
    var SWAY = 36;
    var bands = [[36 + SWAY, 222 - SWAY], [716 + SWAY, 1140 - SWAY], [1424 + SWAY, 1884 - SWAY]];'''),
    ('''      var outside = N.edgeOutsideMin + rnd() * (N.edgeOutsideMax - N.edgeOutsideMin);
      outside = Math.max(outside, 1 - 180 / w);
      var x = side === "left" ? -w * outside : 1080 - w * (1 - outside);''',
     '''      // the outside share at rest stays 5 percent inside the 30 to 70 range, so the x sway (at most 5 percent of the
      // width) keeps it there; the inside part never exceeds 180 px
      var lo = N.edgeOutsideMin + 0.05, hi = N.edgeOutsideMax - 0.05;
      var outside = lo + rnd() * (hi - lo);
      outside = Math.min(hi, Math.max(outside, 1 - 180 / w));
      var x = side === "left" ? -w * outside : 1080 - w * (1 - outside);'''),
    ('''      var ampX = 14 + rnd() * 10, ampY = 22 + rnd() * 16;
      PCM.sway(tl, el, "x", 0, ampX, PCM.periodFor(ampX, N.edgeMaxSpeed * 0.55), rnd(), seconds);
      PCM.sway(tl, el, "y", 0, ampY, PCM.periodFor(ampY, N.edgeMaxSpeed * 0.8), rnd(), seconds);''',
     '''      var ampX = Math.min(14 + rnd() * 10, w * 0.05), ampY = Math.min(22 + rnd() * 14, SWAY);
      PCM.sway(tl, el, "x", 0, ampX, PCM.periodFor(ampX, N.edgeMaxSpeed * 0.55), rnd(), seconds);
      PCM.sway(tl, el, "y", 0, ampY, PCM.periodFor(ampY, N.edgeMaxSpeed * 0.8), rnd(), seconds);'''),
])

patch("pipeline/tests/test-m14.sh", [
    ('''  assert_grep -- "--m-perspective: 1400" "$CSS" "tokens.css exposes the perspective"
  assert_grep -- "--m-hold-normal-drift: 4" "$CSS" "tokens.css exposes the hold speeds"
  assert_grep -- "--m-zone-caption: " "$CSS" "tokens.css exposes the text zones"''',
     '''  assert_grep "m-perspective: 1400;" "$CSS" "tokens.css exposes the perspective"
  assert_grep "m-hold-normal-drift: 4;" "$CSS" "tokens.css exposes the hold speeds"
  assert_grep "m-zone-caption: [0-9]" "$CSS" "tokens.css exposes the text zones"'''),
    ('''  # the compiler mounts the canvas seeded and driven
  python - "$REPO_DIR" <<'EOF' >/tmp/m14-host.txt
import os, sys, re
repo = sys.argv[1]
idx = open(os.path.join(repo, "golden", "test-idea", "project", "index.html"), encoding="utf-8").read() if os.path.isfile(os.path.join(repo, "golden", "test-idea", "project", "index.html")) else ""
m = re.search(r'<div id="paper-canvas"[^>]*>', idx)
host = m.group(0) if m else ""
print("host", "ok" if host and "data-no-timeline" not in host and '"seed"' in host and '"duration"' in host else host[:200] or "no index.html yet")
print("pcm", "ok" if os.path.isfile(os.path.join(repo, "golden", "test-idea", "project", "assets", "pc-motion.js")) else "missing")
EOF
  cat /tmp/m14-host.txt
  assert_grep "^host ok" /tmp/m14-host.txt "the golden project's canvas host is seeded, runs the reel's length and has a timeline"
  assert_grep "^pcm ok" /tmp/m14-host.txt "the golden project carries pc-motion.js"
fi''', '''fi'''),
    ('''    assert_file golden/test-idea/energy.json "golden/test-idea/energy.json written"
    assert_file golden/test-idea/contact-sheet.png "the contact sheet exists"
  fi
fi''', '''    assert_file golden/test-idea/energy.json "golden/test-idea/energy.json written"
    assert_file golden/test-idea/contact-sheet.png "the contact sheet exists"
    # the compiler mounts the canvas seeded and driven, and pc-motion.js travels with the project
    python - "$REPO_DIR" <<'EOF' >/tmp/m14-host.txt
import os, sys, re
repo = sys.argv[1]
idx = open(os.path.join(repo, "golden", "test-idea", "project", "index.html"), encoding="utf-8").read()
m = re.search(r'<div id="paper-canvas"[^>]*>', idx)
host = m.group(0) if m else ""
print("host", "ok" if host and "data-no-timeline" not in host and '"seed"' in host and '"duration"' in host else host[:200] or "no canvas host")
print("pcm", "ok" if os.path.isfile(os.path.join(repo, "golden", "test-idea", "project", "assets", "pc-motion.js")) else "missing")
EOF
    cat /tmp/m14-host.txt
    assert_grep "^host ok" /tmp/m14-host.txt "the golden project's canvas host is seeded, runs the reel's length and has a timeline"
    assert_grep "^pcm ok" /tmp/m14-host.txt "the golden project carries pc-motion.js"
  fi
fi'''),
])
print("round 7 done")
