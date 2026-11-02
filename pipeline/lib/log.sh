# pipeline/lib/log.sh: terminal and log lines (BUILD_SPEC.md section 6). Source common.sh first.
#
#   say TAG text...        print "[HH:MM] TAG    text" (tag padded to 6), append it to logs/runner.log and
#                          overwrite logs/status.txt with it (every tag except the ones in REELS_STATUS_SKIP_TAGS,
#                          default "QUEUE INFO": listings and chatter never replace the status line)
#   fmt_dur SECONDS        2m51s, 45s, 1h02m
#   fmt_min SECONDS        "31 min" (or "43s" under a minute), for the DONE line
#   cut_text TEXT [N]      the text cut at N characters (default 40) with "..." when it was longer
#   plural N word          word or words
#   reels_log_rotate       when logs/runner.log has reached logs.rotate_mb (50 MB; REELS_LOG_ROTATE_BYTES in tests),
#                          move it to runner.log.1 (older files shift to .2 ... up to logs.rotate_keep, default 3,
#                          the oldest is deleted) and start the new file with an INFO line naming the old one.
#                          Returns 0 when it rotated. The runner calls it at startup and at most once a minute.
#   reels_undash VAR       rewrite the variable in place: an em dash (U+2014) becomes ", " whatever the spaces
#                          around it ("a, b"), one at either end is dropped; an en dash (U+2013) between spaces is
#                          treated the same, one inside a word (a range of numbers) becomes a hyphen
#   undash TEXT            the same, printed
#
# Colors: ANSI when the output is a terminal and NO_COLOR is unset. A stage script runs with its stdout in its
# own stage.log and the runner's terminal on fd 3 (REELS_SAY_FD=3), so its say lines still reach the screen.
#
# No file or terminal line of this project may contain an em dash (BUILD_SPEC.md 0.7), but external text does: the
# Claude CLI's network message on this PC ("Can't reach the API server (em dash) check your internet or DNS"), a
# tool's stderr, a model's answer. say() cleans every line it prints, and the composers of one-line messages
# (runner_last_log_line, errors.py, history.txt, blocked.txt, STOPPED.md, E<n>.md's error line) clean their text
# before it is written (M3 review 3, fix 2). The characters are built from their UTF-8 bytes so this file stays clean.

REELS_EM_DASH=$'\xe2\x80\x94'   # U+2014
REELS_EN_DASH=$'\xe2\x80\x93'   # U+2013

reels_undash() {  # reels_undash VAR (the variable's name; its value is rewritten in place)
  local __ud="${!1}" __em="$REELS_EM_DASH" __en="$REELS_EN_DASH"
  [[ "$__ud" == *"$__em"* || "$__ud" == *"$__en"* ]] || return 0
  __ud="${__ud// $__en / $__em }"; __ud="${__ud//$__en/-}"
  while [[ "$__ud" == *" $__em"* ]]; do __ud="${__ud// $__em/$__em}"; done
  while [[ "$__ud" == *"$__em "* ]]; do __ud="${__ud//$__em /$__em}"; done
  while [[ "$__ud" == *"$__em$__em"* ]]; do __ud="${__ud//$__em$__em/$__em}"; done
  __ud="${__ud#"$__em"}"; __ud="${__ud%"$__em"}"
  printf -v "$1" '%s' "${__ud//$__em/, }"
}

undash() { local __u="$1"; reels_undash __u; printf '%s' "$__u"; }

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
  reels_undash text   # external text (a CLI message, a log line, a model's words) may carry an em dash
  printf -v stamp '%(%H:%M)T' -1
  printf -v plain '[%s] %-6s %s' "$stamp" "$tag" "$text"
  if [ "$fd" != "1" ] && ! { true >&"$fd"; } 2>/dev/null; then fd=1; fi
  if [ -t "$fd" ] && [ -z "${NO_COLOR:-}" ]; then
    printf '[%s] %s%-6s\033[0m %s\n' "$stamp" "$(reels_tag_color "$tag")" "$tag" "$text" >&"$fd"
  else
    printf '%s\n' "$plain" >&"$fd"
  fi
  if [ -n "${REELS_LOGS:-}" ]; then
    # [ -d ] is a builtin: the folder is made once, not by a mkdir process on every line (M13: the rename below costs
    # one process already)
    [ -d "$REELS_LOGS" ] || mkdir -p "$REELS_LOGS" 2>/dev/null || return 0
    printf '%s\n' "$plain" >> "$REELS_LOGS/runner.log"
    case " ${REELS_STATUS_SKIP_TAGS:-QUEUE INFO} " in
      *" $tag "*) ;;
      *)  # written aside and renamed, so a reader never sees it empty or half written (M13); a rename refused
          # while another program holds the file open falls back to the direct write
          { printf '%s\n' "$plain" > "$REELS_LOGS/.status.$BASHPID" && mv -f "$REELS_LOGS/.status.$BASHPID" "$REELS_LOGS/status.txt"; } 2>/dev/null \
            || { rm -f "$REELS_LOGS/.status.$BASHPID" 2>/dev/null; printf '%s\n' "$plain" > "$REELS_LOGS/status.txt"; } ;;
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

reels_log_rotate() {
  local f="$REELS_LOGS/runner.log" max mb keep size i
  [ -f "$f" ] || return 1
  if [ -n "${REELS_LOG_ROTATE_BYTES:-}" ]; then max="$REELS_LOG_ROTATE_BYTES"
  else
    mb=50; declare -F cfg >/dev/null 2>&1 && mb="$(cfg logs.rotate_mb 50 2>/dev/null)"
    case "$mb" in ''|*[!0-9]*) mb=50 ;; esac
    max=$(( mb * 1048576 ))
  fi
  size="$(stat -c %s "$f" 2>/dev/null)" || return 1
  case "$size" in ''|*[!0-9]*) return 1 ;; esac
  [ "$size" -ge "$max" ] || return 1
  keep=3; declare -F cfg >/dev/null 2>&1 && keep="$(cfg logs.rotate_keep 3 2>/dev/null)"
  case "$keep" in ''|*[!0-9]*|0) keep=3 ;; esac
  rm -f "$f.$keep"
  for (( i = keep - 1; i >= 1; i-- )); do [ -f "$f.$i" ] && mv -f "$f.$i" "$f.$((i + 1))"; done
  mv -f "$f" "$f.1" || return 1
  local what; if [ "$size" -ge 1048576 ]; then what="$(( size / 1048576 )) MB"; else what="$size bytes"; fi
  REELS_STATUS_SKIP_TAGS="${REELS_STATUS_SKIP_TAGS:-QUEUE INFO}" say INFO "logs/runner.log reached $what: the earlier lines are in logs/runner.log.1 (up to $keep old files are kept)"
  return 0
}
