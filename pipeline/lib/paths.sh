# pipeline/lib/paths.sh: the one module that knows the folder layout (BUILD_SPEC.md 14.5). Sourced by common.sh.
# paths.py gives the same answers (pipeline/tests/test-isolation.sh compares them: `reels_paths_dump` here and
# `python pipeline/lib/paths.py dump` there print the same NAME=value lines).
#
# Inputs (environment): REELS_ROOT (the state root: the repo unless a test points it at a temp folder),
#   REELS_CHANNEL (the channel id, lowercase letters and digits), REELS_GLOBAL_LOCKS (default REELS_ROOT/.locks),
#   REELS_PATH_TRACE=1 (every path chpath resolves is appended to REELS_PATH_TRACE_FILE or stderr).
#
# Exports (the channel ones only while a channel is set):
#   REELS_CHANNELS_DIR   REELS_ROOT/channels
#   REELS_EXPORTS        REELS_ROOT/exports (shared by every channel, section 8)
#   REELS_GLOBAL_LOCKS   REELS_ROOT/.locks (the locks that are not one channel's)
#   REELS_GLOBAL_LOGS    REELS_ROOT/logs (limits.log and engine.log, from M19 on)
#   REELS_CHANNEL_ROOT   REELS_ROOT/channels/<id>
#   REELS_IDEAS REELS_LOGS REELS_LOCKS REELS_RUNS REELS_LIBRARY REELS_STYLES REELS_MOTIONLIB REELS_GOLDEN
#                        the channel's ideas.txt and folders (inside the channel folder; without a channel REELS_LOGS and
#                        REELS_LOCKS are the global folders and REELS_IDEAS is empty)
#
#   chpath <relative>    prints REELS_CHANNEL_ROOT/<relative>; refuses (exit 3) without a channel, a path that
#                        leaves the channel folder and a path inside another channel's folder
#   chcfg <config key>   chpath of the value of a config `paths.*` key (resolved config, config.sh)
#   exportpath <rel>     REELS_EXPORTS/<rel>; refuses another channel's export folder (<other>-N)
#   reels_channel_ids    the ids of the folders in channels/ that hold a channel.json, one per line
#   reels_require_channel   exits 2 with the channel list when no channel is set (tool scripts call it); with exactly
#                        one channel folder and no REELS_CHANNEL it picks that one (tools only: run.sh never guesses)

reels_valid_channel_id() { case "$1" in ''|*[!a-z0-9]*|[0-9]*) return 1 ;; esac; [ "${#1}" -ge 2 ] && [ "${#1}" -le 24 ]; }

