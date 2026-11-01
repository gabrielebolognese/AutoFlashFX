# pipeline/lib/session.sh: model sessions shared by several stages (BUILD_SPEC.md section 3: session A is S1,
# S2, S4 and S5, continued with --resume, so the hooks are chosen with the research in context). Source common.sh,
# log.sh, config.sh, state.sh, status.sh and ai.sh first.
#
#   session_call <key> <role> <stage_dir> <prompt_file> [ai options...]
#       ai() with --session KEY (the session id lives in state.json sessions.KEY, stored by ai() after a success).
#       When the stored session no longer exists (ai() returns 3: the CLI lost it, the machine changed, the
#       session store was cleaned), the same call is made once more in a new session whose prompt starts with the
#       run's memory (session_seed: the idea, facts.md, expansion.md and the latest gate feedback) and then the
#       original prompt; the new id is stored under the same key. Sets the AI_* variables like ai(); returns ai()'s
#       code (never 3).
#   session_seed <run_dir>          print the seed text (a markdown section per file that exists)
#   session_forget <run_dir> <key>  forget the stored session, so the next call starts a new one

[ -n "${REELS_SESSION_LOADED:-}" ] && return 0
REELS_SESSION_LOADED=1

session_seed() {
  local run_dir="$1" idea gate
  idea="$(state_get "$run_dir" idea.text "" 2>/dev/null)"
  echo "# Context: this session continues earlier work whose transcript is no longer available"
  echo
  echo "You worked on this idea in an earlier session (research, then the expansion). That session cannot be resumed,"
  echo "so here is everything it established. Treat it as your own earlier work: do not redo it unless the task below"
  echo "asks you to, and keep every fact, source and decision consistent with it."
  echo
  echo "## The idea"
  echo
  printf '%s\n\n' "$(undash "$idea")"
  if [ -f "$run_dir/01-research/facts.md" ]; then
    echo "## facts.md (the research, every claim with its source)"; echo
    tr -d '\r' < "$run_dir/01-research/facts.md"; echo
  fi
  if [ -f "$run_dir/02-expansion/expansion.md" ]; then
    echo "## expansion.md (the current expansion)"; echo
    tr -d '\r' < "$run_dir/02-expansion/expansion.md"; echo
  fi
  if [ -f "$run_dir/03-gate/gate.json" ]; then
    gate="$(cat "$run_dir/03-gate/gate.json")"
    echo "## The latest gate verdict (03-gate/gate.json)"; echo
    echo "- round: $(json_field "$gate" round "?")"
    echo "- scores: P $(json_field "$gate" scores.P "?"), S $(json_field "$gate" scores.S "?"), C $(json_field "$gate" scores.C "?"), F $(json_field "$gate" F "?")"
    echo "- decision: $(json_field "$gate" decision "?")"
    echo "- reason: $(undash "$(json_field "$gate" reason "")")"
    echo "- evidence P: $(undash "$(json_field "$gate" evidence.P "")")"
    echo "- evidence S: $(undash "$(json_field "$gate" evidence.S "")")"
    echo "- evidence C: $(undash "$(json_field "$gate" evidence.C "")")"
    echo "- evidence F: $(undash "$(json_field "$gate" evidence.F "")")"
    echo "- angle hint: $(undash "$(json_field "$gate" angle_hint "")")"
    echo
  fi
  echo "# The task"
  echo
}

session_forget() {
  state_set "$1" "sessions.$2=null" >/dev/null 2>&1 || true
}

session_call() {
  local key="$1" role="$2" stage_dir="$3" prompt="$4" rc seed run_dir n
  shift 4
  ai "$role" "$stage_dir" "$prompt" --session "$key" "$@"; rc=$?
  [ "$rc" = 3 ] || return $rc
  run_dir="$(dirname "$stage_dir")"
  mkdir -p "$stage_dir/calls"
  n="$(ai_next_number "$stage_dir/calls")"
  seed="$stage_dir/calls/$n-reseed.prompt.md"
  {
    # the prompt's header lines (# Role:, # Stage:) stay first, then the memory, then the task itself
    grep -E '^# (Role|Stage): ' "$prompt" | head -n 2
    echo
    session_seed "$run_dir"
    grep -v -E '^# (Role|Stage): ' "$prompt" | tr -d '\r'
  } > "$seed"
  say WARN "session $key no longer exists ($(undash "${AI_ERROR:-no detail}")): starting a new one seeded with facts.md, expansion.md and the latest gate feedback"
  session_forget "$run_dir" "$key"
  ai "$role" "$stage_dir" "$seed" --session "$key" "$@"; rc=$?
  [ "$rc" = 3 ] && rc=1   # a brand new session cannot be missing; treat a second 3 as a code error
  return $rc
}
