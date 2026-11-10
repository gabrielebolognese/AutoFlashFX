"""gaps.py: logs/editor-gaps.md (BUILD_SPEC.md S15 step 7 and 14.9, M21).

One line per missing editor manifest key, with a running count of the layers it kept from being native, the elements it affected and the
latest reel, sorted by count: the to-do list for the editor's next batches. Per channel (channels/<id>/logs/editor-gaps.md, with its state in
editor-gaps.json) and rolled up for every channel in logs/editor-gaps-all.md at the root.
"""
from __future__ import annotations

import glob
import json
import os


def collect(fallbacks: list[dict]) -> dict:
    """{missing key: {"count": layers, "elements": [names]}} of one reel."""
    out: dict = {}
    for f in fallbacks:
        for k in f.get("missing") or []:
            e = out.setdefault(k, {"count": 0, "elements": []})
            e["count"] += 1
            name = f.get("name") or f.get("layer")
            if name and name not in e["elements"]:
                e["elements"].append(name)
    return out


def merge(state: dict, gaps: dict, video: str) -> dict:
    for k, g in gaps.items():
        e = state.setdefault(k, {"count": 0, "elements": [], "latest": ""})
        e["count"] += g["count"]
        for name in g["elements"]:
            if name not in e["elements"]:
                e["elements"].append(name)
        e["latest"] = video
    return state


def render_md(state: dict, title: str) -> str:
    lines = [f"# {title}", "", "One line per missing editor manifest key: the running count of layers it kept from being native, the elements, the latest reel.", ""]
    for k, e in sorted(state.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        els = ", ".join(e["elements"][:8]) + (" ..." if len(e["elements"]) > 8 else "")
        lines.append(f"- `{k}`: {e['count']} layers; {els}; latest {e.get('latest') or '-'}")
    if not state:
        lines.append("(no gaps: every layer so far was native or baked only because its look changes continuously)")
    return "\n".join(lines) + "\n"


def update_logs(channel_logs: str, root_logs: str, channels_dir: str, gaps: dict, video: str) -> None:
    os.makedirs(channel_logs, exist_ok=True)
    sp = os.path.join(channel_logs, "editor-gaps.json")
    try:
        state = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state = merge(state, gaps, video)
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2)
    with open(os.path.join(channel_logs, "editor-gaps.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(state, "Editor gaps"))
    total: dict = {}
    for p in sorted(glob.glob(os.path.join(channels_dir, "*", "logs", "editor-gaps.json"))):
        try:
            st = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ch = os.path.basename(os.path.dirname(os.path.dirname(p)))
        for k, e in st.items():
            t = total.setdefault(k, {"count": 0, "elements": [], "latest": ""})
            t["count"] += e["count"]
            for name in e["elements"]:
                tag = f"{ch}: {name}"
                if tag not in t["elements"]:
                    t["elements"].append(tag)
            t["latest"] = e.get("latest") or t["latest"]
    os.makedirs(root_logs, exist_ok=True)
    with open(os.path.join(root_logs, "editor-gaps-all.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(total, "Editor gaps, every channel"))
