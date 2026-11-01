# M3 review 1: Error system

Reviewer: fresh session, 2026-10-31. Read BUILD_SPEC.md (sections 0, 3, 4, 6 to 9, 12), CLAUDE.md, PLAN.md (M3),
DECISIONS.md 69 to 87, build/progress.md, build/HUMAN_TODO.md, pipeline/knowledge/known-issues.md,
build/M3/report.md, and the full diff 4f1cf3d..HEAD (ai.sh, limits.py/.sh, errors.py/.sh, protect.py,
treeguard.py, review.sh, bin/review-cycle, runner.sh, run.sh, config.json, the prompts and schemas, the fake claude,
the fixtures, test-m3.sh, test-limits.sh). No earlier review or fix files exist for M3.

## Verdict

REJECTED, 2 required fixes. The acceptance test passes and the build is solid overall; the two fixes are
robustness and spec gaps found by reproduction, not by the tests.

## Acceptance test (run by the reviewer)

`bash pipeline/tests/run-all.sh`: 5 test files, all passed, exit 0.
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed
- test-m3.sh: 279 passed, 0 failed. Section 4 ran the real Opus reviewer and Sonnet fixer on the planted
  `KeyError: 'beatz'`: ERROR, E1.md with every part, F1.md with the five parts, the fixer changed the key, the
  `autofix(10-build): ...` commit in the sandbox repo (none in the real repo), one known-issues line, FIXED, "attempt
  2 after the fix", STEP, `DONE exported #1 (..., 1 issue fixed)`; about 1 minute for the cycle.
- test-limits.sh: 47 passed, 0 failed
- test-no-emdash.sh: 1 passed, 0 failed

The real repo's HEAD and working tree were unchanged afterwards.

Independent checks: the limit parser with my own messages and a fixed clock (2026-10-31 12:00 Europe/Rome) gave the
right reset for "resets 3:45pm", "resets 11am" (rolled to tomorrow), "resets Mon 12:00am" (weekly), "resets 3pm
(America/New_York)" (20:00 Rome, EDT before the Nov 1 switch), "resets Nov 3, 10am", "resets Oct 30, 10am" (next
year), epochs in seconds and milliseconds after "|", "resets Sat 9am" on a Saturday (+7 days), and exit 2 (probe
loop) for "limit reached, try later"; the target is always reset + 120 s. The changed files have no em dash, no
CRLF, and no python3 call. `claude --help` lists every flag ai() passes (`--permission-prompts`, `--effort`,
`--tools`, `--json-schema`).

## Required fixes

1. **A runner killed during a review cycle skips all the Opus cycles after the restart.**
   - File: pipeline/lib/review.sh (`review_note_failure`, `review_decide`) and pipeline/lib/runner.sh
     (`runner_code_error`, the restart path in `runner_run_stage`).
   - Problem: `review_note_failure` stores the signature and `repeats=1` before the review child starts, and
     `review_record` only runs after the child ends. When the runner is killed (Ctrl+C, reboot, kill -9) during
     review cycle 1, the restart runs the failed stage again; its identical failure counts as the second repeat, so
     `review_decide` escalates straight to Fable with zero Opus reviews. Reproduced with the fake claude
     (FAKE_CLAUDE_MODE=hang during the review, kill -9 of the runner and its children, restart with
     FAKE_CLAUDE_REVIEW=no). The restart printed:
     `INFO   S10 building visuals: attempt 2 after the fix` (no fix was made),
     `ESCAL  S10 still failing after 0 reviews, escalating to fable`, and the heartbeat showed `issues: 0 fixed, 2
     open` for one error. Spec 4.2.5 allows up to 3 Opus cycles and skips them only when the same signature appears
     twice in a row across review attempts; spec 3 says killing the runner must never lose work. Also, when only the
     runner pid is killed, the review-cycle child (and its fixer) keeps running with no pid file, so the restarted
     runner can run the stage while an orphaned fixer is still editing pipeline/.
   - Expected: a failure whose previous occurrence never got a review (no `review_record` since the last
     `review_note_failure`) is not counted as a repeat, or, better, the restart resumes the pending review cycle
     (E<n> without F<n>.result.json) instead of rerunning the stage. The open-issue counter is not incremented twice
     for the same unreviewed error; "attempt N after the fix" is printed only when the last outcome was `fixed`. An
     orphaned review-cycle child is adopted or killed at startup, like orphaned stages (a pid file under errors/).
   - Verify: a test-m3 case doing the reproduction above: kill the runner while the reviewer call hangs, restart,
     and assert the next review line is `error in S10: reviewing (cycle 1/3, opus)` (no ESCAL before an Opus cycle),
     the fake log shows the reviewer model `opus`, no "after the fix" INFO line, and `issues.open` is 1.

