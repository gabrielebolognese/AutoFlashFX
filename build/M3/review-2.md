# M3 review 2: Error system

Reviewer: fresh session, 2026-10-31. Read BUILD_SPEC.md (sections 3, 4, 6 to 9, 12), CLAUDE.md, PLAN.md (M3),
DECISIONS.md (69 to 90), build/progress.md, build/HUMAN_TODO.md, pipeline/knowledge/known-issues.md,
build/M3/report.md, review-1.md, fixes-1.md, and the diff 4f1cf3d..HEAD with a close read of the fix commit
525b367 (runner.sh, review.sh, limits.sh, state.sh, errors.py, the flaky fixture, test-m3 sections 9 and 10).

## Verdict

REJECTED, 2 required fixes. The acceptance test passes, and both fixes from review 1 work as tested. The two
required fixes are new defects in fix 2 (classifying a failed stage script from its log tail), found by
reproduction: one can keep an idea stuck forever, which breaks rule zero, and the other sends ordinary code
errors through 21 minutes of transient retries.

## Acceptance test (run by the reviewer)

`bash pipeline/tests/run-all.sh`: 5 test files, all passed, exit 0, about 27 minutes.
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed (including the heartbeat schedule check)
- test-m3.sh: 356 passed, 0 failed. Section 4 ran the real Opus reviewer and Sonnet fixer on the planted bug:
  ERROR, F1.md with the root cause, class, changes, verify command and auto_apply yes, the autofix commit in the
  sandbox repo, FIXED, the restart, DONE counting the fixed issue. Sections 9 (stage script classification) and
  10 (a runner killed during a review cycle resumes it, adopts a live child) pass. One harmless noise line:
  `cp: -r not specified; omitting directory .../fixtures/stages/buggy/__pycache__` (a pycache folder in the real
  fixture folder; it is gitignored).
- test-limits.sh: 55 passed, 0 failed
- test-no-emdash.sh: 1 passed, 0 failed

The real repo's HEAD (7b4b75f) and working tree were unchanged afterwards. The changed files have no em dash, no
CRLF, no `python3` call and no secret.

## Required fixes

1. **A failed stage whose log keeps showing a usage limit loops forever and never reaches the review or a block.**
   - File: pipeline/lib/runner.sh, `runner_stage_failed`, the `limit)` branch.
   - Problem: the limit branch has no counter. When the tail of stage.log matches the limit patterns, the runner
     waits (limit_wait, or limit_wait_unparsed plus the probe) and then reruns the stage. If the rerun fails with
     the same text, it waits again, with no limit. Two ways this happens: (a) the limit text is not a real limit,
     for example a stage that prints research text quoting "hit its usage limit, it resets weekly" (this project's
     ideas are about Claude Code, so such quotes are likely) and then fails on a real exception. The probe answers
     right away, which proves no limit is active, and the stage runs again forever, once every 30 minutes. (b) A
     parsed "resets 3pm" line that keeps coming back: each rerun rolls the reset to the next day, so the idea
     waits one day per attempt, forever. Spec section 4, rule zero: the runner "waits, retries, reviews, fixes,
     flags, drops or blocks one idea, and moves on"; a code error must reach the review (4.2).
     Reproduced in a sandbox with the fake claude and `REELS_SLEEP_SCALE=0`, each run capped at 60 s by `timeout`:
     - the flaky fixture with `FLAKY_MODE=limit FLAKY_FAILS=999`: 8 LIMIT/RESUME pairs (`LIMIT session limit hit,
       resuming at Sun 15:02`), 8 attempts, 0 ERROR lines, killed by the timeout (exit 124).
     - a stage that prints `step 1: wrote facts.md (the source says Claude Code hit its usage limit, it resets
       weekly)` and then a `json.decoder.JSONDecodeError` traceback, exit 1: 6 lines `LIMIT weekly limit hit but
       no reset time found`, 5 lines `RESUME limit is over (probe 1 answered)`, 0 ERROR lines, exit 124.
   - Expected: the limit path of a failed stage script is bounded and is never trusted after the evidence says
     otherwise. (i) When the probe answers on its first try after an unparsed limit, and the rerun fails with the
     same limit text, that text is not a limit: classify it as a code error. (ii) Keep a counter
     `errors.<stage>.limit_tries` in state.json (like transient_tries; reset when the stage passes or the error goes
     to review). When the same stage fails again with the same limit message right after a completed wait (or
     after a configurable cap, for example `errors.script_limit_retries`, default 2), send it to the review loop
     as a code error, for example "usage limit message persisted after 2 waits: exit N: <last line>". The reviewer
     then sees the full log. A real limit that is printed again after a genuine reset still gets its wait the
     first time. Record the choice in DECISIONS.md (next to 88).
   - Verify: a test-m3 section 9 case with the flaky fixture `FLAKY_MODE=limit FLAKY_FAILS=99` and the fake
     reviewer answering no. Assert: at most the capped number of LIMIT lines, then one ERROR naming the persisted
     limit, one reviewer call in the fake log, BLOCK, the runner exits by itself (no timeout). A second case: a
     stage printing a quoted "usage limit ... resets weekly" line, then a traceback, with the fake probe answering
     ok. Assert: at most one LIMIT line, then ERROR and the review.

