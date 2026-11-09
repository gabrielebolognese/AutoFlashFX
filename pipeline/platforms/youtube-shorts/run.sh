#!/usr/bin/env bash
# run.sh of the youtube-shorts exporter (BUILD_SPEC.md section 8, M19). Same shape as pipeline/stages/14-export/run.sh: one
# call to the script model (config models.script) writes the title, the description, the pinned comment and the hashtags;
# exporter.py (next to this file) prepares the prompt's data from <run_dir>/export/input.json and checks and composes the
# result: title one line within export.caption_max with no hashtag or link (a serial part reads "<hook phrase> | <Story
# title>, Part <N>"), a description within export.description_max with a one-sentence first line, no long paragraph, a list
# of 3 to 6 "- " lines, exactly 4 hashtags on the last line, different from the channel's earlier descriptions, and a
# pinned comment with a question (and a line about the next part). An answer that breaks a rule is asked again once in the
# same session with the exact problems; the second answer is written anyway (--force) with NEEDS REVIEW lines in
# export.json (a quality loop, never an error). After it the description is recorded in the channel's
# logs/descriptions.jsonl (once per run). Outputs in <run_dir>/14-export/: export.json (primary: what the runner's export
# step renders into <id>-Ncaptions.txt), input.json (the input with earlier_descriptions filled), export-data.json,
# prompt-export*.md, calls/.
#   bash pipeline/platforms/youtube-shorts/run.sh <run_dir>                (started by the runner's export step)
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
set_activity "writing the title and description"
printf 'activity: writing the title and description\n'
EXPORTER="$HERE/exporter.py"
INPUT_SRC="$RUN_DIR/export/input.json"
[ -f "$INPUT_SRC" ] || stage_fail "export/input.json is missing: the format's export adapter did not run"
VENDOR="$REELS_REPO/$(cfg paths.vendor pipeline/vendor/ig-agent-skill)"
for f in humanize.py slop.json; do
  [ -f "$VENDOR/$f" ] || stage_fail "$VENDOR/$f is missing (the vendored instagram-agent-skill scripts, BUILD_SPEC.md section 10)"
done
TRIES="$(cfg caption.tries 2)"; case "$TRIES" in ''|*[!0-9]*|0) TRIES=2 ;; esac
T_EXPORT="$(cfg timeouts.caption_seconds 900)"
DESCRIPTIONS="$(chpath logs/descriptions.jsonl)" || stage_fail "cannot resolve the channel's logs/descriptions.jsonl (is a channel set?)"

# the input with the channel's last 30 descriptions filled in when the adapter gave none
INPUT="$OUT/input.json"
"$REELS_PY" - "$INPUT_SRC" "$INPUT" "$DESCRIPTIONS" <<'PY' || stage_fail "cannot prepare $INPUT (see the lines above)"
import json, re, sys
src, dst, desc_path = sys.argv[1:4]
def win(p):
    m = re.match(r"^/([A-Za-z])/(.*)$", p)
    return f"{m.group(1).upper()}:/{m.group(2)}" if m else p
with open(win(src), encoding="utf-8-sig") as f:
    inp = json.load(f)
if not inp.get("earlier_descriptions"):
    earlier = []
    try:
        with open(win(desc_path), encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line).get("description")
                except ValueError:
                    continue
                if isinstance(d, str) and d.strip():
                    earlier.append(d)
    except OSError:
        pass
    inp["earlier_descriptions"] = earlier[-30:]
with open(win(dst), "w", encoding="utf-8", newline="\n") as f:
    json.dump(inp, f, ensure_ascii=False, indent=1)
    f.write("\n")
PY

DATA="$OUT/export-data.json"
dres="$("$REELS_PY" "$EXPORTER" data --input "$INPUT" --out "$DATA")" || stage_fail "exporter.py data failed: the input does not fit input.schema.json (see the lines above)"
hook1="$(json_file_field "$DATA" hook1 "")"
[ -n "$hook1" ] || stage_fail "no hook 1 in export/input.json"
say INFO "youtube-shorts export: hook 1 \"$(cut_text "$hook1" 60)\", serial $(json_field "$dres" serial false), part $(json_field "$dres" part 0), $(json_field "$dres" earlier 0) earlier descriptions"

