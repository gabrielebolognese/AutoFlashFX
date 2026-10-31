#!/usr/bin/env bash
# dummy.sh for 09a-animations (Visual plan, animations pass, S9a): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/09a-animations/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 09a-animations plan.json
cat > "$OUT/plan.json" <<'JSON'
{"pass": "animations",
 "scenes": [
  {"id": "s1", "beat": "b1", "start_ms": 0, "end_ms": 1500, "component": "hero-card", "props": {"text": "Your AI site looks fake"}, "enter": "rise", "exit": "cut", "emphasis_hits": [{"word": "fake", "ms": 1110, "effect": "stamp"}], "set_piece": true, "honesty_label": null},
  {"id": "s2", "beat": "b2", "start_ms": 1500, "end_ms": 7000, "component": "caption-line", "props": {}, "enter": "fade", "exit": "slide", "emphasis_hits": [], "set_piece": false, "honesty_label": null},
  {"id": "s3", "beat": "b6", "start_ms": 27000, "end_ms": 30000, "component": "dm-card", "props": {"keyword": "SKILL"}, "enter": "pop", "exit": "cut", "emphasis_hits": [], "set_piece": false, "honesty_label": "mock"}
 ]}
JSON
dummy_end
