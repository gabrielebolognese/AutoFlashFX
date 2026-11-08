#!/usr/bin/env python
"""m17-summary.py: the numbers of build/M17/report.md, as markdown tables, from the files of build/M17 (M17).

  python pipeline/tests/m17-summary.py [--dir build/M17]

Prints: what moves where (counts and sizes per destination), the refindex counts per subject and kind (M18's size), the old paths inside
data per bucket, the baseline per test. Read-only.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ml  # noqa: E402


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def main():
    ml.out_stream()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ml.default_root(), "build", "M17"))
    d = ap.parse_args().dir
    rows = ml.read_tsv(os.path.join(d, "move-manifest.tsv"))[1]
    print("### Destinations\n")
    print("| destination | lines | files | size | methods |")
    print("|---|---|---|---|---|")
    dest = collections.OrderedDict()
    for r in rows:
        if r["scope"] != "top":
            continue
        if r["method"] == "stays":
            key = "stays at the root"
        elif r["new"].startswith("channels/"):
            key = "channels/" + r["new"].split("/")[1] + "/" + (r["new"].split("/")[2] if r["new"].count("/") > 1 else "")
            key = key.rstrip("/")
            if r["new"].startswith("channels/flashfx/logs/"):
                key = "channels/flashfx/logs/"
            elif r["new"] in ("channels/flashfx/ideas.txt",):
                key = "channels/flashfx/ideas.txt"
            else:
                key = key + "/"
        else:
            key = r["new"].split("/")[0] + "/ (renamed in place)"
        e = dest.setdefault(key, {"lines": 0, "files": 0, "bytes": 0, "methods": set()})
        e["lines"] += 1
        e["files"] += int(r["files"])
        e["bytes"] += int(r["bytes"])
        e["methods"].add(r["method"])
    for k, e in dest.items():
        print("| %s | %d | %d | %s | %s |" % (k, e["lines"], e["files"], human(e["bytes"]), ", ".join(sorted(e["methods"]))))
    inner = collections.Counter((r["ms"], r["method"]) for r in rows if r["scope"] == "inner")
    print("\nInner lines (renames and rewrites inside moved folders): %s" % (", ".join("%s %s %d" % (k[0], k[1], v) for k, v in sorted(inner.items())) or "none today (no runs/ and no exports/ yet)"))

    ref = ml.read_tsv(os.path.join(d, "refindex.tsv"))[1]
    print("\n### M18's size: the refindex (rooted occurrences)\n")
    print("| subject | code | comment | prompt | doc | test | fixture | data | config |")
    print("|---|---|---|---|---|---|---|---|---|")
    cnt = collections.Counter((r["subject"], r["kind"]) for r in ref if r["rooted"] == "yes")
    for subj in ("path", "export-name", "config-key", "config-read"):
        print("| %s | %s |" % (subj, " | ".join(str(cnt[(subj, k)]) for k in ("code", "comment", "prompt", "doc", "test", "fixture", "data", "config"))))
    files = collections.Counter()
    for r in ref:
        if r["rooted"] == "yes" and r["kind"] == "code":
            files[r["file"]] += 1
    print("\nTotal %d occurrences in %d files (%d not rooted: nothing to change). Files with the most paths built in code:\n" % (
        len(ref), len(set(r["file"] for r in ref)), len([r for r in ref if r["rooted"] == "no"])))
    for f, n in files.most_common(12):
        print("- %s: %d" % (f, n))
    data = ml.read_tsv(os.path.join(d, "refindex-data.tsv"))[1]
    print("\n### Old paths inside data (refindex-data.tsv)\n")
    print("| bucket | git | forms | occurrences |")
    print("|---|---|---|---|")
    agg = collections.OrderedDict()
    for r in data:
        e = agg.setdefault((r["bucket"], r["git"]), {"forms": set(), "occ": 0})
        e["forms"].add(r["form"])
        e["occ"] += int(r["occurrences"])
    for (b, g), e in agg.items():
        print("| %s | %s | %s | %d |" % (b, g, ", ".join(sorted(e["forms"])), e["occ"]))
    bp = os.path.join(d, "baseline", "results.tsv")
    if os.path.exists(bp):
        print("\n### Baseline\n")
        print("| test | sections | status | passed | failed | seconds |")
        print("|---|---|---|---|---|---|")
        for r in ml.read_tsv(bp)[1]:
            print("| %s | %s | %s | %s | %s | %s |" % (r["test"], r["sections"], r["status"], r["passed"], r["failed"], r["seconds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
