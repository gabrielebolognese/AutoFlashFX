#!/usr/bin/env python
"""m15-frames.py: does every caption word and group move on every frame it is on screen? (test-m15 section 3, M15)

Opens the caption hosts of a built project (10-build/project, or a project folder) in the Playwright harness of M9 with their
real props, seeks every frame at 30 fps and reads the geometry and opacity of every word element (caption-word: #cap-w<i>,
caption-group: the block #grp-<g> and each word #grp-<g>-w<k>). A frame counts as static when an element is visible on it and
on the frame before, and neither its box, its parallax angle, its scale nor its opacity changed (E1, E3: nothing is ever
static).

  python pipeline/tests/m15-frames.py <project_dir> [--json out.json]
prints: hosts, elements, frames checked (element frames), static frames, the first static one, and "all-moving ok" or "all-moving FAIL"
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))

from motion import common as mcommon, harness  # noqa: E402
from review import common as rc  # noqa: E402

EPS = 0.01
VISIBLE = 0.05


def selectors_of(host: dict) -> list[str]:
    props = host["props"]
    out: list[str] = []
    raw = props.get("words_json")
    words = json.loads(raw) if isinstance(raw, str) else (raw or [])
    for i in range(len(words)):
        out.append(f"#cap-w{i}")
    raw = props.get("groups_json")
    groups = json.loads(raw) if isinstance(raw, str) else (raw or [])
    for g, grp in enumerate(groups):
        out.append(f"#grp-{g}")
        for k in range(len(grp.get("words", []))):
            out.append(f"#grp-{g}-w{k}")
    return out


def main() -> int:
    mcommon.setup_streams()
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    project = mcommon.mixed(a.project)
    hosts = [h for h in rc.read_hosts(project) if h.get("captions")]
    summary = {"hosts": len(hosts), "elements": 0, "element_frames": 0, "static_frames": 0, "first_static": None, "per_host": {}}
    with harness.Harness(lib=project) as h:
        for host in hosts:
            comp = mcommon.parse_component(os.path.join(project, host["src"]))
            sels = selectors_of(host)
            dur = (host["end_ms"] - host["start_ms"]) / 1000.0
            n = int(dur * 30) + 1
            times = [i / 30.0 for i in range(n)]
            res = h.measure(comp, host["props"], times, sels)
            rows = res["rows"]
            prev: dict = {}
            checked = static = 0
            first = None
            for i, row in enumerate(rows):
                for s in sels:
                    cur = row.get(s)
                    if not cur or cur["opacity"] < VISIBLE:
                        prev.pop(s, None)
                        continue
                    last = prev.get(s)
                    if last is not None:
                        checked += 1
                        moved = max(abs(cur["x"] - last["x"]), abs(cur["y"] - last["y"]), abs(cur["w"] - last["w"]), abs(cur["h"] - last["h"]),
                                    abs(cur["ry"] - last["ry"]) * 0.5, abs(cur["scale"] - last["scale"]) * 100, abs(cur["opacity"] - last["opacity"]) * 100)
                        if moved < EPS:
                            static += 1
                            if first is None:
                                first = (round(host["start_ms"] / 1000.0 + times[i], 3), s)
                    prev[s] = cur
            summary["elements"] += len(sels)
            summary["element_frames"] += checked
            summary["static_frames"] += static
            if first and summary["first_static"] is None:
                summary["first_static"] = first
            summary["per_host"][host["id"]] = {"component": host["component"], "elements": len(sels), "frames": n, "element_frames": checked, "static": static}
    print(f"hosts {summary['hosts']}, elements {summary['elements']}, element frames checked {summary['element_frames']}, static {summary['static_frames']}"
          + (f", first static at {summary['first_static']}" if summary["first_static"] else ""))
    for hid, v in summary["per_host"].items():
        print(f"  {hid} ({v['component']}): {v['elements']} elements, {v['frames']} frames, {v['element_frames']} element frames, {v['static']} static")
    ok = summary["hosts"] > 0 and summary["element_frames"] > 0 and summary["static_frames"] == 0
    print("all-moving " + ("ok" if ok else "FAIL"))
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(summary, f, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
