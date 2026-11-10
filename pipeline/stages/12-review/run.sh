#!/usr/bin/env bash
# run.sh for 12-review (Review and fix loop, S12): BUILD_SPEC.md section 5, S12. One review round of the mixed draft:
#   0. the energy check (review/energy_check.py, M16): the mixed draft's energy, the reel and every scene against tokens.json energy, no model;
#      a failing scene becomes an [animation] issue with its numbers and goes back to 9a
#   1. the mechanical checks (pipeline/lib/review/mechanical.py: the built composition opened host by host in the
#      Playwright harness at every beat, emphasis and landing time; zones with the caption band exception, the right
#      230 px of the lower half, the fonts and sizes, overlaps and off-canvas, contrast, each emphasis within 80 ms
#      of its word, the branding rules of tweaks.md)
#   2. the style conformance check (review/style_check.py: tools/analyze_refs.py on draft_mixed.mp4 against
#      styles/<style>/analysis: cadence, token colors, accent share, loudness)
#   3. the audio checks (review/audio_check.py: S11's verification, the voice transcribed from the mixed draft and
#      compared with words.json, WER under 5 percent)
#   4. the edit review: a fresh qa session (never the builder) reads the contact sheet, the 10 fps filmstrips of the
#      hook and the transitions, 2 or 3 look-reference stills and the scene list with sound-map.txt, scores 1 to 5
#      on eight criteria, says whether the branding feels natural and lists tagged issues
#   5. the verdict (review/route.py): pass when every check passed and every score is at least 4; otherwise every
#      issue goes back to the step that owns it ([voice] S8, [animation] 9a, [text] 9b, [transition] 9c, [sfx] S11)
#      and every step after it runs again (this stage included), through reopen.txt; caps.review_rounds_opus rounds
#      with the main director and builder (the fixes are Sonnet's fine tuning), then caps.review_rounds_fable escalated
#      rounds (opus, fable only on an idea marked [important], DECISIONS.md 334 and 335); still failing: export anyway with
#      a NEEDS REVIEW flag carrying the notes. Never a stop.
# Outputs in 12-review/: review.json (primary), review-r<n>.json, mechanical.json, style.json, audio.json, edit-r<n>.json,
# filmstrips/, digest/, prompt-r<n>.md, feedback.json (for the re-run stages), notes.md, calls/.
# Relays the Python's progress lines ("@@ACTIVITY", "@@SAY", "@@FLAG", "@@ERROR") like S8 and S10.
#   bash pipeline/stages/12-review/run.sh <run_dir>                        (started by the runner)
# Environment (tests): REELS_REVIEW_SKIP_EDIT=1 skips the qa call (the code checks alone decide; scores count as 5).
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

stage_begin "${1:?usage: run.sh <run_dir>}" 12-review review.json
for f in 10-build/project/index.html 10-build/plan.json 10-build/events.json 11-sfx/cues.json 11-sfx/draft_mixed.mp4 08-voiceover/words.json 07-script/script.json; do
  [ -f "$RUN_DIR/$f" ] || stage_fail "$f is missing: the stage that writes it did not run"
done
command -v ffmpeg >/dev/null 2>&1 || stage_fail "ffmpeg is not on PATH"
export REELS_MOTION_LIB="${REELS_MOTION_LIB:-$(chcfg paths.motion_lib)}"
ROUND="$(state_get "$RUN_DIR" rounds.review 0 2>/dev/null)"; case "$ROUND" in ''|*[!0-9]*) ROUND=0 ;; esac
ROUND=$((ROUND + 1))
TOTAL=$(( $(cfg caps.review_rounds_opus 3) + $(cfg caps.review_rounds_fable 2) ))
ERR_FILE="$OUT/.last-error"
rm -f "$ERR_FILE"

