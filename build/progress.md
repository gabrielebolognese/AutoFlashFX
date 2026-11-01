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
- Status: done (2026-11-01); review 1 fixed the same day (build/M4/fixes-1.md: the angle stage cleans the model's
  `change` text before angle.json is written, and the research model's gh rules are the read-only forms with the
  writing forms denied, DECISIONS.md 110 and 111; pipeline/tests/probe-gh-rules.sh probes the rules with the
  real probe model); review 2 fixed the same day (build/M4/fixes-2.md: an F fail of kind wording, a statement of
  the expansion that facts.md does not back while the core claim is verified, goes to S4 as an angle round
  instead of dropping the idea; only an F fail of kind core drops at once, DECISIONS.md 112). The test has four
  sections: 1 and 2 run without a model (the units and the whole
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
  DECISIONS.md 95 to 112. Report: build/M4/report.md.

## M5 Profile and hooks (S5, S6)
- Status: done (2026-11-01). The test has four sections: 1 and 2 run without a model (the units, then S5 and S6
  through run.sh with the fake claude from the frozen M4 outputs, including the regeneration path: 198 checks in
  about four minutes), 3 and 4 call the real indexer, research and judge models (34 checks; the index call about
  30 s, the S5 and S6 run about 6.5 minutes). M1, M2, M3 (limits), M4 sections 1 and 2 and the em dash scan pass
  with it.
- Test command: `bash pipeline/tests/test-m5.sh` (`M5_SECTIONS="1 2"` for the fake-only sections; `M5_FREEZE=1`
  also adds the real 05-hooks and 06-judge outputs to pipeline/tests/fixtures/runs/test-idea/);
  `bash pipeline/tests/run-all.sh` runs M1 to M5, limits and the em dash scan (about 65 minutes).
- Notes: pipeline/vendor/ig-agent-skill/ (hookscore.py, beats.py, hooks.json, humanize.py, detect.py, slop.json,
  caption.py, LICENSE, templates/voice.md, pinned in VERSION; run them with pipeline/bin/vendor-run).
  pipeline/bin/index-hooks with pipeline/lib/hooks.py: library/.hooks.index.json (id = sha1 of the normalized
  line, family and fit from one batched indexer call for the new ids only, nothing called when hooks.txt is
  unchanged), hooks.lint.txt, .hooks.stats.json, hooks.suggested.txt. pipeline/bin/build-voice-profile with
  pipeline/lib/voiceprofile.py: library/profile/voice.md and account.md (drafts with [FILL IN] placeholders until
  a memo exists; the pace, 195 wpm, and 5 verbatim excerpts measured from reference_long.wav with faster-whisper
  under engine.txt's interpreter; config voice.wpm set from it). S5 (pipeline/stages/05-hooks: run.sh, prompt.md,
  prompt-brief.md, prompt-regenerate.md, model.schema.json, brief.schema.json): session A resumed, or seeded at
  once when no id is stored (session.sh --seed-if-new), the template shortlist (24, every family, win-rate
  weighted, fit preferred), 12 to 20 hooks checked by hooks.py (cap min(8, ceil(wpm x 3 / 60) - 1) spoken
  words, 6 on-screen, a concrete marker, known template ids), then brief.md (2000 to 3000 tokens as words x 1.3);
  `run.sh <run_dir> --regenerate feedback.json` is the judge's one regeneration. S6 (pipeline/stages/06-judge:
  run.sh, prompt-rank.md, prompt-pair.md, rank.schema.json, pair.schema.json) with pipeline/lib/judge.py: the
  hookscore filter (under 50 or a dealbreaker out; fewer than 4 left: S5 regenerates once), two independent
  rankings with different shuffles merged by Borda, the top 4 pairwise in both orders in one call, judge.json
  (winner, runner-up, reasons, the whole trail), the stats update. Config: hooks.*, judge.*, timeouts
  index_seconds, hooks_seconds, brief_seconds, judge_seconds, transcribe_seconds, profile_seconds. Earlier
  milestones touched: session.sh (--seed-if-new), test-m4.sh section 2 (removes the sandbox's account.md so its
  "missing account.md" flag assertion keeps its premise now that M5 drafted the file), config.json, the dummies
  and schemas of 05-hooks and 06-judge. Not built: PLAN.md's setup-venv (engine.txt's interpreter already has
  faster-whisper; M7 decides). Hooks for M6: 05-hooks/brief.md and 06-judge/judge.json (winner = hook 1,
  runner_up = hook 2) are frozen under pipeline/tests/fixtures/runs/test-idea/; voice.md's Pace line is the wpm
  (hooks.py wpm), the vendored beats.py, humanize.py, detect.py and caption.py run through vendor-run;
  write_retry_prompt and the quality-loop pattern of S5 (check in Python, re-ask with the exact problems, flag on
  the last try) are the model for S7's checks. DECISIONS.md 113 to 138. Report: build/M5/report.md.

