# M3 fixes 2: Error system

Fixed 2026-10-31 after build/M3/review-2.md (REJECTED, 2 required fixes), in a fresh session. Read BUILD_SPEC.md
(sections 3, 4, 12), CLAUDE.md, PLAN.md (M3), DECISIONS.md (69 to 90), build/progress.md, build/HUMAN_TODO.md,
pipeline/knowledge/known-issues.md, build/M3/report.md, review-1.md, fixes-1.md and review-2.md. Only the two
required fixes were applied; the optional suggestions of both reviews were left alone (listed at the end).

## Required fix 1: a failed stage whose log kept showing a usage limit looped forever

What changed (pipeline/lib/runner.sh, pipeline/lib/limits.sh, pipeline/lib/review.sh, config.json; DECISIONS.md
91, a cross-reference in 88):
- The `limit)` branch of `runner_stage_failed` is now `runner_limit_failed`, which keeps four fields in state.json
  next to transient_tries: `errors.<stage>.limit_tries` (completed or started waits in this failure streak),
  `limit_message` (the limit line the last wait was for), `limit_waited` (false while the wait runs, true once
  it completed) and `limit_probes` (how many probes an unparsed wait needed; 1 means the first probe answered).
  A restart keeps them; the stage passing (the existing "retried stage passed" reset) and the error going to
  review (`review_begin`) reset them, like transient_tries.
- The first limit message always gets its wait, as before (LIMIT, the wait or the probe loop, RESUME,
  logs/limits.log, "attempt N after the usage limit"). The same failure becomes a code error for the review loop
  instead of another wait when:
  (i) the message comes back unchanged right after a wait that completed. For a parsed limit the reset time it
  named has passed, so a genuine new limit would name a new time: "usage limit message persisted after 1 wait
  (the same message right after the reset it named): exit N: <last line>". For an unparsed limit only when the
  probe model answered on its first try (the review's case: no limit was active, so the text is not a limit):
  "usage limit message persisted after 1 wait (the same message, and the probe model had answered at once): ...".
  An unparsed limit whose probe needed several tries may come back with the same text (it has no time in it) and
  gets another wait. `limit_wait_unparsed` exports the probe count as LIMIT_PROBES for this.
  (ii) in any case after `errors.script_limit_retries` waits (new config key, default 2): "usage limit message
  persisted after 2 waits: exit N: <last line>". The reviewer then sees the full log in E<n>.md.
- A wait the previous runner did not finish (killed or rebooted during a limit wait, restarted before the reset)
  is not a completed wait: `limit_waited` stays false, so the rerun's identical real limit message earns its wait
  again (the cap still bounds it).
- Found by the first run of the cap test, part of this fix: stage.log is appended across attempts and the limit
  detector takes the first limit line of the 40-line tail, so attempt 2 was classified from attempt 1's line (a
  stale limit line, or a stale network error, would have been read again at every later attempt).
  `runner_log_mark` now records the log's size at every stage start (`<stage>/.log-offset`) and
  `runner_stage_failed` classifies only this attempt's part of the log (`runner_log_attempt`); the ERROR line
  and E<n>.md are unchanged (the last line, the last 200 lines).
- Model calls inside ai() are not touched: a limit the CLI reports is a real one and its wait loop stays as it
  was (spec 4.1).

How verified (pipeline/tests/test-m3.sh section 9, four new runner passes with the flaky fixture and the fake
claude, REELS_SLEEP_SCALE=0):
- `FLAKY_MODE=limit FLAKY_FAILS=99` with the fake reviewer answering no (the review's first case): exactly one
  LIMIT line and one RESUME line, the rerun announced, then `ERROR S10 building visuals: usage limit message
  persisted after 1 wait (the same message right after the reset it named): exit 1: You've hit your session limit
  · resets 3pm`, one ERROR line, BLOCK on the reviewer's verdict, exactly one reviewer call in the fake log and no
  probe, the event order LIMIT, RESUME, ERROR, BLOCK, two attempts, limit_tries back to 0, E1.md naming the
  persisted message and showing the stage's limit line; the runner exits 0 by itself (run_once's timeout is not
  hit).
