#!/usr/bin/env bash
# run.sh for 04-angle (Angle research, S4): BUILD_SPEC.md section 5, S4. Runs only when the gate asked for it
# (03-gate reopened this stage through reopen.txt). Session A resumed with the research tools again (config
# research.tools, research.allowed and research.denied: the read-only gh forms and the screenshot tool, the gh
# forms that write denied), given the gate's verdict; the model answers with a new expansion plus what
# it changed, whether the core topic is kept and any new claims it researched (model.schema.json). New claims are
# appended to facts.md and research.json (numbering on), the expansion is checked and composed by
# pipeline/lib/expansion.py exactly as in S2 (with the same retry loop), angle.json (the primary output) and a
# copy angle-<round>.json are written, and reopen.txt names 03-gate so the gate scores the rewritten expansion.
# A model that says no angle keeps the core topic drops the idea (exit 10) and writes the suggestion to
# logs/suggested-ideas.txt.
#   bash pipeline/stages/04-angle/run.sh <run_dir>      (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 04-angle angle.json
cap="$(cfg caps.angle_rounds 2)"
n="$("$REELS_PY" "$LIB/gate.py" angle-rounds --run-dir "$RUN_DIR")"
case "$n" in ''|*[!0-9]*) n=0 ;; esac
[ "$n" -ge 1 ] || stage_fail "04-angle ran without a gate decision asking for an angle (no 03-gate/gate-*.json with decision angle)"
set_activity "finding a better angle (round $n/$cap)"
state_py round "$RUN_DIR" angle "$n" >/dev/null 2>&1 || true

gate_file="$RUN_DIR/03-gate/gate.json"
facts="$RUN_DIR/01-research/facts.md"
exp_dir="$RUN_DIR/02-expansion"
[ -f "$gate_file" ] || stage_fail "03-gate/gate.json is missing"
[ -f "$facts" ] || stage_fail "01-research/facts.md is missing"
[ -f "$exp_dir/expansion.md" ] || stage_fail "02-expansion/expansion.md is missing"
gate="$(cat "$gate_file")"
gP=""; gS=""; gC=""; gF=""; g_reason=""; g_hint=""; g_failing=""; g_round=""; eP=""; eS=""; eC=""; eF=""
eval "$(json_eval "$gate" gP=scores.P gS=scores.S gC=scores.C gF=F g_reason=model_reason g_hint=angle_hint g_failing=failing g_round=round eP=evidence.P eS=evidence.S eC=evidence.C eF=evidence.F)"
[ -n "$g_reason" ] || g_reason="$(json_field "$gate" reason "")"
scores_text="P${gP:-?} S${gS:-?} C${gC:-?} F ${gF:-?}"
failing_text="$(printf '%s' "${g_failing:-[]}" | tr -d '[]"' | tr ',' ' ')"
[ -f "$exp_dir/expansion-r$((n - 1)).md" ] || cp "$exp_dir/expansion.md" "$exp_dir/expansion-r$((n - 1)).md"

previous=""
if [ "$n" -gt 1 ]; then
  previous="$("$REELS_PY" - "$RUN_DIR" <<'EOF'
import glob, json, os, sys
lines = ["## Earlier angle rounds (do something different from these)", ""]
for path in sorted(glob.glob(os.path.join(sys.argv[1], "04-angle", "angle-*.json"))):
    try:
        a = json.load(open(path, encoding="utf-8-sig"))
    except (OSError, ValueError):
        continue
    lines.append(f"- round {a.get('round')}: {a.get('change')}")
print("\n".join(lines) + "\n")
EOF
)"
fi
deliv_file="$(profile_file deliverables.txt || true)"
deliv_text="$("$REELS_PY" "$LIB/expansion.py" deliverables --file "${deliv_file:-/nonexistent}")"
account_text=""
if account="$(profile_file account.md)"; then account_text="$(tr -d '\r' < "$account")"
else account_text="(library/profile/account.md does not exist yet: assume the reel is for people who build and publish with AI and developer tools and want practical, verified information.)"; fi
read -r min_chars max_chars < <(cfg research.expansion_chars '[500, 1500]' | tr -d '[]' | tr ',' ' ')
min_chars="${min_chars:-500}"; max_chars="${max_chars:-1500}"
tries="$(cfg research.expansion_tries 3)"
max_assets="$(cfg research.max_assets 6)"
mkdir -p "$RUN_DIR/01-research/assets"
export REELS_ASSETS_DIR="$RUN_DIR/01-research/assets"
next_claim=$(( $("$REELS_PY" "$LIB/research.py" claims --run-dir "$RUN_DIR" | "$REELS_PY" -c 'import json, sys; print(len(json.load(sys.stdin)))') + 1 ))

