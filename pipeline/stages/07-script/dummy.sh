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
{"written_by": "07-script dummy", "tone": "calm expert", "tones": ["calm expert", "insider"], "picked": "a", "video_type": "default",
 "length_s": [25, 40], "target_seconds": 32.5, "estimated_seconds": 30.2, "wpm": 150, "words": 76, "rounds": 1,
 "hook": {"id": "h01", "spoken": "Your AI site looks fake. One fix.", "on_screen": "Your AI site looks fake", "family": "mistake-warning"},
 "hook2": {"id": "h02", "display": "5 AI tells on your site.", "spoken": "five AI tells on your site", "card": "5 AI tells"},
 "beats": [
  {"id": "b1", "type": "hook", "display": "Your AI site looks fake. One fix.", "spoken": "Your AI site looks fake, one fix", "emphasis": ["fake"], "card": "Your AI site looks fake", "card_words": 5},
  {"id": "b2", "type": "stake", "display": "If you ship client sites with AI, they can tell.", "spoken": "If you ship client sites with AI, they can tell", "emphasis": ["tell"], "card": "Clients can tell", "card_words": 3},
  {"id": "b3", "type": "tool", "display": "Claude Code has a frontend-design skill.", "spoken": "Claude Code has a frontend design skill", "emphasis": ["skill"], "card": "frontend-design skill", "card_words": 2},
  {"id": "b4", "type": "step", "display": "One command installs it.", "spoken": "One command installs it", "emphasis": ["One"], "card": "One command", "card_words": 2},
  {"id": "b5", "type": "payoff", "display": "Same prompt, a page that reads designed.", "spoken": "Same prompt, a page that reads designed", "emphasis": ["designed"], "card": "Reads designed", "card_words": 2},
  {"id": "b6", "type": "ask", "display": "Comment SKILL for the fix.", "spoken": "Comment SKILL for the fix", "emphasis": ["SKILL"], "card": "Comment SKILL", "card_words": 2}
 ],
 "ask": {"keyword": "SKILL", "line": "Comment SKILL for the fix.", "loop_word": "fix"},
 "cut": {"ok": true, "before_words": 95, "after_words": 76, "removed_pct": 20.0},
 "checks": {"ok": true, "hard": [], "soft": [], "info": [], "summary": {"seconds": 30.2, "words": 76, "detect": 78, "beats": 6, "hard": 0, "soft": 0}, "detail": {}},
 "flags": [], "rewrites": []}
JSON
dummy_end
