# pipeline/lib/ideas.sh: bash access to the idea queue (wraps ideas.py). Source common.sh (and config.sh) first.
#
#   ideas_count                      number of ideas in ideas.txt
#   ideas_list                       one line per idea: id <TAB> normalized text
#   ideas_first [--plain]            the first idea as JSON (id, text, raw, queue); exit 3 when the queue is empty
#   ideas_id "<text>"                the id of a text
#   ideas_append "<text>" [source]   append every {block} of the text (JSON result); records logs/.new-ideas
#   ideas_remove <id> [original text]   remove that idea; with the text, an idea edited meanwhile is matched at
#                                    similarity 0.9 or more; otherwise the file is left alone (exit 3)
#
# Every write goes through the lock .locks/ideas with the stale timeout runner.lock_stale_seconds (60 s).

ideas_py() { "$REELS_PY" "$REELS_PIPELINE/lib/ideas.py" "$@"; }

ideas_stale() {
  if [ -z "${REELS_LOCK_STALE:-}" ]; then
    if declare -F cfg >/dev/null 2>&1; then
      REELS_LOCK_STALE="$(cfg runner.lock_stale_seconds 60 2>/dev/null || echo 60)"
    else
      REELS_LOCK_STALE=60
    fi
  fi
  printf '%s' "$REELS_LOCK_STALE"
}

ideas_count() { ideas_py count --file "$REELS_IDEAS"; }
ideas_list()  { ideas_py list --file "$REELS_IDEAS" --plain; }
ideas_first() { ideas_py first --file "$REELS_IDEAS" "$@"; }
ideas_id()    { printf '%s' "$1" | ideas_py id; }

ideas_append() {
  printf '%s' "$1" | ideas_py append --file "$REELS_IDEAS" --root "$REELS_CHANNEL_ROOT" --stale "$(ideas_stale)" \
    --source "${2:-runner}"
}

ideas_remove() {
  if [ $# -ge 2 ]; then
    printf '%s' "$2" | ideas_py remove --file "$REELS_IDEAS" --root "$REELS_CHANNEL_ROOT" --stale "$(ideas_stale)" \
      --id "$1" --text-stdin
  else
    ideas_py remove --file "$REELS_IDEAS" --root "$REELS_CHANNEL_ROOT" --stale "$(ideas_stale)" --id "$1" </dev/null
  fi
}
