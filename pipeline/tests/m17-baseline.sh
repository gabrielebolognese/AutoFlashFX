#!/usr/bin/env bash
# m17-baseline.sh: the machine-level part of the baseline of M17 (the test results are run-fake.sh's): the output of preflight and of
# doctor --quick, and the dummy fingerprint, all in a temp copy of the state files (REELS_ROOT), never on the real folder.
#
#   bash pipeline/tests/m17-baseline.sh [--out DIR]       (default: build/M17/baseline)
#
# Writes in DIR: preflight.txt, doctor-quick.txt (the output and the exit code of each), fingerprint-run.txt and
# fingerprint-exports.txt (the tree of the run folder and of the export that `REELS_DUMMY=all bash run.sh --once` made: names only, the
# date and time of run folder names replaced by <ts>), fingerprint-state.txt (the other entries of the state root after the run),
# dummy-run.txt (the terminal lines of that run). M18 and M19 compare their own dummy runs with these files (the paths move,
# the names inside do not; M19 changes the export names).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$REPO/build/M17/baseline"
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "m17-baseline.sh: unknown option '$1'" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT" || exit 2
OUT="$(cd "$OUT" && pwd)"
export PYTHONUTF8=1 NO_COLOR=1
unset REELS_ROOT REELS_COMMON_LOADED REELS_DUMMY

R="$(mktemp -d)"
trap 'rm -rf "$R" 2>/dev/null || { sleep 3; rm -rf "$R" 2>/dev/null; }' EXIT

# the state files: what the video runner keeps at the root (no reference videos, no caches, no renders)
(cd "$REPO" && tar -c --exclude='styles/*/refs' --exclude='styles/*/analysis' --exclude='motion-lib/.harness' --exclude='motion-lib/.hyperframes' \
  --exclude='motion-lib/renders' --exclude='golden/*/golden.mp4' --exclude='golden/*/project/renders' --exclude='.hyperframes' --exclude='.harness' \
  library styles motion-lib golden ideas.txt config.json) | tar -x -C "$R" || { echo "m17-baseline: copying the state files failed" >&2; exit 1; }
printf '{Claude Code'"'"'s frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it.}\n' > "$R/ideas.txt"
RM="$(cygpath -m "$R" 2>/dev/null || echo "$R")"

run_logged() {  # run_logged <file> <command...>: output, then "exit code N"
  local file="$1"; shift
  { "$@" 2>&1; echo "exit code $?"; } > "$file"
}

echo "m17-baseline: preflight"
run_logged "$OUT/preflight.txt" env REELS_ROOT="$RM" bash "$REPO/pipeline/bin/preflight"
echo "m17-baseline: doctor --quick"
run_logged "$OUT/doctor-quick.txt" env REELS_ROOT="$RM" bash "$REPO/pipeline/bin/doctor" --quick

echo "m17-baseline: the dummy run"
rm -rf "$R/logs" "$R/runs" "$R/exports" "$R/.locks"
export REELS_SLEEP_SCALE=0.001 REELS_STATUS_EVERY=2 REELS_POLL_SECONDS=1 REELS_TICK_SECONDS=0.2 REELS_DUMMY_SECONDS=0.3
{ REELS_ROOT="$RM" REELS_DUMMY=all timeout 900 bash "$REPO/run.sh" --once 2>&1; echo "exit code $?"; } > "$OUT/dummy-run.txt"
tree() {  # tree <dir>: relative paths, a trailing slash on folders, sorted bytewise, the run folder's stamp replaced
  (cd "$1" 2>/dev/null && find . -mindepth 1 | sed 's#^\./##' | while IFS= read -r p; do if [ -d "$p" ]; then echo "$p/"; else echo "$p"; fi; done) \
    | sed -E 's/20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{4}/<ts>/g' | LC_ALL=C sort
}
tree "$R/runs" > "$OUT/fingerprint-run.txt"
tree "$R/exports" > "$OUT/fingerprint-exports.txt"
{
  echo "# the state root after the dummy run, apart from the data folders that moved in M18 (library, styles, motion-lib, golden)"
  (cd "$R" && ls -A | LC_ALL=C sort | grep -v -x -e library -e styles -e motion-lib -e golden | while IFS= read -r p; do
     if [ -d "$p" ]; then echo "$p/"; (cd "$p" && find . -mindepth 1 -maxdepth 1 | sed "s#^\./#$p/#" | LC_ALL=C sort | while IFS= read -r q; do if [ -d "$q" ]; then echo "$q/"; else echo "$q"; fi; done); else echo "$p"; fi
   done)
} | sed -E 's/20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{4}/<ts>/g' > "$OUT/fingerprint-state.txt"
n_run="$(grep -c . "$OUT/fingerprint-run.txt")"
n_exp="$(grep -c . "$OUT/fingerprint-exports.txt")"
echo "m17-baseline: dummy run $(tail -n 1 "$OUT/dummy-run.txt"), run tree $n_run entries, exports tree $n_exp entries -> $OUT"
[ "$n_run" -gt 20 ] && [ "$n_exp" -ge 3 ] && grep -q "exit code 0" "$OUT/dummy-run.txt"
