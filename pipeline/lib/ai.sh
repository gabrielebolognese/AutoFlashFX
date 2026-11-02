# pipeline/lib/ai.sh: every model call goes through ai() (BUILD_SPEC.md section 3). Source common.sh, log.sh,
# config.sh, state.sh and status.sh first (ai.sh sources limits.sh and errors.sh itself).
#
#   ai <role> <stage_dir> <prompt_file> [options]
#     Runs: claude -p --model <models.role.model> --effort <models.role.effort> --output-format json
#           --permission-mode auto --permission-prompts none [--resume SID] [--json-schema SCHEMA]
#           [--tools LIST] [--allowedTools RULES] [--disallowedTools RULES] [--add-dir DIR...] [--max-turns N]
#     with the prompt on stdin (no command-line size limit, no clash with the variadic flags). The raw output goes
#     to <stage_dir>/calls/NNN.json (stderr to NNN.err, the command and timing to NNN.meta, a structured output to
#     NNN.out.json). Model names and efforts come from config.json only.
#     Options:
#       --schema FILE      --json-schema with the file's content; the structured output is validated against the
#                          file with jsonschema; an invalid one gets one retry in the same session with the errors,
#                          then it is a code error (the stage's one schema retry of BUILD_SPEC.md section 5)
#       --resume SID       continue that session
#       --session KEY      resume the session stored in state.json (sessions.KEY) when there is one, and store the
#                          session id there after a success (the run dir is the parent of stage_dir)
#       --tools "A B C"    the tools available to the call (--tools, comma or space separated; "" = none) and, unless
#                          --allowed is given, the same list pre-approved with --allowedTools
#       --allowed "rules"  explicit --allowedTools rules (space separated, for example "Read Edit(pipeline/**)")
#       --allow RULE       one more --allowedTools rule, verbatim (repeatable; for rules with spaces such as
#                          "Bash(gh *)"); when --allow or --allowed is given the --tools list is not pre-approved
#                          by itself, so a bare tool name (Bash) must be listed to be approved without rules
#       --disallow "rules" extra --disallowedTools rules (the protected files below are always denied)
#       --deny RULE        one more --disallowedTools rule, verbatim (repeatable; for rules with spaces such as
#                          "Bash(gh gist *)"); a deny rule wins over every allow rule in every permission mode
#       --add-dir DIR      extra working directory (repeatable)
#       --cwd DIR          where the call runs (default: the repo root)
#       --timeout S        seconds before the call is killed (default timeouts.model_call_seconds; a kill is a
#                          transient error)
#       --max-turns N      --max-turns
#       --activity TEXT    the activity to restore after a wait (default: the current one)
#       --name NAME        a suffix for the call files (calls/NNN-NAME.json)
#       --no-protect       skip the protected files snapshot (tests)
#     Sets: AI_CALL (the NNN.json path), AI_RESULT (the result text), AI_SESSION (the session id), AI_OUT (the
#     structured output file, or ""), AI_CLASS (ok, error, limit, transient), AI_ERROR (the one-line message, never
#     with an em dash: errors.py and ai_write_error clean it, BUILD_SPEC.md 0.7), AI_DETAIL (a short label),
#     AI_FATAL (1 when the reviewer would hit the same wall: login, key, unknown option).
#     Returns 0 on success; 1 on a code error (<stage_dir>/error.json written: class, message, detail, signature,
#     call, rc, role, model, fatal, resume_failed); 3 when the --resume or --session session no longer exists
#     (error.json too; the stored session is cleared so the caller can start a fresh one).
#
#   Failures are classified in the spec's order (pipeline/lib/errors.py): a usage limit waits until the reset plus
#   the margin (limits.sh) and retries the same call in the same session (an unparseable limit sleeps 30 min and
#   probes the probe model every 30 min); a transient error backs off 60 s, 4 min, 16 min (errors.transient_
#   backoff_seconds, scaled by REELS_SLEEP_SCALE) and then counts as a code error; everything else is a code error
#   for the review and fix loop (review.sh).
#
#   Protected files: model calls may not write ideas.txt, library/, styles/ or exports/ and may not read .env.
#   ai() denies Edit and Write on those paths and takes a snapshot of the protected text files before every call
#   (pipeline/lib/protect.py); a changed file is restored and the call becomes a code error.
#
#   ai_restart_note <stage_dir>   prints and removes <stage_dir>/restart-note.md (written by the runner before a
#                                 stage restarts after an automatic fix), so a stage that resumes a session can
#                                 tell the model what failed and what was fixed
#   ai_probe <stage_dir>          one "reply ok" call with the probe model; 0 when it answers (the limit probe)
#
#   Fault injection (M13, the hardening tests; never set in normal use): REELS_FAULT is a comma list of
#     limit:<stage>[@<n>]   the next call in that stage does not reach claude: its NNN.json is a session-limit
#                           result ("You've hit your session limit · resets 3:48pm (Europe/Rome)") with a reset
#                           REELS_FAULT_MINUTES (default 3) ahead, so the real classifier, the LIMIT line, logs/limits.log,
#                           the wait, the RESUME line and the retry in the same session all run. REELS_FAULT_WAIT=fast
#                           fast-forwards that one wait (the other waits keep their scale).
#     kill:<stage>[@<n>]    at the next call in that stage the runner (its pid in .locks/runner/pid) and the stage
#                           are killed with SIGKILL, as a crash or a closed terminal would (the restart test)
#   @<n> limits the fault to the n-th run folder under runs/ (by creation time: @2 is the second idea of a sandbox).
#   Each fault fires once: logs/.faults/<kind>-<stage>[@<n>] records it, so a restarted runner does not fire it again.

