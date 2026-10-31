# M2 fixes 1: Runner core and terminal output

Fix batch, 2026-10-31, after build/M2/review-1.md (REJECTED, 1 required fix). Read: BUILD_SPEC.md (sections 3, 4,
6 to 8 and 12), CLAUDE.md, PLAN.md (M2), DECISIONS.md (52 to 66), build/progress.md, build/HUMAN_TODO.md,
build/M2/report.md and review-1.md. No earlier fix file exists for M2.

## Required fix 1: the runner stopped without STOPPED.md when state.json could not be read or written mid-run

**What was wrong.** `runner_run_stage` returned 2 when `state_stage_start` failed and `runner_process_run`
returned 2 when `state_next` failed; `runner_main` turned that into exit 3 with no STOP line and no
logs/STOPPED.md (status.txt kept an ERROR line, runner-status said "not running" with no reason). A third place
had the same root cause with a different symptom: a state.py failure at `stage-done` (exit 2, a state file error)
was handled like a validation failure, so the idea was blocked with the reason "invalid output: output did not
validate" and the run folder was left behind.

**What changed** (pipeline/lib/runner.sh; recorded as DECISIONS.md 67):
- New `runner_state <read|update> "<ok exit codes>" <state command...>`. It runs the state.py call with its stdout
  in STATE_OUT and its exit code in STATE_RC. An exit code outside the ok set is retried once after
  STATE_RETRY_SECONDS (3 s, scaled by runner_sleep like every configured wait, so 0.05 s in the tests), with a WARN
  line; a second failure prints ERROR, calls `runner_systemic_stop` (STOPPED.md, the STOP line, STOP_REQUESTED) and
  returns 2. The detail is state.py's last stderr line without the tool name and with the run folder in its short
  form, for example `cannot read runs/<id>/state.json: Expecting value: line 1 column 1 (char 0)`.
- The three state calls of the stage path go through it: `state_stage_start` in `runner_run_stage` (ok: 0),
  `state_next` in `runner_process_run` (ok: 0) and `state_stage_done` in `runner_handle_stage_exit` (ok: 0 and 5;
  5 means "the output did not validate" and still takes the code error path as before). `runner_handle_stage_exit`
  therefore has a third result, 2 (stop), documented in its header.
- `runner_main`: a run that ends with rc 2 or with STOP_REQUESTED still makes the runner return 3, but a rc 2 that
  arrives without STOPPED.md first gets a generic systemic stop ("the run ... could not continue (the ERROR line
  before this one in logs/runner.log says why)"). This is the guard the review suggested; it covers any future
  `return 2`.
- `runner_adopt_orphan` returns 3 for "run the stage" (no orphan, or an orphan that left no valid output) and
  otherwise the stage's result; `runner_run_stage` tests for 3. The old `runner_adopt_orphan ... && return $?`
  returned only on 0, so a run that ended inside the orphan path (1), or now a stop (2), fell through and started
  the stage again. The change was needed for the new result 2 to propagate; it closes that gap too.
- `runner_write_stopped` and `runner_systemic_stop` accept several fix lines, numbered in STOPPED.md; the existing
  callers pass one fix and print as before. STOPPED.md for this failure reads: Diagnosis "cannot update
  runs/<id>/state.json (<state.py's message>)"; Fix "1. If the file was only busy (OneDrive syncing it, an antivirus
  scan, an editor holding it): close whatever holds it, or pause OneDrive, and start the runner again. The run
  resumes where it stopped." and "2. If state.json itself is damaged (it is not valid JSON any more): the next
  start skips this run folder and starts the idea over in a new one, because the idea is still in ideas.txt. Move
  runs/<id> out of runs/ (for example into runs/_broken/) when you no longer need it."
