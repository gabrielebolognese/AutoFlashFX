# pipeline/tests/lib.sh: the test harness shared by every test-m*.sh. Source it.
#
# Tests never touch the real queue, runs, exports or logs: sandbox_init creates a temporary state root and exports
# REELS_ROOT so every script writes there. KEEP_SANDBOX=1 keeps the folder for inspection. Since M18 the channel's data sits in
# $SANDBOX/channels/flashfx/ (ideas.txt, library/, styles/, motion-lib/, golden/, runs/, logs/; SANDBOX_CH and SANDBOX_CH_M are that
# folder), config.json, pipeline/, exports/ and the global .locks/ at $SANDBOX; REELS_CHANNEL=flashfx is exported.
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
export REELS_CHANNEL="${TEST_CHANNEL:-flashfx}"   # M18: every script needs a channel (BUILD_SPEC.md 14.5); the tests run flashfx

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
  # M18: the data of a channel lives in channels/<id>/ (BUILD_SPEC.md 14.3). The tests run the channel flashfx (TEST_CHANNEL changes it);
  # SANDBOX_CH and SANDBOX_CH_M are its folder (POSIX and C:/ forms), REELS_CHANNEL is exported for every script
  export REELS_CHANNEL="${TEST_CHANNEL:-flashfx}"
  SANDBOX_CH="$SANDBOX/channels/$REELS_CHANNEL"
  SANDBOX_CH_M="$SANDBOX_M/channels/$REELS_CHANNEL"
  local CH="$SANDBOX_CH" REAL_CH="$REPO_DIR/channels/flashfx"
  mkdir -p "$CH/library/profile" "$CH/logs"
  cp "$REPO_DIR/config.json" "$SANDBOX/config.json"
  cp "$REAL_CH/channel.json" "$CH/channel.json"
  python - "$CH/channel.json" "$REELS_CHANNEL" <<'PYEOF'
import json, sys
p, cid = sys.argv[1], sys.argv[2]
d = json.load(open(p, encoding="utf-8"))
d["id"] = cid
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
PYEOF
  # M16 (Motion and energy rules E8, E9): the milestones before it run their frozen low-energy plans and drafts and their editors that fail
  # the same way every round: the energy rules, the energy check, the liveness checks and the early stop are off in their sandboxes
  # (SANDBOX_ENERGY=on turns them on, as test-m16 does)
  if [ "${SANDBOX_ENERGY:-off}" != on ]; then
    python "$REPO_DIR/pipeline/tests/sandbox-config.py" "$SANDBOX_M/config.json"
  fi
  # SANDBOX_WPM pins voice.wpm in the sandbox's channel.json (M5 and M6: their frozen fixtures and asserted numbers were
  # made at the user's 195 wpm; since M7 the channel's voice.wpm is the reel voice's measured pace)
  if [ -n "${SANDBOX_WPM:-}" ]; then python "$REPO_DIR/pipeline/lib/voiceprofile.py" set-wpm --config "$SANDBOX_CH_M/channel.json" --wpm "$SANDBOX_WPM" >/dev/null; fi
  cp "$REAL_CH/library/hooks.txt" "$CH/library/hooks.txt"
  cp "$REAL_CH"/library/profile/*.txt "$CH/library/profile/" 2>/dev/null || true
  cp "$REAL_CH"/library/profile/*.md "$CH/library/profile/" 2>/dev/null || true
  : > "$CH/ideas.txt"
  # what the hard preflight checks read in the channel folder (since M18 they are the channel's, not the repo's): the style files,
  # tokens.json, the sound map, the motion library's catalog and the brand kit; and a candidates folder for the fixer
  mkdir -p "$CH/styles/paper-cards" "$CH/styles/sfx" "$CH/motion-lib/candidates"
  cp "$REAL_CH"/styles/paper-cards/*.md "$CH/styles/paper-cards/" 2>/dev/null || true
  : > "$CH/motion-lib/candidates/.gitkeep"
  cp "$REAL_CH/styles/paper-cards/tokens.json" "$CH/styles/paper-cards/tokens.json" 2>/dev/null || true
  cp "$REAL_CH/styles/sfx/sfx-map.json" "$CH/styles/sfx/sfx-map.json" 2>/dev/null || true
  cp "$REAL_CH/motion-lib/catalog.json" "$CH/motion-lib/catalog.json" 2>/dev/null || true
  cp -r "$REAL_CH/library/brand" "$CH/library/brand" 2>/dev/null || true
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
    mkdir -p "$SANDBOX/node_modules/hyperframes"
    cp "$REPO_DIR/node_modules/hyperframes/package.json" "$SANDBOX/node_modules/hyperframes/package.json" 2>/dev/null || printf '{"name": "hyperframes", "version": "sandbox"}
' > "$SANDBOX/node_modules/hyperframes/package.json"
    if [ "$with_visual" = 1 ]; then
      for d in compositions assets; do cp -r "$REAL_CH/motion-lib/$d" "$CH/motion-lib/$d"; done
      for f in catalog.json webgl.json hyperframes.json meta.json index.html; do cp "$REAL_CH/motion-lib/$f" "$CH/motion-lib/$f" 2>/dev/null || true; done
      mkdir -p "$CH/motion-lib/gallery"; cp -r "$REAL_CH/motion-lib/gallery/stills" "$CH/motion-lib/gallery/stills" 2>/dev/null || true
      mkdir -p "$CH/golden/test-idea"
      for f in plan.json contact-sheet.png README.md; do cp "$REAL_CH/golden/test-idea/$f" "$CH/golden/test-idea/$f" 2>/dev/null || true; done
      export REELS_NODE_PREFIX="$(mixed "$REPO_DIR")"
    fi
    if [ "$with_review" = 1 ]; then
      # what the review stage reads (M11): the reference analysis summaries and a few look stills (the folder is not
      # in git: the real one is copied when it exists), tools/analyze_refs.py is already in tools/
      local v
      for v in "$REAL_CH"/styles/paper-cards/analysis/v*/; do
        [ -f "$v/summary.json" ] || continue
        mkdir -p "$CH/styles/paper-cards/analysis/$(basename "$v")"
        cp "$v/summary.json" "$CH/styles/paper-cards/analysis/$(basename "$v")/"
        case "$(basename "$v")" in v01|v02) cp "$v"/full_*.png "$CH/styles/paper-cards/analysis/$(basename "$v")/" 2>/dev/null || true ;; esac
      done
      cp "$REAL_CH/styles/paper-cards/analysis/accent_share.txt" "$CH/styles/paper-cards/analysis/" 2>/dev/null || true
    fi
    printf 'exports/
logs/
.locks/
.cache/
channels/*/runs/
channels/*/logs/
channels/*/.locks/
channels/*/.cache/
__pycache__/
*.pyc
channels/*/library/voice/
' > "$SANDBOX/.gitignore"
    git -C "$SANDBOX" init -q
    git -C "$SANDBOX" config user.name "test"
    git -C "$SANDBOX" config user.email "test@localhost"
    git -C "$SANDBOX" add -A 2>/dev/null
    git -C "$SANDBOX" commit -q -m "sandbox" 2>/dev/null
  fi
}

resolved_config() {  # resolved_config: the resolved config (engine config.json + channel.json, BUILD_SPEC.md 14.4) of REELS_CHANNEL under REELS_ROOT as a
                     # file; prints its path. For code that takes --config: the channel keys (voice, sfx, lengths, paths) are not in config.json any more
  local out; out="$(mktemp -d)/config.resolved.json"
  python "$REPO_DIR/pipeline/lib/config.py" resolve --out "$out" || return 1
  mixed "$out"
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