2. **A failed stage script is never classified: limits and transient errors in scripts go straight to the
   reviewer.**
   - File: pipeline/lib/runner.sh (`runner_handle_stage_exit` default branch and `runner_code_error`).
   - Problem: spec section 4 says "On any failed call or script, classify in this order: usage limit, transient,
     code error", with the 60 s, 4 min, 16 min backoff for transient errors and "never send a limit to the
     reviewer". Only model calls inside ai() are classified; a stage script that exits non-zero (a download, gh, a
     Playwright fetch, a render killed by its timeout in later milestones) goes directly to ERROR and the review
     loop. Reproduced: a 10-build stage that prints `fetch failed: ECONNRESET (network reset while downloading)` on
     stderr and exits 1 produced `ERROR S10 ...` immediately and a review cycle, with no RETRY line. A real reviewer
     would most likely answer "external outage, auto_apply no", so a network blip blocks the idea, and three such
     blocks in a row become a systemic STOP, the opposite of rule zero ("waits, retries ... moves on").
   - Expected: before `runner_code_error` starts a review, the runner runs the classifier (errors.py, the same
     patterns ai() uses) on the stage's exit code and the tail of its stage.log/stderr, skipping this when the
     stage's own ai() already wrote an error.json (that error was classified and retried already). A limit waits
     until the reset plus the margin (limit_wait, LIMIT and RESUME lines) and reruns the stage without a review; a
     transient error prints RETRY and reruns the stage after 60 s, 4 min, 16 min (scaled by REELS_SLEEP_SCALE), and
     the fourth failure goes to the review loop as a code error. The counters live in state.json so a restart keeps
     them. Record the choice in DECISIONS.md.
   - Verify: a test-m3 case with a fixture stage that fails with `ECONNRESET` on stderr twice and then succeeds:
     two RETRY lines (60s, 4m in fast-forward), no ERROR, the stage passes; the same stage failing four times ends
     in ERROR and one review cycle; a fixture that prints "You've hit your session limit · resets 3pm" and exits 1
     gets LIMIT and RESUME and no reviewer call in the fake log.

## Repeated from earlier review

None (this is the first review of M3).

## Optional suggestions (do not affect the verdict)

- `review_commit` runs `git add -A -- pipeline motion-lib/candidates`, so any uncommitted work of the user (or of
  an interrupted build batch) under pipeline/ is swept into the `autofix(...)` commit. Consider staging only the
  files the fixer changed (treeguard's `inside` list, or a hash snapshot of pipeline/ before the call), and
  reporting pre-existing modifications in E<n>.md.
- The fixer has Bash under `--permission-mode auto`; add `--disallowedTools` rules for `Bash(git commit:*)`,
  `Bash(git reset:*)`, `Bash(git checkout:*)`, `Bash(git stash:*)`, `Bash(git add:*)` so it cannot commit itself
  (review_commit would then record an empty sha) or discard work inside pipeline/.
- `ai_write_error` runs Python from stdin, where `__file__` is `<stdin>`, so `import errors` looks in the current
  directory and normally falls back to the simpler hash: error.json's `signature` differs from
  `errors.py signature` for the same message. The runner recomputes the signature from the message, so nothing
  breaks today; pass the lib folder explicitly (`$REELS_PIPELINE/lib`) so the field is trustworthy for M4+.
- After a usage limit on a fresh call that already returned a session id, the retry starts a new session (the same
  command, no `--resume`). Spec 4.1 says "retry the same call in the same session"; resuming the returned session
  id when there is one would follow it more literally.
- A reset time equal to the current minute ("resets 12pm" at 12:00) rolls over a whole day; a strictly-past test
  would wait 2 minutes instead of 24 hours.
- Outside M3: config.json still has `tts.fallback: kokoro` and the banner prints "voice: chatterbox (fallback
  kokoro)", while commit a8765bf changed the spec to a single voice with no fallback engine. M7 should remove it.