- `FLAKY_MODE=limit-new` (new fixture mode: a different reset time at every attempt, "resets 3pm", "4pm", "5pm"):
  two LIMIT lines (the cap), "attempt 3 after the usage limit", then `ERROR ... usage limit message persisted
  after 2 waits: exit 1: ... resets 5pm`, one reviewer call, BLOCK, the order LIMIT, RESUME, LIMIT, RESUME, ERROR,
  BLOCK, three attempts, two waits in limits.log.
- `FLAKY_MODE=quoted-limit` (new fixture mode: the review's second case, a log line "step 1: wrote facts.md (the
  source says Claude Code hit its usage limit, it resets weekly)" followed by a json.decoder.JSONDecodeError
  traceback) with the fake probe answering ok: one LIMIT line (`weekly limit hit but no reset time found, probing
  every 30 min`), `RESUME limit is over (probe 1 answered)`, then `ERROR ... usage limit message persisted after 1
  wait (the same message, and the probe model had answered at once): exit 1: json.decoder.JSONDecodeError: ...`,
  no RETRY, the probe call then one reviewer call in the fake log, BLOCK, the order LIMIT, RESUME, ERROR, BLOCK,
  two attempts, E1.md showing the quoted line to the reviewer.
- The earlier section 9 cases are unchanged: a single limit printed by the stage (FLAKY_FAILS=1) still gets
  LIMIT, RESUME, the rerun and the export with no model call.

## Required fix 2: a traceback echoing a source line with "timeout" made a code error transient

What changed (pipeline/lib/errors.py; DECISIONS.md 92):
- `strip_echo()` runs on the stderr text and on a non-JSON stdout before any pattern (limit detection, retry-after,
  fatal, resume failed, transient). It removes the lines indented deeper than a Python `File "...", line N` line
  (the echoed code and its caret lines), caret-only lines together with the code line above them (Node's
  uncaught-exception header) and JavaScript stack frames (`    at ...`, which carry names like
  `Timeout._onTimeout`). Exception lines, chained causes (`cause: Error: read ECONNRESET`, "The above exception
  was the direct cause") and ordinary log lines stay. The ERROR line's message still comes from the raw text (the
  last line, the exception).
- The timeout pattern no longer matches the bare word. TIMEOUT_WORDS: "timed out", TimeoutError,
  TimeoutException, TimeoutExpired (with any prefix, ReadTimeoutError and the like), ETIMEDOUT, ESOCKETTIMEDOUT,
  undici's UND_ERR_*_TIMEOUT, "timeout exceeded | expired | reached | elapsed | occurred | after N | of N |
  while | waiting", Playwright's "Timeout 30000ms exceeded", Go's "i/o timeout", "due to timeout", "deadline
  exceeded", and the noun phrases "request | connection | connect | read | handshake | navigation | socket |
  response | idle | operation | network | upstream | api timeout" when not followed by a number. A keyword
  argument (`timeout=600`), a Node call (`page.setDefaultTimeout(120000)`), a CLI flag or a config echo
  ("timeout 600 s") no longer count. Exit 124 and 137 still count, as before.
- The 40-line tail is still matched as a whole (the review's optional note about an early transient line
  winning over a final exception is left open, see below).

