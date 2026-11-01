#!/usr/bin/env python
"""prompt.py: render a stage's prompt template (pipeline/stages/<stage>/prompt.md).

  python pipeline/lib/prompt.py render TEMPLATE [--out FILE] [--set KEY=VALUE]... [--file KEY=PATH]...
                                        [--allow-missing]

Placeholders are {{KEY}} (capital letters, digits and underscores). --set gives a value, --file inlines a file's
content (a missing file inlines "(none)"). Every value is cleaned of em dashes (errors.undash: no file of this
project may hold one, BUILD_SPEC.md 0.7, and a user file such as account.md may contain some) and of CR
characters. A placeholder with no value is an error (exit 1, the names on stderr) unless --allow-missing, which
leaves it empty. The rendered prompt goes to stdout, or to --out (UTF-8, LF).

Paths may be C:/... or /c/... (both work).
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402

PLACEHOLDER = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def winpath(path: str) -> str:
    """/c/Users/... from Git Bash -> C:/Users/... for Windows Python."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def clean(text: str) -> str:
    return undash(text.replace("\r\n", "\n").replace("\r", "\n"))


def read_file(path: str) -> str:
    try:
        with open(winpath(path), encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return "(none)"


def render(template: str, values: dict, allow_missing: bool) -> tuple[str, list[str]]:
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            return values[key]
        missing.append(key)
        return ""

    return PLACEHOLDER.sub(sub, template), sorted(set(missing))


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("render")
    sp.add_argument("template")
    sp.add_argument("--out")
    sp.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    sp.add_argument("--file", action="append", default=[], metavar="KEY=PATH")
    sp.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    try:
        with open(winpath(args.template), encoding="utf-8-sig") as f:
            template = f.read()
    except OSError as exc:
        print(f"prompt.py: cannot read the template {args.template}: {exc}", file=sys.stderr)
        return 2
    values: dict[str, str] = {}
    for item in args.set:
        key, sep, value = item.partition("=")
        if not sep or not PLACEHOLDER.fullmatch("{{" + key + "}}"):
            print(f"prompt.py: --set wants KEY=VALUE with a capital KEY, got {item[:40]!r}", file=sys.stderr)
            return 1
        values[key] = clean(value)
    for item in args.file:
        key, sep, path = item.partition("=")
        if not sep or not PLACEHOLDER.fullmatch("{{" + key + "}}"):
            print(f"prompt.py: --file wants KEY=PATH with a capital KEY, got {item[:40]!r}", file=sys.stderr)
            return 1
        values[key] = clean(read_file(path)).rstrip("\n")
    text, missing = render(template, values, args.allow_missing)
    if missing and not args.allow_missing:
        print("prompt.py: no value for " + ", ".join(missing), file=sys.stderr)
        return 1
    if not text.endswith("\n"):
        text += "\n"
    if args.out:
        with open(winpath(args.out), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
