# pipeline/lib/runner.sh: the video runner's loop (BUILD_SPEC.md sections 3, 4, 6, 7 and 8). Sourced by run.sh
# after common.sh, log.sh, config.sh, ideas.sh, preflight.sh, history.sh, state.sh, status.sh, export.sh, ai.sh
# (with limits.sh and errors.sh) and review.sh.
#
#   runner_main            the loop: take the first idea (or resume the unfinished run), run the stages in order,
#                          export, drop or block, next idea; when the queue is empty: exit with --once (ONCE=1),
#                          otherwise poll every runner.poll_seconds and print the IDLE line every
#                          runner.status_every_seconds. Returns 0 (queue empty with --once), 3 (systemic stop),
#                          1 (another runner holds .locks/runner), 130 (stopped by the user).
#
# Stage scripts run as child processes: `bash pipeline/stages/<stage>/run.sh <run_dir>` (or dummy.sh when
# REELS_DUMMY is "all" or lists the stage). Their stdout and stderr go to <run_dir>/<stage>/stage.log; the runner's
# terminal is on their fd 3, so their `say` lines reach the screen. Exit codes: 0 done (outputs validated, .done
# written), 10 drop, 20 block, anything else a code error. The runner polls the child every REELS_TICK_SECONDS and
# prints the heartbeat and NEW lines meanwhile.
#
# Environment (tests and tuning): REELS_DUMMY, REELS_DUMMY_SECONDS (and the planted REELS_DUMMY_* of dummy.sh),
# REELS_POLL_SECONDS, REELS_STATUS_EVERY, REELS_TICK_SECONDS (literal seconds, never scaled), REELS_SLEEP_SCALE
# (multiplies the configured waits; 0 logs the wait and does not sleep), REELS_CRASH_AT=assembled|moved (the
# runner kills itself at that point of the export, for the crash tests).
#
# The runner stops on its own only through runner_systemic_stop (STOP line plus logs/STOPPED.md). A state.json that
# cannot be read or written mid-run (OneDrive or an antivirus holding the file, a damaged file) goes through
# runner_state: one retry after STATE_RETRY_SECONDS, then the systemic stop; the idea stays in ideas.txt.
#
# A failed stage script (BUILD_SPEC.md section 4, M3): runner_stage_failed classifies the exit code and the tail of
# stage.log in the spec's order with the classifier ai() uses (pipeline/lib/errors.py): a usage limit is waited out
# (LIMIT, RESUME) and the stage runs again; a transient error is retried after 60 s, 4 min, 16 min (RETRY lines,
# the counter errors.<stage>.transient_tries in state.json survives a restart) and the fourth failure is a code
# error; a stage whose own model call failed (ai() wrote <stage>/error.json in this attempt) was classified and
# retried there already and is a code error at once.
#
# Code errors (BUILD_SPEC.md 4.2, M3): runner_code_error prints ERROR and runs the review and fix loop of
# pipeline/lib/review.sh through the child script pipeline/bin/review-cycle (so the heartbeat keeps printing):
# FIXED restarts the stage, a verdict that needs the user blocks the idea, and the same error blocking
# caps.systemic_block_streak ideas in a row is the systemic stop (logs/.block-streak keeps the streak across
# restarts; an export or a drop resets it). The loop survives a restart: state.json says which stage is under
# review and which cycle E<n> is pending, errors/E<n>.pid names the cycle's child, and runner_resume_review adopts
# a child that still runs, takes the verdict of one that finished, or runs the interrupted cycle again (same E<n>,
# no Opus cycle lost, the stage is not run again).

RUNNER_LOCKED=0
CHILD_PID=""
IN_RUN=0
RUN_DIR=""
STOP_REQUESTED=0
NEXT_PHASE=""; NEXT_STAGE=""; NEXT_LABEL=""; NEXT_ACTIVITY=""; NEXT_ATTEMPTS=""; NEXT_NUMBER=""
STATE_OUT=""; STATE_RC=0        # the last runner_state result: its JSON and its exit code
STATE_RETRY_SECONDS=3           # the wait before the one retry of a failed state.py call (scaled by runner_sleep)

# ------------------------------------------------------------------ setup

