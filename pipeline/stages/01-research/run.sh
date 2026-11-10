#!/usr/bin/env bash
# run.sh for 01-research (Research, S1): BUILD_SPEC.md section 5, S1. Session A with the research model
# (config models.research), tools WebSearch, WebFetch, Read and Bash restricted to the read-only gh forms (gh repo
# view, gh release list, gh release view, gh api repos/...) and `bash pipeline/bin/screenshot ...`, with the gh forms
# that write denied (config research.allowed and research.denied, research_call_args in pipeline/lib/stage.sh).
# The model answers with one JSON object
# (model.schema.json); pipeline/lib/research.py turns it into research.json (the primary output, schema.json),
# facts.md, numbers.json and assets.json, merging the screenshots the model took into assets/.
#   bash pipeline/stages/01-research/run.sh <run_dir>      (started by the runner)
# Exit 0 done, anything else a code error (the review and fix loop). A session that no longer exists is reseeded
# by session_call (pipeline/lib/session.sh). A missing library/profile/account.md is a NEEDS REVIEW flag, not an
# error (BUILD_SPEC.md 2.3).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$(cd "$HERE/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/ai.sh"
source "$LIB/session.sh"
source "$LIB/stage.sh"

stage_begin "${1:?usage: run.sh <run_dir>}" 01-research research.json
set_activity "researching facts"
mkdir -p "$OUT/assets"
export REELS_ASSETS_DIR="$OUT/assets"
max_assets="$(cfg research.max_assets 6)"

account_text=""
if account="$(profile_file account.md)"; then
  account_text="$(tr -d '\r' < "$account")"
else
  account_text="(library/profile/account.md does not exist yet. Assume the reel is for people who build and publish with AI and developer tools and want practical, verified information. Keep the research on the idea's own topic.)"
  flag_once "library/profile/account.md is missing: the research and the expansion used default audience assumptions"
fi

prompt="$OUT/prompt-research.md"
render_prompt "$HERE/prompt.md" "$prompt" "IDEA=$IDEA_TEXT" "TODAY=$TODAY" "ACCOUNT=$account_text" \
  "ASSETS_DIR=$OUT/assets" "MAX_ASSETS=$max_assets" "NOTE=$(stage_note_section)" \
  || stage_fail "cannot render pipeline/stages/01-research/prompt.md"

research_call_args   # --tools, the --allow rules (read-only gh forms, the screenshot tool), the --deny rules (gh forms that write)
session_call "$SESSION_KEY" research "$OUT" "$prompt" --schema "$HERE/model.schema.json" "${RESEARCH_CALL_ARGS[@]}" \
  --timeout "$(cfg timeouts.research_seconds 2700)" --name research --activity "researching facts" \
  || stage_ai_failed

summary="$("$REELS_PY" "$LIB/research.py" finish --run-dir "$RUN_DIR" --model-out "$AI_OUT" --today "$TODAY" \
  --idea-id "$IDEA_ID" --idea "$IDEA_TEXT" --max-assets "$max_assets")" \
  || stage_fail "research.py finish failed on $AI_OUT (see the lines above)"
n_claims=""; n_verified=""; n_numbers=""; n_assets=""; core=""
eval "$(json_eval "$summary" n_claims=claims n_verified=verified n_numbers=numbers n_assets=assets core=core_status)"
say INFO "S1: ${n_claims:-0} claims (${n_verified:-0} verified), ${n_numbers:-0} numbers, ${n_assets:-0} screenshots; core claim ${core:-unverified}"
[ "${n_assets:-0}" = 0 ] && say WARN "S1: no screenshot was saved (01-research/assets/ is empty): the visual stages will have no real page to show"
[ "${n_claims:-0}" = 0 ] && say WARN "S1: the research produced no sourced claim: the gate will fail F"
echo "$STAGE: done"
exit 0
