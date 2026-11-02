# M13 Hardening: build report (2026-11-02)

A previous attempt at this batch was interrupted after it had written the fault injection (ai.sh), the log rotation
(log.sh, status.sh, config.json logs.*) and the runner's rotation call. This session checked that work, repaired one
byte it had damaged (its Python edit had turned the literal carriage return in runner.sh's `tr -d` into a newline, so
the export number would have kept a CR), and built the rest. The uncommitted changes to build-runner.sh (the
`--fallback-model` switch) were in the working tree before this batch; they are not part of M13 and were left as they
are (the build runner is executing that file).

## What was built

1. **Fault injection** (pipeline/lib/ai.sh `ai_fault`, DECISIONS.md 276). `REELS_FAULT=limit:<stage>[@n]` replaces the
   next model call of that stage with a CLI-shaped session-limit result ("You've hit your session limit · resets
   3:48pm (Europe/Rome)", the same session id), so the real classifier, the LIMIT line, logs/limits.log, the wait, the
   RESUME line and the retry in the same session all run unchanged; `REELS_FAULT_WAIT=fast` fast-forwards that wait.
   `REELS_FAULT=kill:<stage>[@n]` kills the runner and the stage with SIGKILL, like a crash. `@n` is the n-th run
   folder; each fault fires once (logs/.faults/).
2. **Log rotation** (log.sh `reels_log_rotate`, DECISIONS.md 277): logs/runner.log moves to runner.log.1 at 50 MB
   (config logs.rotate_mb, rotate_keep 3), checked at startup and at most once a minute; the new file opens with an INFO
   line naming the old one.
3. **status.txt written aside and renamed** (DECISIONS.md 278): measured on this PC, the direct write let a reader see an
   empty file; the rename never does (a reader may find the name missing for a moment, so runner-status, the doctor and
   the test's sampler read again). say() also stopped spawning a mkdir per line, so it costs what it did before.
4. **pipeline/lib/logcheck.py** (DECISIONS.md 279, 284): checks one status line, status.txt, a sampler file, and the whole
   story of runner.log (several rotated files read as one timeline) against spec sections 6 and 7: the banner, START
   (and "resumed at" after a crash), STEP chains, GATE before an export, DONE/DROP/BLOCK, NEXT, LIMIT followed by RESUME,
   the heartbeat's position, text, minute, issue counters and activity (the activity table of section 7, for every
   heartbeat and STEP), no idea silent longer than the heartbeat plus 2 minutes, exports without gaps, the summary's
   counts, no STOP, no em dash, no ANSI code.
5. **pipeline/bin/doctor** (DECISIONS.md 281): a read-only report (versions, Node packages against their pins, disk, the
   voice interpreters, the freshness of the sfx map, tokens and hooks index, the runner and its status line, the last
   session's story, blocked ideas, STOPPED.md, limits, known issues); OK, WARN or FAIL per line, exit 1 on a FAIL.
6. **build-voice-profile --force keeps the hand-written parts** (voiceprofile.py `merge_keep`, DECISIONS.md 280):
   account.md's Brand and Content strategy and voice.md's How I promote word for word, any section the user added, any
   section or field filled by hand where the rebuild only has placeholders, the measured pace and excerpts when nothing
   was measured, and the FlashFX spelling line in its own section; the previous file is copied to logs/voice-profile/;
   a second --force changes nothing. The account.md template now writes the Brand section of the brand kit.
7. **The M13 test**: pipeline/tests/test-m13.sh, the driver pipeline/tests/m13-run.sh (three ideas; a simulated limit at
   the second idea's first S2 call; the runner killed at its first S3 call; the restart; the forever mode stopped with
   SIGTERM; status.txt sampled throughout) and pipeline/tests/fixtures/ideas/three-ideas.txt (Claude Code's /init, the
   Playwright MCP server, ffmpeg's stream copy).
8. **Fixes for what the real runs surfaced** (DECISIONS.md 283 to 287):
   - S8 blocked a reel for a correct "Claude": faster-whisper's small model writes "clod" or "clawed"; S8 and S12's
     audio check now pass the reel's names as faster-whisper hotwords (measured: respellings did nothing, phonemes
     helped in some sentences, hotwords fixed every sentence tried), and S7's one-line rewrite refuses a respelled name
     ("Clawed" for "Claude"), which had made the block certain.
   - S8 blocked a reel for a correct "one thirty" (whisper wrote "130", read as "one hundred thirty"): the paired
     reading of a number and clock times are accepted when the reference says them that way.
   - S8's activity "fixing pronunciation" now always names the line (spec section 7).
   - 09b's checks include the zones rule, and 09c runs 09b again when 09b's plan fails 09b's current checks (the
     runner's own autofix in the rerun's sandbox, ported).
   - S7's share-identity check compares word stems ("Long recording" names "long recordings"); it blocked the ffmpeg
     idea in the second run.
   - The heartbeat's issue counters include S12's review issue (spec: "errors and failed reviews"); logcheck follows.
   - S8's comparison accepts more transcription spellings of words the voice said right (decision 287): a dotted clock
     time, a version read as one number, an acronym in capitals for spelled letters, common homophones (docs and
     docks), a number followed by a comma.

## Files

- New: pipeline/lib/logcheck.py, pipeline/bin/doctor, pipeline/tests/test-m13.sh, pipeline/tests/m13-run.sh,
  pipeline/tests/fixtures/ideas/three-ideas.txt, build/M13/rerun-idea.sh (one idea of the fixture again, detached).
- Evidence: build/M13/real (first real run), build/M13/real2 (the acceptance run: driver.log, result.env, run1.out to
  run3.out, samples.txt, story.json, logs/, exports/), build/M13/rerun and rerun3 (the single-idea reruns), the test
  logs build/M13/test-*.log.
- Changed (M13): pipeline/lib/ai.sh, log.sh, status.sh, runner.sh (the rotation call), pipeline/bin/runner-status,
  pipeline/lib/voiceprofile.py, pipeline/bin/build-voice-profile, config.json (logs.rotate_mb, rotate_keep),
  DECISIONS.md 276 to 287, CLAUDE.md, pipeline/knowledge/known-issues.md (one line tidied).
- Earlier milestones touched, because the M13 runs depend on them: M7 (pipeline/lib/voiceover.py: hotwords, the paired
  number reading, the "fixing pronunciation (line N)" activity; pipeline/lib/tts/whisper_worker.py: the hotwords),
  M6 (pipeline/lib/script_checks.py: the respelling guard of the one-line rewrite, the share-identity stems;
  pipeline/stages/07-script/prompt-rewrite-line.md), M10 (pipeline/lib/visual/plan_validate.py, plan9.py,
  __main__.py, pipeline/lib/visual.sh: the ported autofix; pipeline/tests/test-m10.sh: the no-solution scenario),
  M11 (pipeline/lib/review/audio_check.py: the hotwords), M3 (pipeline/tests/test-m3.sh: a timing flake of section
  10 under load).

## How to run the test

- `bash pipeline/tests/test-m13.sh`: every section; section 3 runs the three ideas with the real models (74 minutes
  when every idea was blocked early, 2 h 50 min for the acceptance run with one export; with three exports expect 6
  to 8 hours).
- `M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh`: the fake-only sections (about 20 minutes).
- `bash pipeline/tests/m13-run.sh real build/M13/real2` makes a real run on its own (start it detached: the Claude Code
  tool stops its background commands after 2 hours), then `M13_REAL_DIR=build/M13/real2 M13_SECTIONS=3 bash
  pipeline/tests/test-m13.sh` checks it.

## Test results

**Section 3, the acceptance run (build/M13/real2, second real run, every fix up to decision 285 in): 33 passed, 0
failed** (build/M13/test-m13-s3.log). The timeline in build/M13/real2/logs/runner.log:

- run 1: idea 1 (/init) exported #1 after 124 minutes (the edit review used its 5 rounds and exported with NEEDS
  REVIEW, as in M12); idea 2 (Playwright MCP) met the simulated session limit at its first S2 call ("LIMIT session limit
  hit, resuming at 14:40 (+2 min margin)", the target in limits.log, "RESUME limit reset, continuing: expanding idea",
  the retry in the same session f024e86d...), then the runner and the stage were killed at its first S3 call (exit 137,
  lock and stage pid left behind as after a real crash);
