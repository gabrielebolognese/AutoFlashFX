# pipeline/lib/stage.sh: shared helpers for the real stage scripts (pipeline/stages/<stage>/run.sh, from M4 on).
# A stage sources common.sh, log.sh, config.sh, state.sh, status.sh, ai.sh, session.sh and this file, then calls
# stage_begin. The runner starts a stage as `bash run.sh <run_dir>` with stdout and stderr in <stage>/stage.log
# and its terminal on fd 3 (REELS_SAY_FD=3), so `say` lines reach the screen and everything else stays in the log.
#
#   stage_begin <run_dir> <stage> <primary output>   sets RUN_DIR, STAGE, OUT (the stage folder), RUN_ID, PRIMARY,
#                                                    IDEA_ID, IDEA_TEXT, TODAY (YYYY-MM-DD) and RESTART_NOTE (the
#                                                    runner's note after an automatic fix, read and removed)
#   stage_drop "<reason>" [<detail json>]            write result.json and exit 10 (the runner prints DROP, removes the
#                                                    idea from ideas.txt and writes the history line with the reason)
#   stage_block "<reason>"                           write result.json and exit 20 (the runner prints BLOCK)
#   stage_fail "<message>"                           print the message as the last log line and exit 1: a code error for
#                                                    the review and fix loop (BUILD_SPEC.md 4.2)
#   stage_ai_failed                                  after a failed ai() or session_call: the error, exit 1 (ai() wrote
#                                                    <stage>/error.json, which the runner's report includes)
#   flag_once "<text>"                               run_flag (a NEEDS REVIEW flag plus the FLAG line) unless the same
#                                                    text is already recorded for this run (a stage may run twice)
#   profile_file <name>                              print the path of library/profile/<name> under the state root;
#                                                    exit 1 (and print nothing) when it is missing
#   render_prompt <template> <out> [KEY=VALUE | @KEY=path]...   pipeline/lib/prompt.py render: {{KEY}} placeholders,
#                                                    @KEY=path inlines a file; a missing placeholder is an error
#   stage_note_section                               the restart note as a prompt section (empty when there is none)
#   cfg_list <key>                                   a config list, one item per line (for --allow rules)
#   research_call_args                               fill RESEARCH_CALL_ARGS with the research model's tool options for
#                                                    ai(): --tools (config research.tools), one --allow per rule of
#                                                    research.allowed (the read-only gh forms, the screenshot tool) and
#                                                    one --deny per rule of research.denied (the gh forms that write);
#                                                    the defaults below apply when a key is missing or empty
#   count_glob <pattern>                             how many files match the glob
#   json_file_field <file> <key> [default]           json_field over a file's content
#
# Exit codes of a stage (PLAN.md section 0): 0 done (the runner validates the primary output against schema.json
# and writes .done), 10 drop, 20 block, anything else a code error. A stage that wants other stages to run again
# after it (the gate reopening 04-angle, the angle stage reopening 03-gate) writes their keys, one per line, to
# <stage>/reopen.txt: state.py stage-done reopens them in the same write that marks the stage done.

[ -n "${REELS_STAGE_LOADED:-}" ] && return 0
REELS_STAGE_LOADED=1

RUN_DIR=""; STAGE=""; OUT=""; RUN_ID=""; PRIMARY=""; IDEA_ID=""; IDEA_TEXT=""; TODAY=""; RESTART_NOTE=""

stage_begin() {
  RUN_DIR="$1"; STAGE="$2"; PRIMARY="$3"
  OUT="$RUN_DIR/$STAGE"
  mkdir -p "$OUT"
  RUN_ID="$(basename "$RUN_DIR")"
  IDEA_ID="$(state_get "$RUN_DIR" idea.id unknown 2>/dev/null)"
  IDEA_TEXT="$(state_get "$RUN_DIR" idea.text "" 2>/dev/null)"
  printf -v TODAY '%(%Y-%m-%d)T' -1
  RESTART_NOTE="$(ai_restart_note "$OUT" 2>/dev/null || true)"
  rm -f "$OUT/result.json" "$OUT/reopen.txt"
  printf '%s: start (pid %s, run %s, %s)\n' "$STAGE" "$$" "$RUN_ID" "$TODAY"
  if [ -n "$RESTART_NOTE" ]; then printf '%s: restart note from the runner:\n%s\n' "$STAGE" "$RESTART_NOTE"; fi
  return 0
}

