#!/usr/bin/env bash
# build-runner.sh: builds the reels autopilot (BUILD_SPEC.md) milestone by milestone, unattended.
#
# Each milestone is a fresh Claude Code session:
#   build batch -> review batch -> (fix batch -> review batch)* until the review approves.
# Reviews escalate from Opus to Fable when problems persist. The runner stops only when a
# milestone is still rejected after every review cycle, or when Claude Code itself cannot run.
#
# Usage (Git Bash, from the instagramReels folder):
#   bash build-runner.sh                 start, or resume where it stopped
#   bash build-runner.sh --from M5       restart from a milestone
#   bash build-runner.sh --review-plan   pause after M0 so you can read PLAN.md
#   bash build-runner.sh --status        print the latest status line and exit
#   bash build-runner.sh --check         check that Claude Code runs with these settings, then exit

set -u

# ---------------------------------------------------------------- settings
SPEC="BUILD_SPEC.md"
BUILD_MODEL="${BUILD_MODEL:-fable}";            BUILD_EFFORT="${BUILD_EFFORT:-max}"
FIX_MODEL="${FIX_MODEL:-fable}";                FIX_EFFORT="${FIX_EFFORT:-max}"
REVIEW_MODEL="${REVIEW_MODEL:-opus}";           REVIEW_EFFORT="${REVIEW_EFFORT:-high}"
ESC_REVIEW_MODEL="${ESC_REVIEW_MODEL:-fable}";  ESC_REVIEW_EFFORT="${ESC_REVIEW_EFFORT:-high}"
PROBE_MODEL="${PROBE_MODEL:-haiku}"
MAX_OPUS_REJECTS="${MAX_OPUS_REJECTS:-3}"       # rejected Opus reviews before escalating
MAX_ESC_REJECTS="${MAX_ESC_REJECTS:-2}"         # rejected Fable reviews before stopping
STATUS_EVERY="${STATUS_EVERY:-300}"             # heartbeat every 5 minutes
LIMIT_MARGIN="${LIMIT_MARGIN:-120}"             # wait 2 minutes past a limit reset
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
# Unattended permissions. If your Claude Code rejects these flags, run with:
#   PERM_FLAGS='--permission-mode acceptEdits --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch' bash build-runner.sh
read -r -a PERM_FLAGS <<< "${PERM_FLAGS:---permission-mode auto --permission-prompts none}"
SLEEP_SCALE="${SLEEP_SCALE:-1}"                 # tests only: 0.001 makes every wait near instant

MS_IDS=(M0 M1 M2 M3 M4 M5 M6 M7 M8 M9 M10 M11 M12 M13)
MS_TITLES=("Plan" "Skeleton" "Runner core and terminal output" "Error system"
           "Research, expansion, gate, angle" "Profile and hooks" "Script" "Voiceover"
           "Sound effects memory map" "Motion library" "Visual stages"
           "Sound effects pass and review loop" "Final render, caption, export, end to end" "Hardening")

BUILD_DIR="build"; STATE="$BUILD_DIR/state.env"; STATUS_FILE="$BUILD_DIR/.status"
LOG="$BUILD_DIR/build.log"; STATUS_TXT="$BUILD_DIR/status.txt"; TODO="$BUILD_DIR/HUMAN_TODO.md"

cd "$(dirname "$0")" || exit 1
mkdir -p "$BUILD_DIR"

# ---------------------------------------------------------------- output
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_G=$'\e[32m'; C_R=$'\e[31m'; C_Y=$'\e[33m'; C_C=$'\e[36m'; C_D=$'\e[90m'; C_0=$'\e[0m'
else
  C_G=""; C_R=""; C_Y=""; C_C=""; C_D=""; C_0=""
fi

say() {  # say TAG message...
  local tag="$1"; shift
  local col="$C_C"
  case "$tag" in
    PASS|DONE) col="$C_G" ;; REJECT|STOP|ERROR) col="$C_R" ;;
    LIMIT|RETRY|ESCAL|HUMAN|WAIT|WARN) col="$C_Y" ;; STATUS) col="$C_D" ;;
  esac
  printf '%s[%s] %-6s%s %s\n' "$col" "$(date +%H:%M)" "$tag" "$C_0" "$*"
  printf '[%s] %-6s %s\n' "$(date '+%F %H:%M')" "$tag" "$*" >> "$LOG"
}

fmt_dur() {  # seconds -> 5h41m / 12m / 40s
  local s=$1
  [ "$s" -lt 0 ] && s=0
  if [ "$s" -ge 3600 ]; then printf '%dh%02dm' $((s/3600)) $(((s%3600)/60))
  elif [ "$s" -ge 60 ]; then printf '%dm' $((s/60))
  else printf '%ds' "$s"; fi
}

