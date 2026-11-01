#!/usr/bin/env bash
# run.sh for 09c-transitions (Visual plan, transitions pass, S9c): BUILD_SPEC.md section 5, S9 9c. A fresh
# visual_director session gets the scene list (from the animations and text passes) and the style's transition
# rules (tokens.json transitions: an animated exit then the next scene enters; fade-blur, fall, push or cut), and
# answers with how each scene leaves. pipeline/lib/visual/plan9.py gives every transition the style's duration,
# writes 09c-transitions/plan.json and the merged plan (merged.json, pipeline/stages/09-plan/schema.json), and the
# validator checks every rule of BUILD_SPEC.md S9 on the whole. One retry with the exact errors, then the review
# path. The shared body is pipeline/lib/visual.sh.
#   bash pipeline/stages/09c-transitions/run.sh <run_dir>                (started by the runner)
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
source "$LIB/visual.sh"
visual_pass_run "${1:?usage: run.sh <run_dir>}" 09c-transitions transitions "planning transitions"
