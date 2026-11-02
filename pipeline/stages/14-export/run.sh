#!/usr/bin/env bash
# run.sh for 14-export (Caption and export, S14): BUILD_SPEC.md section 5, S14, and section 8. One call to the script
# model (config models.script) writes the caption's body, the one ask and the hashtags; pipeline/lib/caption.py gathers
# the inputs (hook 1 as the fixed first line, the keyword and its deliverable, the solution and its rules, the script's
# lines, the brief, the voice hints, the facts the script cites) and composes and checks the result: the first line is
# hook 1 in 125 characters or fewer, one ask (the keyword, once), 3 to 5 hashtags, no link, the solution rules (no
# FlashFX mention unless the solution is flashfx, nothing implying the reel was made in FlashFX, no ad language),
# humanize.py applied, the vendor caption.py lint with no FAIL. A caption that breaks a rule is asked again once in
# the same session with the exact problems; the second answer is written anyway with a NEEDS REVIEW flag (a quality
# loop, never an error). Outputs: export.json (primary: what the runner's export step renders into Ncaptions.txt and
# copies), caption.txt, caption-data.json, prompt-caption*.md, calls/. The export itself (the number, the files, the
# move into exports/N/, the history line) is the runner's step after this stage (pipeline/lib/export.py).
#   bash pipeline/stages/14-export/run.sh <run_dir>                        (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 14-export export.json
set_activity "writing caption"
printf 'activity: writing caption\n'
for f in 07-script/script.json 13-render/final.mp4 13-render/hook2.mp4; do
  [ -f "$RUN_DIR/$f" ] || stage_fail "$f is missing: the stage that writes it did not run"
done
VENDOR="$REELS_REPO/$(cfg paths.vendor pipeline/vendor/ig-agent-skill)"
for f in caption.py humanize.py slop.json; do
  [ -f "$VENDOR/$f" ] || stage_fail "$VENDOR/$f is missing (the vendored instagram-agent-skill scripts, BUILD_SPEC.md section 10)"
done
TRIES="$(cfg caption.tries 2)"; case "$TRIES" in ''|*[!0-9]*|0) TRIES=2 ;; esac
T_CAPTION="$(cfg timeouts.caption_seconds 900)"

DATA="$OUT/caption-data.json"
dres="$("$REELS_PY" "$LIB/caption.py" data --run-dir "$RUN_DIR" --out "$DATA" --config "$REELS_CONFIG")" || stage_fail "caption.py data failed (see the lines above)"
hook1="$(json_file_field "$DATA" hook1 "")"; keyword="$(json_file_field "$DATA" keyword "")"
[ -n "$hook1" ] || stage_fail "no hook 1 found in 07-script/script.json or 06-judge/judge.json"
[ -n "$keyword" ] || stage_fail "no comment keyword found in script.json or expansion.json"
sol_type="$(json_file_field "$DATA" solution.type none)"
say INFO "S14: caption for hook 1 \"$(cut_text "$hook1" 60)\", keyword $keyword, solution $sol_type, $(json_field "$dres" facts 0) cited facts, $(json_field "$dres" needs_review 0) flags"

prompt="$OUT/prompt-caption.md"
render_prompt "$HERE/prompt-caption.md" "$prompt" "IDEA=$(json_file_field "$DATA" idea "")" "HOOK1=$hook1" "KEYWORD=$keyword" \
  "DELIVERABLE=$(json_file_field "$DATA" deliverable "")" "PROBLEM=$(json_file_field "$DATA" problem "")" "IDENTITY=$(json_file_field "$DATA" identity "")" \
  "SOLUTION_LINE=$(json_file_field "$DATA" solution_line "")" "SOLUTION_RULES=$(json_file_field "$DATA" solution_rules "")" \
  "BEATS=$(json_file_field "$DATA" beats "")" "ONE_IDEA=$(json_file_field "$DATA" one_idea "")" "VOICE=$(json_file_field "$DATA" voice "")" \
  "FIRST_LINE_MAX=$(json_file_field "$DATA" first_line_max 125)" "BODY_MIN=$(json_file_field "$DATA" body_min 150)" "BODY_MAX=$(json_file_field "$DATA" body_max 900)" \
  "HASHTAG_MIN=$(json_file_field "$DATA" hashtag_min 3)" "HASHTAG_MAX=$(json_file_field "$DATA" hashtag_max 5)" "NOTE=$(stage_note_section)" \
  || stage_fail "cannot render pipeline/stages/14-export/prompt-caption.md"

try=1; ok=false; result=""; errors="[]"; sid=""
while :; do
  force=()
  [ "$try" -ge "$TRIES" ] && force=(--force)
  if [ -n "$sid" ]; then
    ai script "$OUT" "$prompt" --resume "$sid" --schema "$HERE/model.schema.json" --tools "" --timeout "$T_CAPTION" --name "caption-try$try" --activity "writing caption"; rc=$?
    if [ "$rc" = 3 ]; then
      # the session is gone: the full prompt again, with the problems appended
      prompt_full="$OUT/prompt-caption-full$try.md"
      { cat "$OUT/prompt-caption.md"; printf '\n## Your previous answer did not pass the checks\n\n'; "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
for e in json.loads(sys.argv[1] or "[]"): print("- " + e)' "$errors"; printf '\nAnswer again with the complete JSON object, fixing exactly these points.\n'; } > "$prompt_full"
      ai script "$OUT" "$prompt_full" --schema "$HERE/model.schema.json" --tools "" --timeout "$T_CAPTION" --name "caption-try$try-fresh" --activity "writing caption"; rc=$?
    fi
    [ "$rc" = 0 ] || stage_ai_failed
  else
    ai script "$OUT" "$prompt" --schema "$HERE/model.schema.json" --tools "" --timeout "$T_CAPTION" --name "caption-try$try" --activity "writing caption" || stage_ai_failed
  fi
  sid="$AI_SESSION"
  result="$("$REELS_PY" "$LIB/caption.py" compose --run-dir "$RUN_DIR" --data "$DATA" --answer "$AI_OUT" --out "$OUT/export.json" --vendor "$VENDOR" "${force[@]}")" \
    || stage_fail "caption.py compose failed on $AI_OUT"
  ok="$(json_field "$result" ok false)"
  errors="$(json_field "$result" errors '[]')"
  [ "$ok" = true ] && break
  [ "$try" -ge "$TRIES" ] && break
  say WARN "S14: the caption missed a rule ($(json_field "$errors" 0 "" | cut -c1-110)), asking again (try $((try + 1))/$TRIES)"
  try=$((try + 1))
  prompt="$OUT/prompt-caption-fix$try.md"
  write_retry_prompt "$prompt" script 14-export "$errors" "Answer with the complete JSON object {body, ask_line, hashtags, search_terms, notes}; the first line (hook 1) is added by the runner, write only what follows it."
done
if [ "$ok" != true ]; then
  flag_once "caption breaks a rule after $TRIES tries: $(json_field "$errors" 0 "unknown" | cut -c1-140)"
fi
warns="$(json_field "$result" lint_warnings '[]' | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
w = json.loads(sys.stdin.read() or "[]"); print(("; ".join(w))[:160] if w else "none")')"
say INFO "S14: caption $(json_field "$result" caption_chars 0) chars (first line $(json_field "$result" first_line_chars 0)), $(json_field "$result" hashtags '[]' | tr -d '[]"' | tr ',' ' ' | sed 's/  */ /g'), lint $(json_field "$result" lint_verdict "?") (warnings: $warns), humanize changed $(json_field "$result" humanize_changes 0)"
echo "$STAGE: done"
exit 0
