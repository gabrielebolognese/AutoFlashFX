# M3 fixes 1: Error system

Fixed 2026-10-31 after build/M3/review-1.md (REJECTED, 2 required fixes), in a fresh session. Read BUILD_SPEC.md
(sections 0, 3, 4, 6, 7, 9, 12), CLAUDE.md, PLAN.md (M3), DECISIONS.md, build/progress.md, build/HUMAN_TODO.md,
pipeline/knowledge/known-issues.md, build/M3/report.md and review-1.md (the first review of M3; no earlier fix
notes exist). Only the two required fixes were applied, plus one defect they exposed (the classifier's text
patterns on stage logs, below, part of fix 2). The optional suggestions of the review were left alone.

## Required fix 1: a runner killed during a review cycle skipped all the Opus cycles after the restart

What changed (pipeline/lib/runner.sh, pipeline/lib/review.sh, pipeline/lib/state.sh; DECISIONS.md 89):
- The runner now records the loop in state.json: `review_begin` writes `errors.<stage>.review` (active, rc, msg,
  cmd, activity) when a code error enters the loop, `review_pending_set` writes `errors.<stage>.pending` (the
  cycle number E<n>) before the review-cycle child starts, `review_record` clears pending when the verdict is
  recorded, `review_end` turns the review off with the restart reason (fixed or blocked). The child's pid goes to
  `errors/E<n>.pid`, like a stage's `.pid`.
- `runner_run_stage` checks a failed stage first: when its review is active it calls `runner_resume_review`,
  which runs the loop again (`runner_review_loop`, the former body of `runner_code_error`) instead of running the
  stage. The loop reuses the pending cycle number: `runner_adopt_review` waits for a child that still runs (WARN
  line, the heartbeat keeps printing), takes the verdict in `fixes/F<n>.result.json` when the child finished
  (fixed, no_auto or failed), and runs the cycle again under the same E<n> when it ended without a verdict
  (killed with the runner). The INFO line reads `review cycle E1 (cycle 1/3, opus) was interrupted by the
  previous runner, resuming it: <error>`; the ESCAL line is not repeated for a resumed escalation. A runner killed
  between the verdict fixed and the restart (last_outcome fixed, nothing pending) just runs the stage again.
- `review_note_failure` counts a repeat only when the previous failure got its review (`errors.<stage>.reviewed`,
  false after a failure, true after `review_record`), which is the spec's "twice in a row" across review
  attempts. The open-issue counter is incremented once per ERROR line, and a resumed review prints no ERROR line.
- The INFO line of a rerun of a failed stage names the recorded reason (`errors.<stage>.restart`): "after the fix"
  only when a fix was applied, "after the temporary error", "after the usage limit", "(the previous one failed)";
  a stage that was running when the runner died keeps "(the previous one was interrupted)".
- `json_quote` (state.sh) encodes the message and command as JSON strings for `state_set`.

How verified: pipeline/tests/test-m3.sh section 10 (new), with the unfixable fixture and the fake claude:
- (a) The fake reviewer hangs (FAKE_CLAUDE_MODE=hang); after the reviewer call started, the test kills the
  runner and its whole process tree (`kill_tree`, parents first, from `ps -ef` parent pids) and restarts with a
  reviewer that answers auto_apply no. Asserted: state after the kill (stage failed, review active, pending 1,
  no cycle recorded, E1.pid left), then on the restart the INFO line `review cycle E1 (cycle 1/3, opus) was
  interrupted by the previous runner, resuming it: exit 1: FileNotFoundError...`, no ESCAL, no second ERROR, no
  RETRY, no FIXED, no "after the fix" line, BLOCK on the resumed cycle's verdict, the fake log with exactly two
  reviewer calls both with the Opus model, state cycles 1, repeats 1, escalated false, issues.open 1, attempts 1,
  pending cleared, E1.pid removed, no E2.md, F1.result.json with outcome no_auto, blocked.txt.
