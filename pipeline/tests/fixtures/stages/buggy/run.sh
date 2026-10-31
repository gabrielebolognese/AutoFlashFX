#!/usr/bin/env bash
# Test fixture "buggy" (installed by test-m3.sh as pipeline/stages/10-build/run.sh in a sandbox copy of the repo):
# builds 10-build/events.json from 07-script/script.json with helper.py. helper.py carries a planted bug (a wrong
# key) that the reviewer can find from the traceback and the fixer can repair. Usage: run.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
RUN_DIR="${1:?usage: run.sh <run_dir>}"
OUT="$RUN_DIR/10-build"
mkdir -p "$OUT"
echo "10-build: building events.json from 07-script/script.json"
set_activity "building visuals"
"$REELS_PY" "$(dirname "${BASH_SOURCE[0]}")/helper.py" "$RUN_DIR/07-script/script.json" "$OUT/events.json" || exit 1
mkdir -p "$OUT/project" "$OUT/hook2"
printf '<!-- composition -->\n' > "$OUT/project/index.html"
printf '<!-- hook 2 clip -->\n' > "$OUT/hook2/index.html"
printf 'draft (test fixture)\n' > "$OUT/draft.mp4"
echo "10-build: done"