relay() {
  local line rest tag
  while IFS= read -r line; do
    case "$line" in
      "@@ACTIVITY "*) set_activity "${line#@@ACTIVITY }"; printf 'activity: %s\n' "${line#@@ACTIVITY }" ;;
      "@@SAY "*) rest="${line#@@SAY }"; tag="${rest%% *}"; say "$tag" "${rest#* }" ;;
      "@@FLAG "*) flag_once "${line#@@FLAG }" ;;
      "@@ERROR "*) printf '%s\n' "${line#@@ERROR }" > "$ERR_FILE"; printf '%s\n' "$line" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done
}
review_step() {  # review_step <activity> <command...>: the Python's exit code; its last JSON line in STEP_OUT
  local act="$1"; shift
  set_activity "$act"; printf 'activity: %s\n' "$act"
  local tmp="$OUT/.step.out" rc
  set -o pipefail
  "$@" 2>&1 | relay | tee "$tmp"
  rc=${PIPESTATUS[0]}
  set +o pipefail
  STEP_OUT="$(grep -E '^\{' "$tmp" | tail -n 1)"
  rm -f "$tmp"
  return $rc
}
last_error() { local msg; msg="$(head -n 1 "$ERR_FILE" 2>/dev/null)"; printf '%s' "${msg:-${1:-the review failed}}"; }

say INFO "S12: review round $ROUND/$TOTAL of the draft"
# 0. the energy check (Motion and energy rules E0 and E9): runs first, needs no model; its failing scenes go back to 9a with their numbers
review_step "reviewing: energy check" heavy_run analyze "S12 energy-check" -- "$REELS_PY" "$LIB/review" energy-check --run-dir "$RUN_DIR" --stage-dir "$OUT" || stage_fail "$(last_error "the energy check failed")"
energy_pass="$(json_field "$STEP_OUT" pass false)"; energy_n="$(json_field "$STEP_OUT" issues 0)"; energy_move="$(json_field "$STEP_OUT" moving_share_pct "?")"; energy_skipped="$(json_field "$STEP_OUT" skipped false)"
energy_part=""
[ "$energy_skipped" = true ] || energy_part="energy $([ "$energy_pass" = true ] && echo "ok (moving ${energy_move}%)" || echo "$energy_n issues (moving ${energy_move}%)"), "
# 1. mechanical
review_step "reviewing: mechanical checks" heavy_run render "S12 mechanical" -- "$REELS_PY" "$LIB/review" mechanical --run-dir "$RUN_DIR" --stage-dir "$OUT" || stage_fail "$(last_error "the mechanical checks failed")"
mech_pass="$(json_field "$STEP_OUT" pass false)"; mech_n="$(json_field "$STEP_OUT" issues 0)"
# 2. style
review_step "reviewing: style check" heavy_run analyze "S12 style" -- "$REELS_PY" "$LIB/review" style --run-dir "$RUN_DIR" --stage-dir "$OUT" || stage_fail "$(last_error "the style check failed")"
style_pass="$(json_field "$STEP_OUT" pass false)"; style_n="$(json_field "$STEP_OUT" issues 0)"
# 3. audio
review_step "reviewing: audio check" heavy_run transcribe "S12 audio" -- "$REELS_PY" "$LIB/review" audio --run-dir "$RUN_DIR" --stage-dir "$OUT" || stage_fail "$(last_error "the audio check failed")"
audio_pass="$(json_field "$STEP_OUT" pass false)"; audio_n="$(json_field "$STEP_OUT" issues 0)"; wer="$(json_field "$STEP_OUT" wer_pct "?")"
say INFO "S12: code checks: ${energy_part}mechanical $([ "$mech_pass" = true ] && echo ok || echo "$mech_n issues"), style $([ "$style_pass" = true ] && echo ok || echo "$style_n issues"), audio $([ "$audio_pass" = true ] && echo ok || echo "$audio_n issues") (voice WER ${wer}%)"

