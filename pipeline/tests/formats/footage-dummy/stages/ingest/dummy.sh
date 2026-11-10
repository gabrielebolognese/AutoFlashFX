#!/usr/bin/env bash
# dummy.sh for ingest of the test-only footage-dummy format: a fake output that validates against schema.json. No model calls.
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" ingest clips.json
set_activity "ingesting clips"
printf '{"written_by": "ingest (dummy)", "clips": []}
' > "$OUT/clips.json"
dummy_end
