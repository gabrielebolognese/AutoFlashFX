#!/usr/bin/env bash
# run.sh for 11-sfx (Sound effects, S11): BUILD_SPEC.md section 5, S11. No model. The sound effects memory map is
# refreshed first (bash pipeline/bin/build-sfx-map: a no-op when styles/sfx/ and overrides.txt are unchanged; its one
# indexer call failing is a code error; a missing pack folder means the voice alone plus a NEEDS REVIEW flag), then
# pipeline/lib/sfx/mixsfx.py does the pass: cue types for 10-build/events.json by the spec's rules (seeded per reel),
# files from the map's pools in rotation (logs/sfx-usage.json keeps the last reels' picks), placement by peak or onset,
# levels under the voice, the stem and the mix rendered, then verified (every sound within one frame of its event, no
# unplanned sound, the 8 dB rule, -14 LUFS plus or minus 1, at most -1.5 dBTP), corrected and verified again; still
# failing is a code error (the review path of BUILD_SPEC.md 4.2). Outputs: cues.json (primary), sfx_stem.wav, mix.wav,
# draft_mixed.mp4, sound-map.txt, and the hook 2 clip's cues_hook2 inside cues.json with sfx_stem_hook2.wav and
# mix_hook2.wav. This script relays the Python's progress lines ("@@ACTIVITY", "@@SAY", "@@FLAG", "@@ERROR") like S8.
#   bash pipeline/stages/11-sfx/run.sh <run_dir>                        (started by the runner)
# Environment: REELS_SFX_DIR (another pack folder, tests), REELS_SFX_NO_BUILD=1 (skip the map refresh, tests).
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

stage_begin "${1:?usage: run.sh <run_dir>}" 11-sfx cues.json
set_activity "adding sound effects"
printf 'activity: adding sound effects\n'
for f in 10-build/events.json 10-build/plan.json 10-build/draft.mp4 08-voiceover/vo.wav 08-voiceover/words.json; do
  [ -f "$RUN_DIR/$f" ] || stage_fail "$f is missing: the stage that writes it did not run"
done
command -v ffmpeg >/dev/null 2>&1 || stage_fail "ffmpeg is not on PATH (the mix is rendered with it)"
export REELS_SFX_DIR="${REELS_SFX_DIR:-$(chcfg paths.sfx_dir)}"
export REELS_MOTION_LIB="${REELS_MOTION_LIB:-$(chcfg paths.motion_lib)}"

# 1. the memory map, refreshed (BUILD_SPEC.md 2.6 item 9; the contract of this stage)
if [ "${REELS_SFX_NO_BUILD:-0}" != 1 ]; then
  if [ -d "$REELS_SFX_DIR" ]; then
    set_activity "adding sound effects (checking the sound map)"
    bash "$REELS_PIPELINE/bin/build-sfx-map" --quiet --dir "$REELS_SFX_DIR"; rc=$?
    case "$rc" in
      0) ;;
      1) stage_fail "build-sfx-map: the indexer call failed (see $REELS_LOGS/build-sfx-map/calls/)" ;;
      *) printf 'build-sfx-map exited %s: going on with the map as it is\n' "$rc" ;;
    esac
  else
    printf 'the sound pack folder %s is missing: the voice alone (the stage flags it)\n' "$REELS_SFX_DIR"
  fi
fi

# 2. the pass
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
"$REELS_PY" "$LIB/sfx/mixsfx.py" run --run-dir "$RUN_DIR" --stage-dir "$OUT" 2>&1 | relay
rc=${PIPESTATUS[0]}
set +o pipefail
last_error() { local msg; msg="$(head -n 1 "$ERR_FILE" 2>/dev/null)"; printf '%s' "${msg:-${1:-the sound pass failed}}"; }
case "$rc" in
  0)
    for f in cues.json sfx_stem.wav mix.wav draft_mixed.mp4 sound-map.txt; do [ -f "$OUT/$f" ] || stage_fail "the sound pass finished without writing $f"; done
    echo "$STAGE: done"
    exit 0
    ;;
  3) stage_fail "$(last_error "the sound verification still fails after the corrections")" ;;
  *) stage_fail "$(last_error "the sound pass failed (exit $rc)")" ;;
esac
