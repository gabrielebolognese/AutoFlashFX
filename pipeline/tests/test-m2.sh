#!/usr/bin/env bash
# test-m2.sh: acceptance test for M2 (Runner core and terminal output). No model calls; dummy stages only.
#   bash pipeline/tests/test-m2.sh
#
# Covers (BUILD_SPEC.md section 12, M2, and PLAN.md M2):
#   1. state.py and export.py units: the stage table, run creation, markers, validation, reopen, the state lock
#      under concurrent writers (flags and counters all land, a writer waits for a holder), numbering, captions
#   2. two dummy ideas end to end: banner, queue listing, START/STEP/DONE/NEXT lines, exports/1 and exports/2 with
#      N.mp4, Ncaptions.txt and Nhook2.mp4, two history lines, an empty ideas.txt, the heartbeat on the scaled
#      schedule with every field, the summary line, status.txt, no escape codes under NO_COLOR
#   3. SIGKILL mid-stage, restart: the same run resumes at the same stage, earlier stages skipped, one export
#   4. a crash planted between assembling and moving the export, and one right after the move: no duplicate, no gap
#   5. drop, code error, FLAG and an invalid output: history, blocked.txt, numbering without gaps. Since M3 a code
#      error goes through the review and fix loop, so this section runs with the fake claude (tests/fakes) whose
#      reviewer answers auto_apply no: the idea is blocked with the reviewer's reason and the runner moves on
#   6. forever mode: IDLE lines, the NEW line from add-idea.sh, a second runner refused, SIGTERM
#   7. a stage that is not built yet stops the runner (STOPPED.md) and keeps the idea; runner-status
#   8. state.json damaged mid-run: one retry, then the systemic stop (ERROR, STOP, STOPPED.md with the run folder
#      and the fix, exit 3, the idea kept), seen at stage-done and at stage-start (through the orphan wait)
# Runtime: about 7 minutes (16 dummy stages cost about 2 s each in runner overhead).
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
fast_mode
export REELS_DUMMY=all REELS_DUMMY_SECONDS=0.1

STATE_PY="$REPO_DIR/pipeline/lib/state.py"
EXPORT_PY="$REPO_DIR/pipeline/lib/export.py"
ADD_IDEA="$REPO_DIR/pipeline/bin/add-idea.sh"
IDEA_A="Idea A: the gh CLI in 60 seconds, three flags that matter"
IDEA_B="Idea B: uv replaces pip, venv and pyenv in one tool, città"
IDEA_C="Idea C: ffmpeg loudnorm in two passes for reels"
RUNNER_JOB=""

ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
REEL_RE="${ts_regex}"'REEL   #idea [0-9]+/[0-9]+ "[^"]{1,43}" \| [a-z][^|]* \| minute [0-9]+ \| stage ([0-9]+h[0-9]{2}m|[0-9]+m[0-9]{2}s|[0-9]+s) \| issues: [0-9]+ fixed, [0-9]+ open$'

run_once() {  # run_once <outfile> [env assignments...]: bash run.sh --once in the sandbox, stdout+stderr to the file
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 300 bash "$REPO_DIR/run.sh" --once ) > "$out" 2>&1
}

run_once_timed() {  # like run_once, every line prefixed with epoch seconds (for the heartbeat schedule check)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 300 bash "$REPO_DIR/run.sh" --once 2>&1 \
      | while IFS= read -r line; do printf '%s %s\n' "$EPOCHREALTIME" "$line"; done; exit "${PIPESTATUS[0]}" ) > "$out"
}

runner_bg() {  # runner_bg <outfile> [args...]: start run.sh in the background (RUNNER_JOB = the runner's pid)
  local out="$1"; shift
  ( cd "$SANDBOX" && exec env NO_COLOR=1 bash "$REPO_DIR/run.sh" "$@" ) > "$out" 2>&1 &
  RUNNER_JOB=$!
}

