# pipeline/tests/lib.sh: the test harness shared by every test-m*.sh. Source it.
#
# Tests never touch the real queue, runs, exports or logs: sandbox_init creates a temporary state root and exports
# REELS_ROOT so every script writes there. KEEP_SANDBOX=1 keeps the folder for inspection.
#
#   sandbox_init [--with-pipeline] [--with-visual]
#                                    new temporary root with config.json (voice.wpm set to SANDBOX_WPM when that is
#                                    exported), library text files, an empty ideas.txt;
#                                    --with-pipeline also copies pipeline/ and run.sh and runs git init (so a fixer
#                                    can commit there). Sets SANDBOX (POSIX path) and SANDBOX_M (C:/ form).
#                                    --with-visual (M10) also copies what the visual stages read: motion-lib/
#                                    (compositions, assets, catalog, webgl.json, the stills), styles/paper-cards/
#                                    tokens.json, library/brand/, golden/test-idea/{plan.json, contact-sheet.png,
#                                    README.md}; the Node packages stay in the real repo (REELS_NODE_PREFIX).
#                                    --with-review (M11) also copies the reference analysis summaries and the look
#                                    stills of styles/paper-cards/analysis (the sound pack stays in the real repo:
#                                    REELS_SFX_DIR points at it).
#   sandbox_cleanup                  remove it (also run by the EXIT trap)
#   fast_mode                        REELS_SLEEP_SCALE=0.001 REELS_STATUS_EVERY=2 REELS_POLL_SECONDS=1
#                                    REELS_TICK_SECONDS=0.2 REELS_DUMMY_SECONDS=0.3 (unless already set)
#   fake_claude_on                   put pipeline/tests/fakes first on PATH (POSIX form: a C:/ entry is invisible to
#                                    Git Bash) and point FAKE_CLAUDE_LOG and FAKE_CLAUDE_STATE into the sandbox;
#                                    fails loudly when `command -v claude` is not the fake. fake_claude_off restores
#                                    PATH; fake_claude_reset clears the log and the counters
#   dummy_except STAGE               the REELS_DUMMY list of every stage but that one
#   dummy_after STAGE                the REELS_DUMMY list of every stage after that one
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
  # SANDBOX_WPM pins config voice.wpm in the sandbox (M5 and M6: their frozen fixtures and asserted numbers were
  # made at the user's 195 wpm; since M7 the repo's voice.wpm is the reel voice's measured pace)
  if [ -n "${SANDBOX_WPM:-}" ]; then python "$REPO_DIR/pipeline/lib/voiceprofile.py" set-wpm --config "$SANDBOX_M/config.json" --wpm "$SANDBOX_WPM" >/dev/null; fi
  cp "$REPO_DIR/library/hooks.txt" "$SANDBOX/library/hooks.txt"
  cp "$REPO_DIR"/library/profile/*.txt "$SANDBOX/library/profile/" 2>/dev/null || true
  cp "$REPO_DIR"/library/profile/*.md "$SANDBOX/library/profile/" 2>/dev/null || true
  : > "$SANDBOX/ideas.txt"
  export REELS_ROOT="$SANDBOX_M"
  local with_pipeline=0 with_visual=0 with_review=0 a
  for a in "$@"; do
    case "$a" in --with-pipeline) with_pipeline=1 ;; --with-visual) with_pipeline=1; with_visual=1 ;; --with-review) with_pipeline=1; with_visual=1; with_review=1 ;; esac
  done
  if [ "$with_pipeline" = 1 ]; then
    # a copy of the code as its own git repo, so a fixer commits there and never in the real repo; the style text
    # files and .gitattributes come along because the preflight and the line-ending rules need them
    cp -r "$REPO_DIR/pipeline" "$SANDBOX/pipeline"
    rm -rf "$SANDBOX"/pipeline/lib/__pycache__ "$SANDBOX"/pipeline/tests/fakes/__pycache__
    cp "$REPO_DIR/run.sh" "$SANDBOX/run.sh"
    mkdir -p "$SANDBOX/tools"; cp "$REPO_DIR"/tools/*.py "$SANDBOX/tools/" 2>/dev/null || true   # tools/voice.py: the voiceover's engine code (M7)
    cp "$REPO_DIR/.gitattributes" "$SANDBOX/.gitattributes" 2>/dev/null || true
    mkdir -p "$SANDBOX/styles/paper-cards" "$SANDBOX/motion-lib/candidates"
    cp "$REPO_DIR"/styles/paper-cards/*.md "$SANDBOX/styles/paper-cards/" 2>/dev/null || true
    : > "$SANDBOX/motion-lib/candidates/.gitkeep"
    # what the hard preflight checks of M10 read under the repo: tokens.json, the catalog, the brand kit, the Node package
    cp "$REPO_DIR/styles/paper-cards/tokens.json" "$SANDBOX/styles/paper-cards/tokens.json" 2>/dev/null || true
    cp "$REPO_DIR/motion-lib/catalog.json" "$SANDBOX/motion-lib/catalog.json" 2>/dev/null || true
    cp -r "$REPO_DIR/library/brand" "$SANDBOX/library/brand" 2>/dev/null || true
    mkdir -p "$SANDBOX/node_modules/hyperframes"
    cp "$REPO_DIR/node_modules/hyperframes/package.json" "$SANDBOX/node_modules/hyperframes/package.json" 2>/dev/null || printf '{"name": "hyperframes", "version": "sandbox"}
' > "$SANDBOX/node_modules/hyperframes/package.json"
    if [ "$with_visual" = 1 ]; then
      for d in compositions assets; do cp -r "$REPO_DIR/motion-lib/$d" "$SANDBOX/motion-lib/$d"; done
      for f in catalog.json webgl.json hyperframes.json meta.json index.html; do cp "$REPO_DIR/motion-lib/$f" "$SANDBOX/motion-lib/$f" 2>/dev/null || true; done
      mkdir -p "$SANDBOX/motion-lib/gallery"; cp -r "$REPO_DIR/motion-lib/gallery/stills" "$SANDBOX/motion-lib/gallery/stills" 2>/dev/null || true
      mkdir -p "$SANDBOX/golden/test-idea"
      for f in plan.json contact-sheet.png README.md; do cp "$REPO_DIR/golden/test-idea/$f" "$SANDBOX/golden/test-idea/$f" 2>/dev/null || true; done
      export REELS_NODE_PREFIX="$(mixed "$REPO_DIR")"
    fi
    if [ "$with_review" = 1 ]; then
      # what the review stage reads (M11): the reference analysis summaries and a few look stills (the folder is not
      # in git: the real one is copied when it exists), tools/analyze_refs.py is already in tools/
      local v
      for v in "$REPO_DIR"/styles/paper-cards/analysis/v*/; do
        [ -f "$v/summary.json" ] || continue
        mkdir -p "$SANDBOX/styles/paper-cards/analysis/$(basename "$v")"
        cp "$v/summary.json" "$SANDBOX/styles/paper-cards/analysis/$(basename "$v")/"
        case "$(basename "$v")" in v01|v02) cp "$v"/full_*.png "$SANDBOX/styles/paper-cards/analysis/$(basename "$v")/" 2>/dev/null || true ;; esac
      done
      cp "$REPO_DIR/styles/paper-cards/analysis/accent_share.txt" "$SANDBOX/styles/paper-cards/analysis/" 2>/dev/null || true
    fi
    printf 'runs/