runner_load_stages() {
  STAGE_KEYS=()
  declare -g -A STAGE_LABEL=() STAGE_ACTIVITY=() STAGE_OUTPUT=()
  local key label activity output initial
  while IFS=$'\t' read -r key label activity output initial; do
    [ -n "$key" ] || continue
    STAGE_KEYS+=("$key")
    STAGE_LABEL["$key"]="$label"
    STAGE_ACTIVITY["$key"]="$activity"
    STAGE_OUTPUT["$key"]="$output"
  done < <(state_stages)
  [ ${#STAGE_KEYS[@]} -gt 0 ]
}

runner_lock_take() {
  local dir="$REELS_LOCKS/runner" pid="" rest
  mkdir -p "$REELS_LOCKS"
  if [ -d "$dir" ]; then
    { read -r pid rest < "$dir/pid"; } 2>/dev/null || pid=""
    if [ -n "$pid" ] && [ "$pid" != "$$" ] && ps -p "$pid" >/dev/null 2>&1; then
      echo "run.sh: another runner is already running (pid $pid). Stop it first (Ctrl+C in its window)." >&2
      return 1
    fi
    rm -rf "$dir" 2>/dev/null
  fi
  if ! mkdir "$dir" 2>/dev/null; then
    echo "run.sh: cannot take the runner lock $dir" >&2
    return 1
  fi
  printf '%s %s\n' "$$" "$EPOCHSECONDS" > "$dir/pid"
  RUNNER_LOCKED=1
}

runner_lock_release() {
  if [ "$RUNNER_LOCKED" = 1 ]; then rm -rf "$REELS_LOCKS/runner" 2>/dev/null; fi
  RUNNER_LOCKED=0
}

runner_on_signal() {
  local sig="$1"
  trap - INT TERM
  if [ "$IN_RUN" = 1 ]; then
    say INFO "stopped by the user ($sig) while $(get_activity); bash run.sh resumes this run"
  else
    say INFO "stopped by the user ($sig)"
  fi
  if [ -n "$CHILD_PID" ]; then
    kill -TERM "$CHILD_PID" 2>/dev/null
    sleep 0.3
    kill -KILL "$CHILD_PID" 2>/dev/null
  fi
  runner_lock_release
  exit 130
}

runner_on_exit() {
  runner_lock_release
}

runner_sleep() {  # runner_sleep <seconds> [what]: scaled by REELS_SLEEP_SCALE; 0 means fast-forward (log only)
  reels_sleep "$@"
}

reels_wait_tick() {  # limits.sh calls this between the 60 s chunks of the runner's own waits (a limit, a backoff)
  runner_tick
}

runner_write_stopped() {  # runner_write_stopped "<title>" "<diagnosis>" "<fix>" ["<fix 2>" ...]: numbered fix lines
  local title="$1" diagnosis="$2" n=1 fix
  shift 2
  mkdir -p "$REELS_LOGS"
  {
    echo "# Runner stopped: $title"
    echo
    printf 'Written %(%Y-%m-%d %H:%M)T by run.sh. The runner stops on its own only for a systemic failure.\n' -1
    echo "This file is removed at the next successful start."
    echo
    echo "## Diagnosis"
    echo "- $diagnosis"
    echo
    echo "## Fix"
    for fix in "$@"; do echo "$n. $fix"; n=$((n + 1)); done
    echo
    echo "Then start the runner again: bash run.sh"
  } > "$REELS_LOGS/STOPPED.md"
}

runner_systemic_stop() {  # runner_systemic_stop "<reason>" "<fix>" ["<fix 2>" ...]
  local reason="$1"
  shift
  runner_write_stopped "$reason" "$reason" "$@"
  say STOP "systemic failure: $reason. See logs/STOPPED.md"
  STOP_REQUESTED=1
}

runner_state() {  # runner_state <read|update> "<ok exit codes>" <state command...> -> 0 (STATE_OUT holds the JSON,
                  # STATE_RC the exit code) or 2 after the systemic stop.
  # A state.py call that fails twice, with a short wait in between (OneDrive and antivirus scans hold files briefly;
  # state.py's own save already retries its rename for a second), means the runner can no longer trust
  # runs/<id>/state.json: going on could repeat a stage or duplicate an export, and blocking the idea would hide an
  # environment problem that hits every idea. So it is a systemic stop (BUILD_SPEC.md section 4): ERROR and STOP
  # lines, logs/STOPPED.md with the file and the fix, exit 3; the idea stays in ideas.txt.
  local what="$1" ok="$2" out="$REELS_LOGS/.state.out" err="$REELS_LOGS/.state.err" try detail
  shift 2
  for try in 1 2; do
    "$@" >"$out" 2>"$err"; STATE_RC=$?
    case " $ok " in
      *" $STATE_RC "*) STATE_OUT="$(cat "$out" 2>/dev/null)"; return 0 ;;
    esac
    # the last stderr line, without the tool name and with the run folder in its short form
    detail="$(grep -v '^[[:space:]]*$' "$err" 2>/dev/null | tail -n 1 | tr -d '\r')"
    detail="${detail#state.py: }"; detail="${detail//"$RUN_DIR"/runs/$RUN_ID}"; detail="${detail:0:160}"
    [ -n "$detail" ] || detail="no output from state.py (exit $STATE_RC)"
    [ "$try" = 1 ] || break
    say WARN "cannot $what runs/$RUN_ID/state.json ($detail), trying again in ${STATE_RETRY_SECONDS}s"
    runner_sleep "$STATE_RETRY_SECONDS" "state.json retry"
  done
  say ERROR "cannot $what runs/$RUN_ID/state.json: $detail"
  runner_systemic_stop "cannot $what runs/$RUN_ID/state.json ($detail)" \
    "If the file was only busy (OneDrive syncing it, an antivirus scan, an editor holding it): close whatever holds it, or pause OneDrive, and start the runner again. The run resumes where it stopped." \
    "If state.json itself is damaged (it is not valid JSON any more): the next start skips this run folder and starts the idea over in a new one, because the idea is still in ideas.txt. Move runs/$RUN_ID out of runs/ (for example into runs/_broken/) when you no longer need it."
  return 2
}

# ------------------------------------------------------------------ stages

runner_stage_script() {  # prints the script to run for a stage: dummy.sh when REELS_DUMMY asks for it, else run.sh
  local stage="$1" dir="$REELS_PIPELINE/stages/$1" num short
  num="${stage%%-*}"; short="${num#0}"
  case ",${REELS_DUMMY:-}," in
    *",all,"*|*",$stage,"*|*",$num,"*|*",$short,"*) printf '%s/dummy.sh' "$dir" ;;
    *) printf '%s/run.sh' "$dir" ;;
  esac
}

runner_wait_child() {  # waits for CHILD_PID, ticking (heartbeat, NEW lines) meanwhile; returns its exit code
  local pid="$1" rc
  while kill -0 "$pid" 2>/dev/null; do
    runner_tick
    sleep "$TICK_SECONDS"
  done
  wait "$pid" 2>/dev/null; rc=$?
  return $rc
}

runner_last_log_line() {  # the last non-empty line of a stage log, trimmed, for the ERROR line
  local file="$1" line=""
  [ -f "$file" ] && line="$(grep -v '^[[:space:]]*$' "$file" | tail -n 1 | tr -d '\r')"
  line="${line:0:160}"
  printf '%s' "${line:-no output}"
}

