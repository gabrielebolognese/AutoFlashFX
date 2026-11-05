"""Round 17b: test-m14 section 3 checks the review's reading of the grammar's transients: the DM card's texts are
"arriving" for the main animation (18 frames plus the 3-frame lag), their scale reads 0.85 at the first frame (the 3D
basis length, no cos of the rotation), at least 1 from the landing on (the inertia grows, never shrinks), and "leaving"
during the exit."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/tests/test-m14.sh", [
    ('''    print("counts", counts)
    print("layers-present", "ok" if all(e >= 4 and a >= 8 for _, e, a in counts) else "no")''',
     '''    # the review and the transients: the DM card's texts while it arrives, once landed, while it leaves
    from review import mechanical
    dm = common.parse_component(os.path.join(lib, "compositions", "dm-card.html"))
    h.open(dm, {"enter_at": 0.0, "exit": "fall", "exit_at": 2.5})
    rv = h.page.evaluate(mechanical.REVIEW_JS, {"id": "dm-card", "times": [0.1, 0.5, 1.0, 2.0, 2.6]})
    by_t = {}
    for row in rv["rows"]:
        by_t[row["t"]] = [t for t in row["texts"] if t["opacity"] >= 0.5]
    arriving = by_t.get(0.1, []) and by_t.get(0.5, []) and all(t["transient"] == "main" for t in by_t[0.1] + by_t[0.5])
    first_scale = min((t["scale"] for t in by_t.get(0.1, [])), default=0)
    settled = by_t.get(1.0, []) and by_t.get(2.0, []) and all(t["transient"] == "" and t["scale"] >= 0.999 for t in by_t[1.0] + by_t[2.0])
    small = [t for t in by_t.get(1.0, []) if t["size"] <= 28.5]
    leaving = by_t.get(2.6, []) and all(t["transient"] == "exit" for t in by_t[2.6])
    print("review-rows", {k: [(t["text"][:9], round(t["scale"], 3), t["transient"]) for t in v] for k, v in by_t.items()})
    print("review-arriving", "ok" if arriving and 0.8 <= first_scale <= 0.87 else "no")
    print("review-settled", "ok" if settled and small and all(t["size"] * t["scale"] >= 27.9 for t in small) else "no")
    print("review-leaving", "ok" if leaving else "no")
    print("counts", counts)
    print("layers-present", "ok" if all(e >= 4 and a >= 8 for _, e, a in counts) else "no")'''),
    ('''  assert_grep "^speeds ok" /tmp/m14-i3.txt "the edge layer moves at most 20 px per second, the ambient layer slower"
fi''',
     '''  assert_grep "^speeds ok" /tmp/m14-i3.txt "the edge layer moves at most 20 px per second, the ambient layer slower"
  assert_grep "^review-arriving ok" /tmp/m14-i3.txt "the review sees the DM card's texts arriving for the combined animation (data-pcm-main), the scale read in 3D (0.85 at the first frame)"
  assert_grep "^review-settled ok" /tmp/m14-i3.txt "once landed the texts are judged, their scale at least 1 (the inertia grows): the 28 px labels read 28 px or more"
  assert_grep "^review-leaving ok" /tmp/m14-i3.txt "the review sees the texts leaving during the exit (data-pcm-exit)"
fi'''),
])
print("round 17b done")
