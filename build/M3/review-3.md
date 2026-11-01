# M3 review 3: Error system

Reviewer: fresh session, 2026-11-01 (the previous review 3 attempt stopped on an API connection error before
writing anything, see build/STOPPED.md; this review started over). Read BUILD_SPEC.md (sections 0, 1, 3, 4, 6 to
9, 11, 12), CLAUDE.md, PLAN.md (M3), DECISIONS.md, build/progress.md, build/HUMAN_TODO.md,
pipeline/knowledge/known-issues.md, build/M3/report.md, review-1.md, fixes-1.md, review-2.md, fixes-2.md, and the
diff 4f1cf3d..HEAD, closely reading runner.sh (runner_stage_failed, runner_limit_failed, the review loop and its
resume), review.sh, ai.sh, errors.py, limits.sh and the section 9 fixtures.

## Verdict

REJECTED, 2 required fixes. The acceptance test passes and every fix from reviews 1 and 2 works as tested. Both
required fixes are new, found by reproduction: (1) the classifier misses the network errors this PC actually
produces, including Claude Code's own "No response from API", so a network blip becomes a code error, a review and
usually a block; (2) the runner copies external error text verbatim into its terminal lines and logs, and the
Claude CLI's network message on this PC contains an em dash, which the spec forbids in any file or terminal
message.

## Acceptance test (run by the reviewer)

`bash pipeline/tests/run-all.sh`: about 30 minutes, exit 1 only because of the em dash scan. Details:
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed (including the heartbeat schedule check)
- test-m3.sh: 397 passed, 0 failed. Section 4 ran the real Opus reviewer and Sonnet fixer on the planted
  `KeyError: 'beatz'` (about 1 minute): ERROR, E1.md with every part, F1.md with root cause, class, changes, verify
  command and auto_apply yes, the fixer corrected the key, the verify ran, the `autofix(10-build): ...` commit in
  the sandbox repo (none in the real repo), one known-issues line, FIXED, the restart with its note, DONE counting
  the fixed issue. Sections 5 (unfixable error blocks, the runner continues), 6 (caps, repeated signature,
  escalation), 7 (three identical blocks write STOPPED.md), 8 (guards), 9 (classification of failed stage scripts,
  including the bounded limit path and the traceback case) and 10 (a runner killed during a review cycle) pass.
  Same harmless noise as before: `cp: -r not specified; omitting directory .../buggy/__pycache__`.
- test-limits.sh: 65 passed, 0 failed
- test-no-emdash.sh: 0 passed, 1 failed. The only hit is `build/STOPPED.md:6`, an untracked file written by
  build-runner.sh when the previous review attempt failed: it quotes the CLI's message "Can't reach the API
  server (em dash) check your internet or DNS (ENOTFOUND)". This is the build harness, not M3 code, so it does not
  count against M3 (a HUMAN_TODO line was added). It does show the problem of required fix 2: the same CLI text
  ends up in the runner's own files.

The real repo's HEAD (80d6a0c) and working tree were unchanged by the tests. The files changed since 4f1cf3d have
no em dash, no CRLF, no `python3` call and no secret.

## Required fixes

