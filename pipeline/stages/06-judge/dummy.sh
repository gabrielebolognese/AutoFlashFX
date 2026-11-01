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
{"winner": {"id": "h01", "template_id": "v07", "family": "mistake-warning", "spoken": "Your AI site looks fake, one fix", "on_screen": "Your AI site looks fake", "marker": "one"},
 "runner_up": {"id": "h02", "template_id": "v10", "family": "how-to-system", "spoken": "Install this skill in 30 seconds", "on_screen": "30 second install", "marker": "30 seconds"},
 "reasons": ["dummy judge: h01 names the pain, h02 names the time"],
 "criteria": ["stops the scroll", "sets up the problem", "credible", "fits the voice"],
 "filtered_out": [], "hookscore": {"h01": 70, "h02": 66}, "candidates": ["h01", "h02"], "candidates_mode": "survivors",
 "rankings": [], "borda": {"h01": 1, "h02": 0}, "top": ["h01", "h02"], "pairwise": [], "pairwise_wins": {"h01": 2, "h02": 0},
 "regenerated": false, "calls": 3, "checked": "2026-01-01"}
JSON
dummy_end
