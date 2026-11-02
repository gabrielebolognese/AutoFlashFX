#!/usr/bin/env bash
# dummy.sh for 02-expansion (Expansion, S2): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/02-expansion/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 02-expansion expansion.json
cat > "$OUT/expansion.json" <<'JSON'
{"problem": "My AI-built site looks like every other AI-built site and I cannot say why.",
 "solution": "One skill changes the defaults the model reaches for, so the page stops looking generated.",
 "share_identity": "if you ship client sites with AI", "takeaway": "install one skill before the next build",
 "keyword": "SKILL", "deliverable": "the install command and a before/after checklist", "deliverable_status": "new",
 "one_true_thing": "one command installs it", "evidence": ["facts.md#1", "facts.md#2"],
 "solution_decision": {"type": "external", "name": "the frontend-design skill", "url": "https://github.com/anthropics/skills", "reason": "dummy: the idea names its solution"}}
JSON
cat > "$OUT/solution.json" <<'JSON'
{"type": "external", "name": "the frontend-design skill", "url": "https://github.com/anthropics/skills",
 "reason": "dummy: the idea names its solution", "keyword": "LINK", "deliverable": "the link to the frontend-design skill",
 "deliverable_link": "https://github.com/anthropics/skills", "written_by": "02-expansion (dummy)", "round": 0, "checked": "", "notes": []}
JSON
{
  echo "# Expansion (dummy)"; echo
  echo "Problem: My AI-built site looks like every other AI-built site and I cannot say why."
  echo "Solution: one skill changes the defaults the model reaches for, so the page stops looking generated."
  echo "Solution decision: external (the frontend-design skill, https://github.com/anthropics/skills): the idea names its solution."
  echo "Share driver: if you ship client sites with AI, this is the one install that changes how the result reads."
  echo "Comment keyword: SKILL, deliverable NEW: the install command and a before/after checklist."
  echo "One specific true thing: one command installs it."
  echo "Evidence: facts.md#1, facts.md#2."
  echo "This dummy text is padded so the file lands inside the 500 to 1500 character window the real stage must hit;"
  echo "the real expansion is written by session A with the research in context, and the gate scores it next."
} > "$OUT/expansion.md"
dummy_end