runner_result_reason() {  # the reason a stage gave in result.json (exit 10 or 20)
  local file="$RUN_DIR/$1/result.json" reason=""
  if [ -f "$file" ]; then
    reason="$(json_field "$(cat "$file")" reason "" 2>/dev/null)"
  fi
  printf '%s' "${reason:-no reason given ($1/result.json missing)}"
}

runner_next_text() {  # the "-> next" part of the STEP line
  case "$1" in
    stage) printf '%s' "$2" ;;
    export) printf 'exporting' ;;
    finalize) printf 'finishing' ;;
    *) printf 'done' ;;
  esac
}

runner_run_stage() {  # runner_run_stage <stage> <label> <activity> <attempts> [status] -> 0 continue, 1 run ended, 2 stop
  local stage="$1" label="${2:-$1}" activity="${3:-working}" attempts="${4:-0}" status="${5:-}" script rc res
  script="$(runner_stage_script "$stage")"
  if [ ! -f "$script" ]; then
    runner_systemic_stop "stage $stage is not built yet ($(basename "$script") missing in pipeline/stages/$stage)" \
      "this stage arrives in a later milestone; to exercise the runner today run it with REELS_DUMMY=all bash run.sh --once"
    return 2
  fi
  mkdir -p "$RUN_DIR/$stage"
  if [ "$status" = failed ] && [ "$(state_get "$RUN_DIR" "errors.$stage.review.active" false 2>/dev/null)" = true ]; then
    # the previous runner stopped while this failure was in the review loop: resume the loop, not the stage
    runner_resume_review "$stage" "$label" "$activity"
    return $?
  fi
  runner_adopt_orphan "$stage" "$label" "$activity"; rc=$?
  [ "$rc" = 3 ] || return "$rc"   # 3: no orphan (or it left nothing valid), run the stage; else the stage's result
  if [ "$attempts" -gt 0 ]; then
    if [ "$status" = failed ]; then
      case "$(state_get "$RUN_DIR" "errors.$stage.restart" "" 2>/dev/null)" in
        fixed) say INFO "$label $activity: attempt $((attempts + 1)) after the fix" ;;
        transient) say INFO "$label $activity: attempt $((attempts + 1)) after the temporary error" ;;
        limit) say INFO "$label $activity: attempt $((attempts + 1)) after the usage limit" ;;
        *) say INFO "$label $activity: attempt $((attempts + 1)) (the previous one failed)" ;;
      esac
    else
      say INFO "$label $activity: attempt $((attempts + 1)) (the previous one was interrupted)"
    fi
  fi
  rm -f "$RUN_DIR/$stage/error.json"   # a model call error of this attempt (ai.sh) is told apart from an older one
  runner_state update 0 state_stage_start "$RUN_DIR" "$stage" || return 2
  STAGE_STARTED="$EPOCHSECONDS"
  set_activity "$activity"
  REELS_SAY_FD=3 bash "$script" "$RUN_DIR" 3>&1 >>"$RUN_DIR/$stage/stage.log" 2>&1 &
  CHILD_PID=$!
  printf '%s %s\n' "$CHILD_PID" "$EPOCHSECONDS" > "$RUN_DIR/$stage/.pid"
  runner_wait_child "$CHILD_PID"; rc=$?
  CHILD_PID=""
  rm -f "$RUN_DIR/$stage/.pid"
  runner_handle_stage_exit "$stage" "$label" "$activity" "$rc"
}

runner_adopt_orphan() {  # a stage process left by a killed runner: wait for it, keep its outputs.
                         # Returns 3 when the stage must run (no orphan, or it left no valid output); otherwise the
                         # stage's result from runner_handle_stage_exit (0 continue, 1 run ended, 2 stop).
  local stage="$1" label="$2" activity="$3" pid="" rest
  [ -f "$RUN_DIR/$stage/.pid" ] || return 3
  { read -r pid rest < "$RUN_DIR/$stage/.pid"; } 2>/dev/null || pid=""
  if [ -z "$pid" ] || ! ps -p "$pid" >/dev/null 2>&1; then
    rm -f "$RUN_DIR/$stage/.pid"
    return 3
  fi
  say WARN "$label $activity still runs from the previous runner (pid $pid), waiting for it instead of starting it twice"
  STAGE_STARTED="$EPOCHSECONDS"
  set_activity "$activity"
  while ps -p "$pid" >/dev/null 2>&1; do
    runner_tick
    sleep "$TICK_SECONDS"
  done
  rm -f "$RUN_DIR/$stage/.pid"
  # its exit code is unknown: judge it by its outputs; invalid or missing means run it again
  if state_stage_done "$RUN_DIR" "$stage" >/dev/null 2>&1; then
    runner_handle_stage_exit "$stage" "$label" "$activity" 0
    return $?
  fi
  say INFO "$label $activity: the orphaned process left no valid output, running the stage again"
  return 3
}

