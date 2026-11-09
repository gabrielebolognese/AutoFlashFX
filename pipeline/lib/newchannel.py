#!/usr/bin/env python
"""new-channel (BUILD_SPEC.md 14.7): creates channels/<id>/ from a format's template and a platform's defaults.

    python pipeline/lib/newchannel.py <id> --format <format> --platform <platform> [--name "Display Name"]

  1. checks the id (lowercase letters and digits, 2 to 24, starting with a letter), that the channel does not exist, that the format
     has a template folder (pipeline/formats/<format>/template/) and that the platform has a valid platform.json (and, when the
     format's format.json lists its platforms, that the platform is one of them)
  2. copies the template into channels/<id>/ (every file that says [FILL IN] is something you write), makes an empty ideas.txt
     and logs/, and writes channel.json: id, name, platform, format, language en, enabled false, daily_quota 0, brand, the
     platform's export defaults and the channel-owned config of template/channel.config.json (style, voice, sfx, lengths, paths)
  3. prints what you must fill in and the commands that check it. `bash pipeline/bin/preflight --channel <id>` lists every missing file.

A format or a platform that does not exist is engine work, not a new channel (14.7): exit 2 with that sentence.
Exit codes: 0 created, 2 refused (nothing is written).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402
import platform_lib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE)).replace("\\", "/")
MARKER = "[FILL IN]"


def die(msg: str) -> None:
    print(f"new-channel: {msg}", file=sys.stderr)
    raise SystemExit(2)


def fill_in_files(folder: str) -> list[str]:
    found = []
    for dp, _dn, fn in os.walk(folder):
        for n in sorted(fn):
            full = os.path.join(dp, n)
            try:
                with open(full, encoding="utf-8") as f:
                    if MARKER in f.read():
                        found.append(os.path.relpath(full, folder).replace("\\", "/"))
            except (OSError, UnicodeDecodeError):
                continue
    return sorted(found)


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--format", required=True)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--name", default=None)
    a = ap.parse_args(argv)

    cid = a.id
    if not paths.ID_RE.match(cid):
        die(f"'{cid}' is not a channel id (lowercase letters and digits only, 2 to 24, starting with a letter)")
    dest = f"{paths.channels_dir()}/{cid}"
    if os.path.exists(dest):
        die(f"channels/{cid} exists already")
    fmt_dir = f"{paths.root()}/pipeline/formats/{a.format}" if os.path.isdir(f"{paths.root()}/pipeline/formats/{a.format}") else f"{REPO}/pipeline/formats/{a.format}"
    template = f"{fmt_dir}/template"
    if not os.path.isdir(template):
        die(f"the format '{a.format}' has no template folder ({template}): a new format is engine work, not a new channel (BUILD_SPEC.md 14.7)")
    problems = platform_lib.problems(a.platform)
    if problems:
        die(f"the platform '{a.platform}' is not usable: {problems[0]}; a new platform is engine work, not a new channel (BUILD_SPEC.md 14.7)")
    fj = f"{fmt_dir}/format.json"
    if os.path.isfile(fj):
        try:
            with open(fj, encoding="utf-8-sig") as f:
                supported = json.load(f).get("platforms")
        except (OSError, ValueError):
            supported = None
        if supported and a.platform not in supported:
            die(f"the format '{a.format}' supports {', '.join(supported)}, not '{a.platform}'")

    name = a.name or cid.capitalize()
    shutil.copytree(template, dest, ignore=shutil.ignore_patterns("channel.config.json", "README.md"))
    os.makedirs(f"{dest}/logs", exist_ok=True)
    with open(f"{dest}/ideas.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("")
    config = {}
    cc = f"{template}/channel.config.json"
    if os.path.isfile(cc):
        with open(cc, encoding="utf-8-sig") as f:
            config = json.load(f)
    data = {"id": cid, "name": name, "platform": a.platform, "format": a.format, "language": "en", "enabled": False,
            "daily_quota": 0, "brand": {"display_name": name}}
    defaults = platform_lib.load(a.platform).get("export_defaults") or {}
    if defaults:
        data["export"] = defaults
    if config:
        data["config"] = config
    with open(f"{dest}/channel.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    todo = fill_in_files(dest)
    print(f"new-channel: created channels/{cid}/ ({a.format}, {a.platform}), enabled false")
    if todo:
        print("fill in (each of these says [FILL IN]):")
        for t in todo:
            print(f"  channels/{cid}/{t}")
    print("also made by tools or copied in: styles/paper-cards/tokens.json (bash pipeline/bin/build-tokens), styles/sfx/sfx-map.json "
          "(bash pipeline/bin/build-sfx-map), motion-lib/catalog.json, library/voice/engine.txt (BUILD_SPEC.md 2.5), the brand assets in library/brand/")
    print(f"check: bash pipeline/bin/preflight --channel {cid}   (lists everything missing)")
    print(f"then set \"enabled\": true in channels/{cid}/channel.json and start it: bash run.sh --channel {cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
