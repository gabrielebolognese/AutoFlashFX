#!/usr/bin/env bash
# run.sh for 07-script (Script, S7): BUILD_SPEC.md section 5, S7. Fresh session D with the script model; the cut
# model, the checks model and the judge model in fresh sessions.
# 1. pipeline/lib/script_checks.py setup reads the inputs once (brief.md, judge.json for hook 1 and hook 2,
#    expansion.json, voice.md, pronunciations.txt, the Length line of tweaks.md, the beat map of style.md) and
#    writes plan.json: the pace, the length range, the two tones (the brief's suggestions, else the hook's family),
#    the word targets (the writer overshoots by config script.overshoot_pct so the cut pass can trim 20 percent).
# 2. Round 1: two drafts in two tones in session D (draft B resumes the session so it differs from draft A), each
#    cut by the cut model (10 to 30 percent fewer words, every number and name kept, up to script.cut_tries tries),
#    then humanize.py and every scripted check (beats.py timing and structure, detect.py, placeholders, the stake
#    with the identity, one ask with the keyword that repeats a hook word, the length, the cards) plus the claims
#    check by the checks model against facts.md.
# 3. The pick: the judge model compares the two drafts ("would he say this out loud to a friend?") with the voice
#    excerpts as reference, in a seeded order.
# 4. The loop: up to caps.script_rounds rounds in all; from round 2 the picked draft is rewritten in session D with
#    the failing checks as feedback, then checked again. Hard failures left after the last round (facts,
#    placeholders, a missing requirement, a second ask, the length off by more than 15 percent) block the idea
#    unless the other draft passed every hard check in round 1 (then it is used, with a flag); soft failures
#    (detect.py, timing, the cards, the cut) continue with a NEEDS REVIEW flag.
# 5. script_checks.py compose writes script.json (type, display, spoken, emphasis and card per beat, the ask, hook
#    2's tracks, the checks, the pick, the rounds).
#   bash pipeline/stages/07-script/run.sh <run_dir>                                     (started by the runner)
#   bash pipeline/stages/07-script/run.sh <run_dir> --rewrite-line <beat id> [--reason "<why>"]
#       S8's one-line rewrite: the beat's spoken track rewritten in simpler words (session D when it still exists),
#       script.json updated in place with the change recorded under "rewrites". Exit 0 rewritten, 4 when the model
#       gave no usable line twice, 1 on a code error.
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

REWRITE_BEAT=""; REWRITE_REASON=""
if [ "${2:-}" = "--rewrite-line" ]; then
  REWRITE_BEAT="${3:?usage: run.sh <run_dir> --rewrite-line <beat id> [--reason <why>]}"
  [ "${4:-}" = "--reason" ] && REWRITE_REASON="${5:-}"
fi
stage_begin "${1:?usage: run.sh <run_dir>}" 07-script script.json
PY_CHECKS="$LIB/script_checks.py"
py() { "$REELS_PY" "$PY_CHECKS" "$@"; }
upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }

VENDOR="$REELS_REPO/$(cfg paths.vendor pipeline/vendor/ig-agent-skill)"
for f in beats.py humanize.py detect.py slop.json; do
  [ -f "$VENDOR/$f" ] || stage_fail "$VENDOR/$f is missing (the vendored instagram-agent-skill scripts, BUILD_SPEC.md section 10)"
done
T_SCRIPT="$(cfg timeouts.script_seconds 1800)"; T_CUT="$(cfg timeouts.cut_seconds 900)"
T_CHECKS="$(cfg timeouts.checks_seconds 900)"; T_PICK="$(cfg timeouts.pick_seconds 900)"
ROUNDS="$(cfg caps.script_rounds 3)"; CUT_TRIES="$(cfg script.cut_tries 2)"
PLAN="$OUT/plan.json"

