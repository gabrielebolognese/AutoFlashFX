#!/usr/bin/env bash
# Test fixture "flaky" (installed by test-m3.sh as pipeline/stages/10-build/run.sh in a sandbox): fails FLAKY_FAILS
# times (default 2) the way an external tool fails, then writes a valid events.json. The runner must classify the
# failure (BUILD_SPEC.md section 4: usage limit, transient, code error) instead of sending it to the reviewer.
# FLAKY_MODE: reset (a network reset on stderr, transient), limit (a usage limit message, waited out), limit-new (a
# limit message with a different reset time at every attempt), quoted-limit (a log line that quotes a usage limit,
# then a JSONDecodeError traceback: the text is not a limit), traceback (a KeyError traceback whose frames echo a
# source line with timeout=600: a code error, not a timeout), netdash (the Claude CLI's network message on this PC,
# with its em dash: transient, and the dash must reach no line or file the runner composes), error (a code error).
# The attempt counter is <run_dir>/10-build/.flaky-count. Usage: run.sh <run_dir>
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
    limit-new)   # a different reset time each attempt (a limit hit again after a genuine reset would read like this)
      echo "You've hit your session limit · resets $((n + 2))pm" >&2
      ;;
    quoted-limit)   # a log line that quotes a usage limit, then a real exception (M3 review 2, fix 1)
      echo "step 1: wrote facts.md (the source says Claude Code hit its usage limit, it resets weekly)"
      cat >&2 <<'TRACE'
Traceback (most recent call last):
  File "C:/x/pipeline/stages/10-build/helper.py", line 12, in <module>
    data = json.loads(raw)
  File "C:/Python313/Lib/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
TRACE
      ;;
    traceback)   # a code error whose traceback echoes a source line with "timeout=600" (M3 review 2, fix 2)
      cat >&2 <<'TRACE'
Traceback (most recent call last):
  File "C:/x/pipeline/stages/10-build/helper.py", line 12, in <module>
    r = subprocess.run(cmd, check=True, timeout=600)
  File "C:/x/pipeline/stages/10-build/helper.py", line 20, in build
    beats = plan["beatz"]
KeyError: 'beatz'
TRACE
      ;;
    netdash)   # the CLI's wording with a real U+2014, built from its bytes so this file holds none (M3 review 3, fix 2)
      printf "API Error: Can't reach the API server \xe2\x80\x94 check your internet or DNS (ENOTFOUND)\n" >&2
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
