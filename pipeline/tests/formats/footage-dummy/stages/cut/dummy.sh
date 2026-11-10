#!/usr/bin/env bash
# dummy.sh for cut of the test-only footage-dummy format: a fake output that validates against schema.json. No model calls.
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" cut cut.json
set_activity "cutting clips"
printf '{"written_by": "cut (dummy)", "decisions": [], "frames": 0}
' > "$OUT/cut.json"
dummy_end
