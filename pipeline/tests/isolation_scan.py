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
Second check (M20, BUILD_SPEC.md 14.5 and 14.12): no channel, brand or style name (flashfx, paper-cards, gabryverse, inkhead, any case)
in a shared stage or shared engine file (SHARED below: the stage library's generic stages, the review, sound, voice and timeline
packages, the runner, the state, config and path modules, the platforms, the schemas, config.json, run.sh). The names are allowed only in the
format's own stages (S1 to S7, S9a to S9c, S10, S14) and in pipeline/formats/<format>/; the same allowlist can let a line through.
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


NAMES = re.compile(r"flashfx|paper-cards|gabryverse|inkhead", re.I)
SHARED_DIRS = ("pipeline/stages/08-voiceover", "pipeline/stages/11-sfx", "pipeline/stages/12-review", "pipeline/stages/13-render",
               "pipeline/stages/timeline", "pipeline/stages/timeline-render", "pipeline/lib/review", "pipeline/lib/sfx", "pipeline/lib/tts",
               "pipeline/lib/timeline", "pipeline/platforms", "pipeline/schemas")
SHARED_FILES = ("run.sh", "config.json", "pipeline/lib/voiceover.py", "pipeline/lib/finalrender.py", "pipeline/lib/runner.sh", "pipeline/lib/state.py",
                "pipeline/lib/state.sh", "pipeline/lib/status.sh", "pipeline/lib/history.sh", "pipeline/lib/stage.sh", "pipeline/lib/session.sh",
                "pipeline/lib/heavy.sh", "pipeline/lib/quota.py", "pipeline/lib/export.py", "pipeline/lib/export.sh", "pipeline/lib/platform_lib.py",
                "pipeline/lib/formats.py", "pipeline/lib/config.py", "pipeline/lib/config.sh", "pipeline/lib/paths.py", "pipeline/lib/paths.sh",
                "pipeline/lib/newchannel.py", "pipeline/lib/logcheck.py", "pipeline/lib/ai.sh", "pipeline/lib/limits.py", "pipeline/lib/limits.sh",
                "pipeline/lib/common.sh", "pipeline/lib/log.sh", "pipeline/lib/ideas.py", "pipeline/lib/ideas.sh", "pipeline/lib/protect.py",
                "pipeline/lib/errors.py", "pipeline/lib/errors.sh", "pipeline/lib/review.sh", "pipeline/lib/preflight.sh", "pipeline/lib/dummy.sh",
                "pipeline/lib/model_choice.py", "pipeline/lib/migrate.py", "pipeline/lib/prompt.py", "pipeline/bin/preflight", "pipeline/bin/doctor",
                "pipeline/bin/runner-status", "pipeline/bin/new-channel", "pipeline/bin/review-cycle", "pipeline/bin/migrate-channels",
                "pipeline/bin/add-idea.sh", "pipeline/bin/vendor-run")
TEXT_EXT = (".sh", ".py", ".md", ".json", ".txt", ".html", ".css", ".js")


def shared_files(root):
    out = []
    for d in SHARED_DIRS:
        for dp, dn, fn in os.walk(os.path.join(root, d)):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for n in fn:
                rel = os.path.relpath(os.path.join(dp, n), root).replace("\\", "/")
                if os.path.splitext(n)[1].lower() in TEXT_EXT or "." not in n:
                    out.append(rel)
    out += [f for f in SHARED_FILES if os.path.isfile(os.path.join(root, f))]
    return sorted(set(out))


def name_violations(root):
    """Every line of a shared file that names a channel, a brand or a style (the allowlist can let a line through)."""
    allow = load_allow(root)
    found, used = [], set()
    for rel in shared_files(root):
        try:
            text = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n, line in enumerate(text.split(chr(10)), 1):
            if not NAMES.search(line):
                continue
            if any(fnmatch.fnmatch(rel, g) and rx.search(line) and not used.add(ln) for g, rx, why, ln in allow):
                continue
            found.append((rel, n, line.strip()[:160]))
    return found, used


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
    named, used_names = name_violations(os.path.abspath(a.root))
    used |= used_names
    for rel, n, text in found:
        print("FAIL %s:%d: a literal path to channel data outside the paths module: %s" % (rel, n, text))
    for rel, n, text in named:
        print("FAIL %s:%d: a channel, brand or style name in a shared stage (BUILD_SPEC.md 14.5, 14.12): %s" % (rel, n, text))
    found = found + named
    unused = [e for e in allow if e[3] not in used]
    if a.list:
        print("allowlist: %d entries, %d used" % (len(allow), len(used)))
        for g, rx, why, ln in unused:
            print("  unused entry line %d: %s | %s" % (ln, g, rx.pattern))
    print("isolation_scan: %d violation(s) (%d of them names), %d allowlist entr%s" % (len(found), len(named), len(allow), "y" if len(allow) == 1 else "ies"))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