1. **The classifier misses the network errors this PC really produces: they become code errors, reviews and
   blocks.**
   - Files: pipeline/lib/errors.py (TRANSIENT_PATTERNS), pipeline/tests/test-limits.sh.
   - Problem: spec section 4 makes "network resets" and timeouts transient (back off 60 s, 4 min, 16 min) for any
     failed call or script, and "never send a limit to the reviewer" has the same intent for outages. The patterns
     know Node's and Linux's wording (ECONNRESET, "connection reset", ENOTFOUND, getaddrinfo), but not Windows
     Python's, Chromium's (Playwright, used from M4 on), gh's or curl's, and not one of Claude Code's own network
     messages. Reproduced with `python pipeline/lib/errors.py classify --rc 1 --stderr FILE` (and `--stdout` with a
     JSON result for the CLI case). Each of these is class `error` today:
     - Claude Code, seen in this PC's own session logs (`"formatted":"No response from API"`, code
       StreamNoResponse): a result `{"type":"result","is_error":true,"result":"API Error: No response from API"}`.
       Also the Anthropic SDK's `API Error: Connection error.` and `API Error: terminated`.
     - Windows Python: `ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the
       remote host`, `requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionResetError(10054, 'An
       existing connection was forcibly closed by the remote host', None, 10054, None))`, `ConnectionAbortedError:
       [WinError 10053] ...`, `ConnectionRefusedError: [WinError 10061] No connection could be made because the
       target machine actively refused it`, `urllib3.exceptions.ProtocolError: ('Connection aborted.',
       RemoteDisconnected('Remote end closed connection without response'))`.
     - Chromium through Playwright: `Error: page.goto: net::ERR_CONNECTION_RESET at https://...`,
       `net::ERR_NAME_NOT_RESOLVED`, `net::ERR_INTERNET_DISCONNECTED` (and `net::ERR_TIMED_OUT`,
       `net::ERR_CONNECTION_REFUSED`, `net::ERR_NETWORK_CHANGED`, which the same patterns miss).
     - gh: `error connecting to api.github.com` plus `check your internet connection or https://githubstatus.com`.
     - curl: `curl: (6) Could not resolve host: example.com`, `curl: (7) Failed to connect to example.com port 443
       ...: Couldn't connect to server`.
     For a model call, ai() writes error.json and the stage fails as a code error at once (no backoff); for a
     script, runner_stage_failed sends it straight to ERROR and the review loop. The reviewer (whose own call may
     fail the same way) most likely answers "external outage, auto_apply no", so a short outage blocks the idea,
     and three ideas in a row become a systemic STOP: the case review 1 fix 2 was meant to prevent, still open for
     these wordings.
   - Expected: these messages are transient with a short label, for example: `No response from API`, `Connection
     error\.`, `API Error: terminated` (or `\bterminated\b` only in a CLI result) as "network error"; the
     exception names `ConnectionResetError`, `ConnectionAbortedError`, `RemoteDisconnected`, `Connection aborted`,
     `forcibly closed by the remote host`, `WinError 1005[34]` as "connection reset"; `ConnectionRefusedError`,
     `actively refused`, `WinError 10061`, `Couldn't connect to server`, `Failed to connect to` as "connection
     refused"; Chromium's `net::ERR_(CONNECTION_\w+|NAME_NOT_RESOLVED|INTERNET_DISCONNECTED|NETWORK_\w+|TIMED_OUT|
     ADDRESS_UNREACHABLE)`, `Could not resolve host`, `error connecting to` together with `check your internet
     connection` as "network error". Keep them word-bounded so code errors stay code errors (a `KeyError` or
     `FileNotFoundError` must not match, and a plain "Connection" in a log line must not either).
   - Verify: new test-limits.sh checks, one per line above, assert class `transient` (the CLI case with a JSON
     result on stdout and rc 1); the existing checks (KeyError traceback with `timeout=600`, FileNotFoundError,
     temporary file, config echo, the quoted limit) still give `error`; `bash pipeline/tests/test-limits.sh` and
     `M3_SECTIONS="9" bash pipeline/tests/test-m3.sh` pass.

2. **The runner writes em dashes from external error text into its terminal lines and files.**
   - Files: pipeline/lib/log.sh (`say`), pipeline/lib/runner.sh (`runner_last_log_line` and the messages built
     from it), pipeline/lib/errors.py (`message`), pipeline/lib/history.sh (history.txt, blocked.txt), the
     STOPPED.md writer (`runner_systemic_stop`), pipeline/lib/review.sh (the `- error:` line of E<n>.md).
   - Problem: spec section 0.7 and CLAUDE.md: never write an em dash in any file, prompt, caption, script or
     terminal message. The runner copies the last line of a stage log or a CLI result verbatim into the ERROR
     line, logs/runner.log, logs/status.txt, logs/history.txt, logs/blocked.txt, state.json, errors/E<n>.md and
     the reviewer prompt, and the Claude CLI's network message on this PC contains one (70 occurrences in the
     local session logs: "Can't reach the API server (em dash) check your internet or DNS (ENOTFOUND)"; build-runner.sh
     tripped on the same text in build/STOPPED.md). Reproduced in a test sandbox (the harness's sandbox_init, fake
     claude, `REELS_SLEEP_SCALE=0`, `FAKE_CLAUDE_REVIEW=no`) with a 10-build stage that prints that message on
     stderr and exits 1: three RETRY lines, then
     `[01:04] ERROR  S10 building visuals: temporary error persisted after 3 retries (network error): exit 1: API
     Error: Can't reach the API server <U+2014> check your internet or DNS (ENOTFOUND)`; a byte scan found U+2014 in
     the runner output, logs/runner.log, logs/history.txt, logs/blocked.txt, state.json, E1.md and E1.prompt.md.
     The code already strips em dashes from F<n>.md and the known-issues line (review.sh), so the intent is
     there, but not for the lines the runner composes itself. A model call's error goes the same way through
     ai()'s AI_ERROR and error.json.
   - Expected: every line the runner composes from external text replaces U+2014 (and preferably U+2013 used as
     a dash) with ", " before it is printed or written: `say` (terminal, runner.log, status.txt), the one-line
     messages (`runner_last_log_line`, errors.py `message`, AI_ERROR and error.json), history.txt, blocked.txt,
     STOPPED.md and the `- error:` line of E<n>.md. The verbatim log excerpts inside E<n>.md (the stage.log tail,
     the call's stderr) may stay as they are: they are evidence for the reviewer. Build the character from its
     code point (as review.sh and export.py do) so the source files stay clean.
   - Verify: a test-m3 section 9 case (or a small new fixture mode) where the stage prints the message above with
     a real U+2014 and exits 1 with `FAKE_CLAUDE_REVIEW=no`: after the run, a Python byte scan of the runner
     output, logs/runner.log, logs/status.txt, logs/history.txt, logs/blocked.txt and the `- error:` line of E1.md
     finds no U+2014, and the ERROR line reads `... Can't reach the API server, check your internet or DNS
     (ENOTFOUND)`. A unit check in test-limits.sh: errors.py classify on that text returns a message without
     U+2014.

## Repeated from earlier review

None. Both required fixes are new findings; the four required fixes of reviews 1 and 2 are fixed and covered by
test-m3 sections 9 and 10 and test-limits.sh section 3.

## Optional suggestions (do not affect the verdict)

- Still open from reviews 1 and 2 (optional there too): `review_commit` stages all of pipeline/ and
  motion-lib/candidates/ with `git add -A`; the fixer's Bash has no `--disallowedTools` rules for `git commit`,
  `git reset`, `git checkout`, `git stash`; `ai_write_error` computes the signature without the lib folder on
  sys.path; runner_resume_review starts a new cycle when the runner dies between `review_record` (no_auto) and
  `review_end`; the 40-line tail is matched as a whole; the `__pycache__` cp warning in install_stage.
- A fix whose verify command fails (outcome `failed`) leaves the fixer's edits uncommitted in pipeline/. When the
  idea ends blocked, those unverified edits stay in the working tree for the next ideas, and the next successful
  autofix sweeps them into its commit (the `git add -A` above). Consider restoring the files the fixer changed
  (treeguard already has the snapshot) when the cycle does not end in `fixed`, and keeping them as a patch under
  fixes/F<n>.patch for the next reviewer.
- known-issues.md's header announces `(commit <sha>)` at the end of each line, while review.sh writes `(F<n>,
  runs/<id>)` (the sha is not known before the commit). Align the header with what is written.
- A runner killed twice during a limit wait of a failed stage script (limit_waited stays false) uses up
  errors.script_limit_retries and sends a genuine limit to the reviewer. Rare, and stage scripts reach limits
  through ai() anyway, which waits on its own.
- Outside M3: config.json still has `tts.fallback` while the spec now has a single voice with no fallback engine
  (M7).
