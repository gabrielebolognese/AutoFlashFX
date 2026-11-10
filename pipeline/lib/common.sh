# pipeline/lib/common.sh: shared setup for every runner script. Source it first.
#
# Sets and exports:
#   REELS_REPO      the folder that holds run.sh (resolved from this file's location, never from the environment)
#   REELS_ROOT      the state root: channels/, exports/, .locks/ (default: REELS_REPO; tests point it at a temporary folder)
#   REELS_PIPELINE  REELS_REPO/pipeline
#   REELS_CHANNEL   the channel id (from the environment; run.sh --channel sets it and calls reels_paths_init)
#   REELS_CONFIG    the resolved config (BUILD_SPEC.md 14.4): without a channel the engine config.json (REELS_ROOT/config.json
#                   when it exists, else REELS_REPO/config.json); with one, REELS_CHANNEL_ROOT/.cache/config.resolved.json,
#                   made by pipeline/lib/config.py from config.json, the format's config and channel.json, and made again
#                   whenever one of them is newer (reels_config_refresh)
#   REELS_CONFIG_ENGINE  the engine config.json
#   REELS_IDEAS, REELS_LOGS, REELS_LOCKS and the channel folders: pipeline/lib/paths.sh (the one module that knows the layout)
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
  REELS_CONFIG_ENGINE="$REELS_ROOT/config.json"
else
  REELS_CONFIG_ENGINE="$REELS_REPO/config.json"
fi
REELS_PY="${REELS_PY:-python}"

export REELS_REPO REELS_ROOT REELS_PIPELINE REELS_CONFIG_ENGINE REELS_PY

source "$REELS_PIPELINE/lib/paths.sh"

reels_config_refresh() {  # make REELS_CONFIG current: the resolved config of the channel, or the engine config without one
  local res src stale=0
  if [ -z "${REELS_CHANNEL:-}" ] || [ ! -f "${REELS_CHANNEL_ROOT:-/nonexistent}/channel.json" ]; then
    REELS_CONFIG="$REELS_CONFIG_ENGINE"; export REELS_CONFIG; return 0
  fi
  res="$REELS_CHANNEL_ROOT/.cache/config.resolved.json"
  if [ ! -s "$res" ]; then stale=1; else
    for src in "$REELS_CONFIG_ENGINE" "$REELS_CHANNEL_ROOT/channel.json" "$REELS_PIPELINE"/formats/*/format.json "$REELS_PIPELINE"/tests/formats/*/format.json "${REELS_FORMATS_DIR:-/nonexistent}"/*/format.json; do
      [ -f "$src" ] && [ "$src" -nt "$res" ] && { stale=1; break; }
    done
  fi
  if [ "$stale" = 1 ]; then
    mkdir -p "$REELS_CHANNEL_ROOT/.cache" 2>/dev/null
    if ! "$REELS_PY" "$REELS_PIPELINE/lib/config.py" resolve --out "$res" 2>/dev/null; then
      REELS_CONFIG="$REELS_CONFIG_ENGINE"; export REELS_CONFIG; return 1
    fi
  fi
  REELS_CONFIG="$res"; export REELS_CONFIG
}

reels_set_channel() {  # reels_set_channel <id>: switch this shell to a channel (run.sh --channel; tools that take --channel)
  REELS_CHANNEL="$1"
  reels_paths_init || return 3
  reels_config_refresh || true
}

reels_paths_init || return 3
reels_config_refresh || true

