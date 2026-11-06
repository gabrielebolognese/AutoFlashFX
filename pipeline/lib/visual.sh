# pipeline/lib/visual.sh: the shared body of the three visual plan stages (09a-animations, 09b-text, 09c-transitions;
# BUILD_SPEC.md S9, M10). Each run.sh sources the stage libraries and calls visual_pass_run. Fresh visual_director
# session per pass (DECISIONS.md 22), the structured answer composed into the pass's plan.json by
# pipeline/lib/visual/plan9.py (times snapped to words.json, the branding of tweaks.md applied, the validator's
# rules checked); an answer with problems gets one more call in the same session with the exact errors, then the
# stage fails (the review path of BUILD_SPEC.md 4.2).
#
#   visual_pass_run <run_dir> <stage> <pass> <activity>
#       pass: animations | text | transitions. The prompt template is pipeline/stages/<stage>/prompt.md, the answer
#       schema model.schema.json; the digests pipeline/lib/visual digest writes into <stage>/digest/ fill the
#       {{TIMELINE}}, {{CATALOG}}, {{GOLDEN}}, {{ASSETS}}, {{SOLUTION}}, {{SCENES}}, {{CHUNKS}} and {{TRANSITIONS}}
#       placeholders ("(none)" when a pass has no such digest); {{STYLE}}, {{TWEAKS}}, {{VOCABULARY}} and {{TOKENS}}
#       inline the style files, {{IDEA}} the idea, {{NOTE}} the runner's restart note, {{REVIEW}} the edit review's notes
#       for this pass when the review loop (M11) sent the reel back (python pipeline/lib/review feedback; empty otherwise).
#       After caps.review_rounds_opus failed review rounds the call goes to models.visual_director_escalation.

[ -n "${REELS_VISUAL_LOADED:-}" ] && return 0
REELS_VISUAL_LOADED=1

