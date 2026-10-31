#!/usr/bin/env bash
# dummy.sh for 07-script (Script, S7): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/07-script/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 07-script script.json
cat > "$OUT/script.json" <<'JSON'
{"tone": "calm expert", "video_type": "default", "target_seconds": 30, "wpm": 150,
 "beats": [
  {"id": "b1", "type": "hook", "display": "Your AI site looks fake. One fix.", "spoken": "Your AI site looks fake, one fix", "emphasis": ["fake"], "card": "Your AI site looks fake"},
  {"id": "b2", "type": "stake", "display": "If you ship client sites with AI, they can tell.", "spoken": "If you ship client sites with AI, they can tell", "emphasis": ["tell"], "card": "Clients can tell"},
  {"id": "b3", "type": "tool", "display": "Claude Code has a frontend-design skill.", "spoken": "Claude Code has a frontend design skill", "emphasis": ["skill"], "card": "frontend-design skill"},
  {"id": "b4", "type": "step", "display": "One command installs it.", "spoken": "One command installs it", "emphasis": ["One"], "card": "One command"},
  {"id": "b5", "type": "payoff", "display": "Same prompt, a page that reads designed.", "spoken": "Same prompt, a page that reads designed", "emphasis": ["designed"], "card": "Reads designed"},
  {"id": "b6", "type": "ask", "display": "Comment SKILL for the fix.", "spoken": "Comment SKILL for the fix", "emphasis": ["SKILL"], "card": "Comment SKILL"}
 ],
 "ask": {"keyword": "SKILL", "line": "Comment SKILL for the fix."},
 "checks": {"beats": "pass", "detect": 78, "placeholders": 0, "claims": "pass", "ask": 1}}
JSON
dummy_end
