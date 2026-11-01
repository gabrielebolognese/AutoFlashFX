"""overrides.py: styles/sfx/overrides.txt, the user's word on the map (BUILD_SPEC.md 2.6, item 8).

  ban: <path>                 never use the file
  pin: <cue type>: <path>     put the file first in that pool (this also approves a low-confidence file and
                              overrides the duration window)

Paths are relative to the pack folder with forward slashes, as sfx-map.json prints them; the match is exact, then
case-insensitive, then by bare file name when that name is unique in the pack. Lines starting with # and empty
lines are ignored; anything else is reported as unknown (never fatal). The build creates the file once with the
header below and never rewrites it.

  ensure_file(path) -> True when it was created
  parse(text) -> {"bans": [...], "pins": [...], "unknown": [...]}
  resolve(parsed, files) -> {"banned": {id: line}, "pinned": {cue: [ids]}, "pins_by_id": {id: [cues]},
                             "unmatched": [...]}
  effective_hash(text) -> sha1 of the effective lines (a comment edit changes nothing)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CUE_TYPES, clean, read_text, save_text, sha1_text  # noqa: E402

HEADER = """# styles/sfx/overrides.txt: your word on the sound effects map (BUILD_SPEC.md 2.6).
# pipeline/bin/build-sfx-map reads this file at every rebuild and never rewrites it. Paths are relative to
# styles/sfx/ with forward slashes, exactly as sfx-map.json and SFX-MAP.md print them (a bare file name works when
# it is unique in the pack). Lines starting with # are comments.
#
#   ban: <path>                   never use this file, for any cue type
#   pin: <cue type>: <path>       put this file first in that cue type's pool; this also approves a file the model
#                                 was unsure about (the "waiting" list of SFX-MAP.md) and overrides its duration window
#
# Cue types: transition_slow transition_fast attention hero_enter ui_click stamp number success typing negative
# hook_hit notification.
# Listen first: styles/sfx/previews/<cue type>.wav plays that pool 1 second apart, in the order listed in
# styles/sfx/previews/<cue type>.txt. After editing this file run: bash pipeline/bin/build-sfx-map
#
# Examples (remove the leading # to activate):
# ban: Transition Sound Effects/Magic Spell Sound Effect ( By Ashish Editz )_01.mp3
# pin: hook_hit: Vine Boom.mp3
"""


def ensure_file(path: str) -> bool:
    from common import winpath
    if os.path.isfile(winpath(path)):
        return False
    save_text(path, HEADER)
    return True


def effective_lines(text: str) -> list[tuple[int, str]]:
    out = []
    for n, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        line = raw.strip().lstrip("﻿")
        if not line or line.startswith("#"):
            continue
        out.append((n, line))
    return out


def effective_hash(text: str) -> str:
    return sha1_text("\n".join(line for _, line in effective_lines(text)))


def norm_path(p: str) -> str:
    p = p.strip().strip('"').strip("'").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    for prefix in ("styles/sfx/", "sfx/"):
        if p.lower().startswith(prefix):
            p = p[len(prefix):]
    return p.strip("/")


def parse(text: str) -> dict:
    bans, pins, unknown = [], [], []
    for n, line in effective_lines(text):
        head, sep, rest = line.partition(":")
        key = head.strip().lower()
        if not sep:
            unknown.append({"line": n, "text": clean(line), "reason": "expected 'ban: <path>' or 'pin: <cue type>: <path>'"})
            continue
        if key == "ban":
            path = norm_path(rest)
            if path:
                bans.append({"line": n, "path": path})
            else:
                unknown.append({"line": n, "text": clean(line), "reason": "ban without a path"})
        elif key == "pin":
            cue, sep2, path = rest.partition(":")
            cue = cue.strip().lower().replace("-", "_").replace(" ", "_")
            path = norm_path(path)
            if not sep2 or not path:
                unknown.append({"line": n, "text": clean(line), "reason": "expected 'pin: <cue type>: <path>'"})
            elif cue not in CUE_TYPES:
                unknown.append({"line": n, "text": clean(line), "reason": f"unknown cue type '{clean(cue)}'"})
            else:
                pins.append({"line": n, "cue": cue, "path": path})
        else:
            unknown.append({"line": n, "text": clean(line), "reason": f"unknown keyword '{clean(key)}' (ban or pin)"})
    return {"bans": bans, "pins": pins, "unknown": unknown}


def match_file(path: str, files: list[dict]) -> dict | None:
    for f in files:
        if f["path"] == path:
            return f
    low = path.lower()
    hits = [f for f in files if f["path"].lower() == low]
    if len(hits) == 1:
        return hits[0]
    base = os.path.basename(low)
    hits = [f for f in files if os.path.basename(f["path"]).lower() == base]
    if len(hits) == 1:
        return hits[0]
    return None


def resolve(parsed: dict, files: list[dict]) -> dict:
    banned: dict[str, int] = {}
    pinned: dict[str, list[str]] = {}
    pins_by_id: dict[str, list[str]] = {}
    unmatched = []
    for b in parsed["bans"]:
        f = match_file(b["path"], files)
        if f is None:
            unmatched.append({"line": b["line"], "text": f"ban: {b['path']}", "reason": "no such file in the pack"})
            continue
        banned[f["id"]] = b["line"]
    for p in parsed["pins"]:
        f = match_file(p["path"], files)
        if f is None:
            unmatched.append({"line": p["line"], "text": f"pin: {p['cue']}: {p['path']}", "reason": "no such file in the pack"})
            continue
        ids = pinned.setdefault(p["cue"], [])
        if f["id"] not in ids:
            ids.append(f["id"])
        cues = pins_by_id.setdefault(f["id"], [])
        if p["cue"] not in cues:
            cues.append(p["cue"])
    return {"banned": banned, "pinned": pinned, "pins_by_id": pins_by_id, "unmatched": unmatched}


def load(path: str) -> tuple[str, dict]:
    text = read_text(path)
    return text, parse(text)
