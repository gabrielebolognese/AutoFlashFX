#!/usr/bin/env bash
# run.sh for 08-voiceover (Voiceover, S8): BUILD_SPEC.md section 5, S8. No model of its own; the one line rewrite of
# the ladder goes through pipeline/stages/07-script/run.sh --rewrite-line (the script model).
# The work is done by pipeline/lib/voiceover.py run (Python 3.13): the voice config from library/voice/engine.txt
# (kokoro af_bella, the only engine and voice, never switched), pronunciations.txt applied to the spoken track,
# beat by beat generation with silence tightening in pipeline/lib/tts/kokoro_worker.py under the engine's own
# interpreter (tools/voice.py's Engine class and tighten function), the transcription of every line with
# faster-whisper (pipeline/lib/tts/whisper_worker.py, CPU int8) for the word error rate and the word timestamps,
# the speakability ladder (over 3 percent: the misheard words respelled and the line regenerated; still failing:
# one rewrite through S7 in simpler words and a regeneration; still failing: a NEEDS REVIEW flag at 8 percent or
# less, a block above), the 15 percent overrun check (one rewrite, then a flag), hook 2's voice, the assembly
# (0.05 s lead, 0.1 s between beats, the 1.0 s breath after the hook, 0.2 s tail), loudness (-14 LUFS, true peak at
# most -1.5 dBTP, 48 kHz mono) and words.json (every spoken word with start and end ms and its beat id).
# This script relays the Python's progress to the runner: "@@ACTIVITY text" sets the heartbeat's activity, "@@SAY TAG
# text" prints a terminal line, "@@FLAG text" records a NEEDS REVIEW flag, "@@ERROR text" is the message of a code
# error. Exit 0 done, 20 block (the reason from voiceover.json), 1 a code error (the review and fix loop).
#   bash pipeline/stages/08-voiceover/run.sh <run_dir>                 (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 08-voiceover words.json
set_activity "generating voiceover"
script="$RUN_DIR/07-script/script.json"
[ -f "$script" ] || stage_fail "07-script/script.json is missing: the script stage did not run"
command -v ffmpeg >/dev/null 2>&1 || stage_fail "ffmpeg is not on PATH (the loudness step needs it)"
S7="$REELS_PIPELINE/stages/07-script/run.sh"
[ -f "$S7" ] || stage_fail "pipeline/stages/07-script/run.sh is missing: the ladder's one line rewrite needs it"
ERR_FILE="$OUT/.last-error"
rm -f "$ERR_FILE"

relay() {  # the Python's stdout: relay lines become runner actions, everything else stays in stage.log
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

REELS_BASH="$(reels_mixed "${BASH:-bash}")"; export REELS_BASH   # Git's bash for the S7 rewrite call (a Windows Python's bare `bash` is the WSL launcher)
set -o pipefail
"$REELS_PY" "$LIB/voiceover.py" --config "$REELS_CONFIG" --root "$REELS_CHANNEL_ROOT" --repo "$REELS_REPO" \
  run "$RUN_DIR" --stage-dir "$OUT" --s7 "$S7" 2>&1 | relay
rc=${PIPESTATUS[0]}
set +o pipefail
case "$rc" in
  0)
    [ -f "$OUT/words.json" ] || stage_fail "voiceover.py finished without writing words.json"
    [ -f "$OUT/vo.wav" ] || stage_fail "voiceover.py finished without writing vo.wav"
    echo "$STAGE: done"
    exit 0
    ;;
  20)
    # verdict.json is the small companion of voiceover.json (the trail is too large for a command-line argument)
    reason="$(json_file_field "$OUT/verdict.json" reason "")"
    [ -n "$reason" ] || reason="the voice could not say a line clearly (see 08-voiceover/voiceover.json)"
    stage_block "$reason" "$(json_file_field "$OUT/verdict.json" flags '[]')"
    ;;
  *)
    msg="$(cat "$ERR_FILE" 2>/dev/null | head -n 1)"
    [ -n "$msg" ] || msg="voiceover.py run failed (exit $rc)"
    stage_fail "$msg"
    ;;
esac
