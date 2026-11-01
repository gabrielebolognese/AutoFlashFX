# pipeline/lib/log.sh: terminal and log lines (BUILD_SPEC.md section 6). Source common.sh first.
#
#   say TAG text...        print "[HH:MM] TAG    text" (tag padded to 6), append it to logs/runner.log and
#                          overwrite logs/status.txt with it (every tag except the ones in REELS_STATUS_SKIP_TAGS,
#                          default "QUEUE INFO": listings and chatter never replace the status line)
#   fmt_dur SECONDS        2m51s, 45s, 1h02m
#   fmt_min SECONDS        "31 min" (or "43s" under a minute), for the DONE line
#   cut_text TEXT [N]      the text cut at N characters (default 40) with "..." when it was longer
#   plural N word          word or words
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
