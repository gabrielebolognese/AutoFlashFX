#!/usr/bin/env bash
# dummy.sh for 01-research (Research, S1): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/01-research/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 01-research research.json
idea_id="$(state_get "$RUN_DIR" idea.id unknown)"
today="$(printf '%(%Y-%m-%d)T' -1)"
cat > "$OUT/research.json" <<JSON
{"idea_id": "$idea_id", "idea": "dummy idea", "checked": "$today", "stage": "01-research",
 "core_claim": {"text": "The dummy tool exists and does what the idea says", "status": "verified", "note": "dummy: seen on the example page"},
 "claims": [{"n": 1, "claim": "The dummy tool exists and is open source", "url": "https://example.com/repo", "tier": "primary", "status": "verified", "checked": "$today", "note": "", "added_by": "01-research"},
            {"n": 2, "claim": "It installs with one command", "url": "https://example.com/docs/install", "tier": "primary", "status": "verified", "checked": "$today", "note": "", "added_by": "01-research"}],
 "numbers": {"stars": {"name": "stars", "value": 1234, "unit": "", "url": "https://example.com/repo", "checked": "$today", "note": ""}},
 "pitfalls": ["needs a recent version", "no Windows ARM build"],
 "one_true_thing": ["one command installs it", "1234 stars"],
 "unverified": [],
 "assets": [],
 "summary": "dummy research",
 "sources": {"primary": 2, "vendor": 0, "press": 0, "forum": 0},
 "counts": {"claims": 2, "verified": 2, "false": 0}}
JSON
{"idea_id": "$idea_id", "checked": "$today",
 "claims": [{"claim": "The dummy tool exists and is open source", "url": "https://example.com/repo", "checked": "$today"},
            {"claim": "It installs with one command", "url": "https://example.com/docs/install", "checked": "$today"}],
 "numbers": {"stars": {"value": 1234, "url": "https://example.com/repo", "checked": "$today"}},
 "pitfalls": ["needs a recent version", "no Windows ARM build"],
 "one_true_thing": ["one command installs it", "1234 stars"],
 "assets": []}
JSON
cat > "$OUT/facts.md" <<MD
# Facts: dummy idea

Checked $today (dummy).

## Claims
1. The dummy tool exists and is open source [primary, verified]: https://example.com/repo (checked $today)
2. It installs with one command [primary, verified]: https://example.com/docs/install (checked $today)
MD
printf '{"stars": {"value": 1234, "url": "https://example.com/repo", "checked": "%s"}}\n' "$today" > "$OUT/numbers.json"
printf '[]\n' > "$OUT/assets.json"
mkdir -p "$OUT/assets"
dummy_end
