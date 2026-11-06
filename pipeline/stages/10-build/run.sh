#!/usr/bin/env bash
# run.sh for 10-build (Build visuals and draft render, S10): BUILD_SPEC.md section 5, S10. The merged plan of the three
# S9 passes is compiled into a HyperFrames project built from the motion library (pipeline/lib/visual/project.py over
# pipeline/lib/motion/golden.py: one host per component instance with the plan's props, the caption line, tokens.css,
# the logos as image files with their aspect ratio locked, the transitions as exit props, 3D only where the style
# allows and only when motion-lib/webgl.json says WebGL works, else 2D with a NEEDS REVIEW flag), checked with
# `npx hyperframes check --json`, measured for its sound events (10-build/events.json, every event in absolute ms,
# verified on screen by pipeline/lib/visual/events.py), rendered as a silent draft at 540x960 (draft.mp4: same
# timing and fps; 1080x1920 only in S13), with the hook 2 alternate clip (hook2.mp4, 3.5 s at most) and a contact
# sheet (one still per beat). The builder model (config builder; builder_escalation for 3D-heavy plans or after 2
# failed review rounds) is the repair step: when the check reports errors it edits the project (and only the
# project) until the check passes, up to visual.build_fix_rounds times; still failing is a code error.
# This script relays the Python's progress ("@@ACTIVITY", "@@SAY", "@@FLAG", "@@ERROR" lines) like S8 does.
#   bash pipeline/stages/10-build/run.sh <run_dir>                        (started by the runner)
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

stage_begin "${1:?usage: run.sh <run_dir>}" 10-build events.json
set_activity "building visuals"
for st in 09a-animations 09b-text 09c-transitions; do
  [ -f "$RUN_DIR/$st/plan.json" ] || stage_fail "$st/plan.json is missing: the visual plan stages did not run"
done
command -v ffmpeg >/dev/null 2>&1 || stage_fail "ffmpeg is not on PATH (the draft is downscaled with it)"
command -v ffprobe >/dev/null 2>&1 || stage_fail "ffprobe is not on PATH"
[ -f "$REELS_REPO/node_modules/hyperframes/package.json" ] || stage_fail "node_modules/hyperframes is missing: bash pipeline/bin/setup-node"
export REELS_MOTION_LIB="${REELS_MOTION_LIB:-$(chcfg paths.motion_lib)}"
[ -f "$REELS_MOTION_LIB/catalog.json" ] || stage_fail "$REELS_MOTION_LIB/catalog.json is missing: python pipeline/lib/motion catalog --write"
ERR_FILE="$OUT/.last-error"
rm -f "$ERR_FILE"
PROJECT="$OUT/project"

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
build_step() {  # build_step <step> -> the Python's exit code (0 ok, 5 check errors, 2 render failure, 1 code error)
  local rc
  set -o pipefail
  "$REELS_PY" "$LIB/visual" build --run-dir "$RUN_DIR" --stage-dir "$OUT" --step "$1" 2>&1 | relay
  rc=${PIPESTATUS[0]}
  set +o pipefail
  return $rc
}
last_error() { local msg; msg="$(head -n 1 "$ERR_FILE" 2>/dev/null)"; printf '%s' "${msg:-${1:-the build failed}}"; }

# 1. merge, validate, compile, check
build_step compile; rc=$?
case "$rc" in
  0) ;;
  5)
    # 2. the builder model repairs the project until the check passes (bounded)
    ROUNDS="$(cfg visual.build_fix_rounds 2)"; T_BUILD="$(cfg timeouts.build_seconds 2400)"
    role="$(json_file_field "$OUT/build.json" builder_role builder)"
    r=0
    while [ "$rc" = 5 ] && [ "$r" -lt "$ROUNDS" ]; do
      r=$((r + 1))
      set_activity "building visuals"
      errors_text="$(json_file_field "$OUT/build.json" check_errors '[]' | "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
for e in json.load(sys.stdin): print("- " + str(e))')"
      prompt="$OUT/prompt-repair-r$r.md"
      render_prompt "$HERE/prompt.md" "$prompt" "ROUND=$r" "ROUNDS=$ROUNDS" "PROJECT=$PROJECT" "ERRORS=$errors_text" \
        "SCENES=$("$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
p = json.load(open(sys.argv[1], encoding="utf-8-sig"))
for s in p["scenes"]:
    print(f"- {s[chr(105)+chr(100)]} {s[chr(98)+chr(101)+chr(97)+chr(116)]} ({s[chr(98)+chr(101)+chr(97)+chr(116)+chr(95)+chr(116)+chr(121)+chr(112)+chr(101)]}) {s[chr(115)+chr(116)+chr(97)+chr(114)+chr(116)+chr(95)+chr(109)+chr(115)]}..{s[chr(101)+chr(110)+chr(100)+chr(95)+chr(109)+chr(115)]} ms: " + ", ".join(c["component"] + " (" + c["id"] + ")" for c in s["components"]))' "$OUT/plan.json")" \
        "NOTE=$(stage_note_section)" || stage_fail "cannot render pipeline/stages/10-build/prompt.md"
      say INFO "S10: the check found errors; asking the $role model to repair the project (round $r/$ROUNDS)"
      ai "$role" "$OUT" "$prompt" --tools "Read Glob Grep Edit Write Bash" --allow Read --allow Glob --allow Grep --allow Edit --allow Write \
        --allow "Bash(npx hyperframes *)" --allow "Bash(npx.cmd hyperframes *)" --allow "Bash(ls *)" --allow "Bash(cat *)" \
        --cwd "$PROJECT" --timeout "$T_BUILD" --name "repair-r$r" --activity "building visuals" || stage_ai_failed
      state_set "$RUN_DIR" "rounds.build=$r" >/dev/null 2>&1 || true
      build_step check; rc=$?
    done
    if [ "$rc" = 5 ]; then
      stage_fail "hyperframes check still reports errors after $r builder $(plural "$r" repair): $(json_file_field "$OUT/build.json" check_errors.0 "" | cut -c1-200)"
    fi
    [ "$rc" = 0 ] || stage_fail "$(last_error "the check step failed (exit $rc)")"
    ;;
  *) stage_fail "$(last_error "the compile step failed (exit $rc)")" ;;
esac

# 3. the events, the draft, the hook 2 clip, the contact sheet
build_step finish; rc=$?
case "$rc" in
  0)
    for f in events.json draft.mp4; do [ -f "$OUT/$f" ] || stage_fail "the build finished without writing $f"; done
    echo "$STAGE: done"
    exit 0
    ;;
  *) stage_fail "$(last_error "the finish step failed (exit $rc)")" ;;
esac
