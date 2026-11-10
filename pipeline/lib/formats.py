#!/usr/bin/env python
"""formats.py: the format of a channel (BUILD_SPEC.md 14.7, M20).

A format is pipeline/formats/<id>/format.json (schema pipeline/schemas/format.schema.json): its family, the platforms it
supports, its `config` block, the stages in order (folder, label, activity, output, initial status, session group, caps,
reopen routes), the review rubric, the required channel files and the template folder. The runner, state.py, preflight,
new-channel and the review take the stage order, the session groups and the reopen routes from here, never from a list of
their own.

Formats are looked for in pipeline/formats/ and then in pipeline/tests/formats/ (the test-only footage-dummy); REELS_FORMATS_DIR
(one folder, searched first) lets a test plant a format. A stage's folder is searched in the format's own stages/ folder first,
then in pipeline/stages/ (the stage library).

    import formats
    fmt = formats.load("problem-solution-reel")
    formats.stage_table(fmt)               # [(key, label, activity, output, initial), ...] in the format's order
    formats.stage_dir(fmt, "13-render")    # the folder with run.sh, schema.json, dummy.sh of that stage

Command line (LF output):
    formats.py list                                   the formats found, one per line
    formats.py show ID                                the format.json (pretty)
    formats.py validate [ID]                          check every format (or one) against the schema and the stage library
    formats.py of-channel [--channel ID]              the format id of the channel (REELS_CHANNEL)
    formats.py stages [--format ID | --channel ID]    the stage table: key, label, activity, output, initial, folder (tab separated)
    formats.py stage-dir STAGE [--format ID]          the stage's folder
    formats.py routes STAGE [--format ID]             the stages STAGE may reopen (one per line)
    formats.py session STAGE [--format ID]            the session group of STAGE ('' when none)
    formats.py prompt STAGE NAME [--format ID]        the path of the format's prompt override NAME of STAGE ('' when none)
    formats.py required [--format ID]                 the required channel files (one per line, relative to the channel folder)
    formats.py template [--format ID]                 the template folder
    formats.py get KEY [--format ID]                  a dotted key of format.json
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

REPO = paths.REPO
DEFAULT_FORMAT = "problem-solution-reel"
SCHEMA = REPO + "/pipeline/schemas/format.schema.json"


class FormatError(Exception):
    """A missing or invalid format (exit 2)."""


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def search_dirs() -> list[str]:
    dirs = []
    extra = os.environ.get("REELS_FORMATS_DIR", "")
    if extra:
        dirs.append(extra.replace("\\", "/"))
    dirs += [REPO + "/pipeline/formats", REPO + "/pipeline/tests/formats"]
    return dirs


def dir_of(fmt_id: str) -> str:
    for d in search_dirs():
        if os.path.isfile(f"{d}/{fmt_id}/format.json"):
            return f"{d}/{fmt_id}"
    raise FormatError(f"format '{fmt_id}' not found (looked for format.json in {', '.join(d + '/' + fmt_id for d in search_dirs())})")


def path_of(fmt_id: str) -> str:
    return dir_of(fmt_id) + "/format.json"


def ids() -> list[str]:
    seen: list[str] = []
    for d in search_dirs():
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if os.path.isfile(f"{d}/{name}/format.json") and name not in seen:
                seen.append(name)
    return seen


_CACHE: dict[str, dict] = {}


def load(fmt_id: str) -> dict:
    """format.json of the format, with `_dir` (its folder) added. Cached per process."""
    key = f"{os.environ.get('REELS_FORMATS_DIR', '')}|{fmt_id}"
    if key not in _CACHE:
        p = path_of(fmt_id)
        try:
            data = read_json(p)
        except (OSError, ValueError) as exc:
            raise FormatError(f"{p}: not readable ({exc})") from exc
        data["_dir"] = os.path.dirname(p)
        _CACHE[key] = data
    return _CACHE[key]


def of_channel(channel: str | None = None) -> str:
    """The format id of a channel: channel.json `format`; REELS_FORMAT when set and no channel; else the default format."""
    cid = channel if channel is not None else paths.channel_id()
    if cid:
        cj = paths.channel_json(cid)
        if os.path.isfile(cj):
            try:
                fmt = read_json(cj).get("format", "")
            except (OSError, ValueError):
                fmt = ""
            if fmt:
                return fmt
    return os.environ.get("REELS_FORMAT") or DEFAULT_FORMAT


def current() -> dict:
    return load(of_channel())


def stage_entries(fmt: dict) -> list[dict]:
    return list(fmt.get("stages") or [])


def stage_entry(fmt: dict, key: str) -> dict:
    for s in stage_entries(fmt):
        if s["id"] == key:
            return s
    raise FormatError(f"format '{fmt.get('id')}' has no stage '{key}'")


def stage_table(fmt: dict) -> list[tuple[str, str, str, str, str]]:
    return [(s["id"], s.get("label") or s["id"], s.get("activity") or "working", s.get("output") or "",
             s.get("initial") or "pending") for s in stage_entries(fmt)]


def stage_folder_name(entry: dict) -> str:
    return entry.get("folder") or entry["id"]


def stage_dir(fmt: dict, key: str) -> str:
    """The folder of a stage: the format's own stages/<folder>, else the library pipeline/stages/<folder>."""
    try:
        name = stage_folder_name(stage_entry(fmt, key))
    except FormatError:
        name = key
    own = f"{fmt['_dir']}/stages/{name}"
    if os.path.isdir(own):
        return own
    return f"{REPO}/pipeline/stages/{name}"


