#!/usr/bin/env bash
# ai-driver.sh: call ai() once from a plain shell, for the tests (test-m3.sh). Prints one line of key=value pairs:
# rc, class, result, session, out, error, fatal, call. REELS_ROOT must point at the sandbox.
#   bash pipeline/tests/ai-driver.sh <role> <stage_dir> <prompt_file> [ai options...]
set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
source "$REELS_PIPELINE/lib/log.sh"
source "$REELS_PIPELINE/lib/config.sh"
source "$REELS_PIPELINE/lib/state.sh"
source "$REELS_PIPELINE/lib/status.sh"
source "$REELS_PIPELINE/lib/ai.sh"
role="$1"; stage_dir="$2"; prompt="$3"; shift 3
ai "$role" "$stage_dir" "$prompt" "$@"; rc=$?
printf 'rc=%s\tclass=%s\tresult=%s\tsession=%s\tout=%s\terror=%s\tfatal=%s\tcall=%s\n' \
  "$rc" "$AI_CLASS" "$(printf '%s' "$AI_RESULT" | tr '\n\t' '  ')" "$AI_SESSION" "$AI_OUT" "$(printf '%s' "$AI_ERROR" | tr '\n\t' '  ')" "$AI_FATAL" "$AI_CALL"
exit $rc
