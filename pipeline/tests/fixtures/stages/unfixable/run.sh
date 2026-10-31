#!/usr/bin/env bash
# Test fixture "unfixable" (installed by test-m3.sh as pipeline/stages/10-build/run.sh in a sandbox): needs a key
# file that only the user can create, so no automatic fix is possible; once the user creates it, the stage writes a
# valid events.json. Usage: run.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
RUN_DIR="${1:?usage: run.sh <run_dir>}"
KEY="$REELS_ROOT/library/keys/service.key"
echo "stage: reading the service key from library/keys/service.key"
if [ ! -f "$KEY" ]; then
  echo "FileNotFoundError: library/keys/service.key is missing: this stage needs the API key file that only the user can create" >&2
  exit 1
fi
echo "stage: key found, building events.json"
OUT="$RUN_DIR/10-build"
mkdir -p "$OUT"
cat > "$OUT/events.json" <<JSON
{"composition": "project/index.html", "duration_ms": 30000,
 "events": [{"ms": 0, "type": "hook_hit", "component": "hero-card", "scene": "s1", "scene_change": false, "transition_ms": 0}]}
JSON
echo "stage: done"