## M6 Script (S7)
- Status: done (2026-11-01). The test has three sections: 1 and 2 run without a model (the units of
  script_checks.py and the fake's task fixtures, then S7 through run.sh with the fake claude from the frozen M5
  outputs: the happy path, S8's one-line rewrite, a rewrite round, the block path and the soft path; 56 and 91
  checks in about 8 minutes), 3 calls the real script, cut, checks and judge models on the test idea (15 checks;
  the real S7 took 7 min 05 s, 9 calls, 2 rounds: 11 beats, 36.3 s, detect.py 82, 10 claims all supported). M1,
  M2 (alone on a quiet machine), M3 (the fake sections and limits), M4 sections 1 and 2, M5 sections 1 and 2 and
  the em dash scan pass with it.
- Test command: `bash pipeline/tests/test-m6.sh` (`M6_SECTIONS="1 2"` for the fake-only sections; `M6_FREEZE=1`
  also adds the real 07-script outputs to pipeline/tests/fixtures/runs/test-idea/);
  `bash pipeline/tests/run-all.sh` runs M1 to M6, limits and the em dash scan (about 85 minutes).
- Notes: pipeline/stages/07-script (run.sh, prompt.md, prompt-second.md, prompt-rewrite.md, prompt-cut.md,
  prompt-claims.md, prompt-pick.md, prompt-rewrite-line.md, model.schema.json, cut.schema.json, claims.schema.json,
  pick.schema.json, rewrite-line.schema.json, schema.json, CONTRACT.md) on pipeline/lib/script_checks.py (setup,
  draft, cut-data, cut-apply, cut-best, check, claims-data, claims, feedback, pick-data, pick, compose,
  rewrite-line-data, rewrite-line-apply, numbers, length-rule, tones, round-log; the vendored beats.py,
  humanize.py and detect.py imported as modules, unchanged). Session D (the two drafts and the rewrites; a lost
  session gets the self-contained prompt), the cut and the claims check in fresh sessions, the pick by the judge
  model in a seeded order. Round 1 writes, cuts and checks both drafts, the pick follows, rounds 2 and 3 rewrite
  the pick only; hard failures after the rounds block the idea unless the other draft passed (then a flag), soft
  failures flag. Config: script.*, timeouts script_seconds, cut_seconds, checks_seconds, pick_seconds. Earlier
  milestones touched: stage.sh write_retry_prompt's task argument (M4), the fake claude's "# Task:" fixtures
  (M3), 07-script's schema and dummy (M2), config.json (M1). Hooks for M7: script.json beats[].spoken is the TTS
  text (numbers written out, pronunciations applied; display is the caption text), beats[].seconds the estimate at
  voice.md's pace, hook2.spoken the alternate clip's line, `bash pipeline/stages/07-script/run.sh <run_dir>
  --rewrite-line <beat> --reason "<why>"` the one-line rewrite of S8's ladder (exit 0 rewritten, 4 unusable),
  script.json "rewrites" its record; the frozen 07-script outputs of the test idea are under
  pipeline/tests/fixtures/runs/test-idea/07-script/. DECISIONS.md 139 to 160. Report: build/M6/report.md.

## M7 Voiceover (S8)
- Status: done (2026-11-01). The test has three sections: 1 and 2 run without the engine or a model (48 unit
  checks: engine.txt, the word error rate and its normalizer, the respelling rules, pronunciations, silences, the
  preflight's voice check; then S8 through run.sh with the fake engine and fake transcriber from the frozen M6
  outputs: the happy path with the exact timeline, the ladder with a respelled acronym, a rewritten word and a
  slow line, the flag path, the block path, the engine crash and the engine hang as code errors, the dummy
  stage: 68 checks in about 6 minutes), 3 runs the real Kokoro af_bella and faster-whisper on the frozen script
  (23 checks, the real S8 took 1 min 47 s: synthesis at 0.45x real time plus 12 s to load Kokoro, alignment 41 s, loudness 5 passes; 139 checks pass in about 12 minutes). M1, M2 (alone on a quiet machine), M3 (the fake sections and limits), M4 sections 1 and 2,
  M5 sections 1 and 2, M6 sections 1 and 2 and the em dash scan pass with it.
