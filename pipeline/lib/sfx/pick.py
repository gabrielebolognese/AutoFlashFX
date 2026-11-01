"""pick.py: the file for each cue, from the pools of styles/sfx/sfx-map.json (BUILD_SPEC.md S11 step 2, M11).

Rotation inside a pool (best fit first, pinned files first of all), starting at a seeded offset so two reels do not
open with the same whoosh; never the same file twice in a row for a cue type; the files used for the same cue in the
last config sfx.recent_reels (2) reels (logs/sfx-usage.json) are avoided while the pool has others. A short pool
(typing, negative on this pack: 2 files) alternates its two files. A series (assign.py: the same mandatory cue on one
component within two seconds, a checklist ticking) plays the file of its first member.

  pick(cues, pools, recent, seed, avoid_last=None, last_files=None) -> the cues with "file" (the pack path), "cache",
       "pool_entry" (the map's numbers), "pick_note"
  load_usage(path) / recent_files(usage, exclude_run_id, n_reels) / update_usage(path, usage, run_id, idea_id, cues)
"""
from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_json, save_json  # noqa: E402

USAGE_KEEP = 20


def load_usage(path: str) -> dict:
    data = load_json(path, None) if path else None
    if not isinstance(data, dict) or not isinstance(data.get("reels"), list):
        data = {"version": 1, "reels": []}
    return data


def recent_files(usage: dict, exclude_run_id: str, n_reels: int = 2) -> dict:
    """{cue type: set of paths} used in the last n reels (other than this run)."""
    out: dict = {}
    reels = [r for r in usage.get("reels", []) if r.get("run_id") != exclude_run_id][-max(0, n_reels):]
    for r in reels:
        for cue, paths in (r.get("files") or {}).items():
            out.setdefault(cue, set()).update(paths or [])
    return out


def update_usage(path: str, usage: dict, run_id: str, idea_id: str, cues: list[dict]) -> dict:
    files: dict = {}
    for c in cues:
        if c.get("file"):
            files.setdefault(c["cue_type"], [])
            if c["file"] not in files[c["cue_type"]]:
                files[c["cue_type"]].append(c["file"])
    entry = {"run_id": run_id, "idea_id": idea_id, "at": time.strftime("%Y-%m-%d %H:%M"), "files": files, "sounds": len(cues)}
    reels = [r for r in usage.get("reels", []) if r.get("run_id") != run_id]
    reels.append(entry)
    usage["reels"] = reels[-USAGE_KEEP:]
    usage["version"] = 1
    if path:
        save_json(path, usage)
    return usage


def pick(cues: list[dict], pools: dict, recent: dict | None, seed: int, avoid_last: list[str] | None = None,
         last_files: dict | None = None) -> tuple[list[dict], list[str]]:
    """Assign a file to every cue (in time order per cue type). Cues whose pool is empty are returned without a file
    (the caller drops them with a note). Returns (cues, notes)."""
    rng = random.Random(seed ^ 0x5F5E100)
    recent = recent or {}
    notes: list[str] = []
    by_cue: dict = {}
    for c in sorted(cues, key=lambda c: c["ms"]):
        by_cue.setdefault(c["cue_type"], []).append(c)
    for cue_type, lst in by_cue.items():
        pool = [p for p in (pools.get(cue_type) or []) if p.get("cache")]
        if not pool:
            for c in lst:
                c["file"] = None
                c["pick_note"] = "empty pool"
            notes.append(f"{cue_type}: the pool is empty, {len(lst)} {'sound' if len(lst) == 1 else 'sounds'} dropped")
            continue
        avoid = set(recent.get(cue_type, set()))
        if avoid_last and cue_type in avoid_last and last_files and last_files.get(cue_type):
            avoid |= set(last_files[cue_type])
        fresh = [p for p in pool if p["path"] not in avoid]
        order = fresh if fresh else pool
        if not fresh and avoid:
            notes.append(f"{cue_type}: every file of the pool was used in the last reels; rotating through the pool anyway")
        start = rng.randrange(len(order)) if len(order) > 1 else 0
        i = start
        prev = None
        heads: dict = {}
        for c in lst:
            if c.get("series_of") and c["series_of"] in heads:
                entry = heads[c["series_of"]]   # a series (a checklist ticking) plays one file
            else:
                entry = order[i % len(order)]
                if prev is not None and entry["path"] == prev and len(order) > 1:
                    i += 1
                    entry = order[i % len(order)]
                i += 1
            heads.setdefault(c["id"], entry)
            c["file"] = entry["path"]
            c["cache"] = entry["cache"]
            c["pool_entry"] = {k: entry.get(k) for k in ("id", "path", "cache", "gain_db", "duration_s", "onset_s", "peak_s", "end_s", "effective_s", "attack_s", "pad_start_s", "pad_end_s", "whoosh_speed", "fit", "pinned")}
            c["pick_note"] = "the series' file" if c.get("series_of") else ("pinned" if entry.get("pinned") else ("rotation" if len(order) > 1 else "the only file"))
            prev = entry["path"]
    return cues, notes
