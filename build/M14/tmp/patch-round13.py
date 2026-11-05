"""Round 13: the fit window stops one frame after the candidate duration (the inertia frames after the landing were
biasing the fit toward a shorter move), and a caption chunk starts hidden through an immediate set (a zero-duration
tween at position 0 is not rendered when the timeline is seeked to exactly 0)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/motion/framematch.py", [
    ('''            err = 0.0
            for i in range(i0, min(len(values), i0 + d + 3)):
                v = values[i]''',
     '''            err = 0.0
            for i in range(i0, min(len(values), i0 + d + 2)):  # one frame past the candidate landing: the inertia starts there
                v = values[i]'''),
])

patch("motion-lib/compositions/caption-line.html", [
    ('''        tl.set(div, { opacity: 0 }, 0);       // nothing of the chunk shows before its first word
        tl.set(div, { opacity: 1 }, start);''',
     '''        gsap.set(div, { opacity: 0 });        // nothing of the chunk shows before its first word (set at once: a zero-duration tween at 0 is skipped by a seek to 0)
        tl.set(div, { opacity: 1 }, start);'''),
    ('''        tl.set(div, { opacity: 0, visibility: "hidden" }, end);
        tl.set(div, { visibility: "visible" }, 0);''',
     '''        tl.set(div, { opacity: 0, visibility: "hidden" }, end);'''),
])
print("round 13 done")
