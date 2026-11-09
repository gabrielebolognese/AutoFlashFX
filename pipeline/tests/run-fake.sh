#!/usr/bin/env bash
# run-fake.sh: run every fake-only test (no model call, no engine call) one after the other and record each result (M17).
#
#   bash pipeline/tests/run-fake.sh [options]
#     --out DIR        where the results go (default: build/M17/baseline)
#     --only a,b       only these test files (names without .sh, for example test-m1,test-m9)
#     --in-place       run the tests in this folder (default: in a throwaway copy made by make-test-copy.sh, so a test that
#                      writes into the folder never changes the real one; use --in-place only for a copy or after M18)
#     --keep-copy      keep the throwaway copy (its path is printed)
#     --compare DIR    after the run, apply the baseline rule against the results in DIR (exit 1 on a problem)
#     --append         keep the results already in --out and add this run's (a test of the same name is replaced)
#     --list           print the tests and their sections, run nothing
#   Environment: RUN_FAKE_TIMEOUT (seconds per test file, default 14400), RUN_FAKE_SKIP (a comma list of test names to leave out).
#
# The list is the fake-only part of CLAUDE.md: test-no-emdash, test-limits, test-m1, test-m2, test-m3 (sections 1 2 3 5 to
# 10), m4 (1 2), m5 (1 2), m6 (1 2), m7 (1 2), m8, m9, m10 (1 2), m11 (1 2 3), m12 (1 2 3 5), m13 (1 2 4), m14, m15, m16
# (1 2 3 4 5 7), and the tests of later milestones that the build adds to TESTS below (test-m17: its fixture sections).
# Not in it, because they call a model or the real engine: m3 section 4, m4 sections 3 and 4, m5 sections 3 and 4, m6 section 3,
# m7 section 3, m10 sections 3 and 4, m11 sections 4 and 5, m12 section 4, m13 section 3, m16 section 6.
#
# Results: <out>/results.tsv (test, sections, status pass|fail|error|timeout, passed, failed, exit code, seconds, log),
# <out>/failures.tsv (test, the text of each FAIL line: the known failures), <out>/logs/<test>.log, <out>/summary.txt.
# The baseline rule used by M18 to M24: no test that passed in the baseline fails (a known failure that now passes is fine).
# Durations are recorded, never compared (the video runner may share the CPU).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
export PYTHONUTF8=1

# name|env assignment for the sections|label
TESTS=(
  "test-no-emdash||all"
  "test-limits||all"
  "test-m1||all"
  "test-m2||all"
  "test-m3|M3_SECTIONS=1 2 3 5 6 7 8 9 10|1 2 3 5 6 7 8 9 10"
  "test-m4|M4_SECTIONS=1 2|1 2"
  "test-m5|M5_SECTIONS=1 2|1 2"
  "test-m6|M6_SECTIONS=1 2|1 2"
  "test-m7|M7_SECTIONS=1 2|1 2"
  "test-m8|M8_SECTIONS=1 2|1 2"
  "test-m9||all"
  "test-m10|M10_SECTIONS=1 2|1 2"
  "test-m11|M11_SECTIONS=1 2 3|1 2 3"
  "test-m12|M12_SECTIONS=1 2 3 5|1 2 3 5"
  "test-m13|M13_SECTIONS=1 2 4|1 2 4"
  "test-m14||all"
  "test-m15||all"
  "test-m16|M16_SECTIONS=1 2 3 4 5 7|1 2 3 4 5 7"
  "test-m17|M17_SECTIONS=1 2 3 4|1 2 3 4"
  "test-models||all"
)

OUT="$REPO/build/M17/baseline"
ONLY=""
INPLACE=0
KEEP=0
COMPARE=""
LIST=0
APPEND=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --in-place) INPLACE=1; shift ;;
    --keep-copy) KEEP=1; shift ;;
    --compare) COMPARE="$2"; shift 2 ;;
    --append) APPEND=1; shift ;;
    --list) LIST=1; shift ;;
    -h|--help) sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "run-fake.sh: unknown option '$1'" >&2; exit 2 ;;
  esac
done

if [ "$LIST" = 1 ]; then
  for e in "${TESTS[@]}"; do IFS='|' read -r name envs label <<<"$e"; printf '%s\t%s\n' "$name" "$label"; done
  exit 0
fi

