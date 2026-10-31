#!/usr/bin/env python
"""The working tree guard around the fixer call (BUILD_SPEC.md 4.2: the fixer may edit only pipeline/ and
motion-lib/candidates/).

Before the fixer runs, `snapshot` records `git status --porcelain` with a content hash per entry and keeps a copy
of every modified or untracked file outside the allowed paths (the user's own uncommitted work, which must survive
untouched). After the call, `check` lists what changed outside the allowed paths and, with --restore, puts the
fixer's changes back: a tracked file goes back to its snapshot copy (or to HEAD when it was clean), a new untracked
file is deleted, a deleted file is restored from its copy. A pre-existing untracked file that changed in place (a
log being written, the user's own work) is left alone and only reported ("left"). Nothing inside the allowed
paths is touched.

Usage:
  treeguard.py snapshot --repo REPO --dir DIR --allow PATH [--allow PATH ...]
  treeguard.py check    --repo REPO --dir DIR [--restore]
      prints JSON {outside: [...], restored: [...], left: [...], inside: [...]}; exit 0 when nothing changed
      outside, 1 otherwise
Exit 2 on a git or file error. LF output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

MAX_COPY = 20 * 1024 * 1024


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def winpath(path: str) -> str:
    if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == "/":
        return f"{path[1].upper()}:/{path[3:]}"
    return path


def git(repo: str, *args: str) -> str:
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def own_prefix(repo: str, snap_dir: str) -> str | None:
    """The snapshot folder relative to the repo when it lies inside it (then its files are ignored), else None."""
    rel = os.path.relpath(os.path.abspath(snap_dir), os.path.abspath(repo)).replace("\\", "/")
    return None if rel.startswith("..") or rel == "." else rel.rstrip("/") + "/"


def status_entries(repo: str, skip_prefix: str | None = None) -> dict[str, str]:
    """path -> status code, from git status --porcelain -uall (renames count as the new path)."""
    text = git(repo, "status", "--porcelain=v1", "-uall", "-z")
    entries: dict[str, str] = {}
    parts = text.split("\0")
    i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1
            continue
        code, path = item[:2], item[3:]
        if code[0] in ("R", "C"):
            i += 1  # the original path follows as its own NUL-separated field
        path = path.replace("\\", "/")
        if skip_prefix and path.startswith(skip_prefix):
            i += 1
            continue
        entries[path] = code
        i += 1
    return entries


def digest(path: str) -> str | None:
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def inside_allowed(path: str, allowed: list[str]) -> bool:
    for a in allowed:
        a = a.strip("/").replace("\\", "/")
        if path == a or path.startswith(a + "/"):
            return True
    return False


def cmd_snapshot(args) -> int:
    entries = status_entries(args.repo, own_prefix(args.repo, args.dir))
    store = os.path.join(args.dir, "files")
    if os.path.isdir(args.dir):
        shutil.rmtree(args.dir, ignore_errors=True)
    os.makedirs(store, exist_ok=True)
    manifest = {"allowed": args.allow, "entries": {}}
    for path, code in entries.items():
        full = os.path.join(args.repo, path)
        d = digest(full) if os.path.isfile(full) else None
        manifest["entries"][path] = {"code": code, "sha1": d}
        if not inside_allowed(path, args.allow) and d is not None and os.path.getsize(full) <= MAX_COPY:
            dest = os.path.join(store, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(full, dest)
    with open(os.path.join(args.dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps({"entries": len(entries)}))
    return 0


def cmd_check(args) -> int:
    try:
        with open(os.path.join(args.dir, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"treeguard: no usable snapshot in {args.dir}: {exc}", file=sys.stderr)
        return 2
    allowed = manifest.get("allowed", [])
    before = manifest.get("entries", {})
    now = status_entries(args.repo, own_prefix(args.repo, args.dir))
    outside, inside, restored, left = [], [], [], []
    for path, code in now.items():
        full = os.path.join(args.repo, path)
        d = digest(full) if os.path.isfile(full) else None
        prev = before.get(path)
        changed = prev is None or prev.get("sha1") != d or prev.get("code") != code
        if not changed:
            continue
        (inside if inside_allowed(path, allowed) else outside).append(path)
    for path in before:
        if path not in now and not inside_allowed(path, allowed):
            outside.append(path)  # the fixer reverted or committed the user's change, or deleted the file
    if args.restore:
        store = os.path.join(args.dir, "files")
        for path in outside:
            full = os.path.join(args.repo, path)
            prev = before.get(path)
            copy = os.path.join(store, path)
            try:
                if prev is None:
                    # new since the snapshot: an untracked file the fixer created, or a tracked file it modified
                    tracked = subprocess.run(["git", "-C", args.repo, "ls-files", "--error-unmatch", path],
                                             capture_output=True).returncode == 0
                    if tracked:
                        git(args.repo, "checkout", "--", path)
                    elif os.path.isfile(full):
                        os.remove(full)
                    restored.append(path)
                elif prev.get("code") == "??" and os.path.isfile(full):
                    # a pre-existing untracked file that changed during the call (a log being written, the
                    # user's own work): not the fixer's to lose, so it stays as it is and is only reported
                    left.append(path)
                elif os.path.isfile(copy):
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    shutil.copy2(copy, full)
                    restored.append(path)
                elif prev.get("code", "").strip() == "D" and os.path.isfile(full):
                    os.remove(full)
                    restored.append(path)
            except (OSError, subprocess.CalledProcessError) as exc:
                print(f"treeguard: cannot restore {path}: {exc}", file=sys.stderr)
    print(json.dumps({"outside": outside, "restored": restored, "left": left, "inside": inside}, ensure_ascii=False))
    return 1 if outside else 0


def main(argv=None) -> int:
    setup_streams()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("snapshot")
    sp.add_argument("--repo", required=True); sp.add_argument("--dir", required=True)
    sp.add_argument("--allow", action="append", default=[])
    sp = sub.add_parser("check")
    sp.add_argument("--repo", required=True); sp.add_argument("--dir", required=True)
    sp.add_argument("--restore", action="store_true")
    args = parser.parse_args(argv)
    args.repo = winpath(args.repo); args.dir = winpath(args.dir)
    try:
        return cmd_snapshot(args) if args.cmd == "snapshot" else cmd_check(args)
    except subprocess.CalledProcessError as exc:
        print(f"treeguard: git failed: {exc.stderr.decode('utf-8', 'replace') if exc.stderr else exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"treeguard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
