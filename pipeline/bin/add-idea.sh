#!/usr/bin/env bash
# add-idea.sh: append ideas to ideas.txt through the queue lock. The only supported way to add an idea while
# the runner is running (editing the file by hand can race with the runner's own rewrite).
#
#   bash pipeline/bin/add-idea.sh "{first idea} {second idea}"
#   bash pipeline/bin/add-idea.sh "an idea without braces"        (braces are added for you)
#   echo "{an idea}" | bash pipeline/bin/add-idea.sh
#   bash pipeline/bin/add-idea.sh "{[important] an idea that could blow up}"   (its escalations may use fable)
#
# Prints one line: "added N idea(s) to ideas.txt (queue: M)", plus ", marked important" for a labelled idea
# (DECISIONS.md 323: only those ever use fable). Each addition is also recorded in logs/.new-ideas,
# which the runner reads to print its NEW line.
set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
source "$REELS_PIPELINE/lib/config.sh"
source "$REELS_PIPELINE/lib/ideas.sh"

input=""
if [ $# -gt 0 ]; then
  for arg in "$@"; do
    case "$arg" in
      -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
      *\{*) input="${input}${arg}"$'\n' ;;
      *) input="${input}{${arg}}"$'\n' ;;
    esac
  done
else
  input="$(cat)"
  case "$input" in
    *\{*) ;;
    *) input="{${input}}" ;;
  esac
fi

if [ -z "$(printf '%s' "$input" | tr -d '[:space:]{}')" ]; then
  echo "add-idea: nothing to add. Give the idea in braces as an argument or on stdin." >&2
  exit 1
fi

# The source shows in the runner's NEW line: "Claude Code" when run from a Claude Code session (it sets CLAUDECODE).
source_name="${REELS_SOURCE:-}"
if [ -z "$source_name" ]; then
  if [ -n "${CLAUDECODE:-}" ]; then source_name="Claude Code"; else source_name="add-idea.sh"; fi
fi
printf '%s' "$input" | ideas_py append --file "$REELS_IDEAS" --root "$REELS_ROOT" --stale "$(ideas_stale)" \
  --source "$source_name" --plain
