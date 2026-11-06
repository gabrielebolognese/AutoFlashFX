#!/usr/bin/env python
"""The one Python module that knows the folder layout (BUILD_SPEC.md 14.5). paths.sh gives the same answers.

    import paths
    paths.ch("library/hooks.txt")       -> <root>/channels/<id>/library/hooks.txt (REELS_CHANNEL; refuses another channel)
    paths.library(), paths.styles(), paths.motionlib(), paths.golden(), paths.runs(), paths.logs(), paths.locks(), paths.ideas()
    paths.exports(), paths.export_path("flashfx-3")
    paths.cfg_path(cfg, "paths.profile") -> the value of a resolved-config key, resolved against the channel folder
    paths.channel_ids(), paths.channel_json(id), paths.require_channel()

Environment: REELS_ROOT (default: the repo), REELS_CHANNEL, REELS_GLOBAL_LOCKS, REELS_PATH_TRACE=1 (+ REELS_PATH_TRACE_FILE).
A path inside another channel's folder or another channel's export folder exits with code 3 and an ERROR line.

Command line (LF output):  python paths.py dump | list | channel-root [--channel ID]
"""
from __future__ import annotations

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
ID_RE = re.compile(r"^[a-z][a-z0-9]{1,23}$")

# the names inside a channel folder (BUILD_SPEC.md 14.3): code that is handed a channel folder (ideas.py, export.py, protect.py)
# joins these names, never a literal
IDEAS_FILE = "ideas.txt"
LIBRARY_DIR = "library"
STYLES_DIR = "styles"
MOTIONLIB_DIR = "motion-lib"
GOLDEN_DIR = "golden"
RUNS_DIR = "runs"
LOGS_DIR = "logs"
LOCKS_DIR = ".locks"
EXPORTS_DIR = "exports"