[ -n "${REELS_AI_LOADED:-}" ] && return 0
REELS_AI_LOADED=1
_ai_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
declare -F json_eval >/dev/null 2>&1 || source "$_ai_lib/state.sh"
declare -F set_activity >/dev/null 2>&1 || source "$_ai_lib/status.sh"
source "$_ai_lib/limits.sh"
source "$_ai_lib/errors.sh"
unset _ai_lib

AI_CALL=""; AI_RESULT=""; AI_SESSION=""; AI_OUT=""; AI_CLASS=""; AI_ERROR=""; AI_DETAIL=""; AI_FATAL=0

ai_next_number() {  # the next NNN in a calls folder
  local last
  last="$(ls "$1" 2>/dev/null | grep -o -E '^[0-9]{3}' | sort | tail -n 1)"
  printf '%03d' $(( 10#${last:-0} + 1 ))   # 10#: 008 and 009 are not octal
}

ai_protected_rules() {  # the --disallowedTools rules for the protected files (config review.protected_paths)
  local paths p rules=()
  paths="$(cfg review.protected_paths '["ideas.txt","library","styles","exports"]' | tr -d '[]"' | tr ',' ' ')"
  for p in $paths; do
    case "$p" in
      *.*) rules+=("Edit($p)" "Write($p)" "MultiEdit($p)") ;;
      *) rules+=("Edit($p/**)" "Write($p/**)" "MultiEdit($p/**)" "NotebookEdit($p/**)") ;;
    esac
  done
  rules+=("Read(.env)" "Read(.env.*)")
  printf '%s\n' "${rules[@]}"
}

ai_restart_note() {
  local file="$1/restart-note.md"
  [ -f "$file" ] || return 1
  cat "$file"
  rm -f "$file"
}

ai_write_error() {  # ai_write_error <stage_dir> <class> <message> <detail> <call> <rc> <role> <model> <fatal> <resume_failed>
  local __msg="$3"; reels_undash __msg; set -- "$1" "$2" "$__msg" "${@:4}"   # no em dash in error.json
  "$REELS_PY" - "$@" <<'EOF'
import hashlib, json, os, re, sys, time
d = dict(zip(("stage_dir", "class", "message", "detail", "call", "rc", "role", "model", "fatal", "resume_failed"), sys.argv[1:]))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0] not in ("-", "") else __file__)), "."))
try:
    import errors as errors_lib
    sig = errors_lib.signature(d["message"])