runner_handle_stage_exit() {  # stage label activity rc -> 0 continue, 1 run ended, 2 stop (state.json unusable)
  local stage="$1" label="$2" activity="$3" rc="$4" res src seconds next_phase next_stage next_activity reason
  case "$rc" in
    0)
      runner_state update "0 5" state_stage_done "$RUN_DIR" "$stage" 0 || return 2   # 5: the output did not validate
      res="$STATE_OUT"; src="$STATE_RC"
      if [ "$src" = 0 ]; then
        local issues_fixed="" issues_open="" attempts=""
        # NEXT_* tell the loop what follows, so it does not have to ask state.py again
        eval "$(json_eval "$res" seconds=seconds attempts=attempts NEXT_PHASE=next_phase NEXT_STAGE=next_stage NEXT_LABEL=next_label \
          NEXT_ACTIVITY=next_activity NEXT_ATTEMPTS=next_attempts NEXT_NUMBER=export_number \
          issues_fixed=issues_fixed issues_open=issues_open)"
        ISSUES_FIXED="${issues_fixed:-$ISSUES_FIXED}"
        ISSUES_OPEN="${issues_open:-$ISSUES_OPEN}"
        if [ "${attempts:-1}" -gt 1 ] 2>/dev/null; then  # a retried stage passed: its transient counter starts over
          state_set "$RUN_DIR" "errors.$stage.transient_tries=0" "errors.$stage.restart=null" >/dev/null 2>&1
        fi
        say STEP "$activity done ($(fmt_dur "${seconds:-0}")) -> $(runner_next_text "${NEXT_PHASE:-done}" "$NEXT_ACTIVITY")"
        return 0
      fi
      reason="$(json_field "$res" errors.0 "output did not validate")"
      runner_code_error "$stage" "$label" "$activity" "$rc" "invalid output: $reason"
      return $?
      ;;
    10)
      reason="$(runner_result_reason "$stage")"
      state_stage_fail "$RUN_DIR" "$stage" 10 "drop: $reason" >/dev/null
      runner_drop "$stage" "$reason"
      return 1
      ;;
    20)
      reason="$(runner_result_reason "$stage")"
      state_stage_fail "$RUN_DIR" "$stage" 20 "block: $reason" >/dev/null
      runner_block "$stage" "$label" "$reason"
      return 1
      ;;
    *)
      runner_stage_failed "$stage" "$label" "$activity" "$rc"
      return $?
      ;;
  esac
}

runner_stage_failed() {  # stage label activity rc -> 0 run the stage again (after a limit or a transient wait),
                         # else the review loop's result (0 restart after a fix, 1 run ended, 2 stop)
  # BUILD_SPEC.md section 4 for a failed stage script: classify in order (usage limit, transient, code error) on
  # the exit code and the last errors.classify_tail_lines of stage.log, with the patterns ai() uses
  # (pipeline/lib/errors.py). A stage whose own model call failed (<stage>/error.json, written by ai() in this
  # attempt) was classified and retried there already: it is a code error now. The transient counter lives in
  # state.json (errors.<stage>.transient_tries) so a restart keeps it; a success or a code error resets it.
  local stage="$1" label="$2" activity="$3" rc="$4" log="$RUN_DIR/$stage/stage.log" tail_file="$RUN_DIR/$stage/.log-tail"
  local msg out="" cls="" detail="" retry_after="" l_kind="" l_reset="" l_msg="" tries backoff_n delay tail_n
  msg="exit $rc: $(runner_last_log_line "$log")"
  if [ -f "$RUN_DIR/$stage/error.json" ]; then
    runner_code_error "$stage" "$label" "$activity" "$rc" "$msg"
    return $?
  fi
  tail_n="$(cfg errors.classify_tail_lines 40)"
  if [ -f "$log" ]; then tail -n "$tail_n" "$log" | tr -d '\r' > "$tail_file"; else : > "$tail_file"; fi
  out="$(error_classify "$rc" "" "$tail_file" 2>/dev/null)" || out=""
  rm -f "$tail_file"
  eval "$(json_eval "$out" cls=class detail=detail retry_after=retry_after l_kind=limit.kind l_reset=limit.reset l_msg=limit.message)"
  case "$cls" in
    limit)
      state_stage_fail "$RUN_DIR" "$stage" "$rc" "usage limit (${l_kind:-usage}): ${l_msg:-$msg}" >/dev/null
      state_set "$RUN_DIR" "errors.$stage.restart=\"limit\"" >/dev/null 2>&1
      if [ -n "$l_reset" ]; then
        limit_wait "$l_reset" "${l_kind:-usage}" "$activity" "$l_msg"
      elif ! limit_wait_unparsed "${l_kind:-usage}" "$activity" "$l_msg" -- ai_probe "$RUN_DIR/$stage"; then
        runner_code_error "$stage" "$label" "$activity" "$rc" "usage limit with no reset time, and the probe never answered: $msg"
        return $?
      fi
      return 0
      ;;
    transient)
      tries="$(state_get "$RUN_DIR" "errors.$stage.transient_tries" 0 2>/dev/null)"
      case "$tries" in ''|*[!0-9]*) tries=0 ;; esac
      tries=$((tries + 1))
      backoff_n="$(error_backoff_count)"
      if [ "$tries" -le "$backoff_n" ]; then
        delay="$(error_backoff "$tries")"
        [ -n "$retry_after" ] && [ "$retry_after" -gt "$delay" ] 2>/dev/null && delay="$retry_after"
        state_stage_fail "$RUN_DIR" "$stage" "$rc" "temporary error ($detail), try $tries/$backoff_n: $msg" >/dev/null
        state_set "$RUN_DIR" "errors.$stage.transient_tries=$tries" "errors.$stage.restart=\"transient\"" >/dev/null 2>&1
        say RETRY "temporary error ($detail), retrying in $(fmt_wait "$delay") (try $tries/$backoff_n)"
        set_activity "retrying after temporary error ($detail), next try in $(fmt_wait "$delay") (try $tries/$backoff_n)"
        runner_sleep "$delay" "transient backoff"
        set_activity "$activity"
        return 0
      fi
      runner_code_error "$stage" "$label" "$activity" "$rc" "temporary error persisted after $backoff_n retries ($detail): $msg"
      return $?
      ;;
    *)
      runner_code_error "$stage" "$label" "$activity" "$rc" "$msg"
      return $?
      ;;
  esac
}

