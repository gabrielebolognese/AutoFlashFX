# pipeline/lib/common.sh: shared setup for every runner script. Source it first.
#
# Sets and exports:
#   REELS_REPO      the folder that holds run.sh (resolved from this file's location, never from the environment)
#   REELS_ROOT      the state root: ideas.txt, runs/, exports/, logs/, .locks/, library/ (default: REELS_REPO;
#                   tests point it at a temporary folder)
#   REELS_PIPELINE  REELS_REPO/pipeline
#   REELS_CONFIG    REELS_ROOT/config.json when it exists, else REELS_REPO/config.json
#   REELS_IDEAS, REELS_LOGS, REELS_LOCKS   files and folders under REELS_ROOT
#   REELS_PY        the Python interpreter: python (3.13). Never python3, the Windows Store stub.
#
# Paths are exported in mixed form (C:/Users/...). Git Bash converts command-line arguments that look like POSIX
# paths before a Windows program sees them, but it does not convert environment variables, so /c/... in a variable
# would break every Python helper. cygpath -m gives a form both sides accept.

[ -n "${REELS_COMMON_LOADED:-}" ] && return 0
REELS_COMMON_LOADED=1

export PYTHONUTF8=1
export LANG="${LANG:-C.UTF-8}"

reels_mixed() {
  # Print a path in mixed form (C:/...) when cygpath exists; unchanged elsewhere.
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi
}

_reels_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REELS_REPO="$(reels_mixed "$(cd "$_reels_lib_dir/../.." && pwd)")"
unset _reels_lib_dir

if [ -n "${REELS_ROOT:-}" ]; then
  mkdir -p "$REELS_ROOT" 2>/dev/null || true
  REELS_ROOT="$(reels_mixed "$(cd "$REELS_ROOT" && pwd)")"
else
  REELS_ROOT="$REELS_REPO"
fi

REELS_PIPELINE="$REELS_REPO/pipeline"
if [ -f "$REELS_ROOT/config.json" ]; then
  REELS_CONFIG="$REELS_ROOT/config.json"
else
  REELS_CONFIG="$REELS_REPO/config.json"
fi
REELS_IDEAS="$REELS_ROOT/ideas.txt"
REELS_LOGS="$REELS_ROOT/logs"
REELS_LOCKS="$REELS_ROOT/.locks"
REELS_PY="${REELS_PY:-python}"

export REELS_REPO REELS_ROOT REELS_PIPELINE REELS_CONFIG REELS_IDEAS REELS_LOGS REELS_LOCKS REELS_PY
