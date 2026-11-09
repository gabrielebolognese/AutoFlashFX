#!/usr/bin/env python
"""The export step (BUILD_SPEC.md section 8, from M19): number, assemble, move in one step.

Every export gets its own folder exports/<id>-N/ (<id> is the channel, N counts that channel's exports). The number is
assigned at export time: N = 1 + the highest number of this channel found in exports/ (folders named <id>-<number>) and in
the channel's history.txt (lines "exported <id>-<number>"), so dropped or blocked ideas leave no gaps and deleting a posted
folder never reuses its number. Everything is assembled in runs/<run>/export/ first (an input.json that the platform's
exporter left there stays): <id>-N.mp4 (and <id>-Nhook2.mp4 on a platform that has that clip) copied from the files named in
14-export/export.json, <id>-Ncaptions.txt rendered by the platform's exporter (pipeline/platforms/<platform>/, through
pipeline/lib/platform_lib.py: the HOOKS lines need the name, so only this step can write them). Then the folder is moved
into exports/<id>-N/ with one rename. The lock .locks/exports (mkdir, stale after --stale seconds) is global: the
numbering of every channel shares one exports/ folder. The export record in state.json is updated under state.py's
StateLock (runs/<id>/state.lock), from a fresh load each time.

A crash at any point is safe on restart:
  - before the move: the staging folder is rebuilt and N recomputed (nothing is in exports/ yet)
  - after the move but before state.json was updated: exports/<id>-N/<id>-Ncaptions.txt names this run in its RUN section,
    so the run is recognized as already exported and no second export is made
  - after state.json: the runner only finalizes (idea removal, history line)

Usage:
  export.py run  --run-dir RUN --exports DIR --root ROOT [--channel ID] [--history FILE] [--stale S] [--wait S]
                 [--crash-at assembled|moved]
                 prints JSON {number, name, dir, already}; --crash-at exits 99 right after that point (tests only)
  export.py next-number --exports DIR [--channel ID] [--history FILE]   the number the channel's next export would get
  export.py find --exports DIR --run-id ID [--channel ID]               the number of an existing export of that run (exit 3 when none)
  export.py render --run-dir RUN --number N [--channel ID]              print the captions file that export.json would give (tests)
--channel defaults to REELS_CHANNEL; --history to the channel's logs/history.txt.

Exit codes: 0 ok, 1 usage, 2 missing files or state error, 4 lock timeout, 99 planted crash.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
import platform_lib  # noqa: E402
import state as state_lib  # noqa: E402
from ideas import LockTimeout, QueueLock, winpath  # noqa: E402

RENAME_TRIES = 8
STAGE = "14-export"
KEEP_IN_STAGING = ("input.json",)   # what a platform's exporter leaves in runs/<run>/export/ for this step
HISTORY_LINE = r"\| exported %s-([0-9]+)\s*$"


class ExportError(Exception):
    """Something needed for the export is missing (exit 2)."""


def export_numbers(exports: str, channel: str, history: str | None = None) -> list[int]:
    """The numbers this channel has used: the folders exports/<id>-<number> and the history lines "exported <id>-<number>"."""
    found = set()
    if os.path.isdir(exports):
        pat = re.compile("^%s-([0-9]+)$" % re.escape(channel))
        for name in os.listdir(exports):
            m = pat.match(name)
            if m and os.path.isdir(os.path.join(exports, name)):
                found.add(int(m.group(1)))
    if history and os.path.isfile(history):
        pat = re.compile(HISTORY_LINE % re.escape(channel))
        try:
            with open(history, encoding="utf-8-sig") as f:
                for line in f:
                    m = pat.search(line)
                    if m:
                        found.add(int(m.group(1)))
        except OSError:
            pass
    return sorted(found)


def next_number(exports: str, channel: str, history: str | None = None) -> int:
    nums = export_numbers(exports, channel, history)
    return (nums[-1] + 1) if nums else 1


def run_named_in_captions(path: str) -> str | None:
    """The run folder named in the RUN section of a captions file (the last section of the spec format)."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = [ln.strip() for ln in f.read().replace("\r\n", "\n").split("\n")]
    except OSError:
        return None
    for i, line in enumerate(lines):
        if line == "RUN":
            for cand in lines[i + 1:]:
                if cand:
                    return cand.replace(chr(92), "/").rstrip("/").split("/")[-1]
    return None