# session D: the short prompt resumes the stored session; a lost session gets the self-contained prompt instead
d_call() {  # d_call <name> <schema> <timeout> <activity> <short prompt or ""> <full prompt>
  local name="$1" schema="$2" to="$3" act="$4" short="$5" full="$6" rc
  if [ -n "$short" ] && [ -n "$(state_get "$RUN_DIR" sessions.D "" 2>/dev/null)" ]; then
    ai script "$OUT" "$short" --session D --schema "$schema" --tools "" --timeout "$to" --name "$name" --activity "$act"; rc=$?
    if [ "$rc" = 3 ]; then
      say WARN "S7: session D no longer exists ($(undash "${AI_ERROR:-no detail}")): starting a new one with the full prompt"
      session_forget "$RUN_DIR" D
      ai script "$OUT" "$full" --session D --schema "$schema" --tools "" --timeout "$to" --name "$name-full" --activity "$act"; rc=$?
    fi
  else
    ai script "$OUT" "$full" --session D --schema "$schema" --tools "" --timeout "$to" --name "$name" --activity "$act"; rc=$?
    if [ "$rc" = 3 ]; then
      say WARN "S7: session D no longer exists ($(undash "${AI_ERROR:-no detail}")): starting a new one"
      session_forget "$RUN_DIR" D
      ai script "$OUT" "$full" --session D --schema "$schema" --tools "" --timeout "$to" --name "$name-new" --activity "$act"; rc=$?
    fi
  fi
  [ "$rc" = 3 ] && rc=1
  return $rc
}

# ------------------------------------------------------------------------------------- S8's one-line rewrite
if [ -n "$REWRITE_BEAT" ]; then
  script="$OUT/script.json"
  [ -f "$script" ] || stage_fail "07-script/script.json is missing: nothing to rewrite"
  set_activity "rewriting line $REWRITE_BEAT"
  data="$(py rewrite-line-data --script "$script" --beat "$REWRITE_BEAT")" || stage_fail "no beat $REWRITE_BEAT in script.json"
  prompt="$OUT/prompt-rewrite-line-$REWRITE_BEAT.md"
  render_prompt "$HERE/prompt-rewrite-line.md" "$prompt" "BEAT_ID=$REWRITE_BEAT" "REASON=${REWRITE_REASON:-the word error rate was too high}" \
    "DISPLAY=$(json_field "$data" display)" "SPOKEN=$(json_field "$data" spoken)" "CARD=$(json_field "$data" card)" "WORDS=$(json_field "$data" words)" \
    "MAX_WORDS=$(json_field "$data" words)" "ALL=$(json_field "$data" all)" "PRONUNCIATIONS=$(json_field "$data" pronunciations)" "NOTE=" \
    || stage_fail "cannot render pipeline/stages/07-script/prompt-rewrite-line.md"
  try=1; ok=false; res=""
  while :; do
    d_call "rewrite-line-$REWRITE_BEAT-try$try" "$HERE/rewrite-line.schema.json" "$T_SCRIPT" "rewriting line $REWRITE_BEAT" "$prompt" "$prompt" || stage_ai_failed
    res="$(py rewrite-line-apply --script "$script" --beat "$REWRITE_BEAT" --answer "$AI_OUT" --reason "$REWRITE_REASON")" || stage_fail "script_checks.py rewrite-line-apply failed"
    ok="$(json_field "$res" ok false)"
    [ "$ok" = true ] && break
    [ "$try" -ge 2 ] && break
    say WARN "S7: the rewritten line was not usable ($(json_field "$res" errors.0 "" | cut -c1-100)), asking again"
    try=2
    prompt="$OUT/prompt-rewrite-line-$REWRITE_BEAT-fix.md"
    write_retry_prompt "$prompt" script 07-script "$(json_field "$res" errors '[]')" "Answer with the JSON object {spoken, display, notes} only." rewrite-line
  done
  if [ "$ok" != true ]; then
    say WARN "S7: line $REWRITE_BEAT could not be rewritten ($(json_field "$res" errors.0 "" | cut -c1-100)); script.json unchanged"
    echo "$STAGE: rewrite-line $REWRITE_BEAT failed"
    exit 4
  fi
  say INFO "S7: line $REWRITE_BEAT rewritten in simpler words: \"$(cut_text "$(json_field "$res" spoken)" 70)\""
  echo "$STAGE: rewrite-line $REWRITE_BEAT done"
  exit 0
