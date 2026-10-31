#!/usr/bin/env bash
# dummy.sh for 09c-transitions (Visual plan, transitions pass, S9c): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/09c-transitions/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 09c-transitions plan.json
cat > "$OUT/plan.json" <<'JSON'
{"pass": "transitions",
 "transitions": [{"from": "s1", "to": "s2", "type": "slide", "duration_ms": 300}, {"from": "s2", "to": "s3", "type": "cut", "duration_ms": 0}]}
JSON
dummy_end