2. **A Python traceback that shows a source line containing "timeout" makes a plain code error transient (three
   retries, 21 minutes, then a misleading ERROR line).**
   - File: pipeline/lib/runner.sh (`runner_stage_failed`) and pipeline/lib/errors.py (TRANSIENT_PATTERNS, applied
     to the log tail).
   - Problem: the transient patterns run on the last 40 lines of stage.log, and a Python traceback echoes the
     source line of every frame. Any frame like `subprocess.run(cmd, check=True, timeout=600)` or
     `requests.get(url, timeout=30)` matches `timeout`, so a real exception (KeyError, TypeError) is classified
     transient. This pipeline calls ffmpeg, renders, TTS and alignment through subprocess with the configured
     `timeouts.*`, so most tracebacks from M4 on will contain such a line. The same happens with Node errors whose
     log shows `page.setDefaultTimeout(120000)`. The cost per code error: 60 s + 4 min + 16 min of backoff before
     the review, and the ERROR line and E1.md headline read "temporary error persisted after 3 retries (timeout)",
     which points the reviewer at an outage instead of the bug (spec section 4: an exception is type 3, review and
     fix). Reproduced in a sandbox: a stage printing the traceback below and exiting 1 produced
     `RETRY temporary error (timeout), retrying in 60s (try 1/3)`, `... 4m (try 2/3)`, `... 16m (try 3/3)`, then
     `ERROR S10 building visuals: temporary error persisted after 3 retries (timeout): exit 1: KeyError: 'beatz'`.
     ```
     Traceback (most recent call last):
       File "C:/x/pipeline/stages/10-build/helper.py", line 12, in <module>
         r = subprocess.run(cmd, check=True, timeout=600)
       File "C:/x/pipeline/stages/10-build/helper.py", line 20, in build
         beats = plan["beatz"]
     KeyError: 'beatz'
     ```
     `python pipeline/lib/errors.py classify --rc 1 --stderr <that file>` prints class `transient`, detail `timeout`.
   - Expected: echoed source code is not read as an error message. For example: before the classifier runs on a
     stage log, drop the code lines of Python tracebacks (the indented line after each `File "...", line N, in ...`
     line), or classify from the final exception lines only when the tail contains a traceback (`Traceback (most
     recent call last)` plus the last `SomethingError: ...` line, Node's `at ...` frames removed). Also require
     the timeout words to look like an error (`timed out`, `TimeoutError`, `ETIMEDOUT`, `timeout exceeded`, exit
     124/137) rather than any `timeout` substring, such as a keyword argument. A real timeout (`subprocess.TimeoutExpired:
     Command '...' timed out after 600 seconds`, `TimeoutError: Navigation timeout of 30000 ms exceeded`) stays
     transient, and the flaky fixture's `TypeError: fetch failed` plus `cause: Error: read ECONNRESET` stays
     transient.
   - Verify: test-limits.sh checks for the traceback above (code error), the same traceback ending in
     `subprocess.TimeoutExpired: ... timed out after 600 seconds` (transient), and a Node log line
     `page.setDefaultTimeout(120000)` followed by `TypeError: Cannot read properties of undefined` (code error).
     Plus a test-m3 section 9 case: a stage printing that KeyError traceback gets ERROR at once (no RETRY line) and
     one review.

## Repeated from earlier review

None. Both required fixes of review 1 are fixed and tested (section 10 for the interrupted review cycle, section 9
for the classification of failed stage scripts). The two fixes above are new defects in the code added by fix 2,
not repeats.

## Optional suggestions (do not affect the verdict)

- Still open from review 1 (optional there too): `review_commit` runs `git add -A` on all of pipeline/ and
  motion-lib/candidates/, so uncommitted work there is swept into an `autofix(...)` commit. The fixer's Bash under
  `--permission-mode auto` has no `--disallowedTools` rules for `git commit`, `git reset`, `git checkout` and
  `git stash`. `ai_write_error` computes its signature without the lib folder on sys.path.
- runner_resume_review: if the runner dies in the few milliseconds between `review_record` (outcome no_auto) and
  `review_end`, the restart finds no pending cycle and a last_outcome of no_auto, and starts another review cycle
  instead of blocking. Treating last_outcome no_auto (with nothing pending) as "block now" would close that gap.
- The 40-line tail is matched as a whole, so a transient-looking line written early in the tail wins over a
  clear exception at the end. When the last line is an exception, it could take priority. This is related to
  fix 2 but broader.
- A `__pycache__` folder in pipeline/tests/fixtures/stages/buggy/ makes `install_stage` print a `cp` warning;
  copy only files (`cp "$dir"/*.py "$dir"/*.sh`) or delete pycache in sandbox_init.
- Outside M3: config.json still has `tts.fallback`, while the spec now has a single voice with no fallback engine
  (M7).