fi

# ------------------------------------------------------------------------------------- the inputs and the plan
set_activity "writing script (draft 1/2, round 1/$ROUNDS)"
brief="$RUN_DIR/05-hooks/brief.md"; judge="$RUN_DIR/06-judge/judge.json"; facts="$RUN_DIR/01-research/facts.md"
exp_json="$RUN_DIR/02-expansion/expansion.json"
[ -f "$brief" ] || stage_fail "05-hooks/brief.md is missing: the hooks stage did not run"
[ -f "$judge" ] || stage_fail "06-judge/judge.json is missing: the judge stage did not run"
[ -f "$facts" ] || stage_fail "01-research/facts.md is missing: the research stage did not run"
[ -f "$exp_json" ] || stage_fail "02-expansion/expansion.json is missing: the expansion stage did not run"
style_dir="$(chcfg paths.style_dir)"
voice=""; voice_text="(library/profile/voice.md does not exist yet: assume a direct, plain-spoken creator who talks to developers and builders in short sentences, no hype.)"
if voice="$(profile_file voice.md)"; then
  voice_text="$(tr -d '\r' < "$voice")"
  if "$REELS_PY" "$LIB/voiceprofile.py" is-draft "$voice"; then
    flag_once "library/profile/voice.md is still a draft with [FILL IN] placeholders: the hooks, the judge and the script use default voice assumptions"
  fi
else
  flag_once "library/profile/voice.md is missing: the hooks, the judge and the script use default voice assumptions"
fi
pron_file="$(profile_file pronunciations.txt || true)"
pron_text="$(grep -v -E '^\s*(#|$)' "${pron_file:-/nonexistent}" 2>/dev/null | tr -d '\r' || true)"
[ -n "$pron_text" ] || pron_text="(none: library/profile/pronunciations.txt lists no word yet; say tool names the way the brief suggests)"
wpm="$(cfg voice.wpm "")"; [ -n "$wpm" ] || wpm="$("$REELS_PY" "$LIB/hooks.py" wpm --voice "${voice:-/nonexistent}" --default 150)"  # config voice.wpm: the reel voice's pace (M7)
plan_res="$(py setup --config "$REELS_CONFIG" --brief "$brief" --judge "$judge" --expansion "$exp_json" --voice "${voice:-}" \
  --pronunciations "${pron_file:-}" --tweaks "$style_dir/tweaks.md" --style "$style_dir/style.md" --wpm "$wpm" --rounds "$ROUNDS" \
  --idea-id "$IDEA_ID" --idea-text "$IDEA_TEXT" --solution "$RUN_DIR/02-expansion/solution.json" --out "$PLAN")" || stage_fail "script_checks.py setup failed (judge.json without a winner?)"
