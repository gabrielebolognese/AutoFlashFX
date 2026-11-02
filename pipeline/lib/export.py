#!/usr/bin/env python
"""The export step (BUILD_SPEC.md section 8): number, assemble, move in one step.

The number is assigned at export time: N = the highest number in exports/ plus 1, so dropped or blocked ideas leave
no gaps. Everything is assembled in runs/<id>/export/ first: N.mp4 and Nhook2.mp4 copied from the files named in
14-export/export.json, Ncaptions.txt rendered from export.json in the format of spec section 8 (the HOOKS lines
need N, so only this step can write it; the SOLUTION block comes from export.json's "solution", M12). Then the
folder is moved into exports/N/ with one rename. The lock
.locks/exports (mkdir, stale after --stale seconds) is held from the numbering to the move. The export record in
state.json is updated under state.py's StateLock (runs/<id>/state.lock), from a fresh load each time.

A crash at any point is safe on restart:
  - before the move: the staging folder is rebuilt and N recomputed (nothing is in exports/ yet)
  - after the move but before state.json was updated: exports/N/Ncaptions.txt names this run in its RUN section,
    so the run is recognized as already exported and no second export is made
  - after state.json: the runner only finalizes (idea removal, history line)

Usage:
  export.py run  --run-dir RUN --exports DIR --root ROOT [--stale S] [--wait S] [--crash-at assembled|moved]
                 prints JSON {number, dir, already}; --crash-at exits 99 right after that point (tests only)
  export.py next-number --exports DIR          the number the next export would get
  export.py find --exports DIR --run-id ID     the number of an existing export of that run (exit 3 when none)
  export.py render --run-dir RUN --number N    print the captions file that export.json would give (tests)

Exit codes: 0 ok, 1 usage, 2 missing files or state error, 4 lock timeout, 99 planted crash.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as state_lib  # noqa: E402
import solution as solution_lib  # noqa: E402
from ideas import LockTimeout, QueueLock, winpath  # noqa: E402

RENAME_TRIES = 8
STAGE = "14-export"
EM_DASH = chr(0x2014)  # built from the code point so this file never contains one


class ExportError(Exception):
    """Something needed for the export is missing (exit 2)."""


def numeric_dirs(exports: str) -> list[int]:
    if not os.path.isdir(exports):
        return []
    return sorted(int(n) for n in os.listdir(exports) if n.isdigit() and os.path.isdir(os.path.join(exports, n)))


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
                    return cand.replace("\\", "/").rstrip("/").split("/")[-1]
    return None


def find_export_of(exports: str, run_id: str) -> int | None:
    for n in numeric_dirs(exports):
        cap = os.path.join(exports, str(n), f"{n}captions.txt")
        if os.path.isfile(cap) and run_named_in_captions(cap) == run_id:
            return n
    return None


def write_activity(root: str, text: str) -> None:
    try:
        logs = os.path.join(root, "logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, ".activity"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{int(time.time())}\t{text}\n")
    except OSError:
        pass


def render_captions(m: dict, n: int, run_id: str) -> str:
    """Ncaptions.txt in the format of BUILD_SPEC.md section 8, from the stage's export.json."""
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
    lines += ["", "HOOKS", f'{n}.mp4 uses: "{hooks.get("hook1", "")}"', f'{n}hook2.mp4 uses: "{hooks.get("hook2", "")}"']
    needs = [str(x) for x in (m.get("needs_review") or []) if str(x).strip()]
    if needs:
        lines += ["", "NEEDS REVIEW"] + needs
    lines += ["", "FACTS AND SOURCES"]
    for fact in m.get("facts") or []:
        lines.append(f"- {fact.get('claim', '')}: {fact.get('url', '')} (checked {fact.get('checked', '')})")
    lines += ["", "RUN", f"runs/{run_id}", ""]
    return "\n".join(lines).replace(EM_DASH, ", ")