prompt="$OUT/prompt-export.md"
render_prompt "$HERE/prompt.md" "$prompt" \
  "BRAND_NAME=$(json_file_field "$DATA" brand_name "")" "SUMMARY=$(json_file_field "$DATA" summary "")" "HOOK1=$hook1" \
  "SERIAL_BLOCK=$(json_file_field "$DATA" serial_block "")" "SCRIPT=$(json_file_field "$DATA" script "")" "BEATS=$(json_file_field "$DATA" beats "")" \
  "FACTS=$(json_file_field "$DATA" facts "")" "EARLIER_COUNT=$(json_file_field "$DATA" earlier_count 0)" \
  "OVERLAP_PERCENT=$(json_file_field "$DATA" overlap_percent 30)" "EARLIER_OPENERS=$(json_file_field "$DATA" earlier_openers "")" \
  "EARLIER_DESCRIPTIONS=$(json_file_field "$DATA" earlier_descriptions "")" "NOTE=$(stage_note_section)" \
  "TITLE_RULE=$(json_file_field "$DATA" title_rule "")" "DESCRIPTION_MAX=$(json_file_field "$DATA" description_max 1000)" \
  "PARAGRAPH_MAX=$(json_file_field "$DATA" paragraph_max 200)" "PART_RULE=$(json_file_field "$DATA" part_rule "")" \
  "HASHTAG_RULE=$(json_file_field "$DATA" hashtag_rule "")" "PINNED_RULE=$(json_file_field "$DATA" pinned_rule "")" \
  || stage_fail "cannot render pipeline/platforms/youtube-shorts/prompt.md"

REEL=""
if [ -f "$RUN_DIR/13-render/final.mp4" ]; then
  REEL="$(cd "$RUN_DIR/13-render" && pwd)/final.mp4"
  command -v cygpath >/dev/null 2>&1 && REEL="$(cygpath -m "$REEL")"
fi
reel_args=()
[ -n "$REEL" ] && reel_args=(--reel "$REEL")

try=1; ok=false; result=""; errors="[]"; sid=""
while :; do
  force=()
  [ "$try" -ge "$TRIES" ] && force=(--force)
  if [ -n "$sid" ]; then
    ai script "$OUT" "$prompt" --resume "$sid" --schema "$HERE/model.schema.json" --tools "" --timeout "$T_EXPORT" --name "export-try$try" --activity "writing the title and description"; rc=$?
    if [ "$rc" = 3 ]; then
      # the session is gone: the full prompt again, with the problems appended
      prompt_full="$OUT/prompt-export-full$try.md"
      { cat "$OUT/prompt-export.md"; printf '\n## Your previous answer did not pass the checks\n\n'; "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
for e in json.loads(sys.argv[1] or "[]"): print("- " + e)' "$errors"; printf '\nAnswer again with the complete JSON object, fixing exactly these points.\n'; } > "$prompt_full"
      ai script "$OUT" "$prompt_full" --schema "$HERE/model.schema.json" --tools "" --timeout "$T_EXPORT" --name "export-try$try-fresh" --activity "writing the title and description"; rc=$?
    fi
    [ "$rc" = 0 ] || stage_ai_failed
  else
    ai script "$OUT" "$prompt" --schema "$HERE/model.schema.json" --tools "" --timeout "$T_EXPORT" --name "export-try$try" --activity "writing the title and description" || stage_ai_failed
  fi
  sid="$AI_SESSION"
  result="$("$REELS_PY" "$EXPORTER" compose --input "$INPUT" --answer "$AI_OUT" --out "$OUT/export.json" --vendor "$VENDOR" "${reel_args[@]}" "${force[@]}")" \
    || stage_fail "exporter.py compose failed on $AI_OUT"
  ok="$(json_field "$result" ok false)"
  errors="$(json_field "$result" errors '[]')"
  [ "$ok" = true ] && break
  [ "$try" -ge "$TRIES" ] && break
  say WARN "youtube-shorts export: the text missed a rule ($(json_field "$errors" 0 "" | cut -c1-110)), asking again (try $((try + 1))/$TRIES)"
  try=$((try + 1))
  prompt="$OUT/prompt-export-fix$try.md"
  write_retry_prompt "$prompt" script 14-export "$errors" "Answer with the complete JSON object {title, description, pinned_comment, hashtags}; count every character against the limits."
done
if [ "$ok" != true ]; then
  flag_once "youtube-shorts text breaks a rule after $TRIES tries: $(json_field "$errors" 0 "unknown" | cut -c1-140)"
fi
[ -f "$OUT/export.json" ] || stage_fail "exporter.py wrote no export.json"
"$REELS_PY" "$EXPORTER" record --input "$INPUT" --export "$OUT/export.json" --descriptions "$DESCRIPTIONS" >/dev/null || stage_fail "exporter.py record failed on $DESCRIPTIONS"
say INFO "youtube-shorts export: title $(json_field "$result" title_chars 0) chars, description $(json_field "$result" description_chars 0) chars, hashtags $(json_field "$result" hashtags '[]' | tr -d '[]"' | tr ',' ' ' | sed 's/  */ /g'), humanize changed $(json_field "$result" humanize_changes 0)"
echo "$STAGE: done"
exit 0
