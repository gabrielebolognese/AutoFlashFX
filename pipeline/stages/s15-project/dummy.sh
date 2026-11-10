#!/usr/bin/env bash
# dummy.sh for s15-project (M21): a minimal valid editor.json and an empty project folder, for fast tests of the runner. No model calls.
# Usage: bash pipeline/stages/s15-project/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" s15-project editor.json
set_activity "building editable project"
mkdir -p "$OUT/project"
cat > "$OUT/project/project.json" <<'JSON'
{"schemaVersion": 3, "id": "dummy", "name": "dummy", "settings": {"width": 1080, "height": 1920, "fps": {"num": 30, "den": 1}, "background": {"r": 0, "g": 0, "b": 0, "a": 1}, "sampleRate": 48000},
 "media": {}, "bins": [], "tracks": [], "clips": {}, "markers": [], "captionTracks": {}, "textPresetsLocal": [], "meta": {"createdAt": "2026-01-01T00:00:00.000Z", "modifiedAt": "2026-01-01T00:00:00.000Z", "appVersion": "1.1.0"}}
JSON
printf 'Dummy project: nothing was mapped.\n' > "$OUT/project/FALLBACKS.md"
printf 'Dummy project.\n' > "$OUT/project/OPEN.txt"
cat > "$OUT/editor.json" <<'JSON'
{"written_by": "s15-project (dummy)", "level": "full", "native": 0, "sprites": 0, "overlays": 0, "plates": 0, "baked_captions": 0, "layers": 0, "baked": 0, "captions_native": false,
 "checks": [], "needs_review": [], "gaps": {}, "manifest": {"source": "dummy", "hash": "dummy", "schemaVersion": 3}}
JSON
dummy_end
