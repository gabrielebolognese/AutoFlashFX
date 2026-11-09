# pipeline/lib/heavy.sh: heavy steps take turns across channels (BUILD_SPEC.md 14.6) and the machine's global log.
# Source common.sh, log.sh and config.sh first (status.sh when you want the activity shown while waiting).
#
#   heavy_run <kind> <label> -- command...   runs the command while holding the global lock .locks/heavy.lock. <kind> is one of
#                                            config heavy.kinds (tts, transcribe, render, encode, analyze, frame-match,
#                                            capture); a kind that is not listed runs without the lock. <label> says what runs
#                                            ("S13 render"). A runner that has to wait prints one WAIT line
#                                            ("WAIT heavy: scenarios S13 render holds it since 14:02"), sets its activity
#                                            ("waiting for the heavy lock (scenarios S13 render)") so the heartbeat shows the wait,
#                                            and goes on when the lock is free. A wait over heavy.wait_log_seconds (600) also
#                                            writes a line to logs/engine.log. Returns the command's exit code. Nested calls
#                                            (REELS_HELD_heavy=1) run the command at once.
#   editor_run <label> -- command...         the same, on .locks/editor.lock (the stable editor copy; used from M21)
#   heavy_holder                             prints "<pid> <epoch> <channel> <kind> <label>" of the current holder, exit 1 when none
#   engine_log "text"                        append "<date time> | <channel or -> | text" to the shared logs/engine.log
#                                            (global events only: heavy waits over 10 minutes, shared limit waits, the editor copy)
#
# The lock is a directory made with mkdir (the mechanism of M1), with a file holder inside: "pid epoch channel kind label" (pid is the
# calling script's own bash pid, so ps -p finds it). A lock whose holder is gone is broken (stale by pid); a lock without a holder file
# older than heavy.stale_seconds, or with a holder file older than that, is broken too (a crash between mkdir and the write, a
# recycled pid). REELS_HEAVY_POLL overrides heavy.poll_seconds (tests).

heavy_lock_dir() { printf '%s' "$REELS_GLOBAL_LOCKS/${HEAVY_LOCK_NAME:-heavy}.lock"; }

engine_log() {
  local __text="$*" file
  reels_undash __text
  file="$REELS_GLOBAL_LOGS/engine.log"
  mkdir -p "$REELS_GLOBAL_LOGS" 2>/dev/null || return 0
  printf '%(%Y-%m-%d %H:%M:%S)T | %s | %s\n' -1 "${REELS_CHANNEL:--}" "$__text" >> "$file"
}

heavy_holder() {
  local f; f="$(heavy_lock_dir)/holder"
  [ -f "$f" ] || return 1
  cat "$f" 2>/dev/null
}

heavy_kind_listed() {
  local kinds
  kinds="$(cfg heavy.kinds '[]' 2>/dev/null)"
  case "$kinds" in *"\"$1\""*) return 0 ;; esac
  return 1
}

heavy_break_if_stale() {  # 0 when a stale lock was removed
  local dir hpid hepoch rest age stale mt
  dir="$(heavy_lock_dir)"
  stale="$(cfg heavy.stale_seconds 21600 2>/dev/null)"
  if [ -f "$dir/holder" ]; then
    read -r hpid hepoch rest < "$dir/holder" 2>/dev/null || true
    if [ -n "${hpid:-}" ] && ! ps -p "$hpid" >/dev/null 2>&1; then
      rm -rf "$dir"; return 0
    fi
    if [ -n "${hepoch:-}" ] && [ $(( EPOCHSECONDS - hepoch )) -gt "$stale" ]; then
      rm -rf "$dir"; return 0
    fi
    return 1
  fi
  mt="$(stat -c %Y "$dir" 2>/dev/null || echo "$EPOCHSECONDS")"
  age=$(( EPOCHSECONDS - mt ))
  if [ "$age" -gt 5 ] && { [ "$age" -gt "$stale" ] || [ "$age" -gt 20 ]; }; then rm -rf "$dir"; return 0; fi
  return 1
}

heavy_try() {  # heavy_try <kind> <label>: 0 acquired, 1 busy
  local dir; dir="$(heavy_lock_dir)"
  mkdir -p "$REELS_GLOBAL_LOCKS" 2>/dev/null || true
  if mkdir "$dir" 2>/dev/null; then
    printf '%s %s %s %s %s\n' "$$" "$EPOCHSECONDS" "${REELS_CHANNEL:--}" "$1" "$2" > "$dir/holder"
    return 0
  fi
  heavy_break_if_stale && return 2
  return 1
}

heavy_release() {
  local dir hpid rest; dir="$(heavy_lock_dir)"
  [ -f "$dir/holder" ] || return 0
  read -r hpid rest < "$dir/holder" 2>/dev/null || true
  [ "${hpid:-}" = "$$" ] || return 0
  rm -rf "$dir"
}

heavy_run() {
  local kind="$1" label="$2" rc waited_since="" poll hpid hepoch hch hkind hlabel when logged=0 rt
  shift 2
  [ "${1:-}" = "--" ] && shift
  local lname="${HEAVY_LOCK_NAME:-heavy}" held_var
  held_var="REELS_HELD_${lname}"
  if [ -n "${!held_var:-}" ] || { [ "$lname" = heavy ] && ! heavy_kind_listed "$kind"; }; then
    "$@"; return $?
  fi
  poll="${REELS_HEAVY_POLL:-$(cfg heavy.poll_seconds 2 2>/dev/null)}"
  while :; do
    heavy_try "$kind" "$label"; rt=$?
    [ "$rt" = 0 ] && break
    [ "$rt" = 2 ] && continue
    if [ -z "$waited_since" ]; then
      waited_since="$EPOCHSECONDS"
      read -r hpid hepoch hch hkind hlabel < <(heavy_holder) 2>/dev/null || true
      if [ -n "${hepoch:-}" ]; then printf -v when '%(%H:%M)T' "$hepoch"; else when="?"; fi
      say WAIT "$lname: ${hch:-?} ${hlabel:-${hkind:-a heavy step}} holds it since $when"
      if declare -F set_activity >/dev/null 2>&1; then set_activity "waiting for the $lname lock (${hch:-?} ${hlabel:-${hkind:-?}})"; fi
    fi
    if [ "$logged" = 0 ] && [ $(( EPOCHSECONDS - waited_since )) -ge "$(cfg heavy.wait_log_seconds 600 2>/dev/null)" ]; then
      logged=1
      engine_log "$lname lock: $label of ${REELS_CHANNEL:--} has waited $(( (EPOCHSECONDS - waited_since) / 60 )) min for ${hch:-?} ${hlabel:-?}"
    fi
    sleep "$poll"
  done
  if [ -n "$waited_since" ] && declare -F set_activity >/dev/null 2>&1; then set_activity "$label"; fi
  export "$held_var=1"
  "$@"; rc=$?
  unset "$held_var"
  heavy_release
  return "$rc"
}

editor_run() {  # editor_run <label> -- command...: the same turns on .locks/editor.lock, for advancing or rebuilding the stable editor
                # copy of S15 so two runners never do it at once (M21 uses it; BUILD_SPEC.md 14.6)
  local label="$1"; shift
  [ "${1:-}" = "--" ] && shift
  ( HEAVY_LOCK_NAME=editor; heavy_run editor "$label" -- "$@" )
}
