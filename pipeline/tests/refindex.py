#!/usr/bin/env python
"""refindex.py: every reference that M18 and M19 must change, found before they start (M17, BUILD_SPEC.md section 12, 14.13).

  python pipeline/tests/refindex.py [--root DIR] [--out DIR]

Deterministic (sorted, no clock): run twice, the files are identical. Read-only on everything but --out (default build/M17).

refindex.tsv, one row per occurrence in a tracked text file:
  file, line, col, match, kind, subject, rooted, certainty, change, context
  subject   path         a path that moves: library/, styles/, motion-lib/, golden/, ideas.txt, runs/, logs/, .locks/ (M18), exports/
                         (the folder stays; its contents are renamed in M19)
            export-name  N.mp4, Ncaptions.txt, Nhook2.mp4 in the forms the code and the docs write them (N, {n}, $n, %d), a history
                         line "| exported N"
            config-key   a config key that moves (14.4): a dotted key (voice.wpm) is exact; a section access (cfg["review"],
                         .get("sfx")) is a candidate, and may be an unrelated dict
            config-read  a direct read of config.json or REELS_CONFIG (M18 goes through config.sh and config.py)
  kind      code (a path built in code), prompt (prompt text a model reads), doc (docs and plain text), test (pipeline/tests),
            fixture (frozen test data under pipeline/tests/fixtures), comment (a comment or docstring line of code), data (a
            tracked data file such as a catalog or a plan), config (.gitignore)
  certainty exact; candidate (a config section access that may be an unrelated dict); absolute (the folder's own path written out,
            in any form: it moves with M18 and has to be rewritten or built by the paths module)
  rooted    yes: the path starts at the folder root (it moves); no: a segment before it says it is something else (fixtures/runs/,
            <id>/logs/): nothing to change
  change    the planned change: paths module call (chpath, paths.ch), channel path in docs, export name (M19), resolved config
            (config.sh, config.py), channel path in a test, fixture rewrite only where a test needs it, new .gitignore, none
Left out of the scan: build/, BUILD_SPEC.md, CHANNELS.md, PLAN.md, DECISIONS.md (the plan and its records), M17's own tools and test in
pipeline/tests/ (they name the old layout on purpose), pipeline/vendor/ (third party), and the binary and very large files.

refindex-data.tsv: the old paths inside data files that git does not track or that are data, in every form (relative, mixed C:/,
posix-drive /c/, backslash, json-backslash), counted per folder bucket, state, path name and form, with the first example.
Run folders, captions files and history lines are the ones M18 rewrites; the rest tells whether the moved folders hold
absolute paths of their own (a sound map with C:/ paths, for instance).
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402

SKIP_FILES = {"BUILD_SPEC.md", "CHANNELS.md", "PLAN.md", "DECISIONS.md"}
# M17's own tools and test: they exist to name the folder's layout (the old one, before M18), and their fixtures spell every form of an old path
SKIP_FILES |= {"pipeline/tests/" + n for n in ("manifestlib.py", "inventory.py", "refindex.py", "make-manifest.py", "check-manifest.py", "risk-scan.py",
                                                "m17-fixture.py", "m17-simulate.py", "m17-baseline.sh", "test-m17.sh", "run-fake.sh", "fakeresults.py",
                                                "make-test-copy.sh")}
SKIP_PREFIX = ("build/", "pipeline/vendor/", "node_modules/")
MAX_BYTES = 8 * 1024 * 1024

PATH_NAMES = ("library", "styles", "motion-lib", "golden", "runs", "logs", ".locks", "exports")
PATH_RE = re.compile(r"(?<![\w.\-])(" + "|".join(re.escape(n) for n in PATH_NAMES) + r")[/\\]")
IDEAS_RE = re.compile(r"(?<![\w.\-])ideas\.txt(?![\w.\-])")
EXPORT_RE = re.compile(
    r"(?:(?<![\w.\-])N|\{n\}|\{number\}|\$\{?n(?:um|umber)?\}?|\$\{?N\}?|%d|%s|\{num\})(?:captions\.txt|hook2\.mp4|\.mp4)(?![\w])"
    r"|exports[/\\](?:N\b|\{\w+\}|\$\{?\w+\}?|<\w+>|%d|%s)"
    r"|\|\s*exported\s+(?:N\b|\d+\b|\$\{?\w+\}?|\{\w+\})")
ROOTISH = re.compile(r"(root|repo|sandbox|base|home|state|ROOT|REPO|SANDBOX|dest|copy|tmp)", re.I)

MOVING_TOPS = [k for k in ml.CHANNEL_KEYS + ml.FORMAT_KEYS]
DOTTED_KEYS = []   # filled from config.json: every top.second of a channel or format key
SECTION_RE = None
READ_RE = re.compile(r"\bREELS_CONFIG\b|(?<![\w.\-/])config\.json\b")

SHEBANG_CODE = re.compile(rb"^#!.*\b(bash|sh|python|node)\b")
CODE_SUFFIX = {".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".bash"}
DOC_SUFFIX = {".md", ".txt", ".rst", ""}
DATA_SUFFIX = {".json", ".html", ".htm", ".css", ".svg", ".tsv", ".csv", ".jsonl", ".yaml", ".yml", ".toml"}


def sanitize(s):
    return s.replace("\u2014", ", ").replace("\t", " ").replace("\r", "").strip()


def tracked_files(root):
    r = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True)
    return sorted(x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x)


def file_kind(path, head):
    """(kind, is_code) of a tracked file by its place and its type"""
    ext = os.path.splitext(path)[1].lower()
    base = os.path.basename(path)
    if path.startswith("pipeline/tests/fixtures/"):
        return "fixture", False
    if path == ".gitignore":
        return "config", False
    if path.startswith("pipeline/tests/"):
        return "test", ext in CODE_SUFFIX or bool(SHEBANG_CODE.match(head))
    if "/_prompts/" in path or "/prompts/" in path or re.match(r"^prompt[\w.\-]*\.md$", base) or base.startswith("prompt"):
        return "prompt", False
    if ext in CODE_SUFFIX or (ext == "" and SHEBANG_CODE.match(head)):
        return "code", True
    if ext in DOC_SUFFIX:
        return "doc", False
    if ext in DATA_SUFFIX:
        return "data", False
    return "data", False


def is_comment_line(stripped, ext):
    if ext in (".py", ".sh", ".bash", ""):
        return stripped.startswith("#")
    if ext in (".js", ".mjs", ".cjs", ".ts"):
        return stripped.startswith(("//", "*", "/*"))
    return False


def rooted_of(line, start):
    """(rooted?) from the segment before the match"""
    before = line[:start]
    if not before or before[-1] not in "/\\":
        return True
    m = re.search(r"([\w.\-${}()]+)[/\\]$", before)
    if not m:
        return True            # "/library/..." or ")/library/": a root of some kind
    seg = m.group(1)
    if seg.endswith(("}", ")")) or seg.startswith("$"):
        return True
    return bool(ROOTISH.search(seg)) and seg not in ("fixtures",)


def change_for(subject, kind, rooted):
    if subject == "config-read":
        return "resolved config (config.sh, config.py)"
    if subject == "config-key":
        return "resolved config (config.sh, config.py)"
    if not rooted:
        return "none (not a root path)"
    if subject == "export-name":
        return "export name (M19)" if kind in ("code", "test", "fixture") else "export name in docs (M19)"
    if kind == "config":
        return "new .gitignore (14.3)"
    if kind == "code":
        return "paths module call (chpath, paths.ch)"
    if kind == "test":
        return "channel path in a test (test edit)"
    if kind == "fixture":
        return "fixture rewrite only where a test needs it"
    if kind == "data":
        return "data file: resolved against the channel folder; rewrite only an absolute path"
    return "channel path in docs"


def expand(line, start):
    m = re.compile(r"[\w.\-/\\${}*<>\[\]:]+").match(line, start)
    return line[start:m.end()][:80] if m else line[start:start + 40]


def scan_text(path, kind, is_code, text, rows, dotted_re, section_re, old):
    ext = os.path.splitext(path)[1].lower()
    in_doc = False
    for ln, line in enumerate(text.split("\n"), 1):
        raw = line.rstrip("\r")
        stripped = raw.strip()
        comment = False
        if is_code:
            if ext == ".py":
                n3 = raw.count('"""') + raw.count("'''")
                if in_doc or stripped.startswith(('"""', "'''")):
                    comment = True
                if n3 % 2 == 1:
                    in_doc = not in_doc
                    comment = True
            if not comment:
                comment = is_comment_line(stripped, ext)
        k = "comment" if comment else kind
        if not stripped:
            continue
        found = []
        spans = []
        for form, rx in old.abs_res:          # the root written out (C:/..., /c/..., backslashes): a path that moves, whatever precedes it
            for m in rx.finditer(raw):
                found.append((m.start(), "path", expand(raw, m.start()), "absolute", True))
                spans.append((m.start(), m.end()))
        for m in PATH_RE.finditer(raw):
            if any(a <= m.start() < b for a, b in spans):
                continue
            found.append((m.start(), "path", expand(raw, m.start()), "exact", rooted_of(raw, m.start())))
        for m in IDEAS_RE.finditer(raw):
            if any(a <= m.start() < b for a, b in spans):
                continue
            found.append((m.start(), "path", "ideas.txt", "exact", rooted_of(raw, m.start())))
        for m in EXPORT_RE.finditer(raw):
            found.append((m.start(), "export-name", m.group(0), "exact", True))
        if dotted_re is not None:
            for m in dotted_re.finditer(raw):
                found.append((m.start(), "config-key", m.group(0), "exact", True))
        if section_re is not None:
            for m in section_re.finditer(raw):
                found.append((m.start(), "config-key", m.group(0), "candidate", True))
        for m in READ_RE.finditer(raw):
            found.append((m.start(), "config-read", m.group(0), "exact", True))
        seen = set()
        for start, subject, match, certainty, rooted in sorted(found, key=lambda t: (t[0], t[1], t[2])):
            key = (start, subject)
            if key in seen:
                continue
            seen.add(key)
            subj_kind = k
            # an export name or a config key inside a comment is still reported, as a comment
            rows.append({"file": path, "line": ln, "col": start + 1, "match": sanitize(match), "kind": subj_kind, "subject": subject,
                         "rooted": "yes" if rooted else "no", "certainty": certainty,
                         "change": ("absolute path: rewrite it or build it with the paths module" if certainty == "absolute" else change_for(subject, subj_kind if subj_kind != "comment" else "doc", rooted)),
                         "context": sanitize(raw)[:110]})