def mixed(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/") if path else path


def root() -> str:
    return mixed(os.environ.get("REELS_ROOT") or REPO)


def channel_id() -> str:
    return os.environ.get("REELS_CHANNEL", "")


def channels_dir() -> str:
    return root() + "/channels"


def exports() -> str:
    return root() + "/exports"


def global_locks() -> str:
    return mixed(os.environ.get("REELS_GLOBAL_LOCKS") or (root() + "/.locks"))


def global_logs() -> str:
    return root() + "/logs"


def channel_root(cid: str | None = None) -> str:
    cid = channel_id() if cid is None else cid
    return f"{channels_dir()}/{cid}" if cid else ""


def _trace(path: str) -> None:
    if os.environ.get("REELS_PATH_TRACE") != "1":
        return
    target = os.environ.get("REELS_PATH_TRACE_FILE")
    if target:
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            f.write(path + "\n")
    else:
        sys.stderr.write("PATH " + path + "\n")


class PathRefused(SystemExit):
    def __init__(self, message: str):
        sys.stderr.write("ERROR paths: " + message + "\n")
        super().__init__(3)


def check(path: str) -> str:
    """Refuse (exit 3) a path inside another channel's folder or another channel's export folder."""
    p = mixed(path)
    me = channel_id()
    cd = channels_dir() + "/"
    ex = exports() + "/"
    if me and p.startswith(cd):
        other = p[len(cd):].split("/", 1)[0]
        if other != me:
            raise PathRefused(f"{p} is inside channel '{other}', and this run belongs to channel '{me}' "
                              f"(a channel never reads another channel's folder)")
    elif me and p.startswith(ex):
        first = p[len(ex):].split("/", 1)[0]
        m = re.match(r"^([a-z][a-z0-9]*)-\d+", first)
        if m and m.group(1) != me:
            raise PathRefused(f"{p} is another channel's export folder ('{m.group(1)}'), and this run belongs to channel '{me}'")
    return p


def ch(relative: str = "") -> str:
    """Channel data: <root>/channels/<id>/<relative>."""
    cr = channel_root()
    if not cr:
        raise PathRefused(f"no channel is set (REELS_CHANNEL), cannot resolve '{relative}'")
    rel = str(relative).replace("\\", "/")
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise PathRefused(f"'{relative}' is not relative to the channel folder")
    if ".." in rel.split("/"):
        raise PathRefused(f"'{relative}' leaves the channel folder")
    rel = rel[2:] if rel.startswith("./") else rel
    full = cr if rel in ("", ".") else f"{cr}/{rel}"
    check(full)
    _trace(full)
    return full


def export_path(rel: str = "") -> str:
    full = exports() + (f"/{rel}" if rel else "")
    check(full)
    _trace(full)
    return full


def cfg_path(cfg: dict, key: str, default: str | None = None) -> str:
    cur = cfg
    for part in key.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    if cur is None:
        if default is None:
            raise KeyError(f"config: missing key {key}")
        cur = default
    return ch(str(cur))


def ideas() -> str: return ch(IDEAS_FILE)
def library() -> str: return ch(LIBRARY_DIR)
def styles() -> str: return ch(STYLES_DIR)
def motionlib() -> str: return ch(MOTIONLIB_DIR)
def golden() -> str: return ch(GOLDEN_DIR)
def runs() -> str: return ch(RUNS_DIR)
def brand() -> str: return ch(LIBRARY_DIR + "/brand")


def logs() -> str:
    return ch(LOGS_DIR) if channel_id() else global_logs()


def locks() -> str:
    return ch(LOCKS_DIR) if channel_id() else global_locks()


def channel_json(cid: str | None = None) -> str:
    return channel_root(cid) + "/channel.json"


def channel_ids() -> list[str]:
    out = []
    try:
        names = sorted(os.listdir(channels_dir()))
    except OSError:
        return out
    for name in names:
        if os.path.isfile(f"{channels_dir()}/{name}/channel.json"):
            out.append(name)
    return out


def channel_rows() -> list[dict]:
    rows = []
    for cid in channel_ids():
        try:
            with open(channel_json(cid), encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        rows.append({"id": cid, "name": data.get("name", "?"), "platform": data.get("platform", "?"),
                     "format": data.get("format", "?"), "enabled": data.get("enabled", True) is not False})
    return rows


def require_channel() -> str:
    """The channel of this process; exits 2 with the channel list when none is set or it is unknown."""
    cid = channel_id()
    if not cid:
        ids = channel_ids()
        if len(ids) == 1:
            os.environ["REELS_CHANNEL"] = ids[0]
            return ids[0]
        sys.stderr.write("no channel given: set REELS_CHANNEL=<id>. Channels:\n" + list_text() + "\n")
        raise SystemExit(2)
    if not os.path.isfile(channel_json(cid)):
        sys.stderr.write(f"unknown channel '{cid}'. Channels:\n" + list_text() + "\n")
        raise SystemExit(2)
    return cid


def list_text() -> str:
    rows = channel_rows()
    if not rows:
        return "(no channel folder under channels/)"
    return "\n".join(f"  {r['id']}: {r['name']} ({r['platform']}, {r['format']}, {'enabled' if r['enabled'] else 'disabled'})" for r in rows)


def dump() -> list[tuple[str, str]]:
    cid = channel_id()
    cr = channel_root()
    names = [
        ("REELS_CHANNELS_DIR", channels_dir()), ("REELS_EXPORTS", exports()), ("REELS_GLOBAL_LOCKS", global_locks()),
        ("REELS_GLOBAL_LOGS", global_logs()), ("REELS_CHANNEL_ROOT", cr),
        ("REELS_IDEAS", cr + "/ideas.txt" if cid else ""),
        ("REELS_LOGS", cr + "/logs" if cid else global_logs()),
        ("REELS_LOCKS", cr + "/.locks" if cid else global_locks()),
        ("REELS_RUNS", cr + "/runs" if cid else ""), ("REELS_LIBRARY", cr + "/library" if cid else ""),
        ("REELS_STYLES", cr + "/styles" if cid else ""), ("REELS_MOTIONLIB", cr + "/motion-lib" if cid else ""),
        ("REELS_GOLDEN", cr + "/golden" if cid else ""),
    ]
    return names


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    cmd = argv[0] if argv else "dump"
    if "--channel" in argv:
        os.environ["REELS_CHANNEL"] = argv[argv.index("--channel") + 1]
    if cmd == "dump":
        for k, v in dump():
            print(f"{k}={v}")
        return 0
    if cmd == "list":
        print(list_text())
        return 0
    if cmd == "channel-root":
        print(channel_root())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
