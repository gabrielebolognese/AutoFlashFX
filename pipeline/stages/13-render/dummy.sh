#!/usr/bin/env bash
# dummy.sh for 13-render (Final render, S13): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/13-render/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 13-render render.json
set_activity "rendering hook 2 clip"
cat > "$OUT/render.json" <<'JSON'
{"files": {"reel": "final.mp4", "hook2": "hook2.mp4"},
 "checks": {"width": 1080, "height": 1920, "fps": 30, "duration_ok": true, "codecs_ok": true, "audio": true, "loudness_ok": true, "hook2_seconds": 2.4},
 "pass": true}
JSON
printf 'dummy mp4 (final render) for %s\n' "$RUN_ID" > "$OUT/final.mp4"
printf 'dummy mp4 (hook 2 clip) for %s\n' "$RUN_ID" > "$OUT/hook2.mp4"
dummy_end
