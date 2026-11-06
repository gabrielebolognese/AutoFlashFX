#!/usr/bin/env python
"""The idea queue: parse, read and rewrite ideas.txt (BUILD_SPEC.md section 2.1).

An idea is any text between { and }. It can span several lines. Text outside braces is a note and is ignored.
No nested braces: a second { before the } restarts the block (the earlier, unclosed brace becomes a note) and a
warning is printed. The file is read as UTF-8 (a BOM is fine) with LF or CRLF endings; a file that used CRLF is
written back with CRLF. The id of an idea is the first 12 hex characters of the sha1 of its normalized text
(NFC, whitespace collapsed, trimmed), so it survives edits to other lines.

The label [important] (any case) at the start or the end of a block marks the idea important (DECISIONS.md 333):
its escalations may use fable. The label is not part of the idea: the text and the id are computed without it, the
file keeps it, and the JSON rows carry "important": true.

Every write takes the lock directory <root>/.locks/ideas (mkdir is atomic; a lock older than --stale seconds is
removed and logged) and replaces the file atomically (temp file in the same folder, then os.replace, retried a few
times because OneDrive briefly holds handles).

Usage (paths may be C:/... or /c/..., both work):
  ideas.py list   --file ideas.txt [--plain]
  ideas.py first  --file ideas.txt [--plain]                exit 3 when the queue is empty
  ideas.py count  --file ideas.txt
  ideas.py id                                               text on stdin, prints its id
  ideas.py append --file ideas.txt --root <root> [--source NAME] [--plain]
          text on stdin: every {block} is appended (text without braces is one idea); each addition is recorded in
          <root>/logs/.new-ideas so the runner can print its NEW line
  ideas.py remove --file ideas.txt --root <root> --id ID [--text-stdin] [--plain]
          removes the idea with that id. When no idea has that id and --text-stdin gives the text the runner started
          with, the closest idea is removed only when its similarity is at least 0.9; otherwise nothing changes.

Exit codes: 0 ok, 1 usage, 2 file error, 3 not found (or empty queue), 4 lock timeout.
JSON on stdout unless --plain. Warnings and log lines on stderr.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_choice import split_label  # noqa: E402
import paths  # noqa: E402

ID_LENGTH = 12
MIN_SIMILARITY = 0.9
DEFAULT_STALE_S = 60.0
DEFAULT_WAIT_S = 30.0
REPLACE_TRIES = 5


class QueueError(Exception):
    """A problem with the queue file (exit 2)."""


class LockTimeout(Exception):
    """The lock stayed busy for too long (exit 4)."""


def winpath(path: str) -> str:
    """Accept /c/Users/... from Git Bash as well as C:/Users/...; Windows Python needs the latter."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path)
    if m and os.name == "nt":
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return path


def warn(text: str) -> None:
    print(f"ideas.py: warning: {text}", file=sys.stderr)


def log_line(root: str, tag: str, text: str) -> None:
    """Append a line in the runner's format to <root>/logs/runner.log and echo it on stderr."""
    line = f"[{datetime.now():%H:%M}] {tag:<6} {text}"
    print(line, file=sys.stderr)
    try:
        logs = os.path.join(root, paths.LOGS_DIR)
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, "runner.log"), "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
    except OSError:
        pass


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())