- Test command: `bash pipeline/tests/test-m7.sh` (`M7_SECTIONS="1 2"` for the fake-only sections; `M7_FREEZE=1`
  also copies the real 08-voiceover JSON outputs into pipeline/tests/fixtures/runs/test-idea/, the wavs stay out
  of git); `bash pipeline/tests/run-all.sh` runs M1 to M7, limits and the em dash scan (about 95 minutes).
- Notes: pipeline/stages/08-voiceover (run.sh, CONTRACT.md, schema.json, dummy.sh) on pipeline/lib/voiceover.py
  (engine, engine-check, run, wer, pronounce, respell, silences, energy, measure) and the workers
  pipeline/lib/tts/kokoro_worker.py (tools/voice.py Engine, sentences and tighten under engine.txt's interpreter)
  and whisper_worker.py (faster-whisper small, CPU int8, under config tts.whisper_python). run.sh relays the
  Python's "@@ACTIVITY", "@@SAY", "@@FLAG" and "@@ERROR" lines to the runner and maps the exit code (0 done, 20
  block, else a code error). The voice config: library/voice/engine.txt with the defaults of BUILD_SPEC.md 2.5 for
  missing lines, the defaults alone when the file is missing or names another engine (today's file says turbo:
  HUMAN_TODO), kokoro af_bella only, never a fallback; the preflight check `voice` (engine-check) stops the runner
  when the interpreter is missing or cannot import kokoro or no interpreter imports faster_whisper. The stage:
  pronunciations.txt first (a respelling, or `/phonemes/` as Kokoro's `[word](/phonemes/)`), one batched worker
  call per step, every line tightened with voice.tighten (lead and tail 0) and joined with 0.05 s lead, 0.1 s
  gaps, the 1.0 s breath after the hook beat, 0.2 s tail; every line transcribed (0.5 s padding) and compared
  with the normalizer of DECISIONS.md 168 (split and joined words, digits, years, British spellings, possessives);
  the ladder (respelling by rule, one rewrite through `07-script/run.sh --rewrite-line`, flag at 8 percent or
  under, block above; hook 2 flags only); the 15 percent overrun check on a syllable-spread estimate at config
  voice.wpm (one rewrite, then a flag); loudness by gain plus limiter re-measured to -14 LUFS and -1.5 dBTP (48
  kHz mono 16-bit); words.json from the per-line transcriptions offset by the timeline (the spoken track's words
  with "heard" where whisper differed, the beats' windows, the breath, the pace); voiceover.json the full trail.
  Measured: Kokoro 0.40x real time plus 12 s to load, whisper about 3 s per line, pace 176 wpm after tightening
  (config voice.wpm set to it; S5 and S7 now read config voice.wpm first, voice.md's Pace line is the fallback;
  the M5 and M6 tests pin their sandbox at 195 with SANDBOX_WPM). Config: tts (device, whisper_model small,
  whisper_python, whisper_pad_s, wer_fail_pct 3, wer_flag_max_pct 8, overrun_pct 15, overrun_min_s 0.4, lead_s,
  tail_s; the chatterbox, turbo and qwen settings, gap_ms and voice.reference removed), voice.wpm 176, timeouts
  tts_seconds, align_seconds, loudness_seconds, paths.kokoro_python, the preflight voice entry. Earlier
  milestones touched: config.json (M1), preflight.sh's check type and the banner in status.sh with its assertions
  in test-m1 and test-m2 (M1, M2), S5's and S7's pace source (M5, M6), script_checks.apply_pronunciations (M6),
  tests/lib.sh (tools/ copied into the sandbox, SANDBOX_WPM), the 08-voiceover schema, dummy and contract (M2).
  Fakes: pipeline/tests/fakes/kokoro_worker.py and whisper_worker.py (REELS_TTS_WORKER, REELS_TTS_PYTHON,
  REELS_WHISPER_WORKER, REELS_WHISPER_PYTHON; FAKE_TTS_MODE, FAKE_TTS_SLOW, FAKE_WHISPER_GARBLE), the fixture
  pipeline/tests/fixtures/fake/m7/07-script.rewrite-line.json. Not exercised: pipeline/bin/setup-venv's install
  branches (nothing was missing). Hooks for M8 to M10: 08-voiceover/words.json (beats[].start_ms and end_ms, the
  breath window, words[] with beat ids) and vo.wav are the timeline S9 snaps to; the frozen JSON outputs of the
  test idea are under pipeline/tests/fixtures/runs/test-idea/08-voiceover/ (vo.wav regenerated by running the
  stage or test-m7 section 3). DECISIONS.md 161 to 177. Report: build/M7/report.md.

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
