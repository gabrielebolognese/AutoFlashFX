#!/usr/bin/env bash
# dummy.sh for 14-export (Caption and export, S14): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/14-export/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 14-export export.json
today="$(printf '%(%Y-%m-%d)T' -1)"
flags="$(state_get "$RUN_DIR" flags "[]")"
needs_review="$("$REELS_PY" - "$flags" <<'PY'
import json, sys
sys.stdout.reconfigure(newline="\n")
flags = json.loads(sys.argv[1])
print(json.dumps([str(f.get("stage", "?")) + ": " + str(f.get("text", "")) for f in flags]))
PY
)"
cat > "$OUT/export.json" <<JSON
{"caption": "Your AI site looks fake. One fix.\n\nClaude Code's frontend-design skill changes what the model reaches for. One command installs it.\n\nComment SKILL and I will send you the install command and the checklist.",
 "hashtags": ["#claudecode", "#webdesign", "#aitools"],
 "keyword": "SKILL", "deliverable": "the install command and a before/after checklist", "deliverable_status": "new", "link": "",
 "solution": $("$REELS_PY" - "$RUN_DIR/02-expansion/solution.json" <<'PY'
import json, os, sys
sys.stdout.reconfigure(newline="\n")
p = sys.argv[1]
s = json.load(open(p, encoding="utf-8-sig")) if os.path.isfile(p) else {}
t = str(s.get("type", "none")).lower()
print(json.dumps({"type": t if t in ("flashfx", "external", "method") else "none", "name": str(s.get("name", "")), "url": str(s.get("url", ""))}))
PY
),
 "hooks": {"hook1": "Your AI site looks fake, one fix", "hook2": "Install this skill in 30 seconds"},
 "needs_review": $needs_review,
 "facts": [{"claim": "The dummy tool exists and is open source", "url": "https://example.com/repo", "checked": "$today"},
           {"claim": "It installs with one command", "url": "https://example.com/docs/install", "checked": "$today"}],
 "files": {"reel": "../13-render/final.mp4", "hook2": "../13-render/hook2.mp4"}}
JSON
dummy_end