How verified:
- pipeline/tests/test-limits.sh section 3, ten new checks: the review's KeyError traceback with
  `subprocess.run(cmd, check=True, timeout=600)` in a frame is a code error and its message is `KeyError:
  'beatz'`; the same traceback ending in `subprocess.TimeoutExpired: Command '...' timed out after 600 seconds`
  is transient (timeout); `page.setDefaultTimeout(120000)` followed by `TypeError: Cannot read properties of
  undefined` is a code error; `TimeoutError: Navigation timeout of 30000 ms exceeded` is transient; a Node
  uncaught-exception dump with frames `at Timeout._onTimeout (node:internal/timers)` is a code error; an echoed
  source line `raise ConnectionError("read ECONNRESET")` under a KeyError is a code error; the flaky fixture's
  `TypeError: fetch failed` plus `cause: Error: read ECONNRESET` stays transient; curl's "Operation timed out" is
  transient; a config echo "timeout 600 s, connection timeout=30" before a ValueError is a code error. The
  earlier checks (ECONNRESET on stderr, exit 124, retry-after, FileNotFoundError, a bare 503, a temporary file,
  the stage limit) still pass.
- pipeline/tests/test-m3.sh section 9, one new runner pass: `FLAKY_MODE=traceback` (new fixture mode printing
  that KeyError traceback and exiting 1) gives no RETRY and no LIMIT line, `ERROR S10 building visuals: exit 1:
  KeyError: 'beatz'` at once, one reviewer call, BLOCK, the order ERROR, BLOCK, one attempt, transient_tries 0.

## Test results

`bash pipeline/tests/run-all.sh` after the fixes: 5 test files, all passed, exit 0, 28 minutes on this PC
(started 20:50, finished 21:19):
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed (its section 5 planted code error still goes through the review loop and is
  blocked on the fake reviewer's verdict; the heartbeat schedule check passed on a quiet machine)
- test-m3.sh: 397 passed, 0 failed (356 before the fixes, 41 new in section 9's four runner passes). Section 4 ran
  the real Opus reviewer and Sonnet fixer on the planted `KeyError: 'beatz'` again: ERROR, F1.md, the autofix
  commit in the sandbox repo, FIXED, "attempt 2 after the fix", DONE. Sections 9 and 10 (the review 1 fixes)
  still pass.
- test-limits.sh: 65 passed, 0 failed (55 before, 10 new classifier checks)
- test-no-emdash.sh: 1 passed, 0 failed

Before the suite, section 9 alone found the stale-tail defect described under fix 1 (the cap case got one wait
instead of two, because the detector read attempt 1's limit line from the accumulated log); after the per-attempt
log slice, section 9 passed (84 checks) and the whole suite was run once more, with the result above. The real
repo's HEAD (7b4b75f) and working tree are unchanged by the tests. The changed files have no em dash, no CRLF and
no `python3` call.

## Files changed
- pipeline/lib/runner.sh: runner_limit_failed (new), the limit branch of runner_stage_failed, the counters reset
  on a retried stage's success, the header.
- pipeline/lib/limits.sh: LIMIT_PROBES from limit_wait_unparsed. pipeline/lib/review.sh: review_begin resets the
  limit counters. pipeline/lib/errors.py: strip_echo, TIMEOUT_WORDS, the header. config.json:
  errors.script_limit_retries (2).
- pipeline/tests/fixtures/stages/flaky/run.sh: the modes limit-new, quoted-limit and traceback.
  pipeline/tests/test-limits.sh: ten classifier checks. pipeline/tests/test-m3.sh: four runner passes in
  section 9, the event_tags helper, the probe model name.
- DECISIONS.md 91 and 92 (plus a cross-reference in 88), CLAUDE.md (the build status line), build/progress.md
  (M3).

## Not changed (the reviews' optional suggestions)
Left as they were, because the batch applies only the required fixes: `review_commit` staging all of pipeline/,
the fixer's Bash without git `--disallowedTools` rules, `ai_write_error`'s signature computed without the lib
folder on sys.path, runner_resume_review starting a new cycle when the runner dies between review_record
(no_auto) and review_end, the 40-line tail matched as a whole (an early transient line still wins over a final
exception), the `__pycache__` cp warning of install_stage, and the `tts.fallback` entry in config.json (M7).
