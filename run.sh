#!/usr/bin/env bash
# run.sh: the video runner.
#
#   bash run.sh          process ideas.txt forever (checks for new ideas every 2 minutes when it is empty)
#   bash run.sh --once   stop when the queue is empty
#
# Finished reels appear in exports/N/. Stop it with Ctrl+C; restarting resumes the unfinished run.
# Status: logs/status.txt holds the latest line, logs/runner.log the whole timeline.
#
# Build status: M1 (skeleton). This version runs the preflight, prints the banner and the queue, then exits.
# The processing loop (BUILD_SPEC.md section 3) arrives in M2.
set -u
REELS_RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REELS_RUN_DIR/pipeline/lib/common.sh"
source "$REELS_PIPELINE/lib/log.sh"
source "$REELS_PIPELINE/lib/config.sh"
source "$REELS_PIPELINE/lib/ideas.sh"
source "$REELS_PIPELINE/lib/preflight.sh"

ONCE=0
for arg in "$@"; do
  case "$arg" in
    --once) ONCE=1 ;;
    -h|--help) sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "run.sh: unknown option '$arg' (use --once or no option)" >&2; exit 1 ;;
  esac
done

mkdir -p "$REELS_ROOT/runs" "$REELS_ROOT/exports" "$REELS_LOGS" "$REELS_LOCKS"
[ -f "$REELS_IDEAS" ] || : > "$REELS_IDEAS"

preflight_run || exit $?

plural() { if [ "$1" = "1" ]; then printf '%s' "$2"; else printf '%ss' "$2"; fi; }

runner_banner() {
  local version style primary fallback queue sfx_map sfx_count="not built" sha=""
  version="$(cfg version 0.0.0)"
  style="$(cfg style paper-cards)"
  primary="$(cfg tts.primary unknown)"
  fallback="$(cfg tts.fallback none)"
  queue="$(ideas_count)"
  sfx_map="$REELS_REPO/$(cfg sfx.map styles/sfx/sfx-map.json)"
  if [ -f "$sfx_map" ]; then
    sfx_count="$("$REELS_PY" -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(len(m.get("files", [])), "files")' "$sfx_map" 2>/dev/null || echo "unreadable")"
  fi
  sha="$(git -C "$REELS_REPO" rev-parse --short HEAD 2>/dev/null || true)"
  say START "reels autopilot v${version}${sha:+ (${sha})} | queue: $queue $(plural "$queue" idea) | style: $style | voice: $primary (fallback $fallback) | sfx map: $sfx_count"
  say INFO "root: $REELS_ROOT | mode: $([ "$ONCE" = 1 ] && echo "once" || echo "forever")"
  if [ "$queue" -gt 0 ]; then
    local n=0 id text
    while IFS=$'\t' read -r id text; do
      n=$((n + 1))
      if [ ${#text} -gt 60 ]; then text="${text:0:60}..."; fi
      say QUEUE "$n. $text"
      [ "$n" -ge 10 ] && { [ "$queue" -gt 10 ] && say QUEUE "... and $((queue - 10)) more"; break; }
    done < <(ideas_list)
  fi
}

runner_banner
say INFO "the processing loop arrives in M2: nothing to do yet"
exit 0