except Exception:
    sig = hashlib.sha1(re.sub(r"\d+", "N", d["message"].lower()).encode()).hexdigest()[:12]
out = {"class": d["class"], "message": d["message"], "detail": d["detail"], "signature": sig, "call": d["call"],
       "rc": int(d["rc"] or 0), "role": d["role"], "model": d["model"], "fatal": d["fatal"] == "1",
       "resume_failed": d["resume_failed"] == "1", "at": time.strftime("%Y-%m-%d %H:%M:%S")}
with open(os.path.join(d["stage_dir"], "error.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
EOF
}

ai_extract() {  # ai_extract <NNN.json> <out.json or ""> -> prints the result text; writes the structured output
  "$REELS_PY" - "$1" "${2:-}" <<'EOF'
import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
with open(sys.argv[1], encoding="utf-8-sig") as f:
    data = json.load(f)
if sys.argv[2]:
    so = data.get("structured_output")
    if so is None:
        text = data.get("result") or ""
        try:
            so = json.loads(text)
        except ValueError:
            so = None
    if so is not None:
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
            json.dump(so, f, ensure_ascii=False, indent=1)
print(data.get("result") or "")
EOF
}

ai_probe() {  # ai_probe <stage_dir> -> 0 when the probe model answers
  local stage_dir="$1" calls="$1/calls" n base model effort rc cls
  mkdir -p "$calls"
  n="$(ai_next_number "$calls")"; base="$calls/$n-probe"
  model="$(cfg models.probe.model)"; effort="$(cfg models.probe.effort low)"
  printf 'reply ok' | timeout -k 10 "$(cfg timeouts.probe_seconds 300)" "${REELS_CLAUDE:-claude}" -p --model "$model" \
    --effort "$effort" --output-format json --permission-mode auto --permission-prompts none --tools "" \
    >"$base.json" 2>"$base.err"; rc=$?
  printf 'role: probe\nmodel: %s\nrc: %s\n' "$model" "$rc" > "$base.meta"
  cls="$(json_field "$(error_classify "$rc" "$base.json" "$base.err")" class error)"
  [ "$cls" = ok ]
}

ai_fault_ordinal() {  # ai_fault_ordinal <run_dir>: its position among the run folders by creation time (1-based)
  "$REELS_PY" - "$1" <<'EOF'
import json, os, sys
run = os.path.normpath(sys.argv[1]); runs = os.path.dirname(run); items = []
for name in os.listdir(runs):
    path = os.path.join(runs, name, "state.json")
    if not os.path.isfile(path):
        continue
    try:
        created = json.load(open(path, encoding="utf-8-sig")).get("created", 0)
    except (OSError, ValueError):
        created = 0
    items.append((created, name))
names = [n for _, n in sorted(items)]
print(names.index(os.path.basename(run)) + 1 if os.path.basename(run) in names else 0)
EOF
}

ai_fault() {  # ai_fault <stage_dir> <call base> <resume sid> -> 0 a limit was injected (<base>.json written), 1 none
  [ -n "${REELS_FAULT:-}" ] || return 1
  local stage_dir="$1" base="$2" sid="$3" stage run_dir spec kind target at marker mins when text pid rest
  stage="$(basename "$stage_dir")"; run_dir="$(dirname "$stage_dir")"
  for spec in ${REELS_FAULT//,/ }; do
    kind="${spec%%:*}"; target="${spec#*:}"; at=""
    case "$target" in *@*) at="${target#*@}"; target="${target%%@*}" ;; esac
    [ "$target" = "$stage" ] || continue
    case "$kind" in limit|kill) ;; *) continue ;; esac
    if [ -n "$at" ] && [ "$(ai_fault_ordinal "$run_dir" 2>/dev/null)" != "$at" ]; then continue; fi
    marker="$REELS_LOGS/.faults/$kind-$stage${at:+@$at}"
    [ -e "$marker" ] && continue
    mkdir -p "$REELS_LOGS/.faults"
    printf '%s %s %s\n' "$EPOCHSECONDS" "$(basename "$run_dir")" "$(basename "$base")" > "$marker"
    if [ "$kind" = limit ]; then
      mins="${REELS_FAULT_MINUTES:-3}"
      case "$mins" in ''|*[!0-9]*) mins=3 ;; esac
      [ "$mins" -lt 2 ] && mins=2   # the message has minutes only: at least one whole minute ahead after the rounding
      when=$(( EPOCHSECONDS + mins * 60 ))
      text="You've hit your session limit · resets $("$REELS_PY" -c 'import sys, time