runner_code_error() {  # stage label activity rc message -> 0 restart the stage, 1 run ended (blocked), 2 stop
  # The review and fix loop of BUILD_SPEC.md 4.2 (pipeline/lib/review.sh): the ERROR line, the counters, then
  # runner_review_loop. review_begin records the error in state.json so a restarted runner resumes the loop.
  local stage="$1" label="$2" activity="$3" rc="$4" msg="$5" sig cmd
  say ERROR "$label $activity: $msg"
  state_stage_fail "$RUN_DIR" "$stage" "$rc" "$msg" >/dev/null
  ISSUES_OPEN=$((ISSUES_OPEN + 1))
  state_py issue "$RUN_DIR" open +1 >/dev/null 2>&1
  sig="$(error_signature "$msg")"
  review_note_failure "$RUN_DIR" "$stage" "$sig"
  if [ "$stage" = 14-export ] && [ "$activity" = exporting ]; then
    cmd="python pipeline/lib/export.py run --run-dir $RUN_DIR (pipeline/lib/export.sh export_run)"
  else
    cmd="bash $(runner_stage_script "$stage") $RUN_DIR"
  fi
  review_begin "$RUN_DIR" "$stage" "$rc" "$msg" "$cmd" "$activity"
  runner_review_loop "$stage" "$label" "$activity" "$rc" "$msg" "$sig" "$cmd"
}

runner_resume_review() {  # stage label activity -> as runner_code_error, for a failure the previous runner left in the loop
  local stage="$1" label="$2" activity="$3" rec rc="" msg="" cmd="" act="" sig pending last_outcome last_n
  rec="$(state_get "$RUN_DIR" "errors.$stage" "{}" 2>/dev/null)"
  eval "$(json_eval "$rec" rc=review.rc msg=review.msg cmd=review.cmd act=review.activity sig=last_signature \
    pending=pending last_outcome=last_outcome last_n=last_n)"
  [ -n "$act" ] && activity="$act"
  [ -n "$msg" ] || msg="$(state_get "$RUN_DIR" "stages.$stage.error" "the stage failed" 2>/dev/null)"
  [ -n "$cmd" ] || cmd="bash $(runner_stage_script "$stage") $RUN_DIR"
  [ -n "$sig" ] || sig="$(error_signature "$msg")"
  case "$rc" in ''|*[!0-9]*) rc=1 ;; esac
  if [ -z "$pending" ] && [ "$last_outcome" = fixed ]; then
    # the fix was applied and recorded, the runner died before the restart: nothing left to review
    say INFO "$label $activity: the previous runner stopped right after fix F${last_n:-?} was applied, running the stage again"
    review_end "$RUN_DIR" "$stage" fixed
    return 0
  fi
  runner_review_loop "$stage" "$label" "$activity" "$rc" "$msg" "$sig" "$cmd"
}

runner_review_loop() {  # stage label activity rc msg sig cmd -> 0 restart the stage, 1 run ended (blocked), 2 stop
  # Each cycle runs in the child pipeline/bin/review-cycle, polled like a stage, so the heartbeat keeps printing
  # during the model calls. Until its verdict is recorded, the cycle number is errors.<stage>.pending in state.json
  # and the child's pid is errors/E<n>.pid: a runner restarted in the middle resumes the same cycle E<n> (adopting
  # a child that still runs, taking the verdict of one that finished, running again one that ended without a
  # verdict) instead of running the stage again, so no Opus cycle is lost and no false repeat is counted.
  local stage="$1" label="$2" activity="$3" rc="$4" msg="$5" sig="$6" cmd="$7" n crc result model_name pending kind_text
  local outcome reason summary commit class root_cause user_action fatal
  mkdir -p "$RUN_DIR/errors" "$RUN_DIR/fixes"
  while :; do
    review_decide "$RUN_DIR" "$stage"
    n="$REVIEW_N"
    pending="$(state_get "$RUN_DIR" "errors.$stage.pending" "" 2>/dev/null)"
    case "$pending" in ''|*[!0-9]*) pending="" ;; esac
    [ -n "$pending" ] && n="$pending"
    case "$REVIEW_KIND" in
      block)
        review_end "$RUN_DIR" "$stage" blocked
        runner_block_error "$stage" "$label" "$REVIEW_REASON: $msg" "$sig"
        return $?
        ;;
      fable)
        model_name="$(cfg models.reviewer_escalation.model fable)"
        kind_text="escalated review, $model_name"
        [ -n "$pending" ] || say ESCAL "$label still failing after $REVIEW_DONE $(plural "$REVIEW_DONE" review), escalating to $model_name"
        set_activity "error in $label: escalated review ($model_name)"
        ;;
      *)
        model_name="$(cfg models.reviewer.model opus)"
        kind_text="cycle $REVIEW_CYCLE/$REVIEW_CAP, $model_name"
        set_activity "error in $label: reviewing (cycle $REVIEW_CYCLE/$REVIEW_CAP, $model_name)"
        ;;
    esac
    result=""
    if [ -n "$pending" ]; then
      say INFO "$label $activity: review cycle E$n ($kind_text) was interrupted by the previous runner, resuming it: $msg"
      runner_adopt_review "$stage" "$label" "$n" && result="$(cat "$RUN_DIR/fixes/F$n.result.json" 2>/dev/null)"
    fi
    if [ -z "$result" ]; then
      printf '%s' "$msg" > "$RUN_DIR/errors/E$n.msg"
      printf '%s' "$cmd" > "$RUN_DIR/errors/E$n.cmd"
      rm -f "$RUN_DIR/fixes/F$n.result.json"
      review_pending_set "$RUN_DIR" "$stage" "$n"
      STAGE_STARTED="$EPOCHSECONDS"
      REELS_SAY_FD=3 bash "$REELS_PIPELINE/bin/review-cycle" "$RUN_DIR" "$stage" "$label" "$n" "$REVIEW_KIND" \
        "$REVIEW_CYCLE" "$REVIEW_CAP" "$rc" 3>&1 >>"$RUN_DIR/errors/E$n.log" 2>&1 &
      CHILD_PID=$!
      printf '%s %s\n' "$CHILD_PID" "$EPOCHSECONDS" > "$RUN_DIR/errors/E$n.pid"
      runner_wait_child "$CHILD_PID"; crc=$?
      CHILD_PID=""
      rm -f "$RUN_DIR/errors/E$n.pid"
      result="$(cat "$RUN_DIR/fixes/F$n.result.json" 2>/dev/null)"
      [ -n "$result" ] || result="{\"outcome\": \"error\", \"reason\": \"review-cycle exited $crc without a result (see errors/E$n.log)\"}"
    fi
    outcome=""; reason=""; summary=""; commit=""; class=""; root_cause=""; user_action=""; fatal=""
    eval "$(json_eval "$result" outcome=outcome reason=reason summary=summary commit=commit class=class root_cause=root_cause user_action=user_action fatal=fatal)"
    review_record "$RUN_DIR" "$stage" "$REVIEW_KIND" "$n" "${outcome:-error}"
    case "$outcome" in
      fixed)
        say FIXED "$label: ${summary:-fix F$n applied}${commit:+ (commit $commit)}, restarting stage"
        ISSUES_FIXED=$((ISSUES_FIXED + 1))
        [ "$ISSUES_OPEN" -gt 0 ] && ISSUES_OPEN=$((ISSUES_OPEN - 1))
        state_py issue "$RUN_DIR" fixed +1 >/dev/null 2>&1
        state_py issue "$RUN_DIR" open -1 >/dev/null 2>&1
        review_restart_note "$RUN_DIR" "$stage" "$msg" "$n" "${summary:-fix F$n applied}" "$commit"
        review_end "$RUN_DIR" "$stage" fixed
        set_activity "$activity"
        return 0
        ;;
      no_auto)
        review_end "$RUN_DIR" "$stage" blocked
        runner_block_error "$stage" "$label" "${class:-needs the user}: ${root_cause:-$reason}${user_action:+. Needs you: $user_action}" "$sig"
        return $?
        ;;
      *)
        if [ "$fatal" = 1 ] || [ "$fatal" = true ]; then
          review_end "$RUN_DIR" "$stage" blocked
          runner_block_error "$stage" "$label" "cannot review it: ${reason:-the review call failed}" "$sig"
          return $?
        fi
        say WARN "$label: review cycle E$n ($REVIEW_KIND) did not fix it: ${reason:-no reason given}"
        ;;
    esac
  done
}