def build_key_regexes(root):
    cfg_path = os.path.join(root, "config.json")
    dotted, tops = [], set()
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
        for top, val in cfg.items():
            dest, ms, _ = ml.key_destination(top if not isinstance(val, dict) else top + "." + next(iter(val), ""))
            if top in ml.CHANNEL_KEYS + ml.FORMAT_KEYS:
                tops.add(top)
                if isinstance(val, dict):
                    for second in val:
                        d2, _, _ = ml.key_destination(top + "." + second)
                        if d2 in ("channel", "format"):
                            dotted.append(top + "." + second)
            elif top == "paths" and isinstance(val, dict):
                for second in val:
                    d2, _, _ = ml.key_destination("paths." + second)
                    if d2 == "channel":
                        dotted.append("paths." + second)
    dotted_re = re.compile(r"(?<![\w.\-])(?:" + "|".join(re.escape(k) for k in sorted(set(dotted), key=lambda s: (-len(s), s))) + r")(?![\w])") if dotted else None
    section_re = None
    if tops:
        alt = "|".join(sorted(tops))
        section_re = re.compile(r"""\[\s*["'](?:%s)["']\s*\]|\.get\(\s*["'](?:%s)["']""" % (alt, alt))
    return dotted_re, section_re


def data_scan(root, inv):
    """Old paths inside text data, in every form: per (bucket, state, name, form): files, occurrences, first example."""
    old = ml.OldPaths(root)
    table = {}
    for r in inv.rows:
        p = r["path"]
        if r["kind"] != "file" or ml.is_engine(p):
            continue
        if not ml.is_text_name(p) or r["size"] > 64 * 1024 * 1024:
            continue
        top = p.split("/", 1)[0]
        bucket = top if top in ("runs", "exports", "logs", "library", "styles", "motion-lib", "golden") else "other"
        if p == "ideas.txt":
            bucket = "ideas.txt"
        raw_output = ml.is_raw_model_output(p)
        text = ml.read_text(os.path.join(root, p))
        if text is None:
            continue
        hits = old.scan(text)
        if not hits:
            continue
        lines_cache = None
        for name, form, start, end, matched in hits:
            key = (bucket + (" (raw model output)" if raw_output else ""), r["git"], name, form)
            e = table.setdefault(key, {"files": set(), "occurrences": 0, "example": None})
            e["files"].add(p)
            e["occurrences"] += 1
            if e["example"] is None:
                if lines_cache is None:
                    lines_cache = text
                ln = lines_cache.count("\n", 0, start) + 1
                ls = lines_cache.rfind("\n", 0, start) + 1
                snippet = sanitize(lines_cache[ls:lines_cache.find("\n", start) if lines_cache.find("\n", start) >= 0 else len(lines_cache)])[:90]
                e["example"] = "%s:%d: %s" % (p, ln, snippet)
    rows = []
    for key in sorted(table):
        e = table[key]
        rows.append({"bucket": key[0], "git": key[1], "name": key[2], "form": key[3], "files": len(e["files"]), "occurrences": e["occurrences"], "example": e["example"]})
    return rows


