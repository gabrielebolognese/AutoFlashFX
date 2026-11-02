#!/usr/bin/env bash
# M13: one idea of pipeline/tests/fixtures/ideas/three-ideas.txt again, alone, after a fix (the /init idea after
# DECISIONS.md 283 into build/M13/rerun, the ffmpeg idea after 284 and 286 into build/M13/rerun3).
#   bash build/M13/rerun-idea.sh <text in the idea> <out dir under build/M13>
# Started detached (PowerShell Start-Process), so it outlives one tool call. Writes the out dir (run.out, the sandbox
# path in sandbox.txt) and ends run.out with "exit <rc>".
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
export KEEP_SANDBOX=1
source pipeline/tests/lib.sh
trap - EXIT
PATTERN="${1:-/init}"; OUT="$REPO_DIR/build/M13/${2:-rerun}"
mkdir -p "$OUT"
sandbox_init --with-review
fake_claude_off
export REELS_SFX_DIR="$(mixed "$REPO_DIR/styles/sfx")" REELS_SFX_NO_BUILD=1
grep -v '^#' "$FIXTURES/ideas/three-ideas.txt" | grep -m1 -F -- "$PATTERN" > "$SANDBOX/ideas.txt"
printf '%s\n' "$SANDBOX_M" > "$OUT/sandbox.txt"
{
  echo "started $(date '+%Y-%m-%d %H:%M:%S') in $SANDBOX_M"
  ( cd "$SANDBOX" && env NO_COLOR=1 timeout 21600 bash "$SANDBOX/run.sh" --once )
  echo "exit $?"
  echo "ended $(date '+%Y-%m-%d %H:%M:%S')"
} > "$OUT/run.out" 2>&1