selected() {
  local n="$1"
  if [ -n "${RUN_FAKE_SKIP:-}" ]; then case ",$RUN_FAKE_SKIP," in *",$n,"*) return 1 ;; esac; fi
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$n,"*) return 0 ;; esac
  return 1
}

mkdir -p "$OUT/logs" || exit 2
OUT="$(cd "$OUT" && pwd)"
if [ "$APPEND" = 0 ] || [ ! -s "$OUT/results.tsv" ]; then
  : > "$OUT/failures.tsv"
  printf 'test\tsections\tstatus\tpassed\tfailed\texit\tseconds\tlog\n' > "$OUT/results.tsv"
fi

WORK="$REPO"
COPY=""
if [ "$INPLACE" = 0 ]; then
  COPY="$(mktemp -d)/repo"
  echo "run-fake: making a throwaway copy of the repo in $COPY"
  if ! bash "$HERE/make-test-copy.sh" "$COPY" >"$OUT/logs/_copy.log" 2>&1; then
    echo "run-fake: the copy failed, see $OUT/logs/_copy.log" >&2
    exit 2
  fi
  WORK="$COPY"
fi
cleanup() {
  if [ -n "$COPY" ] && [ "$KEEP" = 0 ]; then rm -rf "$(dirname "$COPY")" 2>/dev/null || true; fi
}
trap cleanup EXIT

TMO="${RUN_FAKE_TIMEOUT:-14400}"
started="$(date +%s)"
ran=0
bad=0
for e in "${TESTS[@]}"; do
  IFS='|' read -r name envs label <<<"$e"
  selected "$name" || continue
  script="$WORK/pipeline/tests/$name.sh"
  if [ ! -f "$script" ]; then echo "run-fake: $name.sh does not exist yet, skipped"; continue; fi
  log="$OUT/logs/$name.log"
  if [ "$APPEND" = 1 ]; then   # a test of the same name is replaced
    grep -v -P "^$name\t" "$OUT/results.tsv" > "$OUT/.r"; mv "$OUT/.r" "$OUT/results.tsv"
    grep -v -P "^$name\t" "$OUT/failures.tsv" > "$OUT/.f"; mv "$OUT/.f" "$OUT/failures.tsv"
  fi
  printf '%s run-fake: %s (sections: %s)\n' "$(date +%H:%M:%S)" "$name" "$label"
  t0="$(date +%s)"
  (
    cd "$WORK" || exit 99
    if [ -n "$envs" ]; then export "${envs%%=*}=${envs#*=}"; fi
    exec timeout "$TMO" bash "pipeline/tests/$name.sh"
  ) >"$log" 2>&1
  rc=$?
  secs=$(( $(date +%s) - t0 ))
  python "$HERE/fakeresults.py" parse "$log" "$name" "$label" "$rc" "$secs" > "$OUT/.row" 2>>"$OUT/logs/_copy.log"
  head -n 1 "$OUT/.row" | sed "s#\t[^\t]*\$#\t${log#$REPO/}#" >> "$OUT/results.tsv"
  tail -n +2 "$OUT/.row" | sed "s/^FAILLINE\t//" | while IFS= read -r l; do printf '%s\t%s\n' "$name" "$l" >> "$OUT/failures.tsv"; done
  rm -f "$OUT/.row"
  status="$(tail -n 1 "$OUT/results.tsv" | cut -f3)"
  printf '%s run-fake: %s %s in %ss\n' "$(date +%H:%M:%S)" "$name" "$status" "$secs"
  ran=$((ran + 1))
  [ "$status" = pass ] || bad=$((bad + 1))
done

{
  printf 'run-fake: %d test files, %d not passing, %d seconds, %s\n' "$ran" "$bad" "$(( $(date +%s) - started ))" "$([ "$INPLACE" = 1 ] && echo 'in place' || echo 'in a throwaway copy')"
  column -t -s "$(printf '\t')" "$OUT/results.tsv" 2>/dev/null || cat "$OUT/results.tsv"
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
if [ "$KEEP" = 1 ] && [ -n "$COPY" ]; then echo "run-fake: the copy is kept in $COPY"; fi

rc=0
if [ -n "$COMPARE" ]; then
  python "$HERE/fakeresults.py" compare "$COMPARE" "$OUT" || rc=1
fi
exit $rc
