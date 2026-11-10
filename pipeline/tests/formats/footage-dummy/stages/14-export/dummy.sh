#!/usr/bin/env bash
# dummy.sh for 14-export of the test-only footage-dummy format: a fake output that validates against schema.json. No model calls.
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 14-export export.json
set_activity "writing caption"
printf '{"caption": "dummy", "hashtags": ["#test"], "keyword": "X", "deliverable": "none", "deliverable_status": "existing", "hooks": {"hook1": "a", "hook2": "b"}, "files": {"reel": "reel.mp4", "hook2": "hook2.mp4"}}
' > "$OUT/export.json"; printf 'dummy mp4
' > "$OUT/reel.mp4"; printf 'dummy mp4
' > "$OUT/hook2.mp4"
dummy_end