wait_for() {  # wait_for <regex> <file> [seconds]: poll until the file matches
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

lock_pid() { cut -d' ' -f1 "$SANDBOX/.locks/runner/pid" 2>/dev/null; }
run_dirs() { ls -d "$SANDBOX"/runs/*/ 2>/dev/null | sed 's|/$||'; }
state_get() { python "$STATE_PY" get "$@"; }
plain() { cut -d' ' -f2- "$1"; }  # strip the epoch prefix of run_once_timed output

# ----------------------------------------------------------------------------------------------------------------
section "1. state.py and export.py units"
sandbox_init
RUNS="$SANDBOX_M/runs"; EXPORTS="$SANDBOX_M/exports"

stages="$(python "$STATE_PY" stages)"
assert_eq "$(printf '%s\n' "$stages" | grep -c .)" "16" "the stage table has 16 stages"
assert_eq "$(printf '%s\n' "$stages" | head -n 1 | cut -f1)" "01-research" "first stage is 01-research"
assert_eq "$(printf '%s\n' "$stages" | tail -n 1 | cut -f1,3)" $'14-export\twriting caption' "last stage is 14-export with its activity"
assert_eq "$(printf '%s\n' "$stages" | awk -F'\t' '$1 == "04-angle" {print $5}')" "skipped" "04-angle starts skipped (the gate reopens it)"
assert_eq "$(python "$STATE_PY" slug "Claude Code's frontend-design skill: it makes websites built with AI stop looking AI-generated.")" \
  "claude-codes-frontend-design-skill" "slug: five ASCII words, apostrophes dropped"

created="$(printf '{%s}' "$IDEA_A" | python "$STATE_PY" new --runs "$RUNS" --id 0123456789ab)"
RD="$(python -c 'import json, sys; print(json.loads(sys.argv[1])["run_dir"])' "$created")"
assert_true "new: the run folder name is <date>_<HHMM>_<slug>" grep -q -E '/runs/20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{4}_idea-a-the-gh-cli$' <<<"$RD"
assert_file "$RD/state.json" "new: state.json written"
assert_file "$RD/idea.txt" "new: idea.txt written"
assert_eq "$(ls -d "$RD"/[0-9]*/ | wc -l | tr -d ' ')" "16" "new: one subfolder per stage"
assert_eq "$(state_get "$RD" idea.text)" "$IDEA_A" "new: the idea text is normalized into state.json"
assert_eq "$(state_get "$RD" stages.01-research.status)" "pending" "new: stages start pending"
assert_eq "$(state_get "$RD" status)" "running" "new: the run is running"
assert_eq "$(python "$STATE_PY" next "$RD" | python -c 'import json, sys; d = json.load(sys.stdin); print(d["phase"], d["stage"], d["activity"])')" \
  "stage 01-research researching facts" "next: the first pending stage with its activity"
assert_true "unfinished: lists the running run" grep -q -F "$(basename "$RD")" <<<"$(python "$STATE_PY" unfinished --runs "$RUNS")"

python "$STATE_PY" stage-start "$RD" 01-research >/dev/null
assert_eq "$(state_get "$RD" stages.01-research.status)" "running" "stage-start: running"
assert_eq "$(state_get "$RD" stages.01-research.attempts)" "1" "stage-start: attempts 1"
printf '{"idea_id": "x"}\n' > "$RD/01-research/research.json"
python "$STATE_PY" stage-done "$RD" 01-research --schemas "$REPO_DIR/pipeline/stages" >"$SANDBOX/done.json" 2>&1; rc=$?
assert_rc 5 $rc "stage-done: an output missing required fields fails with exit 5"
assert_grep "research.json: \\$: 'checked' is a required property" "$SANDBOX/done.json" "stage-done: the validation error names the field"
assert_no_file "$RD/01-research/.done" "stage-done: no .done marker when invalid"
assert_eq "$(state_get "$RD" stages.01-research.status)" "failed" "stage-done: status failed when invalid"
REELS_DUMMY_SECONDS=0 bash "$REPO_DIR/pipeline/stages/01-research/dummy.sh" "$RD" >/dev/null 2>&1
done_out="$(python "$STATE_PY" stage-done "$RD" 01-research --schemas "$REPO_DIR/pipeline/stages")"; rc=$?
assert_rc 0 $rc "stage-done: the dummy output validates"
assert_file "$RD/01-research/.done" "stage-done: .done written"
assert_true "stage-done: reports the next stage and activity" grep -q '"next_stage": "02-expansion", "next_activity": "expanding idea"' <<<"$done_out"
python "$STATE_PY" reopen "$RD" 01-research >/dev/null
assert_no_file "$RD/01-research/.done" "reopen: .done removed"
assert_eq "$(state_get "$RD" stages.01-research.status)" "pending" "reopen: pending again"
python "$STATE_PY" pickup "$RD" >/dev/null; python "$STATE_PY" pickup "$RD" >/dev/null
assert_eq "$(state_get "$RD" timing.sessions)" "2" "pickup: counts sessions (a resume)"
python "$STATE_PY" flag "$RD" 07-script "soft script check failed (detect 64)" >/dev/null
assert_eq "$(state_get "$RD" flags.0.text)" "soft script check failed (detect 64)" "flag: recorded"
python "$STATE_PY" finish "$RD" dropped --reason "test" --stage 03-gate >/dev/null
python "$STATE_PY" unfinished --runs "$RUNS" >/dev/null 2>&1; assert_rc 3 $? "unfinished: exit 3 once the run is finished"

# the state lock (M2 review 2): every command that writes state.json holds runs/<id>/state.lock from its load to its
# save, so concurrent writers (a stage's flag, the heartbeat's touch) lose nothing. 20 flag calls and 10 issue calls
# at once, against a loop of 40 touch calls: without the lock about a third of the flags vanished with exit 0.
created="$(printf '{%s}' "$IDEA_B" | python "$STATE_PY" new --runs "$RUNS" --id 0123456789ac)"
RD2="$(python -c 'import json, sys; print(json.loads(sys.argv[1])["run_dir"])' "$created")"
( for i in $(seq 40); do python "$STATE_PY" touch "$RD2" >/dev/null 2>&1; done ) &
for i in $(seq 20); do python "$STATE_PY" flag "$RD2" 07-script "concurrent flag $i" >/dev/null 2>&1 & done
for i in $(seq 10); do python "$STATE_PY" issue "$RD2" open +1 >/dev/null 2>&1 & done
wait
assert_eq "$(state_get "$RD2" flags | python -c 'import json, sys; f = json.load(sys.stdin); print(len(f), len({x["text"] for x in f}))')" "20 20" \
  "lock: 20 concurrent flag calls against a touch loop keep all 20 flags"
assert_eq "$(state_get "$RD2" issues.open)" "10" "lock: 10 concurrent issue calls count to 10"
assert_file "$RD2/state.lock" "lock: runs/<id>/state.lock sits next to state.json"
# a writer waits while another process holds the lock; with REELS_STATE_LOCK_WAIT it gives up with exit 2 instead
rm -f "$SANDBOX/held"
python - "$(mixed "$REPO_DIR/pipeline/lib")" "$RD2" "$SANDBOX_M/held" <<'PY' &
import sys, time
sys.path.insert(0, sys.argv[1])
import state
with state.StateLock(sys.argv[2]):
    with open(sys.argv[3], "w") as f:
        f.write("locked\n")
    time.sleep(4)
PY
holder=$!
wait_for locked "$SANDBOX/held" 10
t0=$EPOCHREALTIME
REELS_STATE_LOCK_WAIT=1 python "$STATE_PY" touch "$RD2" 2>"$SANDBOX/busy.err"; rc=$?
assert_rc 2 $rc "lock: a writer gives up with exit 2 after REELS_STATE_LOCK_WAIT seconds while another process holds the lock"
assert_grep "^state.py: the lock .*/state.lock stayed busy for 1s" "$SANDBOX/busy.err" "lock: the message names the lock file and the wait"
python "$STATE_PY" touch "$RD2" >/dev/null 2>&1; rc=$?
waited="$(python -c 'import sys; print(float(sys.argv[2]) - float(sys.argv[1]))' "$t0" "$EPOCHREALTIME")"
assert_rc 0 $rc "lock: with the default wait the writer goes through once the holder is done"
assert_true "lock: it waited for the holder (${waited%.*}s)" python -c 'import sys; sys.exit(0 if float(sys.argv[1]) >= 2.0 else 1)' "$waited"
wait $holder 2>/dev/null

assert_eq "$(python "$EXPORT_PY" next-number --exports "$EXPORTS")" "1" "numbering: the first export is 1"
mkdir -p "$SANDBOX/exports/3" "$SANDBOX/exports/7" "$SANDBOX/exports/notes"
assert_eq "$(python "$EXPORT_PY" next-number --exports "$EXPORTS")" "8" "numbering: highest existing number plus 1, other folders ignored"
rm -rf "$SANDBOX/exports"
for st in 13-render 14-export; do REELS_DUMMY_SECONDS=0 bash "$REPO_DIR/pipeline/stages/$st/dummy.sh" "$RD" >/dev/null 2>&1; done
caps="$(python "$EXPORT_PY" render --run-dir "$RD" --number 7)"
assert_eq "$(printf '%s\n' "$caps" | grep -E '^(CAPTION|HASHTAGS|COMMENT KEYWORD|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' | paste -sd,)" \
  "CAPTION,HASHTAGS,COMMENT KEYWORD,HOOKS,NEEDS REVIEW,FACTS AND SOURCES,RUN" "captions: the sections of spec section 8, in order"
assert_true "captions: HOOKS lines carry the export number" grep -q -F '7.mp4 uses: "Your AI site looks fake, one fix"' <<<"$caps"
assert_true "captions: the hook 2 clip line" grep -q -F '7hook2.mp4 uses:' <<<"$caps"
assert_true "captions: NEEDS REVIEW lists the flag" grep -q -F '07-script: soft script check failed (detect 64)' <<<"$caps"
assert_true "captions: the RUN section names the run folder" grep -q -F "runs/$(basename "$RD")" <<<"$caps"
assert_true "captions: the NEW deliverable line" grep -q -F 'NEW deliverable to create before posting' <<<"$caps"

# ----------------------------------------------------------------------------------------------------------------
section "2. two dummy ideas end to end, heartbeat and status lines"
sandbox_init
printf '{%s}\n{%s}\n' "$IDEA_A" "$IDEA_B" > "$SANDBOX/ideas.txt"
t0=$EPOCHSECONDS
run_once_timed "$SANDBOX/run2.ts"; rc=$?
took=$(( EPOCHSECONDS - t0 ))
plain "$SANDBOX/run2.ts" > "$SANDBOX/run2.out"
OUT="$SANDBOX/run2.out"
assert_rc 0 $rc "run.sh --once exits 0 when the queue empties (${took}s for 2 ideas)"
assert_grep "${ts_regex}START  reels autopilot v[0-9.]+.* \| queue: 2 ideas \| style: paper-cards \| voice: kokoro af_bella \| sfx map: not built$" "$OUT" "banner"
assert_grep "${ts_regex}QUEUE  1\. Idea A: the gh CLI" "$OUT" "queue listing: 1."
assert_grep "${ts_regex}QUEUE  2\. Idea B: uv replaces pip" "$OUT" "queue listing: 2."
assert_grep "${ts_regex}START  idea 1/2 \"Idea A: the gh CLI in 60 seconds, three ...\" -> runs/20[0-9-]+_[0-9]{4}_idea-a-the-gh-cli$" "$OUT" "START line: position, text cut at 40, run folder"
assert_grep "${ts_regex}STEP   researching facts done \([0-9]+s\) -> expanding idea$" "$OUT" "STEP line: activity done (time) -> next activity"
assert_grep "${ts_regex}STEP   checking idea \(gate\) done \([0-9]+s\) -> picking hooks$" "$OUT" "STEP skips 04-angle when the gate passes"
assert_grep "${ts_regex}STEP   writing caption done \([0-9]+s\) -> exporting$" "$OUT" "STEP before the export"
assert_eq "$(grep -c -E "${ts_regex}STEP " "$OUT")" "30" "15 STEP lines per idea (16 stages, angle skipped)"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/ \([0-9]+(s| min), 0 issues fixed\)$" "$OUT" "DONE line for export 1"
assert_grep "${ts_regex}NEXT   idea 2/2 \"Idea B: uv replaces pip, venv and pyenv ...\"$" "$OUT" "NEXT line keeps counting the ideas of the session"
assert_grep "${ts_regex}START  idea 2/2 \"Idea B" "$OUT" "START line for the second idea"
assert_grep "${ts_regex}DONE   exported #2 -> exports/2/" "$OUT" "DONE line for export 2"
assert_grep "${ts_regex}IDLE   queue empty: this session 2 exported, 0 dropped, 0 blocked in [0-9ms]+ \| today: [0-9]+ exported, [0-9]+ dropped" "$OUT" "summary line when the queue empties"
assert_not_grep "resumed" "$OUT" "no resume in a clean run"
assert_not_grep $'\x1b' "$OUT" "NO_COLOR output has no escape codes"
assert_eq "$(cat "$SANDBOX/logs/status.txt")" "$(tail -n 1 "$OUT")" "status.txt holds the latest line"
assert_eq "$(grep -c -E "${ts_regex}" "$SANDBOX/logs/runner.log")" "$(grep -c -E "${ts_regex}" "$OUT")" "runner.log has every terminal line"
assert_true "runner.log has more than 40 lines" [ "$(grep -c -E "${ts_regex}" "$SANDBOX/logs/runner.log")" -gt 40 ]
for n in 1 2; do
  assert_file "$SANDBOX/exports/$n/$n.mp4" "exports/$n/$n.mp4"
  assert_file "$SANDBOX/exports/$n/${n}captions.txt" "exports/$n/${n}captions.txt"
  assert_file "$SANDBOX/exports/$n/${n}hook2.mp4" "exports/$n/${n}hook2.mp4"
done
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "1,2" "exports/ holds exactly 1 and 2"
assert_grep '^1\.mp4 uses: "' "$SANDBOX/exports/1/1captions.txt" "captions: HOOKS line with the number"
assert_grep "^runs/$(ls "$SANDBOX/runs" | head -n 1)$" "$SANDBOX/exports/1/1captions.txt" "captions: RUN section names the first run"
assert_eq "$(ls -d "$SANDBOX"/runs/*/export 2>/dev/null | wc -l | tr -d ' ')" "0" "the staging folders were moved, not copied"
assert_eq "$(grep -c . "$SANDBOX/logs/history.txt")" "2" "two history lines"
assert_grep "^20[0-9-]+ [0-9:]+ \| $IDEA_A \| exported 1$" "$SANDBOX/logs/history.txt" "history: date | idea | exported 1"
assert_grep "^20[0-9-]+ [0-9:]+ \| $IDEA_B \| exported 2$" "$SANDBOX/logs/history.txt" "history: the second idea with its accents"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt is empty afterwards"
assert_eq "$(ls "$SANDBOX/runs" | wc -l | tr -d ' ')" "2" "two run folders"
for d in $(run_dirs); do
  assert_eq "$(state_get "$d" status)" "exported" "$(basename "$d"): state exported"
done
assert_eq "$(state_get "$(run_dirs | head -n 1)" export.number)" "1" "state.json holds the export number"
assert_eq "$(state_get "$(run_dirs | head -n 1)" stages.04-angle.status)" "skipped" "04-angle stays skipped"
assert_eq "$(cut -f2 "$SANDBOX/logs/.activity")" "between ideas" "logs/.activity is published by the runner"

reel_n="$(grep -c -E "${ts_regex}REEL " "$OUT")"
assert_true "heartbeat: at least 10 REEL lines in ${took}s with REELS_STATUS_EVERY=2 (got $reel_n)" [ "$reel_n" -ge 10 ]
bad="$(grep -E "${ts_regex}REEL " "$OUT" | grep -v -E "$REEL_RE" | head -n 3)"
assert_eq "$bad" "" "heartbeat: every REEL line has #idea i/n, the text cut at 40, activity, minute, stage, issues"
assert_grep "${ts_regex}REEL   #idea 1/2 \"Idea A: the gh CLI in 60 seconds, three ...\" \| [a-z][a-z (),:0-9/]+ \| minute 0 \| stage [0-9]+s \| issues: 0 fixed, 0 open$" "$OUT" "heartbeat: a first-idea line with the exact text cut, minute 0 and a seconds-only stage timer"
assert_true "heartbeat: the activity field follows the stages" [ "$(grep -E "${ts_regex}REEL " "$OUT" | sed -E 's/^.*" \| ([^|]+) \| minute.*$/\1/' | sort -u | wc -l | tr -d ' ')" -ge 5 ]
assert_grep "${ts_regex}REEL   #idea 2/2 \"Idea B" "$OUT" "heartbeat: second idea position"
gaps="$(python - "$SANDBOX/run2.ts" <<'PY'
import re, sys
times = {}
for line in open(sys.argv[1], encoding="utf-8"):
    m = re.match(r"^(\d+\.\d+) \[\d\d:\d\d\] REEL   #idea (\d+)/", line)
    if m:
        times.setdefault(m.group(2), []).append(float(m.group(1)))
gaps = []
for key, ts in times.items():
    gaps += [b - a for a, b in zip(ts, ts[1:])]
if not gaps:
    print("no gaps"); sys.exit(0)
gaps.sort()
print(f"n={len(gaps)} min={gaps[0]:.2f} median={gaps[len(gaps)//2]:.2f} max={gaps[-1]:.2f}")
# the runner schedules on whole seconds (EPOCHSECONDS), so single gaps range from about 1 s to 3 s around the
# 2 s interval, plus the tick lag between stages; the median must sit on the interval
sys.exit(0 if (gaps[0] >= 0.9 and gaps[-1] <= 6.0 and 1.5 <= gaps[len(gaps)//2] <= 3.0) else 1)
PY
)"; rc=$?
assert_rc 0 $rc "heartbeat: on schedule, every 2 s scaled (gaps $gaps)"

# ----------------------------------------------------------------------------------------------------------------
section "3. SIGKILL mid-stage, restart resumes the same stage"
sandbox_init
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
REELS_DUMMY_SECONDS=2 runner_bg "$SANDBOX/kill1.out" --once
if wait_for '[-]> picking hooks' "$SANDBOX/logs/runner.log" 90; then
  RD="$(run_dirs | head -n 1)"
  wait_for '^[0-9]+' "$RD/05-hooks/.pid" 10
  child="$(cut -d' ' -f1 "$RD/05-hooks/.pid" 2>/dev/null)"
  lp="$(lock_pid)"
  kill -9 $child $lp $RUNNER_JOB 2>/dev/null
  wait $RUNNER_JOB 2>/dev/null
  wait_gone "$lp" 10
  assert_false "the runner is dead after SIGKILL" ps -p "$lp"
  assert_false "the stage child is dead too" ps -p "${child:-0}"
  assert_eq "$(state_get "$RD" stages.05-hooks.status)" "running" "state.json: 05-hooks was running when killed"
  assert_no_file "$RD/05-hooks/.done" "no .done for the killed stage"
  assert_file "$RD/03-gate/.done" "earlier stages have their .done markers"
  assert_file "$SANDBOX/.locks/runner/pid" "the runner lock is left behind by the kill"
  run_once "$SANDBOX/kill2.out"; rc=$?
  OUT="$SANDBOX/kill2.out"
  assert_rc 0 $rc "the restarted runner finishes the run and exits 0"
  assert_grep "${ts_regex}START  idea 1/1 \"Idea A.*\" -> runs/$(basename "$RD") \(resumed at picking hooks, 3 stages done\)$" "$OUT" "START line says where it resumes"
  assert_grep "${ts_regex}INFO   S5 picking hooks: attempt 2 \(the previous one was interrupted\)" "$OUT" "the interrupted attempt is announced"
  assert_not_grep "researching facts done" "$OUT" "the earlier stages are skipped"
  assert_not_grep "expanding idea done" "$OUT" "the earlier stages are skipped (2)"
  assert_grep "${ts_regex}STEP   picking hooks done" "$OUT" "the killed stage runs again"
  assert_grep "${ts_regex}DONE   exported #1" "$OUT" "the resumed run exports #1"
  assert_eq "$(ls "$SANDBOX/runs" | wc -l | tr -d ' ')" "1" "no second run folder was created"
  assert_eq "$(state_get "$RD" stages.01-research.attempts)" "1" "state.json: research ran once"
  assert_eq "$(state_get "$RD" stages.05-hooks.attempts)" "2" "state.json: hooks ran twice"
  assert_eq "$(state_get "$RD" timing.sessions)" "2" "state.json: two sessions"
  assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "1" "exactly one export"
  assert_eq "$(grep -c "| exported 1$" "$SANDBOX/logs/history.txt")" "1" "one history line"
else
  fail "the runner never reached 05-hooks (see $SANDBOX/kill1.out)"; cat "$SANDBOX/kill1.out"
  kill -9 "$(lock_pid)" $RUNNER_JOB 2>/dev/null
fi

# ----------------------------------------------------------------------------------------------------------------
section "4. crashes around the export: no duplicate, no gap"
sandbox_init
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/crash1.out" REELS_CRASH_AT=assembled; rc=$?
RD="$(run_dirs | head -n 1)"
assert_true "the runner died at the planted point (exit $rc)" [ "$rc" -ne 0 ]
assert_grep "planted crash after the export was assembled" "$SANDBOX/crash1.out" "the crash is announced"
assert_file "$RD/export/1.mp4" "the export was assembled in runs/<id>/export/"
assert_no_file "$SANDBOX/exports/1" "nothing moved into exports/ yet"
assert_eq "$(state_get "$RD" export.intent)" "1" "state.json records the intended number"
assert_eq "$(state_get "$RD" export.number)" "" "state.json has no export number yet"
assert_true "the exports lock is left behind" [ -d "$SANDBOX/.locks/exports" ]
run_once "$SANDBOX/crash1b.out"; rc=$?
assert_rc 0 $rc "restart after the crash exits 0"
assert_grep "removed a leftover exports lock" "$SANDBOX/crash1b.out" "the leftover exports lock is cleared at startup"
assert_grep "resumed at exporting, 15 stages done" "$SANDBOX/crash1b.out" "the restart resumes at the export"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$SANDBOX/crash1b.out" "the export completes as #1"
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "1" "exactly one export after the crash"
assert_no_file "$RD/export" "the staging folder is gone"
assert_eq "$(grep -c "| exported 1$" "$SANDBOX/logs/history.txt")" "1" "one history line"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "0" "the idea is removed once"

printf '{%s}\n' "$IDEA_B" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/crash2.out" REELS_CRASH_AT=moved; rc=$?
RD2="$(run_dirs | tail -n 1)"
assert_true "the runner died right after the move (exit $rc)" [ "$rc" -ne 0 ]
assert_file "$SANDBOX/exports/2/2captions.txt" "exports/2 exists after the move"
assert_eq "$(state_get "$RD2" export.number)" "" "state.json does not know the number yet"
assert_eq "$(state_get "$RD2" status)" "running" "the run is still unfinished"
assert_eq "$(grep -c "| exported 2$" "$SANDBOX/logs/history.txt")" "0" "no history line yet"
run_once "$SANDBOX/crash2b.out"; rc=$?
assert_rc 0 $rc "restart after the second crash exits 0"
assert_grep "${ts_regex}DONE   exported #2 -> exports/2/" "$SANDBOX/crash2b.out" "the moved export is recognized as #2"
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "1,2" "no exports/3: no duplicate"
assert_eq "$(grep -c "| exported 2$" "$SANDBOX/logs/history.txt")" "1" "exactly one history line for #2"
assert_eq "$(state_get "$RD2" status)" "exported" "the run is finished"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "0" "the idea is removed"

# ----------------------------------------------------------------------------------------------------------------
section "5. drop, code error, FLAG and invalid output"
sandbox_init --with-pipeline   # the review loop reads and commits in the repo, so the repo is the sandbox copy
fake_claude_on
export FAKE_CLAUDE_REVIEW=no
run_once_sb() {  # like run_once, with the sandbox's own run.sh (REELS_REPO = the sandbox)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 600 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}
printf '{%s}\n{%s}\n{%s}\n' "$IDEA_A" "$IDEA_B" "$IDEA_C" > "$SANDBOX/ideas.txt"
run_once_sb "$SANDBOX/paths.out" REELS_DUMMY_DROP=03-gate REELS_DUMMY_FAIL=10-build REELS_DUMMY_FLAG=07-script \
  REELS_DUMMY_ONCE_FILE="$SANDBOX_M/once"; rc=$?
OUT="$SANDBOX/paths.out"
assert_rc 0 $rc "the runner continues past a drop and a block and exits 0"
assert_grep "${ts_regex}DROP   idea \"Idea A: the gh CLI in 60 seconds, three ...\" dropped: facts do not hold \(dummy 03-gate\)\. Removed from ideas.txt$" "$OUT" "DROP line"
assert_grep "${ts_regex}NEXT   idea 2/3 \"Idea B" "$OUT" "NEXT after the drop"
assert_grep "${ts_regex}ERROR  S10 building visuals: exit 1: Traceback \(planted\): ValueError: dummy 10-build failed on purpose$" "$OUT" "ERROR line with the last log line"
assert_grep "${ts_regex}BLOCK  idea \"Idea B: uv replaces pip, venv and pyenv ...\" blocked at S10: environment problem: fake reviewer: exit 1: .*\. Moved to logs/blocked.txt$" "$OUT" "BLOCK line (the reviewer's verdict: only the user can fix it)"
assert_grep "${ts_regex}NEXT   idea 3/3 \"Idea C" "$OUT" "NEXT after the block"
assert_grep "${ts_regex}FLAG   needs review: dummy soft check failed in 07-script$" "$OUT" "FLAG line printed by the stage"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the third idea exports as #1: no gap for dropped or blocked ideas"
assert_grep "${ts_regex}IDLE   queue empty: this session 1 exported, 1 dropped, 1 blocked" "$OUT" "summary counts"
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "1" "only exports/1"
assert_grep "^20[0-9-]+ [0-9:]+ \| $IDEA_A \| dropped: facts do not hold \(dummy 03-gate\)$" "$SANDBOX/logs/history.txt" "history: dropped line"
assert_grep "^20[0-9-]+ [0-9:]+ \| $IDEA_B \| blocked: environment problem: fake reviewer: exit 1" "$SANDBOX/logs/history.txt" "history: blocked line"
assert_grep "^20[0-9-]+ [0-9:]+ \| $IDEA_C \| exported 1$" "$SANDBOX/logs/history.txt" "history: exported line"
assert_grep "^# 20[0-9-]+ [0-9:]+ \| blocked at S10 \| environment problem: fake reviewer: exit 1: .* \| runs/" "$SANDBOX/logs/blocked.txt" "blocked.txt: the reason line"
assert_grep "^\{$IDEA_B\}$" "$SANDBOX/logs/blocked.txt" "blocked.txt: the idea in braces, ready to re-add"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt is empty"
assert_eq "$(ls "$SANDBOX/runs" | wc -l | tr -d ' ')" "3" "the dropped and blocked run folders are kept"
assert_eq "$(for d in $(run_dirs); do state_get "$d" status; done | paste -sd,)" "dropped,blocked,exported" "state.json statuses"
assert_grep "^NEEDS REVIEW$" "$SANDBOX/exports/1/1captions.txt" "captions: NEEDS REVIEW section when flagged"
assert_grep "^07-script: dummy soft check failed in 07-script$" "$SANDBOX/exports/1/1captions.txt" "captions: the flag text"
assert_eq "$(state_get "$(run_dirs | sed -n 2p)" issues.open)" "1" "the code error counts as an open issue"
assert_file "$(run_dirs | sed -n 2p)/10-build/stage.log" "the failed stage kept its log"
assert_grep "planted failure" "$(run_dirs | sed -n 2p)/10-build/stage.log" "stage.log has the stage's own output"

: > "$SANDBOX/logs/blocked.txt"
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
run_once_sb "$SANDBOX/invalid.out" REELS_DUMMY_INVALID=05-hooks; rc=$?
assert_rc 0 $rc "an invalid output does not stop the runner"
assert_grep "${ts_regex}ERROR  S5 picking hooks: invalid output: 05-hooks/hooks.json: \\$: 'hooks' is a required property$" "$SANDBOX/invalid.out" "ERROR line names the schema violation"
assert_grep "${ts_regex}BLOCK  idea \"Idea A.*\" blocked at S5: environment problem: fake reviewer: invalid output" "$SANDBOX/invalid.out" "an invalid output is a code error: reviewed, then blocked on the reviewer's verdict"
assert_grep "^\{$IDEA_A\}$" "$SANDBOX/logs/blocked.txt" "blocked.txt gets the idea"
fake_claude_off
unset FAKE_CLAUDE_REVIEW

# ----------------------------------------------------------------------------------------------------------------
section "6. forever mode: IDLE, NEW, a second runner refused, SIGTERM"
sandbox_init
: > "$SANDBOX/ideas.txt"
runner_bg "$SANDBOX/forever.out"
OUT="$SANDBOX/forever.out"
if wait_for "IDLE   no ideas" "$OUT" 30; then
  assert_grep "${ts_regex}START  reels autopilot .* \| queue: 0 ideas \|" "$OUT" "banner with an empty queue"
  assert_grep "${ts_regex}INFO   root: .* \| mode: forever" "$OUT" "mode line"
  assert_grep "${ts_regex}IDLE   queue empty: this session 0 exported, 0 dropped, 0 blocked in [0-9]+s \| today: 0 exported, 0 dropped$" "$OUT" "summary line first"
  assert_grep "${ts_regex}IDLE   no ideas in ideas.txt, checking every 1 s \(idle 0 min\) \| today: 0 exported, 0 dropped$" "$OUT" "IDLE line with the poll interval, idle minutes and today's counts"
  ( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/run.sh" --once ) > "$SANDBOX/second.out" 2>&1; rc=$?
  assert_rc 1 $rc "a second runner refuses to start while one runs"
  assert_grep "another runner is already running \(pid $(lock_pid)\)" "$SANDBOX/second.out" "it names the running pid"
  CLAUDECODE=1 bash "$ADD_IDEA" "{$IDEA_C}" >/dev/null
  if wait_for "DONE   exported #1" "$OUT" 120; then
    pass "an idea added while idle is processed"
  else
    fail "the idle runner did not process the added idea"
  fi
  assert_grep "${ts_regex}NEW    idea added from Claude Code \(queue: 1\)$" "$OUT" "NEW line names the source and the queue size"
  assert_grep "${ts_regex}START  idea 1/1 \"Idea C" "$OUT" "START after NEW"
  wait_for "IDLE   no ideas in ideas.txt.*today: 1 exported" "$OUT" 15
  assert_grep "${ts_regex}IDLE   queue empty: this session 1 exported, 0 dropped, 0 blocked" "$OUT" "the summary line again when the queue empties again"
  assert_grep "${ts_regex}IDLE   no ideas in ideas.txt, checking every 1 s \(idle 0 min\) \| today: 1 exported, 0 dropped$" "$OUT" "IDLE line with today's count updated"
  idle_n="$(grep -c "IDLE   no ideas" "$OUT")"
  assert_true "IDLE repeats at the heartbeat cadence (got $idle_n lines)" [ "$idle_n" -ge 2 ]
  assert_eq "$(cat "$SANDBOX/logs/status.txt")" "$(tail -n 1 "$OUT")" "status.txt holds the latest line while idle"
  lp="$(lock_pid)"
  kill -TERM "$lp"
  wait_gone "$lp" 10
  assert_false "SIGTERM stops the runner" ps -p "$lp"
  wait $RUNNER_JOB 2>/dev/null
  assert_grep "${ts_regex}INFO   stopped by the user \(TERM\)" "$OUT" "the stop is announced"
  assert_no_file "$SANDBOX/.locks/runner" "the runner lock is released on SIGTERM"
else
  fail "no IDLE line within 30 s (see $OUT)"; cat "$OUT"
  kill -9 "$(lock_pid)" $RUNNER_JOB 2>/dev/null
fi

# ----------------------------------------------------------------------------------------------------------------
section "7. a stage that is not built yet, and runner-status"
# The first stage without a run.sh (S1 to S4 exist since M4; later milestones move this forward). The stages before
# it run as dummies, so no real model is ever called here; when every stage exists the section is skipped.
MISSING_STAGE=""; BUILT_DUMMIES=""; MISSING_ACTIVITY=""; BUILT_N=0
while IFS=$'\t' read -r key label activity output initial; do
  if [ -f "$REPO_DIR/pipeline/stages/$key/run.sh" ]; then
    BUILT_DUMMIES="${BUILT_DUMMIES:+$BUILT_DUMMIES,}$key"; BUILT_N=$((BUILT_N + 1)); continue
  fi
  MISSING_STAGE="$key"; MISSING_ACTIVITY="$activity"; break
done < <(python "$STATE_PY" stages)
if [ -z "$MISSING_STAGE" ]; then
  pass "every stage has a run.sh: the not-built-yet stop no longer applies (section skipped)"
else
sandbox_init
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
( cd "$SANDBOX" && env REELS_DUMMY="$BUILT_DUMMIES" NO_COLOR=1 timeout 120 bash "$REPO_DIR/run.sh" --once ) > "$SANDBOX/stop.out" 2>&1; rc=$?
assert_rc 3 $rc "a missing real stage ($MISSING_STAGE) is a systemic stop (exit 3)"
assert_grep "${ts_regex}STOP   systemic failure: stage $MISSING_STAGE is not built yet \(run.sh missing in pipeline/stages/$MISSING_STAGE\)\. See logs/STOPPED.md$" "$SANDBOX/stop.out" "STOP line"
assert_file "$SANDBOX/logs/STOPPED.md" "STOPPED.md written"
assert_grep "REELS_DUMMY=all bash run.sh --once" "$SANDBOX/logs/STOPPED.md" "STOPPED.md gives the exact fix"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "1" "the idea stays in ideas.txt"
assert_eq "$(state_get "$(run_dirs | head -n 1)" status)" "running" "the run stays unfinished"
# the stages done before the stop (04-angle stays skipped when the dummy gate passes, so this is not BUILT_N)
done_before_resume="$(python "$STATE_PY" summary "$(run_dirs | head -n 1)" | python -c 'import json, sys; print(json.load(sys.stdin)["stages_done"])')"
status_out="$(bash "$REPO_DIR/pipeline/bin/runner-status" 5)"
assert_true "runner-status: says the runner is not running" grep -q "^runner: not running" <<<"$status_out"
assert_true "runner-status: shows the status line" grep -q "^status: \[.*STOP   systemic failure" <<<"$status_out"
assert_true "runner-status: mentions STOPPED.md" grep -q "STOPPED: logs/STOPPED.md exists" <<<"$status_out"
assert_true "runner-status: shows the log tail" grep -q "^last 5 lines of logs/runner.log:" <<<"$status_out"
run_once "$SANDBOX/stop2.out"; rc=$?
assert_rc 0 $rc "a later start with dummy stages resumes the kept run"
assert_grep "removed logs/STOPPED.md" "$SANDBOX/stop2.out" "the successful start removes STOPPED.md"
plural_stage="stages"; [ "$done_before_resume" = 1 ] && plural_stage="stage"
assert_grep "resumed at $MISSING_ACTIVITY, $done_before_resume $plural_stage done" "$SANDBOX/stop2.out" "the kept run is resumed at the stage that was missing"
assert_grep "${ts_regex}DONE   exported #1" "$SANDBOX/stop2.out" "and exported"
fi

# ----------------------------------------------------------------------------------------------------------------
section "8. state.json damaged mid-run: one retry, then the systemic stop with STOPPED.md"
# The damage lands while the gate's dummy runs (its .pid exists), a window in which nothing writes state.json; the
# runner meets it at stage-done. REELS_STATUS_EVERY=60 keeps the heartbeat (and its state touch) out of the window.
sandbox_init
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
REELS_DUMMY_SECONDS=2 REELS_STATUS_EVERY=60 runner_bg "$SANDBOX/state1.out" --once
OUT="$SANDBOX/state1.out"
if wait_for 'STEP   expanding idea done' "$SANDBOX/logs/runner.log" 90 \
   && RD="$(run_dirs | head -n 1)" && wait_for '^[0-9]+' "$RD/03-gate/.pid" 10; then
  RID="$(basename "$RD")"
  printf 'not json\n' > "$RD/state.json"
  lp="$(lock_pid)"
  wait_gone "$lp" 60 || kill -9 "$lp" $RUNNER_JOB 2>/dev/null
  wait $RUNNER_JOB 2>/dev/null; rc=$?
  assert_rc 3 $rc "the runner stops with exit 3 (a systemic stop, not a silent exit)"
  assert_grep "${ts_regex}WARN   cannot update runs/$RID/state.json \(cannot read runs/$RID/state.json: Expecting value: line 1 column 1 \(char 0\)\), trying again in [0-9]+s$" "$OUT" "WARN line: the failed state call is retried once, with state.py's message in short form"
  assert_grep "${ts_regex}ERROR  cannot update runs/$RID/state.json: cannot read runs/$RID/state.json: Expecting value: line 1 column 1 \(char 0\)$" "$OUT" "ERROR line after the retry"
  assert_grep "${ts_regex}STOP   systemic failure: cannot update runs/$RID/state.json \(.*\)\. See logs/STOPPED.md$" "$OUT" "STOP line"
  assert_eq "$(grep -c -E "${ts_regex}(ERROR|STOP) " "$OUT")" "2" "one ERROR line and one STOP line, no more"
  assert_not_grep "${ts_regex}(BLOCK|DROP|DONE|NEXT) |STEP   checking idea" "$OUT" "the run neither goes on nor ends as blocked, dropped or exported"
  assert_file "$SANDBOX/logs/STOPPED.md" "STOPPED.md written"
  assert_grep "^- cannot update runs/$RID/state.json \(cannot read runs/$RID/state.json: Expecting value: line 1 column 1 \(char 0\)\)$" "$SANDBOX/logs/STOPPED.md" "STOPPED.md names the run folder and the error in its diagnosis"
  assert_grep "^1\. If the file was only busy .*OneDrive.*start the runner again" "$SANDBOX/logs/STOPPED.md" "STOPPED.md fix 1: unlock the file and restart"
  assert_grep "^2\. If state.json itself is damaged .*runs/$RID out of runs/ .*runs/_broken/" "$SANDBOX/logs/STOPPED.md" "STOPPED.md fix 2: move the run folder out of runs/"
  assert_grep "^\[[0-9:]+\] STOP   systemic failure: cannot update runs/$RID/state.json" "$SANDBOX/logs/status.txt" "status.txt holds the STOP line"
  assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "1" "the idea stays in ideas.txt"
  assert_no_file "$SANDBOX/logs/history.txt" "no history line"
  assert_no_file "$SANDBOX/.locks/runner" "the runner lock is released"
  status_out="$(bash "$REPO_DIR/pipeline/bin/runner-status" 3)"
  assert_true "runner-status: says the runner is not running" grep -q "^runner: not running" <<<"$status_out"
  assert_true "runner-status: shows the STOP status line" grep -q "^status: \[.*STOP   systemic failure: cannot update" <<<"$status_out"
  assert_true "runner-status: mentions STOPPED.md" grep -q "^STOPPED: logs/STOPPED.md exists" <<<"$status_out"
else
  fail "the runner never reached the gate's dummy (see $OUT)"; cat "$OUT"
  kill -9 "$(lock_pid)" $RUNNER_JOB 2>/dev/null
fi

# The same failure at the start of a stage (runner_run_stage), reached through the orphan wait: a stage process
# left by a killed runner is waited for instead of being started twice (DECISIONS.md 54). A sleep plays the orphan.
sandbox_init
printf '{%s}\n' "$IDEA_A" > "$SANDBOX/ideas.txt"
ORPHAN=""
REELS_DUMMY_SECONDS=3 REELS_STATUS_EVERY=60 runner_bg "$SANDBOX/state2.out" --once
OUT="$SANDBOX/state2.out"
if wait_for 'START  idea 1/1' "$SANDBOX/logs/runner.log" 60; then
  RD="$(run_dirs | head -n 1)"; RID="$(basename "$RD")"
  sleep 120 & ORPHAN=$!
  printf '%s %s\n' "$ORPHAN" "$EPOCHSECONDS" > "$RD/02-expansion/.pid"
  if wait_for "WARN   S2 expanding idea still runs from the previous runner \(pid $ORPHAN\), waiting for it instead of starting it twice" "$SANDBOX/logs/runner.log" 30; then
    pass "an orphaned stage process is waited for instead of being started twice"
    sleep 1
    assert_no_file "$RD/02-expansion/stage.log" "the stage is not started while the orphan lives"
    printf 'not json\n' > "$RD/state.json"
    kill "$ORPHAN" 2>/dev/null; wait "$ORPHAN" 2>/dev/null
    lp="$(lock_pid)"
    wait_gone "$lp" 60 || kill -9 "$lp" $RUNNER_JOB 2>/dev/null
    wait $RUNNER_JOB 2>/dev/null; rc=$?
    assert_rc 3 $rc "the runner stops with exit 3"
    assert_grep "${ts_regex}INFO   S2 expanding idea: the orphaned process left no valid output, running the stage again$" "$OUT" "the orphan's outputs are judged before the stage runs again"
    assert_grep "${ts_regex}WARN   cannot update runs/$RID/state.json \(.*\), trying again in [0-9]+s$" "$OUT" "WARN line: the stage start is retried once"
    assert_grep "${ts_regex}ERROR  cannot update runs/$RID/state.json: " "$OUT" "ERROR line: the stage start fails"
    assert_grep "${ts_regex}STOP   systemic failure: cannot update runs/$RID/state.json \(.*\)\. See logs/STOPPED.md$" "$OUT" "STOP line"
    assert_not_grep "expanding idea done|${ts_regex}(BLOCK|DROP|DONE) " "$OUT" "the stage never ran and the run did not end another way"
    assert_no_file "$RD/02-expansion/stage.log" "no stage.log: the stage was never started"
    assert_file "$SANDBOX/logs/STOPPED.md" "STOPPED.md written"
    assert_grep "runs/$RID/state.json" "$SANDBOX/logs/STOPPED.md" "STOPPED.md names the run folder"
    assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/ideas.txt")" "1" "the idea stays in ideas.txt"
    assert_no_file "$SANDBOX/.locks/runner" "the runner lock is released"
  else
    fail "the runner did not wait for the planted orphan (see $OUT)"; cat "$OUT"
    kill -9 "$(lock_pid)" $RUNNER_JOB 2>/dev/null
  fi
else
  fail "the runner never started the run (see $OUT)"; cat "$OUT"
  kill -9 "$(lock_pid)" $RUNNER_JOB 2>/dev/null
fi
if [ -n "$ORPHAN" ]; then kill "$ORPHAN" 2>/dev/null; wait "$ORPHAN" 2>/dev/null; fi

test_summary
