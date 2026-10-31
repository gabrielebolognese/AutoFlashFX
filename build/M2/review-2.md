# M2 review 2: Runner core and terminal output

Reviewer: fresh session, 2026-10-31. Read: BUILD_SPEC.md (sections 3, 4, 6 to 8 and 12), CLAUDE.md, PLAN.md (M2),
DECISIONS.md (up to 67), build/progress.md, build/HUMAN_TODO.md, build/M2/report.md, review-1.md, fixes-1.md, and
the log and diff eacc3a2..HEAD, mainly commit 8abc71d (pipeline/lib/runner.sh, pipeline/lib/state.py,
pipeline/tests/test-m2.sh section 8). pipeline/knowledge/ has no known-issues.md yet (it arrives with M3).

## Verdict
REJECTED, 1 required fix. Review 1's required fix is done well and its tests pass. My full test run failed two
checks in test-m2 section 5, though. I traced them to a race in state.py: two processes can each read, change and
save state.json at the same time, so one update gets lost. A stage's NEEDS REVIEW flag can then disappear, and the
reel is exported without its warning. I reproduced this outside the test suite (details below).

## Acceptance test (run by the reviewer)
`bash pipeline/tests/run-all.sh` (about 9 minutes, quiet machine):
- `test-m1.sh: 96 passed, 0 failed`
- `test-no-emdash.sh: 1 passed, 0 failed`
- `test-m2.sh: 211 passed, 2 failed`. `run-all: 3 test files, 1 failed: test-m2.sh`, exit 1.

What passed:
- The three checks the spec names for M2. Section 3: a SIGKILL during a stage, then a restart that resumes the
  same stage. Section 2: two dummy runs produce exports/1/ and exports/2/. Section 2: the fast-mode heartbeat keeps
  its schedule with the right fields.
- Section 4: crashes around the export.
- Section 6: forever mode, IDLE, NEW, a second runner refused, SIGTERM.
- Section 7: a stage that is not built yet.
- All of section 8. This is review 1's fix: state.json damaged at stage-done and at stage-start (the second case
  goes through the orphan wait). Each case prints WARN, then ERROR and STOP, writes STOPPED.md with both fixes,
  exits 3, keeps the idea in ideas.txt and releases the lock.

What failed, both in section 5:
- `FAIL captions: NEEDS REVIEW section when flagged (no match for '^NEEDS REVIEW$' in .../exports/1/1captions.txt)`
- `FAIL captions: the flag text (no match for '^07-script: dummy soft check failed in 07-script$' ...)`
- In the same run, `FLAG line printed by the stage` passed. So the stage did call run_flag, but the flag never
  reached state.json's `flags` list, and the export left out the NEEDS REVIEW section.

## Review 1's fix (checked)
- `runner_state` (runner.sh lines 135 to 160) handles stage-start, stage-done (where exit 5 still means invalid
  output) and next. Each gets one retry, then ERROR, `runner_systemic_stop` with two numbered fixes, and return 2.
- The guard in `runner_main` (lines 505 to 511) gives a generic STOPPED.md to any rc 2 that arrives without one.
- `runner_adopt_orphan` now returns 3 for "run the stage", so results 1 and 2 propagate. Before, an orphan that
  ended the run fell through and started the stage again. That gap is closed too.
- state.py `state_path` now uses forward slashes.
- DECISIONS.md 67 records the choice. No CRLF, no em dash and no `python3` call in the files changed since eacc3a2
  (checked on bytes with Python). No secrets.