t = time.localtime(int(sys.argv[1])); h = t.tm_hour % 12 or 12
print("%d:%02d%s" % (h, t.tm_min, "am" if t.tm_hour < 12 else "pm"))' "$when") ($(cfg runner.timezone Europe/Rome))"
      "$REELS_PY" -c 'import json, sys
print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "duration_ms": 0, "num_turns": 0,
                  "result": sys.argv[1], "session_id": sys.argv[2], "fault": "REELS_FAULT limit"}, ensure_ascii=False))' \
        "$text" "$sid" > "$base.json"
      : > "$base.err"
      printf 'fault: injected session limit (REELS_FAULT %s), reset in about %s min\n' "$spec" "$mins" >> "$base.meta"
      say WARN "fault injected (REELS_FAULT $spec): this call returns a session limit instead of reaching the model"
      return 0
    fi
    # kill: the runner first (so it cannot react to the stage's end), then this stage
    say WARN "fault injected (REELS_FAULT $spec): killing the runner and this stage now"
    printf 'fault: kill (REELS_FAULT %s)\n' "$spec" >> "$base.meta"
    pid=""; { read -r pid rest < "$REELS_LOCKS/runner/pid"; } 2>/dev/null
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null
    kill -9 $$ 2>/dev/null
    exit 137
  done
  return 1
}