video_type=""; len_lo=""; len_hi=""; len_src=""; keyword=""; hook_spoken=""; hook_on_screen=""; hook_id=""
eval "$(json_eval "$plan_res" video_type=video_type keyword=keyword hook_spoken=hook_spoken hook_on_screen=hook_on_screen hook_id=hook_id len_src=length_source)"
len_lo="$(json_file_field "$PLAN" length_s.0 25)"; len_hi="$(json_file_field "$PLAN" length_s.1 40)"
final_lo="$(json_file_field "$PLAN" final_words.0 80)"; final_hi="$(json_file_field "$PLAN" final_words.1 130)"
write_lo="$(json_file_field "$PLAN" write_words.0 120)"; write_hi="$(json_file_field "$PLAN" write_words.1 145)"
tone_a="$(json_file_field "$PLAN" tones.0 insider)"; tone_b="$(json_file_field "$PLAN" tones.1 "calm expert")"
tone_src="$(json_file_field "$PLAN" tone_source brief)"
hook_family="$(json_file_field "$PLAN" hook.family "")"; hook2_spoken="$(json_file_field "$PLAN" hook2.spoken "")"
hook2_on_screen="$(json_file_field "$PLAN" hook2.on_screen "")"
identity="$(json_file_field "$PLAN" identity "")"; problem="$(json_file_field "$PLAN" problem "")"; solution="$(json_file_field "$PLAN" solution "")"
deliverable="$(json_file_field "$PLAN" deliverable "")"; dstatus="$(json_file_field "$PLAN" deliverable_status new)"
case "$dstatus" in existing) deliv_label="existing deliverable: $deliverable" ;; *) deliv_label="NEW deliverable, to create: $deliverable" ;; esac
excerpts="$(json_file_field "$PLAN" voice_excerpts "")"; [ -n "$excerpts" ] || excerpts="(no verbatim excerpts yet: go by the profile above)"
beat_map="$(json_file_field "$PLAN" beat_map "")"
solution_rules="$(json_file_field "$PLAN" solution_rules "")"; solution_type="$(json_file_field "$PLAN" solution_decision.type none)"
[ -n "$keyword" ] || stage_fail "expansion.json has no comment keyword"
tone_guide() { json_file_field "$PLAN" "tone_guide.$1" ""; }
say INFO "S7: hook 1 $hook_id \"$(cut_text "$hook_spoken" 60)\"; $video_type reel of ${len_lo%.*} to ${len_hi%.*} s ($len_src) at $wpm wpm: $final_lo to $final_hi words after the cut; tones $tone_a and $tone_b ($tone_src); solution $solution_type"
WRITE_CTX=("IDEA=$IDEA_TEXT" "HOOK_SPOKEN=$hook_spoken" "HOOK_ON_SCREEN=$hook_on_screen" "HOOK_FAMILY=$hook_family" "SOLUTION_RULES=$solution_rules"
  "HOOK2_SPOKEN=$hook2_spoken" "HOOK2_ON_SCREEN=$hook2_on_screen" "@BRIEF=$brief" "@FACTS=$facts" "VOICE=$voice_text"
  "EXCERPTS=$excerpts" "PRONUNCIATIONS=$pron_text" "BEAT_MAP=$beat_map" "VIDEO_TYPE=$video_type" "LENGTH_LO=${len_lo%.*}"
  "LENGTH_HI=${len_hi%.*}" "WPM=$wpm" "WRITE_LO=$write_lo" "WRITE_HI=$write_hi" "FINAL_LO=$final_lo" "FINAL_HI=$final_hi"
  "BEAT_MAX_WORDS=$(json_file_field "$PLAN" beat_max_words 13)" "STAKE_MAX_WORDS=$(json_file_field "$PLAN" stake_max_words 16)"
  "KEYWORD=$keyword" "DELIVERABLE=$deliv_label" "IDENTITY=$identity" "PROBLEM=$problem")
declare -A CUR REP OK HARD SOFT TONE_OF FIRST
TONE_OF[a]="$tone_a"; TONE_OF[b]="$tone_b"
ROUNDS_LOG="$OUT/rounds.json"; rm -f "$ROUNDS_LOG"
log_round() { py round-log --file "$ROUNDS_LOG" --round "$1" --label "$2" --action "$3" --ok "$4" --hard "$5" --soft "$6" --note "$7" >/dev/null 2>&1 || true; }

