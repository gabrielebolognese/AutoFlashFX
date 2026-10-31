#!/usr/bin/env bash
# dummy.sh for 06-judge (Hook judge, S6): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/06-judge/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 06-judge judge.json
cat > "$OUT/judge.json" <<'JSON'
{"winner": {"id": "h1", "family": "mistake-warning", "spoken": "Your AI site looks fake, one fix", "on_screen": "Your AI site looks fake", "marker": "one fix"},
 "runner_up": {"id": "h2", "family": "how-to-system", "spoken": "Install this skill in 30 seconds", "on_screen": "30 second install", "marker": "30 seconds"},
 "reasons": ["dummy judge: h1 names the pain, h2 names the time"], "filtered_out": [], "rankings": []}
JSON
dummy_end