def find_export_of(exports: str, channel: str, run_id: str) -> int | None:
    for n in export_numbers(exports, channel):
        cap = os.path.join(exports, f"{channel}-{n}", f"{channel}-{n}captions.txt")
        if os.path.isfile(cap) and run_named_in_captions(cap) == run_id:
            return n
    return None


def write_activity(root: str, text: str) -> None:
    try:
        logs = os.path.join(root, paths.LOGS_DIR)
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, ".activity"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{int(time.time())}\t{text}\n")
    except OSError:
        pass


def platform_of(channel: str) -> tuple[dict, object]:
    """The channel's platform.json and its exporter module."""
    pid = platform_lib.of_channel(channel) or "instagram-reels"
    try:
        return platform_lib.load(pid), platform_lib.exporter(pid)
    except platform_lib.PlatformError as exc:
        raise ExportError(str(exc)) from exc


def render_captions(m: dict, n: int, run_id: str, channel: str) -> str:
    """<id>-Ncaptions.txt in the format of the channel's platform (BUILD_SPEC.md section 8), from the stage's export.json."""
    _plat, exporter = platform_of(channel)
    return exporter.render_captions(m, channel, n, run_id)


def load_manifest(run_dir: str, channel: str) -> tuple[dict, dict]:
    """export.json and the absolute paths of the files it names (reel, and hook2 on a platform that has the clip)."""
    plat, _ = platform_of(channel)
    stage_dir = os.path.join(run_dir, STAGE)
    manifest_path = os.path.join(stage_dir, "export.json")
    try:
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        raise ExportError(f"cannot read {STAGE}/export.json: {exc}") from exc
    for key in plat.get("manifest_required") or ["caption", "hashtags", "keyword", "deliverable", "hooks", "files"]:
        if key not in manifest:
            raise ExportError(f"{STAGE}/export.json has no {key}")
    files = manifest.get("files") or {}
    sources = {}
    for key in ("reel", "hook2") if plat.get("hook2") else ("reel",):
        rel = files.get(key)
        if not rel:
            raise ExportError(f"{STAGE}/export.json has no files.{key}")
        full = rel if os.path.isabs(rel) else os.path.join(stage_dir, rel)
        if not os.path.isfile(full):
            raise ExportError(f"{STAGE}: file for {key} is missing: {rel}")
        sources[key] = full
    return manifest, sources


def record_export(run_dir: str, **fields) -> None:
    """Update the export record in state.json under the state lock, from a fresh load, so that no other writer's
    change is lost (the same rule as every state.py command)."""
    with state_lib.StateLock(run_dir):
        state = state_lib.load(run_dir)
        state["export"].update(fields)
        state_lib.save(run_dir, state)


def rename_with_retries(src: str, dst: str) -> None:
    for attempt in range(RENAME_TRIES):
        try:
            os.rename(src, dst)
            return
        except PermissionError:
            if attempt == RENAME_TRIES - 1:
                raise
            time.sleep(0.25)


def clear_staging(staging: str) -> None:
    """Empty runs/<run>/export/ but keep what a platform's exporter put there for this step (input.json)."""
    if not os.path.isdir(staging):
        os.makedirs(staging)
        return
    for name in os.listdir(staging):
        if name in KEEP_IN_STAGING:
            continue
        full = os.path.join(staging, name)
        shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)


def history_of(args) -> str | None:
    if args.history:
        return args.history
    root = args.root or paths.channel_root(args.channel)
    return os.path.join(root, paths.LOGS_DIR, "history.txt") if root else None