reels_channel_ids() {
  local d
  [ -d "$REELS_CHANNELS_DIR" ] || return 0
  for d in "$REELS_CHANNELS_DIR"/*/; do
    [ -f "${d}channel.json" ] && basename "$d"
  done
}

reels_paths_init() {
  REELS_CHANNELS_DIR="$REELS_ROOT/channels"
  REELS_EXPORTS="$REELS_ROOT/exports"
  REELS_GLOBAL_LOCKS="${REELS_GLOBAL_LOCKS:-$REELS_ROOT/.locks}"
  REELS_GLOBAL_LOGS="$REELS_ROOT/logs"
  if [ -n "${REELS_CHANNEL:-}" ]; then
    if ! reels_valid_channel_id "$REELS_CHANNEL"; then
      echo "paths: '$REELS_CHANNEL' is not a channel id (lowercase letters and digits, 2 to 24, starting with a letter)" >&2
      return 3
    fi
    REELS_CHANNEL_ROOT="$REELS_CHANNELS_DIR/$REELS_CHANNEL"
    REELS_IDEAS="$REELS_CHANNEL_ROOT/ideas.txt"
    REELS_LOGS="$REELS_CHANNEL_ROOT/logs"
    REELS_LOCKS="$REELS_CHANNEL_ROOT/.locks"
    REELS_RUNS="$REELS_CHANNEL_ROOT/runs"
    REELS_LIBRARY="$REELS_CHANNEL_ROOT/library"
    REELS_STYLES="$REELS_CHANNEL_ROOT/styles"
    REELS_MOTIONLIB="$REELS_CHANNEL_ROOT/motion-lib"
    REELS_GOLDEN="$REELS_CHANNEL_ROOT/golden"
  else
    REELS_CHANNEL_ROOT=""
    REELS_IDEAS=""
    REELS_LOGS="$REELS_GLOBAL_LOGS"
    REELS_LOCKS="$REELS_GLOBAL_LOCKS"
    REELS_RUNS=""
    REELS_LIBRARY=""; REELS_STYLES=""; REELS_MOTIONLIB=""; REELS_GOLDEN=""
  fi
  export REELS_CHANNELS_DIR REELS_EXPORTS REELS_GLOBAL_LOCKS REELS_GLOBAL_LOGS REELS_CHANNEL_ROOT \
    REELS_IDEAS REELS_LOGS REELS_LOCKS REELS_RUNS REELS_LIBRARY REELS_STYLES REELS_MOTIONLIB REELS_GOLDEN
  [ -n "${REELS_CHANNEL:-}" ] && export REELS_CHANNEL
  return 0
}

reels_channel_list_text() {  # one line per channel: id, name, platform, format, enabled (read with a small Python, no cfg)
  "$REELS_PY" "$REELS_PIPELINE/lib/paths.py" list 2>/dev/null
}

reels_require_channel() {
  if [ -z "${REELS_CHANNEL:-}" ]; then
    local ids n
    ids="$(reels_channel_ids)"; n="$(printf '%s' "$ids" | grep -c . || true)"
    if [ "$n" = 1 ]; then
      REELS_CHANNEL="$ids"; reels_paths_init || return 3
      return 0
    fi
    echo "no channel given: set REELS_CHANNEL=<id> (or pass --channel <id> where the script takes it). Channels:" >&2
    reels_channel_list_text >&2
    exit 2
  fi
  [ -f "$REELS_CHANNEL_ROOT/channel.json" ] || { echo "unknown channel '$REELS_CHANNEL' (no $REELS_CHANNEL_ROOT/channel.json). Channels:" >&2; reels_channel_list_text >&2; exit 2; }
  return 0
}

reels_path_refuse() {  # reels_path_refuse <absolute path>: exit 3 for another channel's folder or export folder
  local p="$1" rest other
  case "$p" in
    "$REELS_CHANNELS_DIR"/*)
      rest="${p#"$REELS_CHANNELS_DIR"/}"; other="${rest%%/*}"
      if [ -n "${REELS_CHANNEL:-}" ] && [ "$other" != "$REELS_CHANNEL" ]; then
        echo "ERROR paths: $p is inside channel '$other', and this run belongs to channel '$REELS_CHANNEL' (a channel never reads another channel's folder)" >&2
        return 3
      fi ;;
    "$REELS_EXPORTS"/*)
      rest="${p#"$REELS_EXPORTS"/}"; other="${rest%%/*}"
      case "$other" in
        [a-z]*-[0-9]*)
          other="${other%-*}"
          if [ -n "${REELS_CHANNEL:-}" ] && [ "$other" != "$REELS_CHANNEL" ]; then
            echo "ERROR paths: $p is another channel's export folder ('$other'), and this run belongs to channel '$REELS_CHANNEL'" >&2
            return 3
          fi ;;
      esac ;;
  esac
  return 0
}

reels_path_trace() {
  [ "${REELS_PATH_TRACE:-}" = 1 ] || return 0
  if [ -n "${REELS_PATH_TRACE_FILE:-}" ]; then printf '%s\n' "$1" >> "$REELS_PATH_TRACE_FILE"; else printf 'PATH %s\n' "$1" >&2; fi
}

chpath() {
  local rel="$1" full part
  if [ -z "${REELS_CHANNEL_ROOT:-}" ]; then
    echo "chpath: no channel is set (REELS_CHANNEL), cannot resolve '$rel'" >&2
    return 3
  fi
  case "$rel" in /*|[A-Za-z]:*) echo "chpath: '$rel' is not relative to the channel folder" >&2; return 3 ;; esac
  case "/$rel/" in */../*) echo "chpath: '$rel' leaves the channel folder" >&2; return 3 ;; esac
  rel="${rel#./}"
  if [ -z "$rel" ] || [ "$rel" = . ]; then full="$REELS_CHANNEL_ROOT"; else full="$REELS_CHANNEL_ROOT/$rel"; fi
  reels_path_refuse "$full" || return 3
  reels_path_trace "$full"
  printf '%s' "$full"
}

chcfg() {  # chcfg <config key> [fallback relative path]
  local rel
  rel="$(cfg "$1" ${2:+"$2"})" || return 1
  chpath "$rel"
}

exportpath() {
  local full="$REELS_EXPORTS${1:+/$1}"
  reels_path_refuse "$full" || return 3
  reels_path_trace "$full"
  printf '%s' "$full"
}

reels_paths_dump() {
  local n
  for n in REELS_CHANNELS_DIR REELS_EXPORTS REELS_GLOBAL_LOCKS REELS_GLOBAL_LOGS REELS_CHANNEL_ROOT REELS_IDEAS \
           REELS_LOGS REELS_LOCKS REELS_RUNS REELS_LIBRARY REELS_STYLES REELS_MOTIONLIB REELS_GOLDEN; do
    printf '%s=%s\n' "$n" "${!n}"
  done
}
