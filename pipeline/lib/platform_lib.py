#!/usr/bin/env python
"""Platforms (BUILD_SPEC.md section 8 and 14.1): pipeline/platforms/<platform>/platform.json says what a platform's export contains.

    import platform_lib                              (not `platform`: that name would hide Python's own module)
    platform_lib.load("youtube-shorts")              -> the platform.json dict (raises PlatformError)
    platform_lib.problems("youtube-shorts")          -> the schema problems of platform.json (empty: valid)
    platform_lib.settings(cid)                       -> the platform's export_defaults with channel.json `export` laid over them
    platform_lib.file_names("instagram-reels", "flashfx", 3)   -> ["flashfx-3.mp4", "flashfx-3captions.txt", "flashfx-3hook2.mp4"]
    platform_lib.exporter("instagram-reels")         -> the module of the platform's exporter (render_captions(manifest, id, n, run_id))
    platform_lib.of_channel(cid)                     -> the platform id of a channel (channel.json)

Command line (LF output):
    python pipeline/lib/platform_lib.py list | show <id> | check <id> | settings <channel id> | of <channel id>
Exit codes: 0 ok, 1 problems, 2 unknown platform or usage.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE)).replace("\\", "/")
PLATFORMS_DIR = "pipeline/platforms"
SCHEMA = "pipeline/schemas/platform.schema.json"


class PlatformError(Exception):
    pass


def repo_root() -> str:
    return os.environ.get("REELS_REPO", "").replace("\\", "/") or REPO


def platform_dir(pid: str) -> str:
    return f"{repo_root()}/{PLATFORMS_DIR}/{pid}"


def platform_ids() -> list[str]:
    base = f"{repo_root()}/{PLATFORMS_DIR}"
    try:
        return sorted(n for n in os.listdir(base) if os.path.isfile(f"{base}/{n}/platform.json"))
    except OSError:
        return []


def load(pid: str) -> dict:
    path = platform_dir(pid) + "/platform.json"
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise PlatformError(f"unknown platform '{pid}' ({path}: {exc}); known: {', '.join(platform_ids()) or 'none'}") from exc


def problems(pid: str) -> list[str]:
    try:
        data = load(pid)
    except PlatformError as exc:
        return [str(exc)]
    out = []
    try:
        import jsonschema
        with open(f"{repo_root()}/{SCHEMA}", encoding="utf-8-sig") as f:
            schema = json.load(f)
        for err in sorted(jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path)):
            out.append(f"{pid}/platform.json: {'/'.join(str(p) for p in err.path) or '(top)'}: {err.message}")
    except ImportError:
        out.append("the jsonschema package is missing: run bash pipeline/bin/setup-python")
    if data.get("id") != pid:
        out.append(f"{pid}/platform.json: id '{data.get('id')}' is not the folder name")
    exp = data.get("exporter")
    if exp and not os.path.isfile(f"{platform_dir(pid)}/{exp}"):
        out.append(f"{pid}/platform.json: the exporter file {exp} is missing")
    hook2_files = [f for f in data.get("files", []) if "hook2" in f]
    if bool(hook2_files) != bool(data.get("hook2")):
        out.append(f"{pid}/platform.json: hook2 is {data.get('hook2')} but files lists {len(hook2_files)} hook 2 file(s)")
    return out


def of_channel(cid: str) -> str:
    try:
        with open(paths.channel_json(cid), encoding="utf-8-sig") as f:
            return json.load(f).get("platform", "")
    except (OSError, ValueError):
        return ""


def settings(cid: str) -> dict:
    """The platform's export defaults with the channel's own `export` block laid over them (BUILD_SPEC.md section 8)."""
    pid = of_channel(cid)
    out = dict(load(pid).get("export_defaults") or {})
    try:
        with open(paths.channel_json(cid), encoding="utf-8-sig") as f:
            out.update(json.load(f).get("export") or {})
    except (OSError, ValueError):
        pass
    return out


def file_names(pid: str, cid: str, n: int) -> list[str]:
    return [f.replace("{id}", cid).replace("{n}", str(n)) for f in load(pid).get("files", [])]


def exporter(pid: str):
    data = load(pid)
    path = f"{platform_dir(pid)}/{data['exporter']}"
    spec = importlib.util.spec_from_file_location(f"reels_exporter_{pid.replace('-', '_')}", path)
    if spec is None or spec.loader is None:
        raise PlatformError(f"cannot load the exporter {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    if not hasattr(mod, "render_captions"):
        raise PlatformError(f"{path} has no render_captions(manifest, channel_id, n, run_id)")
    return mod


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    cmd = argv[0] if argv else ""
    try:
        if cmd == "list":
            for pid in platform_ids():
                print(pid)
            return 0
        if cmd == "show" and len(argv) > 1:
            print(json.dumps(load(argv[1]), indent=2))
            return 0
        if cmd == "check" and len(argv) > 1:
            probs = problems(argv[1])
            for p in probs:
                print(p)
            print(f"platform {argv[1]}: {'ok' if not probs else str(len(probs)) + ' problem(s)'}")
            return 1 if probs else 0
        if cmd == "settings" and len(argv) > 1:
            print(json.dumps(settings(argv[1])))
            return 0
        if cmd == "of" and len(argv) > 1:
            pid = of_channel(argv[1])
            print(pid)
            return 0 if pid else 2
    except PlatformError as exc:
        print(f"platform: {exc}", file=sys.stderr)
        return 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
