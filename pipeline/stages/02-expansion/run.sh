#!/usr/bin/env bash
# run.sh for 02-expansion (Expansion, S2): BUILD_SPEC.md section 5, S2. Session A resumed (the research is in
# context), no tools. The model answers with the five parts as fields (model.schema.json);
# pipeline/lib/expansion.py checks them against the rules and composes expansion.md (500 to 1500 characters) and
# expansion.json (the primary output). A field that breaks a rule, or a text outside the length window, is asked
# again in the same session with the exact problems, up to config research.expansion_tries times; the last try is
# written anyway with a NEEDS REVIEW flag (a quality loop, never an error).
#   bash pipeline/stages/02-expansion/run.sh <run_dir>      (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 02-expansion expansion.json
set_activity "expanding idea"
facts="$RUN_DIR/01-research/facts.md"
[ -f "$facts" ] || stage_fail "01-research/facts.md is missing: the research stage did not run"

deliv_file="$(profile_file deliverables.txt || true)"
deliv_text="$("$REELS_PY" "$LIB/expansion.py" deliverables --file "${deliv_file:-/nonexistent}")"
account_text=""
if account="$(profile_file account.md)"; then
  account_text="$(tr -d '\r' < "$account")"
else
  account_text="(library/profile/account.md does not exist yet: assume the reel is for people who build and publish with AI and developer tools and want practical, verified information.)"
  flag_once "library/profile/account.md is missing: the research and the expansion used default audience assumptions"
fi
read -r min_chars max_chars < <(cfg research.expansion_chars '[500, 1500]' | tr -d '[]' | tr ',' ' ')
min_chars="${min_chars:-500}"; max_chars="${max_chars:-1500}"
tries="$(cfg research.expansion_tries 3)"

prompt="$OUT/prompt-expansion.md"
render_prompt "$HERE/prompt.md" "$prompt" "IDEA=$IDEA_TEXT" "TODAY=$TODAY" "@FACTS=$facts" "DELIVERABLES=$deliv_text" \
  "ACCOUNT=$account_text" "MIN=$min_chars" "MAX=$max_chars" "NOTE=$(stage_note_section)" \
  || stage_fail "cannot render pipeline/stages/02-expansion/prompt.md"

try=1; ok=false; result=""; errors="[]"
while :; do
  force=()
  [ "$try" -ge "$tries" ] && force=(--force)
  session_call A research "$OUT" "$prompt" --schema "$HERE/model.schema.json" --tools "" \
    --timeout "$(cfg timeouts.expansion_seconds 900)" --name "expansion-$try" --activity "expanding idea" \
    || stage_ai_failed
  result="$("$REELS_PY" "$LIB/expansion.py" compose --run-dir "$RUN_DIR" --model-out "$AI_OUT" \
    --deliverables "${deliv_file:-/nonexistent}" --written-by 02-expansion --round 0 --idea "$IDEA_TEXT" \
    --min "$min_chars" --max "$max_chars" "${force[@]}")" || stage_fail "expansion.py compose failed on $AI_OUT"
  ok="$(json_field "$result" ok false)"
  errors="$(json_field "$result" errors '[]')"
  [ "$ok" = true ] && break
  [ "$try" -ge "$tries" ] && break
  say WARN "S2: the expansion missed a rule ($(json_field "$errors" 0 "" | cut -c1-110)), asking again (try $((try + 1))/$tries)"
  try=$((try + 1))
  prompt="$OUT/prompt-expansion-fix$try.md"
  write_retry_prompt "$prompt" research 02-expansion "$errors"
done

chars="$(json_field "$result" chars 0)"; keyword="$(json_field "$result" keyword "")"
dstatus="$(json_field "$result" deliverable_status new)"; refs="$(json_field "$result" evidence_refs '[]' | tr -d '[] ')"
if [ "$ok" != true ]; then
  flag_once "expansion.md breaks a rule after $tries tries: $(json_field "$errors" 0 "unknown" | cut -c1-140)"
fi
say INFO "S2: expansion $chars chars, keyword $keyword ($dstatus), evidence facts.md#${refs//,/, #}"
echo "$STAGE: done"
exit 0