def routes(fmt: dict, key: str) -> list[str]:
    return list(stage_entry(fmt, key).get("reopen") or [])


def session_of(fmt: dict, key: str) -> str:
    return str(stage_entry(fmt, key).get("session") or "")


def prompt_override(fmt: dict, key: str, name: str) -> str:
    """The path of the format's prompt override `name` of a stage (format.json stages[].prompts), or '' when it has none."""
    rel = (stage_entry(fmt, key).get("prompts") or {}).get(name)
    if not rel:
        return ""
    full = f"{fmt['_dir']}/{rel}"
    return full if os.path.isfile(full) else ""


def required_files(fmt: dict) -> list[str]:
    return list(fmt.get("required_files") or [])


def template_dir(fmt: dict) -> str:
    rel = fmt.get("template") or "template"
    return rel.replace("\\", "/") if os.path.isabs(rel) else f"{fmt['_dir']}/{rel}"


def get_dotted(obj, key: str, default=None):
    cur = obj
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return default
    return cur


def validate(fmt_id: str) -> list[str]:
    """Problems of one format (empty list: valid): the schema, unique stages, stage folders that exist, routes and
    session groups that name stages of the format."""
    problems: list[str] = []
    try:
        fmt = load(fmt_id)
    except FormatError as exc:
        return [str(exc)]
    where = path_of(fmt_id)
    try:
        import jsonschema
        schema = read_json(SCHEMA)
        data = {k: v for k, v in fmt.items() if k != "_dir"}
        for err in sorted(jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path)):
            problems.append(f"{where}: {'/'.join(str(p) for p in err.path) or '(top)'}: {err.message}")
    except ImportError:
        problems.append(f"{where}: the jsonschema package is missing: run bash pipeline/bin/setup-python")
    if fmt.get("id") != fmt_id:
        problems.append(f"{where}: id '{fmt.get('id')}' is not the folder name '{fmt_id}'")
    keys = [s.get("id") for s in stage_entries(fmt)]
    for k in set(keys):
        if keys.count(k) > 1:
            problems.append(f"{where}: stage '{k}' appears twice")
    for s in stage_entries(fmt):
        d = stage_dir(fmt, s["id"])
        if not os.path.isdir(d):
            problems.append(f"{where}: stage '{s['id']}' has no folder ({d})")
        for r in s.get("reopen") or []:
            if r not in keys:
                problems.append(f"{where}: stage '{s['id']}' reopens '{r}', which is not a stage of the format")
        if s.get("session") and s["session"] not in (fmt.get("session_groups") or {}):
            problems.append(f"{where}: stage '{s['id']}' names the session group '{s['session']}', which the format does not define")
    for name, grp in (fmt.get("session_groups") or {}).items():
        for k in grp.get("stages") or []:
            if k not in keys:
                problems.append(f"{where}: session group '{name}' names '{k}', which is not a stage of the format")
    if not os.path.isdir(template_dir(fmt)):
        problems.append(f"{where}: template folder {template_dir(fmt)} is missing")
    return problems


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
    opts = {"format": "", "channel": ""}
    for name in ("--format", "--channel"):
        if name in args:
            i = args.index(name)
            opts[name[2:]] = args[i + 1]
            del args[i:i + 2]
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "list":
            for i in ids():
                print(i)
            return 0
        if cmd == "validate":
            problems = []
            for i in (rest[:1] or ids()):
                problems += validate(i)
            for p in problems:
                print(p)
            return 1 if problems else 0
        if cmd == "of-channel":
            print(of_channel(opts["channel"] or None))
            return 0
        fid = opts["format"] or (rest[0] if cmd in ("show",) and rest else "") or of_channel(opts["channel"] or None)
        fmt = load(fid)
        if cmd == "show":
            print(json.dumps({k: v for k, v in fmt.items() if k != "_dir"}, indent=2, ensure_ascii=False))
        elif cmd == "stages":
            for key, label, activity, output, initial in stage_table(fmt):
                print("\t".join((key, label, activity, output, initial, stage_dir(fmt, key))))
        elif cmd == "stage-dir":
            print(stage_dir(fmt, rest[0]))
        elif cmd == "routes":
            for r in routes(fmt, rest[0]):
                print(r)
        elif cmd == "session":
            print(session_of(fmt, rest[0]))
        elif cmd == "prompt":
            print(prompt_override(fmt, rest[0], rest[1]))
        elif cmd == "required":
            for r in required_files(fmt):
                print(r)
        elif cmd == "template":
            print(template_dir(fmt))
        elif cmd == "get":
            v = get_dotted(fmt, rest[0], "")
            print(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, bool)) else v)
        else:
            print(__doc__)
            return 2
    except FormatError as exc:
        print(f"formats.py: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
