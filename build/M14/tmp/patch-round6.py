"""Round 6: the M9 test's sandbox re-proposes the last bullet of each title (the proposals wrap over several lines), the
harness pages take a tag (two harnesses at once never share a page file), the window card's pan comes from pc-motion.js."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/tests/test-m9.sh", [
    ('''for title in ("Caption position", "Right side, captions", "Hook header", "Length", "Accent-filled cards", "3D"):
    s = re.sub(r"^- \\*\\*" + re.escape(title) + r":\\*\\*(?=.*Proposal:)", "- PROPOSED **" + title + ":**", s, count=1, flags=re.M)''',
     '''for title in ("Caption position", "Right side, captions", "Hook header", "Length", "Accent-filled cards", "3D"):
    # the proposal is the last bullet with that title (Length and 3D also have an earlier decision bullet)
    hits = list(re.finditer(r"^- \\*\\*" + re.escape(title) + r":\\*\\*", s, flags=re.M))
    if hits:
        m = hits[-1]
        s = s[:m.start()] + "- PROPOSED **" + title + ":**" + s[m.end():]'''),
])

patch("pipeline/lib/motion/harness.py", [
    ('''def write_page(component: dict, props: dict | None, lib: str, with_canvas: bool = True, background: bool = True) -> str:
    """The harness page is written beside the library (under .harness/) so the <base> keeps asset paths simple."""
    folder = os.path.join(lib, ".harness")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{component['id']}.html")''',
     '''def write_page(component: dict, props: dict | None, lib: str, with_canvas: bool = True, background: bool = True, tag: str = "") -> str:
    """The harness page is written beside the library (under .harness/) so the <base> keeps asset paths simple; `tag`
    names the file apart when two harnesses run at once (a probe next to frame-match, M14)."""
    folder = os.path.join(lib, ".harness")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{component['id']}{tag}.html")'''),
    ('''    def __init__(self, lib: str | None = None, gpu: str = "auto"):
        self.lib = lib or common.motion_lib_dir()
        self.gpu = gpu''', '''    def __init__(self, lib: str | None = None, gpu: str = "auto", tag: str = ""):
        self.lib = lib or common.motion_lib_dir()
        self.gpu = gpu
        self.tag = tag'''),
    ('''        path = write_page(component, props, self.lib, with_canvas, background)
        self.errors = []''', '''        path = write_page(component, props, self.lib, with_canvas, background, self.tag)
        self.errors = []'''),
])

patch("build/M14/tmp/probe.py", [
    ('''with harness.Harness(lib=lib, gpu="hardware") as h:''', '''with harness.Harness(lib=lib, gpu="hardware", tag="-probe") as h:'''),
])

patch("motion-lib/assets/pc-motion.js", [
    ('''  // a steady turn (the CSS-extruded icon)''', '''  // a slow pan of content inside a frame (a screenshot in a window card): a steady move, linear
  PCM.pan = function (tl, el, at, o) {
    o = o || {};
    var seconds = Math.max(0.5, o.seconds || 1);
    tl.fromTo(el, { x: 0, y: 0 }, { x: o.dx || 0, y: o.dy || 0, duration: seconds, ease: "none", immediateRender: false }, at);
    return at + seconds;
  };
  // a steady turn (the CSS-extruded icon)'''),
])
patch("motion-lib/compositions/window-card.html", [
    ('''        tl.fromTo(img, { y: 0 }, { y: -Math.min(80, inner.drift * 2 * Math.max(1, life.until - life.land)), duration: Math.max(0.5, life.until - life.land), ease: "none", immediateRender: false }, life.land);''',
     '''        PCM.pan(tl, img, life.land, { dy: -Math.min(80, inner.drift * 2 * Math.max(1, life.until - life.land)), seconds: life.until - life.land });'''),
])
print("round 6 done")
