#!/usr/bin/env bash
# run.sh for s15-project (S15, BUILD_SPEC.md section 5 and 14.9, M21): the editable project, the last stage of a format. No model call.
# It reads timeline/timeline.json (the single input index), the stable editor copy's capabilities.json (else baseline-capabilities.json),
# and writes runs/<run>/s15-project/: project/ (a Shorts Editor project folder: project.json, media/, fonts/, layers.json, FALLBACKS.md,
# OPEN.txt), layers.json (the capture), editor.json (the summary the export step reads). It never changes the MP4. A failure (a forced one
# with REELS_S15_FAIL=full, an error, the editor.cap_minutes cap) writes the minimal project or project/FAILED.md and a NEEDS REVIEW flag, and
# the stage still ends with exit 0: the export goes on in every case (pipeline/lib/s15/run.py).
#   bash pipeline/stages/s15-project/run.sh <run_dir>                      (started by the runner)
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
source "$LIB/heavy.sh"

stage_begin "${1:?usage: run.sh <run_dir>}" s15-project editor.json
[ -f "$RUN_DIR/timeline/timeline.json" ] || stage_fail "timeline/timeline.json is missing: the timeline stage did not run"
ENABLED="$(cfg editor.project true)"
if [ "$ENABLED" = false ] || [ "$ENABLED" = False ]; then
  printf '%s\n' '{"written_by": "s15-project", "level": "off", "native": 0, "sprites": 0, "overlays": 0, "plates": 0, "baked_captions": 0, "layers": 0, "baked": 0, "captions_native": false, "checks": [], "needs_review": [], "gaps": {}, "manifest": {"source": "", "hash": "", "schemaVersion": 0}}' > "$OUT/editor.json"
  mkdir -p "$OUT/project"
  echo "$STAGE: editor.project is false, no project written"
  exit 0
fi
set_activity "building editable project"
printf 'activity: building editable project\n'
STABLE="$(cfg editor.stable_dir "")"
[ -n "${EDITOR_STABLE_DIR:-}" ] && STABLE="$EDITOR_STABLE_DIR"
ERR_FILE="$OUT/.last-error"; rm -f "$ERR_FILE"
relay() {
  local line rest
  while IFS= read -r line; do
    case "$line" in
      "@@ACTIVITY "*) set_activity "${line#@@ACTIVITY }"; printf 'activity: %s\n' "${line#@@ACTIVITY }" ;;
      "@@SAY "*) rest="${line#@@SAY }"; printf '%s\n' "${rest#* }" ;;
      "@@FLAG "*) flag_once "${line#@@FLAG }" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done
}
ARGS=(run --run-dir "$RUN_DIR")
[ -n "$STABLE" ] && [ -d "$STABLE" ] && ARGS+=(--stable-dir "$STABLE")
[ -n "${REELS_S15_MANIFEST:-}" ] && ARGS+=(--manifest "$REELS_S15_MANIFEST")
[ -n "${REELS_S15_NO_PARITY:-}" ] && ARGS+=(--no-parity)
set -o pipefail
heavy_run render "S15 project" -- editor_run "S15 editor copy" -- "$REELS_PY" "$LIB/s15" "${ARGS[@]}" 2>&1 | relay
rc=${PIPESTATUS[0]}
set +o pipefail
[ "$rc" = 0 ] || stage_fail "S15 stopped with exit $rc (see stage.log)"
[ -f "$OUT/editor.json" ] || stage_fail "S15 wrote no editor.json"
# every NEEDS REVIEW reason the project gave goes to the idea's flags (the export carries them)
"$REELS_PY" - "$OUT/editor.json" <<'PY' | while IFS= read -r reason; do flag_once "$reason"; done
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for r in d.get("needs_review", []):
    print(str(r).replace(chr(0x2014), "-"))
PY
echo "$STAGE: done"
exit 0
