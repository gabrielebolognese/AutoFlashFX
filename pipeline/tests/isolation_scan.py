#!/usr/bin/env python
"""isolation_scan.py: test-isolation.sh part 1 (BUILD_SPEC.md 14.5), the static check.

  python pipeline/tests/isolation_scan.py [--root DIR] [--list]

Fails (exit 1) on any literal path to channel data (library/, styles/, motion-lib/, golden/, ideas.txt, runs/, logs/, exports/,
.locks/) in the engine's code outside pipeline/lib/paths.sh and paths.py: a variable followed by one of those folders, a quoted
folder name used as a path part, a path string that starts with one. It scans pipeline/ (without tests/, vendor/, knowledge/,
formats/*/template/), run.sh and tools/: shell and Python code, scripts without an extension. Markdown, JSON, HTML and CSS are text
for people and models (prompts, schemas, docs), not path building, and are not scanned.

A line is not a violation when:
  - it is a comment, or a line inside a docstring or a heredoc of text (the scanner skips triple-quoted strings)
  - it is a message for a person: it starts with say, note, echo, printf, print, warn, bad, ok, raise, flag_once, run_flag,
    stage_fail, stage_drop, stage_note, parser help text, or it is a continuation of such a call (a string argument)
  - an entry of pipeline/tests/isolation-allowlist.txt matches it. One entry per line: `glob | regex | reason`; the glob matches the file's
    path under the root, the regex the line, the reason says why the literal is fine (a comment about the layout, a label in a
    message, a legacy default that the paths module overrides, a FlashFX name until M20, 14.5). `#` starts a comment.
`--list` prints every violation with its file and line and the entry count of the allowlist.
"""
import argparse
import fnmatch
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

FOLDERS = r"(?:library|styles|motion-lib|golden|runs|logs|exports|\.locks)"
VAR_THEN = re.compile(r"[\w}\)]/" + FOLDERS + r"(?:/|\b)")              # $REELS_ROOT/library, "$x"/runs, root}/logs
QUOTED_PART = re.compile(r"""(?:^|[\s,(\[=])(['"])(?:""" + FOLDERS[3:-1] + r"""|ideas\.txt)\1""")   # os.path.join(root, "library")
STRING_START = re.compile(r"""(['"])(?:""" + FOLDERS[3:-1] + r""")/""")                            # "runs/$id"
IDEAS = re.compile(r"""(?<![\w.-])ideas\.txt(?![\w.-])""")
MESSAGE = re.compile(r"""^\s*(?:say|note|echo|printf|print|warn|bad|ok|raise|flag_once|run_flag|stage_fail|stage_drop|stage_note|"""
                     r"""lines\.append|lines\s*\+=|problems\.append|rep\.(?:err|warn)|out\(|log\(|die|help=|sp\.add_argument|ap\.add_argument|"""
                     r"""p\.add_argument|parser\.add_argument|description=)""")
SKIP_DIRS = ("pipeline/tests/", "pipeline/vendor/", "pipeline/knowledge/", "pipeline/lib/__pycache__/")
OWN = ("pipeline/lib/paths.sh", "pipeline/lib/paths.py")


def code_files(root):
    out = []
    for base in ("pipeline", "tools"):
        for dp, dn, fn in os.walk(os.path.join(root, base)):
            dn[:] = [d for d in dn if d not in ("__pycache__", "node_modules")]
            for n in fn:
                full = os.path.join(dp, n)
                rel = os.path.relpath(full, root).replace("\\", "/")
                if any(rel.startswith(s) for s in SKIP_DIRS) or rel in OWN or "/template/" in rel:
                    continue
                ext = os.path.splitext(n)[1].lower()
                if ext in (".sh", ".py") or (ext == "" and "/bin/" in "/" + rel):
                    out.append(rel)
    if os.path.isfile(os.path.join(root, "run.sh")):
        out.append("run.sh")
    return sorted(out)


def load_allow(root):
    path = os.path.join(root, "pipeline", "tests", "isolation-allowlist.txt")
    entries = []
    if not os.path.exists(path):
        return entries
    for ln, line in enumerate(open(path, encoding="utf-8").read().split("\n"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split(" | ", 2)]
        if len(parts) != 3 or not parts[2]:
            raise SystemExit("isolation-allowlist.txt line %d: want `glob | regex | reason` with a reason" % ln)
        entries.append((parts[0], re.compile(parts[1]), parts[2], ln))
    return entries


def violations(root):
    allow = load_allow(root)
    used = set()
    found = []
    for rel in code_files(root):
        try:
            text = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        is_py = rel.endswith(".py")
        in_doc = False
        in_msg_call = 0
        for n, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if is_py:
                quotes = stripped.count('"""') + stripped.count("'''")
                if in_doc:
                    if quotes % 2 == 1:
                        in_doc = False
                    continue
                if quotes % 2 == 1:
                    in_doc = True
                    continue
                if quotes >= 2:
                    continue
            if not stripped or stripped.startswith("#"):
                continue
            code = re.sub(r"\s#\s.*$", "", line) if not is_py else re.sub(r"\s#\s.*$", "", line)
            hit = VAR_THEN.search(code) or QUOTED_PART.search(code) or STRING_START.search(code) or IDEAS.search(code)
            if not hit:
                continue
            if MESSAGE.match(code) or in_msg_call:
                # a call that continues over several lines (an open parenthesis or a trailing backslash) stays a message
                in_msg_call = 1 if code.rstrip().endswith(("\\", "(", ",")) else 0
                continue
            ok = False
            for glob, rx, why, ln in allow:
                if fnmatch.fnmatch(rel, glob) and rx.search(code):
                    used.add(ln)
                    ok = True
                    break
            if not ok:
                found.append((rel, n, stripped[:160]))
    return found, allow, used


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    found, allow, used = violations(os.path.abspath(a.root))
    for rel, n, text in found:
        print("FAIL %s:%d: a literal path to channel data outside the paths module: %s" % (rel, n, text))
    unused = [e for e in allow if e[3] not in used]
    if a.list:
        print("allowlist: %d entries, %d used" % (len(allow), len(used)))
        for g, rx, why, ln in unused:
            print("  unused entry line %d: %s | %s" % (ln, g, rx.pattern))
    print("isolation_scan: %d violation(s), %d allowlist entr%s" % (len(found), len(allow), "y" if len(allow) == 1 else "ies"))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