def cmd_run(args) -> int:
    run_dir, exports, root, channel = args.run_dir, args.exports, args.root, args.channel
    state = state_lib.load(run_dir)
    run_id = state["run_id"]
    history = history_of(args)
    number = state["export"].get("number")
    if number is not None and os.path.isdir(os.path.join(exports, f"{channel}-{number}")):
        print(json.dumps({"number": number, "name": f"{channel}-{number}", "dir": f"{exports}/{channel}-{number}", "already": True}))
        return 0
    plat, _ = platform_of(channel)
    manifest, sources = load_manifest(run_dir, channel)
    os.makedirs(exports, exist_ok=True)
    with QueueLock(root, args.stale, args.wait, name="exports", locks_dir=args.locks_dir):
        existing = find_export_of(exports, channel, run_id)
        if existing is not None:
            record_export(run_dir, number=existing, intent=existing, assembled=True, moved=True,
                          dir=f"{exports}/{channel}-{existing}")
            print(json.dumps({"number": existing, "name": f"{channel}-{existing}", "dir": f"{exports}/{channel}-{existing}", "already": True}))
            return 0
        n = next_number(exports, channel, history)
        name = f"{channel}-{n}"
        staging = os.path.join(run_dir, "export")
        clear_staging(staging)
        shutil.copyfile(sources["reel"], os.path.join(staging, f"{name}.mp4"))
        if plat.get("hook2"):
            shutil.copyfile(sources["hook2"], os.path.join(staging, f"{name}hook2.mp4"))
        with open(os.path.join(staging, f"{name}captions.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_captions(manifest, n, run_id, channel))
        for keep in KEEP_IN_STAGING:   # input.json is not part of the export: it stays in the run folder
            kept = os.path.join(staging, keep)
            if os.path.isfile(kept):
                shutil.move(kept, os.path.join(run_dir, f"export-{keep}"))
        record_export(run_dir, intent=n, assembled=True, moved=False, dir=None)
        write_activity(root, f"exporting {name}")
        if args.crash_at == "assembled":
            os._exit(99)
        target = os.path.join(exports, name)
        rename_with_retries(staging, target)
        if args.crash_at == "moved":
            os._exit(99)
        record_export(run_dir, number=n, moved=True, dir=f"{exports}/{name}")
    print(json.dumps({"number": n, "name": name, "dir": f"{exports}/{name}", "already": False}))
    return 0


def cmd_next_number(args) -> int:
    print(next_number(args.exports, args.channel, history_of(args)))
    return 0


def cmd_find(args) -> int:
    n = find_export_of(args.exports, args.channel, args.run_id)
    if n is None:
        return 3
    print(n)
    return 0


def cmd_render(args) -> int:
    state = state_lib.load(args.run_dir)
    manifest, _ = load_manifest(args.run_dir, args.channel)
    sys.stdout.write(render_captions(manifest, args.number, state["run_id"], args.channel))
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    default_channel = paths.channel_id() or None

    def channel_arg(sp):
        sp.add_argument("--channel", default=default_channel, help="the channel id (default REELS_CHANNEL)")

    sp = sub.add_parser("run")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--exports", required=True)
    sp.add_argument("--root", required=True, help="the channel folder (its logs/ get the activity line and the history)")
    channel_arg(sp)
    sp.add_argument("--history", default=None, help="the channel's history.txt (default: logs/history.txt of --root)")
    sp.add_argument("--locks-dir", default=None, help="folder of the exports lock (the global locks: numbering is shared)")
    sp.add_argument("--stale", type=float, default=60.0)
    sp.add_argument("--wait", type=float, default=30.0)
    sp.add_argument("--crash-at", choices=("assembled", "moved"))
    sp.set_defaults(func=cmd_run)
    sp = sub.add_parser("next-number")
    sp.add_argument("--exports", required=True)
    channel_arg(sp)
    sp.add_argument("--history", default=None)
    sp.add_argument("--root", default=None)
    sp.set_defaults(func=cmd_next_number)
    sp = sub.add_parser("find")
    sp.add_argument("--exports", required=True)
    sp.add_argument("--run-id", required=True)
    channel_arg(sp)
    sp.set_defaults(func=cmd_find)
    sp = sub.add_parser("render")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--number", type=int, required=True)
    channel_arg(sp)
    sp.set_defaults(func=cmd_render)
    args = parser.parse_args(argv)
    if not args.channel:
        print("export.py: no channel: pass --channel <id> or set REELS_CHANNEL", file=sys.stderr)
        return 1
    for attr in ("run_dir", "exports", "root", "history"):
        if getattr(args, attr, None):
            setattr(args, attr, winpath(getattr(args, attr)).replace("\\", "/"))
    try:
        return args.func(args)
    except LockTimeout as exc:
        print(f"export.py: {exc}", file=sys.stderr)
        return 4
    except (ExportError, state_lib.StateError, OSError) as exc:
        print(f"export.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