exports/
logs/
.locks/
__pycache__/
*.pyc
library/voice/
' > "$SANDBOX/.gitignore"
    git -C "$SANDBOX" init -q
    git -C "$SANDBOX" config user.name "test"
    git -C "$SANDBOX" config user.email "test@localhost"
    git -C "$SANDBOX" add -A 2>/dev/null
    git -C "$SANDBOX" commit -q -m "sandbox" 2>/dev/null
  fi
}

FAKES_DIR="$TESTS_DIR/fakes"
PATH_BEFORE_FAKE=""
FAKE_DIR=""

fake_claude_on() {
  [ -n "$PATH_BEFORE_FAKE" ] || PATH_BEFORE_FAKE="$PATH"
  export PATH="$FAKES_DIR:$PATH_BEFORE_FAKE"
  # the log and the counters live outside the sandbox: inside it the fixer's tree guard would see the log grow
  # during a fixer call and put it back (an untracked file outside pipeline/ that changed)
  [ -n "$FAKE_DIR" ] || FAKE_DIR="$(mixed "$(mktemp -d)")"
  export FAKE_CLAUDE_LOG="$FAKE_DIR/fake-claude.log"
  export FAKE_CLAUDE_STATE="$FAKE_DIR/fake-claude-state"
  fake_claude_reset
  if [ "$(command -v claude)" != "$FAKES_DIR/claude" ]; then
    printf 'FATAL: the fake claude is not first on PATH (command -v claude = %s)
' "$(command -v claude)"
    exit 2
  fi
}

fake_claude_off() {
  if [ -n "$PATH_BEFORE_FAKE" ]; then export PATH="$PATH_BEFORE_FAKE"; fi
  unset FAKE_CLAUDE_LOG FAKE_CLAUDE_STATE FAKE_CLAUDE_MODE FAKE_CLAUDE_SCRIPT FAKE_CLAUDE_REVIEW FAKE_CLAUDE_FIX FAKE_CLAUDE_REPEAT FAKE_CLAUDE_TAMPER_FILE
}

fake_claude_reset() {
  rm -rf "${FAKE_CLAUDE_STATE:-/nonexistent}" 2>/dev/null
  mkdir -p "${FAKE_CLAUDE_STATE:-/tmp/fake-claude-state}"
  : > "${FAKE_CLAUDE_LOG:-/dev/null}"
}

dummy_except() {  # dummy_except <stage key> -> the REELS_DUMMY list of every other stage
  python "$REPO_DIR/pipeline/lib/state.py" stages | cut -f1 | grep -v -x -- "$1" | paste -sd,
}

dummy_after() {  # dummy_after <stage key> -> the REELS_DUMMY list of every stage after that one (the real ones run up to it)
  python "$REPO_DIR/pipeline/lib/state.py" stages | cut -f1 | awk -v s="$1" '$0 > s' | paste -sd,
}

sandbox_cleanup() {
  if [ -n "$SANDBOX" ] && [ -d "$SANDBOX" ] && [ -z "${KEEP_SANDBOX:-}" ]; then
    # a render's browser may still hold a handle for a moment (M10): one more try after a pause
    rm -rf "$SANDBOX" 2>/dev/null || { sleep 3; rm -rf "$SANDBOX" 2>/dev/null || rm -rf "$SANDBOX"; }
  fi
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

tests_cleanup() {
  sandbox_cleanup
  if [ -n "$FAKE_DIR" ] && [ -z "${KEEP_SANDBOX:-}" ]; then rm -rf "$FAKE_DIR"; fi
}

trap tests_cleanup EXIT
