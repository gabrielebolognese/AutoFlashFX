#!/usr/bin/env bash
# Test fixture "aicall" (installed by test-m3.sh as pipeline/stages/10-build/run.sh): one model call through ai()
# (the fake claude in the tests), then a valid events.json. Exercises the limit, transient and error paths of ai()
# inside a running stage. Usage: run.sh <run_dir>
# Knobs: AICALL_ROLE (config role, default indexer), AICALL_SESSION (a session key stored in state.json).
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/ai.sh"
RUN_DIR="${1:?usage: run.sh <run_dir>}"
OUT="$RUN_DIR/10-build"
mkdir -p "$OUT"
set_activity "building visuals"
printf 'Reply with the single word ok.\n' > "$OUT/prompt.md"
if ! ai "${AICALL_ROLE:-indexer}" "$OUT" "$OUT/prompt.md" --tools "" ${AICALL_SESSION:+--session "$AICALL_SESSION"}; then
  echo "10-build: the model call failed: $AI_ERROR" >&2
  exit 1
fi
echo "10-build: model said: $AI_RESULT (session $AI_SESSION)"
cat > "$OUT/events.json" <<JSON
{"composition": "project/index.html", "duration_ms": 30000,
 "events": [{"ms": 0, "type": "hook_hit", "component": "hero-card", "scene": "s1", "scene_change": false, "transition_ms": 0}]}
JSON
echo "10-build: done"