visual_activity() { set_activity "$1"; printf 'activity: %s
' "$1"; }

visual_pass_run() {
  local run_dir="$1" stage="$2" pass="$3" act="$4"
  local here="$REELS_PIPELINE/stages/$stage"
  stage_begin "$run_dir" "$stage" plan.json
  visual_activity "$act"
  local script="$RUN_DIR/07-script/script.json" words="$RUN_DIR/08-voiceover/words.json"
  [ -f "$script" ] || stage_fail "07-script/script.json is missing: the script stage did not run"
  [ -f "$words" ] || stage_fail "08-voiceover/words.json is missing: the voiceover stage did not run"
  local style_dir="$REELS_REPO/$(cfg paths.style_dir styles/paper-cards)" lib_dir="$REELS_REPO/$(cfg paths.motion_lib motion-lib)"
  local tokens="$REELS_REPO/$(cfg paths.tokens styles/paper-cards/tokens.json)"
  for f in "$style_dir/style.md" "$style_dir/tweaks.md" "$style_dir/vocabulary.md" "$tokens" "$lib_dir/catalog.json" "$REELS_REPO/library/brand/brand.json"; do
    [ -f "$f" ] || stage_fail "$f is missing (the preflight checks it; run bash pipeline/bin/preflight)"
  done
  if [ "$pass" != animations ]; then
    [ -f "$RUN_DIR/09a-animations/plan.json" ] || stage_fail "09a-animations/plan.json is missing: the animations pass did not run"
  fi
  if [ "$pass" = transitions ]; then
    [ -f "$RUN_DIR/09b-text/plan.json" ] || stage_fail "09b-text/plan.json is missing: the text pass did not run"
  fi
  export REELS_MOTION_LIB="$lib_dir"
  local py="$REELS_PY $REELS_PIPELINE/lib/visual"
  # 0. a text plan that fails the text pass's own checks now (written before a fix to them: the runner restarts only
  #    the failed stage) is redone first, because the transitions director cannot change card texts or captions
  if [ "$pass" = transitions ]; then
    local tchk trc
    tchk="$($py check-text --run-dir "$RUN_DIR")"; trc=$?
    if [ "$trc" = 4 ]; then
      say WARN "S9: the text plan fails the text pass's checks ($(cut_text "$(json_field "$tchk" errors.0 "")" 120)): running the text pass again first"
      bash "$REELS_PIPELINE/stages/09b-text/run.sh" "$RUN_DIR" >>"$RUN_DIR/09b-text/stage.log" 2>&1 \
        || stage_fail "the text pass, run again because its plan failed its checks, failed: $(tail -n 1 "$RUN_DIR/09b-text/stage.log" | cut -c1-200)"
      visual_activity "$act"
    elif [ "$trc" != 0 ]; then
      stage_fail "visual check-text failed (exit $trc): $(printf '%s' "$tchk" | tail -n 1 | cut -c1-200)"
    fi
  fi
  # 1. the digests
  local dg="$OUT/digest" dres
  dres="$($py digest --run-dir "$RUN_DIR" --out "$dg" --pass "$pass")" || stage_fail "visual digest failed: $(printf '%s' "$dres" | tail -n 1 | cut -c1-200)"
  local sol; sol="$(json_field "$dres" solution.type none)"
  # 2. the prompt
  local prompt="$OUT/prompt.md" f key
  local review_notes
  review_notes="$($REELS_PY "$REELS_PIPELINE/lib/review" feedback --run-dir "$RUN_DIR" --stage "$stage" 2>/dev/null || true)"
  local -a ctx=("IDEA=$IDEA_TEXT" "@STYLE=$style_dir/style.md" "@TWEAKS=$style_dir/tweaks.md" "@VOCABULARY=$style_dir/vocabulary.md" "@TOKENS=$tokens" "NOTE=$(stage_note_section)" "REVIEW=$review_notes")
  for key in TIMELINE CATALOG GOLDEN ASSETS SOLUTION SCENES CHUNKS TRANSITIONS; do
    f="$dg/$(printf '%s' "$key" | tr '[:upper:]' '[:lower:]').md"
    if [ -f "$f" ]; then ctx+=("@$key=$f"); else ctx+=("$key=(none)"); fi
  done
  render_prompt "$here/prompt.md" "$prompt" "${ctx[@]}" || stage_fail "cannot render pipeline/stages/$stage/prompt.md"
  # 3. the call, the composition, one retry with the exact problems
  local tools timeout_s try=1 res rc sid="" role=visual_director review_round
  tools="$(cfg visual.director_tools "Read Glob")"
  timeout_s="$(cfg timeouts.plan_seconds 1800)"
  # who plans (DECISIONS.md 335): the first plan is the design (models.visual_director, opus); a plan made again after
  # a failed review round is fine tuning (models.visual_director_fix, sonnet); after caps.review_rounds_opus failed
  # rounds the escalated director plans it (models.visual_director_escalation: opus, fable on an idea marked important)
  review_round="$(state_get "$RUN_DIR" rounds.review 0 2>/dev/null)"; case "$review_round" in ''|*[!0-9]*) review_round=0 ;; esac
  role="$($REELS_PY "$REELS_PIPELINE/lib/model_choice.py" director-role "$review_round" --config "$REELS_CONFIG" 2>/dev/null)" || role=visual_director
  [ -n "$role" ] || role=visual_director
  local why="the design"
  case "$role" in
    visual_director_fix) why="fine tuning after review round $review_round" ;;
    visual_director_escalation) why="escalated, review round $review_round" ;;
  esac
  say INFO "S9: $act for $(json_field "$dres" idea_id "$IDEA_ID") (solution $sol): asking the visual director ($(ai_model_name "$role" "$RUN_DIR"), $why)$([ -n "$review_notes" ] && echo " with the edit review's notes")"
  while :; do
    if [ -n "$sid" ]; then
      ai "$role" "$OUT" "$prompt" --resume "$sid" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try" --activity "$act"; rc=$?
      if [ "$rc" = 3 ]; then
        say WARN "S9: the director's session no longer exists ($(undash "${AI_ERROR:-no detail}")): asking again in a new one"
        ai "$role" "$OUT" "$prompt" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try-fresh" --activity "$act"; rc=$?
      fi
    else
      ai "$role" "$OUT" "$prompt" --schema "$here/model.schema.json" --tools "$tools" --timeout "$timeout_s" --name "$pass-try$try" --activity "$act"; rc=$?
    fi
    [ "$rc" = 0 ] || stage_ai_failed
    sid="$AI_SESSION"
    visual_activity "validating plan"
    local -a extra=()
    [ "$pass" = transitions ] && extra=(--merged "$OUT/merged.json")
    res="$($py "$pass" --run-dir "$RUN_DIR" --answer "$AI_OUT" --out "$OUT/plan.json" "${extra[@]}")"; rc=$?
    [ "$rc" = 0 ] || [ "$rc" = 4 ] || stage_fail "visual $pass failed (exit $rc): $(printf '%s' "$res" | tail -n 1 | cut -c1-220)"
    if [ "$rc" = 0 ]; then break; fi
    if [ "$try" -ge 2 ]; then
      stage_fail "the $pass plan still has problems after the director's retry: $(json_field "$res" errors.0 "" | cut -c1-200)"
    fi
    say WARN "S9: the $pass plan has $(json_field "$res" errors '[]' | "$REELS_PY" -c 'import json, sys; print(len(json.load(sys.stdin)))') problems ($(cut_text "$(json_field "$res" errors.0 "")" 120)); asking the director once more"
    try=2
    prompt="$OUT/prompt-retry.md"
    write_retry_prompt "$prompt" visual_director "$stage" "$(json_field "$res" errors '[]')" \
      "Answer with the complete JSON object of the $pass pass again (every scene and field), fixing exactly these points and keeping everything else as it was." "$pass"
    visual_activity "$act"
  done
  # 4. the summary and the flags
  local line
  while IFS= read -r line; do [ -n "$line" ] && printf 'note: %s\n' "$line"; done < <(json_field "$res" notes '[]' | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
for n in json.load(sys.stdin): print(n)')
  while IFS= read -r line; do [ -n "$line" ] && printf 'warning: %s\n' "$line"; done < <(json_field "$res" warnings '[]' | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
for n in json.load(sys.stdin): print(n)')
  case "$pass" in
    animations)
      say INFO "S9: animations planned: $(json_field "$res" summary ""); brand slot $(json_field "$res" brand_slot "neutral" | sed 's/^$/neutral/'), hook set piece $(json_field "$res" hook_set_piece false)$([ "$try" = 2 ] && echo ", after one retry")"
      while IFS= read -r line; do
        [ -n "$line" ] && flag_once "the visual director wanted a component the library lacks: $line"
      done < <(json_field "$res" wishlist '[]' | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
for w in json.load(sys.stdin):
    if isinstance(w, dict) and w.get("name"): print(str(w.get("name")) + ": " + str(w.get("does", ""))[:120])')
      ;;
    text) say INFO "S9: text planned: $(json_field "$res" summary "")$([ "$try" = 2 ] && echo ", after one retry")" ;;
    transitions) say INFO "S9: transitions planned: $(json_field "$res" summary ""); the merged plan passes the validator$([ "$try" = 2 ] && echo ", after one retry")" ;;
  esac
  echo "$STAGE: done"
  return 0
}
