"""probe.py: mount components in the harness and print a few measured series (M14 development aid).
  python build/M14/tmp/probe.py card:#card-box,#card-mascot paper-canvas:#paper-edge-0,#paper-ambient-0 ..."""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))
from motion import common, harness, expectations  # noqa: E402

specs = expectations.build(common.tokens())
lib = common.motion_lib_dir()
frames = int(os.environ.get("PROBE_FRAMES", "130"))
show = [int(x) for x in os.environ.get("PROBE_AT", "0,2,4,6,8,10,12,15,20,30,45,60,90,120,129").split(",")]
with harness.Harness(lib=lib, gpu="hardware", tag="-probe") as h:
    for arg in sys.argv[1:]:
        import re as _re
        mm = _re.match(r"^([a-z0-9-]+)(?:@(\{.*\}))?(?::(.*))?$", arg)
        cid, pj, sels = mm.group(1), mm.group(2), mm.group(3) or ""
        props = json.loads(pj) if pj else {}
        comp = common.parse_component(os.path.join(lib, "compositions", cid + ".html"))
        spec = specs.get(cid) or {}
        p = dict(spec.get("props") or {}); p.update(props)
        selectors = sels.split(",") if sels else spec.get("selectors", ["#root"])
        times = [i / 30 for i in range(frames + 1)]
        res = h.measure(comp, p, times, selectors)
        print(f"== {cid} props={json.dumps(p)[:120]} errors={res['errors'][:3]} events={len(res['events'])}")
        for sel in selectors:
            rows = res["rows"]
            print(f"  {sel}:")
            for i in show:
                if i >= len(rows):
                    continue
                m = rows[i].get(sel)
                if m is None:
                    print(f"    f{i:3d}: none")
                    continue
                print(f"    f{i:3d}: op {m['opacity']:.3f} cx {m['cx']:.2f} cy {m['cy']:.2f} w {m['w']:.1f} h {m['h']:.1f} sc {m['scale']:.4f} rot {m['rotation']:.2f} ry {m.get('ry', 0):.2f} rx {m.get('rx', 0):.2f} ty {m.get('ty', 0):.3f} text {m['text'][:20]!r}")
            # static windows: any 15 consecutive frames with no change in the transform or opacity or text
            keys = ("cx", "cy", "w", "h", "scale", "rotation", "ry", "rx", "opacity", "text")
            still = 0
            worst = 0
            first_vis = None
            for i in range(1, len(rows)):
                a, b = rows[i - 1].get(sel), rows[i].get(sel)
                if b and b["opacity"] > 0.02 and first_vis is None:
                    first_vis = i
                moved = a is None or b is None or any((a.get(k) != b.get(k)) for k in keys)
                still = 0 if moved else still + 1
                worst = max(worst, still)
            print(f"    first visible frame {first_vis}, longest run of unchanged frames {worst}")
        for e in res["events"][:12]:
            print("   event", e)