def main():
    ml.out_stream()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ml.default_root())
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    out = a.out or os.path.join(root, "build", "M17")
    dotted_re, section_re = build_key_regexes(root)
    old_paths = ml.OldPaths(root)
    rows = []
    scanned = skipped = 0
    for path in tracked_files(root):
        if path in SKIP_FILES or path.startswith(SKIP_PREFIX):
            continue
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext in ml.BINARY_SUFFIX:
            skipped += 1
            continue
        try:
            if os.path.getsize(full) > MAX_BYTES:
                skipped += 1
                continue
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            skipped += 1
            continue
        if b"\0" in data[:8192]:
            skipped += 1
            continue
        text = data.decode("utf-8", "replace")
        kind, is_code = file_kind(path, data[:200])
        scan_text(path, kind, is_code, text, rows, dotted_re, section_re, old_paths)
        scanned += 1
    rows.sort(key=lambda r: (r["file"], r["line"], r["col"], r["subject"], r["match"]))
    cols = ["file", "line", "col", "match", "kind", "subject", "rooted", "certainty", "change", "context"]
    ml.write_tsv(os.path.join(out, "refindex.tsv"), cols, rows)
    inv = ml.Inventory(root)
    drows = data_scan(root, inv)
    ml.write_tsv(os.path.join(out, "refindex-data.tsv"), ["bucket", "git", "name", "form", "files", "occurrences", "example"], drows)
    print("refindex: %d occurrences in %d tracked text files (%d skipped), %d data rows -> %s" % (len(rows), scanned, skipped, len(drows), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
