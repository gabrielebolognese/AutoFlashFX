#!/usr/bin/env python
"""check-manifest.py: checks the move manifest of the channels plan (M17; M18 to M24 call it; BUILD_SPEC.md 14.13).

  python pipeline/tests/check-manifest.py [--root DIR] [--manifest FILE] [--inventory FILE] [--live] [--strict]
  python pipeline/tests/check-manifest.py --after [--root DIR] [--manifest FILE]

Before the moves (the default) it checks that:
  - the file is well formed (columns, sequence numbers, milestones M18 or M19, scopes, methods)
  - every old path exists
  - no two lines collide: no new path twice, no path moved twice, no top line nested inside another top line, no new path
    that is already taken by a file that stays
  - every new path is inside channels/<id>/ or exports/, or the line stays
  - every file of the inventory, whatever its git state, is covered exactly once, by its own top line or by the line of a
    folder that contains it, or is engine (manifestlib.is_engine); a file that nothing places fails the check (the build
    then ends BLOCKED: "the manifest cannot place some file")
  - the files and bytes of every line equal the inventory's, and the lines plus the engine add up to the inventory's total
  - every inner line (a rename or a rewrite inside a moved folder) sits inside a top line
The inventory is the file given with --inventory (default: the inventory.tsv next to the manifest), or the folder as it is
now with --live. A folder that changed since the manifest was written (the video runner adds files) is a DRIFT warning;
--strict makes it an error. M18 and M19 write the manifest again right before they move, so drift is expected between milestones.

With --after it checks the folder after a migration: every new path is there, no moved folder is left at its old path, the
checksum (a file) or the count and bytes (a folder) match the manifest, a stay is still in place, no rewritten file keeps an old
path or an old export name. Exit 0 when everything passes, 1 otherwise; prints one line per problem.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402

METHODS = {"git-mv", "fs-mv", "rename-in-place", "rewrite", "stays"}
NEW_OK = re.compile(r"^(channels/[a-z][a-z0-9]{1,23}/|exports/)")


def inside(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def load(path):
    header, rows = ml.read_tsv(path)
    return header, rows


def check_before(root, manifest, inv_rows, live, strict):
    problems, warnings = [], []
    header, rows = load(manifest)
    if header != ml.MANIFEST_COLUMNS:
        problems.append("the manifest's columns are %s, want %s" % (header, ml.MANIFEST_COLUMNS))
        return problems, warnings, {}
    top = [r for r in rows if r["scope"] == "top"]
    inner = [r for r in rows if r["scope"] == "inner"]
    for i, r in enumerate(rows, 1):
        if r["seq"] != str(i):
            problems.append("line %d: seq is %s, want %d" % (i, r["seq"], i))
        if r["ms"] not in ("M18", "M19"):
            problems.append("line %d: milestone %r is not M18 or M19" % (i, r["ms"]))
        if r["scope"] not in ("top", "inner"):
            problems.append("line %d: scope %r is not top or inner" % (i, r["scope"]))
        if r["method"] not in METHODS:
            problems.append("line %d: method %r is unknown" % (i, r["method"]))
        if r["method"] == "stays" and r["old"] != r["new"]:
            problems.append("line %d: a stay must keep its path (%s -> %s)" % (i, r["old"], r["new"]))
        if r["method"] == "stays" and r["scope"] != "top":
            problems.append("line %d: a stay is a top line" % i)

    # every old path exists
    for r in rows:
        if not os.path.lexists(os.path.join(root, r["old"])):
            problems.append("line %s: old path %s does not exist" % (r["seq"], r["old"]))

    # collisions
    seen_new, seen_old = {}, {}
    for r in rows:
        if r["method"] == "rewrite":
            key = (r["ms"], r["old"], r["new"])
            if key in seen_new:
                problems.append("line %s: the same rewrite as line %s (%s)" % (r["seq"], seen_new[key], r["old"]))
            seen_new[key] = r["seq"]
            continue
        if r["new"] in seen_new:
            problems.append("line %s: new path %s is also the new path of line %s" % (r["seq"], r["new"], seen_new[r["new"]]))
        seen_new[r["new"]] = r["seq"]
        if r["old"] in seen_old:
            problems.append("line %s: %s is moved twice (line %s too)" % (r["seq"], r["old"], seen_old[r["old"]]))
        seen_old[r["old"]] = r["seq"]
    moved_olds = set(r["old"] for r in top if r["method"] != "stays")
    for a in top:
        for b in top:
            if a is b:
                continue
            if inside(a["old"], b["old"]):
                problems.append("lines %s and %s: %s is inside %s (covered twice)" % (a["seq"], b["seq"], a["old"], b["old"]))
            if a["method"] != "stays" and b["method"] != "stays" and inside(a["new"], b["new"]):
                problems.append("lines %s and %s: new path %s is inside new path %s" % (a["seq"], b["seq"], a["new"], b["new"]))
    for r in top:
        if r["method"] == "stays":
            continue
        # a new path may already exist only when it is the old path of a line that moves away (the exports renames)
        if os.path.lexists(os.path.join(root, r["new"])) and r["new"] not in moved_olds:
            problems.append("line %s: new path %s already exists" % (r["seq"], r["new"]))

    # every new path inside channels/<id>/ or exports/, or stays
    for r in rows:
        if r["method"] == "stays":
            continue
        if not NEW_OK.match(r["new"]):
            problems.append("line %s: new path %s is not inside channels/<id>/ or exports/" % (r["seq"], r["new"]))

    # inner lines sit inside a top line
    for r in inner:
        if not any(inside(r["old"], t["old"]) for t in top):
            problems.append("line %s (inner): %s is inside no top line" % (r["seq"], r["old"]))

    # coverage and totals, against the inventory
    cover = {}
    engine_files = engine_bytes = 0
    total_files = total_bytes = 0
    for row in inv_rows:
        p = row["path"]
        size = int(row["size"])
        nfiles = int(row["files"])
        total_files += nfiles
        total_bytes += size
        covering = [t for t in top if inside(p, t["old"])]
        if len(covering) > 1:
            problems.append("coverage: %s is covered by %d lines (%s)" % (p, len(covering), ", ".join(t["seq"] for t in covering)))
        elif len(covering) == 1:
            if ml.is_engine(p):
                problems.append("coverage: engine file %s is covered by line %s" % (p, covering[0]["seq"]))
            c = cover.setdefault(covering[0]["seq"], [0, 0])
            c[0] += nfiles
            c[1] += size
        else:
            if ml.is_engine(p):
                engine_files += nfiles
                engine_bytes += size
            else:
                problems.append("coverage: nothing places %s (no line covers it, and it is not engine)" % p)
    covered_files = covered_bytes = 0
    for t in top:
        got = cover.get(t["seq"], [0, 0])
        covered_files += got[0]
        covered_bytes += got[1]
        if (got[0], got[1]) != (int(t["files"]), int(t["bytes"])):
            problems.append("line %s (%s): the manifest says %s files, %s bytes; the inventory says %d files, %d bytes"
                            % (t["seq"], t["old"], t["files"], t["bytes"], got[0], got[1]))
    if covered_files + engine_files != total_files or covered_bytes + engine_bytes != total_bytes:
        problems.append("totals: lines %d files + engine %d files = %d, the inventory has %d files; bytes %d + %d = %d against %d"
                        % (covered_files, engine_files, covered_files + engine_files, total_files, covered_bytes, engine_bytes,
                           covered_bytes + engine_bytes, total_bytes))

    # drift: the folder as it is now against the lines
    drift = []
    for t in top:
        full = os.path.join(root, t["old"])
        if not os.path.lexists(full):
            continue
        f, b = ml.tree_stats(root, t["old"])
        if (f, b) != (int(t["files"]), int(t["bytes"])):
            drift.append("line %s (%s): %s files, %s bytes in the manifest; now %d files, %d bytes" % (t["seq"], t["old"], t["files"], t["bytes"], f, b))
        elif t["sha256"] and os.path.isfile(full) and ml.sha256_file(full) != t["sha256"]:
            drift.append("line %s (%s): the checksum changed" % (t["seq"], t["old"]))
    (problems if strict else warnings).extend("DRIFT " + d for d in drift)
    if live is not None:
        live_paths = set(r["path"] for r in live)
        rec_paths = set(r["path"] for r in inv_rows)
        gone = sorted(p for p in rec_paths - live_paths if not ml.is_engine(p))
        new = sorted(p for p in live_paths - rec_paths if not ml.is_engine(p))
        for p in gone[:20]:
            (problems if strict else warnings).append("DRIFT %s was in the inventory and is gone" % p)
        for p in new[:20]:
            (problems if strict else warnings).append("DRIFT %s is new since the inventory" % p)
    stats = {"lines": len(rows), "top": len(top), "inner": len(inner), "files": total_files, "bytes": total_bytes,
             "covered_files": covered_files, "engine_files": engine_files}
    return problems, warnings, stats


def check_after(root, manifest):
    problems = []
    header, rows = load(manifest)
    if header != ml.MANIFEST_COLUMNS:
        return ["the manifest's columns are %s, want %s" % (header, ml.MANIFEST_COLUMNS)], {}
    old_paths = ml.OldPaths(root)
    moves = [(r["old"], r["new"]) for r in rows if r["method"] not in ("rewrite", "stays")]

    def final(path):
        """where a path of the manifest is after every line has run: the longest old prefix that moved (the lines use the old layout)"""
        best = None
        for o, n in moves:
            if inside(path, o) and (best is None or len(o) > len(best[0])):
                best = (o, n)
        return path if best is None else best[1] + path[len(best[0]):]

    # a file that a rewrite changes keeps its count but not its checksum or its bytes
    rewritten = [final(r["new"]) for r in rows if r["method"] == "rewrite"]
    for r in rows:
        full_new = os.path.join(root, r["new"])
        if r["method"] == "stays":
            if not os.path.lexists(full_new):
                problems.append("line %s: %s should stay and is gone" % (r["seq"], r["old"]))
            continue
        if r["method"] == "rewrite":
            tgt = final(r["new"])
            full_new = os.path.join(root, tgt)
            if not os.path.lexists(full_new):
                problems.append("line %s: rewritten file %s is missing" % (r["seq"], tgt))
                continue
            targets = [x for x in ml.Inventory(root).files_under(tgt)] if os.path.isdir(full_new) else [{"path": tgt}]
            for t in targets:
                p = t["path"]
                if not ml.is_text_name(p) or ml.is_raw_model_output(p):
                    continue
                text = ml.read_text(os.path.join(root, p))
                if text is None:
                    continue
                if r["check"] == "no-old-path-left":
                    hits = old_paths.scan(text)
                    if hits:
                        problems.append("line %s: %s still names an old path (%s, %d hit(s))" % (r["seq"], p, hits[0][4], len(hits)))
                elif r["check"] == "export-names":
                    if re.search(r"^[0-9]+(hook2)?\.mp4 uses:", text, re.M) or re.search(r"\| exported [0-9]+ *$", text, re.M):
                        problems.append("line %s: %s still has an old export name" % (r["seq"], p))
            continue
        # a move or a rename
        if not os.path.lexists(full_new):
            problems.append("line %s: new path %s is missing" % (r["seq"], r["new"]))
            continue
        if r["scope"] == "top" and os.path.lexists(os.path.join(root, r["old"])):
            problems.append("line %s: the moved item is still at its old path %s" % (r["seq"], r["old"]))
        if r["scope"] == "inner" and os.path.lexists(os.path.join(root, r["old"])) and r["old"] != r["new"]:
            problems.append("line %s: the renamed file is still at its old path %s" % (r["seq"], r["old"]))
        if r["check"] == "sha256" and r["sha256"] and os.path.isfile(full_new):
            if ml.sha256_file(full_new) != r["sha256"] and not any(inside(w, r["new"]) or inside(r["new"], w) for w in rewritten):
                problems.append("line %s: the checksum of %s changed" % (r["seq"], r["new"]))
        elif r["check"] == "count-and-bytes" and r["scope"] == "top":
            f, b = ml.tree_stats(root, r["new"])
            # a folder with renames or rewrites inside keeps its count; its bytes change only by the rewrites: say so as a problem
            # only when the count differs, or the bytes differ and no rewrite sits inside the folder
            has_rewrite = any(x["method"] == "rewrite" and (inside(x["old"], r["old"]) or inside(x["new"], r["new"])) for x in rows)
            if f != int(r["files"]):
                problems.append("line %s: %s has %d files, the manifest says %s" % (r["seq"], r["new"], f, r["files"]))
            elif b != int(r["bytes"]) and not has_rewrite:
                problems.append("line %s: %s has %d bytes, the manifest says %s" % (r["seq"], r["new"], b, r["bytes"]))
    # no top-level folder of the old layout is left behind when the manifest moved it
    for r in rows:
        if r["scope"] == "top" and r["method"] in ("git-mv", "fs-mv") and "/" not in r["old"] and os.path.isdir(os.path.join(root, r["old"])):
            problems.append("old top-level folder %s still exists" % r["old"])
    return problems, {"lines": len(rows)}


def main():
    ml.out_stream()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ml.default_root())
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--inventory", default=None)
    ap.add_argument("--live", action="store_true", help="check the coverage against the folder as it is now, not against inventory.tsv")
    ap.add_argument("--strict", action="store_true", help="a folder that changed since the manifest was written is an error")
    ap.add_argument("--after", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    manifest = a.manifest or os.path.join(root, "build", "M17", "move-manifest.tsv")
    if not os.path.exists(manifest):
        print("check-manifest: no manifest at %s" % manifest)
        return 1
    if a.after:
        problems, stats = check_after(root, manifest)
        for p in problems:
            print("FAIL " + p)
        print("check-manifest --after: %d line(s) checked, %d problem(s)" % (stats.get("lines", 0), len(problems)))
        return 1 if problems else 0
    inv_path = a.inventory or os.path.join(os.path.dirname(manifest), "inventory.tsv")
    live_rows = None
    if a.live or not os.path.exists(inv_path):
        inv = ml.Inventory(root)
        inv_rows = [{"path": r["path"], "size": r["size"], "files": r["files"]} for r in inv.rows]
    else:
        inv_rows = ml.read_tsv(inv_path)[1]
        if not a.live:
            inv = ml.Inventory(root)
            live_rows = [{"path": r["path"], "size": r["size"], "files": r["files"]} for r in inv.rows]
    problems, warnings, stats = check_before(root, manifest, inv_rows, live_rows, a.strict)
    for w in warnings:
        print("WARN " + w)
    for p in problems:
        print("FAIL " + p)
    if not problems:
        print("check-manifest: ok: %(lines)d lines (%(top)d top, %(inner)d inner) cover %(covered_files)d files, %(engine_files)d engine files, %(files)d in the inventory" % stats)
        return 0
    print("check-manifest: %d problem(s)" % len(problems))
    return 1


if __name__ == "__main__":
    sys.exit(main())
