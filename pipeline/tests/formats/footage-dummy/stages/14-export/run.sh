#!/usr/bin/env bash
# run.sh for 14-export of the test-only footage-dummy format (M20, BUILD_SPEC.md 14.7). No model.
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

stage_begin "${1:?usage: run.sh <run_dir>}" 14-export export.json
set_activity "writing caption"
printf 'activity: writing caption
'
"$REELS_PY" "$HERE/../../footage.py" export "$RUN_DIR" || stage_fail "14-export failed (see the lines above)"
[ -f "$OUT/export.json" ] || stage_fail "14-export finished without writing export.json"
echo "$STAGE: done"
exit 0
