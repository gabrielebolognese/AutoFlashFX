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
 "captions": [{"scene": "s2", "start_ms": 1500, "end_ms": 2300, "words": [{"word": "Your", "start_ms": 1500, "end_ms": 1700, "emphasis": false}, {"word": "AI", "start_ms": 1700, "end_ms": 1900, "emphasis": false}, {"word": "site", "start_ms": 1900, "end_ms": 2200, "emphasis": false}]},
              {"scene": "s2", "start_ms": 2310, "end_ms": 3400, "words": [{"word": "looks", "start_ms": 2310, "end_ms": 2600, "emphasis": false}, {"word": "fake.", "start_ms": 2600, "end_ms": 3000, "emphasis": true}]}],
 "overrides": [{"scene": "s2", "component": "s2-card-1", "prop": "title", "text": "Clients spot it"}],
 "cards": [{"scene": "s1", "component": "s1-headline-1", "prop": "kicker", "text": "AI SITES", "zone": "hero", "words": 2},
           {"scene": "s2", "component": "s2-card-1", "prop": "title", "text": "Clients spot it", "zone": "hero", "words": 3},
           {"scene": "s3", "component": "s3-end-card-1", "prop": "keyword", "text": "SKILL", "zone": "hero", "words": 1}],
 "labels": [{"scene": "s1", "component": "s1-headline-1", "text": "AI SITES", "kind": "kicker"}],
 "notes": "dummy text pass"}
JSON
dummy_end