# 4. the edit review (a fresh qa session per round)
ANSWER=""
if [ "${REELS_REVIEW_SKIP_EDIT:-0}" != 1 ]; then
  review_step "reviewing: edit review (round $ROUND/$TOTAL)" heavy_run encode "S12 filmstrips" -- "$REELS_PY" "$LIB/review" filmstrips --run-dir "$RUN_DIR" --stage-dir "$OUT" || stage_fail "$(last_error "the filmstrips failed")"
  review_step "reviewing: edit review (round $ROUND/$TOTAL)" "$REELS_PY" "$LIB/review" prompt --run-dir "$RUN_DIR" --stage-dir "$OUT" --round "$ROUND" || stage_fail "$(last_error "the prompt digests failed")"
  DG="$OUT/digest"
  PROMPT="$OUT/prompt-r$ROUND.md"
  # the rules that belong to the channel's format (its branding, M20: format.json stages[].prompts.rules) fill {{FORMAT_RULES}}
  RULES_SRC="$("$REELS_PY" "$LIB/formats.py" prompt 12-review rules 2>/dev/null)"
  RULES="$DG/format-rules.md"
  if [ -n "$RULES_SRC" ]; then
    render_prompt "$RULES_SRC" "$RULES" "BRAND=$("$REELS_PY" "$LIB/config.py" brand)" || stage_fail "cannot render the format's review rules $RULES_SRC"
  else
    : > "$RULES"
  fi
  render_prompt "$HERE/prompt.md" "$PROMPT" "IDEA=$IDEA_TEXT" "STYLE=$(cfg style)" "@FORMAT_RULES=$RULES" "@REQUIREMENTS=$DG/requirements.md" "@IMAGES=$DG/images.md" "@SCENES=$DG/scenes.md" \
    "@CHECKS=$DG/checks.md" "@HISTORY=$DG/history.md" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/12-review/prompt.md"
  ai qa "$OUT" "$PROMPT" --schema "$HERE/model.schema.json" --tools "$(cfg review.qa_tools "Read Glob")" --timeout "$(cfg timeouts.edit_review_seconds 1800)" \
    --name "edit-r$ROUND" --activity "reviewing: edit review (round $ROUND/$TOTAL)" || stage_ai_failed
  ANSWER="$AI_OUT"
  [ -n "$ANSWER" ] && [ -f "$ANSWER" ] || stage_fail "the qa model gave no structured answer (see $AI_CALL)"
fi

# 5. the verdict
review_step "reviewing: edit review (round $ROUND/$TOTAL)" "$REELS_PY" "$LIB/review" verdict --run-dir "$RUN_DIR" --stage-dir "$OUT" --round "$ROUND" ${ANSWER:+--answer "$ANSWER"} || stage_fail "$(last_error "the verdict failed")"
eval "$(json_eval "$STEP_OUT" verdict=verdict passed=pass scores=scores low=low_scores n_issues=issues owners=owners reopen=reopen activity=activity next_model=next_model flags=flags)"
scores_text="$("$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
d = json.loads(sys.argv[1] or "{}"); print(", ".join(f"{k} {v}" for k, v in d.items()))' "$scores")"
case "$verdict" in
  pass)
    say INFO "S12: review round $ROUND passed (scores $scores_text)"
    if [ "$ROUND" -gt 1 ]; then state_py issue "$RUN_DIR" fixed +1 >/dev/null 2>&1; state_py issue "$RUN_DIR" open -1 >/dev/null 2>&1; fi
    ;;
  fix)
    state_set "$RUN_DIR" "rounds.review=$ROUND" >/dev/null 2>&1 || true
    [ "$ROUND" -eq 1 ] && state_py issue "$RUN_DIR" open +1 >/dev/null 2>&1
    reopen_list="$("$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
for s in json.loads(sys.argv[1] or "[]"): print(s)' "$reopen")"
    printf '%s\n' "$reopen_list" > "$OUT/reopen.txt"
    say WARN "S12: review round $ROUND failed ($n_issues issues; scores $scores_text): back to $(printf '%s' "$owners" | tr -d '[]"' | tr ',' ' ' | sed 's/  */ /g'), then every step after it runs again"
    set_activity "$activity"; printf 'activity: %s\n' "$activity"
    ;;
  cap|flag|stop)
    state_set "$RUN_DIR" "rounds.review=$ROUND" >/dev/null 2>&1 || true
    [ "$ROUND" -eq 1 ] && state_py issue "$RUN_DIR" open +1 >/dev/null 2>&1
    case "$verdict" in
      cap) why="the $TOTAL rounds are used up" ;;
      stop) why="the same scores and issues came twice in a row (early stop)" ;;
      *) why="nothing upstream can act on its issues" ;;
    esac
    say WARN "S12: review round $ROUND failed and $why: exporting with NEEDS REVIEW (scores $scores_text)"
    ;;
esac
while IFS= read -r f; do [ -n "$f" ] && flag_once "$f"; done < <("$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
for s in json.loads(sys.argv[1] or "[]"): print(s)' "$flags")
echo "$STAGE: done"
exit 0
