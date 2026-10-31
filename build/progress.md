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
- Status: done (2026-10-31). 183 checks pass in about 6.5 minutes, no model calls (dummy stages).
- Test command: `bash pipeline/tests/test-m2.sh` (plus `bash pipeline/tests/test-m1.sh` and
  `bash pipeline/tests/test-no-emdash.sh`; `bash pipeline/tests/run-all.sh` runs everything, about 8 minutes)
- Notes: run.sh is the loop of spec section 3 (pipeline/lib/runner.sh), with state.py and state.sh (state.json,
  stage table, .done markers, resume, reopen), status.sh (banner, heartbeat, IDLE, NEW, summary), history.sh
  (history.txt, blocked.txt), export.py and export.sh (numbering under .locks/exports, assemble, one rename,
  Ncaptions.txt rendered from 14-export/export.json), dummy.sh and one folder per stage under pipeline/stages/ with
  CONTRACT.md, schema.json and dummy.sh (run.sh and prompt.md arrive with each stage's milestone),
  pipeline/bin/runner-status. Until M3 a code error blocks the idea and a missing run.sh is a systemic stop
  (DECISIONS.md 60). Fast test knobs: REELS_DUMMY, REELS_DUMMY_SECONDS and the planted REELS_DUMMY_* lists,
  REELS_STATUS_EVERY, REELS_POLL_SECONDS, REELS_TICK_SECONDS, REELS_CRASH_AT (DECISIONS.md 63, 64). Hooks for M3:
  `runner_code_error` in runner.sh is where the review and fix loop goes; state.py has `issue`, `round`, `reopen`,
  `flag` and per-stage `session_id` fields; the event lines LIMIT, RESUME, RETRY, ERROR, FIXED, ESCAL, STOP are
  plain `say` calls (log.sh colors them already). Report: build/M2/report.md.

## M3 Error system
- Status: not started
- Test command: `bash pipeline/tests/test-m3.sh` (planned)
- Notes:

## M4 Research, expansion, gate, angle (S1 to S4)
- Status: not started
- Test command: `bash pipeline/tests/test-m4.sh` (planned)
- Notes:

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