# ---------------------------------------------------------------- time (virtual in tests)
VOFF=0
now_epoch() { echo $(( $(date +%s) + VOFF )); }
scaled_sleep() {
  local s=$1
  if [ "$SLEEP_SCALE" = "1" ]; then sleep "$s"
  else sleep "$(awk -v s="$s" -v k="$SLEEP_SCALE" 'BEGIN{printf "%.3f", s*k}')"; VOFF=$((VOFF + s)); fi
}
wait_until() {  # sleep in 60 s chunks so a sleeping PC doesn't break the wait
  local t=$1 left
  while [ "$(now_epoch)" -lt "$t" ]; do
    left=$(( t - $(now_epoch) )); [ "$left" -gt 60 ] && left=60
    scaled_sleep "$left"
  done
}

# ---------------------------------------------------------------- python helper
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done

parse_json() {  # parse_json OUT.json -> prints session id, then is_error; writes OUT.txt with the result text
  "$PY" - "$1" <<'EOF'
import json, sys
path = sys.argv[1]
raw = open(path, encoding="utf-8", errors="replace").read()
obj = None
candidates = [raw] + [l for l in reversed(raw.splitlines()) if l.strip().startswith("{")]
for cand in candidates:
    try:
        obj = json.loads(cand)
        break
    except Exception:
        pass
if not isinstance(obj, dict):
    obj = {}
with open(path[:-5] + ".txt", "w", encoding="utf-8") as f:
    f.write(str(obj.get("result") or ""))
print(obj.get("session_id") or "")
print("true" if obj.get("is_error") else "false")
EOF
}

# ---------------------------------------------------------------- state
MS_INDEX=0; PHASE="build"; REVIEW_N=0; OPUS_REJ=0; ESC_REJ=0; ESCALATED=0; LAST_SIG=""
MS_START_SHA=""; MS_START_EPOCH=0; ISSUES_FOUND=0; ISSUES_FIXED=0; LAST_REJECT_COUNT=0
INTERRUPTED=0; STOPPED=0; TOTAL_START=0; BATCH_N=0

save_state() {
  local k
  { for k in MS_INDEX PHASE REVIEW_N OPUS_REJ ESC_REJ ESCALATED LAST_SIG MS_START_SHA MS_START_EPOCH \
             ISSUES_FOUND ISSUES_FIXED LAST_REJECT_COUNT INTERRUPTED STOPPED TOTAL_START BATCH_N; do
      printf '%s=%q\n' "$k" "${!k}"
    done; } > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
}
load_state() { [ -f "$STATE" ] && source "$STATE"; return 0; }

S_VERB=""; S_DETAIL=""; S_WAIT_UNTIL=""; S_PHASE_START=0
set_phase() {  # set_phase VERB [DETAIL]
  S_VERB="$1"; S_DETAIL="${2:-}"; S_PHASE_START=$(now_epoch); S_WAIT_UNTIL=""; write_status
}
write_status() {
  { printf 'S_MS=%q\nS_TITLE=%q\nS_VERB=%q\nS_DETAIL=%q\nS_WAIT_UNTIL=%q\nS_PHASE_START=%q\n' \
      "${MS_IDS[$MS_INDEX]}" "${MS_TITLES[$MS_INDEX]}" "$S_VERB" "$S_DETAIL" "$S_WAIT_UNTIL" "$S_PHASE_START"
    printf 'S_MS_START=%q\nS_START_SHA=%q\nS_FOUND=%q\nS_FIXED=%q\nS_VOFF=%q\n' \
      "$MS_START_EPOCH" "$MS_START_SHA" "$ISSUES_FOUND" "$ISSUES_FIXED" "$VOFF"; } > "$STATUS_FILE.tmp" \
    && mv "$STATUS_FILE.tmp" "$STATUS_FILE"
}