def load_manifest(run_dir: str) -> tuple[dict, dict]:
    """export.json and the absolute paths of the files it names (reel, hook2)."""
    stage_dir = os.path.join(run_dir, STAGE)
    manifest_path = os.path.join(stage_dir, "export.json")
    try:
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        raise ExportError(f"cannot read {STAGE}/export.json: {exc}") from exc
    for key in ("caption", "hashtags", "keyword", "deliverable", "hooks", "files"):
        if key not in manifest:
            raise ExportError(f"{STAGE}/export.json has no {key}")
    files = manifest.get("files") or {}
    sources = {}
    for key in ("reel", "hook2"):
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


def cmd_run(args) -> int:
    run_dir, exports, root = args.run_dir, args.exports, args.root
    state = state_lib.load(run_dir)
    run_id = state["run_id"]
    number = state["export"].get("number")
    if number is not None and os.path.isdir(os.path.join(exports, str(number))):
        print(json.dumps({"number": number, "dir": f"{exports}/{number}", "already": True}))
        return 0
    manifest, sources = load_manifest(run_dir)
    os.makedirs(exports, exist_ok=True)
    with QueueLock(root, args.stale, args.wait, name="exports"):
        existing = find_export_of(exports, run_id)
        if existing is not None:
            record_export(run_dir, number=existing, intent=existing, assembled=True, moved=True,
                          dir=f"{exports}/{existing}")
            print(json.dumps({"number": existing, "dir": f"{exports}/{existing}", "already": True}))
            return 0
        numbers = numeric_dirs(exports)
        n = (numbers[-1] + 1) if numbers else 1
        staging = os.path.join(run_dir, "export")
        if os.path.isdir(staging):
            shutil.rmtree(staging)
        os.makedirs(staging)
        shutil.copyfile(sources["reel"], os.path.join(staging, f"{n}.mp4"))
        shutil.copyfile(sources["hook2"], os.path.join(staging, f"{n}hook2.mp4"))
        with open(os.path.join(staging, f"{n}captions.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_captions(manifest, n, run_id))
        record_export(run_dir, intent=n, assembled=True, moved=False, dir=None)
        write_activity(root, f"exporting #{n}")
        if args.crash_at == "assembled":
            os._exit(99)
        target = os.path.join(exports, str(n))
        rename_with_retries(staging, target)
        if args.crash_at == "moved":
            os._exit(99)
        record_export(run_dir, number=n, moved=True, dir=f"{exports}/{n}")
    print(json.dumps({"number": n, "dir": f"{exports}/{n}", "already": False}))
    return 0


def cmd_next_number(args) -> int:
    numbers = numeric_dirs(args.exports)
    print((numbers[-1] + 1) if numbers else 1)
    return 0


def cmd_find(args) -> int:
    n = find_export_of(args.exports, args.run_id)
    if n is None:
        return 3
    print(n)
    return 0


def cmd_render(args) -> int:
    state = state_lib.load(args.run_dir)
    manifest, _ = load_manifest(args.run_dir)
    sys.stdout.write(render_captions(manifest, args.number, state["run_id"]))
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("run")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--exports", required=True)
    sp.add_argument("--root", required=True)
    sp.add_argument("--stale", type=float, default=60.0)
    sp.add_argument("--wait", type=float, default=30.0)
    sp.add_argument("--crash-at", choices=("assembled", "moved"))
    sp.set_defaults(func=cmd_run)
    sp = sub.add_parser("next-number")
    sp.add_argument("--exports", required=True)
    sp.set_defaults(func=cmd_next_number)
    sp = sub.add_parser("find")
    sp.add_argument("--exports", required=True)
    sp.add_argument("--run-id", required=True)
    sp.set_defaults(func=cmd_find)
    sp = sub.add_parser("render")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--number", type=int, required=True)
    sp.set_defaults(func=cmd_render)
    args = parser.parse_args(argv)
    for attr in ("run_dir", "exports", "root"):
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
