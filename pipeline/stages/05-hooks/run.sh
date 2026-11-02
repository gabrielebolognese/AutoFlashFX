#!/usr/bin/env bash
# run.sh for 05-hooks (Hooks, S5): BUILD_SPEC.md section 5, S5, and 2.2. Session A resumed (a run with no stored
# session starts a new one seeded with facts.md, expansion.md and the gate verdict: session.sh --seed-if-new).
# 1. pipeline/bin/index-hooks rebuilds library/.hooks.index.json when library/hooks.txt changed (one batched call
#    to the indexer model for the new lines; nothing when the file is unchanged).
# 2. pipeline/lib/hooks.py builds the template shortlist (config hooks.shortlist, every family represented, win-rate
#    weighted once the stats have data, fit-for-problem-solution preferred) and the model writes 12 to 20 hooks from
#    at least 3 families (model.schema.json); hooks.py check applies the rules of spec S5 (spoken 8 words or fewer and
#    under 3 s at the user's wpm, on-screen 6 words or fewer, a concrete marker, known template ids, no duplicates)
#    and asks again in the same session with the exact problems, config hooks.tries times; the last try writes what
#    is valid with a NEEDS REVIEW flag, fewer than hooks.min_for_judge valid hooks blocks the idea.
# 3. The same session writes the brief (brief.schema.json), measured as words x 1.3 tokens against
#    config hooks.brief_tokens, with the same retry loop. Session A's job ends here.
# With `--regenerate <feedback.json>` (called once by 06-judge when its hookscore filter leaves too few hooks) the
# stage resumes session A with the survivors and the failures, merges the valid replacements with the survivors,
# rewrites hooks.json and skips the brief.
#   bash pipeline/stages/05-hooks/run.sh <run_dir> [--regenerate <feedback.json>]      (started by the runner)
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

REGEN=""
if [ "${2:-}" = "--regenerate" ]; then REGEN="${3:?usage: run.sh <run_dir> --regenerate <feedback.json>}"; fi
stage_begin "${1:?usage: run.sh <run_dir>}" 05-hooks hooks.json
set_activity "picking hooks"
facts="$RUN_DIR/01-research/facts.md"
exp_md="$RUN_DIR/02-expansion/expansion.md"
exp_json="$RUN_DIR/02-expansion/expansion.json"
[ -f "$facts" ] || stage_fail "01-research/facts.md is missing: the research stage did not run"
[ -f "$exp_md" ] || stage_fail "02-expansion/expansion.md is missing: the expansion stage did not run"
[ -n "$REGEN" ] && [ ! -f "$REGEN" ] && stage_fail "the regeneration feedback file $REGEN is missing"

# the hooks index, rebuilt only when library/hooks.txt changed (BUILD_SPEC.md 2.2: before every hooks stage)
bash "$REELS_PIPELINE/bin/index-hooks" --quiet >> "$OUT/index-hooks.log" 2>&1 \
  || stage_fail "index-hooks failed (exit $?): $(tail -n 1 "$OUT/index-hooks.log" 2>/dev/null)"
lib_dir="$REELS_ROOT/$(cfg paths.library library)"
INDEX="$lib_dir/.hooks.index.json"
STATS="$lib_dir/.hooks.stats.json"
VENDOR_HOOKS="$REELS_REPO/$(cfg paths.vendor pipeline/vendor/ig-agent-skill)/hooks.json"
[ -f "$INDEX" ] || stage_fail "library/.hooks.index.json is missing after index-hooks"

# the voice profile: how the user sounds. The pace comes from config voice.wpm (the reel voice, Kokoro af_bella
# after silence tightening, measured in M7); voice.md's Pace line is the user's own and only a fallback.
voice=""; voice_text=""
if voice="$(profile_file voice.md)"; then
  voice_text="$(tr -d '\r' < "$voice")"
  if "$REELS_PY" "$LIB/voiceprofile.py" is-draft "$voice"; then
    flag_once "library/profile/voice.md is still a draft with [FILL IN] placeholders: the hooks, the judge and the script use default voice assumptions"
  fi
else
  voice_text="(library/profile/voice.md does not exist yet: assume a direct, plain-spoken creator who talks to developers and builders in short sentences, no hype.)"
  flag_once "library/profile/voice.md is missing: the hooks, the judge and the script use default voice assumptions"
fi
if account="$(profile_file account.md)"; then
  if "$REELS_PY" "$LIB/voiceprofile.py" is-draft "$account"; then
    flag_once "library/profile/account.md is still a draft with [FILL IN] placeholders: the research and the hooks used its working assumption"
  fi
