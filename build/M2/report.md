# M2 report: Runner core and terminal output

Built 2026-10-31 from BUILD_SPEC.md section 12 (M2) and PLAN.md (M2). Acceptance test green: 183 checks
in about 6.5 minutes, no model calls (dummy stages). M1's test still passes (96 checks).

## What this batch built
- **The runner loop** (run.sh, pipeline/lib/runner.sh): take the first idea or resume the unfinished run, create
  `runs/<YYYY-MM-DD_HHMM>_<slug>/`, run the 16 stages in order as background child processes (stdout and stderr in
  `<stage>/stage.log`, the terminal on fd 3 so a stage's `say` lines still show), handle the exit codes (0 done
  after schema validation, 10 drop, 20 block, anything else a code error), export, drop or block, next idea.
  `--once` exits when the queue is empty; otherwise the runner polls every `runner.poll_seconds`. A runner lock
  (`.locks/runner`, pid plus liveness) refuses a second runner. Ctrl+C or SIGTERM stops it cleanly and the next
  start resumes.
- **The state machine** (pipeline/lib/state.py, state.sh): state.json with the idea, the stage order and per-stage
  status, attempts, timestamps, session id slot, exit code and error; flags, issue and round counters; export
  intent and number; work-time accounting across sessions. `.done` markers written only after the primary output
  validates against `pipeline/stages/<stage>/schema.json`; `next` re-checks the markers; `reopen` for the gate and
  review loops; `unfinished` for the resume; `pickup` for the session accounting.
- **Resume and crash safety:** a SIGKILL mid-stage leaves the stage `running` without `.done`; the next start says
  `START ... (resumed at picking hooks, 3 stages done)`, announces `attempt 2 (the previous one was interrupted)`,
  skips the done stages and finishes the run in the same folder. An orphaned stage process (runner killed, child
  alive) is waited for and judged by its outputs instead of being started twice.
- **Exports** (pipeline/lib/export.py, export.sh): N = highest number in exports/ plus 1 under `.locks/exports`;
  `runs/<id>/export/` assembled (N.mp4, Nhook2.mp4 copied; Ncaptions.txt rendered from 14-export/export.json in
  the exact format of spec section 8, because the HOOKS lines need N) and moved into `exports/N/` with one
  rename. Two-phase record in state.json plus the RUN section of every captions file make a crash between
  assembling and moving, or right after the move, produce neither a duplicate nor a gap on restart.
- **History and blocked** (pipeline/lib/history.sh): `date | idea | exported N`, `dropped: reason`,
  `blocked: reason`; logs/blocked.txt with a comment line (date, stage, reason, run folder) and the idea in
  braces, ready to paste back.
- **Every terminal line of spec sections 6 and 7** (pipeline/lib/log.sh, status.sh): the banner, `REEL` heartbeat
  every `runner.status_every_seconds` with `#idea i/n`, the idea text cut at 40 characters, the activity (stages
  publish theirs with `set_activity`), minute, stage time and issue counters; `IDLE` with the poll interval, idle
  minutes and today's counts from history.txt; the summary line when the queue empties; `START`, `STEP`, `DONE`,
  `DROP`, `BLOCK`, `NEW` (from add-idea.sh's records, with "Claude Code" as the source inside a Claude Code
  session), `NEXT`, `FLAG`, `STOP`; colors on a terminal, plain text under NO_COLOR or a pipe; runner.log gets
  every line and status.txt the latest status (QUEUE listings and INFO chatter excepted).
- **16 stage folders** under pipeline/stages/, each with a first CONTRACT.md (purpose, inputs, outputs, invariants,
  exit codes, model and session from spec section 5), a first schema.json for the stage's primary JSON output, and
  a dummy.sh that writes outputs which validate (shared helper pipeline/lib/dummy.sh with REELS_DUMMY_SECONDS and
  the planted FAIL, DROP, BLOCK, FLAG and INVALID behaviors). The real run.sh and prompt.md of each stage arrive
  with its milestone.
- **Until M3:** a code error (non-zero exit or invalid output) prints `ERROR`, counts an open issue and blocks the
  idea with the reason "code error ... (no automatic fix before M3)", so the runner moves on (rule zero); a stage
  whose run.sh is not built yet is a systemic stop with logs/STOPPED.md and the idea stays in ideas.txt.
- **pipeline/bin/runner-status**: whether a runner is alive, the latest status line, STOPPED and blocked hints,
  the log tail.
- **Tests:** pipeline/tests/test-m2.sh (seven sections, see below). test-m1.sh section 7 now starts the runner
  with an empty queue (run.sh processes the queue since this batch). tests/lib.sh fast_mode gained
  REELS_TICK_SECONDS and REELS_DUMMY_SECONDS.

## Files
- New: pipeline/lib/{runner.sh, state.py, state.sh, status.sh, history.sh, export.py, export.sh, dummy.sh},
  pipeline/bin/runner-status, pipeline/stages/<16 stages>/{CONTRACT.md, schema.json, dummy.sh},
  pipeline/tests/test-m2.sh, build/M2/report.md.
- Changed: run.sh (the loop), pipeline/lib/log.sh (fd 3 for stages, status skip tags, duration and text helpers,
  no fork per line), pipeline/lib/ideas.py (the lock class takes a name; the ideas lock is unchanged),
  pipeline/bin/add-idea.sh (source name for the NEW line), pipeline/tests/lib.sh, pipeline/tests/test-m1.sh
  (section 7), CLAUDE.md (build status, runner notes, the escaped newline snippet from the M1 review), DECISIONS.md
  (items 52 to 66), build/progress.md, build/HUMAN_TODO.md.
