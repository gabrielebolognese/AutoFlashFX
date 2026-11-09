# pipeline/lib/dummy.sh: shared helper for every pipeline/stages/<stage>/dummy.sh (fast tests, no model calls).
# A dummy stage sources common.sh, log.sh, config.sh, state.sh and status.sh itself, then calls:
#
#   dummy_begin <run_dir> <stage> <primary output>   sets RUN_DIR, STAGE, OUT (the stage folder), RUN_ID, PRIMARY;
#                                                    sleeps REELS_DUMMY_SECONDS (default 1); fires the planted
#                                                    behaviors below; then returns so the stage writes its outputs
#   dummy_end                                        corrupts the primary output when REELS_DUMMY_INVALID lists the
#                                                    stage (exercises the validation path), then logs "done"
#
# Planted behaviors (each a comma list of stage keys, or "all"):
#   REELS_DUMMY_HEAVY=08-voiceover,13-render   the stage's sleep runs inside heavy_run (the global heavy lock); with REELS_HEAVY_TRACE=<file>
#                                 every such step appends "<epoch> start|end <channel> dummy <stage>" lines (test-m19 section 4)
#   REELS_DUMMY_FAIL=10-build     exit 1 without outputs (a code error)
#   REELS_DUMMY_DROP=03-gate      write result.json with a reason and exit 10 (drop the idea)
#   REELS_DUMMY_BLOCK=07-script   write result.json with a reason and exit 20 (block the idea)
#   REELS_DUMMY_FLAG=07-script    record a NEEDS REVIEW flag (prints the FLAG line) and continue
#   REELS_DUMMY_INVALID=05-hooks  write an output that fails its schema (exit 0)
# REELS_DUMMY_ONCE_FILE=<path>: when set, a planted FAIL, DROP or BLOCK fires only once per kind: the first time it
# creates <path>.fail, <path>.drop or <path>.block and later runs (a restart, the next idea) go through normally.

dummy_listed() {  # dummy_listed "<comma list>" -> 0 when STAGE (or all) is in it
  case ",${1:-}," in *",$STAGE,"*|*",all,"*) return 0 ;; esac
  return 1
}

dummy_once_ok() {  # dummy_once_ok <kind> -> 0 when the planted behavior should fire
  [ -z "${REELS_DUMMY_ONCE_FILE:-}" ] && return 0
  [ -e "$REELS_DUMMY_ONCE_FILE.$1" ] && return 1
  : > "$REELS_DUMMY_ONCE_FILE.$1"
  return 0
}

dummy_heavy_sleep() {  # the body of a heavy dummy step: REELS_HEAVY_TRACE (a file) gets "<epoch> start|end <channel> <label>" lines
  local secs="$1"
  heavy_trace start
  sleep "$secs"
  heavy_trace end
}

heavy_trace() {  # heavy_trace start|end: one line in REELS_HEAVY_TRACE
  [ -n "${REELS_HEAVY_TRACE:-}" ] || return 0
  printf '%s %s %s dummy %s\n' "$("$REELS_PY" -c 'import time; print("%.3f" % time.time())')" "$1" "${REELS_CHANNEL:--}" "$STAGE" >> "$REELS_HEAVY_TRACE"
}

dummy_begin() {
  RUN_DIR="$1"; STAGE="$2"; PRIMARY="$3"
  OUT="$RUN_DIR/$STAGE"
  mkdir -p "$OUT"
  RUN_ID="$(basename "$RUN_DIR")"
  DUMMY_INVALID=0
  local secs="${REELS_DUMMY_SECONDS:-1}"
  echo "dummy $STAGE: start (pid $$, sleep ${secs}s)"
  if dummy_listed "${REELS_DUMMY_HEAVY:-}"; then   # a heavy dummy stage: its sleep runs inside heavy_run (M19: the tests of the heavy lock)
    declare -F heavy_run >/dev/null 2>&1 || source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/heavy.sh"
    heavy_run render "dummy $STAGE" -- dummy_heavy_sleep "$secs"
  else
    sleep "$secs"
  fi
  if dummy_listed "${REELS_DUMMY_FAIL:-}" && dummy_once_ok fail; then
    echo "dummy $STAGE: planted failure (REELS_DUMMY_FAIL)" >&2
    echo "Traceback (planted): ValueError: dummy $STAGE failed on purpose" >&2
    exit 1
  fi
  if dummy_listed "${REELS_DUMMY_DROP:-}" && dummy_once_ok drop; then
    printf '{"reason": "facts do not hold (dummy %s)", "detail": "planted by REELS_DUMMY_DROP", "scores": {"P": 1, "S": 1, "C": 1, "F": "fail"}}\n' \
      "$STAGE" > "$OUT/result.json"
    exit 10
  fi
  if dummy_listed "${REELS_DUMMY_BLOCK:-}" && dummy_once_ok block; then
    printf '{"reason": "needs a key only the user has (dummy %s)", "detail": "planted by REELS_DUMMY_BLOCK"}\n' \
      "$STAGE" > "$OUT/result.json"
    exit 20
  fi
  if dummy_listed "${REELS_DUMMY_FLAG:-}"; then
    run_flag "$RUN_DIR" "$STAGE" "dummy soft check failed in $STAGE"
  fi
  if dummy_listed "${REELS_DUMMY_INVALID:-}"; then DUMMY_INVALID=1; fi
}

dummy_end() {
  if [ "${DUMMY_INVALID:-0}" = 1 ]; then
    printf '{"invalid": true, "planted": "REELS_DUMMY_INVALID"}\n' > "$OUT/$PRIMARY"
    echo "dummy $STAGE: wrote an invalid $PRIMARY on purpose"
  fi
  echo "dummy $STAGE: done"
}
