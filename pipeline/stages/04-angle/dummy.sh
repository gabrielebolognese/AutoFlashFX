#!/usr/bin/env bash
# dummy.sh for 04-angle (Angle research, S4): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/04-angle/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 04-angle angle.json
cat > "$OUT/angle.json" <<'JSON'
{"round": 1, "previous_scores": {"P": 1, "S": 1, "C": 2}, "change": "dummy angle: sharper identity in the share line",
 "keeps_core_topic": true}
JSON
[ -f "$RUN_DIR/02-expansion/expansion.md" ] && echo "Angle round 1 (dummy): sharper identity in the share line." >> "$RUN_DIR/02-expansion/expansion.md"
dummy_end