status_line() {  # the heartbeat text, from the status file
  [ -f "$STATUS_FILE" ] || return 1
  # shellcheck disable=SC1090
  source "$STATUS_FILE"
  local now=$(( $(date +%s) + S_VOFF ))
  local minute=$(( (now - S_MS_START) / 60 ))
  local files commits detail="$S_DETAIL"
  files=$( { git diff --name-only "$S_START_SHA" 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
           | sort -u | grep -v "^$BUILD_DIR/" | grep -c . )
  commits=$(git rev-list --count "$S_START_SHA"..HEAD 2>/dev/null || echo 0)
  if [ -n "$S_WAIT_UNTIL" ]; then
    local left=$(( S_WAIT_UNTIL - now )); [ "$left" -lt 0 ] && left=0
    detail="$detail ($(fmt_dur "$left") left)"
  elif [ -n "$detail" ]; then
    detail="$detail, $(fmt_dur $(( now - S_PHASE_START ))) in this step"
  fi
  printf 'still %s milestone %s "%s" (minute %d)%s | files changed: %d | commits: %d | issues so far: %d (%d fixed)' \
    "$S_VERB" "$S_MS" "$S_TITLE" "$minute" "${detail:+ | $detail}" "$files" "$commits" "$S_FOUND" "$S_FIXED"
}

TICKER_PID=""
start_ticker() {
  (
    trap 'exit 0' TERM
    while true; do
      if [ "$SLEEP_SCALE" = "1" ]; then sleep "$STATUS_EVERY"
      else sleep "$(awk -v s="$STATUS_EVERY" -v k="$SLEEP_SCALE" 'BEGIN{printf "%.3f", s*k}')"; fi
      if line=$(status_line); then
        say STATUS "$line"
        printf '[%s] %s\n' "$(date +%H:%M)" "$line" > "$STATUS_TXT"
      fi
    done
  ) &
  TICKER_PID=$!
}
stop_ticker() { [ -n "$TICKER_PID" ] && kill "$TICKER_PID" 2>/dev/null; TICKER_PID=""; }

on_interrupt() {
  stop_ticker; save_state
  say STOP "interrupted by you. Run bash build-runner.sh again to resume at ${MS_IDS[$MS_INDEX]} ($PHASE)."
  exit 130
}
trap on_interrupt INT TERM
trap stop_ticker EXIT

# ---------------------------------------------------------------- limits and errors
parse_reset_epoch() {  # $1 text -> prints epoch. returns 0 parsed, 2 limit but unparseable, 1 no limit
  local text="$1" line when tz e n
  line=$(printf '%s\n' "$text" | grep -iE "hit your .*limit|limit reached|usage limit|limit.*reset|out of extra usage|try again in [0-9]+ (hour|minute)" | tail -1)
  [ -z "$line" ] && return 1
  if [[ $line =~ \|([0-9]{10}) ]]; then echo "${BASH_REMATCH[1]}"; return 0; fi
  if [[ $line =~ try\ again\ in\ ([0-9]+)\ (hour|minute) ]]; then
    n=${BASH_REMATCH[1]}
    if [ "${BASH_REMATCH[2]}" = "hour" ]; then echo $(( $(date +%s) + n * 3600 )); else echo $(( $(date +%s) + n * 60 )); fi
    return 0
  fi
  when=$(printf '%s' "$line" | sed -nE 's/.*[Rr]esets?( at)? +(([A-Z][a-z]{2},? )?([A-Z][a-z]{2} [0-9]{1,2},? )?[0-9]{1,2}(:[0-9]{2})? ?[apAP][mM]).*/\2/p')
  [ -z "$when" ] && return 2
  when=${when//,/}
  tz=$(printf '%s' "$line" | sed -nE 's/.*\(([A-Za-z_]+\/[A-Za-z_]+|UTC)\).*/\1/p')
  e=""
  if [ -n "$tz" ] && [ -e "/usr/share/zoneinfo/$tz" ]; then e=$(TZ="$tz" date -d "$when" +%s 2>/dev/null); fi
  [ -z "$e" ] && e=$(date -d "$when" +%s 2>/dev/null)
  [ -z "$e" ] && return 2
  n=$(date +%s)
  if [ "$e" -le "$n" ]; then
    if printf '%s' "$when" | grep -qE '^[A-Z][a-z]{2} [0-9]{1,2} '; then e=$(( e + 365 * 86400 ))
    elif printf '%s' "$when" | grep -qE '^[A-Z][a-z]{2} '; then e=$(( e + 7 * 86400 ))
    else e=$(( e + 86400 )); fi
  fi
  echo "$e"
}

is_transient() { printf '%s' "$1" | grep -qiE 'overloaded|"?529"?|internal server error|server_error|ECONNRESET|ETIMEDOUT|EAI_AGAIN|socket hang up|network error|timed out|temporarily unavailable|rate_limit|502 |503 |504 '; }
is_fatal()     { printf '%s' "$1" | grep -qiE 'not logged in|run /login|authentication_failed|invalid api key|unknown option|error: unknown|billing_error|account_on_hold|oauth_org_not_allowed|model_not_found|command not found|is not recognized'; }

wait_limit() {  # wait_limit EPOCH TEXT
  local kind="session" target when prev_verb="$S_VERB" prev_detail="$S_DETAIL"
  printf '%s' "$2" | grep -qi weekly && kind="weekly"
  target=$(( $1 + LIMIT_MARGIN ))
  [ "$SLEEP_SCALE" != "1" ] && target=$(( target - $(date +%s) + $(now_epoch) ))
  when=$(date -d "@$(( target - VOFF ))" '+%a %H:%M' 2>/dev/null || echo "?")
  say LIMIT "$kind limit hit, waiting until $when (reset + $((LIMIT_MARGIN / 60)) min)"
  printf '%s %s limit, waiting until %s\n' "$(date '+%F %T')" "$kind" "$when" >> "$BUILD_DIR/limits.log"
  S_VERB="waiting for usage limit in"; S_DETAIL="$kind limit until $when"; S_WAIT_UNTIL="$target"; write_status
  wait_until "$target"
  say RESUME "limit reset, continuing ${MS_IDS[$MS_INDEX]} ($prev_verb)"
  set_phase "$prev_verb" "$prev_detail"
}

wait_unparsed_limit() {
  local prev_verb="$S_VERB" prev_detail="$S_DETAIL"
  say LIMIT "usage limit hit but no reset time found, checking every 30 minutes"
  S_VERB="waiting for usage limit in"; S_DETAIL="no reset time, probing every 30 min"; write_status
  while true; do
    scaled_sleep 1800
    if "$CLAUDE_BIN" -p "reply ok" --model "$PROBE_MODEL" --output-format json "${PERM_FLAGS[@]}" >/dev/null 2>&1; then break; fi
  done
  say RESUME "limit is over, continuing ${MS_IDS[$MS_INDEX]} ($prev_verb)"
  set_phase "$prev_verb" "$prev_detail"
}

CONTINUE_PROMPT="You were interrupted (usage limit or a temporary error). Continue exactly where you stopped: check git status and the files you were writing, finish the batch, and end with the required result line from the original instructions."

CALL_SID=""; CALL_TXT=""; STOP_REASON=""
call_claude() {  # call_claude MODEL EFFORT PROMPT_FILE OUT_BASE -> 0 when the run completed, 1 when Claude Code cannot run
  local model="$1" effort="$2" pfile="$3" out="$4" sid="" prompt tries=0 unknown=0 rc all epoch lim delay
  prompt=$(cat "$pfile")
  while true; do
    local args=(-p "$prompt" --model "$model" --output-format json "${PERM_FLAGS[@]}")
    [ -n "$effort" ] && args+=(--effort "$effort")
    [ -n "$sid" ] && args+=(--resume "$sid")
    "$CLAUDE_BIN" "${args[@]}" > "$out.json" 2> "$out.err" < /dev/null
    rc=$?
    parse_json "$out.json" > "$out.meta"   # sequential: the result file is complete before we read it
    CALL_SID=$(sed -n '1p' "$out.meta"); local is_err; is_err=$(sed -n '2p' "$out.meta")
    CALL_TXT="$out.txt"
    if [ "$rc" -eq 0 ] && [ "$is_err" != "true" ] && [ -s "$out.txt" ]; then return 0; fi
    all="$(cat "$out.json" "$out.err" 2>/dev/null)"
    epoch=$(parse_reset_epoch "$all"); lim=$?
    if [ "$lim" -eq 0 ]; then wait_limit "$epoch" "$all"
    elif [ "$lim" -eq 2 ]; then wait_unparsed_limit
    elif is_fatal "$all"; then
      STOP_REASON="Claude Code cannot run: $(printf '%s' "$all" | grep -iE 'error|not|unknown|invalid' | head -1 | cut -c1-200)"
      return 1
    elif is_transient "$all" && [ "$tries" -lt 3 ]; then
      tries=$((tries + 1)); delay=$(( 60 * 4 ** (tries - 1) ))
      say RETRY "temporary error ($(printf '%s' "$all" | grep -oiE 'overloaded|529|server_error|timed out|ECONNRESET|rate_limit|50[234]' | head -1)), retrying in $(fmt_dur "$delay") (try $tries/3)"
      local pv="$S_VERB" pd="$S_DETAIL"
      S_VERB="retrying"; S_DETAIL="temporary error, next try in $(fmt_dur "$delay")"; write_status
      scaled_sleep "$delay"; set_phase "$pv" "$pd"
    elif [ "$unknown" -lt 2 ]; then
      unknown=$((unknown + 1))
      say RETRY "the batch ended with an error, retrying (try $unknown/2): $(head -c 160 "$out.txt" "$out.err" 2>/dev/null | tr '\n' ' ')"
      scaled_sleep 60
    else
      STOP_REASON="the batch keeps failing: $(head -c 300 "$out.err" "$out.txt" 2>/dev/null | tr '\n' ' ')"
      return 1
    fi
    if [ -n "$CALL_SID" ]; then sid="$CALL_SID"; prompt="$CONTINUE_PROMPT"; fi
  done
}

result_line() { grep -oE "$2: [A-Z]+.*" "$1" 2>/dev/null | tail -1; }  # result_line FILE KEY

# ---------------------------------------------------------------- prompts
common_rules() {
  cat <<EOF
Rules for every batch:
- Read $SPEC (the full spec), CLAUDE.md, PLAN.md, DECISIONS.md, build/progress.md, build/HUMAN_TODO.md and
  pipeline/knowledge/known-issues.md when they exist. They are the memory between batches.
- Nobody is watching. Never wait for me and never ask questions. When something needs me, use the spec's default,
  keep going, and add a line to build/HUMAN_TODO.md: "- $1: what I need to do, where".
- Never write an em dash in any file.
EOF
  if [ "$INTERRUPTED" = "1" ]; then
    echo "- A previous attempt at this batch was interrupted. Check git status, git log and build/$1/ first, and continue that work instead of starting over."
  fi
}

prompt_build() {
  local id="$1" title="$2"
  cat <<EOF
You are building milestone $id ($title) of the Instagram reels autopilot described in $SPEC.
This is one batch of an automated build: build-runner.sh runs each milestone in a fresh session, then a reviewer checks it.

$(common_rules "$id")

Do:
1. Build only milestone $id as defined in $SPEC section 12 and in PLAN.md. Do not start later milestones.
   Touch earlier milestones only when $id depends on it, and say so in your report.
2. Run the acceptance test for $id until it passes. Also run the earlier milestones' tests listed in build/progress.md.
3. Commit your work with clear messages, for example: feat($id): ...
4. Write build/$id/report.md: what you built, the files, how to run the test, a short summary of the test output,
   known gaps, and the HUMAN_TODO items you added.
5. Update build/progress.md (one section per milestone, including the command that runs its test) and the build status in CLAUDE.md.

End your final message with exactly one of these lines:
MILESTONE_RESULT: DONE
MILESTONE_RESULT: BLOCKED <one-line reason>
Use BLOCKED only for something you truly cannot do without me.
EOF
}

prompt_plan() {
  cat <<EOF
You are starting the automated build of the Instagram reels autopilot described in $SPEC. This batch is milestone M0 (Plan).

$(common_rules M0)

Do:
1. Read $SPEC completely.
2. Write PLAN.md: for every milestone M1 to M13, the files it creates, its acceptance test (exact command), and what it depends on.
3. Write DECISIONS.md with the decisions you already made, and CLAUDE.md as described in $SPEC section 11.
4. Create build/progress.md with an empty section per milestone. Write no pipeline code.
5. Commit: docs(M0): plan.
6. Write build/M0/report.md.

End your final message with exactly one of these lines:
MILESTONE_RESULT: DONE
MILESTONE_RESULT: BLOCKED <one-line reason>
EOF
}

prompt_review() {
  local id="$1" title="$2" n="$3" sha="$4"
  cat <<EOF
You are the reviewer for milestone $id ($title) of the build described in $SPEC. This is review $n.
You did not write this code. Fresh session.

$(common_rules "$id")

Read: the parts of $SPEC that $id touches (section 12 for its scope and test), PLAN.md, build/$id/report.md,
every earlier review and fix file in build/$id/, and everything changed since commit $sha
(git diff $sha..HEAD, git log $sha..HEAD, and new files).

Check:
1. The acceptance test for $id: run it yourself and write a short summary of the output.
2. Spec compliance: everything $SPEC section 12 requires for $id, and the parts of sections 1 to 11 it touches.
3. Robustness: errors handled, Windows Git Bash compatibility (paths, CRLF, GNU date, python versus python3), no
   hardcoded secrets, no em dashes.
4. Nothing broken in earlier milestones: run their tests (the commands are in build/progress.md).

Do not edit code. You may run tests and read anything.
Write build/$id/review-$n.md with: the verdict; "Required fixes" as a numbered list (each with file, problem,
expected behavior, how to verify); "Repeated from earlier review" listing any required fix that an earlier review of
$id already asked for; then optional suggestions (these never cause a rejection).
Approve when the acceptance test passes and there is no required fix. Do not reject for style preferences.
For M0, review PLAN.md against the spec instead of code.

End your final message with exactly one of these lines:
REVIEW_VERDICT: APPROVED
REVIEW_VERDICT: REJECTED <number of required fixes>
REVIEW_VERDICT: REJECTED <number of required fixes> REPEATED   (when any required fix repeats an earlier one)
EOF
}

prompt_fix() {
  local id="$1" title="$2" n="$3"
  cat <<EOF
You are fixing milestone $id ($title) of the build described in $SPEC, after review $n rejected it. Fresh session.

$(common_rules "$id")

Read build/$id/report.md, build/$id/review-$n.md, and the earlier reviews and fix notes in build/$id/.
1. Apply every required fix in review-$n.md. No unrelated changes.
2. Re-run the acceptance test for $id and the earlier milestones' tests.
3. Commit: fix($id): ...
4. Write build/$id/fixes-$n.md: each required fix, what you changed, how you verified it.

End your final message with exactly one of these lines:
FIX_RESULT: DONE
FIX_RESULT: BLOCKED <one-line reason>
EOF
}

# ---------------------------------------------------------------- batches
todo_count() { local n; n=$(grep -c '^- ' "$TODO" 2>/dev/null); echo "${n:-0}"; }

run_batch() {  # run_batch ROLE MODEL EFFORT PROMPT_TEXT -> sets BATCH_TXT
  local role="$1" model="$2" effort="$3" text="$4" id="${MS_IDS[$MS_INDEX]}" dir pfile before after
  dir="$BUILD_DIR/$id/batches"; mkdir -p "$dir"
  BATCH_N=$((BATCH_N + 1)); save_state
  pfile="$dir/$(printf '%02d' "$BATCH_N")-$role.prompt.md"
  printf '%s\n' "$text" > "$pfile"
  before=$(todo_count)
  if ! call_claude "$model" "$effort" "$pfile" "${pfile%.prompt.md}"; then
    stop_build "$STOP_REASON"
  fi
  BATCH_TXT="$CALL_TXT"
  after=$(todo_count)
  if [ "$after" -gt "$before" ]; then say HUMAN "$id added $((after - before)) item(s) to $TODO (total $after)"; fi
}

marked_batch() {  # like run_batch, but marks the batch as in progress so a restart knows it was interrupted
  INTERRUPTED=1; save_state
  run_batch "$@"
  INTERRUPTED=0; save_state
}

stop_build() {
  STOPPED=1; save_state; stop_ticker
  local id="${MS_IDS[$MS_INDEX]}"
  {
    echo "# Build stopped at $id (${MS_TITLES[$MS_INDEX]})"
    echo
    echo "When: $(date '+%F %H:%M')"
    echo "Phase: $PHASE (review $REVIEW_N, $OPUS_REJ rejected by opus, $ESC_REJ rejected by fable)"
    echo
    echo "Reason: $1"
    echo
    echo "Last files: build/$id/ (reports, reviews, fixes, batches)"
    echo
    echo "To continue: fix the problem (or edit $SPEC), then run: bash build-runner.sh"
    echo "It resumes at $id with fresh review counters."
  } > "$BUILD_DIR/STOPPED.md"
  say STOP "$id: $1"
  say STOP "see $BUILD_DIR/STOPPED.md. Run bash build-runner.sh again after fixing to resume at $id."
  exit 1
}

start_milestone() {
  PHASE="build"; REVIEW_N=0; OPUS_REJ=0; ESC_REJ=0; ESCALATED=0; LAST_SIG=""; LAST_REJECT_COUNT=0
  ISSUES_FOUND=0; ISSUES_FIXED=0; INTERRUPTED=0
  MS_START_SHA=$(git rev-parse HEAD 2>/dev/null || echo ""); MS_START_EPOCH=$(now_epoch)
  save_state
}

review_sig() {  # a fingerprint of the "Required fixes" section
  "$PY" - "$1" <<'EOF'
import hashlib, re, sys
try:
    t = open(sys.argv[1], encoding="utf-8", errors="replace").read().lower()
except OSError:
    print(""); sys.exit()
m = re.search(r"required fixes(.*?)(repeated from earlier|optional|suggestion|$)", t, re.S)
body = re.sub(r"[^a-z ]+", " ", m.group(1) if m else t)
body = re.sub(r"\s+", " ", body).strip()
print(hashlib.sha1(body.encode()).hexdigest()[:12] if body else "")
EOF
}

run_milestone() {
  local id="${MS_IDS[$MS_INDEX]}" title="${MS_TITLES[$MS_INDEX]}" res verdict count sig model effort elapsed files commits
  mkdir -p "$BUILD_DIR/$id"

  if [ "$PHASE" = "build" ]; then
    say BUILD "$id $title: building ($BUILD_MODEL, $BUILD_EFFORT effort)"
    set_phase "building"
    if [ "$id" = "M0" ]; then marked_batch build "$BUILD_MODEL" "$BUILD_EFFORT" "$(prompt_plan)"
    else marked_batch build "$BUILD_MODEL" "$BUILD_EFFORT" "$(prompt_build "$id" "$title")"; fi
    res=$(result_line "$BATCH_TXT" MILESTONE_RESULT)
    case "$res" in
      *BLOCKED*) stop_build "builder says it needs you: ${res#*BLOCKED}" ;;
      *DONE*) say STEP "$id build batch finished, sending to review" ;;
      *) say WARN "$id build batch ended without a result line, the review will check it" ;;
    esac
    PHASE="review"; save_state
  fi

  while true; do
    if [ "$PHASE" = "fix" ]; then
      say FIX "$id applying review $REVIEW_N fixes ($LAST_REJECT_COUNT required, $FIX_MODEL)"
      set_phase "fixing" "review $REVIEW_N fixes, $FIX_MODEL"
      marked_batch fix "$FIX_MODEL" "$FIX_EFFORT" "$(prompt_fix "$id" "$title" "$REVIEW_N")"
      res=$(result_line "$BATCH_TXT" FIX_RESULT)
      case "$res" in
        *BLOCKED*) stop_build "fixer says it needs you: ${res#*BLOCKED}" ;;
        *) ISSUES_FIXED=$((ISSUES_FIXED + LAST_REJECT_COUNT)) ;;
      esac
      PHASE="review"; save_state
    fi

    # a review interrupted by a kill or crash is redone under the same number
    if [ "$INTERRUPTED" != "1" ]; then REVIEW_N=$((REVIEW_N + 1)); fi
    if [ "$ESCALATED" = "1" ]; then model="$ESC_REVIEW_MODEL"; effort="$ESC_REVIEW_EFFORT"
      say REVIEW "$id review $REVIEW_N (escalated, $model, $((ESC_REJ + 1))/$MAX_ESC_REJECTS)"
      set_phase "reviewing" "review $REVIEW_N, escalated to $model"
    else model="$REVIEW_MODEL"; effort="$REVIEW_EFFORT"
      say REVIEW "$id review $REVIEW_N ($model, $((OPUS_REJ + 1))/$MAX_OPUS_REJECTS)"
      set_phase "reviewing" "review $REVIEW_N, $model"
    fi
    save_state
    marked_batch review "$model" "$effort" "$(prompt_review "$id" "$title" "$REVIEW_N" "$MS_START_SHA")"
    verdict=$(result_line "$BATCH_TXT" REVIEW_VERDICT)

    if [[ "$verdict" == *APPROVED* ]]; then
      elapsed=$(( $(now_epoch) - MS_START_EPOCH ))
      files=$(git diff --name-only "$MS_START_SHA" 2>/dev/null | grep -vc "^$BUILD_DIR/")
      commits=$(git rev-list --count "$MS_START_SHA"..HEAD 2>/dev/null || echo 0)
      git add -A "$BUILD_DIR" >/dev/null 2>&1 && git commit -q -m "build($id): approved after $REVIEW_N review(s)" >/dev/null 2>&1
      say PASS "$id approved after $REVIEW_N review(s): $(fmt_dur "$elapsed"), $files files changed, $commits commits, $ISSUES_FOUND issues found and fixed"
      return 0
    fi

    count=$(printf '%s' "$verdict" | grep -oE '[0-9]+' | head -1); count=${count:-1}
    [ -z "$verdict" ] && say WARN "$id review ended without a verdict line, counted as rejected"
    LAST_REJECT_COUNT=$count; ISSUES_FOUND=$((ISSUES_FOUND + count))
    say REJECT "$id review $REVIEW_N: $count required fix(es), see $BUILD_DIR/$id/review-$REVIEW_N.md"
    sig=$(review_sig "$BUILD_DIR/$id/review-$REVIEW_N.md")
    local repeated=0
    [[ "$verdict" == *REPEATED* ]] && repeated=1
    [ -n "$sig" ] && [ "$sig" = "$LAST_SIG" ] && repeated=1
    LAST_SIG="$sig"

    if [ "$ESCALATED" = "1" ]; then
      ESC_REJ=$((ESC_REJ + 1))
      if [ "$ESC_REJ" -ge "$MAX_ESC_REJECTS" ]; then
        stop_build "still rejected after $OPUS_REJ opus and $ESC_REJ fable reviews. Last review: build/$id/review-$REVIEW_N.md"
      fi
      if [ "$repeated" = "1" ]; then say ESCAL "$id the same problem persists even after escalation, one more fix round before stopping"; fi
    else
      OPUS_REJ=$((OPUS_REJ + 1))
      if [ "$repeated" = "1" ]; then
        ESCALATED=1; say ESCAL "$id the same fixes were requested again, escalating reviews to $ESC_REVIEW_MODEL"
      elif [ "$OPUS_REJ" -ge "$MAX_OPUS_REJECTS" ]; then
        ESCALATED=1; say ESCAL "$id still rejected after $OPUS_REJ opus reviews, escalating reviews to $ESC_REVIEW_MODEL"
      fi
    fi
    PHASE="fix"; save_state
  done
}