runner_adopt_review() {  # stage label n -> 0 when cycle E<n>'s verdict is in fixes/F<n>.result.json (a child of the
                         # previous runner that still ran, or had finished); 1 when the cycle must run again
  local stage="$1" label="$2" n="$3" pidfile="$RUN_DIR/errors/E$3.pid" pid="" rest outcome=""
  if [ -f "$pidfile" ]; then
    { read -r pid rest < "$pidfile"; } 2>/dev/null || pid=""
    if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
      say WARN "$label: review cycle E$n still runs from the previous runner (pid $pid), waiting for it instead of starting it twice"
      STAGE_STARTED="$EPOCHSECONDS"
      while ps -p "$pid" >/dev/null 2>&1; do
        runner_tick
        sleep "$TICK_SECONDS"
      done
    fi
    rm -f "$pidfile"
  fi
  [ -s "$RUN_DIR/fixes/F$n.result.json" ] || return 1
  outcome="$(json_field "$(cat "$RUN_DIR/fixes/F$n.result.json")" outcome "" 2>/dev/null)"
  case "$outcome" in fixed|no_auto|failed) return 0 ;; esac
  return 1   # a cycle that ended without a verdict (killed with the runner, or its file is unreadable) runs again
}

runner_block_error() {  # stage label reason signature -> 1 run ended, 2 systemic stop (the streak reached the cap)
  # Only code-error blocks count toward the streak: an export or a drop resets it (runner_finalize, runner_drop),
  # a quality block (a stage's exit 20) leaves it alone. The file survives a restart; a systemic stop clears it.
  local stage="$1" label="$2" reason="$3" sig="$4" file="$REELS_LOGS/.block-streak" prev_sig="" count=0 cap rest
  runner_block "$stage" "$label" "$reason"
  cap="$(cfg caps.systemic_block_streak 3)"
  [ -f "$file" ] && { read -r prev_sig count rest < "$file"; } 2>/dev/null
  case "$count" in ''|*[!0-9]*) count=0 ;; esac
  if [ -n "$sig" ] && [ "$sig" = "$prev_sig" ]; then count=$((count + 1)); else count=1; fi
  printf '%s %s %s\n' "$sig" "$count" "$label" > "$file"
  if [ "$count" -ge "$cap" ]; then
    rm -f "$file"
    runner_systemic_stop "the same error blocked $count ideas in a row at $label: $reason" \
      "Read the reviewer's verdicts in runs/$RUN_ID/fixes/F*.md (root cause, class, and what only you can do when auto_apply was no) and the reports in runs/$RUN_ID/errors/E*.md." \
      "Fix the cause yourself: install the missing tool or key, free the disk, or correct the code under pipeline/ (the automatic fixer could not)." \
      "Re-add the blocked ideas: paste the braces from logs/blocked.txt into bash pipeline/bin/add-idea.sh (or into a Claude Code session in this folder)."
    return 2
  fi
  return 1
}

# ------------------------------------------------------------------ outcomes

runner_remove_idea() {
  ideas_remove "$IDEA_ID" "$IDEA_TEXT" >/dev/null 2>"$RUN_DIR/.remove.err" && return 0
  local line
  line="$(grep -v '^[[:space:]]*$' "$RUN_DIR/.remove.err" 2>/dev/null | tail -n 1 | tr -d '\r')"
  say WARN "${line:-idea $IDEA_ID could not be removed from ideas.txt}"
}

