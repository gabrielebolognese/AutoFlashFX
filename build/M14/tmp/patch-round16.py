"""Round 16: the combined main animation takes 18 frames (0.6 s, the spec's upper bound) and a screenshot scrolls at 30 px
per second: the object-position scroll moves fewer pixels than the enlarged one did, and the golden's doubled moving
share needs the margin back."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/tokens.py", [
    ('''    "main": {"min_s": 0.3, "max_s": 0.6, "frames": 15, "ease": "power3.inOut",''', '''    "main": {"min_s": 0.3, "max_s": 0.6, "frames": 18, "ease": "power3.inOut",'''),
    ('''    "content": {"scroll_px_s": 24, "note": "a screenshot inside a window card scrolls slowly through its own height (content motion, E1: the content itself keeps moving)"},''',
     '''    "content": {"scroll_px_s": 30, "note": "a screenshot inside a window card scrolls slowly through its own height (content motion, E1: the content itself keeps moving)"},'''),
    ('''            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 24)};",''', '''            f"  --m-scroll-px-s: {g.get('content', {}).get('scroll_px_s', 30)};",'''),
])
patch("motion-lib/assets/pc-motion.js", [
    ('''      mainFrames: cssNum("--m-main-frames", 15),''', '''      mainFrames: cssNum("--m-main-frames", 18),'''),
    ('''      scrollSpeed: cssNum("--m-scroll-px-s", 24),''', '''      scrollSpeed: cssNum("--m-scroll-px-s", 30),'''),
])
patch("motion-lib/compositions/window-card.html", [
    ('''  {"id":"scroll_px_s","type":"number","label":"The screenshot scrolls inside the window at this speed (px per second; 0 = still)","default":24},''',
     '''  {"id":"scroll_px_s","type":"number","label":"The screenshot scrolls inside the window at this speed (px per second; 0 = still)","default":30},'''),
    ('''        mascot: "", honesty: "none", scroll_px_s: 24, hold: "normal", exit: "none", exit_at: -1 }, window.__hyperframes.getVariables());''',
     '''        mascot: "", honesty: "none", scroll_px_s: 30, hold: "normal", exit: "none", exit_at: -1 }, window.__hyperframes.getVariables());'''),
    ('''       inside scrolls slowly (24 px per second by default, scroll_px_s) through its own height (object-fit cover, the''',
     '''       inside scrolls slowly (30 px per second by default, scroll_px_s) through its own height (object-fit cover, the'''),
])
patch("DECISIONS.md", [
    ('''0.92 for small things, or 1.15 from a close start, over 12 frames power3.inOut, and a parallax rotateY or rotateX
    from 12 degrees to 1 starting 3 frames later)''',
     '''0.92 for small things, or 1.15 from a close start, over 18 frames (0.6 s) power3.inOut, and a parallax rotateY or
    rotateX from 12 degrees to 1 starting 3 frames later)'''),
    ('''order: the window cards' screenshots scrolling inside their frames (24 px per second, enlarged a quarter for the
    room: the two window scenes went from 10 and 32 percent moving to 92 and 55), the longer combined entrances (the
    zoom and parallax over 15 frames instead of a bare 8-frame rise) and the inertia's first second.''',
     '''order: the window cards' screenshots scrolling inside their frames (30 px per second through the page's own height
    by object-position: the two window scenes went from 10 and 32 percent moving to over 80 and 60), the longer
    combined entrances (the zoom and parallax over 18 frames instead of a bare 8-frame rise) and the inertia's first
    second.'''),
])
print("round 16 done")