# ---------------------------------------------------------------- setup
ensure_git() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git init -q
    say START "initialized a git repository"
  fi
  if [ ! -f .gitignore ]; then
    cat > .gitignore <<'EOF'
runs/
exports/
logs/
.locks/
.env
node_modules/
__pycache__/
*.mp4
*.mov
library/voice/
styles/*/refs/
styles/*/analysis/
styles/sfx/**/*.wav
styles/sfx/**/*.mp3
styles/sfx/**/*.aif
styles/sfx/**/*.aiff
styles/sfx/**/*.ogg
styles/sfx/**/*.flac
styles/sfx/**/*.m4a
styles/sfx/.cache/
styles/sfx/previews/
build/state.env
build/.status
build/status.txt
build/*.log
build/*/batches/
build/check.*
EOF
  fi
  [ -f .gitattributes ] || printf '*.sh text eol=lf\n' > .gitattributes
  git config user.name >/dev/null 2>&1 || git config user.name "reels-autopilot"
  git config user.email >/dev/null 2>&1 || git config user.email "autopilot@localhost"
  if ! git rev-parse HEAD >/dev/null 2>&1; then
    git add -A >/dev/null 2>&1 && git commit -q -m "chore: initial import before the automated build" >/dev/null 2>&1
  fi
}

