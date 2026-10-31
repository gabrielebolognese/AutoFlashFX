#!/usr/bin/env bash
# dummy.sh for 11-sfx (Sound effects, S11): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/11-sfx/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 11-sfx cues.json
set_activity "adding sound effects (2 sounds)"
cat > "$OUT/cues.json" <<'JSON'
{"seed": 4242,
 "cues": [{"event": 0, "cue_type": "hook_hit", "file": "dummy/hook.wav", "ms": 0, "gain_db": -6},
          {"event": 2, "cue_type": "notification", "file": "dummy/ding.wav", "ms": 27000, "gain_db": -10}],
 "verification": {"accuracy": "pass", "loudness": "pass", "lufs": -14.0, "true_peak_dbtp": -1.6}}
JSON
printf '0.000  hook_hit      dummy/hook.wav   hero-card enters (s1)\n27.000 notification  dummy/ding.wav   dm-card enters (s3)\n' > "$OUT/sound-map.txt"
printf 'dummy wav stem for %s\n' "$RUN_ID" > "$OUT/sfx_stem.wav"
printf 'dummy mp4 (mixed draft) for %s\n' "$RUN_ID" > "$OUT/draft_mixed.mp4"
dummy_end