# ------------------------------------------------------------------------------------- the cut pass
cut_draft() {  # cut_draft <label> <round> <draft file> -> CUR[label] = the cut draft
  local d="$1" r="$2" src="$3" data prompt try=1 res sid="" rc
  local -a attempts=()
  set_activity "cutting script"
  data="$(py cut-data --draft "$src" --plan "$PLAN")" || stage_fail "script_checks.py cut-data failed on $src"
  local text words target floor min_after max_after keep hook_id ask_id
  eval "$(json_eval "$data" text=text words=words target=target floor=floor min_after=min_after max_after=max_after keep=must_keep_text hook_id=hook_id ask_id=ask_id)"
  prompt="$OUT/prompt-cut-$d-r$r.md"
  render_prompt "$HERE/prompt-cut.md" "$prompt" "TEXT=$text" "WORDS=$words" "TARGET=$target" "FLOOR=$floor" "MIN_AFTER=$min_after" \
    "MAX_AFTER=$max_after" "MUST_KEEP=${keep:-(none)}" "HOOK_ID=$hook_id" "ASK_ID=$ask_id" "KEYWORD=$keyword" "NOTE=$(stage_note_section)" \
    || stage_fail "cannot render pipeline/stages/07-script/prompt-cut.md"
  while :; do
    if [ -n "$sid" ]; then
      ai cut "$OUT" "$prompt" --resume "$sid" --schema "$HERE/cut.schema.json" --tools "" --timeout "$T_CUT" --name "cut-$d-r$r-try$try" --activity "cutting script"; rc=$?
      if [ "$rc" = 3 ]; then
        prompt="$OUT/prompt-cut-$d-r$r.md"
        ai cut "$OUT" "$prompt" --schema "$HERE/cut.schema.json" --tools "" --timeout "$T_CUT" --name "cut-$d-r$r-try$try-fresh" --activity "cutting script"; rc=$?
      fi
      [ "$rc" = 0 ] || stage_ai_failed
    else
      ai cut "$OUT" "$prompt" --schema "$HERE/cut.schema.json" --tools "" --timeout "$T_CUT" --name "cut-$d-r$r-try$try" --activity "cutting script" || stage_ai_failed
    fi
    sid="$AI_SESSION"
    res="$(py cut-apply --draft "$src" --answer "$AI_OUT" --plan "$PLAN" --out "$OUT/draft-$d.r$r.cut$try.json" --attempt "$try")" \
      || stage_fail "script_checks.py cut-apply failed on $AI_OUT"
    attempts+=("$OUT/draft-$d.r$r.cut$try.json")
    [ "$(json_field "$res" ok false)" = true ] && break
    [ "$try" -ge "$CUT_TRIES" ] && break
    say WARN "S7: the cut of draft $d missed ($(json_field "$res" errors.0 "" | cut -c1-110)), asking again (try $((try + 1))/$CUT_TRIES)"
    try=$((try + 1))
    prompt="$OUT/prompt-cut-$d-r$r-fix$try.md"
    write_retry_prompt "$prompt" cut 07-script "$(json_field "$res" errors '[]')" \
      "Answer with the complete JSON object of the cut (every beat with id, display, spoken and card, ask_line, notes), cutting the original script again from the start." cut
  done
  res="$(py cut-best --draft "$src" --plan "$PLAN" --attempts "${attempts[@]}" --out "$OUT/draft-$d.r$r.cut.json")" || stage_fail "script_checks.py cut-best failed"
  CUR[$d]="$OUT/draft-$d.r$r.cut.json"
  if [ "$(json_field "$res" ok false)" = true ]; then
    say INFO "S7: draft $d cut from $(json_field "$res" before_words) to $(json_field "$res" after_words) words ($(json_field "$res" removed_pct)%, $(json_field "$res" chosen))"
  else
    say WARN "S7: the cut pass of draft $d did not land ($(json_field "$res" errors.0 "" | cut -c1-110)); continuing with $(json_field "$res" chosen)"
  fi
}

