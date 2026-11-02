#!/usr/bin/env bash
# M12: test-m12 section 4 (the real end to end run, 1 to 3 hours) started detached, so it outlives one tool call.
#   bash build/M12/run-s4.sh      writes build/M12/test-m12-s4.log, ends with "exit <rc>"
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
LOG=build/M12/test-m12-s4.log
{
  echo "started $(date '+%Y-%m-%d %H:%M:%S')"
  for t in claude ffmpeg ffprobe node python git; do printf '%s: %s\n' "$t" "$(command -v "$t" || echo MISSING)"; done
  M12_SECTIONS="4" bash pipeline/tests/test-m12.sh
  echo "exit $?"
  echo "ended $(date '+%Y-%m-%d %H:%M:%S')"
} > "$LOG" 2>&1