runner_drop() {  # stage reason
  local stage="$1" reason="$2"
  say DROP "idea \"$(cut_text "$IDEA_TEXT" 40)\" dropped: $reason. Removed from ideas.txt"
  runner_remove_idea
  history_add dropped "$IDEA_TEXT" "$reason"
  state_finish "$RUN_DIR" dropped "$reason" "$stage" >/dev/null
  SESSION_DROPPED=$((SESSION_DROPPED + 1))
  rm -f "$REELS_LOGS/.block-streak"
}

runner_block() {  # stage label reason
  local stage="$1" label="$2" reason="$3"
  say BLOCK "idea \"$(cut_text "$IDEA_TEXT" 40)\" blocked at $label: $reason. Moved to logs/blocked.txt"
  runner_remove_idea
  blocked_add "$IDEA_RAW" "$label" "$reason" "$RUN_DIR"
  history_add blocked "$IDEA_TEXT" "$reason"
  state_finish "$RUN_DIR" blocked "$reason" "$stage" >/dev/null
  SESSION_BLOCKED=$((SESSION_BLOCKED + 1))
}

runner_do_export() {  # -> 0 exported (state holds the number), 1 run ended, 2 stop, 3 fixed (try again)
  local out rc number
  STAGE_STARTED="$EPOCHSECONDS"
  set_activity "exporting"
  out="$(export_run "$RUN_DIR")"; rc=$?
  case "$rc" in
    0) return 0 ;;
    99)
      say WARN "planted crash after the export was $REELS_CRASH_AT (REELS_CRASH_AT): killing the runner now"
      kill -9 $$
      sleep 5
      exit 137
      ;;
    *)
      runner_code_error "14-export" "S14" "exporting" "$rc" "export failed: $(runner_last_log_line "$RUN_DIR/export.err")"; rc=$?
      [ "$rc" = 0 ] && return 3   # fixed: the loop runs 14-export and the export again
      return $rc
      ;;
  esac
}

runner_finalize() {  # the export is in exports/N: remove the idea, history line, DONE
  local number="$1" fin elapsed
  set_activity "exporting #$number"
  runner_remove_idea
  history_add exported "$IDEA_TEXT" "$number"
  fin="$(state_finish "$RUN_DIR" exported "exported #$number" "" "$number")"
  elapsed="$(json_field "$fin" elapsed 0)"
  say DONE "exported #$number -> exports/$number/ ($(fmt_min "$elapsed"), $ISSUES_FIXED $(plural "$ISSUES_FIXED" issue) fixed)"
  SESSION_EXPORTED=$((SESSION_EXPORTED + 1))
  rm -f "$REELS_LOGS/.block-streak"
  git -C "$REELS_REPO" rev-parse HEAD > "$REELS_LOGS/.last-good-sha" 2>/dev/null || true
}

# ------------------------------------------------------------------ one run

runner_pick_run() {  # sets RUN_DIR and RESUMED; returns 1 when there is nothing to do
  local list first id raw created
  if list="$(state_unfinished 2>/dev/null)"; then
    RUN_DIR="$(json_field "$list" 0.run_dir)"
    RESUMED=1
    return 0
  fi
  first="$(ideas_first 2>/dev/null)" || return 1
  eval "$(json_eval "$first" id=id raw=raw)"
  if ! created="$(state_new "$id" "$raw")"; then
    say ERROR "cannot create a run folder under $REELS_RUNS; retrying at the next poll"
    return 1
  fi
  RUN_DIR="$(json_field "$created" run_dir)"
  RESUMED=0
}

runner_process_run() {  # -> 0 run ended (any outcome), 2 systemic stop requested
  local summary queue nxt phase rc done_n next_act
  IN_RUN=1
  IDLE_SINCE=""
  if ! summary="$(state_pickup "$RUN_DIR")"; then
    say ERROR "cannot read $RUN_DIR/state.json; leaving the folder alone"
    runner_systemic_stop "the unfinished run $RUN_DIR has an unreadable state.json" \
      "inspect the folder; move it out of runs/ (for example into runs/_broken/) to let the runner continue"
    IN_RUN=0
    return 2
  fi
  eval "$(json_eval "$summary" RUN_ID=run_id IDEA_ID=idea_id IDEA_TEXT=idea_text IDEA_RAW=idea_raw \
    ELAPSED_BASE=accumulated SESSION_STARTED=session_started ISSUES_FIXED=issues_fixed ISSUES_OPEN=issues_open \
    done_n=stages_done phase=next.phase next_act=next.activity)"
  ELAPSED_BASE="${ELAPSED_BASE:-0}"; SESSION_STARTED="${SESSION_STARTED:-$EPOCHSECONDS}"
  ISSUES_FIXED="${ISSUES_FIXED:-0}"; ISSUES_OPEN="${ISSUES_OPEN:-0}"; done_n="${done_n:-0}"
  SESSION_N=$((SESSION_N + 1))
  queue="$(ideas_count 2>/dev/null || echo 0)"
  STAGE_STARTED="$EPOCHSECONDS"
  LAST_HEARTBEAT="$EPOCHSECONDS"
  if [ "$RESUMED" = 1 ]; then
    say START "idea $(runner_position "$SESSION_N" "$queue") \"$(cut_text "$IDEA_TEXT" 40)\" -> runs/$RUN_ID (resumed at $(runner_next_text "${phase:-stage}" "$next_act"), $done_n $(plural "$done_n" stage) done)"
  else
    say START "idea $(runner_position "$SESSION_N" "$queue") \"$(cut_text "$IDEA_TEXT" 40)\" -> runs/$RUN_ID"
  fi
  set_activity "starting"
  rc=0
  local nx_stage nx_label nx_activity nx_attempts nx_number nx_status
  NEXT_PHASE=""
  while true; do
    if [ -n "$NEXT_PHASE" ]; then  # left by the last stage-done
      phase="$NEXT_PHASE"; nx_stage="$NEXT_STAGE"; nx_label="$NEXT_LABEL"; nx_activity="$NEXT_ACTIVITY"
      nx_attempts="$NEXT_ATTEMPTS"; nx_number="$NEXT_NUMBER"; nx_status=""
      NEXT_PHASE=""
    else
      runner_state read 0 state_next "$RUN_DIR" || { rc=2; break; }
      nxt="$STATE_OUT"
      eval "$(json_eval "$nxt" phase=phase nx_stage=stage nx_label=label nx_activity=activity nx_attempts=attempts nx_number=number nx_status=stage_status)"
    fi
    case "${phase:-finished}" in
      stage)
        runner_run_stage "$nx_stage" "$nx_label" "$nx_activity" "$nx_attempts" "$nx_status"; rc=$?
        [ "$rc" = 0 ] || break
        ;;
      export)
        runner_do_export; rc=$?
        case "$rc" in
          0|3) NEXT_PHASE=""; rc=0 ;;  # ask state.py for the number (or run the fixed export again)
          *) break ;;
        esac
        ;;
      finalize)
        runner_finalize "$nx_number"
        rc=1; break
        ;;
      *) rc=1; break ;;
    esac
  done
  IN_RUN=0
  set_activity "between ideas"
  [ "$rc" = 2 ] && return 2
  runner_announce_next
  return 0
}

