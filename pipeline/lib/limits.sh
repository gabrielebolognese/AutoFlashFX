# pipeline/lib/limits.sh: usage limit waits and scaled sleeps (BUILD_SPEC.md 4.1). Source common.sh, log.sh,
# config.sh and status.sh first. The parsing itself is pipeline/lib/limits.py (Python zoneinfo, because the GNU
# date in Git Bash has no zoneinfo database and treats TZ=Europe/Rome as UTC).
#
#   reels_sleep_scale                      REELS_SLEEP_SCALE, else runner.sleep_scale (read once)
#   reels_sleep SECONDS [what]             sleep scaled by the scale; 0 = fast-forward: one INFO line, no sleep
#   reels_wait_until EPOCH [what] [prefix] wait in 60 s chunks that re-read the clock (so a PC that slept stays
#                                          right); with a prefix, set_activity "<prefix> (<left> left)" each chunk;
#                                          fast-forward logs one INFO line with the target
#   reels_tick_hook                        called between the 60 s chunks of both waits: runs reels_wait_tick when
#                                          the caller defines it (the runner does: heartbeat and NEW lines)
#   limit_check "<text>"                   -> 0 a limit with a parsed reset (LIMIT_KIND, LIMIT_RESET, LIMIT_TARGET,
#                                          LIMIT_WHEN, LIMIT_MSG set), 2 a limit but nothing parsed, 1 no limit
#   limit_wait RESET KIND "activity" ["message"]   the LIMIT line, logs/limits.log, the wait until RESET plus
#                                          runner.limit_margin_seconds, then the RESUME line and the activity back
#   limit_wait_unparsed KIND "activity" "message" -- probe command...   the LIMIT line, sleep
#                                          errors.unparsed_limit_sleep_seconds, then run the probe command every
#                                          errors.probe_every_seconds until it exits 0 (REELS_PROBE_MAX caps the
#                                          probes in tests, exit 1 when reached), then the RESUME line;
#                                          LIMIT_PROBES holds how many probes it took (1: the first one answered)
#   limits_log "text"                      append "<date time> | text" to logs/limits.log
#   fmt_left SECONDS                       5h41m, 12m
#   fmt_wait SECONDS                       60s, 4m, 16m (the RETRY line)
#   fmt_clock EPOCH                        15:47 when today, Mon 00:02 within a week, else Nov 3 10:00

reels_sleep_scale() {
  if [ -z "${REELS_SLEEP_SCALE_VALUE:-}" ]; then
    REELS_SLEEP_SCALE_VALUE="${REELS_SLEEP_SCALE:-$(cfg runner.sleep_scale 1 2>/dev/null || echo 1)}"
  fi
  printf '%s' "$REELS_SLEEP_SCALE_VALUE"
}

reels_fast_forward() {  # 0 when the scale is 0 (log the wait, do not sleep)
  case "$(reels_sleep_scale)" in 0|0.0|0.00) return 0 ;; esac
  return 1
}

reels_sleep_raw() {  # the scaled sleep without any line, in chunks of at most 60 s with the tick hook in between
  local s="$1" scale whole
  scale="$(reels_sleep_scale)"
  case "$scale" in
    0|0.0|0.00) return 0 ;;
    1|1.0) ;;
    *) s="$(awk -v s="$s" -v k="$scale" 'BEGIN { v = s * k; if (v < 0.05) v = 0.05; printf "%.3f", v }')" ;;
  esac
  whole="${s%%.*}"
  case "$whole" in ''|*[!0-9]*) whole=0 ;; esac
  if [ "$whole" -gt 60 ]; then  # a long wait: the runner's heartbeat and NEW lines keep coming between the chunks
    while [ "$whole" -gt 60 ]; do sleep 60; whole=$((whole - 60)); reels_tick_hook; done
    s="$whole"
  fi
  sleep "$s"
}

reels_tick_hook() {  # between the chunks of a wait: the runner defines reels_wait_tick (heartbeat, NEW lines); stages do not
  if declare -F reels_wait_tick >/dev/null 2>&1; then reels_wait_tick; fi
  return 0
}

reels_sleep() {  # reels_sleep <seconds> [what]
  local s="$1" what="${2:-}"
  if reels_fast_forward; then
    say INFO "fast-forward: skipping a $(fmt_wait "$s") wait${what:+ ($what)}"
    return 0
  fi
  reels_sleep_raw "$s"
}

fmt_wait() {  # fmt_wait <seconds>: 60s, 4m, 16m, 2h30m (the RETRY line's style)
  local s="${1:-0}"
  if [ "$s" -lt 120 ]; then printf '%ds' "$s"
  elif [ $((s % 60)) -eq 0 ] && [ "$s" -lt 3600 ]; then printf '%dm' $((s / 60))
  else fmt_dur "$s"; fi
}

fmt_left() {
  local s="${1:-0}" h m
  [ "$s" -lt 0 ] 2>/dev/null && s=0
  h=$((s / 3600)); m=$(((s % 3600) / 60))
  if [ "$h" -gt 0 ]; then printf '%dh%02dm' "$h" "$m"; else printf '%dm' "$m"; fi
}