# ------------------------------------------------------------------------------------- the checks
check_draft() {  # check_draft <label> <round> <draft file> -> REP, OK, HARD, SOFT, FIRST for the label
  local d="$1" r="$2" file="$3" res data prompt rep
  rep="$OUT/checks-$d-r$r.json"   # its own line: the words of one local statement are expanded before any is assigned
  set_activity "checking script"
  res="$(py check --draft "$file" --plan "$PLAN" --vendor "$VENDOR" --write --out "$rep")" || stage_fail "script_checks.py check failed on $file"
  data="$(py claims-data --draft "$file")" || stage_fail "script_checks.py claims-data failed on $file"
  prompt="$OUT/prompt-claims-$d-r$r.md"
  render_prompt "$HERE/prompt-claims.md" "$prompt" "@FACTS=$facts" "PROBLEM=$problem" "IDENTITY=$identity" "SOLUTION=$solution" \
    "SOLUTION_RULES=$solution_rules" \
    "HOOK_SPOKEN=$hook_spoken" "KEYWORD=$keyword" "BEATS=$(json_field "$data" text)" "NOTE=$(stage_note_section)" \
    || stage_fail "cannot render pipeline/stages/07-script/prompt-claims.md"
  ai checks "$OUT" "$prompt" --schema "$HERE/claims.schema.json" --tools "" --timeout "$T_CHECKS" --name "claims-$d-r$r" --activity "checking script" || stage_ai_failed
  res="$(py claims --report "$rep" --answer "$AI_OUT" --draft "$file")" || stage_fail "script_checks.py claims failed on $AI_OUT"
  REP[$d]="$rep"; CUR[$d]="$file"
  OK[$d]="$(json_field "$res" ok false)"; HARD[$d]="$(json_field "$res" hard 0)"; SOFT[$d]="$(json_field "$res" soft 0)"
  FIRST[$d]="$(json_field "$res" first "")"
  local seconds words detect
  seconds="$(json_file_field "$rep" summary.seconds "?")"; words="$(json_file_field "$rep" summary.words "?")"; detect="$(json_file_field "$rep" summary.detect "?")"
  if [ "${OK[$d]}" = true ]; then
    say INFO "S7: draft $d (${TONE_OF[$d]}) round $r: ${seconds} s, ${words} words, detect ${detect}, $(json_field "$res" claims 0) claims checked: every check passes"
  else
    say WARN "S7: draft $d (${TONE_OF[$d]}) round $r: ${seconds} s, ${words} words, detect ${detect}: ${HARD[$d]} hard and ${SOFT[$d]} soft $(plural "$(( ${HARD[$d]} + ${SOFT[$d]} ))" failure) (first: $(cut_text "${FIRST[$d]}" 110))"
  fi
}

# ------------------------------------------------------------------------------------- round 1: two drafts
i=0
for d in a b; do
  i=$((i + 1))
  tone="${TONE_OF[$d]}"
  set_activity "writing script (draft $i/2, round 1/$ROUNDS)"
  full="$OUT/prompt-write-$d.md"; short=""; extra=""
  if [ "$d" = b ]; then
    extra="(This is draft B, in the $tone tone. Draft A was written in the ${TONE_OF[a]} tone in a session that is no longer available: make this one a different script, not a paraphrase.)"
    short="$OUT/prompt-write-b-short.md"
    render_prompt "$HERE/prompt-second.md" "$short" "DRAFT_LABEL=B" "TONE=$tone" "TONE_GUIDE=$(tone_guide "$tone")" "OTHER_TONE=${TONE_OF[a]}" \
      "WRITE_LO=$write_lo" "WRITE_HI=$write_hi" "KEYWORD=$keyword" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/07-script/prompt-second.md"
  fi
  render_prompt "$HERE/prompt.md" "$full" "${WRITE_CTX[@]}" "DRAFT_LABEL=$(upper "$d")" "TONE=$tone" "TONE_GUIDE=$(tone_guide "$tone")" \
    "EXTRA=$extra" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/07-script/prompt.md"
  d_call "write-$d" "$HERE/model.schema.json" "$T_SCRIPT" "writing script (draft $i/2, round 1/$ROUNDS)" "$short" "$full" || stage_ai_failed
  res="$(py draft --answer "$AI_OUT" --plan "$PLAN" --label "$d" --tone "$tone" --round 1 --source write --out "$OUT/draft-$d.r1.json")" \
    || stage_fail "script_checks.py draft failed on $AI_OUT"
  [ "$(json_field "$res" ok false)" = true ] || stage_fail "draft $d came back without beats ($AI_OUT)"
  say INFO "S7: draft $d ($tone) written: $(json_field "$res" beats) beats, $(json_field "$res" words.display) words before the cut"
  cut_draft "$d" 1 "$OUT/draft-$d.r1.json"
  check_draft "$d" 1 "${CUR[$d]}"
  log_round 1 "$d" "write, cut, check" "${OK[$d]}" "${HARD[$d]}" "${SOFT[$d]}" "${FIRST[$d]}"
