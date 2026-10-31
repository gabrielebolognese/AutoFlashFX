#!/usr/bin/env bash
# run-all.sh: run every test-*.sh in this folder (the milestone tests test-m<n>.sh in order, then the unit tests
# such as test-limits.sh and test-no-emdash.sh). Exit non-zero when any of them fails.
# Extra arguments (for example --quick) are passed to each test.
#   bash pipeline/tests/run-all.sh
set -u
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failed=()
ran=0
while IFS= read -r t; do
  [ -f "$t" ] || continue
  printf '\n######## %s ########\n' "$(basename "$t")"
  if ! bash "$t" "$@"; then failed+=("$(basename "$t")"); fi
  ran=$((ran + 1))
done < <( { ls "$TESTS_DIR"/test-m*.sh 2>/dev/null | sort -V; ls "$TESTS_DIR"/test-*.sh 2>/dev/null | grep -v '/test-m[0-9]*\.sh$' | sort; } )
if [ ${#failed[@]} -eq 0 ]; then
  printf '\nrun-all: %d test files, all passed\n' "$ran"
else
  printf '\nrun-all: %d test files, %d failed: %s\n' "$ran" "${#failed[@]}" "${failed[*]}"
  exit 1
fi
