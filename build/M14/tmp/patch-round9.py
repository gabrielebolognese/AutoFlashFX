"""Round 9: the fits read their end value at the expected landing frame itself (the inertia starts there, so the value is
the landing's), and a caption chunk is hidden until its start (an empty visible container counted as still)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/motion/framematch.py", [
    ('''def local_end(values: list[float | None], i0: int, frames: float) -> float | None:
    """The value just after the move's expected end (the element keeps moving afterwards: the inertia and the hold)."""
    j = min(len(values) - 1, i0 + int(round(frames)) + 2)
    while j > i0 and values[j] is None:
        j -= 1
    return values[j] if j < len(values) else None''',
     '''def local_end(values: list[float | None], i0: int, frames: float, after: int = 0) -> float | None:
    """The value at the move's expected end (plus `after` frames): the element keeps moving afterwards (its inertia
    and hold start exactly at the landing), so the last measured frame would read the move too long."""
    j = min(len(values) - 1, i0 + int(round(frames)) + after)
    while j > i0 and values[j] is None:
        j -= 1
    return values[j] if j < len(values) else None'''),
    ('''    start = values[i0] if i0 < len(values) else None
    end = local_end(values, i0, expected + span)
    if start is None or end is None:''',
     '''    start = values[i0] if i0 < len(values) else None
    end = local_end(values, i0, expected)
    if start is None or end is None:'''),
    ('''            final = local_end(vals, i0, check["frames"])
            start_v = vals[i0] if i0 < len(vals) else None''',
     '''            final = local_end(vals, i0, check["frames"], 1)
            start_v = vals[i0] if i0 < len(vals) else None'''),
    ('''        final = local_end(cys, i0, int(check["frames"]) + int(check["settle_frames"]))
        window = cys[i0:i0 + int(check["frames"]) + int(check["settle_frames"]) + 4]''',
     '''        final = local_end(cys, i0, int(check["frames"]) + int(check["settle_frames"]), 1)
        window = cys[i0:i0 + int(check["frames"]) + int(check["settle_frames"]) + 4]'''),
])

patch("motion-lib/compositions/caption-line.html", [
    ('''        tl.set(div, { opacity: 1 }, 0);
        // the chunk drifts upward while it is on screen (the hold of E1); the fit scale is part of its transform''',
     '''        tl.set(div, { opacity: 0 }, 0);       // nothing of the chunk shows before its first word
        tl.set(div, { opacity: 1 }, start);
        // the chunk drifts upward while it is on screen (the hold of E1); the fit scale is part of its transform'''),
])
print("round 9 done")