preflight() {
  local ok=1
  command -v "$CLAUDE_BIN" >/dev/null 2>&1 || { say ERROR "claude is not on PATH in Git Bash"; ok=0; }
  command -v git >/dev/null 2>&1 || { say ERROR "git is not installed"; ok=0; }
  [ -n "$PY" ] || { say ERROR "Python 3.8+ not found (tried python3, python, py)"; ok=0; }
  [ -f "$SPEC" ] || { say ERROR "$SPEC not found in $(pwd)"; ok=0; }
  date -d "Mon 12:00am" +%s >/dev/null 2>&1 || { say ERROR "GNU date is missing (run this from Git Bash)"; ok=0; }
  [ "$ok" = "1" ] || exit 1
}

check_claude() {  # one tiny call with the same flags the batches use
  local out="$BUILD_DIR/check"
  printf 'Reply with the single word: ok\n' > "$out.prompt.md"
  set_phase "checking Claude Code for"
  if call_claude "$PROBE_MODEL" "" "$out.prompt.md" "$out"; then
    say START "Claude Code check passed ($PROBE_MODEL, flags: ${PERM_FLAGS[*]})"
    return 0
  fi
  say ERROR "Claude Code check failed: $STOP_REASON"
  say ERROR "if the permission flags are the problem, see PERM_FLAGS at the top of build-runner.sh"
  exit 1
}

