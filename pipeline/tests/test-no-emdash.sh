#!/usr/bin/env bash
# test-no-emdash.sh: no em dash (U+2014) in any tracked or new text file, except channels/*/library/hooks.txt (the user's
# file) and pipeline/vendor/ (third-party code). Checks bytes with Python, not grep.
#   bash pipeline/tests/test-no-emdash.sh
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
if python "$TESTS_DIR/no_emdash.py"; then
  pass "no em dash in tracked text files"
else
  fail "em dash found (see the lines above)"
fi
test_summary
