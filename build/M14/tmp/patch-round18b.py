"""Round 18b: the documents for the room rule: DECISIONS.md 304, the M14 report, build/progress.md, CLAUDE.md."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


DECISION = '''304. **Also found by the M11 rerun: the hold fits the room.** The CTA's DM card drops in and lands with its bottom 2 px
    above the safe bottom (decision 302); E1's inertia (16 px, downward: the drop's direction) and the normal hold's
    drift (4 px per second) then carried its message to y 1449 by the end of the ask beat, below the safe bottom of
    1440. E1 offers the hold as a drift, a rotation or a creep, so near a safe edge the element turns and creeps
    instead of drifting: PCM.life reads the element's rest box (layout offsets up to #stage, which no tween changes),
    the room from it to the safe edges in the move's direction (the safe top and bottom, the side margins, the right
    rail in the lower half, as `--m-safe-*` in tokens.css from tokens.json zones) and fits the planned travel into it:
    the inertia plus the drift over the element's life, which is its `until` or `exit_at` when known and else the
    grammar's room_life_s (8 s, tokens.json motion.grammar.hold; the components do not know the host's duration). The
    drift slows first, then the inertia shrinks; the rotation and the creep keep the element alive (frame-match's
    static rule). A component may opt out with `room: false`. The DM card at the CTA's y therefore moves 2 px down and
    grows; at y 700 it drifts as before (test-m14 section 3 checks both). The scale creep still moves a wide card's
    edges a few px outward over a long hold; the review's samples watch for it, and M16's energy loop can tune the
    hold levels and the room per scene with the real lives.
'''

patch("DECISIONS.md", [
    ('''    card.
''' + "", '''    card.
''' + DECISION),
])

patch("build/M14/report.md", [
    ('''  elements to the next sample, and the "landed" sample sits after the combined animation (DECISIONS.md 303; test-m14
  section 3 checks it on the DM card).''',
     '''  elements to the next sample, and the "landed" sample sits after the combined animation (DECISIONS.md 303; test-m14
  section 3 checks it on the DM card).
- The hold drifted the CTA's DM card below the safe bottom (its message reached y 1449 by the end of the ask beat:
  the inertia and the normal drift, downward after a drop, had no room). The hold now fits the room: PCM.life reads
  the element's rest box and the safe edges (tokens.css `--m-safe-*`) and slows the drift, then shrinks the inertia,
  so that the planned travel over the element's life fits; the rotation and the creep keep it alive (DECISIONS.md
  304; test-m14 section 3 checks the DM card at the CTA's y and at y 700).'''),
    ('''  percent outside and move under 20 px per second; the review sees the DM card's texts arriving (scale 0.85 at the
  first frame), settled (scale 1 or more, the 28 px labels at 28 px or more) and leaving.''',
     '''  percent outside and move under 20 px per second; the review sees the DM card's texts arriving (scale 0.85 at the
  first frame), settled (scale 1 or more, the 28 px labels at 28 px or more) and leaving; the DM card at the CTA's y
  keeps its message above the safe bottom for 8 s while the same card at y 700 drifts on.'''),
    ('''  section 3 run again after the transients fix: 10 passed, the 7 before plus the 3 review checks (build/M14/test-m14-s3.log).''',
     '''  sections 1 and 3 run again after the transients and room fixes: 38 passed (the 32 before plus the safe-edge
  variables check, the 3 review checks and the 2 room checks; build/M14/test-m14-s13.log).'''),
])

patch("build/progress.md", [
    ('''  failed in 37 minutes (section 1: 25, section 2: 29, section 3: 7, section 4: 9, section 5: 1; section 3 has 10 checks since
  the transients fix, build/M14/test-m14-s3.log: 10 passed); the partial runs''',
     '''  failed in 37 minutes (section 1: 25, section 2: 29, section 3: 7, section 4: 9, section 5: 1; sections 1 and 3 have 26
  and 12 checks since the transients and room fixes, build/M14/test-m14-s13.log: 38 passed); the partial runs'''),
    ('''  scale read in 3D, arriving and leaving elements left to the next sample; common.py: the landed sample after the
  combined animation). DECISIONS.md 288 to 303. Report: build/M14/report.md.''',
     '''  scale read in 3D, arriving and leaving elements left to the next sample; common.py: the landed sample after the
  combined animation). The hold fits the room to the safe edges (PCM.room, tokens.css --m-safe-*). DECISIONS.md 288
  to 304. Report: build/M14/report.md.'''),
])

patch("CLAUDE.md", [
    ('''  the review reads the scale in 3D, does not judge an element while it arrives or leaves and samples "landed" after
  the combined animation: DECISIONS.md 303).''',
     '''  the review reads the scale in 3D, does not judge an element while it arrives or leaves and samples "landed" after
  the combined animation: DECISIONS.md 303), the hold's room (PCM.room: the inertia and the drift fit the room from
  the element's rest box to the safe edges, `--m-safe-*` in tokens.css, over its life or room_life_s 8 s: near an
  edge the element turns and creeps instead of drifting; DECISIONS.md 304).'''),
])
print("round 18b done")
