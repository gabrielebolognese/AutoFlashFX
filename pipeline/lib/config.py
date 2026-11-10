#!/usr/bin/env python
"""The resolved config (BUILD_SPEC.md 14.4): config.json (engine), the format's `config` block (format.json, from M20),
the channel's `config` block (channel.json), deep-merged in that order (objects merge key by key; arrays and scalars
replace). Every script reads the resolved config through config.sh or this module; nothing else reads config.json.

    import config
    cfg = config.load()                       # resolved for REELS_CHANNEL (the engine config without a channel)
    config.get(cfg, "voice.wpm", 186)

Command line (LF output):
    config.py resolve --out FILE              write the resolved config of REELS_CHANNEL (atomic)
    config.py validate [--channel ID]         check channels/<id>/channel.json against pipeline/schemas/channel.schema.json
    config.py overrides [--channel ID]        the engine keys the channel overrides, one per line
    config.py set-channel KEY JSON            write config.<KEY> = JSON into the channel's channel.json (dotted key)
    config.py sources                         the files the resolved config is made of, one per line
    config.py brand [KEY]                     channel.json brand.KEY (default display_name) of REELS_CHANNEL

The safety keys of review (reviewer_tools, fixer_tools, fixer_paths, protected_paths) are engine keys: a channel
value for them is ignored and validate reports it.
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

REPO = paths.REPO
SAFETY_KEYS = ("reviewer_tools", "fixer_tools", "fixer_paths", "protected_paths")
CHANNEL_OWNED = ("style", "voice", "sfx", "lengths", "paths")
FORMAT_OWNED = ("research", "hooks", "judge", "script", "visual", "caption", "review")
CHANNEL_PATH_KEYS = ("ideas", "runs", "logs", "locks", "library", "hooks", "profile", "voice_dir", "styles", "style_dir",
                     "tokens", "sfx_dir", "motion_lib", "golden")


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def engine_path() -> str:
    root_cfg = paths.root() + "/config.json"
    return root_cfg if os.path.isfile(root_cfg) else REPO + "/config.json"


def deep_merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = copy.deepcopy(base)
        for k, v in over.items():
            out[k] = deep_merge(out[k], v) if k in out else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def format_path(fmt: str) -> str:
    """format.json of a format (pipeline/formats/, then the test-only pipeline/tests/formats/; formats.py knows the folders)."""
    import formats
    try:
        return formats.path_of(fmt)
    except formats.FormatError:
        return f"{REPO}/pipeline/formats/{fmt}/format.json"


def sources(channel: str | None = None) -> list[str]:
    cid = paths.channel_id() if channel is None else channel
    out = [engine_path()]
    if cid:
        cj = paths.channel_json(cid)
        if os.path.isfile(cj):
            try:
                fmt = read_json(cj).get("format", "")
            except (OSError, ValueError):
                fmt = ""
            if fmt and os.path.isfile(format_path(fmt)):
                out.append(format_path(fmt))
            out.append(cj)
    return out


def strip_safety(block: dict) -> dict:
    block = copy.deepcopy(block)
    rv = block.get("review")
    if isinstance(rv, dict):
        for k in SAFETY_KEYS:
            rv.pop(k, None)
    return block


def load(channel: str | None = None) -> dict:
    cid = paths.channel_id() if channel is None else channel
    cfg = read_json(engine_path())
    if not cid:
        return cfg
    cj = paths.channel_json(cid)
    if not os.path.isfile(cj):
        raise SystemExit(f"config: channel '{cid}' has no channel.json ({cj})")
    chan = read_json(cj)
    fmt = chan.get("format", "")
    if fmt and os.path.isfile(format_path(fmt)):
        fdata = read_json(format_path(fmt))
        cfg = deep_merge(cfg, strip_safety(fdata.get("config", {}) or {}))
        # the files a channel of this format must have are preflight checks of the format (format.json required_files, M20): they run
        # before the disk and shell checks of the engine, after its tool checks
        extra = [copy.deepcopy(e) for e in fdata.get("required_files") or []]
        req = (cfg.setdefault("preflight", {}).setdefault("require", []))
        at = next((i for i, e in enumerate(req) if e.get("check") in ("disk", "shell")), len(req))
        req[at:at] = extra
    cfg = deep_merge(cfg, strip_safety(chan.get("config", {}) or {}))
    return cfg


def brand(key: str = "display_name", channel: str | None = None) -> str:
    """channels/<id>/channel.json brand.<key> (display_name falls back to the channel's name, then its id)."""
    cid = paths.channel_id() if channel is None else channel
    if not cid or not os.path.isfile(paths.channel_json(cid)):
        return ""
    data = read_json(paths.channel_json(cid))
    val = (data.get("brand") or {}).get(key)
    if val is None and key == "display_name":
        val = data.get("name") or cid
    return str(val) if val is not None else ""


def get(cfg: dict, key: str, default=None):
    cur = cfg
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return default
    return cur


def write_resolved(out: str, channel: str | None = None) -> None:
    cfg = load(channel)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = f"{out}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, out)


def schema_path() -> str:
    return REPO + "/pipeline/schemas/channel.schema.json"


def validate_channel(cid: str) -> list[str]:
    """Problems of channels/<cid>/channel.json (empty list: valid)."""
    cj = paths.channel_json(cid)
    if not os.path.isfile(cj):
        return [f"{cj}: missing"]
    try:
        data = read_json(cj)
    except (OSError, ValueError) as exc:
        return [f"{cj}: not valid JSON ({exc})"]
    problems = []
    try:
        import jsonschema
        schema = read_json(schema_path())
        for err in sorted(jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in err.path) or "(top)"
            problems.append(f"{cj}: {where}: {err.message}")
    except ImportError:
        problems.append(f"{cj}: the jsonschema package is missing: run bash pipeline/bin/setup-python")
    if data.get("id") != cid:
        problems.append(f"{cj}: id '{data.get('id')}' is not the folder name '{cid}'")
    rv = (data.get("config") or {}).get("review")
    if isinstance(rv, dict):
        for k in SAFETY_KEYS:
            if k in rv:
                problems.append(f"{cj}: config.review.{k} is a safety key of the engine and cannot be overridden by a channel")
    return problems


def overrides(cid: str) -> list[str]:
    """Dotted engine keys the channel's config block sets (everything that is not channel- or format-owned)."""
    block = read_json(paths.channel_json(cid)).get("config", {}) or {}
    found = []

    def walk(d, prefix):
        for k, v in d.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict) and v:
                walk(v, key + ".")
            else:
                found.append(key)

    for k, v in block.items():
        if k in CHANNEL_OWNED or k in FORMAT_OWNED:
            continue
        if isinstance(v, dict) and v:
            walk(v, k + ".")
        else:
            found.append(k)
    return found


def set_channel_key(key: str, value, cid: str | None = None) -> str:
    cj = paths.channel_json(cid)
    data = read_json(cj)
    cur = data.setdefault("config", {})
    parts = key.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value
    tmp = f"{cj}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, cj)
    return cj


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    args = list(argv)
    if "--channel" in args:
        i = args.index("--channel")
        os.environ["REELS_CHANNEL"] = args[i + 1]
        del args[i:i + 2]
    cmd, rest = args[0], args[1:]
    if cmd == "resolve":
        out = rest[rest.index("--out") + 1]
        write_resolved(out)
        return 0
    if cmd == "validate":
        cid = paths.channel_id()
        problems = []
        for one in ([cid] if cid else paths.channel_ids()):
            problems += validate_channel(one)
        for p in problems:
            print(p)
        return 1 if problems else 0
    if cmd == "overrides":
        for k in overrides(paths.require_channel()):
            print(k)
        return 0
    if cmd == "set-channel":
        print(set_channel_key(rest[0], json.loads(rest[1]), paths.require_channel()))
        return 0
    if cmd == "brand":
        print(brand(rest[0] if rest else "display_name"))
        return 0
    if cmd == "sources":
        for s in sources():
            print(s)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