fmt_clock() {  # fmt_clock <epoch>: 15:47 today, Mon 00:02 within 7 days, Nov 3 10:00 beyond
  local t="$1" day today days
  printf -v day '%(%Y%m%d)T' "$t"
  printf -v today '%(%Y%m%d)T' -1
  if [ "$day" = "$today" ]; then printf '%(%H:%M)T' "$t"; return; fi
  days=$(( (t - EPOCHSECONDS) / 86400 ))
  if [ "$days" -lt 7 ]; then printf '%(%a %H:%M)T' "$t"; else printf '%(%b %-d %H:%M)T' "$t" 2>/dev/null || printf '%(%b %d %H:%M)T' "$t"; fi
}

reels_wait_until() {  # reels_wait_until <epoch> [what] [activity prefix]
  local target="$1" what="${2:-}" prefix="${3:-}" now left chunk
  now="$EPOCHSECONDS"
  [ "$target" -le "$now" ] && return 0
  if reels_fast_forward; then
    say INFO "fast-forward: skipping the wait until $(fmt_clock "$target") ($(fmt_left $((target - now))))${what:+ ($what)}"
    [ -n "$prefix" ] && set_activity "$prefix (0m left)"
    return 0
  fi
  while :; do
    now="$EPOCHSECONDS"
    left=$((target - now))
    [ "$left" -le 0 ] && break
    [ -n "$prefix" ] && set_activity "$prefix ($(fmt_left "$left") left)"
    chunk=$(( left < 60 ? left : 60 ))
    reels_sleep_raw "$chunk"
    reels_tick_hook
  done
}

limits_log() {
  mkdir -p "$REELS_LOGS" 2>/dev/null || return 0
  printf '%(%Y-%m-%d %H:%M:%S)T | %s\n' -1 "$*" >> "$REELS_LOGS/limits.log"
}

limit_margin() { printf '%s' "${REELS_LIMIT_MARGIN:-$(cfg runner.limit_margin_seconds 120)}"; }

limit_check() {  # limit_check "<text>" -> 0 parsed, 2 unparsed limit, 1 none
  local out rc tz
  tz="$(cfg runner.timezone "" 2>/dev/null)"
  out="$(printf '%s' "$1" | "$REELS_PY" "$REELS_PIPELINE/lib/limits.py" detect --stdin --tz "$tz" --margin "$(limit_margin)")"; rc=$?
  LIMIT_KIND=""; LIMIT_RESET=""; LIMIT_TARGET=""; LIMIT_WHEN=""; LIMIT_MSG=""
  [ "$rc" = 1 ] && return 1
  eval "$(json_eval "$out" LIMIT_KIND=kind LIMIT_RESET=reset LIMIT_TARGET=target LIMIT_WHEN=when LIMIT_MSG=message)"
  return $rc
}

limit_wait() {  # limit_wait <reset epoch> <kind> "<activity>" ["<message>"]
  local reset="$1" kind="${2:-usage}" activity="${3:-working}" message="${4:-}" margin target started margin_text
  margin="$(limit_margin)"
  target=$((reset + margin))
  started="$EPOCHSECONDS"
  if [ $((margin % 60)) -eq 0 ]; then margin_text="+$((margin / 60)) min margin"; else margin_text="+${margin}s margin"; fi
  say LIMIT "$kind limit hit, resuming at $(fmt_clock "$target") ($margin_text)"
  printf -v _reset_iso '%(%Y-%m-%d %H:%M)T' "$reset"
  printf -v _target_iso '%(%Y-%m-%d %H:%M:%S)T' "$target"
  limits_log "$kind limit | reset $_reset_iso | waiting until $_target_iso (reset + ${margin} s)${message:+ | \"$message\"}"
  reels_wait_until "$target" "$kind limit" "waiting for usage limit ($kind) until $(fmt_clock "$target")"
  limits_log "resumed after the $kind limit (waited $(fmt_dur $((EPOCHSECONDS - started))))"
  say RESUME "limit reset, continuing: $activity"
  set_activity "$activity"
}

limit_wait_unparsed() {  # limit_wait_unparsed <kind> "<activity>" "<message>" -- <probe command...>
  local kind="${1:-usage}" activity="${2:-working}" message="${3:-}" first every n=0 max="${REELS_PROBE_MAX:-}"
  shift 3
  [ "${1:-}" = "--" ] && shift
  first="$(cfg errors.unparsed_limit_sleep_seconds 1800)"
  every="$(cfg errors.probe_every_seconds 1800)"
  say LIMIT "$kind limit hit but no reset time found, probing every $((every / 60)) min (first probe in $((first / 60)) min)"
  limits_log "$kind limit | no reset time parsed | probing every ${every} s after ${first} s${message:+ | \"$message\"}"
  set_activity "waiting for usage limit ($kind), no reset time given, probing every $((every / 60)) min"
  reels_sleep "$first" "unparsed limit"
  LIMIT_PROBES=0
  while :; do
    n=$((n + 1))
    LIMIT_PROBES="$n"
    if "$@"; then break; fi
    if [ -n "$max" ] && [ "$n" -ge "$max" ]; then
      say WARN "the usage limit probe failed $n times and REELS_PROBE_MAX is $max, giving up"
      return 1
    fi
    set_activity "waiting for usage limit ($kind), probe $n failed, next probe in $((every / 60)) min"
    reels_sleep "$every" "limit probe"
  done
  limits_log "resumed after the $kind limit (probe $n answered)"
  say RESUME "limit is over (probe $n answered), continuing: $activity"
  set_activity "$activity"
}
