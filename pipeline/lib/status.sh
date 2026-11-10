# pipeline/lib/status.sh: the runner's terminal messages (BUILD_SPEC.md sections 6 and 7). Source common.sh,
# log.sh, config.sh, ideas.sh and history.sh first. The runner (runner.sh) owns the globals these read.
#
#   set_activity "<text>"        publish the current activity (logs/.activity: epoch TAB text); stages call it too
#   get_activity                 print the current activity text
#   runner_banner                START banner (version, queue, style, voice, sfx map), INFO root and mode, the queue
#   runner_heartbeat             the REEL line: #idea i/n "text..." | activity | minute M | stage T | issues: f fixed, o open
#   runner_idle_line             the IDLE line: no ideas ..., checking every N min (idle M min) | today: e exported, d dropped
#   runner_summary_line          when the queue empties: this session's counts and duration, plus today's
#   runner_check_new_ideas       print a NEW line for every record add-idea.sh left in logs/.new-ideas, then clear it
#   runner_tick                  what runs between polls: new ideas, the log rotation (at most once a minute;
#                                REELS_LOG_ROTATE_EVERY seconds in tests) and the heartbeat when it is due inside a run
#
# Globals (set by runner.sh): ONCE, IN_RUN, SESSION_N, IDEA_TEXT, RUN_DIR, ELAPSED_BASE, SESSION_STARTED,
# STAGE_STARTED, ISSUES_FIXED, ISSUES_OPEN, HEARTBEAT_EVERY, LAST_HEARTBEAT, IDLE_SINCE, POLL_SECONDS,
# SESSION_START, SESSION_EXPORTED, SESSION_DROPPED, SESSION_BLOCKED.

set_activity() {
  mkdir -p "$REELS_LOGS" 2>/dev/null || return 0
  printf '%s\t%s\n' "$EPOCHSECONDS" "$1" > "$REELS_LOGS/.activity"
}

get_activity() {
  local epoch text
  if [ -f "$REELS_LOGS/.activity" ]; then
    IFS=$'\t' read -r epoch text < "$REELS_LOGS/.activity" || true
    printf '%s' "${text:-working}"
  else
    printf 'working'
  fi
}

runner_banner() {
  local version style primary fallback queue sfx_map sfx_count="not built" sha=""
  version="$(cfg version 0.0.0)"
  style="$(cfg style -)"
  primary="$("$REELS_PY" "$REELS_PIPELINE/lib/voiceover.py" engine --brief 2>/dev/null)"; [ -n "$primary" ] || primary="unknown"
  fallback="none"  # one voice per reel, no fallback (BUILD_SPEC.md 2.5)
  queue="$(ideas_count 2>/dev/null || echo 0)"
  queue="${queue:-0}"
  sfx_map="$(chcfg sfx.map)"
  if [ -f "$sfx_map" ]; then
    sfx_count="$("$REELS_PY" -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(len(m.get("files", [])), "files")' "$sfx_map" 2>/dev/null || echo "unreadable")"
  fi
  sha="$(git -C "$REELS_REPO" rev-parse --short HEAD 2>/dev/null || true)"
  say START "reels autopilot v${version}${sha:+ (${sha})} | queue: $queue $(plural "$queue" idea) | style: $style | voice: $primary | sfx map: $sfx_count"
  say INFO "root: $REELS_ROOT | channel: $REELS_CHANNEL | mode: $([ "${ONCE:-0}" = 1 ] && echo "once (stops when the queue is empty)" || echo "forever (Ctrl+C stops it, a restart resumes)")${REELS_DUMMY:+ | dummy stages: $REELS_DUMMY}"
  if [ "$queue" -gt 0 ]; then
    local n=0 id text
    while IFS=$'\t' read -r id text; do
      n=$((n + 1))
      say QUEUE "$n. $(cut_text "$text" 60)"
      [ "$n" -ge 10 ] && { [ "$queue" -gt 10 ] && say QUEUE "... and $((queue - 10)) more"; break; }
    done < <(ideas_list)
  fi
}

runner_heartbeat() {
  local now="$EPOCHSECONDS" queue minute stage_s
  queue="$(ideas_count 2>/dev/null || echo 0)"
  minute=$(( (ELAPSED_BASE + now - SESSION_STARTED) / 60 ))
  stage_s=$(( now - STAGE_STARTED ))
  say REEL "#idea $(runner_position "$SESSION_N" "$queue") \"$(cut_text "$IDEA_TEXT" 40)\" | $(get_activity) | minute $minute | stage $(fmt_dur "$stage_s") | issues: ${ISSUES_FIXED} fixed, ${ISSUES_OPEN} open"
  LAST_HEARTBEAT="$now"
  [ -n "${RUN_DIR:-}" ] && state_touch "$RUN_DIR" >/dev/null 2>&1 || true
}

runner_today_text() {
  local e d b
  read -r e d b < <(history_counts)
  printf 'today: %s exported, %s dropped' "$e" "$d"
  [ "${b:-0}" -gt 0 ] && printf ', %s blocked' "$b"
  return 0
}

runner_idle_line() {
  local now="$EPOCHSECONDS" idle_min every
  idle_min=$(( (now - IDLE_SINCE) / 60 ))
  if [ -n "${QUOTA_TEXT:-}" ]; then   # M19: the daily quota is reached, the next idea waits for midnight in the channel's timezone
    say IDLE "$QUOTA_TEXT"
    LAST_HEARTBEAT="$now"
    return 0
  fi
  if [ "$POLL_SECONDS" -ge 60 ] 2>/dev/null; then every="$((POLL_SECONDS / 60)) min"; else every="${POLL_SECONDS} s"; fi
  say IDLE "no ideas in ideas.txt, checking every $every (idle $idle_min min) | $(runner_today_text)"
  LAST_HEARTBEAT="$now"
}

runner_summary_line() {
  local took=$(( EPOCHSECONDS - SESSION_START ))
  say IDLE "queue $([ -n "${QUOTA_TEXT:-}" ] && echo "held by the quota" || echo empty): this session $SESSION_EXPORTED exported, $SESSION_DROPPED dropped, $SESSION_BLOCKED blocked in $(fmt_dur "$took") | $(runner_today_text)"
}

runner_check_new_ideas() {
  local file="$REELS_LOGS/.new-ideas" epoch id queue source
  [ -s "$file" ] || return 0
  local tmp="$file.$$"
  mv -f "$file" "$tmp" 2>/dev/null || return 0
  while IFS=$'\t' read -r epoch id queue source; do
    [ -n "$id" ] || continue
    say NEW "idea added from ${source:-add-idea.sh} (queue: ${queue:-?})"
  done < "$tmp"
  rm -f "$tmp"
}

runner_tick() {
  runner_check_new_ideas
  if [ $(( EPOCHSECONDS - ${LOG_ROTATE_CHECKED:-0} )) -ge "${REELS_LOG_ROTATE_EVERY:-60}" ]; then  # runner.log over 50 MB: rotate (M13)
    LOG_ROTATE_CHECKED="$EPOCHSECONDS"
    reels_log_rotate || true
  fi
  if [ "${IN_RUN:-0}" = 1 ] && [ $(( EPOCHSECONDS - LAST_HEARTBEAT )) -ge "$HEARTBEAT_EVERY" ]; then
    runner_heartbeat
  fi
}
