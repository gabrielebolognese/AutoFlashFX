#!/usr/bin/env bash
# dummy.sh for timeline-render (M20): fake outputs that validate against schema.json. No model calls.
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" timeline-render render.json
set_activity "rendering timeline"
printf '{"pass": true, "files": {"reel": "final.mp4"}, "frames": 30}\n' > "$OUT/render.json"
printf 'dummy mp4 (timeline render) for %s\n' "$RUN_ID" > "$OUT/final.mp4"
dummy_end
