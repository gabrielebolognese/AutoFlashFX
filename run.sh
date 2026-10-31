#!/usr/bin/env bash
# run.sh: the video runner.
#
#   bash run.sh          process ideas.txt forever (checks for new ideas every 2 minutes when it is empty)
#   bash run.sh --once   stop when the queue is empty
#
# Finished reels appear in exports/N/. Stop it with Ctrl+C; restarting resumes the unfinished run.
# Status: logs/status.txt holds the latest line, logs/runner.log the whole timeline
# (bash pipeline/bin/runner-status prints both).
#
# Build status: M3 (error system). The loop, the state machine, resume, exports numbering, history, every status
# line, usage limit waits, transient retries and the review and fix loop exist; the real stages arrive from M4 on.
# Until then run it with dummy stages:
#   REELS_DUMMY=all bash run.sh --once
set -u
REELS_RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REELS_RUN_DIR/pipeline/lib/common.sh"
source "$REELS_PIPELINE/lib/log.sh"
source "$REELS_PIPELINE/lib/config.sh"
source "$REELS_PIPELINE/lib/ideas.sh"
source "$REELS_PIPELINE/lib/preflight.sh"
source "$REELS_PIPELINE/lib/history.sh"
source "$REELS_PIPELINE/lib/state.sh"
source "$REELS_PIPELINE/lib/status.sh"
source "$REELS_PIPELINE/lib/export.sh"
source "$REELS_PIPELINE/lib/ai.sh"
source "$REELS_PIPELINE/lib/review.sh"
source "$REELS_PIPELINE/lib/runner.sh"

ONCE=0
for arg in "$@"; do
  case "$arg" in
    --once) ONCE=1 ;;
    -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "run.sh: unknown option '$arg' (use --once or no option)" >&2; exit 1 ;;
  esac
done
export ONCE

runner_main
exit $?