runner_announce_next() {
  local first queue="" text=""
  first="$(ideas_first 2>/dev/null)" || return 0
  eval "$(json_eval "$first" queue=queue text=text)"
  say NEXT "idea $(runner_position $((SESSION_N + 1)) "${queue:-1}") \"$(cut_text "$text" 40)\""
}

runner_position() {  # runner_position <k> <queue now> -> "k/total": total counts the ideas done this session plus
  local k="$1" queue="${2:-0}" total  # the ones still queued (the current idea is still in ideas.txt), as in spec 7
  case "$queue" in ''|*[!0-9]*) queue=0 ;; esac
  total=$(( k - 1 + queue ))
  [ "$total" -lt "$k" ] && total="$k"
  printf '%s/%s' "$k" "$total"
}

# ------------------------------------------------------------------ main loop

runner_main() {
  ONCE="${ONCE:-0}"
  mkdir -p "$REELS_ROOT/runs" "$REELS_ROOT/exports" "$REELS_LOGS" "$REELS_LOCKS"
  [ -f "$REELS_IDEAS" ] || : > "$REELS_IDEAS"
  runner_lock_take || return 1
  trap 'runner_on_signal INT' INT
  trap 'runner_on_signal TERM' TERM
  trap runner_on_exit EXIT
  preflight_run || return $?
  runner_load_stages || { say ERROR "cannot load the stage table (pipeline/lib/state.py stages)"; return 1; }

  REELS_RUNS="$REELS_ROOT/$(cfg paths.runs runs)"
  REELS_EXPORTS="$REELS_ROOT/$(cfg paths.exports exports)"
  export REELS_RUNS REELS_EXPORTS
  POLL_SECONDS="${REELS_POLL_SECONDS:-$(cfg runner.poll_seconds 120)}"
  HEARTBEAT_EVERY="${REELS_STATUS_EVERY:-$(cfg runner.status_every_seconds 300)}"
  TICK_SECONDS="${REELS_TICK_SECONDS:-1}"
  mkdir -p "$REELS_RUNS" "$REELS_EXPORTS"

  rm -f "$REELS_LOGS/.new-ideas"   # the banner shows the queue; NEW lines start after it
  if [ ! -s "$REELS_LOGS/.last-good-sha" ]; then  # the baseline for the error reports' git diff (review.sh)
    git -C "$REELS_REPO" rev-parse HEAD > "$REELS_LOGS/.last-good-sha" 2>/dev/null || rm -f "$REELS_LOGS/.last-good-sha"
  fi
  if [ -d "$REELS_LOCKS/exports" ]; then
    rm -rf "$REELS_LOCKS/exports"  # only a runner takes it, and this is the only runner: a leftover from a crash
    say WARN "removed a leftover exports lock from a previous runner"
  fi

  runner_banner
  SESSION_START="$EPOCHSECONDS"
  SESSION_N=0; SESSION_EXPORTED=0; SESSION_DROPPED=0; SESSION_BLOCKED=0
  IDLE_SINCE=""; LAST_HEARTBEAT="$EPOCHSECONDS"
  ELAPSED_BASE=0; SESSION_STARTED="$EPOCHSECONDS"; STAGE_STARTED="$EPOCHSECONDS"
  ISSUES_FIXED=0; ISSUES_OPEN=0; IDEA_TEXT=""; IDEA_ID=""; IDEA_RAW=""; RUN_ID=""; RESUMED=0

  while true; do
    runner_tick
    if runner_pick_run; then
      runner_process_run; rc=$?
      if [ "$rc" = 2 ] || [ "$STOP_REQUESTED" = 1 ]; then
        # the runner never exits on its own without a STOP line and logs/STOPPED.md (BUILD_SPEC.md section 4): a
        # stop that runner_systemic_stop did not write gets a generic diagnosis here
        [ "$STOP_REQUESTED" = 1 ] || runner_systemic_stop "the run ${RUN_DIR:-?} could not continue (the ERROR line before this one in logs/runner.log says why)" \
          "read the last lines of logs/runner.log and fix what they name"
        return 3
      fi
      continue
    fi
    if [ -z "$IDLE_SINCE" ]; then
      runner_summary_line
      [ "$ONCE" = 1 ] && return 0
      IDLE_SINCE="$EPOCHSECONDS"
      runner_idle_line
    elif [ $(( EPOCHSECONDS - LAST_HEARTBEAT )) -ge "$HEARTBEAT_EVERY" ]; then
      runner_idle_line
    fi
    if [ -n "${REELS_POLL_SECONDS:-}" ]; then sleep "$POLL_SECONDS"; else runner_sleep "$POLL_SECONDS" "idle poll"; fi
  done
}
