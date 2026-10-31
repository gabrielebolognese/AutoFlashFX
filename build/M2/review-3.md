# M2 review 3: Runner core and terminal output

Reviewer: fresh session, 2026-10-31. Read: BUILD_SPEC.md (sections 3, 4, 6 to 8 and 12), CLAUDE.md, PLAN.md (M2),
DECISIONS.md (up to 68), build/progress.md, build/HUMAN_TODO.md, build/M2/report.md, review-1.md, fixes-1.md,
review-2.md, fixes-2.md, and the log and diff eacc3a2..HEAD. I read the code that matters most in full:
pipeline/lib/runner.sh, status.sh, log.sh, state.sh, run.sh, and commit c12e600 (the StateLock in state.py and
record_export in export.py). pipeline/knowledge/known-issues.md does not exist yet (it arrives with M3).

## Verdict
APPROVED. The acceptance test passes, review 2's required fix is done and holds up when I test it myself, and I
found no new required fix.

## Acceptance test (run by the reviewer)
`bash pipeline/tests/test-m2.sh`: `220 passed, 0 failed`, exit 0, 9 minutes (real 8m59s).
- Section 2 (two dummy runs): exports/1/ and exports/2/ each hold N.mp4, Ncaptions.txt and Nhook2.mp4, with two
  history lines and an empty ideas.txt. Heartbeat check: `gaps n=31 min=1.26 median=2.23 max=3.25` against a 2 s
  scaled schedule. Every field regex passes, and the NO_COLOR output has no escape codes.
- Section 3 (SIGKILL mid-stage): the restart's START line names the stage it resumes at, the same stage runs
  again, the earlier stages are skipped, and the resumed run exports #1.
- Section 4: crashes planted after assembling and after the move cause neither a duplicate nor a gap.
- Section 5: the drop, code error, FLAG and invalid output paths pass, including the captions checks review 2 saw
  fail (`NEEDS REVIEW` section and the flag text).
- Sections 6 to 8: forever mode, IDLE, NEW, a second runner refused, SIGTERM, a stage that is not built yet,
  runner-status, and the state.json damage scenarios. In each damage scenario the runner prints WARN, retries,
  prints ERROR and STOP, writes STOPPED.md, exits 3, keeps the idea and releases the lock.
- Section 1 lock unit: 20 concurrent flag calls against a touch loop keep all 20 flags, and 10 concurrent issue
  calls count to 10.

Earlier milestones: `bash pipeline/tests/test-m1.sh`: `96 passed, 0 failed`. `bash pipeline/tests/test-no-emdash.sh`:
`1 passed, 0 failed`. Nothing is broken.

## Review 2's fix (checked)
- `StateLock` in state.py locks one byte of runs/<id>/state.lock with `msvcrt.locking` LK_NBLCK and unlocks
  after a seek to 0. Each of the 12 writing commands holds the lock from load to save through `@locked`.
  export.py's three export-record writes reload state.json under the same lock. Nothing nests the lock in one
  process, so it cannot deadlock itself.
- I probed it myself on this machine, outside the test suite. While one Python process held the lock, a second
  process with REELS_STATE_LOCK_WAIT=1 failed after 1 s with `stayed busy for 1s ([Errno 13] Permission denied)`.
  After a `kill -9` of the holder, a new process got the lock at once. So the OS frees the lock when its holder
  dies, as DECISIONS.md 68 says.
- A lock that stays busy is exit 2. `runner_state` turns that into a retry and then the systemic stop.

## Spec compliance and robustness (checked)
- Section 3: the loop, --once, polling, one run folder per idea with state.json and one subfolder per stage, done
  only with a valid output plus `.done`, resume first, no lost work or duplicate export on a kill.
- Sections 6 and 7: the banner, REEL, IDLE, summary, START, STEP, DONE, DROP, BLOCK, NEW, NEXT, FLAG and STOP
  lines, 6-character tags, colors only on a terminal without NO_COLOR, and status.txt. As PLAN.md says, GATE and
  ANGLE are formatted here and first printed by the real gate in M4. LIMIT, RESUME, RETRY, FIXED and ESCAL are
  wired in M3.
- Section 8: N is computed under the exports lock, the export is assembled in runs/<id>/export/, moved with one
  rename, and the captions file follows the section order.
- Section 4: every way the runner stops by itself now goes through `runner_systemic_stop`, with the guard in
  `runner_main` catching any rc 2 that has no STOPPED.md yet.
- Windows: `python` only (the one `python3` mention is an error message telling the user not to use it), C:/
  paths through cygpath -m, LF output from Python. Every file changed since eacc3a2 is free of CRLF and em dashes
  (I checked the bytes with Python). No secrets.
- `.gitignore` has an uncommitted `voicetests/` line. It is the user's own edit, not the build's, so I left it
  alone.

## Required fixes
None.

## Repeated from earlier review
None.

## Optional suggestions (not a reason to reject)
1. **Open items carried over from reviews 1 and 2:**
   - call `state_finish` before removing the idea and writing history in `runner_drop`, `runner_block` and
     `runner_finalize` (or route those calls through `runner_state`), so a crash or a write failure in that
     window cannot resume a run whose idea is already gone
   - on Ctrl+C, kill the stage's whole process tree, not only its bash child (this matters from M4 on, when
     stages start python, node and claude)
   - use `sleep & wait` while idle, so SIGTERM does not wait up to 120 s
   - print the idle line every 5 minutes; today it comes every 360 s, because the check only runs after each
     120 s poll
   - measure the stage timer from the current activity, not from the start of the stage
   - add a test where state.json is read-only (the write-failure path)
   - remove the double stage-done in the orphan path
2. **`run_flag` ignores a failed `state_flag`** (pipeline/lib/state.sh). If the state lock stays busy for 30 s, or
   state.json cannot be written, it still prints `FLAG needs review: ...` while the flag never reaches state.json.
   The export would then have no NEEDS REVIEW section. Print a WARN and return non-zero, so M3's stages can treat
   a lost flag as an error.
3. **A failed `record_export` after the move** (pipeline/lib/export.py). If the last `record_export` fails after
   `rename_with_retries`, export.py exits non-zero, and the runner blocks the idea even though exports/N/ is
   complete. A restart would not repeat the export (`find_export_of` handles that), but history.txt would say
   "blocked" for a reel that exists. This is very unlikely. Retrying the record, or treating the moved folder as
   the truth, would close it.
