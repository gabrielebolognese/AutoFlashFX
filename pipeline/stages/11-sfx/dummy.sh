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
{"written_by": "11-sfx", "seed": 4242, "round": 0, "counts": {"mandatory": 2},
 "cues": [{"id": "c01", "cue_type": "hook_hit", "group": "mandatory", "priority": 0, "ms": 2400, "file": "dummy/hook.wav", "gain_db": -6, "reel_start_ms": 1900, "offset_ms": 0, "play_ms": 1200,
           "event": {"ms": 2400, "type": "enter", "component": "hero-3d", "instance": "s1-hero-3d-2", "scene": "s1", "beat": "b1", "scene_change": false}},
          {"id": "c02", "cue_type": "notification", "group": "mandatory", "priority": 0, "ms": 27000, "file": "dummy/ding.wav", "gain_db": -10, "reel_start_ms": 26900, "offset_ms": 0, "play_ms": 800,
           "event": {"ms": 27000, "type": "notification", "component": "dm-card", "instance": "s9-dm-card-2", "scene": "s9", "beat": "b9", "scene_change": false}}],
 "dropped": [],
 "verification": {"pass": true, "passes": 1, "accuracy": {"pass": true, "checked": 2, "max_error_ms": 3, "tolerance_ms": 33, "results": [], "unplanned": []},
                  "voice_rule": {"pass": true, "min_margin_db": 9.1, "results": []}, "loudness": {"pass": true, "lufs": -14.0, "true_peak_dbtp": -1.6}, "corrections": []},
 "files": {"stem": "sfx_stem.wav", "mix": "mix.wav", "draft_mixed": "draft_mixed.mp4", "sound_map": "sound-map.txt"}, "hook2": null}
JSON
printf '0.000  hook_hit      dummy/hook.wav   hero-card enters (s1)\n27.000 notification  dummy/ding.wav   dm-card enters (s3)\n' > "$OUT/sound-map.txt"
printf 'dummy wav stem for %s\n' "$RUN_ID" > "$OUT/sfx_stem.wav"
printf 'dummy mp4 (mixed draft) for %s\n' "$RUN_ID" > "$OUT/draft_mixed.mp4"
dummy_end
