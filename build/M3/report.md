# M3 report: Error system

Built 2026-10-31 from BUILD_SPEC.md section 4 and section 12 (M3) and PLAN.md (M3). Acceptance test green
(numbers in "Test output summary" below); the M1 and M2 tests, the new limits unit test and the em dash scan pass
with it. One section of the M3 test makes real model calls (the Opus reviewer and the Sonnet fixer on a planted
bug); everything else runs against a fake claude.

## What this batch built
- **Every model call through ai()** (pipeline/lib/ai.sh): `claude -p --model <config> --effort <config>
  --output-format json --permission-mode auto --permission-prompts none`, plus `--resume`, `--json-schema`,
  `--tools`, `--allowedTools`, `--disallowedTools`, `--add-dir` and `--max-turns` as requested; the prompt on
  stdin; every call saved as `<stage>/calls/NNN.json` with `.err`, `.meta` (the exact command, timing, class)
  and `.out.json` (the structured output). Model names and efforts come from config.json only. The protected
  files (ideas.txt, library/, styles/, exports/, .env) are denied to the model's Edit and Write tools and guarded
  by a snapshot before every call (pipeline/lib/protect.py) that restores a changed file and turns the call into
  a code error. `--session KEY` stores and resumes session ids in state.json; a session that no longer exists
  returns 3 so M4 can reseed. An answer that fails its schema is asked once more in the same session with the
  validation errors (the stage's one schema retry), then it is a code error.
- **Usage limits** (pipeline/lib/limits.py and limits.sh): detection in stdout, stderr and the JSON result; every
  format of spec 4.1 (time only, weekday and time, date and time, a timezone in parentheses, an epoch after a
  `|`), the rollovers (+1 day, +7 days, next year for a date), the wait until the reset plus 120 s in 60 s chunks
  that re-read the clock, the activity text "waiting for usage limit (weekly) until Mon 00:02 (5h41m left)",
  logs/limits.log with the target, the LIMIT and RESUME lines, the retry of the same call in the same session,
  and the 30-minute probe loop with the probe model when nothing parses. Time zones go through Python zoneinfo
  because the Git Bash `date` has no zoneinfo database (DECISIONS.md 69).
- **The classifier** (pipeline/lib/errors.py and errors.sh), in the spec's order: limit, transient (overloaded,
  529, 5xx, timeouts including a call killed by its timeout, network resets, rate limits with retry-after) with
  the backoff 60 s, 4 min, 16 min and then a code error, and code errors; plus the normalized error signature
  (digits, paths, hex ids and timestamps stripped, sha1, 12 characters). RETRY lines and the "retrying after
  temporary error" activity.
