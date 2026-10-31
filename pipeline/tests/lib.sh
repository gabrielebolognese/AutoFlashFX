# pipeline/tests/lib.sh: the test harness shared by every test-m*.sh. Source it.
#
# Tests never touch the real queue, runs, exports or logs: sandbox_init creates a temporary state root and exports
# REELS_ROOT so every script writes there. KEEP_SANDBOX=1 keeps the folder for inspection.
#
#   sandbox_init [--with-pipeline]   new temporary root with config.json, library text files, an empty ideas.txt;
#                                    --with-pipeline also copies pipeline/ and run.sh and runs git init (so a fixer
#                                    can commit there). Sets SANDBOX (POSIX path) and SANDBOX_M (C:/ form).
#   sandbox_cleanup                  remove it (also run by the EXIT trap)
#   fast_mode                        REELS_SLEEP_SCALE=0.001 REELS_STATUS_EVERY=2 REELS_POLL_SECONDS=1
#                                    REELS_TICK_SECONDS=0.2 REELS_DUMMY_SECONDS=0.3 (unless already set)
#   pass / fail "text"               count and print a PASS or FAIL line
#   assert_eq got expected "name"    assert_ne, assert_rc expected actual "name"
#   assert_true "name" cmd args...   assert_false
#   assert_file path "name"          assert_no_file
#   assert_grep pattern file "name"  (extended regex)   assert_not_grep
#   section "title"
#   test_summary                     prints the totals; exits non-zero when anything failed
set -u
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$TESTS_DIR/../.." && pwd)"
FIXTURES="$TESTS_DIR/fixtures"
TEST_NAME="${TEST_NAME:-$(basename "${0:-test}")}"
PASS_N=0
FAIL_N=0
SANDBOX=""
SANDBOX_M=""
export PYTHONUTF8=1
export LANG="${LANG:-C.UTF-8}"
unset REELS_ROOT REELS_COMMON_LOADED

mixed() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi; }

pass() { PASS_N=$((PASS_N + 1)); printf 'PASS  %s\n' "$*"; }
fail() { FAIL_N=$((FAIL_N + 1)); printf 'FAIL  %s\n' "$*"; }
section() { printf '\n== %s ==\n' "$*"; }

assert_eq() { if [ "$1" = "$2" ]; then pass "$3"; else fail "$3 (expected '$2', got '$1')"; fi; }
assert_ne() { if [ "$1" != "$2" ]; then pass "$3"; else fail "$3 (both were '$1')"; fi; }
assert_rc() { if [ "$2" = "$1" ]; then pass "$3"; else fail "$3 (expected exit $1, got $2)"; fi; }
assert_true() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$name"; else fail "$name"; fi; }
assert_false() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then fail "$name"; else pass "$name"; fi; }
assert_file() { if [ -f "$1" ]; then pass "$2"; else fail "$2 (missing file $1)"; fi; }
assert_no_file() { if [ ! -e "$1" ]; then pass "$2"; else fail "$2 (unexpected $1)"; fi; }
assert_grep() {
  if grep -q -E -- "$1" "$2" 2>/dev/null; then pass "$3"; else fail "$3 (no match for '$1' in $2)"; fi
}
assert_not_grep() {
  if grep -q -E -- "$1" "$2" 2>/dev/null; then fail "$3 (unexpected match for '$1' in $2)"; else pass "$3"; fi
}

sandbox_init() {
  sandbox_cleanup
  SANDBOX="$(mktemp -d)"
  SANDBOX_M="$(mixed "$SANDBOX")"
  mkdir -p "$SANDBOX/library/profile" "$SANDBOX/logs"
  cp "$REPO_DIR/config.json" "$SANDBOX/config.json"
  cp "$REPO_DIR/library/hooks.txt" "$SANDBOX/library/hooks.txt"
  cp "$REPO_DIR"/library/profile/*.txt "$SANDBOX/library/profile/" 2>/dev/null || true
  : > "$SANDBOX/ideas.txt"
  export REELS_ROOT="$SANDBOX_M"
  if [ "${1:-}" = "--with-pipeline" ]; then
    cp -r "$REPO_DIR/pipeline" "$SANDBOX/pipeline"
    cp "$REPO_DIR/run.sh" "$SANDBOX/run.sh"
    git -C "$SANDBOX" init -q
    git -C "$SANDBOX" add -A
    git -C "$SANDBOX" -c user.name=test -c user.email=test@localhost commit -q -m "sandbox"
  fi
}

sandbox_cleanup() {
  if [ -n "$SANDBOX" ] && [ -d "$SANDBOX" ] && [ -z "${KEEP_SANDBOX:-}" ]; then rm -rf "$SANDBOX"; fi
  [ -n "$SANDBOX" ] && [ -n "${KEEP_SANDBOX:-}" ] && printf 'sandbox kept: %s\n' "$SANDBOX_M"
  SANDBOX=""
}

fast_mode() {
  export REELS_SLEEP_SCALE=0.001 REELS_STATUS_EVERY=2 REELS_POLL_SECONDS=1 REELS_TICK_SECONDS=0.2
  export REELS_DUMMY_SECONDS="${REELS_DUMMY_SECONDS:-0.3}"
}

test_summary() {
  printf '\n%s: %d passed, %d failed\n' "$TEST_NAME" "$PASS_N" "$FAIL_N"
  [ "$FAIL_N" -eq 0 ]
}

trap sandbox_cleanup EXIT
