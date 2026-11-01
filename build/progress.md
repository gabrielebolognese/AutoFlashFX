# Build progress

One section per milestone. Each build batch fills in: status, the exact command that runs the milestone's
acceptance test, the commits, and notes for later batches. Reviewers run every test command listed here.

## M0 Plan
- Status: done (2026-10-31). PLAN.md, DECISIONS.md, CLAUDE.md written; no code.
- Test command: none (the reviewer reads PLAN.md against BUILD_SPEC.md).
- Notes: see build/M0/report.md.

## M1 Skeleton
- Status: done (2026-10-31). 96 checks pass in about 35 seconds, no model calls.
- Test command: `bash pipeline/tests/test-m1.sh` (plus `bash pipeline/tests/test-no-emdash.sh`;
  `bash pipeline/tests/run-all.sh` runs every test that exists)
- Notes: config.json, ideas.txt (the test idea), library/hooks.txt (moved, unchanged), library/profile headers,
  pipeline/lib/{common,log,config,ideas,preflight}.sh, pipeline/lib/ideas.py, pipeline/bin/{add-idea.sh,
  validate-json, preflight, setup-python}, run.sh (preflight and banner; the loop arrives in M2), the test harness
  pipeline/tests/lib.sh and the parser fixtures. Windows gotchas are recorded in DECISIONS.md 38 to 40 (mixed
  paths through cygpath -m, Python output forced to LF). add-idea.sh records additions in logs/.new-ideas for the
  M2 NEW line. Report: build/M1/report.md.

## M2 Runner core and terminal output
- Status: done (2026-10-31); reviews 1 and 2 fixed the same day (build/M2/fixes-1.md, fixes-2.md). 220 checks pass
  in 7 to 10 minutes depending on the machine's load (measured 6.5 to 9.5 minutes), no model calls (dummy stages).
  Section 2's heartbeat-schedule check measures the runner's loop timing: it fails when other work saturates the
  CPU, so run the test on a quiet machine.
- Test command: `bash pipeline/tests/test-m2.sh` (plus `bash pipeline/tests/test-m1.sh` and
  `bash pipeline/tests/test-no-emdash.sh`; `bash pipeline/tests/run-all.sh` runs everything, about 9 minutes)