## Required fixes
1. **Concurrent state.json writers lose updates (a stage's FLAG can vanish before the export).**
   - Files: pipeline/lib/state.py (every command that does `load()` ... `save()`: flag, touch, stage-start,
     stage-done, stage-fail, issue, round, set, reopen, finish). Also pipeline/lib/status.sh line 66: the
     heartbeat's `state_touch` runs while the stage's own process may be writing.
   - Problem: two processes write state.json while a stage runs:
     - the stage, through `run_flag`/`state_flag` (and from M3 on `issue`, `round`, `set` for session ids)
     - the runner, through `runner_heartbeat` -> `state_touch` on every heartbeat
     Each process loads the whole file, changes it and writes it back with `os.replace`, with no lock. When the two
     calls overlap, whichever saves last wins, and the other one's change is lost without any error (both exit 0).
     The stage still prints the FLAG line, but the flag is gone from state.json. export.py then writes Ncaptions.txt
     without the NEEDS REVIEW section that BUILD_SPEC.md section 8 requires "when flagged", so a reel that failed
     a soft check is exported looking clean. With the default 300 s heartbeat the window is small but real. It
     grows with load and with every state write stages add from M3 on. In the fast test mode (heartbeat every 2 s)
     it makes test-m2 section 5 fail intermittently, which is what happened in my run.
   - Reproduced outside the test suite: one run made with `state.py new`. Then a loop of 40 `state.py touch` calls
     ran in the background while 20 `state.py flag` calls ran in the foreground. Result: `flag calls that exited
     0: 20/20`, `flags in state.json: 13`. Seven flags were lost and nothing on stderr reported it.
   - Expected: an update to state.json is never lost, whichever processes write it. Recommended fix: make
     load-change-save atomic across processes inside state.py. Take an exclusive lock around each mutating command,
     for example:
     - a `state.json.lock` taken with `msvcrt.locking` on Windows (fcntl elsewhere), or
     - an `os.mkdir` lock with a timeout and stale-lock cleanup, like the ideas.txt lock from M1.
     Hold it from `load` to `save`. Read-only commands (next, summary, get, pickup when it does not write) can stay
     unlocked, because `os.replace` keeps every read whole. Smaller alternative: keep the heartbeat out of
     state.json entirely (write `last_seen` to a sidecar file), and make sure no other runner write happens while a
     stage runs. That fixes the race today but leaves M3's stage writes exposed, so the lock is the better fix.
     Record the choice in DECISIONS.md.
   - Verify:
     - (a) Add a test-m2 unit that runs N concurrent `state.py flag` calls (for example 20) against a loop of
       `state.py touch` calls and asserts that state.json has exactly N flags. Today it gets 13 of 20.
     - (b) `bash pipeline/tests/test-m2.sh` passes section 5 consistently. Run it twice.
     - (c) `bash pipeline/tests/run-all.sh` is all green.

## Repeated from earlier review
None. Review 1's only required fix (the stop without STOPPED.md) is fixed and tested. This race is new: review 1's
test run happened to miss it.

## Optional suggestions (not a reason to reject)
1. **Review 1's optional items 1 to 5 are still open.** They are: state_finish before removing the idea in drop
   and block, killing the stage's whole process tree on Ctrl+C, `sleep & wait` so SIGTERM is not delayed while
   idle, the idle heartbeat cadence (every 360 s with the defaults), and the stage timer. Item 1 has a related
   case: `state_stage_fail` and `state_finish` in `runner_drop`, `runner_block` and `runner_finalize` still call
   state.py directly, outside `runner_state`, with their output discarded. If state.json cannot be written at that
   moment, the idea is already gone from ideas.txt and its history line is written, but the run stays `running`.
   The next pickup then resumes it: it runs the gate or the failed stage again for an idea that no longer exists, or
   it repeats finalize and writes a second history line. No export is ever duplicated, but routing these two calls
   through `runner_state` (or calling state_finish first) would close the gap.
2. **The write-failure path is untested.** Section 8 tests a damaged file (a read failure). A cheap second case
   would make state.json read-only (Git Bash's `chmod -w` sets the Windows read-only attribute, so `os.replace`
   fails with PermissionError). That would cover the "busy file" branch that STOPPED.md fix 1 describes.
3. In the orphan path, `runner_adopt_orphan` calls `state_stage_done` directly (line 252) and then
   `runner_handle_stage_exit` calls it a second time through `runner_state`. That works, because the second call
   is idempotent, but the first call could be the check itself (validate without saving), which would avoid the
   double write.
4. build/progress.md says the M2 test takes about 7 minutes. On this machine the full run-all took about 9, which
   matches the "about 9 minutes" given for run-all. Fine as is.