fi
wpm="$(cfg voice.wpm "")"; [ -n "$wpm" ] || wpm="$("$REELS_PY" "$LIB/hooks.py" wpm --voice "${voice:-/nonexistent}" --default 150)"  # config voice.wpm: the reel voice's pace (M7)
max_sec="$(cfg hooks.spoken_max_seconds 3)"
limits="$("$REELS_PY" "$LIB/hooks.py" limits --wpm "$wpm" --max-words "$(cfg hooks.spoken_max_words 8)" --max-seconds "$max_sec")"
max_words="$(json_field "$limits" max_words 7)"
min_hooks="$(cfg hooks.min_hooks 12)"; max_hooks="$(cfg hooks.max_hooks 20)"; min_families="$(cfg hooks.min_families 3)"
min_for_judge="$(cfg hooks.min_for_judge 4)"; tries="$(cfg hooks.tries 3)"

# the expansion's fields for the prompts
keyword="$(json_file_field "$exp_json" keyword "?")"
deliverable="$(json_file_field "$exp_json" deliverable "")"; reels_undash deliverable
dstatus="$(json_file_field "$exp_json" deliverable_status new)"
identity="$(json_file_field "$exp_json" share_identity "")"; reels_undash identity
problem="$(json_file_field "$exp_json" problem "")"; reels_undash problem
one_true="$(json_file_field "$exp_json" one_true_thing "")"; reels_undash one_true
deliv_file="$(profile_file deliverables.txt || true)"
deliv_text="$("$REELS_PY" "$LIB/expansion.py" deliverables --file "${deliv_file:-/nonexistent}")"

# the template shortlist (kept across a regeneration so the same template ids stay valid)
if [ -z "$REGEN" ] || [ ! -f "$OUT/shortlist.json" ]; then
  "$REELS_PY" "$LIB/hooks.py" shortlist --index "$INDEX" --stats "$STATS" --vendor "$VENDOR_HOOKS" \
    --n "$(cfg hooks.shortlist 24)" --per-family "$(cfg hooks.per_family 2)" --fit-weight "$(cfg hooks.fit_weight_other 0.35)" \
    --seed "$IDEA_ID" --out "$OUT/shortlist.json" > "$OUT/shortlist.summary.json" || stage_fail "hooks.py shortlist failed"
fi
templates_text="$("$REELS_PY" "$LIB/hooks.py" templates-text --shortlist "$OUT/shortlist.json")"
check_args=(--shortlist "$OUT/shortlist.json" --index "$INDEX" --vendor "$VENDOR_HOOKS" --wpm "$wpm"
  --min "$min_hooks" --max "$max_hooks" --min-families "$min_families" --on-screen-max "$(cfg hooks.on_screen_max_words 6)"
  --max-words "$(cfg hooks.spoken_max_words 8)" --max-seconds "$max_sec" --min-for-judge "$min_for_judge" --idea-id "$IDEA_ID")

# ---------------------------------------------------------------------------------------------- the hooks
if [ -z "$REGEN" ]; then
  prompt="$OUT/prompt-hooks.md"
  render_prompt "$HERE/prompt.md" "$prompt" "IDEA=$IDEA_TEXT" "@EXPANSION=$exp_md" "VOICE=$voice_text" \
    "TEMPLATES=$templates_text" "MIN=$min_hooks" "MAX=$max_hooks" "MIN_FAMILIES=$min_families" "MAX_WORDS=$max_words" \
    "MAX_SECONDS=$max_sec" "WPM=$wpm" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/05-hooks/prompt.md"
  name_prefix="hooks"
  extra_args=()
else
  # the judge's feedback: survivors (kept) and failures (replaced)
  survivors="$(json_file_field "$REGEN" survivors '[]' | tr -d '[]" ' )"
  n_surv="$(printf '%s' "$survivors" | awk -F, '{print ($0 == "" ? 0 : NF)}')"
  n_new=$(( min_hooks - n_surv + 4 )); [ $(( n_surv + n_new )) -gt "$max_hooks" ] && n_new=$(( max_hooks - n_surv ))
  [ "$n_new" -lt 4 ] && n_new=4
  surv_text="$(json_file_field "$REGEN" survivors_text "(none)")"; reels_undash surv_text
  fail_text="$(json_file_field "$REGEN" failures_text "(none)")"; reels_undash fail_text
  prompt="$OUT/prompt-regenerate.md"
  render_prompt "$HERE/prompt-regenerate.md" "$prompt" "MIN_SURVIVORS=$(cfg judge.min_survivors 4)" "N_NEW=$n_new" \
    "SURVIVORS=$surv_text" "FAILURES=$fail_text" "MAX_WORDS=$max_words" "MAX_SECONDS=$max_sec" "WPM=$wpm" \
    "TEMPLATES=$templates_text" "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/05-hooks/prompt-regenerate.md"
  cp "$OUT/hooks.json" "$OUT/hooks-before-regenerate.json" 2>/dev/null || true
  name_prefix="regenerate"
  extra_args=(--keep "$OUT/hooks-before-regenerate.json" --survivors "$survivors" --written-by "05-hooks regenerate")
  say INFO "S5: regenerating hooks for the judge ($n_surv passed the filter, $n_new new ones asked)"
