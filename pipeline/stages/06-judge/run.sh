#!/usr/bin/env bash
# run.sh for 06-judge (Hook judge, S6): BUILD_SPEC.md section 5, S6. Scripts plus the judge model in fresh sessions.
# 1. pipeline/lib/judge.py score runs the vendor's hookscore.py on every spoken line: dealbreakers and scores under
#    config judge.min_hookscore are out. Fewer than judge.min_survivors left: 05-hooks regenerates once (session A
#    with the failures as feedback), then the judge continues with the best available.
# 2. Two full rankings with different shuffles (two independent calls), merged by Borda count; the top judge.top_n
#    compared pairwise in both orders in one call. The model ranks and compares; judge.py decides (most pairwise
#    wins, ties by Borda points, then hookscore) and composes judge.json.
# 3. library/.hooks.stats.json is updated (picked, won, judge scores per template) after judge.json is written.
#   bash pipeline/stages/06-judge/run.sh <run_dir>      (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 06-judge judge.json
set_activity "judging hooks"
hooks_file="$RUN_DIR/05-hooks/hooks.json"
exp_json="$RUN_DIR/02-expansion/expansion.json"
[ -f "$hooks_file" ] || stage_fail "05-hooks/hooks.json is missing: the hooks stage did not run"
JUDGE="$LIB/judge.py"
VENDOR="$REELS_REPO/$(cfg paths.vendor pipeline/vendor/ig-agent-skill)"
[ -f "$VENDOR/hookscore.py" ] || stage_fail "$VENDOR/hookscore.py is missing (the vendored instagram-agent-skill scripts, BUILD_SPEC.md section 10)"
STATS="$REELS_ROOT/$(cfg paths.library library)/.hooks.stats.json"
min_score="$(cfg judge.min_hookscore 50)"; min_surv="$(cfg judge.min_survivors 4)"; top_n="$(cfg judge.top_n 4)"
timeout_s="$(cfg timeouts.judge_seconds 900)"

# 1. the hookscore filter, and one regeneration by S5 when too few hooks survive
score_hooks() {
  "$REELS_PY" "$JUDGE" score --hooks "$hooks_file" --hookscore "$VENDOR/hookscore.py" --out "$OUT/scores.json" --min "$min_score"
}
res="$(score_hooks)" || stage_fail "judge.py score failed (hookscore.py)"
n_surv="$(json_field "$res" survivors '[]' | "$REELS_PY" -c 'import json, sys; print(len(json.load(sys.stdin)))')"
n_all="$(json_field "$res" n 0)"
regenerated=0
if [ "$n_surv" -lt "$min_surv" ] && [ ! -f "$OUT/regenerated.json" ]; then
  "$REELS_PY" "$JUDGE" feedback --hooks "$hooks_file" --scores "$OUT/scores.json" --out "$OUT/regenerate-feedback.json" >/dev/null \
    || stage_fail "judge.py feedback failed"
  say WARN "S6: only $n_surv of $n_all hooks passed hookscore (min $min_score, no dealbreaker): asking S5 to regenerate once"
  set_activity "picking hooks"
  if bash "$REELS_PIPELINE/stages/05-hooks/run.sh" "$RUN_DIR" --regenerate "$OUT/regenerate-feedback.json" >> "$OUT/regenerate.log" 2>&1; then
    printf '{"at": "%s", "survivors_before": %s}\n' "$(date '+%Y-%m-%d %H:%M')" "$n_surv" > "$OUT/regenerated.json"
  else
    rc=$?
    case "$rc" in
      20) stage_block "the hooks regeneration blocked the idea: $(json_file_field "$RUN_DIR/05-hooks/result.json" reason "no reason")" ;;
      *) stage_fail "the hooks regeneration failed (exit $rc): $(tail -n 1 "$OUT/regenerate.log" 2>/dev/null)" ;;
    esac
  fi
  set_activity "judging hooks"
  res="$(score_hooks)" || stage_fail "judge.py score failed after the regeneration"
  n_surv="$(json_field "$res" survivors '[]' | "$REELS_PY" -c 'import json, sys; print(len(json.load(sys.stdin)))')"
  n_all="$(json_field "$res" n 0)"
  regenerated=1
elif [ -f "$OUT/regenerated.json" ]; then
  regenerated=1
fi
[ "$n_all" -ge 2 ] || stage_block "fewer than 2 hooks to judge ($n_all in hooks.json)"
cand="$("$REELS_PY" "$JUDGE" candidates --hooks "$hooks_file" --scores "$OUT/scores.json" --min-survivors "$min_surv" --top "$top_n")" \
  || stage_fail "judge.py candidates failed"
candidates="$(json_field "$cand" candidates '[]' | tr -d '[]" ')"
cand_mode="$(json_field "$cand" mode survivors)"
n_cand="$(printf '%s' "$candidates" | awk -F, '{print ($0 == "" ? 0 : NF)}')"
[ "$n_cand" -ge 2 ] || stage_block "fewer than 2 hooks to judge after the filter"
say INFO "S6: $n_surv of $n_all hooks passed hookscore (min $min_score); judging $n_cand ($cand_mode)"