- Removed: pipeline/stages/.gitkeep (the folder has content now).
- Earlier milestones touched: M1's ideas.py, add-idea.sh, log.sh, tests/lib.sh and test-m1.sh as listed above,
  because M2 builds on them (DECISIONS.md 66). M1's test passes unchanged in meaning.

## How to run the test
```
bash pipeline/tests/test-m2.sh          # the M2 acceptance test (about 6.5 minutes)
bash pipeline/tests/test-m1.sh          # M1 (about 40 s)
bash pipeline/tests/run-all.sh          # everything plus the em dash scan (about 8 minutes)
```
KEEP_SANDBOX=1 keeps the temporary roots. The tests never touch the real ideas.txt, runs/, exports/ or logs/.
To watch the runner by hand: `REELS_DUMMY=all bash run.sh --once` (dummy stages; it removes the processed idea
from ideas.txt and writes dummy files to exports/, so prefer a copy of the folder).

## Test output summary
`test-m2.sh: 183 passed, 0 failed` (about 6.5 minutes), `test-m1.sh: 96 passed, 0 failed`,
`test-no-emdash.sh: 1 passed`.
1. Units: the 16-stage table (04-angle starts skipped), the slug, run creation (state.json, idea.txt, 16
   subfolders), stage-start and stage-done (an output missing a required field fails with exit 5 and names the
   field, no `.done`; the dummy output validates and `.done` appears), reopen, session counting, flags, export
   numbering (empty: 1; folders 3 and 7 plus a stray one: 8), the captions render with every section in order,
   the HOOKS lines carrying the number, NEEDS REVIEW from the flags and the RUN section.
2. Two dummy ideas: banner with `queue: 2 ideas`, the QUEUE listing, `START idea 1/2 "...cut at 40..." -> runs/...`,
   30 STEP lines (angle skipped), `DONE exported #1`, `NEXT idea 2/2`, `DONE exported #2`, the IDLE summary with the
   session counts; exports/1 and exports/2 with N.mp4, Ncaptions.txt and Nhook2.mp4, the staging folders gone, two
   history lines (accents intact), ideas.txt empty, both runs exported in state.json; every REEL line matches the
   field regex, the heartbeat gaps stay within the scaled schedule (REELS_STATUS_EVERY=2); status.txt equals the
   last line; runner.log mirrors the terminal; no escape codes.
3. SIGKILL during 05-hooks (runner and stage child killed): state shows the stage running without `.done`, the
   restart prints the resumed START line and the attempt 2 note, skips the earlier stages, exports #1, one run
   folder, attempts 1 and 2, two sessions, one history line.
4. Crash planted after assembling: nothing in exports/, intent recorded, the leftover exports lock removed at the
   next start, the restart resumes "at exporting, 15 stages done" and exports #1 once. Crash planted after the
   move: exports/2 exists, the restart recognizes it as this run's export, no exports/3, one history line.
5. Three ideas with a planted gate drop, a planted build failure and a planted flag: DROP, NEXT 2/3, ERROR with the
   stage's last log line, BLOCK, NEXT 3/3, FLAG, the third idea exported as #1 (no gap), the summary counts,
   history and blocked.txt lines, three run folders with statuses dropped, blocked, exported, the NEEDS REVIEW
   section in the captions file, the open issue counter; an invalid 05-hooks output gives an ERROR naming the
   schema violation and a block.
6. Forever mode with an empty queue: the summary line, the IDLE line with "checking every 1 s (idle 0 min)" and
   today's counts, a second runner refused with the running pid, an idea added with add-idea.sh under CLAUDECODE
   produces `NEW idea added from Claude Code (queue: 1)`, START, DONE, the summary again and IDLE with
   `today: 1 exported`; SIGTERM prints the stop line and releases the lock.
7. Without REELS_DUMMY the first stage is not built: exit 3, the STOP line, STOPPED.md with the fix, the idea kept
   in ideas.txt, the run kept; runner-status reports all of it; a later dummy start removes STOPPED.md, resumes the
   kept run from its first stage and exports it.

## Known gaps
- The error path is M3: today a code error blocks the idea (DECISIONS.md 60) and the lines LIMIT, RESUME, RETRY,
  FIXED and ESCAL are formatted by `say` but never printed.
- The schemas and CONTRACT.md files are first versions; each stage's milestone refines them (the file names and the
  primary output per stage are fixed in state.py).
- Runner overhead is about 2 s per stage transition on this machine (Python start-ups, the jsonschema import,
  Windows forks), irrelevant next to real stages but it sets the test's runtime.
- The heartbeat's work-time accounting has the heartbeat's granularity: a crash loses at most one interval.
- The `REEL` denominator uses the ideas still in ideas.txt; an unfinished run whose idea was removed by hand shows
  `i/i`.

## HUMAN_TODO items added
- M2: nothing required; a note that `bash run.sh` stops with STOPPED.md until the real stages exist, how to watch
  the loop with dummy stages, and how to re-add a blocked idea from logs/blocked.txt.

## Commits
- feat(M2): runner core: loop, state machine, resume, exports numbering, history, status lines, dummy stages
- docs(M2): decisions 52 to 66, progress, human todo, CLAUDE.md build status
- docs(M2): report (this file, committed after it was written)
