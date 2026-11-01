#!/usr/bin/env bash
# run.sh for 03-gate (Idea gate, S3): BUILD_SPEC.md section 5, S3. A fresh session B with the gate model every
# round, no tools. The model scores P, S and C (0 to 3) with quoted evidence and gives its F verdict with its kind
# (model.schema.json); pipeline/lib/gate.py applies the rules: F fails with kind core whatever the model said when
# the research found the core claim false or unverified, and an F fail of kind core drops at once; pass when P, S
# and C are at least 2 and F is ok; a different-topic verdict drops with a suggestion in logs/suggested-ideas.txt;
# otherwise (P, S or C below 2, or F failing for wording: a statement of the expansion that facts.md does not back
# while the idea holds, DECISIONS.md 112) an angle round while caps.angle_rounds allows it, else drop. Decision
# angle: the ANGLE line and <stage>/reopen.txt naming 04-angle
# (state.py stage-done reopens it in the same write that marks this stage done); 04-angle reopens this stage when it
# is done, so the gate runs again on the rewritten expansion. Decision drop: exit 10 with the scores in the reason.
#   bash pipeline/stages/03-gate/run.sh <run_dir>      (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 03-gate gate.json
set_activity "checking idea (gate)"
exp_md="$RUN_DIR/02-expansion/expansion.md"
exp_json="$RUN_DIR/02-expansion/expansion.json"
facts="$RUN_DIR/01-research/facts.md"
research="$RUN_DIR/01-research/research.json"
[ -f "$exp_md" ] || stage_fail "02-expansion/expansion.md is missing: the expansion stage did not run"
[ -f "$facts" ] || stage_fail "01-research/facts.md is missing: the research stage did not run"

cap="$(cfg caps.angle_rounds 2)"
angles_done="$(count_glob "$RUN_DIR/04-angle/angle-*.json")"
round=$((angles_done + 1))
core_status="$(json_file_field "$research" core_claim.status unverified)"
core_note="$(json_file_field "$research" core_claim.note "")"
keyword="$(json_file_field "$exp_json" keyword "?")"
dstatus="$(json_file_field "$exp_json" deliverable_status new)"
case "$dstatus" in
  existing) deliverable_text="the keyword $keyword exists in deliverables.txt (its deliverable is ready)" ;;
  *) deliverable_text="the keyword $keyword is NEW (its deliverable does not exist yet and must be realistic to create)" ;;
esac
history=""
if [ "$angles_done" -gt 0 ]; then
  history="$("$REELS_PY" - "$RUN_DIR" <<'EOF'
import glob, json, os, sys
run_dir = sys.argv[1]
parts = []
for path in sorted(glob.glob(os.path.join(run_dir, "03-gate", "gate-*.json"))):
    try:
        g = json.load(open(path, encoding="utf-8-sig"))
    except (OSError, ValueError):
        continue
    s = g.get("scores", {})
    kind = f" ({g.get('F_kind')})" if g.get("F") == "fail" and g.get("F_kind") else ""
    parts.append(f"gate round {g.get('round')}: P{s.get('P')} S{s.get('S')} C{s.get('C')} F {g.get('F')}{kind}, decision {g.get('decision')}, reason: {g.get('model_reason') or g.get('reason')}")
for path in sorted(glob.glob(os.path.join(run_dir, "04-angle", "angle-*.json"))):
    try:
        a = json.load(open(path, encoding="utf-8-sig"))
    except (OSError, ValueError):
        continue
    parts.append(f"angle round {a.get('round')} changed: {a.get('change')}")
print("Earlier rounds (the expansion below is the rewritten one): " + " | ".join(parts) if parts else "")
EOF
)"
else
  history="This is the first time the expansion is scored."
fi

prompt="$OUT/prompt-gate-r$round.md"
render_prompt "$HERE/prompt.md" "$prompt" "IDEA=$IDEA_TEXT" "TODAY=$TODAY" "@EXPANSION=$exp_md" "@FACTS=$facts" \
  "CORE_STATUS=$core_status" "CORE_NOTE=$core_note" "DELIVERABLE_STATUS=$deliverable_text" "ROUND=$round" "CAP=$cap" \
  "HISTORY=$history" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/03-gate/prompt.md"

ai gate "$OUT" "$prompt" --schema "$HERE/model.schema.json" --tools "" \
  --timeout "$(cfg timeouts.gate_seconds 900)" --name "gate-r$round" --activity "checking idea (gate)" \
  || stage_ai_failed

out="$("$REELS_PY" "$LIB/gate.py" decide --run-dir "$RUN_DIR" --model-out "$AI_OUT" --round "$round" \
  --angles-done "$angles_done" --cap "$cap" --core-status "$core_status" --today "$TODAY" --idea "$IDEA_TEXT")" \
  || stage_fail "gate.py decide failed on $AI_OUT"
decision=""; scores_text=""; failing_text=""; reason=""; suggestion=""
eval "$(json_eval "$out" decision=decision scores_text=scores_text failing_text=failing_text reason=reason suggestion=suggested_idea)"
case "$decision" in
  pass)
    if [ "$angles_done" -gt 0 ]; then
      say GATE "passed ($scores_text) after $angles_done angle $(plural "$angles_done" round)"
    else
      say GATE "passed ($scores_text)"
    fi
    ;;
  angle)
    say ANGLE "gate failed ($failing_text): finding a better angle, round $round/$cap"
    printf '04-angle\n' > "$OUT/reopen.txt"
    ;;
  drop)
    if [ -n "$suggestion" ]; then
      "$REELS_PY" "$LIB/gate.py" suggest --logs "$REELS_LOGS" --idea "$IDEA_TEXT" --suggestion "$suggestion" --source 03-gate >/dev/null \
        && say INFO "S3: a different idea was suggested and written to logs/suggested-ideas.txt"
    fi
    stage_drop "$reason" "$(json_field "$out" scores '{}')"
    ;;
  *) stage_fail "gate.py decide returned an unknown decision '$decision'" ;;
esac
echo "$STAGE: done ($decision, $scores_text)"
exit 0
