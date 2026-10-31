#!/usr/bin/env bash
# dummy.sh for 08-voiceover (Voiceover, S8): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/08-voiceover/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 08-voiceover words.json
for i in 1 2 3; do set_activity "generating voiceover (beat $i/3)"; sleep 0.1; done
set_activity "aligning words"
cat > "$OUT/words.json" <<'JSON'
{"engine": "dummy", "sample_rate": 48000, "duration_ms": 30000,
 "words": [{"word": "Your", "start_ms": 0, "end_ms": 250, "beat": "b1"}, {"word": "AI", "start_ms": 260, "end_ms": 500, "beat": "b1"},
           {"word": "site", "start_ms": 510, "end_ms": 800, "beat": "b1"}, {"word": "looks", "start_ms": 810, "end_ms": 1100, "beat": "b1"},
           {"word": "fake", "start_ms": 1110, "end_ms": 1500, "beat": "b1"}, {"word": "Comment", "start_ms": 27000, "end_ms": 27500, "beat": "b6"},
           {"word": "SKILL", "start_ms": 27510, "end_ms": 28000, "beat": "b6"}]}
JSON
cat > "$OUT/words_hook2.json" <<'JSON'
{"engine": "dummy", "sample_rate": 48000, "duration_ms": 2400,
 "words": [{"word": "Install", "start_ms": 0, "end_ms": 400, "beat": "hook2"}, {"word": "this", "start_ms": 410, "end_ms": 600, "beat": "hook2"}]}
JSON
printf 'dummy wav (no audio) for %s\n' "$RUN_ID" > "$OUT/vo.wav"
printf 'dummy wav (no audio) hook 2 for %s\n' "$RUN_ID" > "$OUT/vo_hook2.wav"
dummy_end
