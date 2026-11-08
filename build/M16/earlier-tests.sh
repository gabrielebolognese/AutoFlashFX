#!/usr/bin/env bash
# build/M16/earlier-tests.sh: the earlier milestones' tests whose code M16 touched (fake-only sections), one log each under
# build/M16/earlier-tests/. Run: bash build/M16/earlier-tests.sh
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
mkdir -p build/M16/earlier-tests
run() {  # run <name> <env assignments...> -- <command...>
  local name="$1"; shift
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done
  shift
  local t0=$SECONDS
  env "${envs[@]}" "$@" > "build/M16/earlier-tests/$name.log" 2>&1
  local rc=$?
  printf '%s: exit %s, %s passed, %s failed, %s s\n' "$name" "$rc" "$(grep -c '^PASS' "build/M16/earlier-tests/$name.log")" "$(grep -c '^FAIL' "build/M16/earlier-tests/$name.log")" "$((SECONDS - t0))" | tee -a build/M16/earlier-tests/summary.txt
}
: > build/M16/earlier-tests/summary.txt
run test-m9 X=1 -- bash pipeline/tests/test-m9.sh
run test-m10 M10_SECTIONS="1 2" -- bash pipeline/tests/test-m10.sh
run test-m11 M11_SECTIONS="1 2 3" -- bash pipeline/tests/test-m11.sh
run test-m12 M12_SECTIONS="1 2 3 5" -- bash pipeline/tests/test-m12.sh
run test-m13 M13_SECTIONS="1 2 4" -- bash pipeline/tests/test-m13.sh
run test-m14 M14_SECTIONS="2 4 5" -- bash pipeline/tests/test-m14.sh
run test-m15 X=1 -- bash pipeline/tests/test-m15.sh
run test-no-emdash X=1 -- bash pipeline/tests/test-no-emdash.sh
run test-m2 X=1 -- bash pipeline/tests/test-m2.sh
echo done >> build/M16/earlier-tests/summary.txt
