"""common.py: shared helpers and constants of the sound effects memory map (BUILD_SPEC.md 2.6, M8).

Everything under pipeline/lib/sfx/ imports from here: the cue types, the file extensions, path helpers (Git Bash
gives /c/... paths, Windows Python wants C:/...), JSON and text writers (UTF-8, LF, atomic), the em dash cleaner
(no file of this project may hold one, BUILD_SPEC.md 0.7; a model's note or a tool's message may).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from errors import undash  # noqa: E402  (pipeline/lib/errors.py)

MAP_VERSION = 1          # the sfx-map.json format; a change rebuilds the map
MEASURE_VERSION = 2      # the measurement code; a change re-measures every file

AUDIO_EXTS = (".wav", ".mp3", ".aif", ".aiff", ".ogg", ".flac")

# The 12 cue types of BUILD_SPEC.md 2.6, with the description the indexer model and SFX-MAP.md use.
CUE_TYPES: dict[str, str] = {
    "transition_slow": "slow whoosh, for slower transitions (400 ms or longer, or into calm beats)",
    "transition_fast": "fast whoosh, for quick scene swaps",
    "attention": "a random fast whoosh on a visual change that has no other sound, to keep attention up",
    "hero_enter": "soft pop or click, only for hero cards and giant numbers",
    "ui_click": "a small UI click for chips, toggles and highlights changing state",
    "stamp": "short thud or hit",
    "number": "tick or short counter",
    "success": "positive UI ding (checkmarks)",
    "typing": "keyboard or UI typing (comment fields, terminals), trimmed to the typing duration",
    "negative": "soft error or scratch (strike-throughs)",
    "hook_hit": "impact with a whoosh, for the hook's set piece",
    "notification": "message sound (the CTA's DM card)",
}

# The duration window per cue type, in seconds of effective sound (onset to the -40 dB tail end). Inside the
# window the duration fit is 1; it falls linearly to 0 at twice the upper bound (far too long) and at half the
# lower bound. config sfx.cue_windows overrides these.
CUE_WINDOWS: dict[str, tuple[float, float]] = {
    "transition_slow": (0.40, 2.50),
    "transition_fast": (0.08, 0.80),
    "attention": (0.08, 0.70),
    "hero_enter": (0.03, 0.70),
    "ui_click": (0.01, 0.40),
    "stamp": (0.05, 1.00),
    "number": (0.01, 0.35),
    "success": (0.10, 1.80),
    "typing": (0.40, 30.0),
    "negative": (0.08, 1.80),
    "hook_hit": (0.20, 2.50),
    "notification": (0.15, 2.50),
}

# What kind of attack each cue type wants: "sharp" (a click, a hit: the peak right at the onset), "swell" (a slow
# whoosh: the peak well after the onset), "any".
CUE_ATTACK: dict[str, str] = {
    "transition_slow": "swell", "transition_fast": "any", "attention": "any", "hero_enter": "sharp",
    "ui_click": "sharp", "stamp": "sharp", "number": "sharp", "success": "any", "typing": "any",
    "negative": "any", "hook_hit": "any", "notification": "any",
}


def winpath(path: str) -> str:
    """/c/Users/... from Git Bash -> C:/Users/... for Windows Python (other paths unchanged)."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else (path or "")


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def clean(value, one_line: bool = True) -> str:
    """A string without em dashes, CRs or (one_line) line breaks."""
    text = "" if value is None else str(value)
    text = undash(text.replace("\r\n", "\n").replace("\r", "\n"))
    if one_line:
        text = " ".join(text.split())
    return text


def load_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, data) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def save_text(path: str, content: str) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, path)


def read_text(path: str) -> str:
    try:
        with open(winpath(path), encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def out_json(data) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def file_id(relpath: str) -> str:
    """The stable id of a pack file: the first 10 hex characters of sha1 of its relative path."""
    return sha1_text(relpath)[:10]


def slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:n].rstrip("-")) or "file"


def round_or_none(value, digits: int = 3):
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return round(v, digits)


def list_audio_files(pack_dir: str) -> list[dict]:
    """Every audio file under the pack (recursive, extensions of BUILD_SPEC.md 2.6, any case), skipping .cache/
    and previews/ (the pack's own generated folders) and dot folders. Sorted by relative path."""
    root = winpath(pack_dir)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d.lower() != "previews")
        for name in filenames:
            if not name.lower().endswith(AUDIO_EXTS):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                st = os.stat(full)
            except OSError:
                continue
            out.append({"path": rel, "size": int(st.st_size), "mtime": int(st.st_mtime)})
    out.sort(key=lambda e: e["path"])
    return out


def folder_hash(entries: list[dict]) -> str:
    """The hash of the pack folder: paths, sizes and dates (BUILD_SPEC.md 2.6 item 9)."""
    lines = [f"{e['path']}\t{e['size']}\t{e['mtime']}" for e in entries]
    return sha1_text("\n".join(lines))
