"""Round 17c: the documents for the transients fix: DECISIONS.md 303, the M14 report, build/progress.md, CLAUDE.md."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


DECISION = '''303. **Also found by the M11 rerun: the review judged elements mid-entrance.** With E2 every entering element starts
    at scale 0.85 (0.92 small, 1.15 close) and rotated 12 degrees, and the review's font rule multiplied a text's font
    size by a 2D reading of its transform (hypot(a, b), which is cos 12 degrees under a rotateY), so a sample inside the
    first frames of a DM card read its 28 px labels as 23 px. Three changes. The grammar marks every element's main
    animation window on the element itself (`data-pcm-main="from,to"` in local seconds, from the start to the end of
    the zoom and the lagging rotation: 21 frames) and its exit window (`data-pcm-exit`), both set once when the
    timeline is built (PCM.mark). The review reads the scale as the length of the transformed basis vectors (the 3D
    matrix's first two columns: a rotation is not a scale) and does not judge a text or an image while it, or one of
    its ancestors, is inside such a window: arriving and leaving elements are transients by design (E1 phases 1 and 4),
    judged at the next sample of their life; mechanical.json counts them (counts.transient). The "landed" sample time
    of decision 245 moves to after the combined animation (the component's start plus the grammar's main frames plus
    the rotation lag plus 100 ms, or its landing plus 100 ms when its life is shorter), so the zone and overlap checks
    read the element at rest rather than at 0.98 scale and 5 degrees. Once landed the grammar only grows an element
    (the inertia's scale 0.04 and the hold's creep go up), so a text never reads smaller than its designed size after
    its entrance: the 24 px floor stays a rule about the design. test-m14 section 3 checks the three states on the DM
    card.
'''

patch("DECISIONS.md", [
    ('''    same time: the image box never leaves the window, so the review's off-canvas rule stays quiet.
''', '''    same time: the image box never leaves the window, so the review's off-canvas rule stays quiet.
''' + DECISION),
])

patch("build/M14/report.md", [
    ('''- The same acceptance left the CTA's DM card (y 1305) ending below the safe bottom once the caption band's exception
  was gone: the director's default, the golden plan, the fixtures and the frozen run now place it at y 1266 with the
  lockup at 1146, and the validator's CTA exemption follows the band exception (DECISIONS.md 302). The window card's
  screenshot scrolls by its object-position (the image box stays inside the window; the review's off-canvas rule had
  flagged the transformed image).''',
     '''- The same acceptance left the CTA's DM card (y 1305) ending below the safe bottom once the caption band's exception
  was gone: the director's default, the golden plan, the fixtures and the frozen run now place it at y 1266 with the
  lockup at 1146, and the validator's CTA exemption follows the band exception (DECISIONS.md 302). The window card's
  screenshot scrolls by its object-position (the image box stays inside the window; the review's off-canvas rule had
  flagged the transformed image).
- The review judged elements mid-entrance: a sample inside a DM card's first frames read its 28 px labels as 23 px
  (E2's scale 0.85 times a 2D reading of the rotated transform). The grammar now marks every element's main animation
  and exit windows (data-pcm-main, data-pcm-exit), the review reads the scale in 3D and leaves arriving and leaving
  elements to the next sample, and the "landed" sample sits after the combined animation (DECISIONS.md 303; test-m14
  section 3 checks it on the DM card).'''),
    ('''  M11 (mechanical.py). Their fake-only tests were run again (below).''',
     '''  M11 (mechanical.py: the 3D scale, the transients, and common.py's landed sample time). Their fake-only tests were
  run again (below).'''),
    ('''- Section 3: icon-3d draws with WebGL (data-webgl 1, 16 percent of its area) and with the fallback (data-webgl 0,
  12 layers, turning); the layers for three seeds stay out of the text zones over 40 s, hold no text, sit 30 to 70
  percent outside and move under 20 px per second.''',
     '''- Section 3: icon-3d draws with WebGL (data-webgl 1, 16 percent of its area) and with the fallback (data-webgl 0,
  12 layers, turning); the layers for three seeds stay out of the text zones over 40 s, hold no text, sit 30 to 70
  percent outside and move under 20 px per second; the review sees the DM card's texts arriving (scale 0.85 at the
  first frame), settled (scale 1 or more, the 28 px labels at 28 px or more) and leaving.'''),
    ('''- The full run: 71 passed, 0 failed (section 1: 25, section 2: 24, section 3: 10, section 4: 11, section 5: 1).''',
     '''- The full run: 71 passed, 0 failed (section 1: 25, section 2: 24, section 3: 10, section 4: 11, section 5: 1);
  section 3 run again after the transients fix: 13 passed (build/M14/test-m14-s3.log).'''),
])

patch("build/progress.md", [
    ('''  M9 (test-m9's sandbox, harness.py's tag and 3D-aware measures, golden.py, gallery.py, catalog.py), M10 (project.py,
  visual/common.py, plan_validate.py, plan9.py, events.py, the frozen index.html canvas hosts), M11 (mechanical.py).
  DECISIONS.md 288 to 300. Report: build/M14/report.md.''',
     '''  M9 (test-m9's sandbox, harness.py's tag and 3D-aware measures, golden.py, gallery.py, catalog.py), M10 (project.py,
  visual/common.py, plan_validate.py, plan9.py, events.py, the frozen index.html canvas hosts), M11 (mechanical.py: the
  scale read in 3D, arriving and leaving elements left to the next sample; common.py: the landed sample after the
  combined animation). DECISIONS.md 288 to 303. Report: build/M14/report.md.'''),
])

patch("CLAUDE.md", [
    ('''  frame-match's life checks (never static for 0.5 s, the inertia 2 to 4 s) and per-component energy (catalog.json
  `energy`, the gallery's energy line), golden/test-idea/energy.json and build/M14/golden-energy-before.json.''',
     '''  frame-match's life checks (never static for 0.5 s, the inertia 2 to 4 s) and per-component energy (catalog.json
  `energy`, the gallery's energy line), golden/test-idea/energy.json and build/M14/golden-energy-before.json, the
  review's reading of the grammar's transients (PCM.mark sets `data-pcm-main` and `data-pcm-exit` on every element,
  the review reads the scale in 3D, does not judge an element while it arrives or leaves and samples "landed" after
  the combined animation: DECISIONS.md 303).'''),
])
print("round 17c done")
