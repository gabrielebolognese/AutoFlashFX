# pipeline/lib/history.sh: logs/history.txt and logs/blocked.txt (BUILD_SPEC.md sections 2.1, 4.2, 4.3).
# Source common.sh first.
#
#   history_add exported "<idea text>" <N>            "date | idea | exported N"   (not repeated for the same N)
#   history_add dropped  "<idea text>" "<reason>"     "date | idea | dropped: reason"
#   history_add blocked  "<idea text>" "<reason>"     "date | idea | blocked: reason"
#   blocked_add "<raw idea>" <stage> "<reason>" <run_dir>   two lines in logs/blocked.txt: a comment with the date,
#                                                     stage, reason and run folder, then the idea in braces, ready to
#                                                     paste into add-idea.sh
#   history_counts [YYYY-MM-DD]                       prints "exported dropped blocked" for that day (default today)
#
# The date is "YYYY-MM-DD HH:MM" in local time. The idea text is the normalized one-line text.

history_file() { printf '%s' "$REELS_LOGS/history.txt"; }

history_add() {
  local kind="$1" idea="$2" detail="$3" stamp line file
  file="$(history_file)"
  mkdir -p "$REELS_LOGS"
  printf -v stamp '%(%Y-%m-%d %H:%M)T' -1
  case "$kind" in
    exported)
      if [ -f "$file" ] && grep -q -F -- "| exported $detail" "$file" 2>/dev/null \
         && grep -F -- "| exported $detail" "$file" | grep -q -F -- "| $idea |"; then
        return 0  # already written (a restart after the export)
      fi
      line="$stamp | $idea | exported $detail" ;;
    dropped) line="$stamp | $idea | dropped: $detail" ;;
    blocked) line="$stamp | $idea | blocked: $detail" ;;
    *) echo "history_add: unknown kind '$kind'" >&2; return 1 ;;
  esac
  printf '%s\n' "$line" >> "$file"
}

blocked_add() {
  local raw="$1" stage="$2" reason="$3" run_dir="${4:-}" stamp rel
  mkdir -p "$REELS_LOGS"
  printf -v stamp '%(%Y-%m-%d %H:%M)T' -1
  rel="${run_dir#"$REELS_ROOT"/}"
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
      if ($0 ~ /\| exported [0-9]+ *$/) e++; else if ($0 ~ /\| dropped: /) d++; else if ($0 ~ /\| blocked: /) b++ }
    END { printf "%d %d %d\n", e, d, b }' "$file"
}
