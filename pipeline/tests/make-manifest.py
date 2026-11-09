#!/usr/bin/env python
"""make-manifest.py: the move manifest of the channels plan (M17 plans it, M18 and M19 execute it; BUILD_SPEC.md 14.13).

  python pipeline/tests/make-manifest.py [--root DIR] [--out FILE] [--keys-out FILE]

Reads the folder as it is and writes, by fixed rules (deterministic: the same folder gives the same bytes):
  --out        build/M17/move-manifest.tsv  every move, in execution order. Columns: seq, ms (M18 or M19), scope, method, old,
               new, git (tracked, untracked, ignored, mixed), files, bytes, sha256 (the checksum of a file), check, reason.
               scope: top = the line that covers its files (a file, a folder, a stay); inner = an action inside a folder a
               top line moves (a file rename, a rewrite of text), which covers nothing by itself.
               method: git-mv (tracked files: the folder or file is moved with git mv, which carries the untracked and ignored
               files inside it), fs-mv (a same-drive rename), rename-in-place (the same folder, a new name), rewrite (the text of
               a file changes: old paths in every form, or the export names), stays (the item stays where it is, on purpose).
               check: sha256 (one file), count-and-bytes (a folder), no-old-path-left (a rewrite).
  --keys-out   build/M17/config-keys.tsv    every config.json key and its destination: engine, format or channel.

The rules (FlashFX is the only channel that exists; its id is a constant of this file and of manifestlib.py):
  engine (never listed)   pipeline/, tools/, build/, node_modules/, run.sh, config.json, package files, the docs, .git*
  M18 moves               ideas.txt, library/, styles/, motion-lib/, golden/, runs/, .locks/ into channels/flashfx/; every item of
                          logs/ except the shared ones (limits.log, engine.log, editor-*) into channels/flashfx/logs/
  M18 rewrites            old paths (root-relative, C:/, /c/, backslashes) in the text files of every run folder (not the raw
                          model outputs calls/*.json), in every captions file and in logs/history.txt
  M19 renames             exports/N/ becomes exports/flashfx-N/ with N.mp4, Ncaptions.txt, Nhook2.mp4 renamed; the HOOKS, RUN and
                          EDITOR lines of the captions file and the "exported N" history lines follow
  stays                   the shared logs, the user's scratch folders (manifestlib.STAY_TOP), anything unexpected in exports/
A top-level item that no rule places is left out of the manifest on purpose: check-manifest.py then fails the coverage check
and the build ends BLOCKED ("the manifest cannot place some file").
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402

CH = ml.CHANNEL
DEST = "channels/" + CH


def build(root, inv=None):
    inv = inv or ml.Inventory(root)
    old_paths = ml.OldPaths(root)
    lines = []

    def add(ms, scope, method, old, new, reason, files=None, nbytes=None, git=None, check=None):
        if files is None or nbytes is None or git is None:
            f, b, g, *_ = inv.stats(old)
            files = f if files is None else files
            nbytes = b if nbytes is None else nbytes
            git = g if git is None else git
        if check is None:
            check = "sha256" if (inv.exists(old) and not inv.is_dir(old)) else "count-and-bytes"
        sha = ml.sha256_file(os.path.join(inv.root, old)) if (check == "sha256" and inv.exists(old)) else ""
        lines.append({"seq": len(lines) + 1, "ms": ms, "scope": scope, "method": method, "old": old, "new": new, "git": git,
                      "files": files, "bytes": nbytes, "sha256": sha, "check": check, "reason": reason})

    def comp(old):
        f, b, g, t, u, i = inv.stats(old)
        return "tracked=%d untracked=%d ignored=%d" % (t, u, i)

    def mover(old):
        f, b, g, t, u, i = inv.stats(old)
        return "git-mv" if t else "fs-mv"

    # ---- M18: the data of FlashFX into channels/flashfx/ ----
    for old, new in ml.CHANNEL_MOVES:
        if not inv.exists(old):
            continue
        why = {
            "ideas.txt": "the idea queue of the channel",
            "library": "the curated library: hooks, profile, voice (engine.txt and the reference recordings, ignored), brand kit; carries its ignored files",
            "styles": "the looks (paper-cards: style files tracked, refs and analysis ignored) and the sound pack (audio ignored) with its map",
            "motion-lib": "the approved components, candidates, gallery; carries the ignored renders and caches",
            "golden": "the golden videos: plan files tracked, renders ignored",
            "runs": "one working folder per idea (machine only, ignored): unfinished runs move with their channel and resume",
            ".locks": "the old root locks of the video runner (stale once the runner is stopped); the channel gets its own",
        }[old]
        add("M18", "top", mover(old), old, DEST + "/" + new, "%s; %s" % (why, comp(old)))
    logs_children = inv.children("logs") if inv.is_dir("logs") else []
    for name in logs_children:
        old = "logs/" + name
        if name in ml.SHARED_LOGS:
            add("M18", "top", "stays", old, old, "shared log of the whole machine (14.3): stays at the root; %s" % comp(old))
        else:
            add("M18", "top", mover(old), old, DEST + "/logs/" + name, "channel log or the log of a channel tool; %s" % comp(old))
    for name in sorted(ml.STAY_TOP):
        if inv.exists(name):
            add("M18", "top", "stays", name, name, ml.STAY_TOP[name] + "; " + comp(name))

    # ---- M18: rewrites of old paths ----
    def scan_files(prefix_paths):
        """(files with old paths, bytes of those files, occurrences by form) among the text files given"""
        nfiles = nbytes = 0
        forms = {}
        for r in prefix_paths:
            p = r["path"]
            if not ml.is_text_name(p) or ml.is_raw_model_output(p):
                continue
            text = ml.read_text(os.path.join(inv.root, p))
            if text is None:
                continue
            hits = old_paths.scan(text)
            if hits:
                nfiles += 1
                nbytes += r["size"]
                for h in hits:
                    forms[h[1]] = forms.get(h[1], 0) + 1
        return nfiles, nbytes, forms

    def form_text(forms):
        return ", ".join("%s %d" % (k, forms[k]) for k in sorted(forms)) or "none"

    if inv.is_dir("runs"):
        for rid in inv.children("runs"):
            rel = "runs/" + rid
            if not inv.is_dir(rel):
                continue
            n, b, forms = scan_files(inv.files_under(rel))
            if n:
                add("M18", "inner", "rewrite", rel, DEST + "/" + rel, "old paths in the text files of the run (not calls/*.json): occurrences by form: " + form_text(forms),
                    files=n, nbytes=b, git="ignored", check="no-old-path-left")
    hist = "logs/history.txt"
    if inv.exists(hist):
        n, b, forms = scan_files(inv.files_under(hist))
        if n:
            add("M18", "inner", "rewrite", hist, DEST + "/" + hist, "old paths in the history lines: occurrences by form: " + form_text(forms),
                files=1, nbytes=b, git="ignored", check="no-old-path-left")
    ex_dirs = []
    if inv.is_dir("exports"):
        for name in inv.children("exports"):
            if re.fullmatch(r"[0-9]+", name) and inv.is_dir("exports/" + name):
                ex_dirs.append(name)
        ex_dirs.sort(key=int)
    for n_ in ex_dirs:
        cap = "exports/%s/%scaptions.txt" % (n_, n_)
        if inv.exists(cap):
            nn, b, forms = scan_files(inv.files_under(cap))
            if nn:
                add("M18", "inner", "rewrite", cap, cap, "old paths in the captions file (the RUN path): occurrences by form: " + form_text(forms),
                    files=1, nbytes=b, git="ignored", check="no-old-path-left")

    # ---- M19: exports ----
    for name in inv.children("exports") if inv.is_dir("exports") else []:
        old = "exports/" + name
        if name in ex_dirs:
            continue
        add("M19", "top", "stays", old, old, "not an exports/N folder: the exporter does not know it; stays; %s" % comp(old))
    for n_ in ex_dirs:
        old = "exports/" + n_
        new = "exports/%s-%s" % (CH, n_)
        add("M19", "top", "rename-in-place", old, new, "exports/N becomes exports/<id>-N (section 8); project/ and every other file keep their names; %s" % comp(old),
            git="ignored" if not inv.stats(old)[3] else None)
    for n_ in ex_dirs:
        for suffix in (".mp4", "captions.txt", "hook2.mp4"):
            fn = n_ + suffix
            old = "exports/%s/%s" % (n_, fn)
            if inv.exists(old):
                add("M19", "inner", "rename-in-place", old, "exports/%s-%s/%s-%s" % (CH, n_, CH, fn), "export file name (section 8): %s-%s" % (CH, fn))
    for n_ in ex_dirs:
        cap = "exports/%s/%scaptions.txt" % (n_, n_)
        if inv.exists(cap):
            add("M19", "inner", "rewrite", cap, "exports/%s-%s/%s-%scaptions.txt" % (CH, n_, CH, n_),
                "the HOOKS names (%s-%s.mp4 uses, %s-%shook2.mp4 uses), the RUN path and the EDITOR path follow the new names" % (CH, n_, CH, n_),
                files=1, check="export-names")
    hist_after = DEST + "/" + hist       # the history after M18 has moved it (M19 runs on the folder as M18 left it)
    if inv.exists(hist):
        text = ml.read_text(os.path.join(inv.root, hist)) or ""
        n_exported = len(re.findall(r"\| exported [0-9]+ *$", text, re.M))
        if n_exported:
            add("M19", "inner", "rewrite", hist, DEST + "/" + hist, "history lines: %d line(s) '| exported N' become '| exported %s-N'" % (n_exported, CH),
                files=1, check="export-names")
    elif inv.exists(hist_after):
        text = ml.read_text(os.path.join(inv.root, hist_after)) or ""
        n_exported = len(re.findall(r"\| exported [0-9]+ *$", text, re.M))
        if n_exported:
            add("M19", "top", "stays", hist_after, hist_after, "the channel's history stays where M18 put it; its export lines are rewritten below; tracked=0 untracked=0 ignored=1")
            add("M19", "inner", "rewrite", hist_after, hist_after, "history lines: %d line(s) '| exported N' become '| exported %s-N'" % (n_exported, CH),
                files=1, check="export-names")
    return lines


def config_rows(root):
    path = os.path.join(root, "config.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    rows = []

    def short(v):
        s = json.dumps(v, ensure_ascii=True, separators=(",", ":"))
        return s if len(s) <= 60 else s[:57] + "..."

    def walk(node, prefix, depth):
        for k, v in node.items():
            key = prefix + k
            if isinstance(v, dict) and depth < 1 and v:
                walk(v, key + ".", depth + 1)
            else:
                dest, ms, note = ml.key_destination(key)
                rows.append({"key": key, "destination": dest, "moves_in": ms, "value": short(v), "note": note})
    walk(cfg, "", 0)
    return rows


def main():
    ml.out_stream()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ml.default_root())
    ap.add_argument("--out", default=None)
    ap.add_argument("--keys-out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    out = a.out or os.path.join(root, "build", "M17", "move-manifest.tsv")
    keys_out = a.keys_out or os.path.join(os.path.dirname(out), "config-keys.tsv")
    lines = build(root)
    ml.write_tsv(out, ml.MANIFEST_COLUMNS, lines)
    ml.write_tsv(keys_out, ["key", "destination", "moves_in", "value", "note"], config_rows(root))
    tops = [x for x in lines if x["scope"] == "top"]
    print("make-manifest: %d lines (%d top, %d inner) -> %s" % (len(lines), len(tops), len(lines) - len(tops), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
