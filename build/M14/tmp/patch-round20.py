"""Round 20: an exit wins. A short-lived chip (630 ms) exits (a fall from 297 ms) before its main animation window ends
(700 ms): the review's transient check met data-pcm-main first and called the mid-fall chip "arriving", so the
short-life rule of round 19 judged it mid-fall (its text 1000 px below its place). The check now reports "exit" when
any window of the element or its ancestors is an exit, and the short-life sample sits 50 ms before the exit (the
compiled plan's exit_at), or before the end when the element has no exit."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/review/mechanical.py", [
    ('''  const transientAt = (el, t) => {
    let node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      for (const name of ["data-pcm-main", "data-pcm-exit"]) {
        const v = node.getAttribute(name);
        if (!v) continue;
        const parts = v.split(",");
        const a = parseFloat(parts[0]), b = parseFloat(parts[1]);
        if (isFinite(a) && isFinite(b) && t >= a - 1e-4 && t < b - 1e-4) return name === "data-pcm-main" ? "main" : "exit";
      }
      node = node.parentElement;
    }
    return "";
  };''',
     '''  const transientAt = (el, t) => {
    // an exit wins over a main animation (a short-lived element may leave before its entrance window ends)
    let node = el, main = false;
    while (node && node.id !== "stage" && node !== document.body) {
      for (const name of ["data-pcm-exit", "data-pcm-main"]) {
        const v = node.getAttribute(name);
        if (!v) continue;
        const parts = v.split(",");
        const a = parseFloat(parts[0]), b = parseFloat(parts[1]);
        if (isFinite(a) && isFinite(b) && t >= a - 1e-4 && t < b - 1e-4) {
          if (name === "data-pcm-exit") return "exit";
          main = true;
        }
      }
      node = node.parentElement;
    }
    return main ? "main" : "";
  };'''),
])

patch("pipeline/lib/review/common.py", [
    ('''            if settled < last:
                add(settled, f"{c['id']} landed")
            else:
                # a life shorter than the main animation window: the element is judged once, at the last sample of its
                # life that is not an exit (mechanical.py), so the samples sit as late as they can
                if int(land) + 100 < last:
                    add(int(land) + 100, f"{c['id']} landed")
                if last - 50 > start + 100:
                    add(last - 50, f"{c['id']} last")''',
     '''            if settled < last:
                add(settled, f"{c['id']} landed")
            else:
                # a life shorter than the main animation window: the element is judged once, at the last sample of its
                # life that is not an exit (mechanical.py), so the samples sit as late as they can: 50 ms before the
                # exit (the compiled plan's exit_at, local seconds) or before the end
                props = c.get("props") or {}
                exit_at = props.get("exit_at")
                leaves = last
                if props.get("exit") not in (None, "", "none") and exit_at is not None and float(exit_at) >= 0:
                    leaves = min(last, start + int(round(float(exit_at) * 1000)))
                if int(land) + 100 < leaves:
                    add(int(land) + 100, f"{c['id']} landed")
                if leaves - 50 > start + 100:
                    add(leaves - 50, f"{c['id']} last")'''),
])

patch("DECISIONS.md", [
    ('''    idea) would never be judged, so it is judged once, at the last sample of its life that is not an exit (check_times
    adds one 50 ms before its end, where the zoom and the rotation are nearly settled), for its geometry and with its
    designed size; the M11 test's planted chip above the safe top found this.''',
     '''    idea) would never be judged, so it is judged once, at the last sample of its life that is not an exit (check_times
    adds one 50 ms before its exit, or before its end when it has none), for its geometry and with its designed size;
    the M11 test's planted chip above the safe top found this, and its honest twin, which falls out 297 ms into its
    630 ms life, found that an exit window must win over a main window still open (the review had called the
    mid-fall chip "arriving" and judged it 1000 px below its place).'''),
])
print("round 20 done")
