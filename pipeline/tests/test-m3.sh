#!/usr/bin/env bash
# test-m3.sh: acceptance test for M3 (Error system). One section makes real model calls (the Opus reviewer and the
# Sonnet fixer on a planted bug); everything else uses the fake claude in pipeline/tests/fakes.
#   bash pipeline/tests/test-m3.sh                 everything (10 to 20 minutes, dominated by the real calls)
#   M3_SECTIONS="1 2 3" bash pipeline/tests/test-m3.sh    only those sections (4 is the real-model one; 1 to 10 exist)
#
# Covers (BUILD_SPEC.md section 12, M3, and PLAN.md M3):
#   1. ai() units with the fake: the command line (model and effort from config, tools, the protected-file denials),
#      the call files, the schema retry in the same session, --session storage, a missing session (exit 3), the
#      protected files guard, fatal errors, the restart note
#   2. usage limits: every format of spec 4.1 through ai() in fast-forward mode, the LIMIT and RESUME lines, the
#      target in logs/limits.log checked against an independent computation, the same session on the retry, the
#      probe loop when nothing parses, limits on stderr and in plain text; then one full runner pass with a limit
#      inside a stage
#   3. transient errors: 60 s, 4 min, 16 min, then a code error; a timeout kill counts as transient
#   4. the planted bug (real Opus reviewer and Sonnet fixer, in a sandbox git repo): E1.md with every part, F1.md
#      with the five parts, the autofix commit, the known-issues line, the stage restarts and passes, ERROR then FIXED
#   5. an unfixable error (the fake reviewer answers auto_apply no): BLOCK then NEXT, blocked.txt, the run folder
#      kept, the next idea exported, the block streak reset by the export
#   6. the caps: the repeated-signature rule skips the remaining Opus cycles (ERROR, FIXED, ERROR, ESCAL, FIXED,
#      ERROR, BLOCK) and failed verifications use up the three cycles before the escalation
#   7. three identical blocks in a row: STOP, logs/STOPPED.md with the diagnosis and the fix, exit 3, the fourth
#      idea left in the queue
#   8. the two guards as units: treeguard.py (the fixer's changes outside pipeline/ are undone, the user's own
#      uncommitted work and a log that grew during the call survive) and protect.py (protected files restored)
#   9. a failed stage script is classified before any review (M3 review 1, fix 2): a network reset is retried
#      (RETRY 60 s, 4 min, 16 min, then a code error and one review), a usage limit printed by the stage is waited
#      out (LIMIT, RESUME, no reviewer call), a stage whose own model call failed goes straight to the review;
#      the limit path is bounded (M3 review 2, fix 1: the same limit message right after its wait, or the third
#      limit message, is a code error with one review) and a traceback's echoed frames are not an error (fix 2)
#  10. a runner killed during a review cycle (M3 review 1, fix 1): the restart resumes the same cycle (no ESCAL
#      before an Opus cycle, no second ERROR, one open issue) and adopts a review-cycle child that still runs
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
fast_mode
export REELS_DUMMY_SECONDS=0.1
SECTIONS="${M3_SECTIONS:-1 2 3 4 5 6 7 8 9 10}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }

STATE_PY="$REPO_DIR/pipeline/lib/state.py"
DRIVER="$REPO_DIR/pipeline/tests/ai-driver.sh"
FIX_STAGES="$FIXTURES/stages"
IDEA_A="Idea A: the gh CLI in 60 seconds, three flags that matter"
IDEA_B="Idea B: uv replaces pip, venv and pyenv in one tool, città"
IDEA_C="Idea C: ffmpeg loudnorm in two passes for reels"
IDEA_D="Idea D: the fourth idea stays in the queue"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
RUNNER_JOB=""
KEY_ERROR="exit 1: FileNotFoundError: library/keys/service.key is missing: this stage needs the API key file that only the user can create"
REVIEWER="$(python -c 'import json; print(json.load(open("config.json"))["models"]["reviewer"]["model"])')"
ESCALATION="$(python -c 'import json; print(json.load(open("config.json"))["models"]["reviewer_escalation"]["model"])')"
FIXER="$(python -c 'import json; print(json.load(open("config.json"))["models"]["fixer"]["model"])')"
PROBE="$(python -c 'import json; print(json.load(open("config.json"))["models"]["probe"]["model"])')"

