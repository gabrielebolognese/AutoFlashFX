# M3 review 4: Error system

Reviewer: fresh session, 2026-11-01. Read BUILD_SPEC.md (sections 0, 3, 4, 7, 12), CLAUDE.md, PLAN.md (M3),
DECISIONS.md (69 to 94), build/progress.md, build/HUMAN_TODO.md, pipeline/knowledge/known-issues.md,
build/M3/report.md, review-1.md to review-3.md, fixes-1.md to fixes-3.md, and the diff 4f1cf3d..HEAD, closely
reading what changed since review 3 (cba4bcc, 1c1d316): errors.py (the regrouped network patterns, undash()),
log.sh (reels_undash, undash, say), runner.sh, history.sh, review.sh, ai.sh, limits.sh, the netdash fixture and the
new checks in test-m3.sh sections 3 and 9 and test-limits.sh.

## Verdict

APPROVED. The acceptance test passes, both required fixes of review 3 are in place and tested, and I found no new
defect that needs a required fix. The fixes of reviews 1 and 2 still pass their tests (test-m3 sections 9 and 10,
test-limits.sh section 3).

## Acceptance test (run by the reviewer)

`bash pipeline/tests/run-all.sh`: about 30 minutes, exit 0, "run-all: 5 test files, all passed".
- test-m1.sh: 96 passed, 0 failed
- test-m2.sh: 220 passed, 0 failed
- test-m3.sh: 424 passed, 0 failed. Section 1 and 2: the fake claude produces every limit format and the runner
  waits for the right moment in fast-forward. Section 3: transient backoff 60 s, 4 min, 16 min, then a code error;
  the new cases ("API Error: No response from API" retried then succeeding; the CLI's network message with its em
  dash giving a clean AI_ERROR, runner.log and error.json while the raw call file keeps the character). Section 4
  ran the real Opus reviewer and Sonnet fixer on the planted bug (about 1 minute): ERROR, E1.md with every part,
  F1.md, the `autofix(...)` commit in the sandbox repo, FIXED, the restart, the stage passes, DONE counts the fixed
  issue. Sections 5 to 10 pass (blocking, the caps and escalation, the systemic stop after three identical blocks,
  the guards, the classification of failed stage scripts including the new netdash pass with its byte scans, a
  runner killed during a review cycle). The only noise is the known `cp: -r not specified; omitting directory
  .../buggy/__pycache__`.
- test-limits.sh: 94 passed, 0 failed
- test-no-emdash.sh: 1 passed, 0 failed (the repo scan is clean, including the untracked files)

After the suite the real repo's HEAD (1c1d316) and working tree are as before the run (the pre-existing
uncommitted changes to .gitignore and build-runner.sh, and the untracked tools/voice.py and earlier review files,
are not from the build's M3 code and were not touched).

## Spec compliance (section 12, M3, and section 4)

- The classifier (limit, transient, code error, in that order), limit parsing for every format with GNU date,
  60-second chunked waits, the unparsed-limit probe, the transient backoff, the error file E<n>.md with every part
  of 4.2.1, the reviewer with read-only tools, the fixer limited to pipeline/ and motion-lib/candidates/, the
  `autofix(<stage>): <cause>` commit, the known-issues line, the restart with a note, the caps (3 Opus cycles, the
  repeated-signature skip, one Fable escalation), blocking with logs/blocked.txt and the systemic stop with
  logs/STOPPED.md: all present and exercised by test-m3.sh.
- Both section 12 tests exist and pass: the fake claude first on PATH with every limit format in fast-forward, and
  the planted bug fixed by the real reviewer and fixer.
- Review 3 fix 1 (network wordings): checked by hand with `errors.py classify`; Windows Python, Chromium, curl, gh
  and Claude Code's own messages are transient; a KeyError and a FileNotFoundError stay code errors.
- Review 3 fix 2 (em dashes from external text): say(), runner_last_log_line, errors.py's message, ai_write_error,
  history.txt, blocked.txt, STOPPED.md, the drop and block reasons, E<n>.md's error line, the restart note,
  F<n>.result.json and limits.log all clean their text; I checked reels_undash on "a(dash)b", "a (dash) b", a
  leading or trailing dash, doubled dashes and an en dash inside a number range. The other direct writer of
  runner.log (ideas.py log_line) never writes external text.

## Robustness

No em dash in the repo, no CRLF in the files changed since 4f1cf3d, no `python3` call (the only mention is the
preflight fix text in config.json, which says to avoid it), no secret. Character constants are built from bytes or
code points, so the sources stay clean.

## Required fixes

None.

## Repeated from earlier review

None.

## Optional suggestions (do not affect the verdict)

- The new network patterns are matched against the whole 40-line tail of a failed stage script (the "tail matched
  as a whole" note of reviews 1 to 3), and a few of them are broad: `\bconnection error\.`, `\bConnectionError\b`,
  `failed to connect to\b` and `max retries exceeded`. Reproduced: a log with "Handled connection error. moving on"
  followed by `KeyError: 'x'` is classified transient; so is urllib3's "Max retries exceeded ... (Caused by
  SSLError(SSLCertVerificationError ...))" and a local `net::ERR_CONNECTION_REFUSED at http://localhost:5173/`.
  The cost is bounded (three backoffs, about 21 minutes, then the normal review), so this is efficiency, not
  correctness. Consider anchoring `connection error\.` to the CLI's `API Error: Connection error.`, classifying on
  the last error block only (from the last `Traceback` or the last few lines), and excluding `SSLError` /
  `certificate verify failed` from the "max retries" rule.
- Still open from earlier reviews (optional there too): `review_commit` staging all of pipeline/ with `git add -A`,
  no `--disallowedTools` git rules for the fixer, `ai_write_error`'s signature computed without the lib folder on
  sys.path, runner_resume_review between review_record (no_auto) and review_end, the failed fix's unverified edits
  left in the working tree, the known-issues header announcing `(commit <sha>)`, a runner killed twice during a
  limit wait using up errors.script_limit_retries, the `__pycache__` cp warning in install_stage, and
  `tts.fallback` in config.json (M7).
- HUMAN_TODO still asks for build-runner.sh's stop_build message to strip U+2014; build-runner.sh has uncommitted
  local edits now (the human's), so whoever touches it next should check that line.
