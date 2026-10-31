# pipeline/lib/log.sh: terminal and log lines (BUILD_SPEC.md section 6). Source common.sh first.
#
#   say TAG text...        print "[HH:MM] TAG    text" (tag padded to 6), append it to logs/runner.log and
#                          overwrite logs/status.txt with it (every tag except the ones in REELS_STATUS_SKIP_TAGS,
#                          default "QUEUE INFO": listings and chatter never replace the status line)
#   fmt_dur SECONDS        2m51s, 45s, 1h02m
#   fmt_min SECONDS        "31 min" (or "43s" under a minute), for the DONE line
#   cut_text TEXT [N]      the text cut at N characters (default 40) with "..." when it was longer
#   plural N word          word or words
#
# Colors: ANSI when the output is a terminal and NO_COLOR is unset. A stage script runs with its stdout in its
# own stage.log and the runner's terminal on fd 3 (REELS_SAY_FD=3), so its say lines still reach the screen.

reels_tag_color() {
  case "$1" in
    START|DONE|READY|PASS) printf '\033[32m' ;;
    ERROR|BLOCK|STOP|FAIL) printf '\033[31m' ;;
    WARN|FLAG|LIMIT|RETRY|ESCAL|DROP) printf '\033[33m' ;;
    STEP|GATE|NEXT|NEW|RESUME|FIXED|ANGLE) printf '\033[36m' ;;
    REEL|IDLE) printf '\033[1m' ;;
    *) printf '\033[2m' ;;
  esac
}

say() {
  local tag="$1"; shift
  local text="$*" stamp plain fd="${REELS_SAY_FD:-1}"
  printf -v stamp '%(%H:%M)T' -1
  printf -v plain '[%s] %-6s %s' "$stamp" "$tag" "$text"
  if [ "$fd" != "1" ] && ! { true >&"$fd"; } 2>/dev/null; then fd=1; fi
  if [ -t "$fd" ] && [ -z "${NO_COLOR:-}" ]; then
    printf '[%s] %s%-6s\033[0m %s\n' "$stamp" "$(reels_tag_color "$tag")" "$tag" "$text" >&"$fd"
  else
    printf '%s\n' "$plain" >&"$fd"
  fi
  if [ -n "${REELS_LOGS:-}" ]; then
    mkdir -p "$REELS_LOGS" 2>/dev/null || return 0
    printf '%s\n' "$plain" >> "$REELS_LOGS/runner.log"
    case " ${REELS_STATUS_SKIP_TAGS:-QUEUE INFO} " in
      *" $tag "*) ;;
      *) printf '%s\n' "$plain" > "$REELS_LOGS/status.txt" ;;
    esac
  fi
}

fmt_dur() {
  local s="${1:-0}" h m
  [ "$s" -lt 0 ] 2>/dev/null && s=0
  h=$((s / 3600)); m=$(((s % 3600) / 60)); s=$((s % 60))
  if [ "$h" -gt 0 ]; then printf '%dh%02dm' "$h" "$m"
  elif [ "$m" -gt 0 ]; then printf '%dm%02ds' "$m" "$s"
  else printf '%ds' "$s"; fi
}

fmt_min() {
  local s="${1:-0}"
  if [ "$s" -ge 60 ]; then printf '%d min' "$(( (s + 30) / 60 ))"; else printf '%ds' "$s"; fi
}

cut_text() {
  local text="$1" n="${2:-40}"
  if [ "${#text}" -gt "$n" ]; then printf '%s...' "${text:0:$n}"; else printf '%s' "$text"; fi
}

plural() { if [ "$1" = "1" ]; then printf '%s' "$2"; else printf '%ss' "$2"; fi; }