def idea_id(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()[:ID_LENGTH]


def read_queue(path: str) -> tuple[str, str]:
    """Return (text with LF endings, the newline style the file used)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return "", "\n"
    except OSError as exc:
        raise QueueError(f"cannot read {path}: {exc}") from exc
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        warn(f"{os.path.basename(path)} is not valid UTF-8; read as cp1252")
        text = data.decode("cp1252", errors="replace")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n").replace("\r", "\n"), newline


def parse(text: str) -> tuple[list[dict], list[str]]:
    """Find every {block}. Returns the blocks (start, end, raw, text, id) and the warnings."""
    blocks: list[dict] = []
    warnings: list[str] = []
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if start is not None:
                warnings.append(f"unclosed brace at offset {start} ignored: a new block opens at offset {i}")
            start = i
        elif ch == "}" and start is not None:
            raw = text[start + 1:i]
            clean, important = split_label(raw)
            norm = normalize(clean)
            if norm:
                blocks.append({"start": start, "end": i + 1, "raw": raw.strip(), "text": norm, "id": idea_id(clean),
                               "important": important})
            else:
                warnings.append(f"empty braces at offset {start} ignored")
            start = None
    if start is not None:
        warnings.append(f"unclosed brace at offset {start} ignored: the file ends before its closing brace")
    return blocks, warnings


def load(path: str) -> tuple[str, str, list[dict]]:
    text, newline = read_queue(path)
    blocks, warnings = parse(text)
    for w in warnings:
        warn(w)
    return text, newline, blocks


def cut_block(text: str, block: dict) -> str:
    """Remove the block; when it stood alone on its lines, remove those lines too. Notes around it stay."""
    s, e = block["start"], block["end"]
    line_start = text.rfind("\n", 0, s) + 1
    nl = text.find("\n", e)
    line_end = len(text) if nl == -1 else nl + 1
    if text[line_start:s].strip() == "" and text[e:line_end].strip() == "":
        return text[:line_start] + text[line_end:]
    return text[:s] + text[e:]


def write_atomic(path: str, text: str, newline: str) -> None:
    data = (text.replace("\n", newline) if newline != "\n" else text).encode("utf-8")
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(REPLACE_TRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == REPLACE_TRIES - 1:
                    raise
                time.sleep(0.2)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise QueueError(f"cannot write {path}: {exc}") from exc


class QueueLock:
    """A lock directory <root>/.locks/<name> created with mkdir, stale after stale_s seconds.
    name is "ideas" for the queue and "exports" for the export numbering (export.py)."""

    def __init__(self, root: str, stale_s: float = DEFAULT_STALE_S, wait_s: float = DEFAULT_WAIT_S,
                 name: str = "ideas", locks_dir: str | None = None):
        self.root = root
        self.name = name
        self.dir = os.path.join(locks_dir or os.path.join(root, paths.LOCKS_DIR), name)
        self.stale_s = stale_s
        self.wait_s = wait_s

    def __enter__(self) -> "QueueLock":
        os.makedirs(os.path.dirname(self.dir), exist_ok=True)
        deadline = time.monotonic() + self.wait_s
        while True:
            try:
                os.mkdir(self.dir)
            except OSError:
                age = self._age()
                if age is not None and age > self.stale_s:
                    self._break(age)
                    continue
                if time.monotonic() > deadline:
                    raise LockTimeout(f"the {self.name} lock stayed busy for {self.wait_s:.0f}s ({self._holder()})")
                time.sleep(0.05)
                continue
            try:
                with open(os.path.join(self.dir, "pid"), "w", encoding="utf-8") as f:
                    f.write(f"{os.getpid()} {int(time.time())}\n")
            except OSError:
                pass
            return self

    def __exit__(self, *exc) -> None:
        try:
            os.remove(os.path.join(self.dir, "pid"))
        except OSError:
            pass
        try:
            os.rmdir(self.dir)
        except OSError:
            pass

    def _age(self):
        try:
            return time.time() - os.stat(self.dir).st_mtime
        except OSError:
            return None

    def _holder(self) -> str:
        try:
            with open(os.path.join(self.dir, "pid"), encoding="utf-8") as f:
                return "pid " + f.read().split()[0]
        except (OSError, IndexError):
            return "holder unknown"

    def _break(self, age: float) -> None:
        holder = self._holder()
        recheck = self._age()
        if recheck is None or recheck <= self.stale_s:
            return  # somebody took a fresh lock meanwhile
        try:
            os.remove(os.path.join(self.dir, "pid"))
        except OSError:
            pass
        try:
            os.rmdir(self.dir)
        except OSError:
            return
        log_line(self.root, "WARN", f"removed a stale {self.name} lock (age {age:.0f}s, {holder})")


def mark_new(root: str, ids: list[str], queue: int, source: str) -> None:
    """Record each addition in logs/.new-ideas: epoch, id, queue size, source. The runner reads and clears it."""
    try:
        logs = os.path.join(root, paths.LOGS_DIR)
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, ".new-ideas"), "a", encoding="utf-8", newline="\n") as f:
            for one in ids:
                f.write(f"{int(time.time())}\t{one}\t{queue}\t{source}\n")
    except OSError:
        pass


def read_stdin() -> str:
    data = sys.stdin.buffer.read()
    return data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def emit(args, payload, plain: str) -> None:
    if args.plain:
        if plain:
            print(plain)
    else:
        print(json.dumps(payload, ensure_ascii=False))


def public(block: dict, n: int) -> dict:
    return {"n": n, "id": block["id"], "text": block["text"], "raw": block["raw"], "important": bool(block.get("important"))}


def cmd_list(args) -> int:
    _, _, blocks = load(args.file)
    rows = [public(b, i + 1) for i, b in enumerate(blocks)]
    emit(args, rows, "\n".join(f"{r['id']}\t{r['text']}" for r in rows))
    return 0


def cmd_first(args) -> int:
    _, _, blocks = load(args.file)
    if not blocks:
        emit(args, {"empty": True, "queue": 0}, "")
        return 3
    row = public(blocks[0], 1)
    row["queue"] = len(blocks)
    emit(args, row, f"{row['id']}\t{row['text']}")
    return 0


def cmd_count(args) -> int:
    _, _, blocks = load(args.file)
    print(len(blocks))
    return 0


def cmd_id(args) -> int:
    text = read_stdin().strip()
    if text.startswith("{") and text.endswith("}") and text.count("{") == 1 and text.count("}") == 1:
        text = text[1:-1]
    text = split_label(text)[0]
    if not normalize(text):
        print("ideas.py id: give the idea text on stdin", file=sys.stderr)
        return 1
    print(idea_id(text))
    return 0


def cmd_append(args) -> int:
    given = read_stdin()
    if "{" in given:
        new_blocks, warnings = parse(given)
        for w in warnings:
            warn(w)
        texts = [b["raw"] for b in new_blocks]
    else:
        texts = [given.strip()] if normalize(given) else []
    if not texts:
        print("ideas.py append: no idea found in the input (write it between { and })", file=sys.stderr)
        return 1
    with QueueLock(args.root, args.stale, args.wait):
        text, newline, _ = load(args.file)
        if text and not text.endswith("\n"):
            text += "\n"
        for t in texts:
            text += "{" + t + "}\n"
        write_atomic(args.file, text, newline)
        total = len(parse(text)[0])
    labels = [split_label(t) for t in texts]
    ids = [idea_id(clean) for clean, _ in labels]
    marked = sum(1 for _, important in labels if important)
    mark_new(args.root, ids, total, args.source)
    n = len(ids)
    note = "" if not marked else (", marked important" if n == 1 else f", {marked} marked important")
    emit(args, {"added": ids, "queue": total, "important": marked},
         f"added {n} idea{'s' if n != 1 else ''} to {os.path.basename(args.file)} (queue: {total}){note}")
    return 0


def cmd_remove(args) -> int:
    hint = normalize(read_stdin()) if args.text_stdin else ""
    with QueueLock(args.root, args.stale, args.wait):
        text, newline, blocks = load(args.file)
        match = next((b for b in blocks if b["id"] == args.id), None)
        similarity = None
        best_ratio, candidate = 0.0, None
        if match is None and hint:
            for b in blocks:
                ratio = difflib.SequenceMatcher(None, hint, b["text"]).ratio()
                if ratio > best_ratio:
                    best_ratio, candidate = ratio, b
            if candidate is not None and best_ratio >= MIN_SIMILARITY:
                match, similarity = candidate, best_ratio
        if match is None:
            detail = f", closest similarity {best_ratio:.2f}" if candidate is not None else ""
            reason = (f"idea {args.id} is not in {os.path.basename(args.file)} "
                      f"(edited or removed by hand{detail}); file left alone")
            log_line(args.root, "WARN", reason)
            emit(args, {"removed": None, "reason": reason, "queue": len(blocks)}, reason)
            return 3
        new_text = cut_block(text, match)
        write_atomic(args.file, new_text, newline)
        remaining = len(parse(new_text)[0])
    if similarity is not None:
        log_line(args.root, "INFO",
                 f"idea {args.id} was edited meanwhile; removed the closest match {match['id']} "
                 f"(similarity {similarity:.2f})")
    emit(args, {"removed": match["id"], "similarity": similarity, "queue": remaining},
         f"removed {match['id']} (queue: {remaining})")
    return 0


def main(argv=None) -> int:
    # Windows Python writes CRLF to pipes by default; the bash readers want LF and UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, func, root=False, lock=False, file=True):
        sp = sub.add_parser(name)
        if file:
            sp.add_argument("--file", required=True, help="ideas.txt")
        sp.add_argument("--plain", action="store_true", help="human output instead of JSON")
        if root:
            sp.add_argument("--root", help="the channel folder, holding .locks/ and logs/ (default: the file's folder)")
        if lock:
            sp.add_argument("--stale", type=float, default=DEFAULT_STALE_S, help="seconds before a lock is stale")
            sp.add_argument("--wait", type=float, default=DEFAULT_WAIT_S, help="seconds to wait for the lock")
        sp.set_defaults(func=func)
        return sp

    add("list", cmd_list)
    add("first", cmd_first)
    add("count", cmd_count)
    add("id", cmd_id, file=False)
    sp = add("append", cmd_append, root=True, lock=True)
    sp.add_argument("--source", default="add-idea", help="who added it (for the NEW line)")
    sp = add("remove", cmd_remove, root=True, lock=True)
    sp.add_argument("--id", required=True)
    sp.add_argument("--text-stdin", action="store_true", help="the original text is on stdin (similarity fallback)")

    args = parser.parse_args(argv)
    if hasattr(args, "file"):
        args.file = winpath(args.file)
    if hasattr(args, "root"):
        args.root = winpath(args.root) if args.root else os.path.dirname(os.path.abspath(args.file))
    try:
        return args.func(args)
    except LockTimeout as exc:
        print(f"ideas.py: {exc}", file=sys.stderr)
        return 4
    except QueueError as exc:
        print(f"ideas.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
