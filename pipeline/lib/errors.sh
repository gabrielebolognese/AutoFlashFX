# pipeline/lib/errors.sh: the error classifier and signatures (BUILD_SPEC.md section 4). Source common.sh and
# config.sh first. The work is in pipeline/lib/errors.py; these wrappers read the config for it.
#
#   error_classify RC STDOUT_FILE STDERR_FILE   prints the JSON of errors.py classify: class (ok, limit, transient,
#                                               error), message, detail, retry_after, session_id, structured, fatal,
#                                               resume_failed, limit {kind, reset, target, when, message}
#   error_signature "<message>"                 the normalized signature (12 hex characters, DECISIONS.md 19)
#   error_backoff N                             the wait before transient retry N (1-based): errors.transient_backoff_seconds
#   error_backoff_count                         how many transient retries there are (the table's length)

error_classify() {
  local tz margin
  tz="$(cfg runner.timezone "" 2>/dev/null)"
  margin="${REELS_LIMIT_MARGIN:-$(cfg runner.limit_margin_seconds 120)}"
  "$REELS_PY" "$REELS_PIPELINE/lib/errors.py" classify --rc "$1" --stdout "$2" --stderr "$3" --tz "$tz" --margin "$margin"
}

error_signature() {
  printf '%s' "$1" | "$REELS_PY" "$REELS_PIPELINE/lib/errors.py" signature --stdin
}

error_backoff_table() {
  if [ -z "${ERROR_BACKOFF_TABLE:-}" ]; then
    ERROR_BACKOFF_TABLE="$(cfg errors.transient_backoff_seconds '[60, 240, 960]' | tr -d '[] ' | tr ',' ' ')"
    [ -n "$ERROR_BACKOFF_TABLE" ] || ERROR_BACKOFF_TABLE="60 240 960"
  fi
  printf '%s' "$ERROR_BACKOFF_TABLE"
}

error_backoff() {  # error_backoff <try> -> seconds
  local n="$1" i=0 v
  for v in $(error_backoff_table); do
    i=$((i + 1))
    [ "$i" = "$n" ] && { printf '%s' "$v"; return 0; }
  done
  printf '%s' "$v"
}

error_backoff_count() {
  local n=0 v
  for v in $(error_backoff_table); do n=$((n + 1)); done
  printf '%s' "$n"
}