done

# ------------------------------------------------------------------------------------- the pick
set_activity "checking script"
pdata="$(py pick-data --drafts "${CUR[a]}" "${CUR[b]}" --reports "${REP[a]}" "${REP[b]}" --seed "$IDEA_ID:pick" --out "$OUT/pick-data.json")" \
  || stage_fail "script_checks.py pick-data failed"
prompt="$OUT/prompt-pick.md"
render_prompt "$HERE/prompt-pick.md" "$prompt" "EXCERPTS=$excerpts" "VOICE=$voice_text" "HOOK_SPOKEN=$hook_spoken" \
  "TEXT_1=$(json_field "$pdata" text_1)" "TEXT_2=$(json_field "$pdata" text_2)" "TONE_1=$(json_field "$pdata" tone_1)" "TONE_2=$(json_field "$pdata" tone_2)" \
  "CHECKS_1=$(json_field "$pdata" checks_1)" "CHECKS_2=$(json_field "$pdata" checks_2)" "NOTE=$(stage_note_section)" \
  || stage_fail "cannot render pipeline/stages/07-script/prompt-pick.md"
ai judge "$OUT" "$prompt" --schema "$HERE/pick.schema.json" --tools "" --timeout "$T_PICK" --name pick --activity "checking script" || stage_ai_failed
pres="$(py pick --data "$OUT/pick-data.json" --answer "$AI_OUT" --out "$OUT/pick.json")" || stage_fail "script_checks.py pick failed on $AI_OUT"
P="$(json_field "$pres" winner a)"
[ "$(json_field "$pres" lenient false)" = true ] && say WARN "S7: the judge's answer named no draft; draft $P (shown first) is taken"
say INFO "S7: the judge picked draft $P (${TONE_OF[$P]}): $(cut_text "$(json_field "$pres" reason "")" 120)"
idx=1; [ "$P" = b ] && idx=2

# ------------------------------------------------------------------------------------- rounds 2 and on: rewrite the pick
r=1
while [ "${OK[$P]}" != true ] && [ "$r" -lt "$ROUNDS" ]; do
  r=$((r + 1))
  set_activity "writing script (draft $idx/2, round $r/$ROUNDS)"
  feedback="$(py feedback --report "${REP[$P]}" --plan "$PLAN")" || stage_fail "script_checks.py feedback failed"
  draft_json="$(py draft-text --draft "${CUR[$P]}" --as-answer)" || stage_fail "script_checks.py draft-text failed"
  short="$OUT/prompt-rewrite-$P-r$r.md"
  render_prompt "$HERE/prompt-rewrite.md" "$short" "DRAFT_LABEL=$(upper "$P")" "TONE=${TONE_OF[$P]}" "ROUND=$r" "ROUNDS=$ROUNDS" \
    "FEEDBACK=$feedback" "DRAFT_JSON=$draft_json" "HOOK_SPOKEN=$hook_spoken" "KEYWORD=$keyword" "FINAL_LO=$final_lo" "FINAL_HI=$final_hi" \
    "BEAT_MAX_WORDS=$(json_file_field "$PLAN" beat_max_words 13)" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/07-script/prompt-rewrite.md"
  full="$OUT/prompt-rewrite-$P-r$r-full.md"
  render_prompt "$HERE/prompt.md" "$full" "${WRITE_CTX[@]}" "DRAFT_LABEL=$(upper "$P")" "TONE=${TONE_OF[$P]}" "TONE_GUIDE=$(tone_guide "${TONE_OF[$P]}")" \
    "EXTRA=## This is a rewrite, not a first draft
