#!/usr/bin/env bash
# dummy.sh for 05-hooks (Hooks, S5): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/05-hooks/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 05-hooks hooks.json
cat > "$OUT/hooks.json" <<'JSON'
{"idea_id": "dummy", "written_by": "05-hooks dummy", "checked": "2026-01-01", "wpm": 150, "max_spoken_words": 7,
 "templates_considered": 12, "families": ["how-to-system", "mistake-warning", "tools-listicle"], "rule_errors": [],
 "hooks": [
  {"id": "h01", "template_id": "v07", "family": "mistake-warning", "spoken": "Your AI site looks fake, one fix", "on_screen": "Your AI site looks fake", "marker": "one", "marker_kind": "number"},
  {"id": "h02", "template_id": "v10", "family": "how-to-system", "spoken": "Install this skill in 30 seconds", "on_screen": "30 second install", "marker": "30 seconds", "marker_kind": "time"},
  {"id": "h03", "template_id": "v11", "family": "tools-listicle", "spoken": "3 signs a site was AI built", "on_screen": "3 signs of AI sites", "marker": "3", "marker_kind": "number"},
  {"id": "h04", "template_id": "v02", "family": "mistake-warning", "spoken": "Stop shipping generic Claude Code pages", "on_screen": "Stop shipping generic pages", "marker": "Claude Code", "marker_kind": "tool"}
 ]}
JSON
printf '# Brief (dummy)\n\nHook 1 and hook 2 come from 06-judge/judge.json. Facts in 01-research/facts.md. Keyword SKILL.\n' > "$OUT/brief.md"
dummy_end
