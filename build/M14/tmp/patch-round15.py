"""Round 15: the CTA's DM card and the end card's lockup move up (dm y 1305 to 1266, lockup_y 1170 to 1146): with the
captions at y 1332 the safe-zone exception of the old caption band (y 1480) is gone, and the DM card at 1305 ended
below the safe bottom (1440). The director's defaults (plan9.apply_branding), the golden plan (goldenplan.py), the
validator fixtures and the frozen run plans and projects follow."""
import json
import os
import re

DM_Y_OLD, DM_Y_NEW = 1305, 1266
LOCK_OLD, LOCK_NEW = 1170, 1146


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/lib/visual/plan9.py", [
    ('''              "props": {"verb": "Comment", "keyword": keyword, "line1": "and I send it to you", "line2": "", "lockup_w": 300, "lockup_y": 1170}}''',
     '''              "props": {"verb": "Comment", "keyword": keyword, "line1": "and I send it to you", "line2": "", "lockup_w": 300, "lockup_y": 1146}}'''),
    ('''                        "x": 110, "y": 1305, "w": 740, "enter": "drop"}}''',
     '''                        "x": 110, "y": 1266, "w": 740, "enter": "drop"}}  # ends above the safe bottom (1440) now that the captions sit at 1332 (M14)'''),
])
patch("pipeline/lib/motion/goldenplan.py", [
    ('''"lockup": "brand/lockup/lockup-gradient-on-light.png", "lockup_w": 300, "lockup_y": 1170}},''',
     '''"lockup": "brand/lockup/lockup-gradient-on-light.png", "lockup_w": 300, "lockup_y": 1146}},'''),
    ('''"time_label": "", "app_label": "Instagram", "x": 110, "y": 1305, "w": 740, "enter": "drop"}},''',
     '''"time_label": "", "app_label": "Instagram", "x": 110, "y": 1266, "w": 740, "enter": "drop"}},'''),
])


def walk(obj):
    """Every dict in a JSON value."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def fix_json(path):
    raw = open(path, encoding="utf-8-sig").read()
    data = json.loads(raw)
    n = 0
    for d in walk(data):
        comp = d.get("component")
        props = d.get("props") if isinstance(d.get("props"), dict) else None
        if comp == "dm-card" and props is not None and props.get("y") == DM_Y_OLD:
            props["y"] = DM_Y_NEW; n += 1
        if comp == "end-card" and props is not None and props.get("lockup_y") == LOCK_OLD:
            props["lockup_y"] = LOCK_NEW; n += 1
        # the director's answers nest the props the same way; a bare dm entry with y
        if d.get("component") == "dm-card" and d.get("y") == DM_Y_OLD:
            d["y"] = DM_Y_NEW; n += 1
        if d.get("component") == "end-card" and d.get("lockup_y") == LOCK_OLD:
            d["lockup_y"] = LOCK_NEW; n += 1
    if n:
        indent = 1 if raw.startswith("{\n \"") else 2
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.write("\n")
    return n


def fix_text(path):
    s = open(path, encoding="utf-8").read()
    s2 = s.replace(f'"y": {DM_Y_OLD}', f'"y": {DM_Y_NEW}').replace(f'\\"y\\": {DM_Y_OLD}', f'\\"y\\": {DM_Y_NEW}')
    s2 = s2.replace(f'"lockup_y": {LOCK_OLD}', f'"lockup_y": {LOCK_NEW}').replace(f'\\"lockup_y\\": {LOCK_OLD}', f'\\"lockup_y\\": {LOCK_NEW}')
    if s2 != s:
        open(path, "w", encoding="utf-8", newline="\n").write(s2)
        return 1
    return 0


files = []
for root in ("pipeline/tests/fixtures/plans", "pipeline/tests/fixtures/runs/test-idea", "pipeline/tests/fixtures/fake/m10", "golden/test-idea"):
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f).replace("\\", "/")
            if f.endswith(".json") or f == "index.html":
                files.append(p)
changed = 0
for p in files:
    raw = open(p, encoding="utf-8-sig", errors="replace").read()
    if str(DM_Y_OLD) not in raw and str(LOCK_OLD) not in raw:
        continue
    if p.endswith(".json"):
        try:
            k = fix_json(p)
        except ValueError:
            k = fix_text(p)
    else:
        k = fix_text(p)
    if k:
        changed += 1
        print("fixed", p, k)
print("files changed", changed)
# the validator's zone rule around the CTA
s = open("pipeline/lib/visual/plan_validate.py", encoding="utf-8").read()
i = s.find('elif s["id"] == cta and y1 > safe_bottom + tol and cid not in ("dm-card", "end-card"):')
print("plan_validate context:\n" + s[i - 900:i + 300])