- run 2 (the restart): "START idea 1/2 ... (resumed at checking idea (gate), 2 stages done)", "S3 checking idea (gate):
  attempt 2 (the previous one was interrupted)", the gate passed; idea 2 was then blocked at S8 by the spec's voice rule
  (after its one rewrite the line "Heads up: Playwright's command line ..." was still heard as "Headset ...", 25
  percent); idea 3 (ffmpeg) was blocked at S7 by the share-identity check fixed afterwards (decision 286); the summary
  "queue empty: this session 0 exported, 0 dropped, 2 blocked";
- run 3 (forever mode on the empty queue): the summary, "IDLE no ideas in ideas.txt, checking every 2 s", then SIGTERM:
  "stopped by the user (TERM)", exit 130.
- logcheck.py found no problem in the whole story (every line, STEP chains, GATE, heartbeat counters and activities,
  LIMIT/RESUME, NEXT, the summaries); 503 samples of status.txt, every one a valid line; no em dash; exports numbered
  1 without gaps; history.txt one line per idea with exported or blocked and the reason.

**The first real run (build/M13/real, 74 minutes)** passed the same checks except one (32 of 33): its log has the
activity "fixing pronunciation" without the line, fixed afterwards (decision 284), so its log can never pass that check.
It surfaced the S8 bugs: the /init idea blocked for a correct "Claude" (decision 283) and the ffmpeg idea for a correct
"one thirty" (decision 284); the Playwright idea was blocked at S7 by a facts failure (the spec's rule).

**Validation reruns, one idea each, with the fixes:** the /init idea (build/M13/rerun, 141 minutes): S8 passed (2 of 12
lines misheard on the first pass instead of 6, none of them "Claude"), the runner's own review and fix loop repaired a
09b zones bug on the way (two autofix commits, ported to the repo, decision 285), exported #1 with NEEDS REVIEW from the
edit review's cap; logcheck: no problem. The ffmpeg idea (build/M13/rerun3): S7 passed this time (the stem fix), and
S8 blocked it again on three new transcription spellings of words the voice said right ("10.30" for "ten thirty",
"docks" for "docs", "FFM" for "eff eff em"); after the fix of decision 287, S8 replayed on that run passed (1 of 12
lines misheard, fixed by its rewrite; build/M13/rerun3/s8-again.out, voiceover-blocked.json and
voiceover-replayed.json). The rerun was not taken further than S8.

**Fake-only sections** (build/M13/test-m13-s124.log): 100 passed, 0 failed: section 1 (logcheck on a good timeline and
14 broken ones, the rotation alone and inside a live dummy run whose 2 rotated files still tell one story, the status
rename, the fault injection by itself, build-voice-profile --force on a copy of the profile, the doctor), section 2 (the
same three-idea scenario with the fake claude, about 11 minutes), section 4 (no em dash).

**Earlier milestones' tests after the touches to their code:** test-m1 96, test-m2 207 (a first run under the load of
two real pipelines failed its heartbeat timing check once; say() was then made as cheap as before), test-m3 fake 373
plus section 10 again 34 (its orphaned-reviewer scenario was a timing flake under load; the fake reviewer now waits
90 s), test-m5 fake 198, test-m6 fake 147 (twice), test-m7 fake 116 (three times), test-m10 fake 133 plus section 2
again 104 (M12's new solution.json in the frozen run had broken its no-solution scenario), test-m11 fake sections 1 and 2 (four
failures in section 2 from a one-off empty export.json written by the S14 dummy under heavy load; not reproduced), then
section 2 again 110, section 3 28 and section 1 again 89, test-limits 94, test-no-emdash 1. All passing.

