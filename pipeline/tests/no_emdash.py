#!/usr/bin/env python
"""Scan every tracked and new (not ignored) text file of the repo for an em dash (U+2014).

Skips the user's hooks files (channels/*/library/hooks.txt, never edited to pass a test), vendored code (pipeline/vendor/) and binary extensions.
Prints "path:line" for every hit and exits 1 when there is any; exits 0 when the repo is clean.
Run from anywhere: python pipeline/tests/no_emdash.py
"""
import fnmatch
import os
import subprocess
import sys

SKIP_PREFIXES = ("pipeline/vendor/", "node_modules/", ".hyperframes/")
SKIP_GLOBS = ("channels/*/library/hooks.txt",)
BINARY = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".woff", ".woff2", ".ttf",
          ".otf", ".ico", ".pdf", ".zip", ".pyc")
EM_DASH = bytes([0xE2, 0x80, 0x94])  # U+2014 in UTF-8, built from numbers so this file never contains one


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    repo = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    listing = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=repo,
                             capture_output=True, check=True).stdout
    hits = 0
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8", "replace")
        if path.startswith(SKIP_PREFIXES) or path.lower().endswith(BINARY) or any(fnmatch.fnmatch(path, g) for g in SKIP_GLOBS):
            continue
        try:
            with open(os.path.join(repo, path), "rb") as f:
                data = f.read()
        except OSError:
            continue
        if EM_DASH not in data:
            continue
        for n, line in enumerate(data.split(b"\n"), 1):
            if EM_DASH in line:
                print(f"{path}:{n}")
                hits += 1
    if hits:
        print(f"no_emdash: {hits} em dash(es) found", file=sys.stderr)
        return 1
    print("no_emdash: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
