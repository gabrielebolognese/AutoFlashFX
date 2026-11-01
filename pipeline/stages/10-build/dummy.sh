#!/usr/bin/env bash
# dummy.sh for 10-build (Build visuals and draft render, S10): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls, no render. Usage: bash pipeline/stages/10-build/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 10-build events.json
cat > "$OUT/events.json" <<'JSON'
{"written_by": "10-build (dummy)", "composition": "project/index.html", "duration_ms": 30000, "fps": 30,
 "counts": {"enter": 2, "scene_change": 2, "notification": 1},
 "verified": {"checked": 3, "changed": 3, "failed": []},
 "timeline_check": {"ok": true, "clips": 4, "mismatches": []},
 "harness_errors": [],
 "events": [{"ms": 0, "frame": 0, "type": "enter", "cue": "hero_enter", "component": "headline", "instance": "s1-headline-1", "scene": "s1", "beat": "b1", "el": "hl-lines", "scene_change": false, "transition_ms": 0, "verified": true},
            {"ms": 1500, "frame": 45, "type": "scene_change", "cue": "transition", "component": "scene", "instance": null, "scene": "s2", "beat": "b2", "from_scene": "s1", "el": null, "scene_change": true, "transition_ms": 133, "transition_type": "fade-blur", "next_beat_type": "stake", "verified": true},
            {"ms": 1500, "frame": 45, "type": "enter", "cue": "hero_enter", "component": "card", "instance": "s2-card-1", "scene": "s2", "beat": "b2", "el": "card-box", "scene_change": false, "transition_ms": 0, "verified": true},
            {"ms": 27000, "frame": 810, "type": "scene_change", "cue": "transition", "component": "scene", "instance": null, "scene": "s3", "beat": "b6", "from_scene": "s2", "el": null, "scene_change": true, "transition_ms": 333, "transition_type": "fall", "next_beat_type": "ask", "verified": true},
            {"ms": 27267, "frame": 818, "type": "notification", "cue": "notification", "component": "dm-card", "instance": "s3-dm-card-2", "scene": "s3", "beat": "b6", "el": "dm", "scene_change": false, "transition_ms": 0, "verified": true}]}
JSON
mkdir -p "$OUT/project" "$OUT/hook2"
printf '<!-- dummy composition for %s -->\n' "$RUN_ID" > "$OUT/project/index.html"
printf '<!-- dummy hook 2 clip for %s -->\n' "$RUN_ID" > "$OUT/hook2/index.html"
printf 'dummy mp4 (silent draft) for %s\n' "$RUN_ID" > "$OUT/draft.mp4"
printf 'dummy mp4 (hook 2 clip) for %s\n' "$RUN_ID" > "$OUT/hook2.mp4"
printf '{"written_by": "10-build (dummy)", "builder_role": "builder", "check_ok": true, "webgl": true}\n' > "$OUT/build.json"
dummy_end
