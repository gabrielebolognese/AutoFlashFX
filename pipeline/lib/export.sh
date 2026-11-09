# pipeline/lib/export.sh: the export step (BUILD_SPEC.md section 8), wrapping export.py. Source common.sh,
# config.sh and ideas.sh first.
#
#   export_run <run_dir>     number, assemble runs/<run>/export/ and move it into exports/<id>-N/ in one step (BUILD_SPEC.md section 8),
#                            under the global lock .locks/exports (the numbering of every channel shares exports/); prints JSON
#                            {number, name, dir, already}. Exit 0 ok, 99 planted crash (REELS_CRASH_AT), 2 missing files, 4 lock
#                            timeout. stderr goes to <run_dir>/export.err.
#   export_next_number       the number the channel's next export would get (from exports/ and the channel's history.txt)
#   export_name <N>          <id>-N, the folder and file stem of export N of this channel

export_run() {
  local run_dir="$1" crash="${REELS_CRASH_AT:-}"
  "$REELS_PY" "$REELS_PIPELINE/lib/export.py" run --run-dir "$run_dir" \
    --exports "$REELS_EXPORTS" --root "$REELS_CHANNEL_ROOT" --channel "$REELS_CHANNEL" --history "$REELS_LOGS/history.txt" --locks-dir "$REELS_GLOBAL_LOCKS" --stale "$(ideas_stale)" \
    ${crash:+--crash-at "$crash"} 2>"$run_dir/export.err"
}

export_next_number() {
  "$REELS_PY" "$REELS_PIPELINE/lib/export.py" next-number --exports "$REELS_EXPORTS" --channel "$REELS_CHANNEL" --history "$REELS_LOGS/history.txt"
}

export_name() {
  printf '%s-%s' "$REELS_CHANNEL" "$1"
}