## Known gaps

- whisper still mishears some lowercase command names ("init" heard as "and it"); hotwords cover names with a capital
  only. Such a line goes to the rewrite (it passed there in the rerun) or, for hook 2, gets a NEEDS REVIEW flag.
- The real runs are slow mostly because of the 5 edit-review rounds (as in M12): most reels end with NEEDS REVIEW from
  the editor while the motion library lacks the components the director asks for (the M12 HUMAN_TODO line).
- The log rotation inside a live run is tested with fast clocks (dummy stages and a 6 KB limit), not at 50 MB in a
  real run.
- Most real ideas still end blocked or with NEEDS REVIEW: of the six ideas of the two three-idea runs, one exported,
  two were blocked by the S8 bugs fixed here, one by the share-identity check fixed here, one by a facts failure and
  one by a line the voice garbled after its rewrite (both the spec's rules). The S8 rule (one rewrite, then block
  above 8 percent) is strict for a single short line; changing it is a spec decision, so it stays.
- One unexplained flake: the S14 dummy once left an empty export.json while two real pipelines and a test ran at once
  (most likely a here-document temp file that could not be created); not reproduced.

## HUMAN_TODO items added

- M13: `bash pipeline/bin/doctor`: the one-look health check; run it after changing anything on the PC or when the
  runner seems stuck.
- M13: build-runner.sh's uncommitted changes (the `--fallback-model` switch) predate M13; commit or drop them while the
  build runner is stopped.
- M13: the two reels of the M13 runs (build/M13/rerun/1.mp4 and build/M13/real2/exports/1/, both the /init idea, both
  NEEDS REVIEW from the edit review's cap) are worth one look each; their captions files list the components the
  visual director keeps asking for.