- (b) The fake reviewer is slow (FAKE_CLAUDE_DELAY=20, new knob); only the runner is killed. Asserted: the
  review-cycle child still runs, the restart prints `WARN S10: review cycle E1 still runs from the previous
  runner (pid N), waiting for it instead of starting it twice`, then BLOCK on its verdict, one reviewer call in
  all, cycles 1, issues.open 1, no ESCAL, the child gone and its pid file removed.
- The earlier sections (4 with the real models, 5, 6, 7) still pass: the counters, the repeated-signature
  shortcut (ERROR, FIXED, ERROR, ESCAL, FIXED, ERROR, BLOCK) and the failed-verification ladder are unchanged.

## Required fix 2: a failed stage script was never classified

What changed (pipeline/lib/runner.sh, pipeline/lib/limits.sh, pipeline/lib/errors.py, config.json; DECISIONS.md
88 and 90):
- `runner_handle_stage_exit` sends a non-zero exit (other than 10 and 20) to the new `runner_stage_failed`, which
  runs the classifier (`error_classify`, pipeline/lib/errors.py, the same patterns ai() uses) on the exit code
  and the last `errors.classify_tail_lines` (40, new config key) of stage.log, CR stripped. A stage whose own
  model call failed has `<stage>/error.json` from ai() (the runner removes the file at every stage start, so it
  is this attempt's) and goes straight to the review: that call was classified and retried inside ai().
- A limit: `state_stage_fail` with the message, `limit_wait` (LIMIT line, logs/limits.log, the wait until the
  reset plus the margin, RESUME line) or `limit_wait_unparsed` with `ai_probe`, then the stage runs again with
  `INFO ... attempt N after the usage limit`. No review, no reviewer call.
- A transient error: `errors.<stage>.transient_tries` in state.json (so a restart keeps the ladder), RETRY line
  `temporary error (<detail>), retrying in 60s (try 1/3)` then 4m and 16m (the configured backoff, scaled by
  REELS_SLEEP_SCALE; a larger retry-after replaces the step), the activity text "retrying after temporary error
  ...", the stage runs again with `INFO ... attempt N after the temporary error`; the fourth failure is a code
  error `temporary error persisted after 3 retries (<detail>): exit N: <last line>` and enters the review loop.
  A success (a retried stage that passes) or a code error resets the counter.
- The runner's own waits keep the heartbeat alive: `reels_sleep_raw` and `reels_wait_until` (limits.sh) call
  `reels_tick_hook` between 60 s chunks, which runs `reels_wait_tick` when the caller defines it; runner.sh
  defines it as `runner_tick` (heartbeat and NEW lines). Stages and review-cycle do not define it.
- Found by the first dry run, part of this fix: the classifier's text patterns were written for CLI results and
  misfired on stage logs. "FileNotFoundError" matched the ENOTFOUND pattern case-insensitively (the unfixable
  fixture came out transient), a bare "503" or "429" in a log counted as an HTTP status, and "temporary file"
  counted as a temporary error. The error codes are now word-bounded, a status number needs a word next to it
  ("API Error: 503", "HTTP 502", "status 500"; the JSON field api_error_status still counts alone), and
  "temporary" needs "failure", "error", "problem", "outage" or "temporarily unavailable". The detail label of a
  529 found in text is "overloaded" (as when found in the JSON field).

How verified:
- pipeline/tests/test-m3.sh section 9 (new), with the new fixture pipeline/tests/fixtures/stages/flaky/ (fails
  FLAKY_FAILS times in FLAKY_MODE reset, limit or error, then writes a valid events.json):
  - a network reset twice then success: `RETRY ... 60s (try 1/3)`, `RETRY ... 4m (try 2/3)`, two fast-forward
    backoff waits, the INFO lines of the reruns, no ERROR, BLOCK, FIXED or ESCAL, STEP, DONE, zero model calls,
    attempts 3, transient_tries reset to 0, issues 0;
  - the same stage failing four times: three RETRY lines (60 s, 4 min, 16 min), one ERROR `temporary error
    persisted after 3 retries (connection reset): exit 1: ...ECONNRESET`, then BLOCK on the fake reviewer's
    verdict, exactly one reviewer call, attempts 4, E1.md naming the persisted error, the tag order RETRY, RETRY,
    RETRY, ERROR, BLOCK;
  - a usage limit printed by the stage ("You've hit your session limit · resets 3pm"): LIMIT with the kind,
    target and margin, the fast-forward wait, `RESUME limit reset, continuing: building visuals`, `attempt 2
    after the usage limit`, no ERROR or RETRY, DONE, zero model calls, the limits.log line with the stage's
    message, attempts 2;
  - a stage whose own ai() call failed (fake script: an error result, then a reviewer answering no) with a
    transient-looking last log line (AICALL_FAIL_NOTE, new knob of the aicall fixture): no RETRY, ERROR at once
    with that last line, BLOCK, the stage's call then one reviewer call, attempts 1, E1.md carrying error.json.
- pipeline/tests/test-limits.sh gained eight classifier checks: FileNotFoundError is a code error, a bare 503 in
  a log is not a status, a temporary file is not a temporary error, `API Error: 503` is transient (server
  error), `getaddrinfo ENOTFOUND` is transient (network error), `connection refused` is transient, `Temporary
  failure in name resolution` is transient, and a limit printed by a stage script is a limit.
- Section 2's runner pass (a limit inside a stage through ai()) and section 3 (ai() transient backoff) still
  pass, so the model-call path is unchanged.

## Test results

`bash pipeline/tests/run-all.sh` after the fixes: 5 test files, all passed, exit 0, about 25 minutes on this PC
(started 19:28, finished 19:53):
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed (section 5's planted code error still goes through the review loop and is
  blocked on the fake reviewer's verdict; a planted failure is classified as a code error, not retried)
- test-m3.sh: 356 passed, 0 failed (279 before the fixes, 77 new in sections 9 and 10). Section 4 ran the real Opus
  reviewer and Sonnet fixer on the planted `KeyError: 'beatz'` again: ERROR, F1.md, the autofix commit in the
  sandbox repo, FIXED, "attempt 2 after the fix", DONE, about 1 minute.
- test-limits.sh: 55 passed, 0 failed (47 before, 8 new classifier checks)
- test-no-emdash.sh: 1 passed, 0 failed

Before the suite, sections 9 and 10 alone found the ENOTFOUND defect (the unfixable fixture classified as
transient) and two test-side mistakes (state.json keys read without a default), both fixed before the full run.
The real repo's HEAD and working tree are unchanged by the tests (section 4 asserts it). The changed files have
no em dash, no CRLF and no `python3` call.

## Files changed
- pipeline/lib/runner.sh: runner_stage_failed (new), runner_code_error split into the prologue and
  runner_review_loop, runner_resume_review and runner_adopt_review (new), the INFO wording by restart reason,
  error.json removed at stage start, the transient counter reset on success, reels_wait_tick, the header.
- pipeline/lib/review.sh: review_begin, review_pending_set, review_end (new), review_note_failure (repeats only
  after a review), review_record (clears pending, sets reviewed), the header.
- pipeline/lib/limits.sh: chunked sleeps with reels_tick_hook. pipeline/lib/state.sh: json_quote.
- pipeline/lib/errors.py: the tightened transient patterns. config.json: errors.classify_tail_lines.
- pipeline/tests/test-m3.sh: sections 9 and 10, wait_gone and kill_tree helpers, the reviewer model names hoisted
  to the top. pipeline/tests/test-limits.sh: eight classifier checks. pipeline/tests/fakes/claude.py:
  FAKE_CLAUDE_DELAY. pipeline/tests/fixtures/stages/flaky/run.sh (new), fixtures/stages/aicall/run.sh
  (AICALL_FAIL_NOTE).
- DECISIONS.md 88 to 90, CLAUDE.md (the automatic fixes rule, the build status line), build/progress.md (M3).

## Not changed (the review's optional suggestions)
Left as they were, because the batch applies only the required fixes: `review_commit` staging all of pipeline/,
the fixer's Bash without git `--disallowedTools` rules, `ai_write_error`'s signature computed without the lib
folder on sys.path, a limit retry that starts a new session when the failed call already returned a session id,
a reset time equal to the current minute rolling over a day, and the `tts.fallback` entry in config.json (M7).