# ---------------------------------------------------------------- main
[ "${BUILD_RUNNER_LIB_ONLY:-0}" = "1" ] && return 0 2>/dev/null
FROM=""; REVIEW_PLAN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift ;;
    --review-plan) REVIEW_PLAN=1 ;;
    --status) if [ -f "$STATUS_TXT" ]; then cat "$STATUS_TXT"; elif line=$(status_line); then echo "$line"; else echo "not started"; fi; exit 0 ;;
    --check) preflight; check_claude; exit 0 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $1"; exit 2 ;;
  esac
  shift
done

preflight
ensure_git
[ -f "$TODO" ] || printf '# Things the build needs from you\n\nEach line: milestone, what to do, where.\n\n' > "$TODO"
load_state

if [ -n "$FROM" ]; then
  idx=-1
  for i in "${!MS_IDS[@]}"; do [ "${MS_IDS[$i]}" = "$FROM" ] && idx=$i; done
  [ "$idx" -lt 0 ] && { echo "unknown milestone: $FROM (use M0 to M13)"; exit 2; }
  MS_INDEX=$idx; STOPPED=0; start_milestone
elif [ ! -f "$STATE" ]; then
  MS_INDEX=0; TOTAL_START=$(now_epoch); start_milestone
elif [ "$STOPPED" = "1" ]; then
  STOPPED=0; OPUS_REJ=0; ESC_REJ=0; ESCALATED=0; LAST_SIG=""
  [ "$PHASE" = "fix" ] && PHASE="review"
  save_state
  say START "resuming after a stop: ${MS_IDS[$MS_INDEX]} with fresh review counters"