$(grep -v -E '^# (Role|Stage|Task): ' "$short")
" "NOTE=" || stage_fail "cannot render the full rewrite prompt"
  d_call "rewrite-$P-r$r" "$HERE/model.schema.json" "$T_SCRIPT" "writing script (draft $idx/2, round $r/$ROUNDS)" "$short" "$full" || stage_ai_failed
  res="$(py draft --answer "$AI_OUT" --plan "$PLAN" --label "$P" --tone "${TONE_OF[$P]}" --round "$r" --source rewrite --previous "${CUR[$P]}" --out "$OUT/draft-$P.r$r.json")" \
    || stage_fail "script_checks.py draft failed on $AI_OUT"
  [ "$(json_field "$res" ok false)" = true ] || stage_fail "the rewrite of draft $P came back without beats ($AI_OUT)"
  check_draft "$P" "$r" "$OUT/draft-$P.r$r.json"
  log_round "$r" "$P" "rewrite, check" "${OK[$P]}" "${HARD[$P]}" "${SOFT[$P]}" "${FIRST[$P]}"
done
state_set "$RUN_DIR" "rounds.script=$r" >/dev/null 2>&1 || true

# ------------------------------------------------------------------------------------- the verdict
final="$P"; fallback=""
other=a; [ "$P" = a ] && other=b
if [ "${OK[$P]}" != true ] && [ "${HARD[$P]}" -gt 0 ]; then
  if [ "${HARD[$other]:-1}" -eq 0 ]; then
    say WARN "S7: draft $P still fails a hard check after $r $(plural "$r" round) ($(cut_text "${FIRST[$P]}" 100)); using draft $other, which passed every hard check in round 1"
    final="$other"; fallback="draft $P could not be fixed in $r rounds: ${FIRST[$P]}"
    flag_once "script: the judge's pick (draft $P) still failed a hard check after $r rounds, draft $other was used instead: $(cut_text "${FIRST[$P]}" 120)"
  else
    stage_block "script still failing after $r $(plural "$r" round): $(cut_text "${FIRST[$P]}" 170)" "$(json_file_field "${REP[$P]}" hard '[]')"
  fi
fi
if [ "$(json_file_field "${CUR[$final]}" cut.ok false)" != true ]; then
  flag_once "soft script check failed: the cut pass did not remove 10 to 30 percent of draft $final's words ($(cut_text "$(json_file_field "${CUR[$final]}" cut.errors.0 "no attempt landed")" 120))"
fi
if [ "${OK[$final]}" != true ]; then
  flags_text="$("$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
rep = json.load(open(sys.argv[1], encoding="utf-8-sig"))
seen = set()
for f in rep.get("soft", []):
    if f["check"] in seen: continue
    seen.add(f["check"])
    print(f["check"] + ": " + f["message"][:130])' "${REP[$final]}")"
  while IFS= read -r line; do
    [ -n "$line" ] && flag_once "soft script check failed after $r $(plural "$r" round): $line"
  done <<<"$flags_text"
fi

# ------------------------------------------------------------------------------------- script.json
flags_json="$(state_get "$RUN_DIR" flags "[]" 2>/dev/null | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
flags = json.load(sys.stdin)
print(json.dumps([f.get("text", "") for f in flags if isinstance(f, dict) and f.get("stage") == "07-script"], ensure_ascii=False))' 2>/dev/null || echo '[]')"
cres="$(py compose --draft "${CUR[$final]}" --report "${REP[$final]}" --plan "$PLAN" --pick "$OUT/pick.json" --rounds "$r" --rounds-log "$ROUNDS_LOG" \
  --flags "$flags_json" --fallback "$fallback" --draft-info "a=${CUR[a]}" "b=${CUR[b]}" --out "$OUT/script.json")" || stage_fail "script_checks.py compose failed"
say INFO "S7: script.json: draft $final (${TONE_OF[$final]}), $(json_field "$cres" beats) beats, $(json_field "$cres" seconds) s ($(json_field "$cres" words) words at $wpm wpm), cut $(json_field "$cres" removed_pct)%, detect $(json_field "$cres" detect), $r $(plural "$r" round); session D done"
echo "$STAGE: done (draft $final, $r rounds)"
exit 0
