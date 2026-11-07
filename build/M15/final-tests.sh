#!/usr/bin/env bash
# the final runs after the last changes of M15 (one driver, one after another; logs in build/M15/final-tests/)
cd "$(dirname "$0")/../.." || exit 1
mkdir -p build/M15/final-tests
: > build/M15/final-tests/summary.txt
run() {
  local name="$1"; shift
  local t0=$SECONDS
  env "$@" > "build/M15/final-tests/$name.log" 2>&1
  printf '%s: %s, %s s\n' "$name" "$(grep -E ': [0-9]+ passed, [0-9]+ failed' "build/M15/final-tests/$name.log" | tail -n 1)" "$((SECONDS - t0))" >> build/M15/final-tests/summary.txt
}
run m14 M14_SECTIONS="2 4 5" bash pipeline/tests/test-m14.sh
run m15 bash pipeline/tests/test-m15.sh
run m11 M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh
run m13 M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh
run m10 M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh
echo done >> build/M15/final-tests/summary.txt