stage_result_json() {  # stage_result_json "<reason>" "<detail json or empty>"
  local reason="$1" detail="${2:-}"
  reels_undash reason
  "$REELS_PY" - "$reason" "$detail" "$STAGE" "$OUT/result.json" <<'EOF'
import json, sys
reason, detail, stage, path = sys.argv[1:5]
try:
    detail_value = json.loads(detail) if detail else None
except ValueError:
    detail_value = detail
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"reason": reason, "detail": detail_value, "stage": stage}, f, ensure_ascii=False, indent=1)
EOF
}

stage_drop() {
  stage_result_json "$1" "${2:-}"
  local reason="$1"; reels_undash reason
  printf '%s: drop: %s\n' "$STAGE" "$reason"
  exit 10
}

stage_block() {
  stage_result_json "$1" "${2:-}"
  local reason="$1"; reels_undash reason
  printf '%s: block: %s\n' "$STAGE" "$reason"
  exit 20
}

stage_fail() {
  local msg="$1"; reels_undash msg
  printf '%s: %s\n' "$STAGE" "$msg" >&2
  exit 1
}

stage_ai_failed() {
  local msg="${AI_ERROR:-the model call failed}"; reels_undash msg
  printf '%s: model call failed (%s): %s\n' "$STAGE" "${AI_CLASS:-error}" "$msg" >&2
  exit 1
}

flag_once() {
  local flags
  flags="$(state_get "$RUN_DIR" flags "[]" 2>/dev/null)"
  if "$REELS_PY" -c 'import json, sys
flags = json.loads(sys.argv[1] or "[]")
sys.exit(0 if any(f.get("text") == sys.argv[2] for f in flags if isinstance(f, dict)) else 1)' "$flags" "$1" 2>/dev/null; then
    return 0
  fi
  run_flag "$RUN_DIR" "$STAGE" "$1"
}

profile_file() {
  local path="$REELS_ROOT/$(cfg paths.profile library/profile)/$1"
  [ -f "$path" ] || return 1
  printf '%s' "$path"
}

render_prompt() {
  local tpl="$1" out="$2" a
  shift 2
  local -a args=()
  for a in "$@"; do
    case "$a" in
      @*) args+=(--file "${a#@}") ;;
      *) args+=(--set "$a") ;;
    esac
  done
  "$REELS_PY" "$REELS_PIPELINE/lib/prompt.py" render "$tpl" --out "$out" "${args[@]}"
}

stage_note_section() {
  [ -n "${RESTART_NOTE:-}" ] || return 0
  printf '## Note from the runner\n\n%s\n\nThe outputs of that attempt were discarded: do the work again from the inputs and answer in full.\n' "$RESTART_NOTE"
}

cfg_list() {
  cfg "$1" '[]' | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
try:
    items = json.loads(sys.stdin.read() or "[]")
except ValueError:
    items = []
for item in items if isinstance(items, list) else []:
    print(item)'
}

# The research model's tools (S1 and S4; BUILD_SPEC.md S1, DECISIONS.md 104 and 111). Pre-approved: the web tools,
# Read, the read-only gh forms the spec names (repo view, README, releases, stars, last commit) and the screenshot
# tool. Denied, because the model reads untrusted pages with the user's gh login: the gh forms that act on the
# account or the disk (auth, gist, clone, download, the verbs that write, gh api with a method or a field flag,
# which turns a read into a mutation). A deny rule wins over an allow rule in every permission mode and applies to
# every subcommand of a compound command; a `*` matches any text, "gh api* -X*" covers the flag in any position.
# config research.allowed and research.denied replace these lists; an empty or missing list falls back to them.
RESEARCH_TOOLS_DEFAULT="WebSearch WebFetch Read Bash"
RESEARCH_ALLOWED_DEFAULT=(WebSearch WebFetch Read "Bash(gh repo view *)" "Bash(gh release list *)" "Bash(gh release view *)"
  "Bash(gh api repos/*)" "Bash(bash pipeline/bin/screenshot *)")
