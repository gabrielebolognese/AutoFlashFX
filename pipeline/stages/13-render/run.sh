#!/usr/bin/env bash
# run.sh for 13-render (Final render, S13): BUILD_SPEC.md section 5, S13. No model. pipeline/lib/finalrender.py renders
# the built composition (10-build/project/) with HyperFrames at 1080x1920, 30 fps as a silent video, muxes the approved
# mix (11-sfx/mix.wav, or the voice alone with a flag) into final.mp4 with ffmpeg as AAC 48 kHz (the video copied, never
# re-encoded unless a check asks for it), then checks it with ffprobe and loudnorm: the size, the rate, h264 High,
# yuv420p, the audio, the duration equal to the voice within 0.2 s, the loudness at -14 LUFS with the true peak under
# -1.5 dBTP. The hook 2 clip (10-build/hook2/ with 11-sfx/mix_hook2.wav) takes the same path, 3.5 s at most. A failed
# check gets one ffmpeg post-pass that fixes only the detail that differs; still failing is a code error (the review and
# fix path). Outputs: render.json (primary), final.mp4, hook2.mp4, video.mp4 (the silent render, kept for a re-mux).
# Relays the Python's progress lines ("@@ACTIVITY", "@@SAY", "@@FLAG", "@@ERROR") like S8, S10 and S11.
#   bash pipeline/stages/13-render/run.sh <run_dir>                        (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 13-render render.json
set_activity "rendering final video"
printf 'activity: rendering final video\n'
for f in 10-build/project/index.html 10-build/plan.json 08-voiceover/vo.wav; do
  [ -f "$RUN_DIR/$f" ] || stage_fail "$f is missing: the stage that writes it did not run"
done
for tool in ffmpeg ffprobe node; do
  command -v "$tool" >/dev/null 2>&1 || stage_fail "$tool is not on PATH (the final render needs HyperFrames and ffmpeg)"
done
export REELS_MOTION_LIB="${REELS_MOTION_LIB:-$(chcfg paths.motion_lib)}"

ERR_FILE="$OUT/.last-error"
rm -f "$ERR_FILE"
relay() {
  local line rest tag
  while IFS= read -r line; do
    case "$line" in
      "@@ACTIVITY "*) set_activity "${line#@@ACTIVITY }"; printf 'activity: %s\n' "${line#@@ACTIVITY }" ;;
      "@@SAY "*) rest="${line#@@SAY }"; tag="${rest%% *}"; say "$tag" "${rest#* }" ;;
      "@@FLAG "*) flag_once "${line#@@FLAG }" ;;
      "@@ERROR "*) printf '%s\n' "${line#@@ERROR }" > "$ERR_FILE"; printf '%s\n' "$line" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done
}
set -o pipefail
heavy_run render "S13 render" -- "$REELS_PY" "$LIB/finalrender.py" run --run-dir "$RUN_DIR" --stage-dir "$OUT" --config "$REELS_CONFIG" 2>&1 | relay
rc=${PIPESTATUS[0]}
set +o pipefail
last_error() { local msg; msg="$(head -n 1 "$ERR_FILE" 2>/dev/null)"; printf '%s' "${msg:-${1:-the final render failed}}"; }
case "$rc" in
  0)
    for f in render.json final.mp4 hook2.mp4; do [ -f "$OUT/$f" ] || stage_fail "the render finished without writing $f"; done
    echo "$STAGE: done"
    exit 0
    ;;
  2) stage_fail "$(last_error "an input of the final render is missing")" ;;
  3) stage_fail "$(last_error "a check of the final render still fails after the post-pass")" ;;
  *) stage_fail "$(last_error "the final render failed (exit $rc)")" ;;
esac
