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
{"templates_considered": 12, "families": ["tools-listicle", "mistake-warning", "how-to-system"],
 "hooks": [
  {"id": "h1", "template_id": "t01", "family": "mistake-warning", "spoken": "Your AI site looks fake, one fix", "on_screen": "Your AI site looks fake", "marker": "one fix"},
  {"id": "h2", "template_id": "t02", "family": "how-to-system", "spoken": "Install this skill in 30 seconds", "on_screen": "30 second install", "marker": "30 seconds"},
  {"id": "h3", "template_id": "t03", "family": "tools-listicle", "spoken": "3 signs a site was AI built", "on_screen": "3 signs of AI sites", "marker": "3"},
  {"id": "h4", "template_id": "t04", "family": "mistake-warning", "spoken": "Stop shipping generic AI pages", "on_screen": "Stop shipping generic pages", "marker": "Claude Code"}
 ]}
JSON
printf '# Brief (dummy)\n\nHook 1 candidates above. Facts in 01-research/facts.md. Keyword SKILL.\n' > "$OUT/brief.md"
dummy_end