fi

try=1; ok=false; result=""; errors="[]"; written=false
while :; do
  force=()
  [ "$try" -ge "$tries" ] && force=(--force)
  session_call A research "$OUT" "$prompt" --seed-if-new --schema "$HERE/model.schema.json" --tools "" \
    --timeout "$(cfg timeouts.hooks_seconds 1200)" --name "$name_prefix-try$try" --activity "picking hooks" || stage_ai_failed
  result="$("$REELS_PY" "$LIB/hooks.py" check --answer "$AI_OUT" --out "$OUT/hooks.json" "${check_args[@]}" "${extra_args[@]}" "${force[@]}")" \
    || stage_fail "hooks.py check failed on $AI_OUT"
  ok="$(json_field "$result" ok false)"
  errors="$(json_field "$result" errors '[]')"
  written="$(json_field "$result" written false)"
  [ "$ok" = true ] && break
  [ "$try" -ge "$tries" ] && break
  say WARN "S5: the hooks missed a rule ($(json_field "$errors" 0 "" | cut -c1-110)), asking again (try $((try + 1))/$tries)"
  try=$((try + 1))
  prompt="$OUT/prompt-$name_prefix-fix$try.md"
  write_retry_prompt "$prompt" research 05-hooks "$errors" "Answer with the complete JSON object of the hooks stage (every hook, template_id copied exactly from the list, family, spoken, on_screen, marker, marker_kind, notes)."
done
if [ "$ok" != true ]; then
  if [ "$written" = true ]; then
    flag_once "hooks.json breaks a rule after $tries tries: $(json_field "$errors" 0 "unknown" | cut -c1-140)"
  else
    stage_block "fewer than $min_for_judge valid hooks after $tries tries: $(json_field "$errors" 0 "unknown" | cut -c1-160)"
  fi
fi
kept="$(json_field "$result" kept 0)"; families="$(json_field "$result" families '[]' | tr -d '[]" ')"
# new hook shapes the model noticed go to library/hooks.suggested.txt (never to hooks.txt; the user moves them)
if [ -z "$REGEN" ]; then
  n_sugg="$("$REELS_PY" "$LIB/hooks.py" suggest --file "$lib_dir/hooks.suggested.txt" --shapes "$(json_file_field "$AI_OUT" suggested_shapes '[]')" \
    --source "run $RUN_ID (05-hooks)" 2>/dev/null | "$REELS_PY" -c 'import json, sys; print(json.load(sys.stdin).get("added", 0))' 2>/dev/null || echo 0)"
  [ "${n_sugg:-0}" -gt 0 ] && say INFO "S5: $n_sugg new hook $(plural "$n_sugg" shape) written to library/hooks.suggested.txt"
fi
n_lib="$("$REELS_PY" -c 'import json, sys; h = json.load(open(sys.argv[1], encoding="utf-8-sig"))["hooks"]; print(sum(1 for x in h if x.get("template_source") == "library"))' "$OUT/hooks.json" 2>/dev/null || echo 0)"
if [ -n "$REGEN" ]; then
  say INFO "S5: hooks regenerated: $kept hooks from ${families//,/, } ($n_lib from hooks.txt, $((kept - n_lib)) vendor shapes)"
  echo "$STAGE: regenerated"
  exit 0
fi
say INFO "S5: $kept hooks from ${families//,/, } ($n_lib from hooks.txt, $((kept - n_lib)) vendor shapes), spoken cap $max_words words at $wpm wpm"

# ---------------------------------------------------------------------------------------------- the brief
set_activity "picking hooks"
hooks_text="$("$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
for h in json.load(open(sys.argv[1], encoding="utf-8-sig"))["hooks"]:
    print("- " + h["id"] + " (" + h["family"] + ", template " + h["template_id"] + "): spoken: " + h["spoken"] + " | on screen: " + h["on_screen"] + " | marker: " + h["marker"] + " (" + h.get("marker_kind", "") + ")")' "$OUT/hooks.json")"