ai() {
  local role="$1" stage_dir="$2" prompt_file="$3"
  shift 3
  local schema="" resume="" session_key="" tools="__default__" allowed="" disallow="" timeout_s="" activity=""
  local cwd="" max_turns="" protect=1 name=""
  local -a add_dirs=() allow_extra=() deny_extra=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --schema) schema="$2"; shift 2 ;;
      --resume) resume="$2"; shift 2 ;;
      --session) session_key="$2"; shift 2 ;;
      --tools) tools="$2"; shift 2 ;;
      --allowed) allowed="$2"; shift 2 ;;
      --allow) allow_extra+=("$2"); shift 2 ;;
      --disallow) disallow="$2"; shift 2 ;;
      --deny) deny_extra+=("$2"); shift 2 ;;
      --add-dir) add_dirs+=("$2"); shift 2 ;;
      --timeout) timeout_s="$2"; shift 2 ;;
      --activity) activity="$2"; shift 2 ;;
      --cwd) cwd="$2"; shift 2 ;;
      --max-turns) max_turns="$2"; shift 2 ;;
      --name) name="$2"; shift 2 ;;
      --no-protect) protect=0; shift ;;
      *) echo "ai: unknown option '$1'" >&2; return 1 ;;
    esac
  done
  AI_CALL=""; AI_RESULT=""; AI_SESSION=""; AI_OUT=""; AI_CLASS=""; AI_ERROR=""; AI_DETAIL=""; AI_FATAL=0
  if [ ! -f "$prompt_file" ]; then AI_ERROR="ai: prompt file $prompt_file is missing"; AI_CLASS=error; echo "$AI_ERROR" >&2; return 1; fi
  local model effort run_dir calls
  model="$(cfg "models.$role.model")" || { AI_ERROR="ai: no model for role '$role' in config.json"; AI_CLASS=error; echo "$AI_ERROR" >&2; return 1; }
  effort="$(cfg "models.$role.effort" medium)"
  run_dir="$(dirname "$stage_dir")"
  calls="$stage_dir/calls"
  mkdir -p "$calls"
  [ -n "$timeout_s" ] || timeout_s="$(cfg timeouts.model_call_seconds 3600)"
  [ -n "$activity" ] || activity="$(get_activity)"
  [ -n "$cwd" ] || cwd="$REELS_REPO"
  local session_from_state=0
  if [ -n "$session_key" ] && [ -z "$resume" ]; then
    resume="$(state_get "$run_dir" "sessions.$session_key" "" 2>/dev/null)"
    [ -n "$resume" ] && session_from_state=1
  fi
  local -a tool_args=() allow_args=() deny_args=() dir_args=() schema_args=()
  if [ "$tools" != "__default__" ]; then
    tool_args=(--tools "$(printf '%s' "$tools" | tr ' ' ',' | tr -s ',')")
    if [ -z "$allowed" ] && [ ${#allow_extra[@]} -eq 0 ]; then allowed="$(printf '%s' "$tools" | tr ',' ' ')"; fi
  fi
  local -a allow_list=()
  if [ -n "$allowed" ]; then read -r -a allow_list <<<"$allowed"; fi
  if [ ${#allow_extra[@]} -gt 0 ]; then allow_list+=("${allow_extra[@]}"); allowed="${allow_list[*]}"; fi
  [ ${#allow_list[@]} -gt 0 ] && allow_args=(--allowedTools "${allow_list[@]}")
  local -a deny_list; mapfile -t deny_list < <(ai_protected_rules)
  if [ -n "$disallow" ]; then local -a extra; read -r -a extra <<<"$disallow"; deny_list+=("${extra[@]}"); fi
  [ ${#deny_extra[@]} -gt 0 ] && deny_list+=("${deny_extra[@]}")
  deny_args=(--disallowedTools "${deny_list[@]}")
  local d; for d in "${add_dirs[@]}"; do dir_args+=(--add-dir "$d"); done
  if [ -n "$schema" ]; then
    # the CLI's validator rejects a "$schema" key naming the 2020-12 meta-schema, so the command line gets the
    # schema without "$schema" and "$id" (the file keeps them for the local jsonschema validation)
    schema_args=(--json-schema "$("$REELS_PY" -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
d.pop("$schema", None); d.pop("$id", None)
sys.stdout.write(json.dumps(d, ensure_ascii=False, separators=(",", ":")))' "$schema")")
  fi
  local tries=0 schema_retry=0 n base rc cls out message detail retry_after sid structured fatal resume_failed errs delay
  local faulted=0 scale_before
  local backoff_n; backoff_n="$(error_backoff_count)"
  local prompt="$prompt_file"
  while :; do
    n="$(ai_next_number "$calls")"
    base="$calls/$n${name:+-$name}"
    local -a cmd=("${REELS_CLAUDE:-claude}" -p --model "$model" --effort "$effort" --output-format json
                  --permission-mode auto --permission-prompts none)
    [ -n "$resume" ] && cmd+=(--resume "$resume")
    [ -n "$max_turns" ] && cmd+=(--max-turns "$max_turns")
    cmd+=("${schema_args[@]}" "${tool_args[@]}" "${allow_args[@]}" "${deny_args[@]}" "${dir_args[@]}")
    {
      printf 'role: %s\nmodel: %s\neffort: %s\nprompt: %s\nresume: %s\nschema: %s\ntools: %s\nallowed: %s\ncwd: %s\nstarted: %(%Y-%m-%d %H:%M:%S)T\n' \
        "$role" "$model" "$effort" "$prompt" "$resume" "$schema" "$tools" "$allowed" "$cwd" -1
      printf 'command:'; printf ' %q' "${cmd[@]}"; printf '\n'
    } > "$base.meta"
    if [ "$protect" = 1 ]; then
      "$REELS_PY" "$REELS_PIPELINE/lib/protect.py" snapshot --root "$REELS_ROOT" --repo "$REELS_REPO" --dir "$calls/.protect" >/dev/null 2>&1 || protect=0
    fi
    faulted=0
    if ai_fault "$stage_dir" "$base" "$resume"; then
      rc=1; faulted=1   # REELS_FAULT: a simulated session limit in place of the call (M13)
    else
      ( cd "$cwd" && timeout -k 15 "$timeout_s" "${cmd[@]}" < "$prompt" > "$base.json" 2> "$base.err" ); rc=$?
    fi
    printf 'ended: %(%Y-%m-%d %H:%M:%S)T\nrc: %s\n' -1 "$rc" >> "$base.meta"
    AI_CALL="$base.json"
    if [ "$protect" = 1 ]; then
      local changed
      changed="$("$REELS_PY" "$REELS_PIPELINE/lib/protect.py" check --root "$REELS_ROOT" --repo "$REELS_REPO" --dir "$calls/.protect" --restore 2>/dev/null)"
      if [ $? -ne 0 ]; then
        rm -rf "$calls/.protect"
        local what; what="$(json_field "$changed" changed '[]')"
        [ "$what" = "[]" ] && what="$(json_field "$changed" added '[]')"
        [ "$what" = "[]" ] && what="$(json_field "$changed" removed '[]')"
        [ "$what" = "[]" ] && what="exports/ listing"
        AI_CLASS=error; AI_DETAIL="protected files"
        AI_ERROR="the model call changed protected files ($what); restored from the snapshot"
        printf 'protected files changed: %s\n' "$changed" >> "$base.meta"
        ai_write_error "$stage_dir" error "$AI_ERROR" "$AI_DETAIL" "$base.json" "$rc" "$role" "$model" 0 0
        return 1
      fi
      rm -rf "$calls/.protect"
    fi
    out="$(error_classify "$rc" "$base.json" "$base.err")"
    eval "$(json_eval "$out" cls=class message=message detail=detail retry_after=retry_after sid=session_id structured=structured fatal=fatal resume_failed=resume_failed)"
    printf 'class: %s\ndetail: %s\nmessage: %s\n' "$cls" "$detail" "$message" >> "$base.meta"
    # one model at its own limit while the others still answer ("You've reached your Fable limit. Switch to another
    # model ..."): the message has no reset time, so it is neither a usage limit to wait out nor a code error to fix.
    # The call carries on with config models.limit_fallback (default opus) in the same session (DECISIONS.md 275).
    local fb_model; fb_model="$(cfg models.limit_fallback.model opus)"
    # (the CLI reports it as api error 429, model_requires_usage_credits, which the classifier calls a transient rate limit)
    if { [ "$cls" = error ] || [ "$cls" = transient ]; } && [ "$model" != "$fb_model" ] \
       && printf '%s' "$message" | grep -qiE "reached your [a-z0-9 ._-]+ limit|switch to another model"; then
      say WARN "$role: $model is at its own usage limit, this call carries on with $fb_model"
      printf 'model limit: %s -> %s\n' "$model" "$fb_model" >> "$base.meta"
      model="$fb_model"; effort="$(cfg models.limit_fallback.effort "$effort")"
      continue
    fi
    AI_CLASS="$cls"; AI_DETAIL="$detail"
    case "$cls" in
      ok)
        AI_SESSION="$sid"
        if [ -n "$schema" ]; then
          AI_OUT="$base.out.json"
          AI_RESULT="$(ai_extract "$base.json" "$AI_OUT")"
          errs=""
          if [ ! -f "$AI_OUT" ]; then
            errs="no JSON object in the answer"
          else
            errs="$("$REELS_PY" "$REELS_PIPELINE/bin/validate-json" "$schema" "$AI_OUT" 2>&1 | head -n 8)" || true
            [ "$("$REELS_PY" "$REELS_PIPELINE/bin/validate-json" "$schema" "$AI_OUT" >/dev/null 2>&1; echo $?)" = 0 ] && errs=""
          fi
          reels_undash errs   # the validator quotes the model's values
          if [ -n "$errs" ]; then
            if [ "$schema_retry" = 0 ] && [ -n "$sid" ]; then
              schema_retry=1
              {
                echo "Your previous answer did not match the required JSON schema:"
                printf '%s\n' "$errs"
                echo
                echo "Answer again with only the JSON object that matches the schema, nothing else."
              } > "$base.retry.md"
              say WARN "$role output did not match the schema ($(printf '%s' "$errs" | head -n 1)), asking once more in the same session"
              prompt="$base.retry.md"; resume="$sid"
              continue
            fi
            AI_CLASS=error; AI_DETAIL="invalid output"
            AI_ERROR="output did not match the schema after one retry: $(printf '%s' "$errs" | head -n 1)"
            ai_write_error "$stage_dir" error "$AI_ERROR" "$AI_DETAIL" "$base.json" "$rc" "$role" "$model" 0 0
            return 1
          fi
        else
          AI_RESULT="$(ai_extract "$base.json" "")"
        fi
        if [ -n "$session_key" ] && [ -n "$sid" ]; then
          state_set "$run_dir" "sessions.$session_key=\"$sid\"" >/dev/null 2>&1 || true
        fi
        return 0
        ;;
      limit)
        local l_kind l_reset l_msg
        eval "$(json_eval "$out" l_kind=limit.kind l_reset=limit.reset l_msg=limit.message)"
        if [ -n "$l_reset" ]; then
          if [ "$faulted" = 1 ] && [ "${REELS_FAULT_WAIT:-}" = fast ]; then
            scale_before="$(reels_sleep_scale)"; REELS_SLEEP_SCALE_VALUE=0   # fast-forward the injected limit's wait only
            limit_wait "$l_reset" "$l_kind" "$activity" "$l_msg"
            REELS_SLEEP_SCALE_VALUE="$scale_before"
          else
            limit_wait "$l_reset" "$l_kind" "$activity" "$l_msg"
          fi
        else
          limit_wait_unparsed "$l_kind" "$activity" "$l_msg" -- ai_probe "$stage_dir" || {
            AI_CLASS=error; AI_ERROR="usage limit with no reset time, and the probe never answered"
            ai_write_error "$stage_dir" error "$AI_ERROR" "limit" "$base.json" "$rc" "$role" "$model" 0 0
            return 1
          }
        fi
        continue
        ;;
      transient)
        tries=$((tries + 1))
        if [ "$tries" -le "$backoff_n" ]; then
          delay="$(error_backoff "$tries")"
          [ -n "$retry_after" ] && [ "$retry_after" -gt "$delay" ] 2>/dev/null && delay="$retry_after"
          say RETRY "temporary error ($detail), retrying in $(fmt_wait "$delay") (try $tries/$backoff_n)"
          set_activity "retrying after temporary error ($detail), next try in $(fmt_wait "$delay") (try $tries/$backoff_n)"
          reels_sleep "$delay" "transient backoff"
          set_activity "$activity"
          continue
        fi
        AI_CLASS=error
        AI_ERROR="temporary error persisted after $backoff_n retries ($detail): $message"
        ai_write_error "$stage_dir" error "$AI_ERROR" "$detail" "$base.json" "$rc" "$role" "$model" 0 0
        return 1
        ;;
      *)
        AI_ERROR="$message"
        [ "$fatal" = true ] && AI_FATAL=1
        ai_write_error "$stage_dir" error "$AI_ERROR" "$detail" "$base.json" "$rc" "$role" "$model" \
          "$([ "$fatal" = true ] && echo 1 || echo 0)" "$([ "$resume_failed" = true ] && echo 1 || echo 0)"
        if [ "$resume_failed" = true ]; then
          [ "$session_from_state" = 1 ] && state_set "$run_dir" "sessions.$session_key=null" >/dev/null 2>&1
          return 3
        fi
        return 1
        ;;
    esac
  done
}
