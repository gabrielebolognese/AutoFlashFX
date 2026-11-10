#!/usr/bin/env bash
# run.sh for cut of the test-only footage-dummy format (M20, BUILD_SPEC.md 14.7). No model.
#   bash run.sh <run_dir>                                                  (started by the runner)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$(cd "$HERE/../../../../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/ai.sh"
source "$LIB/session.sh"
source "$LIB/stage.sh"

stage_begin "${1:?usage: run.sh <run_dir>}" cut cut.json
set_activity "cutting clips"
printf 'activity: cutting clips
'
"$REELS_PY" "$HERE/../../footage.py" cut "$RUN_DIR" || stage_fail "cut failed (see the lines above)"
[ -f "$OUT/cut.json" ] || stage_fail "cut finished without writing cut.json"
echo "$STAGE: done"
exit 0
