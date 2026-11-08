#!/usr/bin/env python
"""m17-simulate.py: executes a move manifest on a FIXTURE folder, naively, to prove that the manifest means what check-manifest.py --after checks (M17).

  python pipeline/tests/m17-simulate.py <fixture-root> <manifest.tsv> [--only M18|M19]

This is not migrate-channels (M18 builds that, with the dry run, the undo, the retries and the verification). It is the shortest executor of the
manifest's semantics, used by test-m17.sh on the fixture of m17-fixture.py; never run it on the real folder.
Per line, in order: stays does nothing; git-mv runs `git mv`; fs-mv and rename-in-place rename; a rewrite replaces the old paths (the
channel prefix goes in, in every form) or the export names. A path under a folder that an earlier line moved is translated first.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402

CH = ml.CHANNEL


def translate(path, moved):
    best = None
    for old, new in moved:
        if path == old or path.startswith(old + "/"):
            if best is None or len(old) > len(best[0]):
                best = (old, new)
    return path if best is None else best[1] + path[len(best[0]):]


def rewrite_old_paths(text, old_paths):
    hits = old_paths.scan(text)
    out, pos = [], 0
    for name, form, start, end, matched in hits:
        if start < pos:
            continue
        out.append(text[pos:start])
        sep = {"backslash": "\\", "json-backslash": "\\\\"}.get(form, "/")
        head = matched[: len(matched) - len(name)] if len(matched) > len(name) else ""   # the absolute root and its separator, or nothing
        out.append(head + "channels" + sep + CH + sep + name)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    root = os.path.abspath(sys.argv[1])
    manifest = sys.argv[2]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    rows = ml.read_tsv(manifest)[1]
    old_paths = ml.OldPaths(root)
    moved = []
    for r in rows:
        if only and r["ms"] != only:
            continue
        if r["method"] == "stays":
            continue
        src = translate(r["old"], moved)
        dst = r["new"] if r["method"] != "rewrite" else None
        if r["scope"] == "inner" and r["method"] == "rename-in-place":
            dst = translate(r["new"], moved)
        if r["method"] in ("git-mv", "fs-mv", "rename-in-place"):
            os.makedirs(os.path.dirname(os.path.join(root, dst)) or root, exist_ok=True)
            if r["method"] == "git-mv":
                subprocess.run(["git", "-C", root, "mv", src, dst], check=True, capture_output=True)
            else:
                os.rename(os.path.join(root, src), os.path.join(root, dst))
            if r["scope"] == "top":
                moved.append((r["old"], r["new"]))
            continue
        # rewrite
        target = translate(r["new"], moved) if r["ms"] == "M19" else src
        full = os.path.join(root, target)
        files = [os.path.join(root, f["path"]) for f in ml.Inventory(root).files_under(target)] if os.path.isdir(full) else [full]
        for f in files:
            rel = ml.posix(os.path.relpath(f, root))
            if not ml.is_text_name(rel) or ml.is_raw_model_output(rel):
                continue
            text = ml.read_text(f)
            if text is None:
                continue
            if r["check"] == "no-old-path-left":
                new = rewrite_old_paths(text, old_paths)
            elif r["check"] == "export-names":
                new = re.sub(r"^([0-9]+)((?:hook2)?\.mp4 uses:)", lambda m: "%s-%s%s" % (CH, m.group(1), m.group(2)), text, flags=re.M)
                new = re.sub(r"^([0-9]+)(hook2\.mp4 uses:)", lambda m: "%s-%s%s" % (CH, m.group(1), m.group(2)), new, flags=re.M)
                new = re.sub(r"\| exported ([0-9]+) *$", lambda m: "| exported %s-%s" % (CH, m.group(1)), new, flags=re.M)
            else:
                continue
            if new != text:
                with open(f, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new)
    print("simulate: %d lines executed" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
