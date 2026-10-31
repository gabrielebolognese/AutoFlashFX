#!/usr/bin/env bash
# Test fixture "flaky" (installed by test-m3.sh as pipeline/stages/10-build/run.sh in a sandbox): fails FLAKY_FAILS
# times (default 2) the way an external tool fails, then writes a valid events.json. The runner must classify the
# failure (BUILD_SPEC.md section 4: usage limit, transient, code error) instead of sending it to the reviewer.
# FLAKY_MODE: reset (a network reset on stderr, transient), limit (a usage limit message, waited out), error (a
# code error). The attempt counter is <run_dir>/10-build/.flaky-count. Usage: run.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
RUN_DIR="${1:?usage: run.sh <run_dir>}"
OUT="$RUN_DIR/10-build"
mkdir -p "$OUT"
n=0
[ -f "$OUT/.flaky-count" ] && read -r n < "$OUT/.flaky-count"
n=$((n + 1))
printf '%s\n' "$n" > "$OUT/.flaky-count"
echo "stage: attempt $n, fetching the reference clip"
if [ "$n" -le "${FLAKY_FAILS:-2}" ]; then
  case "${FLAKY_MODE:-reset}" in
    limit)
      echo "You've hit your session limit · resets 3pm" >&2
      ;;
    error)
      echo "ValueError: the reference clip has no frames (planted)" >&2
      ;;
    *)
      echo "TypeError: fetch failed" >&2
      echo "    cause: Error: read ECONNRESET (network reset while downloading)" >&2
      ;;
  esac
  exit 1
fi
echo "stage: fetched, building events.json"
cat > "$OUT/events.json" <<JSON
{"composition": "project/index.html", "duration_ms": 30000,
 "events": [{"ms": 0, "type": "hook_hit", "component": "hero-card", "scene": "s1", "scene_change": false, "transition_ms": 0}]}
JSON
echo "stage: done"