- pipeline/lib/state.py: `state_path` returns forward slashes (the review's optional item 6). Done because
  state.py's messages now appear in the STOP line and in STOPPED.md, where `runs/<id>\state.json` read badly.

**Why a systemic stop and not a block.** A state.json that cannot be read or written is an environment problem (a
file lock, a damaged file, an unwritable folder) that would hit every idea, and going on without a trusted state
could repeat a stage or duplicate an export. The idea stays in ideas.txt. The existing stop for an unreadable
state.json at pickup is unchanged.

**How verified.** New section 8 of pipeline/tests/test-m2.sh, two scenarios, 30 checks:
1. The stage-done path. A dummy run with REELS_DUMMY_SECONDS=2 and REELS_STATUS_EVERY=60 (no heartbeat, so nothing
   else touches state.json in the window); after `STEP expanding idea done`, once `03-gate/.pid` exists, state.json
   is overwritten with "not json". Asserts: exit 3; the WARN line with the retry; one ERROR and one STOP line and
   no BLOCK, DROP, DONE or NEXT; STOPPED.md with the diagnosis naming runs/<id>/state.json and state.py's message,
   fix 1 (OneDrive, restart) and fix 2 (runs/<id> out of runs/, runs/_broken/); status.txt holds the STOP line;
   the idea stays in ideas.txt; no history line; the lock is released; runner-status reports not running, the STOP
   status line and the STOPPED.md hint.
2. The stage-start path (line 181 in the review), reached through the orphan wait. A `sleep` is planted as the
   orphan of 02-expansion (`02-expansion/.pid`) before the runner gets there; the runner prints "still runs from
   the previous runner (pid N), waiting for it instead of starting it twice" and does not start the stage (no
   stage.log); state.json is then damaged and the orphan killed; the runner judges the orphan's outputs ("left no
   valid output, running the stage again"), the stage start fails, the retry fails: ERROR, STOP, STOPPED.md,
   exit 3, the idea kept, the lock released. This is also the first test of `runner_adopt_orphan`.

The damage is planted while a stage runs rather than "right after the STEP line": between a STEP line and the
next `state_stage_start` the runner spends milliseconds, and an overwrite that lands before stage-start's own save
is simply overwritten by it. While a stage runs nothing writes state.json, so the first state call to meet the
damage is known in advance.

**Test results.**
- `bash pipeline/tests/test-m2.sh` (second run, by itself): `213 passed, 0 failed` (183 before this fix plus the
  30 of section 8), exit 0, 12 minutes under load. The heartbeat check read `gaps n=29 min=1.23 median=2.07
  max=2.83`, on its 2 s schedule.
- `bash pipeline/tests/run-all.sh` (first run): `test-m1.sh: 96 passed, 0 failed`, `test-no-emdash.sh: 1 passed`,
  `test-m2.sh: 212 passed, 1 failed`, exit 1. The one failure was section 2's heartbeat-schedule check
  (`gaps n=38 min=1.41 median=4.08 max=12.55`), a timing measurement of the runner's loop that this fix does not
  touch: during that run the PC was saturated by other projects' work (a vitest run with 16 node workers, two vite
  servers, three other Claude Code sessions, CPU at 56%), and the same two-idea run took 240 s against 79 s in
  the second run. Every check of section 8 and every other check passed in both runs. The timing check passed in
  the second run, as it did for the builder and the reviewer. build/progress.md now says to run the test on a quiet
  machine.
- The section 8 scenarios were also run on their own three times while writing them (30 of 30 each time), once
  with KEEP_SANDBOX=1 to read the terminal lines and STOPPED.md by eye; the text quoted above is from that run.
- No em dash and no CRLF in the changed files (checked on bytes with Python); `bash -n` on the shell files and
  `python -m py_compile` on state.py pass.

## Optional suggestions from the review
Not applied, out of the required scope: 1 (state_finish before the removal in drop and block), 2 (killing the
stage's process tree), 3 (SIGTERM while idle), 4 (the idle heartbeat cadence), 5 (the stage timer). Applied: 6
(state_path separators), for the reason above. The note under 2 that the orphan path had no test is covered by
scenario 2.

## Files
- Changed: pipeline/lib/runner.sh, pipeline/lib/state.py (one line), pipeline/tests/test-m2.sh (section 8 and
  its header), DECISIONS.md (item 67), build/progress.md (M2 status), build/M2/fixes-1.md (this file).
- build/HUMAN_TODO.md: nothing added, nothing needs the user.
- Not touched, left as the user's uncommitted work: build-runner.new.sh.

## Commits
- 8abc71d fix(M2): a state.json failure mid-run is a systemic stop with STOPPED.md (runner.sh, state.py,
  test-m2.sh, DECISIONS.md 67, build/progress.md)
- docs(M2): fixes 1 notes (this file, committed after it was written)

Left uncommitted on purpose, not mine: build-runner.new.sh and build/M2/review-1.md (the build runner commits the
review at approval, as it did for M0 and M1).
