#!/usr/bin/env python
"""The protected files guard around every model call (BUILD_SPEC.md section 3, DECISIONS.md 13).

Model calls may not write to any channel's ideas.txt, library/ or styles/, or to exports/. ai() denies the Edit and
Write tools on those paths, and this script is the second net: a snapshot of the protected text files before the call and a
check after it. A changed, removed or added file is restored from the snapshot and reported, so ai() can raise a
code error. exports/ is only listed (renders are too big to copy): a change there is reported, not restored.

Protected set, for every channel under <root>/channels/: ideas.txt; text files (.md, .txt, .json) under library/ and
styles/ (skipping voice recordings, refs/, analysis/, .cache/ and previews/); and the names and sizes of the entries
in <root>/exports/. --repo is accepted and ignored (the styles are channel data since M18).

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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402  (the names inside a channel folder)

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


def protected_files(root: str, repo: str = "") -> dict[str, str]:
    """root-relative key -> absolute path, for every protected text file of every channel that exists:
    channels/<id>/ideas.txt, channels/<id>/library/** and channels/<id>/styles/** (BUILD_SPEC.md 14.4)."""
    found: dict[str, str] = {}
    chans = os.path.join(root, "channels")
    try:
        ids = sorted(d for d in os.listdir(chans) if os.path.isdir(os.path.join(chans, d)))
    except OSError:
        return found
    for cid in ids:
        ideas = os.path.join(chans, cid, paths.IDEAS_FILE)
        if os.path.isfile(ideas):
            found[f"channels/{cid}/{paths.IDEAS_FILE}"] = ideas
        for sub in (paths.LIBRARY_DIR, paths.STYLES_DIR):
            base = os.path.join(chans, cid, sub)
            if not os.path.isdir(base):
                continue
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for name in filenames:
                    if name.lower().endswith(TEXT_EXT):
                        full = os.path.join(dirpath, name)
                        rel = os.path.relpath(full, base).replace("\\", "/")
                        found[f"channels/{cid}/{sub}/{rel}"] = full
                        if len(found) > MAX_FILES:
                            return found
    return found


def exports_listing(root: str) -> dict[str, int]:
    base = os.path.join(root, paths.EXPORTS_DIR)
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


def abs_for(key: str, root: str, repo: str = "") -> str:
    if not key.startswith("channels/") or ".." in key.split("/"):
        raise ValueError(key)
    return os.path.join(root, key)


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
