"""Round 11: a growing bar's first frame is read against its own baseline (a flat plane in a rotated card projects a few
px tall), the slide's and the bubble's final value is read at the settle frame itself, and the headline's words and
mark are parts of the block that holds (its own rotation and scale creep are the check)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/motion/framematch.py", [
    ('''def first_visible(rows, sel, thr: float = 0.02, key: str = "opacity") -> int | None:
    vals = series(rows, sel, key)
    return first_index(vals, 0, lambda v: v > thr)''',
     '''def first_visible(rows, sel, thr: float = 0.02, key: str = "opacity") -> int | None:
    vals = series(rows, sel, key)
    return first_index(vals, 0, lambda v: v > thr)


def first_grow(rows, sel, key: str = "h", step: float = 6.0) -> int | None:
    """The first frame a bar or line has grown by `step` px over its baseline (the smallest of its first frames: a flat
    plane inside a rotated card projects a few px tall before it grows, M14)."""
    vals = series(rows, sel, key)
    first = [v for v in vals[:6] if v is not None]
    base = min(first) if first else 0.0
    return first_index(vals, 0, lambda v: v >= base + step)'''),
    ('''            if mode == "grow":
                firsts.append(first_visible(rows, s, thr=1.0, key="h"))''',
     '''            if mode == "grow":
                firsts.append(first_grow(rows, s))'''),
    ('''            final = local_end(vals, i0, check["frames"], 1)
            start_v = vals[i0] if i0 < len(vals) else None''',
     '''            final = local_end(vals, i0, check["frames"])
            start_v = vals[i0] if i0 < len(vals) else None'''),
    ('''        final = local_end(cys, i0, int(check["frames"]) + int(check["settle_frames"]), 1)''',
     '''        final = local_end(cys, i0, int(check["frames"]) + int(check["settle_frames"]))'''),
])

patch("pipeline/lib/motion/expectations.py", [
    ('''        life={"selector": "#hl-lines", "at": 0, "no_inertia": True})''',
     '''        life={"selector": "#hl-lines", "at": 0, "no_inertia": True, "skip": ["#hl-mark"] + [f"#hl-lines .pc-word:nth-child({i})" for i in (1, 2, 3)]})'''),
])
print("round 11 done")
