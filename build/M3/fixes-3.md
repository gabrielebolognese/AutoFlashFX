# M3 fixes 3: Error system

Fixed 2026-11-01 after build/M3/review-3.md (REJECTED, 2 required fixes), in a fresh session. Read BUILD_SPEC.md
(sections 0, 4, 7, 12), CLAUDE.md, PLAN.md (M3), DECISIONS.md (69 to 92), build/progress.md, build/HUMAN_TODO.md,
pipeline/knowledge/known-issues.md, build/M3/report.md, review-1.md, fixes-1.md, review-2.md, fixes-2.md and
review-3.md. Only the two required fixes were applied; the optional suggestions of the three reviews were left
alone (listed at the end). One housekeeping step outside the M3 code: the stale build/STOPPED.md that the build
harness wrote when the first review-3 attempt lost its connection (the only em dash hit of the repo, see
HUMAN_TODO) was deleted, because the build had resumed and HUMAN_TODO asked for exactly that.

## Required fix 1: the classifier missed the network errors this PC really produces

What changed (pipeline/lib/errors.py; DECISIONS.md 93):
- The transient patterns knew Node's and Linux's wording (ECONNRESET, "connection reset", ENOTFOUND, getaddrinfo)
  and nothing else, so a network blip in a stage script or a model call became a code error at once (for a model
  call ai() wrote error.json without any backoff; for a script runner_stage_failed went straight to ERROR and the
  review loop), most likely an "external outage, auto_apply no" verdict, a blocked idea, and three in a row the
  systemic stop. The patterns are now grouped by label, each code word-bounded and each phrase whole:
  - "connection reset": ECONNRESET, "connection reset", "socket hang up", EPIPE, ConnectionResetError,
    ConnectionAbortedError, BrokenPipeError, RemoteDisconnected, "Connection aborted", "forcibly closed by the
    remote host", "remote end closed connection", WinError or Errno 10053 and 10054, "connection dropped";
  - "connection refused": ECONNREFUSED, "connection refused", ConnectionRefusedError, the CLI's bare
    ConnectionRefused, "actively refused", WinError or Errno 10061, curl's "Couldn't connect to server" and
    "Failed to connect to";
  - "network error": EAI_AGAIN, ENOTFOUND, getaddrinfo, "network error", "fetch failed", ENETUNREACH,
    EHOSTUNREACH, ENETDOWN, Claude Code's "No response from API", "Can't reach the API server", "Unable to connect
    to API", FailedToOpenSocket, the SDK's "Connection error." and "API Error: terminated", Chromium's
    net::ERR_CONNECTION_*, NAME_NOT_RESOLVED, INTERNET_DISCONNECTED, NETWORK_*, TIMED_OUT, ADDRESS_UNREACHABLE,
    EMPTY_RESPONSE, PROXY_CONNECTION_FAILED and SOCKET_NOT_CONNECTED, curl's "Could not resolve host", gh's "error
    connecting to" only together with its "check your internet connection" line, Python's ConnectionError,
    NewConnectionError and NameResolutionError, urllib3's "Max retries exceeded";
  - "stream interrupted" gains the CLI's "Connection closed mid-response", "The response stopped arriving" and
    "response above may be incomplete".
