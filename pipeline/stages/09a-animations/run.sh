#!/usr/bin/env bash
# run.sh for 09a-animations (Visual plan, animations pass, S9a): BUILD_SPEC.md section 5, S9 9a. A fresh
# visual_director session gets the script and the voice's word times, the motion library's catalog, the golden
# reel, the research screenshots, the style files and the branding rules that follow the reel's solution, and
# answers with one scene per beat: the components, their props and the spoken word each one lands on.
# pipeline/lib/visual/plan9.py composes 09a-animations/plan.json from it (every time snapped to words.json, the
# hook's set piece in the breath, the CTA's FlashFX DM card and lockup, the brand slot by the solution), and the
# validator (pipeline/lib/visual/plan_validate.py) checks the scenes' rules against tokens.json and catalog.json.
# An answer with problems gets one more call in the same session with the exact errors, then the stage fails
# (the review path). The shared body is pipeline/lib/visual.sh.
#   bash pipeline/stages/09a-animations/run.sh <run_dir>                 (started by the runner)
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
visual_pass_run "${1:?usage: run.sh <run_dir>}" 09a-animations animations "planning animations"
