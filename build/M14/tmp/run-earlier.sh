#!/usr/bin/env bash
# run-earlier.sh: the fake-only tests of the milestones M14 touched, one after another, each into its own log under
# build/M14/tmp/, then a summary line per test (M14 report: "the earlier milestones' fake-only tests still pass").
set -u
cd "$(dirname "$0")/../../.."
export PYTHONUNBUFFERED=1
run() {  # run <name> <command...>
  local name="$1"; shift
  local log="build/M14/tmp/earlier-$name.log"
  local t0; t0="$(date +%s)"
  "$@" > "$log" 2>&1
  local rc=$?
  local t1; t1="$(date +%s)"
  printf '%s: exit %s, %s, %s s\n' "$name" "$rc" "$(grep -E '^test-m[0-9]+\.sh: ' "$log" | tail -1)" "$((t1 - t0))" | tee -a build/M14/tmp/earlier-summary.txt
}
: > build/M14/tmp/earlier-summary.txt
run m9 env bash pipeline/tests/test-m9.sh
run m10-fake env M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh
run m11-fake env M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh
run m12-fake env M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh
run m13-fake env M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh
echo "done" >> build/M14/tmp/earlier-summary.txt
