#!/usr/bin/env bash
# run.sh for 09b-text (Visual plan, text pass, S9b): BUILD_SPEC.md section 5, S9 9b. A fresh visual_director session
# gets the animations plan (the instances and their first-draft texts), the script, the voice's words and the
# baseline caption chunks, and answers with the final on-screen texts (6 words or fewer per card), the caption
# chunks (1 to 4 words, the emphasis words) and the labels. pipeline/lib/visual/plan9.py composes 09b-text/plan.json:
# the chunks get their times from words.json (the words and their order never change; a chunk wider than the
# caption line is split), the card texts become prop overrides of the 9a instances, the honesty labels follow the
# props; the validator checks the caption, card and honesty rules. One retry with the exact errors, then the review
# path. The shared body is pipeline/lib/visual.sh.
#   bash pipeline/stages/09b-text/run.sh <run_dir>                       (started by the runner)
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
visual_pass_run "${1:?usage: run.sh <run_dir>}" 09b-text text "planning text"
