# M2 review 1: Runner core and terminal output

Reviewer: fresh session, 2026-10-31. Read: BUILD_SPEC.md (sections 1 to 4, 6 to 8, 12), CLAUDE.md, PLAN.md (M2),
DECISIONS.md (52 to 66), build/progress.md, build/HUMAN_TODO.md, build/M2/report.md, the diff and log
eacc3a2..HEAD (run.sh, pipeline/lib/{runner,state,status,log,history,export,dummy}.sh/.py, the 16 stage folders,
runner-status, the M1 files touched, the tests). No earlier review or fix file exists for M2.

## Verdict
REJECTED, 1 required fix. The acceptance test passes and the build matches the spec well. One exit path
breaks spec section 4: the runner can stop by itself without writing logs/STOPPED.md.

## Acceptance test (run by the reviewer)
`bash pipeline/tests/run-all.sh` (about 8 minutes): `test-m1.sh: 96 passed, 0 failed`,
`test-m2.sh: 183 passed, 0 failed`, `test-no-emdash.sh: 1 passed, 0 failed`, `run-all: 3 test files, all passed`.
- Section 2: two dummy ideas produce exports/1 and exports/2 with N.mp4, Ncaptions.txt and Nhook2.mp4, plus two
  history lines. ideas.txt ends up empty. The heartbeat ran 27 gaps at 1.80 to 2.16 s on a 2 s schedule, and every
  REEL line matches the field regex. status.txt equals the last line, and the NO_COLOR output has no escape codes.
- Section 3: after a SIGKILL during 05-hooks, the restart prints `START ... (resumed at picking hooks, 3 stages done)`
  and the attempt 2 note, then exports #1 once. state.json shows research run once and hooks twice.
- Section 4: crashes planted after assembling and after the move cause neither a duplicate nor a gap.
- Sections 5 to 7: the drop, block, flag and invalid output paths, forever mode with IDLE, NEW from Claude Code,
  the second runner refused, SIGTERM, and the systemic stop for a stage that is not built yet all pass.
- Earlier milestones: test-m1 passes, so nothing is broken.

## Spec compliance (checked)
- Section 3: the loop, --once and polling, one run folder per idea (`runs/<YYYY-MM-DD_HHMM>_<slug>/`, state.json
  and one subfolder per stage), done only when the output validates and `.done` exists, resume first, skipping done
  stages, no lost work or duplicate export on a kill: present.
- Sections 6 and 7: banner, REEL, IDLE, summary, START, STEP, DONE, DROP, BLOCK, NEW, NEXT, FLAG, STOP, the
  6-character tags, colors only on a terminal without NO_COLOR, status.txt: present. LIMIT, RESUME, RETRY, FIXED
  and ESCAL are formatted and colored now and get wired in M3, as PLAN.md says.
- Section 8: N = highest plus 1 under a lock, assembled in runs/<id>/export/ and moved in one rename, the captions
  file in the exact section order, removal and history after the export: present.
- Section 4.3 history.txt and blocked.txt formats: present.
- Windows: python (never python3), C:/ paths through cygpath -m and winpath, LF output from Python, no GNU-only
  date tricks. No CRLF and no em dash in any tracked file M2 touched (the only hits are user-curated files from
  before M2). No secrets.

## Required fixes
1. **The runner stops without STOPPED.md when state.json cannot be read or written mid-run.**
   - File: pipeline/lib/runner.sh. `runner_run_stage` line 181 (`state_stage_start ... || { say ERROR ...;
     return 2; }`) and `runner_process_run` line 381 (`state_next ... || { say ERROR ...; rc=2; break; }`) return
     2 without calling `runner_systemic_stop`. `runner_main` lines 461 and 462 then return 3, so the runner exits.
     It never prints a STOP line and never writes logs/STOPPED.md. status.txt shows only an ERROR line, and
     runner-status reports "not running" with no reason.
   - Reproduced: a sandbox with one dummy idea, with state.json overwritten with "not json" right after
     `STEP expanding idea done`. Output: `ERROR  cannot update .../state.json`, then `rc=3`, no STOPPED.md, and
     status.txt holds that ERROR line. OneDrive and antivirus file locks make a failed `os.replace` (5 tries over
     1 s in state.py `save`) a realistic trigger on this machine (see the M0 HUMAN_TODO about OneDrive).
   - Expected (BUILD_SPEC.md section 4, rule zero and 4.2 item 6): the runner stops on its own only through the
     systemic stop, and that stop always writes logs/STOPPED.md with the diagnosis and the exact fix and prints the
     STOP line. Either route these two failures through `runner_systemic_stop` (same style as the unreadable
     state.json case at `state_pickup`, lines 350 to 355, with a fix such as "close programs holding the file /
     pause OneDrive, or move the run folder to runs/_broken/"), or retry once after a short wait before stopping.
     A guard in `runner_main` would also work: when `rc=2` and STOP_REQUESTED is 0, call `runner_systemic_stop`
     with a generic reason. That guard covers any future `return 2` too.
   - Verify: add a test-m2 case that makes state.json unreadable between two stages (wait for the STEP line in
     runner.log, then overwrite state.json). Assert exit 3, a STOP line in the output, logs/STOPPED.md that names
     the run folder and gives a fix, and the STOP line in status.txt.

## Repeated from earlier review
None (this is the first review of M2).

## Optional suggestions (not a reason to reject)
1. **Crash window in drop and block.** `runner_drop` and `runner_block` remove the idea and write history before
   `state_finish`. A kill in that window leaves the run `running` with the stage `failed`. The restart then runs
   the gate (or the failed stage) again for an idea that is already gone from ideas.txt, and can write a second
   history line. Call `state_finish` first, or teach `next_phase` that a stage that failed with exit 10 or 20 ends
   the run.
2. **Ctrl+C and the stage's process tree.** `runner_on_signal` sends TERM and then KILL to the stage's bash child
   only. On Windows, its native grandchildren (python, node, claude) can outlive it and keep writing outputs while
   the restart runs the stage again. This matters from M4 on: consider killing the whole tree (for example
   `taskkill //T //F //PID <winpid>` through `ps -W`, or a process group), and keeping `.pid` until the tree is
   gone. The orphan adoption path (`runner_adopt_orphan`) has no test yet.
3. **SIGTERM while idle.** `sleep "$POLL_SECONDS"` runs in the foreground, so a `kill <pid>` (not Ctrl+C) waits up
   to 120 s before the trap runs. `sleep N & wait $!` makes the trap run at once.
4. **Idle heartbeat cadence.** With the defaults (poll 120 s, heartbeat 300 s), IDLE prints every 360 s, because
   the check runs only after each poll. Sleeping `min(poll, time to next heartbeat)` gives the 5-minute rhythm.
5. **The stage timer** counts from the start of the stage attempt, not from the current activity (DECISIONS.md 58
   records this on purpose). Spec section 7 says "since the current activity started". Fine for now. Revisit when
   S7 and S12 change their activity text by round, where "stage 0m40s" on "fixing [text] issues (round 2)" would
   read better.
6. Cosmetic: state.py error messages mix separators (`...runs/<id>\state.json`) because of `os.path.join` on a
   C:/ path. `.replace("\\", "/")` in `state_path` would keep the logs uniform.
