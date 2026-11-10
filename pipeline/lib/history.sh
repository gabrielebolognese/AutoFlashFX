# pipeline/lib/history.sh: logs/history.txt and logs/blocked.txt (BUILD_SPEC.md sections 2.1, 4.2, 4.3).
# Source common.sh first.
#
#   history_add exported "<idea text>" <id>-N [solution]     "date | idea | solution | exported <id>-N"  (not repeated for the same name; M19)
#   history_add dropped  "<idea text>" "<reason>" [solution] "date | idea | solution | dropped: reason"
#   history_add blocked  "<idea text>" "<reason>" [solution] "date | idea | solution | blocked: reason"
#     solution (M12, BUILD_SPEC.md 4.3) is the reel's solution type (one lowercase word, for example external or method), or "-" when the
#     idea ended before S2 chose one (the default); S2 reads the recent lines to keep the balance target
#   blocked_add "<raw idea>" <stage> "<reason>" <run_dir>   two lines in logs/blocked.txt: a comment with the date,
#                                                     stage, reason and run folder, then the idea in braces, ready to
#                                                     paste into add-idea.sh
#   history_counts [YYYY-MM-DD]                       prints "exported dropped blocked" for that day (default today)
#
# The date is "YYYY-MM-DD HH:MM" in local time. The idea text is the normalized one-line text. Every field is
# cleaned of em dashes before it is written (reels_undash, log.sh): a reason may quote a CLI message or a model's
# words, and no file of this project may hold one (BUILD_SPEC.md 0.7).

declare -F reels_undash >/dev/null 2>&1 || source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/log.sh"

history_file() { printf '%s' "$REELS_LOGS/history.txt"; }

history_add() {
  local kind="$1" idea="$2" detail="$3" solution="${4:--}" stamp line file
  reels_undash idea; reels_undash detail
  case "$solution" in ""|*[!a-z0-9_-]*) solution="-" ;; esac
  file="$(history_file)"
  mkdir -p "$REELS_LOGS"
  printf -v stamp '%(%Y-%m-%d %H:%M)T' -1
  case "$kind" in
    exported)
      if [ -f "$file" ] && grep -F -- "| $idea |" "$file" 2>/dev/null | grep -q -E -- "[|] exported ${detail} *$"; then
        return 0  # already written (a restart after the export)
      fi
      line="$stamp | $idea | $solution | exported $detail" ;;
    dropped) line="$stamp | $idea | $solution | dropped: $detail" ;;
    blocked) line="$stamp | $idea | $solution | blocked: $detail" ;;
    *) echo "history_add: unknown kind '$kind'" >&2; return 1 ;;
  esac
  printf '%s\n' "$line" >> "$file"
}

history_solution() {  # history_solution <run_dir>: the run's solution type for the history line (- before S2 decided)
  local t
  t="$("$REELS_PY" "$REELS_PIPELINE/lib/solution.py" type --run-dir "$1" 2>/dev/null | tr -d '\r')"
  printf '%s' "${t:--}"
}

blocked_add() {
  local raw="$1" stage="$2" reason="$3" run_dir="${4:-}" stamp rel
  reels_undash raw; reels_undash reason
  mkdir -p "$REELS_LOGS"
  printf -v stamp '%(%Y-%m-%d %H:%M)T' -1
  rel="${run_dir#"$REELS_CHANNEL_ROOT"/}"
  {
    printf '# %s | blocked at %s | %s%s\n' "$stamp" "$stage" "$reason" "${rel:+ | $rel}"
    printf '{%s}\n' "$raw"
  } >> "$REELS_LOGS/blocked.txt"
}

history_counts() {
  local day="${1:-}" file
  [ -n "$day" ] || printf -v day '%(%Y-%m-%d)T' -1
  file="$(history_file)"
  if [ ! -f "$file" ]; then printf '0 0 0\n'; return 0; fi
  awk -v day="$day" 'index($0, day) == 1 {
      if ($0 ~ /\| exported ([a-z][a-z0-9]*-)?[0-9]+ *$/) e++; else if ($0 ~ /\| dropped: /) d++; else if ($0 ~ /\| blocked: /) b++ }
    END { printf "%d %d %d\n", e, d, b }' "$file"
}
