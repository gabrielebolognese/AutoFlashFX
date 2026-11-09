#!/usr/bin/env python
"""instagram-reels: the captions file of the platform (BUILD_SPEC.md section 8, "Captions file, instagram-reels").

render_captions(manifest, channel_id, n, run_id) turns the stage's export.json (pipeline/stages/14-export, written by
pipeline/lib/caption.py) into <id>-Ncaptions.txt. The export step (pipeline/lib/export.py) calls it through
pipeline/lib/platform_lib.py; the stage that writes export.json is pipeline/stages/14-export (platform.json `stage`).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import solution as solution_lib  # noqa: E402

EM_DASH = chr(0x2014)  # built from the code point so this file never contains one


def render_captions(m: dict, channel_id: str, n: int, run_id: str) -> str:
    name = f"{channel_id}-{n}"
    hooks = m.get("hooks") or {}
    link = (m.get("link") or "").strip()
    deliverable = (m.get("deliverable") or "").strip()
    keyword_line = f"{m.get('keyword', '')} -> DM them: {deliverable}"
    if link:
        keyword_line += " " + link
    lines = ["CAPTION", (m.get("caption") or "").rstrip(), "",
             "HASHTAGS", " ".join(m.get("hashtags") or []), "",
             "COMMENT KEYWORD", keyword_line.rstrip()]
    if (m.get("deliverable_status") or "existing") == "new":
        lines.append(f"NEW deliverable to create before posting: {deliverable}")
    # SOLUTION (M12, spec section 8): flashfx | external: name link | method (the stage's export.json carries it;
    # a run without 02-expansion/solution.json says so)
    lines += ["", "SOLUTION", solution_lib.block_text(m.get("solution") if isinstance(m.get("solution"), dict) else None)]
    lines += ["", "HOOKS", f'{name}.mp4 uses: "{hooks.get("hook1", "")}"', f'{name}hook2.mp4 uses: "{hooks.get("hook2", "")}"']
    needs = [str(x) for x in (m.get("needs_review") or []) if str(x).strip()]
    if needs:
        lines += ["", "NEEDS REVIEW"] + needs
    lines += ["", "FACTS AND SOURCES"]
    for fact in m.get("facts") or []:
        lines.append(f"- {fact.get('claim', '')}: {fact.get('url', '')} (checked {fact.get('checked', '')})")
    lines += ["", "RUN", f"channels/{channel_id}/runs/{run_id}", ""]
    return "\n".join(lines).replace(EM_DASH, ", ")
