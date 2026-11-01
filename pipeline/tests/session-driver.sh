#!/usr/bin/env bash
# session-driver.sh: call session_call once from a plain shell, for the tests (test-m4.sh). Prints one line of
# key=value pairs: rc, class, result, session, out, error, call. REELS_ROOT must point at the sandbox.
#   bash pipeline/tests/session-driver.sh <key> <role> <stage_dir> <prompt_file> [ai options...]
set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
source "$REELS_PIPELINE/lib/log.sh"
source "$REELS_PIPELINE/lib/config.sh"
source "$REELS_PIPELINE/lib/state.sh"
source "$REELS_PIPELINE/lib/status.sh"
source "$REELS_PIPELINE/lib/ai.sh"
source "$REELS_PIPELINE/lib/session.sh"
key="$1"; role="$2"; stage_dir="$3"; prompt="$4"; shift 4
session_call "$key" "$role" "$stage_dir" "$prompt" "$@"; rc=$?
printf 'rc=%s\tclass=%s\tresult=%s\tsession=%s\tout=%s\terror=%s\tcall=%s\n' \
  "$rc" "$AI_CLASS" "$(printf '%s' "$AI_RESULT" | tr '\n\t' '  ')" "$AI_SESSION" "$AI_OUT" "$(printf '%s' "$AI_ERROR" | tr '\n\t' '  ')" "$AI_CALL"
exit $rc