- **The review and fix loop** (pipeline/lib/review.sh, pipeline/bin/review-cycle, the prompts and schemas in
  pipeline/stages/_prompts/): on a code error the runner prints ERROR and starts a review cycle as a background
  child (the heartbeat keeps printing). The cycle writes `runs/<id>/errors/E<n>.md` (stage, command, exit code,
  the last 200 log lines, the input files, CONTRACT.md, the git diff since the last successful run, every previous
  E and F file of the stage), calls the reviewer (Opus; read-only tools plus WebSearch and WebFetch; E<n>.md and
  pipeline/knowledge/known-issues.md in the prompt), renders `fixes/F<n>.md` from its structured verdict (root
  cause, class, exact changes, verify command, auto_apply), calls the fixer (Sonnet; Edit and Write approved
  under pipeline/ and motion-lib/candidates/ only), guards the working tree (pipeline/lib/treeguard.py: the
  fixer's changes outside those folders are undone, the user's own uncommitted work survives), runs the verify
  command itself, appends the known-issues line and commits `autofix(<stage>): <summary>`. Then FIXED, a restart
  note for the stage (`<stage>/restart-note.md`, read by `ai_restart_note`) and the stage runs again ("attempt 2
  after the fix").
- **Caps, escalation, blocking, the systemic stop:** up to 3 Opus cycles per stage per idea; the same signature
  twice in a row skips the remaining Opus cycles; then 1 escalation cycle with the Fable reviewer (ESCAL line,
  every previous E and F file in its report); a verdict with auto_apply no, a fatal review failure or the
  exhausted caps block the idea (removed from ideas.txt, in logs/blocked.txt with the reason, run folder kept,
  BLOCK then NEXT). The same error signature blocking 3 ideas in a row writes logs/STOPPED.md (the error, the F
  files to read, how to re-add the ideas) with the STOP line and exit 3; an export or a drop resets the streak
  (logs/.block-streak survives restarts).
- **Config:** `errors` (backoff table, the unparsed limit sleep and probe interval, the repeated-signature count,
  the log tail), `timeouts` (model call, reviewer, fixer, verify, probe) and `review` (reviewer tools, fixer tools,
  fixer paths, protected paths) sections in config.json. pipeline/knowledge/known-issues.md created (header).
- **Tests:** pipeline/tests/test-limits.sh (47 checks: every format with a fixed clock and zone, kinds, the
  margin, the signature and the classifier), pipeline/tests/test-m3.sh (eight sections, see below), the fake
  claude pipeline/tests/fakes/claude (modes for every limit format on three channels, transient failures, a hang,
  bad JSON, fatal, a missing session, tampering with a protected file, the reviewer and fixer verdicts by policy;
  it logs every call so the tests assert the exact command line), pipeline/tests/ai-driver.sh and the fixture
  stages pipeline/tests/fixtures/stages/{buggy,unfixable,aicall}/.

## Files
- New: pipeline/lib/{ai.sh, limits.py, limits.sh, errors.py, errors.sh, protect.py, treeguard.py, review.sh},
  pipeline/bin/review-cycle, pipeline/stages/_prompts/{reviewer.md, reviewer.schema.json, fixer.md,
  fixer.schema.json}, pipeline/knowledge/known-issues.md, pipeline/tests/{test-m3.sh, test-limits.sh,
  ai-driver.sh}, pipeline/tests/fakes/{claude, claude.py}, pipeline/tests/fixtures/stages/buggy/{run.sh,
  helper.py}, pipeline/tests/fixtures/stages/unfixable/run.sh, pipeline/tests/fixtures/stages/aicall/run.sh,
  build/M3/report.md.
- Changed: run.sh (sources ai.sh and review.sh, build status), pipeline/lib/runner.sh (runner_code_error is the
  review and fix loop; runner_block_error and the block streak; the export failure goes through the loop; the
  restart message after a fix; runner_sleep delegates to limits.sh; logs/.last-good-sha), config.json (errors,
  timeouts, review), pipeline/tests/lib.sh (fake_claude_on, fake_claude_off, dummy_except; the pipeline sandbox
  also carries the style text files, .gitattributes, a .gitignore and a git identity), pipeline/tests/test-m2.sh
  (section 5), CLAUDE.md, DECISIONS.md (items 69 to 87), build/progress.md, build/HUMAN_TODO.md.
- Removed: pipeline/knowledge/.gitkeep (the folder has content now).
- Earlier milestones touched, because M3 replaces their placeholders: M2's runner.sh (the M2 code error path
  blocked the idea with "no automatic fix before M3"; it now runs the loop) and test-m2.sh section 5 (a planted
  code error now goes through the loop, so the section runs with the fake claude whose reviewer answers
  auto_apply no, and the expected BLOCK, history and blocked.txt texts carry the reviewer's reason); M1's
  config.json (new sections) and tests/lib.sh (helpers). M1 and M2 keep passing.

## How to run the test
```
bash pipeline/tests/test-m3.sh                 # the M3 acceptance test (10 to 20 minutes; section 4 calls real models)
M3_SECTIONS="4" bash pipeline/tests/test-m3.sh # only the real reviewer and fixer section (a few minutes)
M3_SECTIONS="1 2 3 5 6 7 8" bash pipeline/tests/test-m3.sh   # everything with the fake claude, no model calls
bash pipeline/tests/test-limits.sh             # the limit parser and classifier units (seconds)
bash pipeline/tests/run-all.sh                 # M1, M2, M3, limits and the em dash scan (about 25 minutes)
```
KEEP_SANDBOX=1 keeps the temporary roots. The tests never touch the real ideas.txt, runs/, exports/ or logs/, and
the fixer commits only inside the sandbox copy of the repo (the real repo's HEAD is asserted unchanged).

## Test output summary
`bash pipeline/tests/run-all.sh`: 5 test files, all passed, exit 0, 19 min 25 s on this PC:
`test-m1.sh: 96 passed, 0 failed`, `test-m2.sh: 220 passed, 0 failed` (section 5 now goes through the review loop
with the fake reviewer), `test-m3.sh: 279 passed, 0 failed`, `test-limits.sh: 47 passed, 0 failed`,
`test-no-emdash.sh: 1 passed, 0 failed`. test-m3.sh alone takes about 10 minutes; its real-model section 4 ran in
about 2 minutes (the Opus review call took 28 s and the Sonnet fix call 15 s in the kept run, the rest is the
dummy stages and the export). The sections, in the order of the test:

1. ai() units with the fake: the command line (model and effort from config, `--tools` and the pre-approved
   list, the protected-file denials, the prompt on stdin, the repo root as cwd), the call files, the schema retry
   in the same session with the errors, `--session` storage and resume, a missing session (exit 3, the stored id
   cleared), the protected files guard (ideas.txt restored, a code error), fatal errors, the restart note.
2. Usage limits: time, time with a zone (Rome, New York), weekday, date and epoch formats, plus relative ones,
   each with the LIMIT line, the fast-forward INFO line, the RESUME line and the limits.log target checked against
   an independent computation (reset plus 120 s), and the retry in the same session; limits on stderr and in
   plain text; the unparseable limit (30 min sleep, the probe with the probe model, RESUME, three calls); then a
   full runner pass with a limit inside a stage (LIMIT, RESUME naming the stage's activity, STEP, DONE, no ERROR).
3. Transient errors: RETRY in 60s, 4m, 16m then success (4 calls); a fourth failure is a code error with no fifth
   call; a network reset on stderr; a call killed by its timeout.
4. The planted bug with the real models: `ERROR S10 building visuals: exit 1: KeyError: 'beatz'`, E1.md with
   every part, F1.md with the five parts (class "pipeline bug", the helper named, a verify command, auto_apply
   yes), the fixer changed the key, the verify log, the `autofix(10-build): ...` commit in the sandbox repo and
   none in the real one, one known-issues line, `FIXED S10: <cause> (commit <sha>), restarting stage`, "attempt 2
   after the fix", the stage passes, `DONE exported #1 (..., 1 issue fixed)`, state.json counters, the restart
   note, the reviewer and fixer calls under errors/calls/ with the configured models. The whole cycle took about
   one minute on this PC.
5. An unfixable error (the fake reviewer answers auto_apply no): BLOCK with "environment problem: ... Needs you:
   ...", NEXT, blocked.txt, history, the run kept with E1.md and F1.md (auto_apply no), one reviewer call with
   the read-only tools and the schema, the next idea exported once the key exists, the streak reset.
6. The caps: ERROR, FIXED, ERROR, ESCAL after one review (the repeated signature), FIXED, ERROR, BLOCK; the
   reviewer, fixer, escalation reviewer and fixer calls with the configured models; the fixer's tools and path
   rules; E2 carrying E1 and F1; two autofix commits and known-issues lines; state counters; then the variant where
   every verification fails: four WARN lines, ESCAL after 3 reviews, BLOCK, no restart, no commit.
7. Three identical blocks in a row: three BLOCK lines, the STOP line, STOPPED.md with the diagnosis and the three
   numbered fixes, exit 3, the fourth idea left in ideas.txt, blocked.txt with the three ideas, status.txt and
   runner-status.
8. The guards as units: treeguard.py (a log that grew during the call and the user's own modified file survive;
   the fixer's edits outside pipeline/ are undone, its new files deleted) and protect.py (ideas.txt, a deleted
   library file and the style restored, a new library file removed, an exports change reported).

## Known gaps
- The fixer's Bash tool can still run arbitrary commands inside the repo; the path rules bound only its Edit and
  Write tools, and the tree guard puts back what it changed outside pipeline/ and motion-lib/candidates/. A
  command that writes elsewhere on the PC is not caught.
- A pre-existing untracked file inside the repo that changes during a fixer call is left alone and reported
  (INFO line), by design: this covers logs the runner itself writes into the repo.
- The limit message formats come from the spec and the user's build-runner.sh; the exact text of the CLI's
  usage-limit result in `--output-format json` was not observable in this batch (no limit was hit). The detector
  looks at the result text, stderr and plain stdout, so a message in any of them is found.
- A call killed by its timeout may leave the node process of `claude` alive for a while (the `timeout -k 15`
  kills the shell shim first); M13 hardening can look at process trees.
- The restart note is written for every restart after a fix, but no stage consumes it yet (the real stages
  arrive from M4).
- Test runtime: test-m3 takes 10 to 20 minutes, mostly dummy-stage overhead in the runner passes (about 2 s per
  stage transition) and the real calls of section 4 (one to three minutes).

## HUMAN_TODO items added
- M3: nothing required; a note that the runner now fixes its own code errors (each fix is an `autofix(<stage>)`
  commit plus a known-issues line, worth skimming now and then) and what to do when STOPPED.md names a repeated
  error.

## Commits
- feat(M3): error system: ai() with limit waits and transient retries, the classifier, the reviewer and fixer
  loop, escalation, blocking, the systemic stop (code, config, tests, the fake claude, the fixtures)
- docs(M3): decisions 69 to 87, progress, human todo, CLAUDE.md build status
- docs(M3): report (this file, committed after it was written)
