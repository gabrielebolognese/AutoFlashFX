#!/usr/bin/env python
"""risk-scan.py: everything that can break the moves of M18 and M19, each marked BLOCKER or NOTE (M17, BUILD_SPEC.md section 12).

  python pipeline/tests/risk-scan.py [--root DIR] [--out DIR]

Reads the folder, the manifest (build/M17/move-manifest.tsv), the inventory and the refindex files of --out (default build/M17);
writes <out>/risks.md and <out>/riskiest-moves.md. Read-only on everything else.
BLOCKER: the moves must not start while it is true (M18 either refuses, or resolves it first: the line says which).
NOTE: something to know, a risk the move's own checks cover, or a count M18 will work from.
Checks: a video runner alive, an unfinished run, uncommitted changes, open or locked files (processes that may hold files),
OneDrive sync and files not on this disk, old paths inside data, paths longer than 200 characters (before and after the move),
symlinks, files the manifest cannot place, disk space, a channels/ folder that is already there, the runner-written tracked files,
direct reads of config.json, branches waiting to be merged.
"""
import argparse
import collections
import importlib.util
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return ""


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def running_processes():
    try:
        r = subprocess.run(["tasklist", "/NH", "/FO", "CSV"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return {}
    names = collections.Counter()
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        m = re.match(r'"([^"]+)"', line)
        if m:
            names[m.group(1).lower()] += 1
    return names


def main():
    ml.out_stream()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ml.default_root())
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    out = a.out or os.path.join(root, "build", "M17")
    inventory = load_module("inventory_mod", "inventory.py")
    checker = load_module("check_manifest_mod", "check-manifest.py")
    inv = ml.Inventory(root)
    manifest_path = os.path.join(out, "move-manifest.tsv")
    rows = ml.read_tsv(manifest_path)[1] if os.path.exists(manifest_path) else []
    top = [r for r in rows if r["scope"] == "top"]
    blockers, notes = [], []

    def B(title, detail):
        blockers.append((title, detail))

    def N(title, detail):
        notes.append((title, detail))

    state = inventory.machine_state(root, inv)

    # a video runner alive
    if state["runner"].startswith("ALIVE"):
        B("A video runner is alive", "%s. M18 refuses to move anything while any runner holds a lock. Stop it (Ctrl+C in its window) before M18." % state["runner"])
    else:
        N("No video runner is alive", state["runner"] + ". It must stay stopped from M18 on until the migration is verified (build/HUMAN_TODO.md).")
    if os.path.isdir(os.path.join(root, ".locks")):
        B("A .locks/ folder exists", "its entries: %s. M18 moves .locks/ with the channel only when no pid in it is alive." % ", ".join(os.listdir(os.path.join(root, ".locks"))))

    # unfinished runs
    if state["unfinished_runs"]:
        N("Unfinished runs", "%d run(s) have a stage that is not done: %s. They move with their channel and resume at the same stage; nothing waits for the user."
          % (len(state["unfinished_runs"]), "; ".join(state["unfinished_runs"][:10])))
    else:
        N("No unfinished runs", "runs/ has %d run folder(s) and none is unfinished (runs/ %s)." % (state["finished_runs"], "exists" if os.path.isdir(os.path.join(root, "runs")) else "does not exist yet"))
    if not os.path.isdir(os.path.join(root, "exports")) or not state["exports"]:
        N("No exports yet", "exports/ is absent or empty: the manifest has no M19 line today. M19 writes the manifest again first, so exports made before then are renamed (the rules and the fixture test cover them).")
    if not os.path.isdir(os.path.join(root, "runs")):
        N("No runs/ folder", "runs/ does not exist: the manifest has no run lines and no run rewrites today; the rules (and test-m17's fixture folder, which has runs and exports) cover them.")

    # uncommitted changes
    porcelain = [ln for ln in git(root, "status", "--porcelain").splitlines() if ln.strip()]
    outside = [ln for ln in porcelain if not (ln[3:].startswith("build/") or ln[3:].startswith("pipeline/tests/") or ln[3:] in ("CLAUDE.md", "PLAN.md", "DECISIONS.md"))]
    if outside:
        B("Uncommitted changes outside build/ and pipeline/tests/", "%d: %s. M18 refuses to start while git has uncommitted changes outside its own files; it first commits "
          "the two runner-written files as a snapshot, and test output such as motion-lib/gallery/frame-match.json must be committed or restored by the build before then "
          "(M17 does not touch motion-lib)." % (len(outside), "; ".join(x.strip() for x in outside[:8])))
    if porcelain and not outside:
        N("Uncommitted changes inside build/ and pipeline/tests/", "%d entries (M17's own files until its commit)." % len(porcelain))
    runner_written = [p for p in ("library/.hooks.stats.json", "library/hooks.suggested.txt") if inv.exists(p)]
    if runner_written:
        N("Runner-written tracked files", "%s change on every real run: M18 commits them as they are (chore: snapshot runner-written files before the move) before migrating." % ", ".join(runner_written))

    # branches
    branches = [b.strip(" *+") for b in git(root, "branch", "--list").splitlines()]
    extra = [b for b in branches if b and b != "main"]
    if extra:
        N("Other local branches", "%s. The branch important-ideas (the user's model change: Sonnet as the main model, fable only for [important] ideas) waits to be merged into main "
          "at the M18 pause; merge it before M18 starts, on a clean tree, then renumber DECISIONS 323 to 325 if the numbers are taken. It adds pipeline/tests/test-models.sh, which "
          "run-fake.sh picks up once the file exists." % ", ".join(extra))

    # open or locked files
    procs = running_processes()
    watch = {k: v for k, v in procs.items() if k in ("node.exe", "chrome.exe", "msedge.exe", "chromium.exe", "ffmpeg.exe", "ffprobe.exe", "code.exe", "onedrive.exe", "python.exe", "claude.exe")}
    N("Processes that may hold files open", "running now: %s. A process with a file open in a moved folder (a render, a browser harness, an editor) makes a rename fail; "
      "migrate-channels retries as the runner's moves do and undoes itself when a rename still fails. Close editors and browsers that have motion-lib/, styles/ or golden/ open."
      % (", ".join("%s x%d" % kv for kv in sorted(watch.items())) or "none of node, chrome, ffmpeg, an editor"))

    # OneDrive
    sync = state["onedrive_path"] or state["onedrive_process"]
    if sync:
        N("OneDrive syncs this folder", "%s. %d file(s) are online-only (not on this disk): %s. OneDrive may hold a handle on a file it is uploading, so a rename can fail for a moment; "
          "the migration retries, and the whole move is one rename per folder. Files that are online-only are downloaded by a copy but not by a rename."
          % ("the path is under OneDrive" + ("; OneDrive.exe is running" if state["onedrive_process"] else ""), state["online_only_files"],
             "none" if not inv.online_only else ", ".join(inv.online_only[:5])))
        if inv.online_only:
            B("Files that are online-only", "%d file(s) are not on this disk: make them available offline before M18 (right click, Always keep on this device)." % len(inv.online_only))
    else:
        N("OneDrive", "no sign that this folder is synced")

    # old paths inside data
    data_rows = ml.read_tsv(os.path.join(out, "refindex-data.tsv"))[1] if os.path.exists(os.path.join(out, "refindex-data.tsv")) else []
    ignored_old = [r for r in data_rows if r["git"] != "tracked" and "raw model output" not in r["bucket"]]
    tracked_old = [r for r in data_rows if r["git"] == "tracked"]
    if data_rows:
        by_bucket = collections.Counter()
        for r in ignored_old:
            by_bucket[(r["bucket"], r["form"])] += int(r["occurrences"])
        N("Old paths inside ignored data", "%d occurrences in %d (bucket, form) groups: %s. Run files, captions files and history lines are rewritten by M18 (14.13); old paths in the "
          "ignored caches of motion-lib/.harness and .hyperframes and in golden/*/project/.hyperframes name the folder's own absolute path and are rebuilt by the tools that wrote them "
          "(a stale cache is not a correctness problem, a stale <base href> in a harness page is). Details: refindex-data.tsv."
          % (sum(by_bucket.values()), len(by_bucket), "; ".join("%s %s %d" % (k[0], k[1], v) for k, v in sorted(by_bucket.items())[:8])))
        absolute = [r for r in tracked_old if r["form"] != "relative"]
        if absolute:
            N("Absolute old paths inside tracked data", "%d (path, form) group(s), %d occurrences, for example %s. After the move these name a folder that no longer exists "
              "(motion-lib/gallery/play/*.html carry a <base href> to motion-lib/): M18 rewrites them where a test or a tool reads them, or the gallery tool rewrites them "
              "(python pipeline/lib/motion gallery), and lists each one in its report." % (len(absolute), sum(int(r["occurrences"]) for r in absolute), absolute[0]["example"][:120]))

    # the refindex totals
    ref_path = os.path.join(out, "refindex.tsv")
    if os.path.exists(ref_path):
        ref = ml.read_tsv(ref_path)[1]
        by = collections.Counter((r["subject"], r["kind"]) for r in ref if r["rooted"] == "yes")
        N("Size of M18's code work (refindex)", "%d occurrences in %d files. Paths built in code (kind code): %d; export names in code: %d; direct reads of config.json: %d; "
          "tests: %d; docs and prompts: %d. Details: refindex.tsv, counts per kind in report.md."
          % (len(ref), len(set(r["file"] for r in ref)), by[("path", "code")], by[("export-name", "code")], by[("config-read", "code")],
             sum(v for k, v in by.items() if k[1] == "test"), sum(v for k, v in by.items() if k[1] in ("doc", "prompt"))))

    # long paths, now and after the move
    longest_now = max((len(posix_abs(root, r["path"])) for r in inv.rows if r["kind"] == "file"), default=0)
    new_long = []
    for t in top:
        if t["method"] == "stays":
            continue
        shift = len(t["new"]) - len(t["old"])
        for r in inv.files_under(t["old"]):
            n = len(posix_abs(root, r["path"])) + shift
            if n > 200:
                new_long.append((n, t["new"] + r["path"][len(t["old"]):]))
    new_long.sort(reverse=True)
    if inv.long_paths:
        N("Paths longer than 200 characters now", "%d, for example %s" % (len(inv.long_paths), inv.long_paths[0]))
    if new_long:
        worst = new_long[0]
        if worst[0] >= 255:
            B("Paths too long after the move", "%d file(s) would pass 255 characters (the Windows limit is 260), the longest %d: %s. Shorten the path or the run folder name first." % (len([x for x in new_long if x[0] >= 255]), worst[0], worst[1]))
        else:
            N("Paths longer than 200 characters after the move", "%d file(s); the longest is %d characters (limit 260): %s. The new prefix adds %d characters to every moved path."
              % (len(new_long), worst[0], worst[1], len("channels/flashfx/")))
    else:
        N("Path lengths", "the longest path now is %d characters; after the move the new prefix adds %d, so none passes 200 today. Runs and exports added later have longer names (a run folder is "
          "<date>_<slug>): checked again when M18 writes the manifest." % (longest_now, len("channels/flashfx/")))

    # symlinks
    if inv.symlinks:
        B("Symlinks in the folder", "%d: %s. A symlink inside a moved folder points at a path that may not follow it." % (len(inv.symlinks), ", ".join(inv.symlinks[:8])))
    else:
        N("Symlinks", "none in the walked folders (node_modules is not walked and is engine)")
    if inv.unreadable:
        B("Unreadable files", "%d: %s" % (len(inv.unreadable), ", ".join(inv.unreadable[:8])))

    # files the manifest cannot place
    if rows:
        inv_rows = [{"path": r["path"], "size": r["size"], "files": r["files"]} for r in inv.rows]
        problems, warnings, stats = checker.check_before(root, manifest_path, inv_rows, None, False)
        for p in problems:
            B("The manifest does not hold", p)
        if not problems:
            N("The manifest places every file", "%(covered_files)d files are covered by %(top)d top lines, %(engine_files)d are engine, %(files)d in the inventory" % stats)
        for w in warnings:
            N("Drift", w)
    else:
        B("No manifest", "run make-manifest.py first")

    # disk
    free = state["free_gb"] or 0
    if free < 2:
        B("Not enough free disk", "%.1f GB free; M18 needs 2 GB." % free)
    else:
        N("Disk space", "%.1f GB free (M18 needs 2 GB; the moves are renames and add no data; the rehearsal fixture and the test copies take under 1 GB)." % free)

    if os.path.exists(os.path.join(root, "channels")):
        kids = os.listdir(os.path.join(root, "channels"))
        B("channels/ already exists", "it holds %s; M18 creates channels/flashfx/ and refuses to merge into an existing folder." % (", ".join(kids) or "nothing"))

    # the gitignore and the hooks rule
    gi = os.path.join(root, ".gitignore")
    if os.path.exists(gi):
        text = open(gi, encoding="utf-8").read().splitlines()
        names = r"(runs|exports|logs|\.locks|library|styles|motion-lib|golden)/"
        anchored = [ln for ln in text if ln.strip() and not ln.startswith("#") and re.match(r"^!?/?" + names, ln)]
        N(".gitignore rules to rewrite", "%d rule(s) name the old folders and must become channels/*/... rules, committed before the first move (14.3): %s"
          % (len(anchored), "; ".join(anchored[:10])))
    N("The curated hooks file", "pipeline/tests/no_emdash.py skips library/hooks.txt by path (the user's file with its dashes): M18 changes the skip path to channels/*/library/hooks.txt "
      "and never edits the hooks file to make a test pass.")
    N("The folder voicetests/", "14 untracked files (the user's voice experiments) stay at the root on purpose: a stays line, not channel data.")

    # the riskiest moves
    scored = []
    for t in top:
        ignored_bytes = 0
        if t["method"] != "stays":
            for r in inv.files_under(t["old"]):
                if r["git"] != "tracked":
                    ignored_bytes += r["size"]
        score = ignored_bytes / (1024.0 * 1024.0) + int(t["files"]) / 50.0 + (30 if t["git"] == "mixed" else 0) + (500 if t["method"] == "stays" else 0) * 0
        why = []
        if ignored_bytes:
            why.append("%s of files git does not hold (only the undo script can bring them back)" % human(ignored_bytes))
        if t["git"] == "mixed":
            why.append("tracked and ignored files in one folder (git mv carries both; git check-ignore must pass at the new path)")
        if int(t["files"]) > 1000:
            why.append("%s files" % t["files"])
        if t["old"] in ("library", "ideas.txt"):
            why.append("curated by the user: never to be lost or edited")
        if t["old"].startswith("logs/"):
            why.append("a log the runner appends to: moves only with the runner stopped")
        if t["method"] == "stays":
            why.append("stays in place, no risk")
            score = 0
        scored.append((score, t, why))
    scored.sort(key=lambda x: (-x[0], x[1]["seq"]))
    with open(os.path.join(out, "riskiest-moves.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# The riskiest moves (M17)\n\nRanked by the bytes git cannot restore, the files, and mixed git state. From move-manifest.tsv.\n\n")
        for i, (score, t, why) in enumerate(scored[:10], 1):
            f.write("%d. `%s` -> `%s` (%s, %s files, %s; %s): %s\n" % (i, t["old"], t["new"], t["method"], t["files"], human(int(t["bytes"])), t["ms"], "; ".join(why) or "small and tracked"))
        f.write("\nM18 also rewrites text: old paths in the run folders, the captions files and the history lines, and the config keys move from config.json into channel.json "
                "(config-keys.tsv); those are the riskiest edits that are not moves.\n")

    with open(os.path.join(out, "risks.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Risks of the moves (M17)\n\nWritten by `python pipeline/tests/risk-scan.py`. BLOCKER: the moves must not start while it is true. NOTE: to know, or covered by the "
                "move's own checks.\n\n")
        f.write("## BLOCKERs (%d)\n\n" % len(blockers))
        for title, detail in blockers:
            f.write("- **BLOCKER %s**: %s\n" % (title, detail))
        if not blockers:
            f.write("None.\n")
        f.write("\n## NOTEs (%d)\n\n" % len(notes))
        for title, detail in notes:
            f.write("- **NOTE %s**: %s\n" % (title, detail))
    print("risk-scan: %d BLOCKER(s), %d NOTE(s) -> %s" % (len(blockers), len(notes), out))
    return 0


def posix_abs(root, rel):
    return ml.posix(os.path.join(root, rel))


if __name__ == "__main__":
    sys.exit(main())
