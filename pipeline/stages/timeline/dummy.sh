#!/usr/bin/env bash
# dummy.sh for timeline (M20): a minimal timeline.json that validates against schema.json, for fast tests of the runner. No model calls.
# Usage: bash pipeline/stages/timeline/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" timeline timeline.json
set_activity "building timeline"
cat > "$OUT/timeline.json" <<'JSON'
{"version": 1,
 "settings": {"width": 1080, "height": 1920, "fps": {"num": 30, "den": 1}, "duration_frames": 30, "sample_rate": 48000, "background": "#000000"},
 "sources": [], "layers": [],
 "captions": {"style": "dummy", "chunks": []},
 "audio": {"voice": null, "sfx": [], "footage": [], "music": []},
 "markers": [],
 "provenance": {"written_by": "timeline (dummy)"}}
JSON
dummy_end
