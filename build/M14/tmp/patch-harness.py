p = "pipeline/lib/motion/harness.py"
s = open(p, encoding="utf-8").read()
old = '''      const cs = getComputedStyle(el);
      let scale = 1, rotation = 0;
      try { const m = new DOMMatrixReadOnly(cs.transform); scale = Math.hypot(m.a, m.b); rotation = Math.atan2(m.b, m.a) * 180 / Math.PI; } catch (e) {}
      row[sel] = { x: r.left, y: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + r.height / 2,
                   opacity: Math.round(op * 1000) / 1000, scale: Math.round(scale * 10000) / 10000, rotation: Math.round(rotation * 100) / 100,
                   text: (el.textContent || "").trim().slice(0, 80), tag: el.tagName };'''
new = '''      const cs = getComputedStyle(el);
      // the element's own transform: the scale from the length of the x basis vector (m11, m12, m13: exact under a 3D
      // parallax rotation, which a 2D hypot(a, b) would read as a smaller scale), the 2D rotation, and the parallax
      // angles ry (rotateY) and rx (rotateX) for the hold checks (M14)
      let scale = 1, rotation = 0, ry = 0, rx = 0, tx = 0, ty = 0;
      try {
        const m = new DOMMatrixReadOnly(cs.transform);
        const sx = Math.hypot(m.m11, m.m12, m.m13), sy = Math.hypot(m.m21, m.m22, m.m23);
        scale = Math.max(sx, sy);
        rotation = Math.atan2(m.m12, m.m11) * 180 / Math.PI;
        ry = Math.atan2(-m.m13, Math.hypot(m.m11, m.m12)) * 180 / Math.PI;
        rx = Math.atan2(m.m23, Math.hypot(m.m21, m.m22)) * 180 / Math.PI;
        tx = m.m41; ty = m.m42;
      } catch (e) {}
      row[sel] = { x: r.left, y: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + r.height / 2,
                   opacity: Math.round(op * 1000) / 1000, scale: Math.round(scale * 10000) / 10000, rotation: Math.round(rotation * 100) / 100,
                   ry: Math.round(ry * 100) / 100, rx: Math.round(rx * 100) / 100, tx: Math.round(tx * 1000) / 1000, ty: Math.round(ty * 1000) / 1000,
                   text: (el.textContent || "").trim().slice(0, 80), tag: el.tagName };'''
assert old in s
s = s.replace(old, new)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("harness patched")

# energy CLI: the repo's tokens by default
p = "pipeline/lib/review/energy.py"
s = open(p, encoding="utf-8").read()
old = '''    plan = load_json(a.plan) if a.plan else None
    tokens = load_json(a.tokens) if a.tokens else None'''
new = '''    plan = load_json(a.plan) if a.plan else None
    tokens_path = a.tokens or default_tokens_path()
    tokens = load_json(tokens_path) if tokens_path and os.path.isfile(tokens_path) else None'''
assert old in s
s = s.replace(old, new)
s = s.replace('''def load_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)
''', '''def load_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def default_tokens_path() -> str:
    """The style's tokens.json (config paths.tokens under the repo, or styles/paper-cards/tokens.json)."""
    try:
        from motion import common as mcommon
        return mcommon.tokens_path()
    except Exception:  # noqa: BLE001
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(here))), "styles", "paper-cards", "tokens.json")
''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("energy cli patched")

# the canvas layers' CSS
p = "motion-lib/assets/paper-cards.css"
s = open(p, encoding="utf-8").read()
s += '''
/* the canvas life (Motion and energy rules E5, E7; pc-motion.js PCM.canvas): the edge filler behind the content, partly
   outside the frame, and the ambient stars, dots and clouds in the margins. No text, never on a text zone. */
.pc-edge-layer, .pc-ambient-layer { position: absolute; inset: 0; pointer-events: none; }
.pc-edge, .pc-ambient { position: absolute; will-change: transform, opacity; }
.pc-edge svg, .pc-ambient svg { width: 100%; height: 100%; display: block; }
'''
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("css patched")
