#!/usr/bin/env bash
# dummy.sh for 03-gate (Idea gate, S3): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/03-gate/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 03-gate gate.json
cat > "$OUT/gate.json" <<'JSON'
{"round": 1, "scores": {"P": 3, "S": 2, "C": 3}, "F": "ok", "pass": true, "decision": "pass",
 "evidence": {"P": "one first-person problem sentence", "S": "names an identity", "C": "SKILL with a described deliverable",
              "F": "both claims point to facts.md"},
 "reason": "dummy gate: passes"}
JSON
dummy_end