- The wordings beyond the review's list come from this PC's own Claude Code session logs, read before the fix:
  "Can't reach the API server" (117 times), "Unable to connect to API (ENOTFOUND)" (32), "(ConnectionRefused)"
  (13), "(FailedToOpenSocket)" (10), "Connection dropped (ECONNRESET)" (6), "No response from API", "Connection
  closed mid-response", "Connection error.", "terminated". The pattern order is unchanged (timeout, reset, refused,
  network, server, temporary, stream), so a message that names a specific cause keeps the specific label
  (requests' ConnectionError wrapping a ConnectionResetError is "connection reset", not "network error").
- Nothing else in the classifier moved: strip_echo still runs first, the timeout words, the status context and the
  "temporary" rule are as review 2 left them, exit 124 and 137 still count as a timeout, the limit detection and
  the fatal patterns are untouched.

How verified:
- pipeline/tests/test-limits.sh section 3, 29 new checks: the CLI results "API Error: No response from API",
  "Connection error.", "terminated", "Unable to connect to API (ConnectionRefused)", "(FailedToOpenSocket)",
  "Connection dropped (ECONNRESET)" and "Connection closed mid-response" (each as a JSON result on stdout with
  exit 1) are transient with the labels above; Windows Python's ConnectionResetError WinError 10054, requests'
  ConnectionError wrapping it, ConnectionAbortedError WinError 10053, ConnectionRefusedError WinError 10061 and
  urllib3's RemoteDisconnected; Chromium's net::ERR_CONNECTION_RESET, NAME_NOT_RESOLVED, INTERNET_DISCONNECTED,
  TIMED_OUT, CONNECTION_REFUSED and NETWORK_CHANGED; gh's two lines; curl's "Could not resolve host" and "Failed to
  connect to". The negatives: a plain "connection" in a log line before a KeyError, "error connecting to" without
  gh's second line, FileNotFoundError and the KeyError traceback with timeout=600 are still code errors; every
  earlier check (the temporary file, the bare 503, the config echo, the quoted stage limit) still passes.
- pipeline/tests/test-m3.sh section 3: "API Error: No response from API" from the fake claude goes through
  ai()'s backoff (RETRY temporary error (network error), 60 s in fast-forward) and the retry succeeds, two calls
  in all.

## Required fix 2: the runner wrote em dashes from external text into its lines and files

What changed (pipeline/lib/log.sh, runner.sh, errors.py, history.sh, review.sh, ai.sh, limits.sh; DECISIONS.md 94):
- log.sh defines REELS_EM_DASH (U+2014) and REELS_EN_DASH (U+2013) from their UTF-8 bytes, so the source stays
  clean, and `reels_undash VAR` (in place, pure bash, no subprocess: say() runs it on every line) with `undash
  TEXT` (printed): an em dash becomes ", " whatever the spaces around it, one at either end of the text is
  dropped, an en dash between spaces is treated the same and one inside a word (a range of numbers) becomes a
  hyphen. Checked in the C, C.UTF-8 and en_US.UTF-8 locales.
- `say` cleans every line it prints: the terminal, logs/runner.log and logs/status.txt, a stage's own say lines
  through fd 3 included.
- The composers clean their text before it is written anywhere: `runner_last_log_line` (so the message that
  becomes the ERROR line, state.json's stage error, errors/E<n>.msg, the fixer prompt and the restart note is
  clean at the source), errors.py's `undash()` on the classifier's message with the same rules in Python (ai()'s
  AI_ERROR and error.json come from it; `ai_write_error` cleans the message it writes and the schema-retry
  validation errors, which quote the model's values, are cleaned too), `history_add` and `blocked_add` (every
  field, the idea's braces copy included), `runner_write_stopped` (STOPPED.md: title, diagnosis, fixes),
  `runner_drop` and `runner_block` (the reason, which may be the reviewer's or a stage model's text),
  `review_error_file` (the "- error:" line of E<n>.md), `review_cycle` (the message in the fixer prompt),
  `review_restart_note` (the message and the reviewer's summary), `review_write_result` (every value of
  F<n>.result.json, for example a verify log line) and `limits_log` (the quoted limit message).
- Left verbatim on purpose: the stage.log tail and the call's stderr inside E<n>.md (and so the reviewer prompt
  that embeds E<n>.md), the raw call files under calls/, stage.log itself: they are evidence for the reviewer, as
  the review allowed. F<n>.md and the known-issues line were already cleaned before this fix.
- history.sh sources log.sh itself when reels_undash is not defined yet (run.sh already sources log.sh first;
  this keeps the library usable alone).

How verified:
- pipeline/tests/test-m3.sh section 9, one new runner pass with the flaky fixture's new mode `netdash`, which
  prints the CLI's exact message with a real U+2014 (built from its bytes, so the fixture file holds none) on
  stderr at every attempt, with the fake reviewer answering no: three RETRY lines naming the network error, then
  `ERROR S10 building visuals: temporary error persisted after 3 retries (network error): exit 1: API Error:
  Can't reach the API server, check your internet or DNS (ENOTFOUND)`, the BLOCK line with the same cleaned text,
  the order RETRY, RETRY, RETRY, ERROR, BLOCK, one reviewer call; then a Python byte scan finds no U+2014 in the
  runner output, logs/runner.log, logs/status.txt, logs/history.txt, logs/blocked.txt, state.json, errors/E1.msg,
  fixes/F1.md, fixes/F1.result.json and the "- error:" line of E1.md, while stage.log and E1.md's log excerpt
  still hold the character (the stage really printed it), and history.txt has the cleaned reason.
- pipeline/tests/test-m3.sh section 3: the same message as the fake claude's error result at every try through
  ai(): after the three retries AI_ERROR reads `temporary error persisted after 3 retries (network error): API
  Error: Can't reach the API server, check your internet or DNS (ENOTFOUND)`, the raw call file still holds the
  U+2014, runner.log and error.json do not.
- pipeline/tests/test-limits.sh: the classifier's message for that CLI result has the comma and no U+2014, and a
  stage's exception line with two em dashes ("step (dash) done", "RuntimeError: no beats (dash) check the plan") is
  cleaned the same way.
- pipeline/tests/test-no-emdash.sh: the repo scan is clean (every file changed here builds the character from its
  bytes or code point; the stale build/STOPPED.md was deleted).

## Test results

`bash pipeline/tests/run-all.sh` after the fixes: 5 test files, all passed, exit 0, 29 minutes on this PC (started
01:31, finished 02:00):
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed (the heartbeat schedule check passed on a quiet machine)
- test-m3.sh: 424 passed, 0 failed (397 before the fixes, 27 new: 7 in section 3, 20 in section 9). Section 4 ran
  the real Opus reviewer and Sonnet fixer on the planted `KeyError: 'beatz'` again: ERROR, F1.md, the autofix
  commit in the sandbox repo, FIXED, the restart, DONE. Sections 9 and 10 (the review 1 and 2 fixes) still pass.
- test-limits.sh: 94 passed, 0 failed (65 before, 29 new classifier checks)
- test-no-emdash.sh: 1 passed, 0 failed (the stale build/STOPPED.md is gone; every file changed here builds the
  character from its bytes or code point)

Before the suite: test-limits.sh alone (94 passed) and `M3_SECTIONS="3 9" bash pipeline/tests/test-m3.sh` found
two wrong expectations in the new netdash case, not a code problem: the BLOCK line and the history line quote the
fake reviewer's root cause, which is the first 120 characters of the error headline, so the cleaned text ends at
"check your int"; the two patterns were shortened and every byte scan had passed at the first run. The real
repo's HEAD (80d6a0c) and working tree are unchanged by the tests (section 4 asserts it). The changed files have
no em dash, no CRLF and no `python3` call.

## Files changed
- pipeline/lib/errors.py: RESET_WORDS, REFUSED_WORDS, NETWORK_WORDS, STREAM_WORDS and the regrouped
  TRANSIENT_PATTERNS, EM_DASH, EN_DASH, undash(), classify() wrapping classify_raw(), the header.
- pipeline/lib/log.sh: REELS_EM_DASH, REELS_EN_DASH, reels_undash, undash, say() cleaning its text, the header.
- pipeline/lib/runner.sh: runner_last_log_line, runner_write_stopped, runner_drop, runner_block, the header.
- pipeline/lib/history.sh: history_add and blocked_add clean every field, the log.sh guard, the header.
- pipeline/lib/review.sh: review_error_file, review_cycle, review_restart_note, review_write_result.
- pipeline/lib/ai.sh: ai_write_error, the schema-retry errors, the header. pipeline/lib/limits.sh: limits_log.
- pipeline/tests/fixtures/stages/flaky/run.sh: the netdash mode. pipeline/tests/test-limits.sh: 29 classifier
  checks and the header. pipeline/tests/test-m3.sh: section 3 (two ai() cases) and section 9 (the netdash pass).
- DECISIONS.md 93 and 94, CLAUDE.md (the build status line, the em dash rule names the helpers), build/progress.md
  (M3), build/HUMAN_TODO.md (the build/STOPPED.md line, updated), build/STOPPED.md deleted (untracked).

## Not changed (the reviews' optional suggestions)
Left as they were, because the batch applies only the required fixes: `review_commit` staging all of pipeline/,
the fixer's Bash without git `--disallowedTools` rules, `ai_write_error`'s signature computed without the lib
folder on sys.path, runner_resume_review starting a new cycle when the runner dies between review_record
(no_auto) and review_end, the 40-line tail matched as a whole, the `__pycache__` cp warning of install_stage, the
unverified edits of a failed fix left in the working tree, the known-issues header announcing `(commit <sha>)`,
a runner killed twice during a limit wait using up errors.script_limit_retries, and the `tts.fallback` entry in
config.json (M7).
