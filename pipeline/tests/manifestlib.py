#!/usr/bin/env python
"""manifestlib.py: what inventory.py, make-manifest.py, check-manifest.py, refindex.py and risk-scan.py share (M17).

The folder as the channels plan sees it (BUILD_SPEC.md 14.3, 14.13): the engine stays, FlashFX's data moves into
channels/flashfx/ (M18), the exports are renamed in place (M19). This module knows:
  - the inventory: every file of the folder with its size and git state (tracked, untracked, ignored); the three trees
    that are not walked file by file (.git, node_modules, build) are one summary row each; Python caches are left out
  - the rules: which top-level items are engine, which move, which stay, where logs/ items go (RULES below)
  - the forms an old path takes inside text (root-relative, C:/, /c/, backslashes, JSON-escaped backslashes)
  - the manifest's TSV format
Deterministic: nothing here reads the clock or the environment except where a function says so.
Python 3.13, standard library only. Never imports anything from pipeline/lib.
"""
import hashlib
import os
import re
import subprocess
import sys

CHANNEL = "flashfx"

# ---- the rules -------------------------------------------------------------------------------------------------------

SUMMARY_TREES = (".git", "node_modules", "build")      # one summary row each: not walked file by file
SKIP_DIRS = ("__pycache__",)                            # disposable caches, left out of every count
SKIP_SUFFIX = (".pyc",)

# Engine: stays where it is, never moves (14.1)
ENGINE_TOP = {"pipeline", "tools", "build", "node_modules", ".git", ".gitignore", ".gitattributes", "run.sh", "config.json",
              "package.json", "package-lock.json", "requirements.txt", "build-runner.sh", "BUILD_SPEC.md", "CHANNELS.md",
              "CLAUDE.md", "DECISIONS.md", "PLAN.md", "README.md", ".claude", ".github"}

# FlashFX's data: top-level item -> destination (M18)
CHANNEL_MOVES = [("ideas.txt", "ideas.txt"), ("library", "library"), ("styles", "styles"), ("motion-lib", "motion-lib"),
                 ("golden", "golden"), ("runs", "runs"), (".locks", ".locks")]

# logs/ items that stay at the root because they are shared (14.3); every other item of logs/ moves into the channel
SHARED_LOGS = ("limits.log", "engine.log", "editor-capabilities.json", "editor-upgrade.json", "editor-gaps-all.md")

# Top-level items that are not channel data and not engine: they stay, on purpose, and the report says so
STAY_TOP = {"voicetests": "the user's voice experiments: not channel data, not read by the pipeline, not tracked"}

# Old paths: the items that move in M18 (what a text file may name)
OLD_NAMES = ("library", "styles", "motion-lib", "golden", "runs", "logs", ".locks")
OLD_FILES = ("ideas.txt",)

TEXT_SUFFIX = {".json", ".txt", ".md", ".log", ".html", ".htm", ".js", ".mjs", ".css", ".tsv", ".csv", ".py", ".sh", ".err",
               ".meta", ".out", ".svg", ".vtt", ".srt", ".yaml", ".yml", ".jsonl", ".lock", ".toml", ".cfg", ".ini", ""}
BINARY_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aif",
                 ".aiff", ".woff", ".woff2", ".ttf", ".otf", ".ico", ".pdf", ".zip", ".gz", ".7z", ".pyc", ".bin", ".npy",
                 ".onnx", ".pt", ".safetensors", ".glb", ".gltf"}


def out_stream():
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def default_root():
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def posix(p):
    return p.replace("\\", "/")


def is_engine(path):
    top = path.split("/", 1)[0]
    return top in ENGINE_TOP


