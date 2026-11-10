#!/usr/bin/env bash
# run.sh for timeline (M20, BUILD_SPEC.md 14.8): the final video as layers in time. No model. For a generated format
# (format.json timeline.builder = composition) it writes runs/<run>/timeline/timeline.json from the plans, words.json, cues.json and
# the composition S13 rendered (pipeline/lib/timeline/compose.py), then checks it against them (check.py): the duration within 1 frame
# of final.mp4, every word, every sound, every composition layer. A failed check is a code error (the review and fix path).
# A format of the footage family writes timeline.json in its cut stage and has no stage of this name.
#   bash pipeline/stages/timeline/run.sh <run_dir>                         (started by the runner)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$(cd "$HERE/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/ai.sh"
source "$LIB/session.sh"
source "$LIB/stage.sh"

stage_begin "${1:?usage: run.sh <run_dir>}" timeline timeline.json
set_activity "building timeline"
printf 'activity: building timeline\n'
FORMAT="$("$REELS_PY" "$LIB/formats.py" of-channel 2>/dev/null)"
BUILDER="$("$REELS_PY" "$LIB/formats.py" get timeline.builder --format "$FORMAT" 2>/dev/null)"
[ -n "$BUILDER" ] || BUILDER=composition
[ "$BUILDER" = composition ] || stage_fail "format $FORMAT has timeline.builder '$BUILDER': only 'composition' is built by this stage (a cut format writes timeline.json in its cut stage)"
ERR_FILE="$OUT/.last-error"; rm -f "$ERR_FILE"
relay() {
  local line rest tag
  while IFS= read -r line; do
    case "$line" in
      "@@ACTIVITY "*) set_activity "${line#@@ACTIVITY }"; printf 'activity: %s\n' "${line#@@ACTIVITY }" ;;
      "@@SAY "*) rest="${line#@@SAY }"; tag="${rest%% *}"; printf '%s\n' "${rest#* }" ;;
      "@@FLAG "*) flag_once "${line#@@FLAG }" ;;
      "@@ERROR "*) printf '%s\n' "${line#@@ERROR }" > "$ERR_FILE"; printf '%s\n' "$line" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done
}
set -o pipefail
"$REELS_PY" "$LIB/timeline" build --run-dir "$RUN_DIR" --out "$OUT/timeline.json" --format "$FORMAT" --channel "${REELS_CHANNEL:-}" 2>&1 | relay
rc=${PIPESTATUS[0]}
set +o pipefail
last_error() { local msg; msg="$(head -n 1 "$ERR_FILE" 2>/dev/null)"; printf '%s' "${msg:-${1:-the timeline failed}}"; }
[ "$rc" = 0 ] || stage_fail "$(last_error "building the timeline failed (exit $rc)")"
"$REELS_PY" "$LIB/timeline" check --run-dir "$RUN_DIR" --json "$OUT/check.json" > "$OUT/check.txt" 2>&1; rc=$?
cat "$OUT/check.txt"
if [ "$rc" != 0 ]; then
  stage_fail "the timeline does not match what it describes: $(grep '^FAIL' "$OUT/check.txt" | head -n 2 | tr '\n' ' ')"
fi
echo "$STAGE: done"
exit 0
