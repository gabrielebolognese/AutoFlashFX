# M2 fixes 2: Runner core and terminal output

Fix batch, 2026-10-31, after build/M2/review-2.md (REJECTED, 1 required fix). Read: BUILD_SPEC.md (sections 3, 4,
8 and 12), CLAUDE.md, PLAN.md (M2), DECISIONS.md (up to 67), build/progress.md, build/HUMAN_TODO.md,
build/M2/report.md, review-1.md, fixes-1.md and review-2.md. pipeline/knowledge/known-issues.md does not exist yet
(it arrives with M3).

## Required fix 1: concurrent state.json writers lost updates (a stage's FLAG could vanish before the export)

**What was wrong.** Every state.py command that changes state.json did load, change, save with no lock between
processes. While a stage runs, two processes write the file: the stage (`run_flag` -> `state.py flag`; from M3 on
`issue`, `round` and `set` too) and the runner's heartbeat (`runner_heartbeat` -> `state.py touch`, every
runner.status_every_seconds). When two calls overlapped, the later `os.replace` won and the earlier change was
gone, with exit 0 on both sides. Reproduced before the fix with the reviewer's recipe (a loop of 40 `touch` calls in
the background against 20 `flag` calls): `flag calls that exited 0: 20/20`, `flags in state.json: 17`. In the fast
test mode (heartbeat every 2 s) this made test-m2 section 5 lose the planted flag now and then, so the export's
Ncaptions.txt had no NEEDS REVIEW section.

**What changed** (recorded as DECISIONS.md 68):
- pipeline/lib/state.py: a `StateLock` class and a `locked` decorator. The lock is an OS file lock on
  `runs/<id>/state.lock` (one byte locked with `msvcrt.locking` LK_NBLCK on Windows, `fcntl.flock` elsewhere),
  held from the command's load to its save. The 12 commands that may write carry `@locked`: pickup, next (it
  saves when a .done marker vanished), stage-start, stage-done, stage-fail, reopen, flag, issue, round, set, touch,
  finish. Read-only commands (summary, get, unfinished) stay unlocked, because `os.replace` keeps every read whole;
  `new` creates the folder and needs none.
  - Why an OS lock and not the mkdir lock of ideas.txt: the OS releases it when the holder exits, a kill -9
    included (checked on this machine with a probe: a second process fails at once with EACCES while the lock is
    held, and a holder killed hard frees it immediately), so there is no stale lock to detect and no wait before
    breaking one. The ideas and exports locks are unchanged.
  - Waiting: a waiter polls every 20 ms for up to 30 s (`REELS_STATE_LOCK_WAIT` overrides the seconds, for tests),
    then fails with `the lock runs/<id>/state.lock stayed busy for 30s (...)` and exit 2, which `runner_state`
    turns into the WARN, retry, ERROR and STOP of DECISIONS.md 67. EACCES when opening the lock file (OneDrive or an
    antivirus holding it) is retried within the same wait. A missing run folder keeps its old message (`no
    state.json in ...`), because the lock is taken only next to an existing state.json. The lock file is never
    written and stays in the run folder (0 bytes).
- pipeline/lib/export.py: its three writes of the export record (`intent` before the move, `number` after it, and
  the "already exported" case) go through a new `record_export`, which takes the same StateLock, loads state.json
  fresh and saves. Before, export.py wrote back a state loaded at the start of the export. Nothing else writes
  during the export in M2 (the runner calls it synchronously and no stage runs), so this closes the same hole for
  later milestones rather than a failure seen today.
- pipeline/lib/status.sh line 66 (the heartbeat's `state_touch`) is unchanged: the lock serializes it with the
  stage's writes, and `last_seen` keeps the work-time accounting of DECISIONS.md 56.
- Docs: the state.py docstring, the state.sh header, the export.py docstring, CLAUDE.md's folder map (state.lock),
  build/progress.md (M2 status and check count), DECISIONS.md 68.

**How verified.**
- (a) New unit in test-m2 section 1, 7 checks: 20 `state.py flag` calls and 10 `state.py issue open +1` calls
  launched at once against a background loop of 40 `state.py touch` calls on one run; state.json ends with exactly
  20 flags (20 distinct texts) and issues.open 10, and state.lock sits next to state.json. Then a holder (an inline
  Python that takes StateLock for 4 s) and a `touch` with REELS_STATE_LOCK_WAIT=1: exit 2 after about 1 s with the
  message naming the lock file and the wait; a `touch` with the default wait goes through once the holder is done,
  exit 0, after waiting (3 s measured). Before the fix the same recipe, run by hand, kept 17 of 20 flags; with the
  fix, 20 of 20 in every run (twice by hand, then in the test).
- (b) `bash pipeline/tests/test-m2.sh` by itself: `220 passed, 0 failed` (213 before plus the 7 new checks),
  exit 0, 9.5 minutes; section 5's two captions checks (the `NEEDS REVIEW` section and the flag text) pass; the
  heartbeat check read `gaps n=28 min=1.75 median=2.02 max=2.23`. The second run is the one inside run-all below.
- (c) `bash pipeline/tests/run-all.sh`, right after (b): `test-m1.sh: 96 passed, 0 failed`, `test-m2.sh: 220
  passed, 0 failed` (the second M2 run, section 5 green again), `test-no-emdash.sh: 1 passed, 0 failed`,
  `run-all: 3 test files, all passed`, exit 0, 10 minutes. This second M2 run was slower (110 s against 73 s for
  the two ideas of section 2, with other sessions working on the PC); its heartbeat check still passed (`gaps n=32
  min=1.34 median=2.58 max=3.90`), and the lock unit measured a 4 s wait for the holder.
- Earlier milestones: `test-m1.sh: 96 passed, 0 failed` and `test-no-emdash.sh: 1 passed, 0 failed`, run alone
  before the M2 run and again inside run-all.
- `bash -n` on the changed shell files, `python -m py_compile` on state.py and export.py; no CRLF, no em dash and no
  `python3` in the changed files (checked on bytes with Python).

## Optional suggestions from the review
Not applied, out of the required scope: 1 (state_finish before the removal in drop and block, and routing
`state_stage_fail` and `state_finish` through `runner_state`), 2 (a test for the write-failure path with a read-only
state.json), 3 (the double stage-done in the orphan path). 4 (the runtime): build/progress.md now gives the measured
range instead of one number.

## Files
- Changed: pipeline/lib/state.py, pipeline/lib/export.py, pipeline/lib/state.sh (header), pipeline/tests/test-m2.sh
  (section 1 and the header), DECISIONS.md (item 68), build/progress.md (M2 status), CLAUDE.md (folder map:
  state.lock), build/M2/fixes-2.md (this file).
- build/HUMAN_TODO.md: nothing added, nothing needs the user.
- Not touched, left as the user's uncommitted work: build-runner.new.sh and tools/voice.py (the user's voice
  script, which appeared untracked during this batch; PLAN.md names it for M7). build/M2/review-1.md and
  review-2.md stay uncommitted for the build runner's approval commit, as for M0 and M1.

## Commits
- c12e600 fix(M2): state.json writes hold an OS file lock, so concurrent writers lose nothing (state.py,
  export.py, state.sh, test-m2.sh, DECISIONS.md 68, build/progress.md, CLAUDE.md)
- docs(M2): fixes 2 notes (this file, committed after it was written)