fi
[ "$TOTAL_START" = "0" ] && TOTAL_START=$(now_epoch)

check_claude
say START "build runner: ${#MS_IDS[@]} batches (M0 to M13), now at ${MS_IDS[$MS_INDEX]} ${MS_TITLES[$MS_INDEX]} ($PHASE). Status every $(fmt_dur "$STATUS_EVERY")."
say START "builder $BUILD_MODEL ($BUILD_EFFORT), reviewer $REVIEW_MODEL then $ESC_REVIEW_MODEL, fixer $FIX_MODEL. Log: $LOG"
start_ticker

while [ "$MS_INDEX" -lt "${#MS_IDS[@]}" ]; do
  run_milestone
  if [ "${MS_IDS[$MS_INDEX]}" = "M0" ] && [ "$REVIEW_PLAN" = "1" ] && [ -t 0 ]; then
    say WAIT "PLAN.md is approved by the reviewer. Read it now; press Enter to start building (Ctrl+C to stop)"
    read -r _
  fi
  MS_INDEX=$((MS_INDEX + 1))
  if [ "$MS_INDEX" -lt "${#MS_IDS[@]}" ]; then
    start_milestone
    say NEXT "${MS_IDS[$MS_INDEX]} ${MS_TITLES[$MS_INDEX]}"
  fi
done

stop_ticker
save_state
say DONE "all ${#MS_IDS[@]} batches complete in $(fmt_dur $(( $(now_epoch) - TOTAL_START ))). $(todo_count) item(s) in $TODO"
[ "$(todo_count)" -gt 0 ] && grep '^- ' "$TODO" | sed 's/^/        /'
exit 0
