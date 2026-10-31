#!/usr/bin/env bash
# dummy.sh for 10-build (Build visuals and draft render, S10): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/10-build/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 10-build events.json
cat > "$OUT/events.json" <<'JSON'
{"composition": "project/index.html", "duration_ms": 30000,
 "events": [{"ms": 0, "type": "hook_hit", "component": "hero-card", "scene": "s1", "scene_change": false, "transition_ms": 0},
            {"ms": 1500, "type": "scene_change", "component": "caption-line", "scene": "s2", "scene_change": true, "transition_ms": 300},
            {"ms": 27000, "type": "notification", "component": "dm-card", "scene": "s3", "scene_change": true, "transition_ms": 0}]}
JSON
mkdir -p "$OUT/project" "$OUT/hook2"
printf '<!-- dummy composition for %s -->\n' "$RUN_ID" > "$OUT/project/index.html"
printf '<!-- dummy hook 2 clip for %s -->\n' "$RUN_ID" > "$OUT/hook2/index.html"
printf 'dummy mp4 (silent draft) for %s\n' "$RUN_ID" > "$OUT/draft.mp4"
dummy_end
