"""icon-3d is treated like hero-3d wherever the pipeline special-cases the 3D component (clip_start, the label, the footprint)."""
import re

def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:60])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)

patch("pipeline/lib/visual/events.py", [
    ('''                if inst["component"] == "hero-3d":
                    props["clip_start"] = 0''', '''                if inst["component"] in ("hero-3d", "icon-3d"):
                    props["clip_start"] = 0'''),
])
patch("pipeline/lib/motion/golden.py", [
    ('''            if comp["component"] == "hero-3d":
                props["clip_start"] = round(start, 3)''', '''            if comp["component"] in ("hero-3d", "icon-3d"):
                props["clip_start"] = round(start, 3)'''),
])
patch("pipeline/lib/review/mechanical.py", [
    ('''            if host["component"] == "hero-3d":
                props["clip_start"] = 0''', '''            if host["component"] in ("hero-3d", "icon-3d"):
                props["clip_start"] = 0'''),
])
patch("pipeline/lib/visual/plan_validate.py", [
    ('''    if cid in ("hero-3d", "mascot", "logo-tile", "paper-canvas", "caption-line", "camera-move", "exit-move", "thumb-grid"):
        return bool(props.get("label")) if cid == "hero-3d" else False''', '''    if cid in ("hero-3d", "icon-3d", "mascot", "logo-tile", "paper-canvas", "caption-line", "camera-move", "exit-move", "thumb-grid"):
        return bool(props.get("label")) if cid in ("hero-3d", "icon-3d") else False'''),
    ('''                if k not in declared and not (c["component"] == "hero-3d" and k == "clip_start"):''',
     '''                if k not in declared and not (c["component"] in ("hero-3d", "icon-3d") and k == "clip_start"):'''),
    ('''            if c["component"] == "hero-3d" and re.search(r"flashfx", str(c.get("props", {}).get("label", "")), re.I):''',
     '''            if c["component"] in ("hero-3d", "icon-3d") and re.search(r"flashfx", str(c.get("props", {}).get("label", "")), re.I):'''),
])
s = open("pipeline/lib/visual/common.py", encoding="utf-8").read()
print("common.py 452:", s.splitlines()[451])
print("common.py 486:", s.splitlines()[485])
s = s.replace('''    if component == "hero-3d":
        return _num(props, "enter_frames", 12)''', '''    if component in ("hero-3d", "icon-3d"):
        return _num(props, "enter_frames", 12)''')
lines = s.splitlines()
# the footprint special case at line 452 (0-based 451)
if lines[451].strip() == 'if component == "hero-3d":':
    lines[451] = lines[451].replace('if component == "hero-3d":', 'if component in ("hero-3d", "icon-3d"):')
    s = "\n".join(lines) + "\n"
    print("footprint patched")
open("pipeline/lib/visual/common.py", "w", encoding="utf-8", newline="\n").write(s)
s = open("pipeline/lib/visual/plan9.py", encoding="utf-8").read()
i = s.find('if cid == "hero-3d":')
print("plan9 context:", s[i - 300:i + 200] if i >= 0 else "not found")
