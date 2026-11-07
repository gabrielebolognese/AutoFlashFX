#!/usr/bin/env bash
# the earlier milestones' tests after the changes of M15 (one after another, one log each in build/M15/earlier-tests/)
cd "$(dirname "$0")/../.." || exit 1
mkdir -p build/M15/earlier-tests
run() {  # run <name> <env assignments..., then the command>
  local name="$1"; shift
  local t0=$SECONDS
  env "$@" > "build/M15/earlier-tests/$name.log" 2>&1
  printf '%s: %s, %s s\n' "$name" "$(grep -E ': [0-9]+ passed, [0-9]+ failed' "build/M15/earlier-tests/$name.log" | tail -n 1)" "$((SECONDS - t0))" >> build/M15/earlier-tests/summary.txt
}
: > build/M15/earlier-tests/summary.txt
mv build/M15/earlier-tests/m10.log build/M15/earlier-tests/m10-first-run.log 2>/dev/null
run m11 M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh
run m9 bash pipeline/tests/test-m9.sh
run m14 M14_SECTIONS="2 4 5" bash pipeline/tests/test-m14.sh
run m6 M6_SECTIONS="1 2" bash pipeline/tests/test-m6.sh
run m12 M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh
run m13 M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh
run m15 bash pipeline/tests/test-m15.sh
run m10 M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh
echo done >> build/M15/earlier-tests/summary.txt