- Notes: run.sh is the loop of spec section 3 (pipeline/lib/runner.sh), with state.py and state.sh (state.json,
  stage table, .done markers, resume, reopen), status.sh (banner, heartbeat, IDLE, NEW, summary), history.sh
  (history.txt, blocked.txt), export.py and export.sh (numbering under .locks/exports, assemble, one rename,
  Ncaptions.txt rendered from 14-export/export.json), dummy.sh and one folder per stage under pipeline/stages/ with
  CONTRACT.md, schema.json and dummy.sh (run.sh and prompt.md arrive with each stage's milestone),
  pipeline/bin/runner-status. Until M3 a code error blocks the idea and a missing run.sh is a systemic stop
  (DECISIONS.md 60); a state.json that cannot be read or written mid-run is a systemic stop after one retry
  (`runner_state`, DECISIONS.md 67); every state.json write holds the OS file lock runs/<id>/state.lock, so
  concurrent writers (a stage's flag, the heartbeat's touch) lose nothing (DECISIONS.md 68). Fast test knobs: REELS_DUMMY, REELS_DUMMY_SECONDS and the planted REELS_DUMMY_* lists,
  REELS_STATUS_EVERY, REELS_POLL_SECONDS, REELS_TICK_SECONDS, REELS_CRASH_AT (DECISIONS.md 63, 64). Hooks for M3:
  `runner_code_error` in runner.sh is where the review and fix loop goes; state.py has `issue`, `round`, `reopen`,
  `flag` and per-stage `session_id` fields; the event lines LIMIT, RESUME, RETRY, ERROR, FIXED, ESCAL, STOP are
  plain `say` calls (log.sh colors them already). Report: build/M2/report.md.

## M3 Error system
- Status: done (2026-10-31); reviews 1 and 2 fixed the same day (build/M3/fixes-1.md: a failed stage script is
  classified before any review, and a runner killed during a review cycle resumes the cycle, DECISIONS.md 88, 89;
  build/M3/fixes-2.md: the limit path of a failed stage script is bounded, and echoed traceback lines are not error
  messages, DECISIONS.md 91, 92); review 3 fixed 2026-11-01 (build/M3/fixes-3.md: the classifier knows the network
  wordings this PC really produces, and no external text carries an em dash into a runner line or file,
  DECISIONS.md 93, 94). The test has ten sections (one calls the real Opus reviewer and Sonnet fixer,
  about 2 minutes); the whole suite (M1, M2, M3, limits, em dash scan) passes in about 30 minutes.
- Test command: `bash pipeline/tests/test-m3.sh` (10 to 20 minutes; section 4 calls the real Opus reviewer and
  Sonnet fixer, `M3_SECTIONS="1 2 3 5 6 7 8 9 10"` runs everything else with the fake claude) plus
  `bash pipeline/tests/test-limits.sh` (the parser and classifier units, seconds); `bash pipeline/tests/run-all.sh`
  runs M1, M2, M3, limits and the em dash scan (about 25 minutes).
- Notes: every model call goes through `ai()` in pipeline/lib/ai.sh (prompt on stdin, calls saved under
  `<stage>/calls/`, the protected files denied and guarded by pipeline/lib/protect.py, the schema retry in the same
  session, `--session KEY` for session ids in state.json). Usage limits: pipeline/lib/limits.py (Python zoneinfo,
  because the Git Bash date has no zone database) and limits.sh (the wait in 60 s chunks, LIMIT and RESUME lines,
  logs/limits.log, the probe loop). The classifier and the signature: pipeline/lib/errors.py and errors.sh
  (transient backoff 60 s, 4 min, 16 min, then a code error). The review and fix loop: pipeline/lib/review.sh with
  the child script pipeline/bin/review-cycle (E<n>.md, the Opus reviewer with structured output rendered as F<n>.md,
  the Sonnet fixer bounded to pipeline/ and motion-lib/candidates/ by path rules plus pipeline/lib/treeguard.py, the
  verify command, the known-issues line and the `autofix(<stage>): ...` commit, the restart note), the caps
  (3 Opus cycles, the repeated signature shortcut, 1 Fable escalation), blocking with the reviewer's reason, the
  systemic stop after 3 identical blocks (logs/.block-streak). Prompts and schemas in pipeline/stages/_prompts/.
  A failed stage script is classified before any review (limit: wait, at most errors.script_limit_retries times
  and never for a message that comes back unchanged right after its wait; transient: 60 s, 4 min, 16 min; else
  the review loop), with the source lines that tracebacks echo stripped first (errors.py strip_echo). External text
  (a CLI message, a tool's stderr, a model's words) never carries an em dash into a line or file the runner
  composes: `say` cleans every terminal line and the composers call `reels_undash VAR` or `undash TEXT` (log.sh) or
  errors.py `undash()`; stages from M4 on that write external text into their own files should do the same.
  Test knobs: REELS_SLEEP_SCALE=0 (fast-forward), REELS_PROBE_MAX, REELS_LIMIT_MARGIN, REELS_CLAUDE, the fake's
  FAKE_CLAUDE_* (pipeline/tests/fakes/claude.py). Hooks for M4: `ai <role> <stage_dir> <prompt> --session A
  --schema ...` returns 3 when the stored session is gone (reseed), `ai_restart_note <stage_dir>` gives the note
  written after a fix, every stage's error lands in `<stage>/error.json` for the report. DECISIONS.md 69 to 87.
  Report: build/M3/report.md.

## M4 Research, expansion, gate, angle (S1 to S4)
- Status: done (2026-11-01). The test has four sections: 1 and 2 run without a model (the units and the whole
  angle loop through run.sh with the fake claude answering from fixtures, about a minute), 3 and 4 call the real
  research, expansion and gate models on the test idea and on a deliberately false idea (15 to 30 minutes).
- Test command: `bash pipeline/tests/test-m4.sh` (`M4_SECTIONS="1 2"` for the fake-only sections;
  `M4_FREEZE=1` also rewrites the frozen fixtures under pipeline/tests/fixtures/runs/test-idea/);
  `bash pipeline/tests/run-all.sh` runs M1 to M4, limits and the em dash scan (about 50 minutes).
- Notes: the real stages pipeline/stages/{01-research,02-expansion,03-gate,04-angle}/run.sh with prompt.md,
  model.schema.json (the model's answer) and schema.json (the stage's file); the shared stage library
  pipeline/lib/stage.sh (stage_begin, stage_drop, stage_fail, flag_once, render_prompt, write_retry_prompt),
  pipeline/lib/session.sh (session A with the reseed after a lost session), pipeline/lib/prompt.py (templates),
  research.py, expansion.py, gate.py (the files and the decisions), pipeline/lib/screenshot.py behind
  pipeline/bin/screenshot (Playwright, headless Chromium, 1080 px, blocked sites reported, writes only under
  runs/). The handover of the angle loop goes through <stage>/reopen.txt, applied by state.py stage-done in the
  same write that marks the stage done; the rounds are derived from the gate-*.json and angle-*.json files.
  Config: research (tools, allowed rules, max_assets, expansion_chars, expansion_tries), timeouts.research_seconds,
  angle_seconds, expansion_seconds, gate_seconds, screenshot_seconds, the warn-level playwright preflight item.
  Event lines GATE and ANGLE; drop reasons carry the scores. Frozen fixtures of the test idea under
  pipeline/tests/fixtures/runs/test-idea/ (research, expansion, gate, the model answers under calls/); the fake's
  stage fixtures under pipeline/tests/fixtures/fake/m4/ (FAKE_CLAUDE_FIXTURES). Hooks for M5: S5 resumes session A
  with `session_call A research <stage_dir> <prompt> ...` (the reseed covers a missing session), the brief needs
  facts.md, expansion.json (keyword, deliverable, identity) and gate.json; `stage_begin` and friends in
  stage.sh; prompts start with "# Role: <role>" and "# Stage: <key>" so the fake can answer by stage.
  DECISIONS.md 95 to 109. Report: build/M4/report.md.

## M5 Profile and hooks (S5, S6)
- Status: not started
- Test command: `bash pipeline/tests/test-m5.sh` (planned)
- Notes:

## M6 Script (S7)
- Status: not started
- Test command: `bash pipeline/tests/test-m6.sh` (planned)
- Notes:

## M7 Voiceover (S8)
- Status: not started
- Test command: `bash pipeline/tests/test-m7.sh` (planned)
- Notes:

## M8 Sound effects memory map
- Status: not started
- Test command: `bash pipeline/tests/test-m8.sh` (planned)
- Notes:

## M9 Motion library
- Status: not started
- Test command: `bash pipeline/tests/test-m9.sh` (planned)
- Notes:

## M10 Visual stages (S9, S10)
- Status: not started
- Test command: `bash pipeline/tests/test-m10.sh` (planned)
- Notes:

## M11 Sound effects pass and review loop (S11, S12)
- Status: not started
- Test command: `bash pipeline/tests/test-m11.sh` (planned)
- Notes:

## M12 Final render, caption, export, end to end (S13, S14)
- Status: not started
- Test command: `bash pipeline/tests/test-m12.sh` (planned)
- Notes:

## M13 Hardening
- Status: not started
- Test command: `bash pipeline/tests/test-m13.sh` (planned)
- Notes:
