#!/usr/bin/env python
"""The protected files guard around every model call (BUILD_SPEC.md section 3, DECISIONS.md 13).

Model calls may not write to ideas.txt, library/, styles/ or exports/. ai() denies the Edit and Write tools on
those paths, and this script is the second net: a snapshot of the protected text files before the call and a
check after it. A changed, removed or added file is restored from the snapshot and reported, so ai() can raise a
code error. exports/ is only listed (renders are too big to copy): a change there is reported, not restored.

Protected set: <root>/ideas.txt; text files (.md, .txt, .json) under <root>/library/ and <repo>/styles/ (skipping
voice recordings, refs/, analysis/, .cache/ and previews/); the names and sizes of the entries in <root>/exports/.

Usage:
  protect.py snapshot --root ROOT --repo REPO --dir DIR     write DIR/manifest.json and copies under DIR/files/
  protect.py check    --root ROOT --repo REPO --dir DIR [--restore]
      prints JSON {changed, added, removed, exports_changed, restored}; exit 0 clean, 1 something changed
Exit 2 on a usage or file error. LF output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

TEXT_EXT = (".md", ".txt", ".json")
SKIP_DIRS = {"refs", "analysis", ".cache", "previews", "voice", "__pycache__", ".git"}
MAX_FILES = 2000


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


def sha1_of(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_files(root: str, repo: str) -> dict[str, str]:
    """relative key -> absolute path, for every protected text file that exists."""
    found: dict[str, str] = {}
    ideas = os.path.join(root, "ideas.txt")
    if os.path.isfile(ideas):
        found["root/ideas.txt"] = ideas
    for label, base in (("root/library", os.path.join(root, "library")), ("repo/styles", os.path.join(repo, "styles"))):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.lower().endswith(TEXT_EXT):
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, base).replace("\\", "/")
                    found[f"{label}/{rel}"] = full
                    if len(found) > MAX_FILES:
                        return found
    return found


def exports_listing(root: str) -> dict[str, int]:
    base = os.path.join(root, "exports")
    out: dict[str, int] = {}
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if os.path.isdir(full):
            total = 0
            for f in os.listdir(full):
                try:
                    total += os.path.getsize(os.path.join(full, f))
                except OSError:
                    pass
            out[name + "/"] = total
        else:
            try:
                out[name] = os.path.getsize(full)
            except OSError:
                out[name] = -1
    return out


def abs_for(key: str, root: str, repo: str) -> str:
    if key == "root/ideas.txt":
        return os.path.join(root, "ideas.txt")
    if key.startswith("root/library/"):
        return os.path.join(root, "library", key[len("root/library/"):])
    if key.startswith("repo/styles/"):
        return os.path.join(repo, "styles", key[len("repo/styles/"):])
    raise ValueError(key)


def cmd_snapshot(args) -> int:
    files = protected_files(args.root, args.repo)
    store = os.path.join(args.dir, "files")
    if os.path.isdir(args.dir):
        shutil.rmtree(args.dir, ignore_errors=True)
    os.makedirs(store, exist_ok=True)
    manifest = {"files": {}, "exports": exports_listing(args.root)}
    for key, full in files.items():
        try:
            manifest["files"][key] = sha1_of(full)
            dest = os.path.join(store, key)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(full, dest)
        except OSError as exc:
            print(f"protect: cannot snapshot {full}: {exc}", file=sys.stderr)
    with open(os.path.join(args.dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps({"files": len(manifest["files"]), "exports": len(manifest["exports"])}))
    return 0


def cmd_check(args) -> int:
    try:
        with open(os.path.join(args.dir, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"protect: no usable snapshot in {args.dir}: {exc}", file=sys.stderr)
        return 2
    before = manifest.get("files", {})
    now_files = protected_files(args.root, args.repo)
    changed, added, removed, restored = [], [], [], []
    for key, digest in before.items():
        full = now_files.get(key)
        if full is None:
            removed.append(key)
        else:
            try:
                if sha1_of(full) != digest:
                    changed.append(key)
            except OSError:
                changed.append(key)
    for key in now_files:
        if key not in before:
            added.append(key)
    exports_changed = exports_listing(args.root) != manifest.get("exports", {})
    if args.restore:
        store = os.path.join(args.dir, "files")
        for key in changed + removed:
            src = os.path.join(store, key)
            dest = abs_for(key, args.root, args.repo)
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                restored.append(key)
            except OSError as exc:
                print(f"protect: cannot restore {dest}: {exc}", file=sys.stderr)
        for key in added:
            try:
                os.remove(now_files[key])
                restored.append(key)
            except OSError as exc:
                print(f"protect: cannot remove {now_files[key]}: {exc}", file=sys.stderr)
    out = {"changed": changed, "added": added, "removed": removed, "exports_changed": exports_changed,
           "restored": restored}
    print(json.dumps(out, ensure_ascii=False))
    return 1 if (changed or added or removed or exports_changed) else 0


def main(argv=None) -> int:
    setup_streams()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "check"):
        sp = sub.add_parser(name)
        sp.add_argument("--root", required=True)
        sp.add_argument("--repo", required=True)
        sp.add_argument("--dir", required=True)
        if name == "check":
            sp.add_argument("--restore", action="store_true")
    args = parser.parse_args(argv)
    for attr in ("root", "repo", "dir"):
        setattr(args, attr, winpath(getattr(args, attr)))
    try:
        return cmd_snapshot(args) if args.cmd == "snapshot" else cmd_check(args)
    except OSError as exc:
        print(f"protect: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