RESEARCH_DENIED_DEFAULT=("Bash(gh auth *)" "Bash(gh gist *)" "Bash(gh repo clone *)" "Bash(gh release download *)"
  "Bash(gh * create *)" "Bash(gh * delete *)" "Bash(gh * edit *)" "Bash(gh * comment *)" "Bash(gh * merge *)"
  "Bash(gh * close *)" "Bash(gh * reopen *)" "Bash(gh * review *)" "Bash(gh * fork *)" "Bash(gh * sync *)"
  "Bash(gh * transfer *)" "Bash(gh * lock *)" "Bash(gh * upload *)" "Bash(gh * run *)" "Bash(gh * rerun *)"
  "Bash(gh * cancel *)" "Bash(gh * set *)" "Bash(gh * add *)" "Bash(gh * archive *)" "Bash(gh * rename *)"
  "Bash(gh api* -X*)" "Bash(gh api* --method*)" "Bash(gh api* -f*)" "Bash(gh api* -F*)" "Bash(gh api* --field*)"
  "Bash(gh api* --raw-field*)" "Bash(gh api* --input*)")
RESEARCH_CALL_ARGS=()
research_call_args() {
  local rule n
  RESEARCH_CALL_ARGS=(--tools "$(cfg research.tools "$RESEARCH_TOOLS_DEFAULT")")
  n=0
  while IFS= read -r rule; do [ -n "$rule" ] || continue; RESEARCH_CALL_ARGS+=(--allow "$rule"); n=$((n + 1)); done < <(cfg_list research.allowed)
  if [ "$n" -eq 0 ]; then for rule in "${RESEARCH_ALLOWED_DEFAULT[@]}"; do RESEARCH_CALL_ARGS+=(--allow "$rule"); done; fi
  n=0
  while IFS= read -r rule; do [ -n "$rule" ] || continue; RESEARCH_CALL_ARGS+=(--deny "$rule"); n=$((n + 1)); done < <(cfg_list research.denied)
  if [ "$n" -eq 0 ]; then for rule in "${RESEARCH_DENIED_DEFAULT[@]}"; do RESEARCH_CALL_ARGS+=(--deny "$rule"); done; fi
}

count_glob() {
  local n=0 f
  for f in $1; do [ -e "$f" ] && n=$((n + 1)); done
  printf '%s' "$n"
}

json_file_field() {
  local file="$1"; shift
  if [ -f "$file" ]; then json_field "$(cat "$file")" "$@"; else
    if [ $# -ge 2 ]; then printf '%s\n' "$2"; else return 3; fi
  fi
}

write_retry_prompt() {  # write_retry_prompt <out> <role> <stage> '<errors json list>' ["extra line"] [task]
  # task (M6): a "# Task: <task>" header line after the stage line, for stages whose calls differ by task (S7's
  # write, cut, claims, pick); the fake claude serves fixtures by it
  "$REELS_PY" - "$1" "$2" "$3" "$4" "${5:-}" "${6:-}" <<'PY'
import json, sys
out, role, stage, errors_json, extra, task = sys.argv[1:7]
try:
    errors = json.loads(errors_json or "[]")
except ValueError:
    errors = [errors_json]
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write(f"# Role: {role}\n# Stage: {stage}\n" + (f"# Task: {task}\n" if task else "") + "\nYour previous answer did not pass the stage's checks:\n")
    for e in errors:
        f.write(f"- {e}\n")
    f.write("\nAnswer again with the complete JSON object (every field, not only the changed ones), fixing exactly these points and keeping everything else as it was. Only the JSON object, nothing else.\n")
    if extra:
        f.write(extra.rstrip() + "\n")
PY
}