prompt="$OUT/prompt-angle-r$n.md"
render_prompt "$HERE/prompt.md" "$prompt" "IDEA=$IDEA_TEXT" "TODAY=$TODAY" "@FACTS=$facts" "@EXPANSION=$exp_dir/expansion.md" \
  "GATE_SCORES=$scores_text" "GATE_FAILING=${failing_text:-none}" "GATE_REASON=$g_reason" \
  "GATE_EVIDENCE=- P: $eP
- S: $eS
- C: $eC
- F: $eF" "GATE_HINT=$g_hint" "PREVIOUS_ANGLES=$previous" "DELIVERABLES=$deliv_text" "ACCOUNT=$account_text" \
  "ROUND=$n" "CAP=$cap" "MIN=$min_chars" "MAX=$max_chars" "MAX_ASSETS=$max_assets" "NEXT_CLAIM=$next_claim" \
  "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/04-angle/prompt.md"

research_call_args   # --tools, the --allow rules (read-only gh forms, the screenshot tool), the --deny rules (gh forms that write)
try=1; ok=false; result=""; errors="[]"; added_total=0; change=""
while :; do
  force=()
  [ "$try" -ge "$tries" ] && force=(--force)
  session_call A research "$OUT" "$prompt" --schema "$HERE/model.schema.json" "${RESEARCH_CALL_ARGS[@]}" \
    --timeout "$(cfg timeouts.angle_seconds 2700)" --name "angle-r$n-try$try" \
    --activity "finding a better angle (round $n/$cap)" || stage_ai_failed
  change="$(json_file_field "$AI_OUT" change "")"
  reels_undash change   # the model's words go into angle.json, the drop reason and the next round's prompt: no em dash (CLAUDE.md)
  if [ "$(json_file_field "$AI_OUT" keeps_core_topic true)" = false ]; then
    suggestion="$(json_file_field "$AI_OUT" suggested_idea "")"
    if [ -n "$suggestion" ]; then
      "$REELS_PY" "$LIB/gate.py" suggest --logs "$REELS_LOGS" --idea "$IDEA_TEXT" --suggestion "$suggestion" --source 04-angle >/dev/null \
        && say INFO "S4: a different idea was suggested and written to logs/suggested-ideas.txt"
    fi
    stage_drop "no angle keeps the core topic ($scores_text): ${change:-the angle stage found no angle inside the topic}; suggestion written to logs/suggested-ideas.txt" \
      "$(json_field "$gate" scores '{}')"
  fi
  added="$("$REELS_PY" "$LIB/research.py" append-claims --run-dir "$RUN_DIR" --claims "$AI_OUT" --today "$TODAY" \
    --added-by "04-angle round $n" 2>/dev/null)" && added_total=$((added_total + $(json_field "$added" added 0)))
  result="$("$REELS_PY" "$LIB/expansion.py" compose --run-dir "$RUN_DIR" --model-out "$AI_OUT" \
    --deliverables "${deliv_file:-/nonexistent}" --written-by "04-angle round $n" --round "$n" --idea "$IDEA_TEXT" \
    --min "$min_chars" --max "$max_chars" "${force[@]}")" || stage_fail "expansion.py compose failed on $AI_OUT"
  ok="$(json_field "$result" ok false)"
  errors="$(json_field "$result" errors '[]')"
  [ "$ok" = true ] && break
  [ "$try" -ge "$tries" ] && break
  say WARN "S4: the new expansion missed a rule ($(json_field "$errors" 0 "" | cut -c1-110)), asking again (try $((try + 1))/$tries)"
  try=$((try + 1))
  prompt="$OUT/prompt-angle-r$n-fix$try.md"
  write_retry_prompt "$prompt" research 04-angle "$errors" "Answer with the complete JSON object of the angle stage (change, keeps_core_topic, suggested_idea, new_claims and every expansion field)."
done
[ "$ok" = true ] || flag_once "expansion.md (angle round $n) breaks a rule after $tries tries: $(json_field "$errors" 0 "unknown" | cut -c1-140)"

chars="$(json_field "$result" chars 0)"
"$REELS_PY" - "$OUT" "$n" "$g_round" "$gP" "$gS" "$gC" "$gF" "$change" "$added_total" "$chars" "$TODAY" "$failing_text" <<'EOF'
import json, os, sys
out, n, g_round, p, s, c, f, change, added, chars, today, failing = sys.argv[1:13]
def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
record = {"round": int(n), "gate_round": num(g_round), "previous_scores": {"P": num(p), "S": num(s), "C": num(c), "F": f},
          "previous_failing": failing.split(), "change": change, "keeps_core_topic": True, "new_claims": int(added),
          "expansion_chars": int(chars), "written": "02-expansion/expansion.md", "checked": today}
for name in ("angle.json", f"angle-{n}.json"):
    with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
EOF
printf '03-gate\n' > "$OUT/reopen.txt"
say INFO "S4: angle round $n/$cap, $added_total new $(plural "$added_total" claim), expansion $chars chars: $(printf '%s' "$change" | cut -c1-120)"
echo "$STAGE: done"
exit 0