state_get() { python "$STATE_PY" get "$@"; }
run_dirs() { ls -d "$SANDBOX"/runs/*/ 2>/dev/null | sed 's|/$||'; }
lock_pid() { cut -d' ' -f1 "$SANDBOX/.locks/runner/pid" 2>/dev/null; }

run_once() {  # run_once <outfile> [env...]: the sandbox's own run.sh (so REELS_REPO is the sandbox repo)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 1800 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}

runner_bg() {  # runner_bg <outfile> [args...]
  local out="$1"; shift
  ( cd "$SANDBOX" && exec env NO_COLOR=1 bash "$SANDBOX/run.sh" "$@" ) > "$out" 2>&1 &
  RUNNER_JOB=$!
}

wait_for() {  # wait_for <regex> <file> [seconds]
  local i=0 n=$(( ${3:-30} * 5 ))
  while [ $i -lt $n ]; do
    grep -q -E -- "$1" "$2" 2>/dev/null && return 0
    sleep 0.2; i=$((i + 1))
  done
  return 1
}

wait_gone() {  # wait_gone <pid> [seconds]
  local i=0 n=$(( ${2:-10} * 5 ))
  while [ $i -lt $n ]; do ps -p "$1" >/dev/null 2>&1 || return 0; sleep 0.2; i=$((i + 1)); done
  return 1
}

kill_tree() {  # kill_tree <pid>: SIGKILL the process, then every descendant (ps -ef lists bash and native children
               # with their parent pid; the parent goes first so it cannot react to a child's death)
  local pid="$1" kids k
  kids="$(ps -ef 2>/dev/null | awk -v p="$pid" 'NR > 1 && $3 == p { print $2 }')"
  kill -9 "$pid" 2>/dev/null
  for k in $kids; do kill_tree "$k"; done
}

install_stage() {  # install_stage <fixture name> <stage key>: the fixture's files become the stage's run.sh (+ helpers)
  cp "$FIX_STAGES/$1"/* "$SANDBOX/pipeline/stages/$2/"
  git -C "$SANDBOX" add -A >/dev/null 2>&1
  git -C "$SANDBOX" commit -q -m "test: install the $1 fixture as $2" >/dev/null 2>&1
}

new_run() {  # new_run "<idea>" -> RD (the run dir, mixed path) and SD (its 10-build folder) with a prompt file
  RD="$(printf '{%s}' "$1" | python "$STATE_PY" new --runs "$SANDBOX_M/runs" --id "$(printf '%s' "$1" | sha1sum | cut -c1-12)" \
        | python -c 'import json, sys; print(json.load(sys.stdin)["run_dir"])')"
  SD="$RD/10-build"
  mkdir -p "$SD"
  printf 'Reply with the single word ok.\n' > "$SD/prompt.md"
}

drive() {  # drive <role> [ai options...] -> DRIVE_OUT (the key=value line), DRIVE_RC
  local role="$1"; shift
  DRIVE_OUT="$(bash "$DRIVER" "$role" "$SD" "$SD/prompt.md" "$@" 2>>"$SANDBOX/driver.err" | tail -n 1)"
  DRIVE_RC="$(field rc)"; [ -n "$DRIVE_RC" ] || DRIVE_RC=99
}
field() { printf '%s\n' "$DRIVE_OUT" | tr '\t' '\n' | sed -n "s/^$1=//p"; }
fake_calls() { python -c 'import json, sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG"; }
fake_field() {  # fake_field <call n> <key>
  python -c '
import json, sys
n, key = int(sys.argv[2]), sys.argv[3]
for line in open(sys.argv[1], encoding="utf-8"):
    d = json.loads(line)
    if d["n"] == n:
        v = d.get(key)
        print(v if not isinstance(v, (list, dict)) else json.dumps(v)); break' "$FAKE_CLAUDE_LOG" "$1" "$2"
}
event_tags() {  # event_tags <runner output>: the event lines' tags in order, comma separated
  python -c '
import re, sys
print(",".join(m.group(1) for m in re.finditer(r"^\[\d\d:\d\d\] (LIMIT|RESUME|RETRY|ERROR|BLOCK|FIXED|ESCAL) ", open(sys.argv[1], encoding="utf-8").read(), re.M)))' "$1"
}
fake_roles() {  # the role:model pairs of every logged call, comma separated
  python - "$FAKE_CLAUDE_LOG" <<'EOF'
import json, sys
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    if line.strip():
        d = json.loads(line)
        out.append((d["role"] or "call") + ":" + str(d["model"]))
print(",".join(out))
EOF
}

expected_target() {  # expected_target <fmt> -> "YYYY-MM-DD HH:MM:SS" of reset + 120 s, computed independently
  python - "$1" <<'EOF'
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
fmt = sys.argv[1]
rome = ZoneInfo("Europe/Rome")
now = datetime.now(rome)
def at(h, m, zone=rome):
    n = datetime.now(zone)
    t = n.replace(hour=h, minute=m, second=0, microsecond=0)
    return t + timedelta(days=1) if t <= n else t
if fmt == "time": t = at(15, 45)
elif fmt == "time-tz": t = at(15, 0)
elif fmt == "time-tz-ny": t = at(15, 0, ZoneInfo("America/New_York"))
elif fmt == "weekday":
    t = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=(0 - now.weekday()) % 7)
    if t <= now: t += timedelta(days=7)
elif fmt == "date":
    t = now.replace(month=11, day=3, hour=10, minute=0, second=0, microsecond=0)
    if t <= now: t = t.replace(year=t.year + 1)
elif fmt == "epoch": t = datetime.fromtimestamp(1793696400, rome)
print(datetime.fromtimestamp(int(t.timestamp()) + 120).strftime("%Y-%m-%d %H:%M:%S"))
EOF
}
fmt_epoch() { python -c 'import sys, datetime; print(datetime.datetime.fromtimestamp(int(sys.argv[1])).strftime("%Y-%m-%d %H:%M:%S"))' "$1"; }

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. ai() units with the fake claude"
sandbox_init
fake_claude_on
export REELS_SLEEP_SCALE=0
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
new_run "$IDEA_A"
LOG="$SANDBOX/logs/runner.log"

FAKE_CLAUDE_MODE=ok drive indexer --tools ""
assert_rc 0 "$DRIVE_RC" "a plain call succeeds"
assert_eq "$(field result)" "ok" "AI_RESULT holds the result text"
assert_eq "$(field class)" "ok" "AI_CLASS is ok"
assert_true "AI_SESSION holds the session id" grep -q '^fake-' <<<"$(field session)"
assert_file "$SD/calls/001.json" "the raw output is saved as calls/001.json"
assert_file "$SD/calls/001.meta" "calls/001.meta written"
assert_grep "^model: haiku$" "$SD/calls/001.meta" "the model comes from config (indexer -> haiku)"
assert_grep "^effort: low$" "$SD/calls/001.meta" "the effort comes from config (indexer -> low)"
assert_grep "^class: ok$" "$SD/calls/001.meta" "the meta records the class"
assert_eq "$(fake_field 1 model)" "haiku" "the fake saw --model haiku"
assert_eq "$(fake_field 1 effort)" "low" "the fake saw --effort low"
assert_eq "$(fake_field 1 tools)" '[""]' "--tools \"\" disables the tools"
assert_true "the protected files are denied: Edit(ideas.txt)" grep -q 'Edit(ideas.txt)' <<<"$(fake_field 1 disallowed)"
assert_true "the protected files are denied: Write(library/**)" grep -q 'Write(library/\*\*)' <<<"$(fake_field 1 disallowed)"
assert_true "the protected files are denied: Edit(styles/**), Edit(exports/**)" grep -q 'Edit(styles/\*\*).*Edit(exports/\*\*)' <<<"$(fake_field 1 disallowed)"
assert_true ".env is denied to Read" grep -q 'Read(.env)' <<<"$(fake_field 1 disallowed)"
assert_eq "$(fake_field 1 prompt_head)" "Reply with the single word ok." "the prompt arrives on stdin"
assert_eq "$(fake_field 1 cwd)" "$(mixed "$REPO_DIR")" "the call runs in the repo root"

FAKE_CLAUDE_MODE=ok drive indexer --tools "Read Glob" --add-dir "$RD" --max-turns 4
assert_eq "$(fake_field 2 tools)" '["Read,Glob"]' "--tools passes a comma list"
assert_eq "$(fake_field 2 allowed)" '["Read", "Glob"]' "the same tools are pre-approved with --allowedTools"
assert_eq "$(fake_field 2 add_dir)" "[\"$RD\"]" "--add-dir is passed"
assert_eq "$(fake_field 2 max_turns)" "4" "--max-turns is passed"

printf '{"type":"object","required":["ok","text"],"properties":{"ok":{"type":"boolean"},"text":{"type":"string"}}}\n' > "$SANDBOX/schema.json"
printf 'bad-json\nok\n' > "$SANDBOX/script.txt"
fake_claude_reset
FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" drive indexer --tools "" --schema "$SANDBOX_M/schema.json"
assert_rc 0 "$DRIVE_RC" "schema: an invalid structured output is retried once and the second answer is accepted"
assert_eq "$(fake_calls)" "2" "schema: two calls"
sid1="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["session_id"])' "$SD/calls/003.json")"
assert_eq "$(fake_field 2 resume)" "$sid1" "schema: the retry resumes the session of the first answer"
assert_true "schema: the retry prompt carries the validation errors" grep -q "did not match the required JSON schema" <<<"$(fake_field 2 prompt_head)"
assert_grep "WARN   indexer output did not match the schema" "$LOG" "schema: a WARN line names the retry"
assert_file "$(field out)" "schema: AI_OUT names the structured output file"
assert_true "schema: the structured output is the valid one" grep -q '"ok": true' "$(field out)"
printf 'bad-json\nbad-json\n' > "$SANDBOX/script.txt"
fake_claude_reset
FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" drive indexer --tools "" --schema "$SANDBOX_M/schema.json"
assert_rc 1 "$DRIVE_RC" "schema: still invalid after the retry is a code error"
assert_true "schema: the error names the schema" grep -q "^output did not match the schema after one retry" <<<"$(field error)"
assert_file "$SD/error.json" "error.json written"
assert_grep '"class": "error"' "$SD/error.json" "error.json: class error"
assert_grep '"signature": "[0-9a-f]{12}"' "$SD/error.json" "error.json: a signature"

rm -f "$SD/error.json"; fake_claude_reset
FAKE_CLAUDE_MODE=ok drive indexer --tools "" --session A
sidA="$(state_get "$RD" sessions.A "")"
assert_true "--session stores the session id in state.json" grep -q '^fake-' <<<"$sidA"
FAKE_CLAUDE_MODE=ok drive indexer --tools "" --session A
assert_eq "$(fake_field 2 resume)" "$sidA" "--session resumes the stored session"
FAKE_CLAUDE_MODE=resume-missing drive indexer --tools "" --session A
assert_rc 3 "$DRIVE_RC" "a session that no longer exists returns 3"
assert_eq "$(state_get "$RD" sessions.A "cleared")" "" "the stored session is cleared"
assert_grep '"resume_failed": true' "$SD/error.json" "error.json: resume_failed"

before="$(cat "$SANDBOX/ideas.txt")"
rm -f "$SD/error.json"
FAKE_CLAUDE_TAMPER_FILE="$SANDBOX_M/ideas.txt" FAKE_CLAUDE_MODE=tamper drive indexer --tools ""
assert_rc 1 "$DRIVE_RC" "a call that changed a protected file is a code error"
assert_eq "$(cat "$SANDBOX/ideas.txt")" "$before" "ideas.txt is restored from the snapshot"
assert_true "the error names the protected file" grep -q "protected files (\[\"root/ideas.txt\"\])" <<<"$(field error)"
assert_no_file "$SD/calls/.protect" "the snapshot folder is removed"

FAKE_CLAUDE_MODE=fatal drive indexer --tools ""
assert_rc 1 "$DRIVE_RC" "not logged in is a code error"
assert_eq "$(field fatal)" "1" "AI_FATAL is set for a login problem"
assert_grep '"fatal": true' "$SD/error.json" "error.json: fatal"
FAKE_CLAUDE_MODE="error:Boom happened in the fake" drive indexer --tools ""
assert_rc 1 "$DRIVE_RC" "an error result is a code error"
assert_eq "$(field error)" "Boom happened in the fake" "AI_ERROR carries the message"
FAKE_CLAUDE_MODE=echo drive indexer --tools ""
assert_eq "$(field result)" "Reply with the single word ok." "echo: the prompt arrived verbatim"

printf 'note: the previous attempt failed\n' > "$SD/restart-note.md"
note="$(bash -c "source '$REPO_DIR/pipeline/lib/common.sh'; source '$REPO_DIR/pipeline/lib/log.sh'; source '$REPO_DIR/pipeline/lib/config.sh'; source '$REPO_DIR/pipeline/lib/state.sh'; source '$REPO_DIR/pipeline/lib/status.sh'; source '$REPO_DIR/pipeline/lib/ai.sh'; ai_restart_note '$SD'")"
assert_eq "$note" "note: the previous attempt failed" "ai_restart_note prints the note"
assert_no_file "$SD/restart-note.md" "ai_restart_note removes it"
unset REELS_SLEEP_SCALE
fi

# ----------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. usage limits through ai(), every format, fast-forward"
sandbox_init
fake_claude_on
export REELS_SLEEP_SCALE=0
new_run "$IDEA_B"
LOG="$SANDBOX/logs/runner.log"; LIMITS_LOG="$SANDBOX/logs/limits.log"
for fmt in time time-tz time-tz-ny weekday date epoch; do
  fake_claude_reset; : > "$LOG"; : > "$LIMITS_LOG"
  FAKE_CLAUDE_MODE="limit:$fmt" drive indexer --tools "" --resume "sess-$fmt"
  assert_rc 0 "$DRIVE_RC" "limit $fmt: the call succeeds after the wait"
  kind="session"; case "$fmt" in weekday) kind="weekly" ;; time-tz|time-tz-ny|epoch) kind="usage" ;; esac
  assert_grep "${ts_regex}LIMIT  $kind limit hit, resuming at ([0-9]{2}:[0-9]{2}|[A-Z][a-z]{2} [0-9]{2}:[0-9]{2}|[A-Z][a-z]{2} [0-9]{1,2} [0-9]{2}:[0-9]{2}) \(\+2 min margin\)$" "$LOG" "limit $fmt: LIMIT line with the kind, the target and the margin"
  assert_grep "${ts_regex}INFO   fast-forward: skipping the wait until " "$LOG" "limit $fmt: fast-forward logs the wait instead of sleeping"
  assert_grep "${ts_regex}RESUME limit reset, continuing: " "$LOG" "limit $fmt: RESUME line"
  assert_grep "\| waiting until $(expected_target "$fmt") \(reset \+ 120 s\) \|" "$LIMITS_LOG" "limit $fmt: limits.log has the right target (reset + 120 s)"
  assert_eq "$(fake_calls)" "2" "limit $fmt: one retry"
  assert_eq "$(fake_field 2 resume)" "sess-$fmt" "limit $fmt: the retry is the same call in the same session"
done
for fmt in "time+90" "epoch+30"; do
  fake_claude_reset; : > "$LOG"; : > "$LIMITS_LOG"
  FAKE_CLAUDE_MODE="limit:$fmt" drive indexer --tools ""
  assert_rc 0 "$DRIVE_RC" "limit $fmt: the call succeeds after the wait"
  exp="$(fmt_epoch $(( $(fake_field 1 limit_epoch) + 120 )))"
  assert_grep "\| waiting until $exp \(reset \+ 120 s\) \|" "$LIMITS_LOG" "limit $fmt: the target is the message's moment plus 120 s"
done
for channel in stderr plain; do
  fake_claude_reset; : > "$LOG"
  FAKE_CLAUDE_MODE="limit:time:$channel" drive indexer --tools ""
  assert_rc 0 "$DRIVE_RC" "a limit on $channel is detected and the call retried"
  assert_grep "${ts_regex}LIMIT  session limit hit" "$LOG" "limit on $channel: LIMIT line"
done
fake_claude_reset; : > "$LOG"; : > "$LIMITS_LOG"
FAKE_CLAUDE_MODE=limit:unparsed drive indexer --tools ""
assert_rc 0 "$DRIVE_RC" "unparsed limit: the call succeeds once the probe answers"
assert_grep "${ts_regex}LIMIT  usage limit hit but no reset time found, probing every 30 min \(first probe in 30 min\)$" "$LOG" "unparsed limit: LIMIT line"
assert_grep "${ts_regex}INFO   fast-forward: skipping a 30m wait \(unparsed limit\)$" "$LOG" "unparsed limit: the 30 min sleep"
assert_grep "${ts_regex}RESUME limit is over \(probe 1 answered\), continuing: " "$LOG" "unparsed limit: RESUME after the probe"
assert_grep "\| no reset time parsed \| probing every 1800 s after 1800 s \|" "$LIMITS_LOG" "unparsed limit: limits.log line"
assert_eq "$(fake_calls)" "3" "unparsed limit: the limit, the probe, the retry"
assert_eq "$(fake_field 2 model)" "$(python -c 'import json; print(json.load(open("config.json"))["models"]["probe"]["model"])')" "the probe uses the probe model from config"
assert_true "the probe files are named NNN-probe" ls "$SD/calls" | grep -q -- '-probe.json$'

# a limit inside a running stage: the runner's log tells the story and the stage still finishes
sandbox_init --with-pipeline
fake_claude_on
install_stage aicall 10-build
printf '{%s}\n' "$IDEA_B" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/limit.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FAKE_CLAUDE_MODE="limit:time+90"; rc=$?
OUT="$SANDBOX/limit.out"
assert_rc 0 $rc "the runner finishes the idea after a limit inside a stage"
assert_grep "${ts_regex}LIMIT  session limit hit, resuming at [0-9]{2}:[0-9]{2} \(\+2 min margin\)$" "$OUT" "runner: LIMIT line from inside the stage"
assert_grep "${ts_regex}RESUME limit reset, continuing: building visuals$" "$OUT" "runner: RESUME names the stage's activity"
assert_grep "${ts_regex}STEP   building visuals done" "$OUT" "runner: the stage finishes after the wait"
assert_grep "${ts_regex}DONE   exported #1" "$OUT" "runner: the idea is exported"
exp="$(fmt_epoch $(( $(fake_field 1 limit_epoch) + 120 )))"
assert_grep "\| waiting until $exp \(reset \+ 120 s\) \|" "$SANDBOX/logs/limits.log" "runner: limits.log has the target (reset + 120 s)"
assert_grep "model said: ok" "$(run_dirs | head -n 1)/10-build/stage.log" "runner: the stage got the answer after the retry"
assert_not_grep "${ts_regex}(ERROR|BLOCK) " "$OUT" "runner: a limit is never an error"
unset REELS_SLEEP_SCALE
fi

# ----------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. transient errors: 60 s, 4 min, 16 min, then a code error"
sandbox_init
fake_claude_on
export REELS_SLEEP_SCALE=0
new_run "$IDEA_C"
LOG="$SANDBOX/logs/runner.log"
FAKE_CLAUDE_MODE=transient:3 drive indexer --tools ""
assert_rc 0 "$DRIVE_RC" "three transient failures, then success"
assert_grep "${ts_regex}RETRY  temporary error \(overloaded\), retrying in 60s \(try 1/3\)$" "$LOG" "RETRY 1: 60 s"
assert_grep "${ts_regex}RETRY  temporary error \(overloaded\), retrying in 4m \(try 2/3\)$" "$LOG" "RETRY 2: 4 min"
assert_grep "${ts_regex}RETRY  temporary error \(overloaded\), retrying in 16m \(try 3/3\)$" "$LOG" "RETRY 3: 16 min"
assert_eq "$(grep -c "fast-forward: skipping a .* wait (transient backoff)" "$LOG")" "3" "three scaled backoff waits"
assert_eq "$(fake_calls)" "4" "four calls in all"
fake_claude_reset; : > "$LOG"; rm -f "$SD/error.json"
FAKE_CLAUDE_MODE=transient:4 drive indexer --tools ""
assert_rc 1 "$DRIVE_RC" "a fourth transient failure is a code error"
assert_true "the error says the retries are used up" grep -q "^temporary error persisted after 3 retries (overloaded)" <<<"$(field error)"
assert_eq "$(fake_calls)" "4" "no fifth call"
assert_grep '"class": "error"' "$SD/error.json" "error.json: class error after the retries"
fake_claude_reset; : > "$LOG"
FAKE_CLAUDE_MODE=transient-stderr:1 drive indexer --tools ""
assert_rc 0 "$DRIVE_RC" "a network reset on stderr is transient"
assert_grep "${ts_regex}RETRY  temporary error \(connection reset\), retrying in 60s \(try 1/3\)$" "$LOG" "RETRY names the reset"
printf 'hang:30\nok\n' > "$SANDBOX/script.txt"
fake_claude_reset; : > "$LOG"
FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" drive indexer --tools "" --timeout 2
assert_rc 0 "$DRIVE_RC" "a call killed by the timeout is retried"
assert_grep "${ts_regex}RETRY  temporary error \(timeout\), retrying in 60s \(try 1/3\)$" "$LOG" "RETRY names the timeout"
# the network wordings this PC produces are transient through ai() too (M3 review 3, fix 1), and the em dash of the
# Claude CLI's network message never reaches AI_ERROR, the RETRY and ERROR lines or error.json (fix 2)
fake_claude_reset; : > "$LOG"; rm -f "$SD/error.json"
printf 'error:API Error: No response from API\nok\n' > "$SANDBOX/script.txt"
FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" drive indexer --tools ""
assert_rc 0 "$DRIVE_RC" "Claude Code's 'No response from API' is retried, then the call succeeds"
assert_grep "${ts_regex}RETRY  temporary error \(network error\), retrying in 60s \(try 1/3\)$" "$LOG" "RETRY names the network error"
assert_eq "$(fake_calls)" "2" "two calls: the failed one and the retry"
fake_claude_reset; : > "$LOG"; rm -f "$SD/error.json"
em=$'\xe2\x80\x94'
printf "error:API Error: Can't reach the API server %s check your internet or DNS (ENOTFOUND)\n" "$em" > "$SANDBOX/script.txt"
FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" drive indexer --tools ""
assert_rc 1 "$DRIVE_RC" "the CLI's network message at every try is a code error after the three retries"
assert_eq "$(field error)" "temporary error persisted after 3 retries (network error): API Error: Can't reach the API server, check your internet or DNS (ENOTFOUND)" "AI_ERROR carries the message with a comma where the CLI had the em dash"
assert_true "the CLI really answered with the em dash (the raw call file holds U+2014)" python -c 'import sys; sys.exit(0 if bytes([0xE2, 0x80, 0x94]) in open(sys.argv[1], "rb").read() else 1)' "$(field call)"
assert_true "no U+2014 in runner.log or error.json" python -c '
import sys
sys.exit(1 if any(bytes([0xE2, 0x80, 0x94]) in open(p, "rb").read() for p in sys.argv[1:]) else 0)' "$LOG" "$SD/error.json"
unset REELS_SLEEP_SCALE
fi

# ----------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. a planted bug: the real Opus reviewer and Sonnet fixer (several minutes)"
fake_claude_off
sandbox_init --with-pipeline
install_stage buggy 10-build
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
head_before="$(git -C "$SANDBOX" rev-parse HEAD)"
real_head_before="$(git -C "$REPO_DIR" rev-parse HEAD)"
start=$EPOCHSECONDS
run_once "$SANDBOX/real.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0.001; rc=$?
took=$((EPOCHSECONDS - start))
OUT="$SANDBOX/real.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner exits 0 after fixing the planted bug (took $(( took / 60 )) min)"
assert_grep "${ts_regex}ERROR  S10 building visuals: exit 1: KeyError: 'beatz'$" "$OUT" "ERROR line with the stage, the activity and the traceback's last line"
assert_grep "${ts_regex}FIXED  S10: .* \(commit [0-9a-f]{7,}\), restarting stage$" "$OUT" "FIXED line with the cause and the commit"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 2 after the fix$" "$OUT" "the stage restarts"
assert_grep "${ts_regex}STEP   building visuals done" "$OUT" "the stage passes after the fix"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/ \(.*, 1 issue fixed\)$" "$OUT" "DONE counts the fixed issue"
assert_true "the ERROR comes before the FIXED, then the restart" python -c '
import re, sys
log = open(sys.argv[1], encoding="utf-8").read()
e = log.find("ERROR  S10"); f = log.find("FIXED  S10"); r = log.find("attempt 2 after the fix")
sys.exit(0 if 0 <= e < f < r else 1)' "$OUT"
E1="$RD/errors/E1.md"; F1="$RD/fixes/F1.md"
assert_file "$E1" "errors/E1.md written"
assert_grep "^- stage: 10-build$" "$E1" "E1: the stage"
assert_grep "^- command: bash .*pipeline/stages/10-build/run.sh " "$E1" "E1: the command"
assert_grep "^- exit code: 1$" "$E1" "E1: the exit code"
assert_grep "^## Last 200 lines of 10-build/stage.log$" "$E1" "E1: the log section"
assert_grep "KeyError: 'beatz'" "$E1" "E1: the traceback is in the log lines"
assert_grep "^## Input files" "$E1" "E1: the input files section"
assert_grep "^07-script/script.json	[0-9]+$" "$E1" "E1: lists the stage's input file with its size"
assert_grep "^## CONTRACT.md of 10-build$" "$E1" "E1: the contract section"
assert_grep "^# 10-build: Build visuals and draft render" "$E1" "E1: the contract text"
assert_grep "^## Git diff since the last successful run$" "$E1" "E1: the git diff section"
assert_grep "^## Previous error and fix files for this stage$" "$E1" "E1: the previous files section"
assert_grep "^\(none: this is the first error of 10-build in this run\)$" "$E1" "E1: no previous files"
assert_file "$F1" "fixes/F1.md written by the reviewer step"
assert_grep "^## Root cause$" "$F1" "F1: root cause"
assert_grep "^## Class$" "$F1" "F1: class"
assert_grep "^(pipeline bug|bad model output|environment problem|external outage)$" "$F1" "F1: one of the four classes"
assert_grep "^## Changes$" "$F1" "F1: changes"
assert_grep "helper.py" "$F1" "F1: the change names the helper"
assert_grep "^## Verify$" "$F1" "F1: the verify command"
assert_grep "^## auto_apply: yes$" "$F1" "F1: auto_apply yes"
assert_file "$RD/fixes/F1.result.json" "F1.result.json written"
assert_grep '"outcome": "fixed"' "$RD/fixes/F1.result.json" "F1: outcome fixed"
assert_file "$RD/fixes/F1.verify.log" "the verify command ran (F1.verify.log)"
assert_grep '"beats"' "$SANDBOX/pipeline/stages/10-build/helper.py" "the fixer corrected the key in helper.py"
assert_not_grep '"beatz"' "$SANDBOX/pipeline/stages/10-build/helper.py" "the wrong key is gone"
assert_true "the autofix commit exists in the sandbox repo" grep -q '^autofix(10-build): ' <<<"$(git -C "$SANDBOX" log --format=%s "$head_before..HEAD")"
assert_eq "$(git -C "$SANDBOX" status --porcelain | grep -v '^??' | wc -l | tr -d ' ')" "0" "nothing left uncommitted in the sandbox repo"
assert_eq "$(git -C "$REPO_DIR" rev-parse HEAD)" "$real_head_before" "the real repo got no commit"
assert_grep "^- [0-9]{4}-[0-9]{2}-[0-9]{2} \| 10-build \| .* \(F1, runs/" "$SANDBOX/pipeline/knowledge/known-issues.md" "known-issues.md gained one line (symptom -> fix)"
assert_eq "$(grep -c '^- ' "$SANDBOX/pipeline/knowledge/known-issues.md")" "1" "exactly one known-issues line"
assert_eq "$(state_get "$RD" errors.10-build.cycles)" "1" "state: one review cycle"
assert_eq "$(state_get "$RD" issues.fixed)" "1" "state: one issue fixed"
assert_eq "$(state_get "$RD" issues.open)" "0" "state: no open issue"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "2" "state: two attempts of the stage"
assert_eq "$(state_get "$RD" status)" "exported" "state: the run is exported"
assert_file "$RD/10-build/restart-note.md" "the restart note was written for the second attempt"
assert_grep "^Fix F1 applied" "$RD/10-build/restart-note.md" "the restart note names the fix"
assert_file "$RD/errors/calls/001-E1-review.json" "the reviewer call is saved under errors/calls/"
assert_file "$RD/errors/calls/002-E1-fix.json" "the fixer call is saved under errors/calls/"
assert_grep "^model: $(python -c 'import json; print(json.load(open("config.json"))["models"]["reviewer"]["model"])')$" "$RD/errors/calls/001-E1-review.meta" "the reviewer used the reviewer model"
assert_grep "^model: $(python -c 'import json; print(json.load(open("config.json"))["models"]["fixer"]["model"])')$" "$RD/errors/calls/002-E1-fix.meta" "the fixer used the fixer model"
assert_eq "$(ls "$SANDBOX/exports")" "1" "exports/1 exists"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 5; then
section "5. an unfixable error blocks the idea and the runner continues"
sandbox_init --with-pipeline
fake_claude_on
install_stage unfixable 10-build
printf '{%s}\n{%s}\n' "$IDEA_A" "$IDEA_B" > "$SANDBOX/ideas.txt"
export FAKE_CLAUDE_REVIEW=no REELS_DUMMY="$(dummy_except 10-build)"
runner_bg "$SANDBOX/block.out" --once
OUT="$SANDBOX/block.out"
if wait_for "BLOCK  idea" "$SANDBOX/logs/runner.log" 120; then
  mkdir -p "$SANDBOX/library/keys" && printf 'the key\n' > "$SANDBOX/library/keys/service.key"   # the user fixes it before idea B
  pass "the first idea is blocked"
else
  fail "no BLOCK line within 120 s"; cat "$OUT"
fi
wait $RUNNER_JOB 2>/dev/null; rc=$?
assert_rc 0 $rc "the runner continues past the block and exits 0 when the queue is empty"
assert_grep "${ts_regex}ERROR  S10 building visuals: $KEY_ERROR$" "$OUT" "ERROR line"
assert_grep "${ts_regex}BLOCK  idea \"Idea A: the gh CLI in 60 seconds, three ...\" blocked at S10: environment problem: fake reviewer: .*Needs you: create library/keys/service.key with your API key \(fake reviewer\)\. Moved to logs/blocked.txt$" "$OUT" "BLOCK line with the class, the root cause and what the user must do"
assert_grep "${ts_regex}NEXT   idea 2/2 \"Idea B" "$OUT" "NEXT after the block"
assert_grep "${ts_regex}DONE   exported #1" "$OUT" "the next idea is exported once the key exists"
assert_not_grep "${ts_regex}(FIXED|ESCAL|STOP) " "$OUT" "no fix, no escalation, no stop"
assert_grep "^# 20[0-9-]+ [0-9:]+ \| blocked at S10 \| environment problem: .* \| runs/" "$SANDBOX/logs/blocked.txt" "blocked.txt: the reason line"
assert_grep "^\{$IDEA_A\}$" "$SANDBOX/logs/blocked.txt" "blocked.txt: the idea in braces"
assert_grep "\| $IDEA_A \| (-|external) \| blocked: environment problem: " "$SANDBOX/logs/history.txt" "history: the blocked line (with the solution field, M12)"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt is empty"
RD="$(run_dirs | head -n 1)"
assert_eq "$(state_get "$RD" status)" "blocked" "the run folder is kept with status blocked"
assert_file "$RD/errors/E1.md" "E1.md kept"
assert_grep "^## auto_apply: no$" "$RD/fixes/F1.md" "F1.md says auto_apply no"
assert_grep "^User action: create library/keys/service.key" "$RD/fixes/F1.md" "F1.md carries the user action"
assert_grep '"outcome": "no_auto"' "$RD/fixes/F1.result.json" "the cycle's outcome is no_auto"
assert_eq "$(fake_roles)" "reviewer:$(python -c 'import json; print(json.load(open("config.json"))["models"]["reviewer"]["model"])')" "one reviewer call, no fixer call"
assert_eq "$(fake_field 1 tools)" '["Read,Glob,Grep,WebSearch,WebFetch"]' "the reviewer has read-only tools plus WebSearch and WebFetch"
assert_eq "$(fake_field 1 schema)" "True" "the reviewer answers with a JSON schema"
assert_eq "$(fake_field 1 cwd)" "$SANDBOX_M" "the reviewer runs in the repo root (the sandbox)"
assert_true "the reviewer prompt holds the error report" grep -q "^# Role: reviewer" <<<"$(fake_field 1 prompt_head)"
assert_grep "^## Known issues" "$RD/errors/E1.prompt.md" "the reviewer prompt includes known-issues.md"
assert_no_file "$SANDBOX/logs/.block-streak" "the export reset the block streak"
unset FAKE_CLAUDE_REVIEW REELS_DUMMY
fi

# ----------------------------------------------------------------------------------------------------------------
if want 6; then
section "6. the caps: the repeated-signature rule and the escalation, with fake fixes"
sandbox_init --with-pipeline
fake_claude_on
install_stage unfixable 10-build
printf '{%s}\n' "$IDEA_C" > "$SANDBOX/ideas.txt"
head_before="$(git -C "$SANDBOX" rev-parse HEAD)"
run_once "$SANDBOX/escal.out" FAKE_CLAUDE_REVIEW=yes FAKE_CLAUDE_FIX=ok REELS_DUMMY="$(dummy_except 10-build)"; rc=$?
OUT="$SANDBOX/escal.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner exits 0 after blocking the idea"
assert_eq "$(grep -c -E "${ts_regex}ERROR  S10 building visuals: " "$OUT")" "3" "three failures of the stage (the original, after the fix, after the escalated fix)"
assert_eq "$(grep -c -E "${ts_regex}FIXED  S10: fake fix for 10-build \(nothing changed\) \(commit [0-9a-f]{7,}\), restarting stage$" "$OUT")" "2" "two FIXED lines with commits"
assert_grep "${ts_regex}ESCAL  S10 still failing after 1 review, escalating to $ESCALATION$" "$OUT" "ESCAL after one review: the repeated signature skips the remaining Opus cycles"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 2 after the fix$" "$OUT" "attempt 2 after the first fix"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 3 after the fix$" "$OUT" "attempt 3 after the escalated fix"
assert_grep "${ts_regex}BLOCK  idea \"Idea C.*\" blocked at S10: still failing after 1 review cycle and the escalated review: $KEY_ERROR\. Moved to logs/blocked.txt$" "$OUT" "BLOCK after the escalation failed"
assert_true "the order is ERROR, FIXED, ERROR, ESCAL, FIXED, ERROR, BLOCK" python -c '
import re, sys
tags = [m.group(1) for m in re.finditer(r"^\[\d\d:\d\d\] (ERROR|FIXED|ESCAL|BLOCK) ", open(sys.argv[1], encoding="utf-8").read(), re.M)]
sys.exit(0 if tags == ["ERROR", "FIXED", "ERROR", "ESCAL", "FIXED", "ERROR", "BLOCK"] else 1)' "$OUT"
assert_eq "$(fake_roles)" "reviewer:$REVIEWER,fixer:$FIXER,reviewer:$ESCALATION,fixer:$FIXER" "reviewer, fixer, escalation reviewer, fixer, with the models from config"
assert_eq "$(fake_field 2 tools)" '["Read,Glob,Grep,Edit,Write,Bash"]' "the fixer's tools"
assert_true "the fixer may edit pipeline/ and motion-lib/candidates/ only" grep -q 'Edit(pipeline/\*\*).*Edit(motion-lib/candidates/\*\*)' <<<"$(fake_field 2 allowed)"
assert_true "the fixer prompt is the fixer role" grep -q "^# Role: fixer" <<<"$(fake_field 2 prompt_head)"
assert_file "$RD/errors/E1.md" "E1.md"
assert_file "$RD/errors/E2.md" "E2.md"
assert_grep "^### E1.md \(the first 40 lines" "$RD/errors/E2.md" "E2 includes the previous error file"
assert_grep "^### F1.md$" "$RD/errors/E2.md" "E2 includes the previous fix file"
assert_grep "^## Escalation$" "$RD/errors/E2.prompt.md" "the escalation reviewer gets the escalation note"
assert_eq "$(git -C "$SANDBOX" log --format=%s "$head_before..HEAD" | grep -c '^autofix(10-build): ')" "2" "two autofix commits"
assert_eq "$(grep -c '^- ' "$SANDBOX/pipeline/knowledge/known-issues.md")" "2" "two known-issues lines"
assert_eq "$(state_get "$RD" errors.10-build.cycles)" "1" "state: one Opus cycle"
assert_eq "$(state_get "$RD" errors.10-build.escalated)" "true" "state: escalated"
assert_eq "$(state_get "$RD" errors.10-build.repeats)" "3" "state: the signature repeated three times"
assert_eq "$(state_get "$RD" issues.fixed)" "2" "state: two issues fixed"
assert_eq "$(state_get "$RD" issues.open)" "1" "state: one issue open"
assert_grep "^Fix F2 applied" "$RD/10-build/restart-note.md" "the last restart note names F2"
assert_file "$SANDBOX/logs/.block-streak" "the block streak file exists after a code-error block"
assert_true "the streak counts 1" grep -q -E '^[0-9a-f]{12} 1 S10$' "$SANDBOX/logs/.block-streak"

# failed verifications use up the three Opus cycles, then the escalation, then the block
sandbox_init --with-pipeline
fake_claude_on
install_stage unfixable 10-build
printf '{%s}\n' "$IDEA_C" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/verify.out" FAKE_CLAUDE_REVIEW=verify-fails FAKE_CLAUDE_FIX=ok REELS_DUMMY="$(dummy_except 10-build)"; rc=$?
OUT="$SANDBOX/verify.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner exits 0"
assert_eq "$(grep -c -E "${ts_regex}WARN   S10: review cycle E[0-9]+ \((opus|fable|$REVIEWER|$ESCALATION)\) did not fix it: verify command failed \(exit 1\)" "$OUT")" "4" "four failed cycles (three Opus, one escalation), each with a WARN"
assert_grep "${ts_regex}ESCAL  S10 still failing after 3 reviews, escalating to $ESCALATION$" "$OUT" "ESCAL after the three Opus cycles"
assert_grep "${ts_regex}BLOCK  idea \"Idea C.*\" blocked at S10: still failing after 3 review cycles and the escalated review: " "$OUT" "BLOCK after the escalation"
assert_eq "$(grep -c -E "${ts_regex}ERROR  " "$OUT")" "1" "the stage ran once: a failed verification does not restart it"
assert_not_grep "${ts_regex}FIXED  " "$OUT" "no FIXED line"
for k in 1 2 3 4; do assert_file "$RD/fixes/F$k.verify.log" "F$k.verify.log exists"; done
assert_grep '"outcome": "failed"' "$RD/fixes/F4.result.json" "F4: outcome failed"
assert_grep "^### F3 verify log" "$RD/errors/E4.md" "E4 carries the earlier verify logs"
assert_eq "$(git -C "$SANDBOX" log --format=%s | grep -c '^autofix')" "0" "no autofix commit when nothing verified"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 7; then
section "7. three identical blocks in a row stop the runner with STOPPED.md"
sandbox_init --with-pipeline
fake_claude_on
install_stage unfixable 10-build
printf '{%s}\n{%s}\n{%s}\n{%s}\n' "$IDEA_A" "$IDEA_B" "$IDEA_C" "$IDEA_D" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/stop.out" FAKE_CLAUDE_REVIEW=no REELS_DUMMY="$(dummy_except 10-build)"; rc=$?
OUT="$SANDBOX/stop.out"
assert_rc 3 $rc "the runner stops with exit 3"
assert_eq "$(grep -c -E "${ts_regex}BLOCK  " "$OUT")" "3" "three BLOCK lines"
assert_grep "${ts_regex}STOP   systemic failure: the same error blocked 3 ideas in a row at S10: environment problem: .*\. See logs/STOPPED.md$" "$OUT" "STOP line"
assert_not_grep "${ts_regex}START  idea 4/4" "$OUT" "the fourth idea is never started"
assert_file "$SANDBOX/logs/STOPPED.md" "STOPPED.md written"
assert_grep "^# Runner stopped: the same error blocked 3 ideas in a row at S10" "$SANDBOX/logs/STOPPED.md" "STOPPED.md title"
assert_grep "^- the same error blocked 3 ideas in a row at S10: environment problem: fake reviewer: " "$SANDBOX/logs/STOPPED.md" "STOPPED.md diagnosis names the error"
assert_grep "^1\. Read the reviewer's verdicts in runs/.*/fixes/F\*\.md" "$SANDBOX/logs/STOPPED.md" "STOPPED.md fix 1: the verdicts"
assert_grep "^2\. Fix the cause yourself" "$SANDBOX/logs/STOPPED.md" "STOPPED.md fix 2: fix the cause"
assert_grep "^3\. Re-add the blocked ideas: paste the braces from logs/blocked.txt" "$SANDBOX/logs/STOPPED.md" "STOPPED.md fix 3: re-add the ideas"
assert_grep "^Then start the runner again: bash run.sh$" "$SANDBOX/logs/STOPPED.md" "STOPPED.md footer"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "1" "the fourth idea stays in ideas.txt"
assert_eq "$(grep -c '^{' "$SANDBOX/logs/blocked.txt")" "3" "blocked.txt holds the three ideas"
assert_no_file "$SANDBOX/logs/.block-streak" "the streak is cleared by the stop"
assert_eq "$(grep -c -E "${ts_regex}(ERROR) " "$OUT")" "3" "one ERROR per idea"
assert_grep "^\[[0-9:]+\] STOP   systemic failure: the same error blocked 3 ideas" "$SANDBOX/logs/status.txt" "status.txt holds the STOP line"
status_out="$(cd "$SANDBOX" && bash "$SANDBOX/pipeline/bin/runner-status" 3)"
assert_true "runner-status mentions STOPPED.md and the blocked ideas" grep -q "STOPPED: logs/STOPPED.md exists" <<<"$status_out"
assert_true "runner-status counts the blocked ideas" grep -q "^blocked: 3 idea" <<<"$status_out"
assert_eq "$(ls "$SANDBOX/runs" | wc -l | tr -d ' ')" "3" "three run folders kept"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 8; then
section "8. the guards: treeguard.py around the fixer, protect.py around every call"
sandbox_init --with-pipeline
TG="$REPO_DIR/pipeline/lib/treeguard.py"
printf 'user work\n' > "$SANDBOX/notes.txt"                           # untracked, there before the call
printf 'user edit\n' >> "$SANDBOX/run.sh"                              # tracked, modified by the user before the call
python "$TG" snapshot --repo "$SANDBOX_M" --dir "$SANDBOX_M/.tg" --allow pipeline --allow motion-lib/candidates >/dev/null
assert_true "treeguard: a clean check exits 0" python "$TG" check --repo "$SANDBOX_M" --dir "$SANDBOX_M/.tg"
printf 'log line\n' >> "$SANDBOX/notes.txt"                            # grows during the call: left alone
printf 'fixer edit\n' >> "$SANDBOX/run.sh"                             # the fixer edited the user's modified file: back to the user's version
printf 'new\n' > "$SANDBOX/stray.txt"                                  # created by the fixer outside: deleted
printf 'fixer edit\n' >> "$SANDBOX/styles/paper-cards/style.md"        # clean tracked file edited by the fixer: back to HEAD
printf 'inside\n' >> "$SANDBOX/pipeline/knowledge/known-issues.md"     # inside the allowed paths: kept
out="$(python "$TG" check --repo "$SANDBOX_M" --dir "$SANDBOX_M/.tg" --restore)"; rc=$?
assert_rc 1 $rc "treeguard: changes outside the allowed paths are reported (exit 1)"
assert_eq "$(paste -sd, "$SANDBOX/notes.txt")" "user work,log line" "treeguard: a pre-existing untracked file that grew during the call is left alone"
assert_eq "$(tail -n 1 "$SANDBOX/run.sh")" "user edit" "treeguard: the user's own change to a tracked file survives, the fixer's edit on top of it is undone"
assert_no_file "$SANDBOX/stray.txt" "treeguard: a file the fixer created outside is deleted"
assert_eq "$(git -C "$SANDBOX" status --porcelain -- styles/paper-cards/style.md)" "" "treeguard: a clean tracked file edited by the fixer goes back to HEAD"
assert_grep "^inside$" "$SANDBOX/pipeline/knowledge/known-issues.md" "treeguard: changes inside pipeline/ are kept"
assert_true "treeguard: the report names what was left alone" grep -q '"left": \["notes.txt"\]' <<<"$out"
assert_true "treeguard: the report names what was put back" grep -q '"restored": \[' <<<"$out"
PR="$REPO_DIR/pipeline/lib/protect.py"
printf '{an idea}\n' > "$SANDBOX/ideas.txt"
mkdir -p "$SANDBOX/exports/1"; printf 'reel\n' > "$SANDBOX/exports/1/1.mp4"
python "$PR" snapshot --root "$SANDBOX_M" --repo "$SANDBOX_M" --dir "$SANDBOX_M/.pr" >/dev/null
assert_true "protect: a clean check exits 0" python "$PR" check --root "$SANDBOX_M" --repo "$SANDBOX_M" --dir "$SANDBOX_M/.pr"
printf '{another}\n' >> "$SANDBOX/ideas.txt"                           # the model appended an idea
printf 'x\n' > "$SANDBOX/library/profile/new.txt"                      # the model created a profile file
printf 'x\n' >> "$SANDBOX/styles/paper-cards/style.md"                 # the model edited the style
rm -f "$SANDBOX/library/hooks.txt"                                     # the model deleted the hooks
printf 'bad\n' > "$SANDBOX/exports/1/extra.txt"                         # the model wrote into an export
out="$(python "$PR" check --root "$SANDBOX_M" --repo "$SANDBOX_M" --dir "$SANDBOX_M/.pr" --restore)"; rc=$?
assert_rc 1 $rc "protect: changes to protected files are reported (exit 1)"
assert_eq "$(cat "$SANDBOX/ideas.txt")" "{an idea}" "protect: ideas.txt is restored"
assert_no_file "$SANDBOX/library/profile/new.txt" "protect: a new file under library/ is removed"
assert_file "$SANDBOX/library/hooks.txt" "protect: a deleted library file is restored"
assert_eq "$(git -C "$SANDBOX" status --porcelain -- styles/paper-cards/style.md)" "" "protect: style.md is restored"
assert_true "protect: the exports change is reported (not restored)" grep -q '"exports_changed": true' <<<"$out"
assert_true "protect: the report names the changed files" grep -q '"changed": \["root/ideas.txt", "repo/styles/paper-cards/style.md"\]' <<<"$out"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 9; then
section "9. a failed stage script is classified: transient retries, a usage limit, then the code error"
# a network reset twice, then success: two RETRY lines, no ERROR, no reviewer call
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/flaky.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=reset FLAKY_FAILS=2; rc=$?
OUT="$SANDBOX/flaky.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner exports the idea after two temporary failures of the stage"
assert_grep "${ts_regex}RETRY  temporary error \(connection reset\), retrying in 60s \(try 1/3\)$" "$OUT" "RETRY 1: 60 s"
assert_grep "${ts_regex}RETRY  temporary error \(connection reset\), retrying in 4m \(try 2/3\)$" "$OUT" "RETRY 2: 4 min"
assert_eq "$(grep -c "fast-forward: skipping a .* wait (transient backoff)" "$OUT")" "2" "two scaled backoff waits (fast-forward)"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 2 after the temporary error$" "$OUT" "the first rerun is announced"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 3 after the temporary error$" "$OUT" "the second rerun too"
assert_not_grep "${ts_regex}(ERROR|BLOCK|FIXED|ESCAL) " "$OUT" "no ERROR: a temporary error is retried, not reviewed"
assert_grep "${ts_regex}STEP   building visuals done" "$OUT" "the stage passes on the third attempt"
assert_grep "${ts_regex}DONE   exported #1" "$OUT" "the idea is exported"
assert_eq "$(fake_calls)" "0" "no model call at all: the reviewer was never asked"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "3" "state: three attempts of the stage"
assert_eq "$(state_get "$RD" errors.10-build.transient_tries)" "0" "state: the transient counter is reset by the success"
assert_eq "$(state_get "$RD" issues.open)" "0" "state: no open issue"
assert_eq "$(state_get "$RD" issues.fixed)" "0" "state: nothing fixed"

# the same stage failing four times: the fourth failure is a code error with one review cycle
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_B" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/flaky4.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=reset FLAKY_FAILS=9 FAKE_CLAUDE_REVIEW=no; rc=$?
OUT="$SANDBOX/flaky4.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner blocks the idea on the reviewer's verdict and exits 0"
assert_eq "$(grep -c -E "${ts_regex}RETRY  " "$OUT")" "3" "three RETRY lines (60 s, 4 min, 16 min)"
assert_grep "${ts_regex}RETRY  temporary error \(connection reset\), retrying in 16m \(try 3/3\)$" "$OUT" "RETRY 3: 16 min"
assert_grep "${ts_regex}ERROR  S10 building visuals: temporary error persisted after 3 retries \(connection reset\): exit 1: .*ECONNRESET" "$OUT" "the fourth failure is a code error"
assert_eq "$(grep -c -E "${ts_regex}ERROR  " "$OUT")" "1" "one ERROR line"
assert_grep "${ts_regex}BLOCK  idea \"Idea B.*\" blocked at S10: environment problem: fake reviewer: temporary error persisted" "$OUT" "then the review loop: the reviewer's verdict blocks the idea"
assert_eq "$(fake_roles)" "reviewer:$REVIEWER" "one reviewer call, after the retries"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "4" "state: four attempts"
assert_eq "$(state_get "$RD" errors.10-build.transient_tries)" "0" "state: the counter is reset when the error goes to review"
assert_grep "^- error: temporary error persisted after 3 retries \(connection reset\)" "$RD/errors/E1.md" "E1.md names the persisted temporary error"
assert_true "the order is RETRY, RETRY, RETRY, ERROR, BLOCK" python -c '
import re, sys
tags = [m.group(1) for m in re.finditer(r"^\[\d\d:\d\d\] (RETRY|ERROR|BLOCK|FIXED|ESCAL) ", open(sys.argv[1], encoding="utf-8").read(), re.M)]
sys.exit(0 if tags == ["RETRY", "RETRY", "RETRY", "ERROR", "BLOCK"] else 1)' "$OUT"

# a usage limit printed by a stage script: LIMIT, the wait, RESUME, the stage again, no review, no model call
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_C" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/flakylimit.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=limit FLAKY_FAILS=1; rc=$?
OUT="$SANDBOX/flakylimit.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner exports the idea after the limit"
assert_grep "${ts_regex}LIMIT  session limit hit, resuming at ([0-9]{2}:[0-9]{2}|[A-Z][a-z]{2} [0-9]{2}:[0-9]{2}) \(\+2 min margin\)$" "$OUT" "LIMIT line from the stage's message"
assert_grep "${ts_regex}INFO   fast-forward: skipping the wait until " "$OUT" "the wait until the reset plus the margin (fast-forward)"
assert_grep "${ts_regex}RESUME limit reset, continuing: building visuals$" "$OUT" "RESUME names the stage's activity"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 2 after the usage limit$" "$OUT" "the rerun is announced"
assert_not_grep "${ts_regex}(ERROR|RETRY|BLOCK) " "$OUT" "a limit is never an error"
assert_grep "${ts_regex}DONE   exported #1" "$OUT" "exported"
assert_eq "$(fake_calls)" "0" "no reviewer call, no probe"
assert_grep "\| session limit \| reset .* \| waiting until .* \(reset \+ 120 s\) \| \"You've hit your session limit" "$SANDBOX/logs/limits.log" "limits.log has the wait with the stage's message"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "2" "state: two attempts"

# a stage whose own model call failed (ai() wrote error.json) is not classified again: the log tail looks
# transient, but ai() already classified and retried that call; the runner goes straight to the review
sandbox_init --with-pipeline
fake_claude_on
install_stage aicall 10-build
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
printf 'error:Boom happened in the model call\nreview:no\n' > "$SANDBOX/script.txt"
run_once "$SANDBOX/aierr.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" \
  AICALL_FAIL_NOTE="note: the fetch failed with ECONNRESET right after the model call"; rc=$?
OUT="$SANDBOX/aierr.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner blocks the idea and exits 0"
assert_not_grep "${ts_regex}RETRY  " "$OUT" "no RETRY: the model call's error was classified by ai() already (error.json)"
assert_grep "${ts_regex}ERROR  S10 building visuals: exit 1: note: the fetch failed with ECONNRESET right after the model call$" "$OUT" "ERROR at once, with the last log line"
assert_grep "${ts_regex}BLOCK  idea \"Idea A.*\" blocked at S10: " "$OUT" "then the reviewer's block"
assert_eq "$(fake_roles)" "call:haiku,reviewer:$REVIEWER" "the stage's own call, then one reviewer call"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "1" "state: the stage ran once"
assert_grep "^## Model call error \(10-build/error.json\)" "$RD/errors/E1.md" "E1.md carries the model call's error.json"
assert_grep '"message": "Boom happened in the model call"' "$RD/10-build/error.json" "error.json is this attempt's"

# the limit path is bounded (M3 review 2, fix 1): a stage that prints the same limit message again right after the
# wait it earned is a code error for the review loop, not another wait (and never a loop forever)
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/limitloop.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=limit FLAKY_FAILS=99 FAKE_CLAUDE_REVIEW=no; rc=$?
OUT="$SANDBOX/limitloop.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner ends on its own: the persisted limit message reaches the review and the block"
assert_eq "$(grep -c -E "${ts_regex}LIMIT  " "$OUT")" "1" "one LIMIT line: the first limit message gets its wait"
assert_grep "${ts_regex}RESUME limit reset, continuing: building visuals$" "$OUT" "RESUME after the wait"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 2 after the usage limit$" "$OUT" "the rerun is announced"
assert_grep "${ts_regex}ERROR  S10 building visuals: usage limit message persisted after 1 wait \(the same message right after the reset it named\): exit 1: You've hit your session limit .* resets 3pm$" "$OUT" "the same message after its wait is a code error naming the persisted limit"
assert_eq "$(grep -c -E "${ts_regex}ERROR  " "$OUT")" "1" "one ERROR line"
assert_grep "${ts_regex}BLOCK  idea \"Idea A.*\" blocked at S10: environment problem: fake reviewer: usage limit message persisted" "$OUT" "the reviewer's verdict blocks the idea"
assert_eq "$(fake_roles)" "reviewer:$REVIEWER" "one reviewer call, no probe (the reset time was parsed)"
assert_eq "$(event_tags "$OUT")" "LIMIT,RESUME,ERROR,BLOCK" "the order is LIMIT, RESUME, ERROR, BLOCK"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "2" "state: two attempts"
assert_eq "$(state_get "$RD" errors.10-build.limit_tries)" "0" "state: the limit counter is reset when the error goes to review"
assert_grep "^- error: usage limit message persisted after 1 wait" "$RD/errors/E1.md" "E1.md names the persisted limit message"
assert_grep "resets 3pm" "$RD/errors/E1.md" "E1.md shows the stage's limit line to the reviewer"

# a limit message that changes at every attempt (a new reset time each time) gets errors.script_limit_retries
# waits (2), then the next one is a code error
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_B" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/limitcap.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=limit-new FLAKY_FAILS=99 FAKE_CLAUDE_REVIEW=no; rc=$?
OUT="$SANDBOX/limitcap.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner ends on its own after the capped waits"
assert_eq "$(grep -c -E "${ts_regex}LIMIT  " "$OUT")" "2" "two LIMIT lines: the cap errors.script_limit_retries"
assert_grep "${ts_regex}INFO   S10 building visuals: attempt 3 after the usage limit$" "$OUT" "the second rerun is announced"
assert_grep "${ts_regex}ERROR  S10 building visuals: usage limit message persisted after 2 waits: exit 1: You've hit your session limit .* resets 5pm$" "$OUT" "the third limit message is a code error"
assert_eq "$(fake_roles)" "reviewer:$REVIEWER" "one reviewer call"
assert_grep "${ts_regex}BLOCK  idea \"Idea B.*\" blocked at S10: " "$OUT" "BLOCK on the reviewer's verdict"
assert_eq "$(event_tags "$OUT")" "LIMIT,RESUME,LIMIT,RESUME,ERROR,BLOCK" "the order is LIMIT, RESUME, LIMIT, RESUME, ERROR, BLOCK"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "3" "state: three attempts"
assert_eq "$(grep -c "session limit | reset" "$SANDBOX/logs/limits.log")" "2" "limits.log has the two waits"

# a log line that quotes a usage limit ("hit its usage limit, it resets weekly") before a real exception: the
# unparsed limit gets its sleep and the probe (which answers at once), the rerun prints the same text, and that is
# a code error with one review, not a probe loop every 30 minutes forever
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_C" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/quoted.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=quoted-limit FLAKY_FAILS=99 FAKE_CLAUDE_REVIEW=no; rc=$?
OUT="$SANDBOX/quoted.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner ends on its own"
assert_eq "$(grep -c -E "${ts_regex}LIMIT  " "$OUT")" "1" "one LIMIT line: the quoted limit is waited out once"
assert_grep "${ts_regex}LIMIT  weekly limit hit but no reset time found, probing every 30 min \(first probe in 30 min\)$" "$OUT" "an unparsed weekly limit enters the probe loop"
assert_grep "${ts_regex}RESUME limit is over \(probe 1 answered\), continuing: building visuals$" "$OUT" "the probe answered at once"
assert_grep "${ts_regex}ERROR  S10 building visuals: usage limit message persisted after 1 wait \(the same message, and the probe model had answered at once\): exit 1: json.decoder.JSONDecodeError: Expecting value: line 1 column 1 \(char 0\)$" "$OUT" "the same quoted text after the probe is a code error"
assert_not_grep "${ts_regex}RETRY  " "$OUT" "no RETRY: the traceback is a code error, not a temporary error"
assert_eq "$(fake_roles)" "call:$PROBE,reviewer:$REVIEWER" "the probe call, then one reviewer call"
assert_grep "${ts_regex}BLOCK  idea \"Idea C.*\" blocked at S10: " "$OUT" "BLOCK on the reviewer's verdict"
assert_eq "$(event_tags "$OUT")" "LIMIT,RESUME,ERROR,BLOCK" "the order is LIMIT, RESUME, ERROR, BLOCK"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "2" "state: two attempts"
assert_grep "resets weekly" "$RD/errors/E1.md" "E1.md shows the quoted line to the reviewer"

# a traceback whose frames echo a source line with "timeout=600" (M3 review 2, fix 2) is a code error at once: no
# RETRY ladder, ERROR with the exception line, one review
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/trace.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=traceback FLAKY_FAILS=99 FAKE_CLAUDE_REVIEW=no; rc=$?
OUT="$SANDBOX/trace.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner ends on its own"
assert_not_grep "${ts_regex}(RETRY|LIMIT) " "$OUT" "no RETRY and no LIMIT: an echoed source line is not an error message"
assert_grep "${ts_regex}ERROR  S10 building visuals: exit 1: KeyError: 'beatz'$" "$OUT" "ERROR at once, with the exception line"
assert_eq "$(fake_roles)" "reviewer:$REVIEWER" "one reviewer call"
assert_grep "${ts_regex}BLOCK  idea \"Idea A.*\" blocked at S10: " "$OUT" "BLOCK on the reviewer's verdict"
assert_eq "$(event_tags "$OUT")" "ERROR,BLOCK" "the order is ERROR, BLOCK"
assert_eq "$(state_get "$RD" stages.10-build.attempts)" "1" "state: the stage ran once (no transient retry)"
assert_eq "$(state_get "$RD" errors.10-build.transient_tries 0)" "0" "state: no transient try"

# the Claude CLI's network message on this PC holds an em dash (M3 review 3, fix 2): the stage prints it at every
# attempt (transient: three retries, then the code error and the review), and no line or file the runner composes
# keeps the dash, while the verbatim log excerpt inside E1.md may
sandbox_init --with-pipeline
fake_claude_on
install_stage flaky 10-build
printf '{%s}\n' "$IDEA_B" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/netdash.out" REELS_DUMMY="$(dummy_except 10-build)" REELS_SLEEP_SCALE=0 FLAKY_MODE=netdash FLAKY_FAILS=99 FAKE_CLAUDE_REVIEW=no; rc=$?
OUT="$SANDBOX/netdash.out"
RD="$(run_dirs | head -n 1)"
assert_rc 0 $rc "the runner ends on its own"
assert_eq "$(grep -c -E "${ts_regex}RETRY  temporary error \(network error\)" "$OUT")" "3" "three RETRY lines name the network error"
assert_grep "${ts_regex}ERROR  S10 building visuals: temporary error persisted after 3 retries \(network error\): exit 1: API Error: Can't reach the API server, check your internet or DNS \(ENOTFOUND\)$" "$OUT" "the ERROR line reads the message with a comma where the CLI had the em dash"
assert_grep "${ts_regex}BLOCK  idea \"Idea B.*\" blocked at S10: environment problem: fake reviewer: temporary error persisted after 3 retries \(network error\): exit 1: API Error: Can't reach the API server, check your int" "$OUT" "the BLOCK line too (the fake reviewer quotes the first 120 characters of the error line)"
assert_eq "$(event_tags "$OUT")" "RETRY,RETRY,RETRY,ERROR,BLOCK" "the order is RETRY, RETRY, RETRY, ERROR, BLOCK"
assert_eq "$(fake_roles)" "reviewer:$REVIEWER" "one reviewer call after the retries"
assert_true "the stage really printed the em dash (stage.log holds U+2014)" python -c 'import sys; sys.exit(0 if bytes([0xE2, 0x80, 0x94]) in open(sys.argv[1], "rb").read() else 1)' "$RD/10-build/stage.log"
for f in "$OUT" "$SANDBOX/logs/runner.log" "$SANDBOX/logs/status.txt" "$SANDBOX/logs/history.txt" "$SANDBOX/logs/blocked.txt" \
         "$RD/state.json" "$RD/errors/E1.msg" "$RD/fixes/F1.md" "$RD/fixes/F1.result.json"; do
  assert_true "no U+2014 in $(basename "$f")" python -c 'import sys; sys.exit(1 if bytes([0xE2, 0x80, 0x94]) in open(sys.argv[1], "rb").read() else 0)' "$f"
done
assert_true "no U+2014 in the error line of E1.md" python -c '
import sys
line = next((l for l in open(sys.argv[1], "rb").read().split(b"\n") if l.startswith(b"- error: ")), b"")
sys.exit(1 if (not line or bytes([0xE2, 0x80, 0x94]) in line) else 0)' "$RD/errors/E1.md"
assert_grep "^- error: temporary error persisted after 3 retries \(network error\): exit 1: API Error: Can't reach the API server, check your internet or DNS \(ENOTFOUND\)$" "$RD/errors/E1.md" "E1.md's error line reads the cleaned message"
assert_true "E1.md still shows the stage's verbatim line to the reviewer (U+2014 in the log excerpt)" python -c 'import sys; sys.exit(0 if bytes([0xE2, 0x80, 0x94]) in open(sys.argv[1], "rb").read() else 1)' "$RD/errors/E1.md"
assert_grep "blocked: environment problem: fake reviewer: temporary error persisted after 3 retries \(network error\): exit 1: API Error: Can't reach the API server, check your int" "$SANDBOX/logs/history.txt" "history.txt has the cleaned reason"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 10; then
section "10. a runner killed during a review cycle: the restart resumes the cycle, no Opus cycle lost"
# (a) the whole process tree dies while the reviewer call hangs: the restart runs the same cycle E1 as cycle 1/3
sandbox_init --with-pipeline
fake_claude_on
install_stage unfixable 10-build
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
export REELS_DUMMY="$(dummy_except 10-build)"
FAKE_CLAUDE_MODE=hang runner_bg "$SANDBOX/rkill1.out" --once
if wait_for '"role": "reviewer"' "$FAKE_CLAUDE_LOG" 120; then
  RD="$(run_dirs | head -n 1)"
  wait_for '^[0-9]+' "$RD/errors/E1.pid" 10
  cycle_pid="$(cut -d' ' -f1 "$RD/errors/E1.pid" 2>/dev/null)"
  lp="$(lock_pid)"
  kill_tree "$lp"; kill -9 $RUNNER_JOB 2>/dev/null
  wait $RUNNER_JOB 2>/dev/null
  wait_gone "$lp" 10
  assert_false "the runner is dead after SIGKILL" ps -p "$lp"
  assert_false "the review cycle child is dead too" ps -p "${cycle_pid:-0}"
  assert_eq "$(state_get "$RD" stages.10-build.status)" "failed" "state: the stage had failed (under review) when killed"
  assert_eq "$(state_get "$RD" errors.10-build.review.active)" "true" "state: the review loop was active"
  assert_eq "$(state_get "$RD" errors.10-build.pending)" "1" "state: cycle E1 was pending"
  assert_eq "$(state_get "$RD" errors.10-build.cycles 0)" "0" "state: no cycle recorded yet"
  assert_file "$RD/errors/E1.pid" "the cycle's pid file is left behind by the kill"
  run_once "$SANDBOX/rkill2.out" FAKE_CLAUDE_REVIEW=no; rc=$?
  OUT="$SANDBOX/rkill2.out"
  assert_rc 0 $rc "the restarted runner blocks the idea on the reviewer's verdict and exits 0"
  assert_grep "${ts_regex}START  idea 1/1 \"Idea A.*\" -> runs/$(basename "$RD") \(resumed at building visuals, " "$OUT" "START says where it resumes"
  assert_grep "${ts_regex}INFO   S10 building visuals: review cycle E1 \(cycle 1/3, $REVIEWER\) was interrupted by the previous runner, resuming it: $KEY_ERROR$" "$OUT" "the restart resumes cycle E1 as cycle 1/3 with the Opus reviewer"
  assert_not_grep "${ts_regex}(ESCAL|ERROR|RETRY|FIXED) " "$OUT" "no ESCAL before an Opus cycle, no second ERROR: the stage did not run again"
  assert_not_grep "after the fix" "$OUT" "no 'after the fix' line: nothing was fixed"
  assert_grep "${ts_regex}BLOCK  idea \"Idea A.*\" blocked at S10: environment problem: fake reviewer: " "$OUT" "BLOCK on the resumed cycle's verdict"
  assert_eq "$(fake_roles)" "reviewer:$REVIEWER,reviewer:$REVIEWER" "the hung reviewer call, then the resumed cycle's reviewer call, both with the Opus reviewer"
  assert_eq "$(state_get "$RD" errors.10-build.cycles)" "1" "state: one Opus cycle in all"
  assert_eq "$(state_get "$RD" errors.10-build.repeats)" "1" "state: the signature was counted once"
  assert_eq "$(state_get "$RD" errors.10-build.escalated false)" "false" "state: no escalation"
  assert_eq "$(state_get "$RD" issues.open)" "1" "state: one open issue, not two"
  assert_eq "$(state_get "$RD" stages.10-build.attempts)" "1" "state: the stage ran once"
  assert_eq "$(state_get "$RD" errors.10-build.pending)" "" "state: nothing pending after the verdict"
  assert_no_file "$RD/errors/E1.pid" "the cycle's pid file is removed"
  assert_no_file "$RD/errors/E2.md" "no E2: the interrupted cycle kept its number"
  assert_grep '"outcome": "no_auto"' "$RD/fixes/F1.result.json" "F1.result.json holds the verdict"
  assert_grep "^# 20[0-9-]+ [0-9:]+ \| blocked at S10 \| environment problem: " "$SANDBOX/logs/blocked.txt" "blocked.txt has the idea"
else
  fail "the reviewer call never started (see $SANDBOX/rkill1.out)"; cat "$SANDBOX/rkill1.out"
  kill_tree "$(lock_pid)"; kill -9 $RUNNER_JOB 2>/dev/null
fi

# (b) only the runner dies: its review-cycle child keeps working, the restart adopts it and takes its verdict
sandbox_init --with-pipeline
fake_claude_on
install_stage unfixable 10-build
printf '{%s}\n' "$IDEA_B" > "$SANDBOX/ideas.txt"
FAKE_CLAUDE_DELAY=20 FAKE_CLAUDE_REVIEW=no runner_bg "$SANDBOX/rkill3.out" --once
if wait_for '"role": "reviewer"' "$FAKE_CLAUDE_LOG" 120; then
  RD="$(run_dirs | head -n 1)"
  wait_for '^[0-9]+' "$RD/errors/E1.pid" 10
  cycle_pid="$(cut -d' ' -f1 "$RD/errors/E1.pid" 2>/dev/null)"
  lp="$(lock_pid)"
  kill -9 "$lp" $RUNNER_JOB 2>/dev/null
  wait $RUNNER_JOB 2>/dev/null
  wait_gone "$lp" 10
  assert_true "the review cycle child still runs after the runner died" ps -p "${cycle_pid:-0}"
  run_once "$SANDBOX/rkill4.out" FAKE_CLAUDE_REVIEW=no; rc=$?
  OUT="$SANDBOX/rkill4.out"
  assert_rc 0 $rc "the restarted runner exits 0"
  assert_grep "${ts_regex}WARN   S10: review cycle E1 still runs from the previous runner \(pid $cycle_pid\), waiting for it instead of starting it twice$" "$OUT" "the orphaned cycle is adopted"
  assert_grep "${ts_regex}BLOCK  idea \"Idea B.*\" blocked at S10: environment problem: fake reviewer: " "$OUT" "its verdict blocks the idea"
  assert_eq "$(fake_roles)" "reviewer:$REVIEWER" "one reviewer call in all: the adopted cycle's"
  assert_eq "$(state_get "$RD" errors.10-build.cycles)" "1" "state: one cycle"
  assert_eq "$(state_get "$RD" issues.open)" "1" "state: one open issue"
  assert_not_grep "${ts_regex}(ESCAL|ERROR|FIXED) " "$OUT" "no ESCAL, no second ERROR"
  assert_false "the adopted child has ended" ps -p "$cycle_pid"
  assert_no_file "$RD/errors/E1.pid" "its pid file is removed"
else
  fail "the reviewer call never started (see $SANDBOX/rkill3.out)"; cat "$SANDBOX/rkill3.out"
  kill_tree "$(lock_pid)"; kill -9 $RUNNER_JOB 2>/dev/null
fi
unset REELS_DUMMY
fi

test_summary
