"""Round 10: the strip correlation finds the reference move anywhere in the component's move frames (the combined
entrance of E2 adds a zoom before a chart's bars grow, so the biggest change is no longer where the strip's move is);
a growing bar starts at a hair, not at zero (a zero-height plane in a 3D context reads a few px tall); the chart's
depth keeps the title only."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/motion/strips.py", [
    ('''def correlate(ref_curve: list[float], cur_curve: list[float], frames: int, points: int = 12) -> tuple[float, int, int]:''',
     '''def correlate_sliding(ref_curve: list[float], cur_curve: list[float], frames: int, points: int = 12) -> tuple[float, int, int]:
    """The reference's move window against every window of `frames` frames in the component's curve (M14: the combined
    entrance of E2 puts a zoom before the move a strip shows, so the biggest change is not always the strip's move);
    the best Pearson r over the onsets and a 1-frame shift of the reference onset."""
    o_ref, e_ref = move_window(ref_curve)
    e_ref = min(e_ref, o_ref + max(3, frames) - 1)
    best = (-1.0, o_ref, 0)
    n = max(3, frames)
    for shift in (-1, 0, 1):
        r0 = max(0, o_ref + shift)
        seg = ref_curve[r0:e_ref + 1] + [0.0]
        if len(seg) < 3:
            continue
        ref_rs = resample(seg, points)
        for onset in range(0, max(1, len(cur_curve) - 2)):
            win = cur_curve[onset:onset + n]
            if len(win) < 3 or max(win) <= 0:
                continue
            r = pearson(ref_rs, resample(win + [0.0], points))
            if r > best[0]:
                best = (r, r0, onset)
    return best


def correlate(ref_curve: list[float], cur_curve: list[float], frames: int, points: int = 12) -> tuple[float, int, int]:'''),
])

patch("pipeline/lib/motion/framematch.py", [
    ('''        r, o_ref, o_cur = strips.correlate(ref, cur, move_frames)
        entry = {"strip": rel, "r": round(r, 3), "ref_onset": o_ref, "cur_onset": o_cur, "frames": move_frames}''',
     '''        r, o_ref, o_cur = strips.correlate(ref, cur, move_frames)
        r2, o_ref2, o_cur2 = strips.correlate_sliding(ref, cur, move_frames)
        if r2 > r:
            r, o_ref, o_cur = r2, o_ref2, o_cur2
        entry = {"strip": rel, "r": round(r, 3), "ref_onset": o_ref, "cur_onset": o_cur, "frames": move_frames}'''),
])

patch("motion-lib/assets/pc-motion.js", [
    ('''    fromV[prop] = 0; fromV.transformOrigin = o.origin || ((o.axis || "y") === "x" ? "0% 50%" : "50% 100%");''',
     '''    fromV[prop] = 0.001; fromV.transformOrigin = o.origin || ((o.axis || "y") === "x" ? "0% 50%" : "50% 100%");  // a hair, not zero: a flat plane in a 3D context reads a few px tall'''),
])

patch("motion-lib/compositions/chart-card.html", [
    ('''      PCM.depth(cc, [title, v.kind === "gauge" ? gauge : bars]);''', '''      PCM.depth(cc, [title]);  // the bars stay in the card's plane: a bar growing from nothing measures cleanly there'''),
])
print("round 10 done")
