#!/usr/bin/env python
"""inventory.py: the inventory of the folder for the channels plan (M17, BUILD_SPEC.md section 12).

  python pipeline/tests/inventory.py [--root DIR] [--out DIR]

Writes <out>/inventory.tsv (every file of the folder, whatever its git state, with its size; .git, node_modules and build/
are one summary row each, Python caches are left out) and <out>/inventory.md (every top-level item, the big data
folders summed per folder, the state of the machine: a video runner alive, the ideas queued, unfinished runs, the exports,
free disk, whether the folder is synced by OneDrive). Read-only on everything but --out. The default out is build/M17.
The tsv is deterministic for a given folder; the md also says what the machine looks like right now.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f GB" % n


def pid_alive(pid):
    """Is a process with this pid alive: Git Bash's ps first (the runner's lock holds a Git Bash pid), tasklist second."""
    for cmd in (["ps", "-p", str(pid)], ["tasklist", "/FI", "PID eq %s" % pid, "/NH"]):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        if cmd[0] == "ps":
            if r.returncode == 0:
                return True
            continue
        if re.search(rb"\b%d\b" % int(pid), r.stdout):
            return True
    return False


def machine_state(root, inv):
    st = {}
    lock = os.path.join(root, ".locks", "runner", "pid")
    pid = ""
    try:
        with open(lock, encoding="utf-8") as f:
            pid = f.read().split()[0]
    except (OSError, IndexError):
        pass
    if pid and pid_alive(pid):
        st["runner"] = "ALIVE (pid %s, from .locks/runner/pid)" % pid
    elif pid:
        st["runner"] = "not running (a stale lock names pid %s)" % pid
    else:
        st["runner"] = "not running (no .locks/runner/pid)"
    status = os.path.join(root, "logs", "status.txt")
    if os.path.exists(status):
        try:
            with open(status, encoding="utf-8", errors="replace") as f:
                line = f.read().strip()
        except OSError:
            line = "(unreadable)"
        st["status_line"] = line[:200]
        st["status_age_min"] = int((time.time() - os.path.getmtime(status)) // 60)
    # the ideas queued
    ideas = os.path.join(root, "ideas.txt")
    queued = 0
    try:
        with open(ideas, encoding="utf-8", errors="replace") as f:
            queued = len(re.findall(r"^\s*\{", f.read(), re.M))
    except OSError:
        pass
    st["ideas_queued"] = queued
    # unfinished runs: a state.json whose run status is not a final one
    unfinished, finished, unreadable = [], 0, 0
    runs = os.path.join(root, "runs")
    if os.path.isdir(runs):
        for name in sorted(os.listdir(runs)):
            sp = os.path.join(runs, name, "state.json")
            if not os.path.isfile(sp):
                continue
            try:
                with open(sp, encoding="utf-8-sig") as f:
                    state = json.load(f)
            except (OSError, ValueError):
                unreadable += 1
                continue
            status_value = str(state.get("status", "running"))
            if status_value in ("exported", "dropped", "blocked", "finished", "done"):
                finished += 1
            else:
                stages = state.get("stages") or {}
                pending = [k for k, v in stages.items() if isinstance(v, dict) and v.get("status") not in ("done", "skipped")]
                unfinished.append("%s (status %s, next stage %s)" % (name, status_value, pending[0] if pending else "-"))
    st["unfinished_runs"] = unfinished
    st["finished_runs"] = finished
    st["unreadable_state"] = unreadable
    exports = []
    ex = os.path.join(root, "exports")
    if os.path.isdir(ex):
        exports = sorted(os.listdir(ex), key=ml.natural_key)
    st["exports"] = exports
    try:
        st["free_gb"] = round(shutil.disk_usage(root).free / (1024 ** 3), 1)
    except OSError:
        st["free_gb"] = None
    st["onedrive_path"] = "onedrive" in root.lower()
    st["onedrive_env"] = os.environ.get("OneDrive", "") or os.environ.get("OneDriveConsumer", "")
    st["onedrive_process"] = False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OneDrive.exe", "/NH"], capture_output=True, timeout=20)
        st["onedrive_process"] = b"OneDrive.exe" in r.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    st["online_only_files"] = len(inv.online_only)
    return st


BIG_FOLDERS = [
    ("runs/", lambda p: p.startswith("runs/")),
    ("exports/", lambda p: p.startswith("exports/")),
    ("logs/", lambda p: p.startswith("logs/")),
    ("library/voice/", lambda p: p.startswith("library/voice/")),
    ("styles/*/refs/", lambda p: re.match(r"^styles/[^/]+/refs/", p) is not None),
    ("styles/*/analysis/", lambda p: re.match(r"^styles/[^/]+/analysis/", p) is not None),
    ("styles/sfx/ audio", lambda p: p.startswith("styles/sfx/") and os.path.splitext(p)[1].lower() in (".wav", ".mp3", ".aif", ".aiff", ".ogg", ".flac", ".m4a")),
    ("render outputs", lambda p: ("/renders/" in p) or p.endswith("/golden.mp4") or p.endswith("/draft.mp4") or (p.startswith("golden/") and p.endswith(".mp4"))),
    ("motion-lib/.harness and .hyperframes (caches)", lambda p: p.startswith("motion-lib/.harness/") or p.startswith("motion-lib/.hyperframes/")),
]


def main():
    ml.out_stream()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ml.default_root())
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    out = a.out or os.path.join(root, "build", "M17")
    inv = ml.Inventory(root)

    rows = []
    for r in inv.rows:
        rows.append({"path": r["path"], "kind": r["kind"], "size": r["size"], "files": r["files"], "git": r["git"], "top": r["path"].split("/", 1)[0]})
    ml.write_tsv(os.path.join(out, "inventory.tsv"), ml.INVENTORY_COLUMNS, rows)

    total = inv.dirs.get("", {"files": 0, "bytes": 0})
    state = machine_state(root, inv)
    md = []
    md.append("# Inventory of the folder (M17)\n")
    md.append("Written by `python pipeline/tests/inventory.py`. inventory.tsv has one row per file (path, kind, size, files, git state, top-level item).")
    md.append("`.git`, `node_modules` and `build` are one summary row each (kind tree); `__pycache__` folders and `.pyc` files are left out.\n")
    md.append("Total: **%d files, %s** (%d rows in inventory.tsv). Git state of the walked files: tracked %d, untracked (not ignored) %d, ignored %d.\n"
              % (total["files"], human(total["bytes"]), len(rows), total["tracked"], total["untracked"], total["ignored"]))

    md.append("## State of the machine\n")
    md.append("- Video runner: %s" % state["runner"])
    if "status_line" in state:
        md.append("- logs/status.txt (%d minutes old): `%s`" % (state["status_age_min"], state["status_line"]))
    md.append("- Ideas queued in ideas.txt: %d" % state["ideas_queued"])
    md.append("- Runs: %d finished, %d unfinished, %d with an unreadable state.json" % (state["finished_runs"], len(state["unfinished_runs"]), state["unreadable_state"]))
    for u in state["unfinished_runs"]:
        md.append("  - unfinished: %s" % u)
    md.append("- Exports present: %s" % (", ".join("exports/" + e for e in state["exports"]) if state["exports"] else "none (no exports/ folder or it is empty)"))
    md.append("- Free disk: %s GB" % state["free_gb"])
    sync = []
    if state["onedrive_path"]:
        sync.append("the folder path contains OneDrive")
    if state["onedrive_env"]:
        sync.append("the environment names a OneDrive folder (%s)" % state["onedrive_env"])
    if state["onedrive_process"]:
        sync.append("OneDrive.exe is running")
    md.append("- Synced by OneDrive: %s; %d files are online-only (not on this disk)" % ("YES (" + "; ".join(sync) + ")" if sync else "no sign of it", state["online_only_files"]))
    md.append("")

    md.append("## Top-level items\n")
    md.append("| item | kind | files | size | tracked | untracked | ignored |")
    md.append("|---|---|---|---|---|---|---|")
    tops = ml.read_tsv(os.path.join(out, "inventory.tsv"))[1]
    items = {}
    for r in tops:
        t = r["top"]
        it = items.setdefault(t, {"files": 0, "bytes": 0, "tracked": 0, "untracked": 0, "ignored": 0, "other": 0, "dir": False})
        it["files"] += int(r["files"])
        it["bytes"] += int(r["size"])
        if r["git"] in ("tracked", "untracked", "ignored"):
            it[r["git"]] += int(r["files"])
        else:
            it["other"] += int(r["files"])
        if "/" in r["path"] or r["kind"] == "tree":
            it["dir"] = True
    for name in sorted(items):
        it = items[name]
        md.append("| %s | %s | %d | %s | %d | %d | %d%s |" % (name + ("/" if it["dir"] else ""), "folder" if it["dir"] else "file", it["files"], human(it["bytes"]),
                                                       it["tracked"], it["untracked"], it["ignored"], (" (+%d in a summary row)" % it["other"]) if it["other"] else ""))
    md.append("")

    md.append("## The big data folders, summed\n")
    md.append("| folder | files | size | tracked | untracked | ignored |")
    md.append("|---|---|---|---|---|---|")
    walked = [r for r in tops if r["kind"] == "file"]
    for label, pred in BIG_FOLDERS:
        n = b = t = u = i = 0
        for r in walked:
            if pred(r["path"]):
                n += 1
                b += int(r["size"])
                t += r["git"] == "tracked"
                u += r["git"] == "untracked"
                i += r["git"] == "ignored"
        md.append("| %s | %d | %s | %d | %d | %d |" % (label, n, human(b), t, u, i))
    md.append("")
    md.append("Per styles/sfx, library/voice, styles/*/refs and styles/*/analysis folder:\n")
    md.append("| folder | files | size |")
    md.append("|---|---|---|")
    for d in sorted(inv.dirs):
        if re.match(r"^styles/[^/]+/(refs|analysis)$", d) or d in ("library/voice", "styles/sfx", "motion-lib/renders", "golden"):
            s = inv.dirs[d]
            md.append("| %s/ | %d | %s |" % (d, s["files"], human(s["bytes"])))
    md.append("")

    md.append("## What the walk found\n")
    md.append("- Symlinks: %d%s" % (len(inv.symlinks), "".join("\n  - " + x for x in inv.symlinks[:20])))
    md.append("- Paths longer than 200 characters (absolute): %d%s" % (len(inv.long_paths), "".join("\n  - " + x for x in inv.long_paths[:20])))
    md.append("- Unreadable files: %d%s" % (len(inv.unreadable), "".join("\n  - " + x for x in inv.unreadable[:20])))
    md.append("")
    with open(os.path.join(out, "inventory.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md).replace(chr(0x2014), ", ") + "\n")
    print("inventory: %d rows, %d files, %s -> %s" % (len(rows), total["files"], human(total["bytes"]), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
