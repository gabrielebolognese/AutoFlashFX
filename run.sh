#!/usr/bin/env bash
# run.sh: the video runner.
#
#   bash run.sh --channel <id>          process the channel's ideas.txt forever (checks for new ideas every 2 minutes
#                                       when it is empty); REELS_CHANNEL=<id> does the same
#   bash run.sh --channel <id> --once   stop when the queue is empty
#   bash run.sh                         without a channel: exit 2 and the list of channels
#   --allow-disabled                    run a channel whose channel.json says "enabled": false (tests and checks)
#
# One runner per channel at a time; runners of different channels may run side by side. Finished reels appear in
# exports/. Stop it with Ctrl+C; restarting resumes the unfinished run.
# Status: channels/<id>/logs/status.txt holds the latest line, channels/<id>/logs/runner.log the whole timeline
# (bash pipeline/bin/runner-status prints both).
#
# Build status: tracked at the top of CLAUDE.md. To exercise the whole loop with dummy stages:
#   REELS_DUMMY=all bash run.sh --once
set -u
REELS_RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REELS_RUN_DIR/pipeline/lib/common.sh"
source "$REELS_PIPELINE/lib/log.sh"
source "$REELS_PIPELINE/lib/config.sh"
source "$REELS_PIPELINE/lib/ideas.sh"
source "$REELS_PIPELINE/lib/preflight.sh"
source "$REELS_PIPELINE/lib/history.sh"
source "$REELS_PIPELINE/lib/state.sh"
source "$REELS_PIPELINE/lib/status.sh"
source "$REELS_PIPELINE/lib/export.sh"
source "$REELS_PIPELINE/lib/ai.sh"
source "$REELS_PIPELINE/lib/review.sh"
source "$REELS_PIPELINE/lib/runner.sh"

ONCE=0
ALLOW_DISABLED=0
want_channel="${REELS_CHANNEL:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --once) ONCE=1 ;;
    --allow-disabled) ALLOW_DISABLED=1 ;;
    --channel) [ $# -ge 2 ] || { echo "run.sh: --channel needs an id" >&2; exit 2; }; want_channel="$2"; shift ;;
    --channel=*) want_channel="${1#--channel=}" ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "run.sh: unknown option '$1' (use --channel <id>, --once, --allow-disabled)" >&2; exit 1 ;;
  esac
  shift
done
export ONCE
if [ -z "$want_channel" ]; then
  echo "run.sh: no channel given. Start one with: bash run.sh --channel <id> [--once]. Channels:" >&2
  reels_channel_list_text >&2
  exit 2
fi
if ! reels_valid_channel_id "$want_channel" || [ ! -f "$REELS_CHANNELS_DIR/$want_channel/channel.json" ]; then
  echo "run.sh: unknown channel '$want_channel'. Channels:" >&2
  reels_channel_list_text >&2
  exit 2
fi
reels_set_channel "$want_channel" || exit 2
if [ "$ALLOW_DISABLED" != 1 ] && [ "$(cfg_channel_enabled)" = false ]; then
  echo "run.sh: channel '$want_channel' is disabled (channel.json: \"enabled\": false). Use --allow-disabled to run it anyway." >&2
  exit 2
fi

runner_main
exit $?