read -r min_tok max_tok < <(cfg hooks.brief_tokens '[2000, 3000]' | tr -d '[]' | tr ',' ' ')
min_tok="${min_tok:-2000}"; max_tok="${max_tok:-3000}"
min_words=$(( min_tok * 10 / 13 + 60 )); max_words_brief=$(( max_tok * 10 / 13 - 60 ))
read -r len_lo len_hi < <(cfg lengths.default_s '[25, 40]' | tr -d '[]' | tr ',' ' ')
read -r list_lo list_hi < <(cfg lengths.list_s '[45, 75]' | tr -d '[]' | tr ',' ' ')
length_rule="${len_lo:-25} to ${len_hi:-40} second (${list_lo:-45} to ${list_hi:-75} seconds for a list or explainer)"
case "$dstatus" in existing) deliv_label="existing: $deliverable" ;; *) deliv_label="NEW, to create: $deliverable" ;; esac
btries="$(cfg hooks.brief_tries 3)"
prompt="$OUT/prompt-brief.md"
render_prompt "$HERE/prompt-brief.md" "$prompt" "IDEA=$IDEA_TEXT" "@EXPANSION=$exp_md" "HOOKS=$hooks_text" \
  "DELIVERABLES=$deliv_text" "LENGTH_RULE=$length_rule" "KEYWORD=$keyword" "DELIVERABLE=$deliv_label" \
  "MIN_WORDS=$min_words" "MAX_WORDS=$max_words_brief" "MIN_TOKENS=$min_tok" "MAX_TOKENS=$max_tok" \
  "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/05-hooks/prompt-brief.md"
try=1; ok=false; bres=""; berrors="[]"
while :; do
  force=()
  [ "$try" -ge "$btries" ] && force=(--force)
  session_call A research "$OUT" "$prompt" --seed-if-new --schema "$HERE/brief.schema.json" --tools "" \
    --timeout "$(cfg timeouts.brief_seconds 1200)" --name "brief-try$try" --activity "picking hooks" || stage_ai_failed
  video_type="$(json_file_field "$AI_OUT" video_type default)"
  tones="$(json_file_field "$AI_OUT" suggested_tones '[]' | tr -d '[]"')"; reels_undash tones
  {
    printf '# Brief: %s\n\n' "$(printf '%s' "$IDEA_TEXT" | cut -c1-100)"
    printf -- '- Written by 05-hooks on %s for run %s. Facts and sources: 01-research/facts.md (cite claims by number). Hooks: 05-hooks/hooks.json; hook 1 and hook 2 are chosen by 06-judge (judge.json), the brief works with any of them.\n' "$TODAY" "$RUN_ID"
    printf -- '- Comment keyword: %s (%s). Share identity: %s.\n' "$keyword" "$deliv_label" "${identity:-?}"
    printf -- '- Solution: %s. %s\n' "$("$REELS_PY" - "$RUN_DIR/02-expansion/solution.json" <<'EOF'
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
p = sys.argv[1]
if not os.path.isfile(p):
    print("none decided (the run predates the solution choice; the reel counts as not FlashFX)"); sys.exit(0)
s = json.load(open(p, encoding="utf-8-sig"))
print(f"{s.get('type')}" + (f" ({s.get('name')}" + (f", {s.get('url')}" if s.get("url") else "") + ")" if s.get("name") else ""))
EOF
)" "$([ "$(json_file_field "$RUN_DIR/02-expansion/solution.json" type none)" = flashfx ] && echo "The reel shows FlashFX solving the problem with no ad language and never implies the reel itself was made in FlashFX." || echo "The script and the caption never mention FlashFX (the solution rules of BUILD_SPEC.md S7).")"
    printf -- '- Video type: %s (%s). Suggested tones: %s.\n' "$video_type" "$length_rule" "${tones:-see below}"
  } > "$OUT/brief-header.md"
  bres="$("$REELS_PY" "$LIB/hooks.py" brief --answer "$AI_OUT" --out "$OUT/brief.md" --header "$OUT/brief-header.md" \
    --min "$min_tok" --max "$max_tok" "${force[@]}")" || stage_fail "hooks.py brief failed on $AI_OUT"
  ok="$(json_field "$bres" ok false)"
  berrors="$(json_field "$bres" errors '[]')"
  [ "$ok" = true ] && break
  [ "$try" -ge "$btries" ] && break
  say WARN "S5: the brief missed the length ($(json_field "$berrors" 0 "" | cut -c1-110)), asking again (try $((try + 1))/$btries)"
  try=$((try + 1))
  prompt="$OUT/prompt-brief-fix$try.md"
  write_retry_prompt "$prompt" research 05-hooks "$berrors" "Answer with the complete JSON object of the brief (brief_markdown with every section, video_type, suggested_tones)."
done
[ "$ok" = true ] || flag_once "brief.md is outside the token range after $btries tries: $(json_field "$berrors" 0 "unknown" | cut -c1-140)"
say INFO "S5: brief.md $(json_field "$bres" tokens 0) tokens ($(json_field "$bres" words 0) words), video type $(json_field "$bres" video_type default); session A done"
echo "$STAGE: done"
exit 0
