"""Round 12: the `after` check fits the reference's move from the frame before it first shows (not from its second frame),
and reads "gone" only after the reference was visible; caption chunks drift at the normal hold speed."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/motion/framematch.py", [
    ('''    elif kind == "after":
        ref = check["ref_selector"]
        if check.get("ref_mode") == "gone":
            op = series(rows, ref, "opacity")
            ref_end = first_index(op, 0, lambda v: v <= 0.01)
        else:
            ys = pos_series(rows, ref, "y")
            start_i = first_visible(rows, ref) or 0
            fit = fit_duration(ys, start_i, int(check.get("ref_frames", 8)), ("expo.out", "power3.out", "power2.out"))
            ref_end = None if fit["d"] is None else start_i + fit["d"]''',
     '''    elif kind == "after":
        ref = check["ref_selector"]
        if check.get("ref_mode") == "gone":
            op = series(rows, ref, "opacity")
            shown = first_visible(rows, ref) or 0
            ref_end = first_index(op, shown, lambda v: v <= 0.01)
        else:
            ys = pos_series(rows, ref, "y")
            # the move starts the frame before the element first shows (its opacity is 0 on its first frame)
            start_i = max(0, (first_visible(rows, ref) or 1) - 1)
            fit = fit_duration(ys, start_i, int(check.get("ref_frames", 8)), ("expo.out", "power3.out", "power2.out"))
            ref_end = None if fit["d"] is None else start_i + fit["d"]'''),
])

patch("motion-lib/compositions/caption-line.html", [
    ('''  {"id":"hold","type":"enum","label":"Hold level (the chunk drifts while it is on screen)","default":"calm","options":[{"value":"calm","label":"calm"},{"value":"normal","label":"normal"},{"value":"lively","label":"lively"}]}''',
     '''  {"id":"hold","type":"enum","label":"Hold level (the chunk drifts upward while it is on screen)","default":"normal","options":[{"value":"calm","label":"calm"},{"value":"normal","label":"normal"},{"value":"lively","label":"lively"}]}'''),
    ('''      var v = PC.vars({ chunks_json: [], y: 1480, max_w: 620, word_frames: 4, box_frames: 4, box_rise: 9, out_frames: 2, hold: "calm" }, window.__hyperframes.getVariables());''',
     '''      var v = PC.vars({ chunks_json: [], y: 1480, max_w: 620, word_frames: 4, box_frames: 4, box_rise: 9, out_frames: 2, hold: "normal" }, window.__hyperframes.getVariables());'''),
    ('''       fades out over 2 frames; the next chunk's first word starts on the following frame. While a chunk is on screen it
       drifts upward at the calm hold speed (E1: nothing stands still; the two caption modes of E3 come in M15). */''',
     '''       fades out over 2 frames; the next chunk's first word starts on the following frame. While a chunk is on screen it
       drifts upward at the hold speed (normal, 4 px per second: E1, nothing stands still; the two caption modes of E3
       come in M15). */'''),
])
print("round 12 done")
