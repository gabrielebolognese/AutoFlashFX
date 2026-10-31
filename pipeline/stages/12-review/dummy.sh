#!/usr/bin/env bash
# dummy.sh for 12-review (Review and fix loop, S12): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/12-review/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 12-review review.json
set_activity "reviewing: edit review (round 1/5)"
cat > "$OUT/review.json" <<'JSON'
{"round": 1, "pass": true, "mechanical": {"pass": true}, "style": {"pass": true}, "audio": {"pass": true, "wer": 0.01},
 "edit_review": {"scores": {"stop": 5, "hierarchy": 4, "look": 4, "variety": 4, "sync": 5, "sound": 4, "generic": 4, "requirements": 4},
                 "issues": []}}
JSON
dummy_end
