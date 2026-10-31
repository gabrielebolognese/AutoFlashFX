#!/usr/bin/env bash
# dummy.sh for 09b-text (Visual plan, text pass, S9b): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/09b-text/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 09b-text plan.json
cat > "$OUT/plan.json" <<'JSON'
{"pass": "text",
 "cards": [{"scene": "s1", "text": "Your AI site looks fake", "zone": "center"}, {"scene": "s3", "text": "Comment SKILL", "zone": "lower"}],
 "captions": [{"start_ms": 0, "end_ms": 800, "words": ["Your", "AI", "site"], "emphasis": null},
              {"start_ms": 810, "end_ms": 1500, "words": ["looks", "fake"], "emphasis": "fake"}],
 "labels": [{"scene": "s3", "text": "mock", "kind": "honesty"}]}
JSON
dummy_end
