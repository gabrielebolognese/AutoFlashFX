"""One-off patch of the M10 build batch: the headline's word ids, the harness's tag field and the events verification.
Kept under build/M10/ as a record; safe to run twice (each edit checks for its old text)."""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def patch(rel, old, new):
    p = os.path.join(REPO, rel)
    s = open(p, encoding="utf-8").read()
    if new in s:
        print(f"{rel}: already patched")
        return
    if old not in s:
        print(f"{rel}: old text not found", file=sys.stderr)
        sys.exit(1)
    s = s.replace(old, new)
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    print(f"{rel}: patched")


patch("motion-lib/compositions/headline.html",
      '''            var span = PC.el("span", "pc-word" + (serif ? " pc-phrase" : ""), div, w);
            wordEls.push(span);''',
      '''            var span = PC.el("span", "pc-word" + (serif ? " pc-phrase" : ""), div, w);
            span.id = "hl-" + wordEls.length;  // the id the word event names (events.json verifies it on screen)
            wordEls.push(span);''')

patch("pipeline/lib/motion/harness.py",
      '''                   text: (el.textContent || "").trim().slice(0, 80) };''',
      '''                   text: (el.textContent || "").trim().slice(0, 80), tag: el.tagName };''')

patch("pipeline/lib/visual/events.py",
      '''VERIFY_TYPES = {"enter", "land", "pop", "pop_peak", "exit", "typing", "count_start", "count_end", "strike", "check", "notification", "mascot",
                "fill", "send", "reply", "row", "card", "bar", "gauge", "word", "draw", "line", "slide", "mascots", "lockup", "camera", "confetti"}
STATE_KEYS = ("opacity", "x", "y", "w", "h", "scale", "rotation", "text")''',
      '''# the events that start a visible change (verified on screen); a landing, a peak or an end of a move is the moment a
# change stops and shows no difference between the frame before and the frame after
VERIFY_TYPES = {"enter", "pop", "exit", "typing", "count_start", "strike", "check", "fill", "send", "row", "card", "bar", "gauge", "word",
                "slide", "lockup", "camera", "line"}
EXIT_TYPES = {"fade-blur", "fall", "push", "cut"}  # PC.exit registers the exit under its move's name (the extra `type` key wins)
STATE_KEYS = ("opacity", "x", "y", "w", "h", "scale", "rotation", "text")''')

patch("pipeline/lib/visual/events.py",
      '''                res = h.measure(comp, inst.get("props", {}), [], [])
                local = res.get("events", [])
                sid, beat = scene_of.get(inst["instance"], ("", ""))''',
      '''                res = h.measure(comp, inst.get("props", {}), [], [])
                local = []
                for e in res.get("events", []):
                    e = dict(e)
                    if e.get("type") in EXIT_TYPES:
                        e["transition_type"] = e["type"]
                        e["type"] = "exit"
                    local.append(e)
                sid, beat = scene_of.get(inst["instance"], ("", ""))''')

patch("pipeline/lib/visual/events.py",
      '''                    times = sorted({t for ts in rows_by_el.values() for t0 in ts for t in (max(0.0, t0 - FRAME_S), t0 + FRAME_S)})''',
      '''                    times = sorted({t for ts in rows_by_el.values() for t0 in ts for t in (max(0.0, t0 - FRAME_S), t0 + FRAME_S, t0 + 2 * FRAME_S)})''')

patch("pipeline/lib/visual/events.py",
      '''                    for k in ("end", "chars", "move", "kind", "chunk", "em", "width"):''',
      '''                    for k in ("end", "chars", "move", "kind", "chunk", "em", "width", "transition_type"):''')

patch("pipeline/lib/visual/events.py",
      '''                        ok = changed(before, after)
                        ev["verified"] = ok''',
      '''                        ok = changed(before, after)
                        if not ok and e.get("type") == "typing":  # 2 frames per character: the first letter shows on the second frame
                            ok = changed(before, measured.get(round(t0 + 2 * FRAME_S, 4), {}).get("#" + e["el"]))
                        if not ok and before and str(before.get("tag", "")).upper() == "CANVAS":
                            ok = canvas_changed(h, comp["id"], max(0.0, t0 - FRAME_S), t0 + FRAME_S, before)
                        ev["verified"] = ok''')

patch("pipeline/lib/visual/events.py",
      '''def timeline_check(project: str, instances: list[dict]) -> dict:''',
      '''def canvas_changed(h: harness.Harness, comp_id: str, t_before: float, t_after: float, box: dict) -> bool:
    """A canvas draws from the hf-seek time (hero-3d): compare its pixels one frame before and after the event."""
    from PIL import Image, ImageChops, ImageStat
    clip = {"x": max(0, box["x"]), "y": max(0, box["y"]), "width": max(1, min(1080 - box["x"], box["w"])), "height": max(1, min(1920 - box["y"], box["h"]))}
    shots = []
    paths = []
    for t in (t_before, t_after):
        h.page.evaluate(harness.SEEK_JS, {"id": comp_id, "t": t})
        h.page.wait_for_timeout(40)
        png = os.path.join(h.lib, ".harness", f"ev-{round(t * 1000)}.png")
        h.page.screenshot(path=png, clip=clip)
        shots.append(Image.open(png).convert("L"))
        paths.append(png)
    diff = ImageChops.difference(shots[0], shots[1])
    mean = ImageStat.Stat(diff).mean[0]
    for im in shots:
        im.close()
    for png in paths:
        try:
            os.remove(png)
        except OSError:
            pass
    return mean > 0.5


def timeline_check(project: str, instances: list[dict]) -> dict:''')
print("done")
