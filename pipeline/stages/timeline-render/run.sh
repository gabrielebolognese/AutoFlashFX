#!/usr/bin/env bash
# run.sh for timeline-render (M20, BUILD_SPEC.md 14.8): a footage format's final render. No model. Checks the timeline the cut stage wrote
# (pipeline/lib/timeline/check.py), then renders it with ffmpeg (pipeline/lib/timeline/render_ffmpeg.py: trims, joins, burned captions,
# the audio mix and its loudness) into timeline-render/final.mp4, one heavy step (the global heavy lock). Primary output: render.json.
#   bash pipeline/stages/timeline-render/run.sh <run_dir>                  (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" timeline-render render.json
set_activity "rendering timeline"
printf 'activity: rendering timeline\n'
[ -f "$RUN_DIR/timeline/timeline.json" ] || stage_fail "timeline/timeline.json is missing: the cut stage did not write it"
for tool in ffmpeg ffprobe; do command -v "$tool" >/dev/null 2>&1 || stage_fail "$tool is not on PATH"; done
"$REELS_PY" "$LIB/timeline" check --run-dir "$RUN_DIR" --json "$OUT/check.json" > "$OUT/check.txt" 2>&1; rc=$?
cat "$OUT/check.txt"
[ "$rc" = 0 ] || stage_fail "the timeline does not match what it describes: $(grep '^FAIL' "$OUT/check.txt" | head -n 2 | tr '\n' ' ')"
ERR_FILE="$OUT/.last-error"; rm -f "$ERR_FILE"
set -o pipefail
heavy_run encode "timeline render" -- "$REELS_PY" "$LIB/timeline" render --run-dir "$RUN_DIR" --out "$OUT/final.mp4" --work "$OUT/.work" --json "$OUT/render.json" 2>&1 | {
  while IFS= read -r line; do
    case "$line" in
      "@@ACTIVITY "*) set_activity "${line#@@ACTIVITY }" ;;
      "@@SAY "*) rest="${line#@@SAY }"; printf '%s\n' "${rest#* }" ;;
      "@@ERROR "*) printf '%s\n' "${line#@@ERROR }" > "$ERR_FILE"; printf '%s\n' "$line" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done
}
rc=${PIPESTATUS[0]}
set +o pipefail
if [ "$rc" != 0 ]; then
  msg="$(head -n 1 "$ERR_FILE" 2>/dev/null)"
  stage_fail "${msg:-the timeline render failed (exit $rc)}"
fi
[ -f "$OUT/final.mp4" ] && [ -f "$OUT/render.json" ] || stage_fail "the render finished without writing final.mp4 and render.json"
echo "$STAGE: done"
exit 0