# the reel's context for the prompts
problem="$(json_file_field "$exp_json" problem "")"; reels_undash problem
identity="$(json_file_field "$exp_json" share_identity "")"; reels_undash identity
one_true="$(json_file_field "$exp_json" one_true_thing "")"; reels_undash one_true
keyword="$(json_file_field "$exp_json" keyword "?")"
voice_text="(library/profile/voice.md does not exist yet: assume a direct, plain-spoken creator who talks to developers and builders in short sentences, no hype.)"
if voice="$(profile_file voice.md)"; then voice_text="$(tr -d '\r' < "$voice")"; fi
context=("IDEA=$IDEA_TEXT" "PROBLEM=$problem" "IDENTITY=$identity" "ONE_TRUE_THING=$one_true" "KEYWORD=$keyword" "VOICE=$voice_text")

# 2. two independent rankings with different shuffles, merged by Borda count
for k in 1 2; do
  hooks_text="$("$REELS_PY" "$JUDGE" rank-prompt --hooks "$hooks_file" --candidates "$candidates" --seed "$IDEA_ID:$k" --out "$OUT/labels-$k.json")" \
    || stage_fail "judge.py rank-prompt failed"
  prompt="$OUT/prompt-rank-$k.md"
  render_prompt "$HERE/prompt-rank.md" "$prompt" "${context[@]}" "HOOKS=$hooks_text" || stage_fail "cannot render pipeline/stages/06-judge/prompt-rank.md"
  ai judge "$OUT" "$prompt" --schema "$HERE/rank.schema.json" --tools "" --timeout "$timeout_s" --name "rank-$k" \
    --activity "judging hooks" || stage_ai_failed
  pr="$("$REELS_PY" "$JUDGE" parse-ranking --labels "$OUT/labels-$k.json" --answer "$AI_OUT" --out "$OUT/ranking-$k.json")" \
    || stage_fail "judge.py parse-ranking failed on $AI_OUT"
  [ "$(json_field "$pr" complete true)" = true ] || say WARN "S6: ranking $k did not list every hook once; the missing ones were ranked last"
done
borda="$("$REELS_PY" "$JUDGE" borda --rankings "$OUT/ranking-1.json" "$OUT/ranking-2.json" --top "$top_n" --out "$OUT/borda.json")" \
  || stage_fail "judge.py borda failed"
top="$(json_field "$borda" top '[]' | tr -d '[]" ')"

# 3. the top hooks compared pairwise in both orders, in one call
pairs_text="$("$REELS_PY" "$JUDGE" pair-prompt --hooks "$hooks_file" --top "$top" --out "$OUT/pairs.json")" || stage_fail "judge.py pair-prompt failed"
prompt="$OUT/prompt-pairwise.md"
render_prompt "$HERE/prompt-pair.md" "$prompt" "${context[@]}" "PAIRS=$pairs_text" || stage_fail "cannot render pipeline/stages/06-judge/prompt-pair.md"
ai judge "$OUT" "$prompt" --schema "$HERE/pair.schema.json" --tools "" --timeout "$timeout_s" --name pairwise \
  --activity "judging hooks" || stage_ai_failed
tally="$("$REELS_PY" "$JUDGE" tally --pairs "$OUT/pairs.json" --answer "$AI_OUT" --borda "$OUT/borda.json" --scores "$OUT/scores.json" --out "$OUT/tally.json")" \
  || stage_fail "judge.py tally failed on $AI_OUT"
answered="$(json_field "$tally" answered 0)"; asked="$(json_field "$tally" asked 0)"
[ "$answered" = "$asked" ] || say WARN "S6: the pairwise call answered $answered of $asked comparisons; the rest count as no vote"

# judge.json, then the stats
summary="$("$REELS_PY" "$JUDGE" compose --hooks "$hooks_file" --scores "$OUT/scores.json" --rankings "$OUT/ranking-1.json" "$OUT/ranking-2.json" \
  --borda "$OUT/borda.json" --tally "$OUT/tally.json" --out "$OUT/judge.json" --regenerated "$regenerated" --candidates-mode "$cand_mode" --today "$TODAY")" \
  || stage_fail "judge.py compose failed"
winner_id=""; winner_spoken=""; winner_family=""; winner_template=""; runner_id=""; runner_spoken=""
eval "$(json_eval "$summary" winner_id=winner_id winner_spoken=winner_spoken winner_family=winner_family winner_template=winner_template runner_id=runner_up_id runner_spoken=runner_up_spoken)"
picked="$(json_field "$summary" picked '[]' | tr -d '[]" ')"
"$REELS_PY" "$LIB/hooks.py" stats-update --stats "$STATS" --picked "$picked" --won "$winner_template" \
  --scores "$(json_field "$summary" scores '{}')" --texts "$(json_field "$summary" texts '{}')" --date "$TODAY" >/dev/null \
  || say WARN "S6: could not update library/.hooks.stats.json"
say INFO "S6: hook 1 $winner_id \"$(cut_text "$winner_spoken" 60)\" ($winner_family), hook 2 $runner_id \"$(cut_text "$runner_spoken" 60)\"; $n_surv/$n_all passed the filter, 3 judge calls"
echo "$STAGE: done ($winner_id, $runner_id)"
exit 0
