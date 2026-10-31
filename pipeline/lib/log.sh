# pipeline/lib/log.sh: terminal and log lines (BUILD_SPEC.md section 6). Source common.sh first.
#
#   say TAG text...
#
# Prints "[HH:MM] TAG    text" with the tag padded to 6 characters, in color when stdout is a terminal and
# NO_COLOR is unset, appends the plain line to logs/runner.log and overwrites logs/status.txt with it.
# M1 ships this minimal version; M2 adds the heartbeat, the IDLE line and the status rules per tag.

reels_tag_color() {
  case "$1" in
    START|DONE|READY|PASS) printf '\033[32m' ;;
    ERROR|BLOCK|STOP|FAIL) printf '\033[31m' ;;
    WARN|FLAG|LIMIT|RETRY|ESCAL|DROP) printf '\033[33m' ;;
    STEP|GATE|NEXT|NEW|RESUME|FIXED|ANGLE) printf '\033[36m' ;;
    *) printf '\033[2m' ;;
  esac
}

say() {
  local tag="$1"; shift
  local text="$*" stamp plain
  stamp="$(date +%H:%M)"
  plain="$(printf '[%s] %-6s %s' "$stamp" "$tag" "$text")"
  if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    printf '[%s] %s%-6s\033[0m %s\n' "$stamp" "$(reels_tag_color "$tag")" "$tag" "$text"
  else
    printf '%s\n' "$plain"
  fi
  if [ -n "${REELS_LOGS:-}" ]; then
    mkdir -p "$REELS_LOGS" 2>/dev/null || return 0
    printf '%s\n' "$plain" >> "$REELS_LOGS/runner.log"
    printf '%s\n' "$plain" > "$REELS_LOGS/status.txt"
  fi
}
