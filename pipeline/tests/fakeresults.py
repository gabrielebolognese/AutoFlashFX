#!/usr/bin/env python
"""fakeresults.py: the bookkeeping of pipeline/tests/run-fake.sh (M17).

  python pipeline/tests/fakeresults.py parse <log> <name> <sections> <rc> <seconds>   one TSV row, FAIL lines to stdout after it
  python pipeline/tests/fakeresults.py compare <baseline-dir> <new-dir>              the baseline rule of M17

The baseline rule (BUILD_SPEC.md 12, M17): no test that passed in the baseline fails now. A known failure that now
passes is fine. Durations are recorded, never compared. The comparison works per test file and per failing assertion:
a test file that passed must pass, and a FAIL line that is not in the baseline's failures of the same file is new.
"""
import csv
import json
import os
import re
import sys

PASSED_RE = re.compile(r":\s+(\d+) passed,\s+(\d+) failed")
FAIL_RE = re.compile(r"^FAIL\s+(.*)$")


def parse(log, name, sections, rc, seconds):
    passed = failed = None
    fails = []
    with open(log, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            m = PASSED_RE.search(line)
            if m:
                passed, failed = int(m.group(1)), int(m.group(2))
            m = FAIL_RE.match(line)
            if m:
                fails.append(m.group(1).strip())
    rc = int(rc)
    if rc == 124:
        status = "timeout"
    elif passed is None:
        status = "pass" if rc == 0 else "error"
    elif rc == 0 and not failed:
        status = "pass"
    else:
        status = "fail"
    row = [name, sections, status, "" if passed is None else passed, "" if failed is None else failed, rc, seconds, log]
    return row, fails


def read_results(d):
    rows = {}
    p = os.path.join(d, "results.tsv")
    if os.path.exists(p):
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                rows[r["test"]] = r
    fails = {}
    p = os.path.join(d, "failures.tsv")
    if os.path.exists(p):
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.reader(f, delimiter="\t"):
                if len(r) >= 2:
                    fails.setdefault(r[0], set()).add(r[1])
    return rows, fails


def compare(base_dir, new_dir):
    base, base_fails = read_results(base_dir)
    new, new_fails = read_results(new_dir)
    problems = []
    for name, b in sorted(base.items()):
        n = new.get(name)
        if n is None:
            problems.append("%s: in the baseline, not run now" % name)
            continue
        if b["status"] == "pass" and n["status"] != "pass":
            problems.append("%s: passed in the baseline, now %s" % (name, n["status"]))
        extra = new_fails.get(name, set()) - base_fails.get(name, set())
        for e in sorted(extra):
            if b["status"] == "pass" or e:
                problems.append("%s: new failing check: %s" % (name, e))
    fixed = [name for name, b in sorted(base.items()) if b["status"] != "pass" and name in new and new[name]["status"] == "pass"]
    print("baseline rule: %d test files compared, %d problem(s), %d known failure(s) now passing" % (len(base), len(problems), len(fixed)))
    for p in problems:
        print("  PROBLEM " + p)
    for x in fixed:
        print("  FIXED   " + x)
    return 1 if problems else 0


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    if len(argv) >= 7 and argv[1] == "parse":
        row, fails = parse(*argv[2:7])
        print("\t".join(str(x) for x in row))
        for x in fails:
            print("FAILLINE\t" + x)
        return 0
    if len(argv) == 4 and argv[1] == "compare":
        return compare(argv[2], argv[3])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