def is_text_name(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_SUFFIX:
        return False
    return ext in TEXT_SUFFIX


def is_raw_model_output(path):
    """runs/<id>/**/calls/*.json: the raw model outputs, never rewritten (14.13)."""
    parts = path.split("/")
    return "calls" in parts[:-1] and parts[-1].endswith(".json")


# ---- the inventory ---------------------------------------------------------------------------------------------------

def git_lists(root):
    """(tracked set, untracked-not-ignored set) of paths; empty sets when the folder is not a git repo."""
    def run(args):
        try:
            r = subprocess.run(["git", "-C", root] + args, capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return None
        return set(x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x)
    tracked = run(["ls-files", "-z"])
    if tracked is None:
        return set(), set()
    untracked = run(["ls-files", "-z", "-o", "--exclude-standard"]) or set()
    return tracked, untracked


class Inventory:
    """Every file under root (except the summary trees and the caches) and the sums per directory.

    files: list of dict(path, size, git, kind) sorted by path; kind is file or tree (a summary row)
    dirs:  path -> dict(files, bytes, tracked, untracked, ignored)   ('' is the whole folder)
    symlinks, long_paths, unreadable: lists for the risk scan
    """

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.rows = []
        self.dirs = {}
        self.symlinks = []
        self.long_paths = []
        self.unreadable = []
        self.online_only = []     # OneDrive files that are not on this disk (recall flags), for the risk scan
        tracked, untracked = git_lists(self.root)
        self.is_git = bool(tracked) or os.path.isdir(os.path.join(self.root, ".git"))
        for top in sorted(os.listdir(self.root)):
            full = os.path.join(self.root, top)
            if top in SUMMARY_TREES and os.path.isdir(full):
                self._summary(top, full)
                continue
            if os.path.isdir(full) and not os.path.islink(full):
                self._walk(top, full, tracked, untracked)
            else:
                self._add_file(top, full, tracked, untracked)
        self.rows.sort(key=lambda r: r["path"])

    def _bump(self, path, size, state, n=1):
        parts = path.split("/")
        for i in range(len(parts)):
            d = "/".join(parts[:i])  # '' for the root, then each ancestor folder (not the file itself)
            s = self.dirs.setdefault(d, {"files": 0, "bytes": 0, "tracked": 0, "untracked": 0, "ignored": 0, "other": 0})
            s["files"] += n
            s["bytes"] += size
            if state in ("tracked", "untracked", "ignored"):
                s[state] += n
            else:
                s["other"] += n

    def _summary(self, top, full):
        files = size = 0
        for dp, dn, fn in os.walk(full):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for n in fn:
                if n.endswith(SKIP_SUFFIX):
                    continue
                try:
                    size += os.lstat(os.path.join(dp, n)).st_size
                    files += 1
                except OSError:
                    pass
        self.rows.append({"path": top, "size": size, "files": files, "git": "mixed", "kind": "tree"})
        self._bump(top + "/x", size, "other", files)

    def _walk(self, top, full, tracked, untracked):
        for dp, dn, fn in os.walk(full):
            dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
            for d in list(dn):
                dpath = os.path.join(dp, d)
                if os.path.islink(dpath):
                    self.symlinks.append(posix(os.path.relpath(dpath, self.root)))
            for n in sorted(fn):
                if n.endswith(SKIP_SUFFIX):
                    continue
                self._add_file(posix(os.path.relpath(os.path.join(dp, n), self.root)), os.path.join(dp, n), tracked, untracked)

    def _add_file(self, rel, full, tracked, untracked):
        try:
            st = os.lstat(full)
        except OSError:
            self.unreadable.append(rel)
            return
        if os.path.islink(full):
            self.symlinks.append(rel)
        if getattr(st, "st_file_attributes", 0) & (0x400000 | 0x40000):   # RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN
            self.online_only.append(rel)
        if rel in tracked:
            state = "tracked"
        elif rel in untracked:
            state = "untracked"
        else:
            state = "ignored" if self.is_git else "untracked"
        if len(posix(full)) > 200:
            self.long_paths.append(rel)
        self.rows.append({"path": rel, "size": st.st_size, "files": 1, "git": state, "kind": "file"})
        self._bump(rel, st.st_size, state)

    def exists(self, path):
        return os.path.lexists(os.path.join(self.root, path))

    def is_dir(self, path):
        return os.path.isdir(os.path.join(self.root, path))

    def stats(self, path):
        """(files, bytes, git state, tracked, untracked, ignored) of a file or a folder under root."""
        if path in self.dirs and self.is_dir(path):
            s = self.dirs[path]
            return s["files"], s["bytes"], _state(s), s["tracked"], s["untracked"], s["ignored"]
        for r in self.rows:
            if r["path"] == path:
                st = r["git"]
                return 1, r["size"], st, int(st == "tracked"), int(st == "untracked"), int(st == "ignored")
        return 0, 0, "none", 0, 0, 0

    def children(self, path):
        """Immediate children (names) of a folder under root, from the filesystem, sorted; caches left out."""
        full = os.path.join(self.root, path) if path else self.root
        try:
            return sorted(n for n in os.listdir(full) if n not in SKIP_DIRS and not n.endswith(SKIP_SUFFIX))
        except OSError:
            return []

    def files_under(self, path):
        pre = path.rstrip("/") + "/"
        return [r for r in self.rows if r["kind"] == "file" and (r["path"] == path or r["path"].startswith(pre))]


def _state(s):
    kinds = [k for k in ("tracked", "untracked", "ignored") if s[k]]
    if not kinds:
        return "none"
    return kinds[0] if len(kinds) == 1 and not s["other"] else "mixed"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_stats(root, rel):
    """(files, bytes) of a file or folder under root, by walking, with the same exclusions as the inventory."""
    full = os.path.join(root, rel)
    if os.path.isfile(full):
        return 1, os.path.getsize(full)
    files = size = 0
    for dp, dn, fn in os.walk(full):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for n in fn:
            if n.endswith(SKIP_SUFFIX):
                continue
            try:
                size += os.lstat(os.path.join(dp, n)).st_size
                files += 1
            except OSError:
                pass
    return files, size


# ---- old paths inside text -------------------------------------------------------------------------------------------

class OldPaths:
    """The old paths (M18) in every form they take inside a text: root-relative, C:/ (mixed), /c/ (Git Bash), backslashes
    (single, and doubled as JSON writes them). Counts per (name, form)."""

    FORMS = ("relative", "mixed", "posix-drive", "backslash", "json-backslash")

    def __init__(self, root):
        self.root = os.path.abspath(root)
        mixed = posix(self.root)                               # C:/Users/there/...
        m = re.match(r"^([A-Za-z]):(/.*)$", mixed)
        drive = ("/" + m.group(1).lower() + m.group(2)) if m else None   # /c/Users/there/...
        back = mixed.replace("/", "\\")                        # C:\Users\there\...
        self.abs_forms = [("mixed", mixed), ("backslash", back), ("json-backslash", back.replace("\\", "\\\\"))]
        if drive:
            self.abs_forms.append(("posix-drive", drive))
        names = "|".join(re.escape(n) for n in OLD_NAMES)
        self.rel_dir = re.compile(r"(?<![\w.\-/\\])(" + names + r")(?=[/\\])")
        self.rel_file = re.compile(r"(?<![\w.\-/\\])(" + "|".join(re.escape(n) for n in OLD_FILES) + r")(?![\w.\-])")
        self.abs_res = []
        for form, base in self.abs_forms:
            sep = r"(?:\\\\|\\|/)" if form in ("backslash", "json-backslash") else "/"
            pat = re.escape(base) + sep + "(" + "|".join(re.escape(n) for n in OLD_NAMES + OLD_FILES) + r")(?![\w.\-])"
            flags = re.IGNORECASE if form in ("mixed", "backslash", "json-backslash", "posix-drive") else 0
            self.abs_res.append((form, re.compile(pat, flags)))

    def scan(self, text):
        """list of (name, form, start, end, matched) for every old path in text"""
        out = []
        taken = []
        for form, rx in self.abs_res:
            for m in rx.finditer(text):
                out.append((m.group(1).lower(), form, m.start(), m.end(), m.group(0)))
                taken.append((m.start(), m.end()))
        for m in self.rel_dir.finditer(text):
            nxt = text[m.end():m.end() + 1]
            form = "backslash" if nxt == "\\" else "relative"
            if form == "backslash" and text[m.end():m.end() + 2] == "\\\\":
                form = "json-backslash"
            if not any(a <= m.start() < b for a, b in taken):
                out.append((m.group(1), form, m.start(), m.end(), m.group(0)))
        for m in self.rel_file.finditer(text):
            if not any(a <= m.start() < b for a, b in taken):
                out.append((m.group(1), "relative", m.start(), m.end(), m.group(0)))
        out.sort(key=lambda t: (t[2], t[3]))
        return out


def read_text(path, limit=64 * 1024 * 1024):
    """The text of a file (utf-8, errors replaced), or None when it is binary, too big or unreadable."""
    try:
        if os.path.getsize(path) > limit:
            return None
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")


# ---- TSV -------------------------------------------------------------------------------------------------------------

MANIFEST_COLUMNS = ["seq", "ms", "scope", "method", "old", "new", "git", "files", "bytes", "sha256", "check", "reason"]
INVENTORY_COLUMNS = ["path", "kind", "size", "files", "git", "top"]


def write_tsv(path, columns, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:   # no csv module: a backslash in a cell must stay one backslash
        f.write("\t".join(columns) + "\n")
        for r in rows:
            f.write("\t".join(_cell(r.get(c, "")) for c in columns) + "\n")


def _cell(v):
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        cells = ln.split("\t")
        cells += [""] * (len(header) - len(cells))
        rows.append(dict(zip(header, cells)))
    return header, rows


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# ---- config.json keys and their destinations (14.4) ------------------------------------------------------------------

CHANNEL_KEYS = ("style", "voice", "sfx", "lengths")                         # M18: into channels/<id>/channel.json `config`
FORMAT_KEYS = ("research", "hooks", "judge", "script", "visual", "caption", "review")   # M20: into format.json `config`
REVIEW_SAFETY_KEYS = ("reviewer_tools", "fixer_tools", "fixer_paths", "protected_paths")   # engine, whatever the format
# config `paths`: the ones that point at channel data are resolved against the channel folder (14.4, 14.5)
CHANNEL_PATH_KEYS = ("ideas", "runs", "logs", "locks", "library", "hooks", "profile", "voice_dir", "styles", "style_dir", "tokens",
                     "sfx_dir", "motion_lib", "golden")


def key_destination(key):
    """(destination, milestone, note) of a dotted config.json key: engine, format or channel."""
    parts = key.split(".")
    top = parts[0]
    if top in CHANNEL_KEYS:
        return "channel", "M18", "channel-owned (style, voice, sfx, lengths): into channels/<id>/channel.json config, value unchanged"
    if top == "paths":
        if len(parts) > 1 and parts[1] in CHANNEL_PATH_KEYS:
            return "channel", "M18", "a path to channel data: resolved against the channel folder (paths module)"
        if len(parts) > 1 and parts[1] == "exports":
            return "engine", "-", "exports/ is shared, at the root: resolved against REELS_ROOT"
        return "engine", "-", "an engine path (vendor, known issues, interpreters)"
    if top == "review":
        if len(parts) > 1 and parts[1] in REVIEW_SAFETY_KEYS:
            return "engine", "-", "a safety key of review: engine, resolved for every channel (protect.py, treeguard)"
        return "format", "M20", "format-owned (problem-solution-reel): moves into format.json config; until then it stays here"
    if top in FORMAT_KEYS:
        return "format", "M20", "format-owned (problem-solution-reel): moves into format.json config; until then it stays here"
    return "engine", "-", "engine key: stays in config.json"
