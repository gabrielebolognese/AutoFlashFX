# pipeline/lib/export.sh: the export step (BUILD_SPEC.md section 8), wrapping export.py. Source common.sh,
# config.sh and ideas.sh first.
#
#   export_run <run_dir>     number, assemble runs/<id>/export/ and move it into exports/N/ in one step, under the
#                            lock .locks/exports; prints JSON {number, dir, already}. Exit 0 ok, 99 planted crash
#                            (REELS_CRASH_AT), 2 missing files, 4 lock timeout. stderr goes to <run_dir>/export.err.
#   export_next_number       the number the next export would get (tests)

export_run() {
  local run_dir="$1" crash="${REELS_CRASH_AT:-}"
  "$REELS_PY" "$REELS_PIPELINE/lib/export.py" run --run-dir "$run_dir" \
    --exports "${REELS_EXPORTS:-$REELS_ROOT/exports}" --root "$REELS_ROOT" --stale "$(ideas_stale)" \
    ${crash:+--crash-at "$crash"} 2>"$run_dir/export.err"
}

export_next_number() {
  "$REELS_PY" "$REELS_PIPELINE/lib/export.py" next-number --exports "${REELS_EXPORTS:-$REELS_ROOT/exports}"
}
