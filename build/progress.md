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
  also refreshes the five frozen 08-voiceover outputs in pipeline/tests/fixtures/runs/test-idea/; without it,
  section 3 adds the untracked vo.wav and vo_hook2.wav whenever they are missing); `bash pipeline/tests/run-all.sh`
  runs M1 to M7, limits and the em dash scan (about 95 minutes).
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
  test idea are under pipeline/tests/fixtures/runs/test-idea/08-voiceover/: the three JSON files tracked, vo.wav
  and vo_hook2.wav ignored by git and added by test-m7 section 3 whenever they are missing (all five files from
  one run; review 1 fix 1, build/M7/fixes-1.md). DECISIONS.md 161 to 177. Report: build/M7/report.md.

## M8 Sound effects memory map
- Status: done (2026-11-01). The test has two sections, neither calls a model: 1 builds a synthetic pack with
  ffmpeg in the sandbox and drives build-sfx-map through every path with the fake claude answering the indexer
  call from fixtures (the model path with the retry for a skipped id, the no-op rebuild, ban and pin through
  rebuilds, a new and a removed file, --check, the failed call, --no-model); 2 checks the committed map of
  styles/sfx/ (coverage, fields, pools, previews, a no-op rebuild with the fake claude in error mode). 164 checks
  pass in about 90 seconds. M1 (96 checks) and the em dash scan pass with it; M2 was run for its banner
  assertion.
- Test command: `bash pipeline/tests/test-m8.sh` (`M8_SECTIONS="1"` or `"2"` for one section);
  `bash pipeline/tests/run-all.sh` runs M1 to M8, limits and the em dash scan (about 97 minutes).
- Notes: `bash pipeline/bin/build-sfx-map [--force] [--reclassify] [--no-model] [--check] [--quiet] [--dir DIR]`
  over pipeline/lib/sfx/ (common.py, measure.py: ffprobe, ffmpeg decode to 48 kHz float, numpy envelope
  analysis, ebur128 loudness and true peak, the normalized cache copy; classify.py: name rules, whoosh speed,
  the prompt lines and the model answers; overrides.py: ban and pin; pools.py: the quality filter, fit, pools;
  previews.py; writemap.py: sfx-map.json and SFX-MAP.md; sfxmap.py: the CLI steps plan, measure,
  classify-plan, build, check). The pack styles/sfx/ (106 files): 93 mapped, 13 excluded with reasons, 12
  waiting for the user's pin (model confidence under 0.6), 27 files classified by one haiku call (cached in the
  map), pools of 8 for the whoosh, click, pop and number cue types, stamp 4, notification 4, success 3, typing 2
  and negative 2 (short: HUMAN_TODO). Thresholds in config sfx.build (DECISIONS.md 181, 182, 185). A rebuild of
  an unchanged folder is a no-op (folder hash, overrides hash, settings hash) and never calls a model; a changed
  folder measures only the new and changed files. Outputs: styles/sfx/sfx-map.json, SFX-MAP.md, overrides.txt
  (tracked), previews/<cue type>.wav and .txt, .cache/<id>-<slug>.wav (ignored). The prompt
  pipeline/stages/_prompts/classify-sfx.md with classify-sfx.schema.json; the map's schema
  pipeline/lib/sfx/map.schema.json. Earlier milestones touched: config.json (sfx.build, the warn-level preflight
  entry for the map), test-m1 and test-m2 (the banner accepts `sfx map: N files`), 11-sfx/CONTRACT.md (the map's
  contract for M11). Hooks for M11: run `bash pipeline/bin/build-sfx-map --quiet` at the start of S11 (exit 1 =
  the indexer call failed, a code error; a missing map = voice only plus a flag); pick from `pools[<cue>]` (best
  fit first, pinned first), place whooshes by `peak_s` and the rest by `onset_s`, mix the `cache` copy (gain
  already applied, peak -12 dBFS, same timeline as the original); `short_pools` lists the thin ones. Hooks for
  M9: the cue type names and descriptions live in pipeline/lib/sfx/common.py CUE_TYPES (the components' declared
  sound events use the same twelve names). DECISIONS.md 178 to 191. Report: build/M8/report.md.

## M9 Motion library
- Status: done (2026-11-01). The test has six sections, none calls a model: 1 tokens (a sandbox copy of style.md and
  tweaks.md: build, schema, the cross-check against the sources, the no-op rebuild, a touched tweaks.md, an accepted
  PROPOSED line), 2 the library (`npx hyperframes lint` and `check --json` on motion-lib/, the catalog against the
  files, the logo spots' aspect ratios measured in the harness, one still per component), 3 frame-match (every
  component in compositions/ passes against vocabulary.md and the reference strips; the gallery page with a still
  and a player per component), 4 the golden reel (plan.json against the plan schema, the render at 1080x1920 30 fps
  within 0.2 s of vo.wav with audio, the contact sheet, the CTA branding), 5 the WebGL test, 6 the em dash scan.
  80 checks pass in about 8 minutes (frame-match about 4 minutes, the golden render about 70 s, the WebGL test
  about a minute); the first run on a machine also downloads chrome-headless-shell (about 150 MB).
- Test command: `bash pipeline/tests/test-m9.sh` (`M9_SECTIONS="1 2"` for the quick sections; section 4 needs the
  frozen vo.wav that test-m7 section 3 writes); `bash pipeline/tests/run-all.sh` runs M1 to M9, limits and the em
  dash scan.
- Notes: `bash pipeline/bin/build-tokens` (pipeline/lib/tokens.py, tokens.schema.json): styles/paper-cards/tokens.json
  from style.md plus tweaks.md by explicit rules, every number cross-checked against the sources, the in-force
  tweaks lines winning and PROPOSED lines ignored until the word is removed, the 15 open questions decided
  (DECISIONS.md 192 to 196), plus motion-lib/assets/tokens.css. The library motion-lib/ is a HyperFrames project
  (DECISIONS.md 197 to 205): compositions/<id>.html for the 24 vocabulary items plus paper-canvas, dm-card and
  hero-3d (Three.js, hf-seek), the shared assets/paper-cards.css and .js, the OFL fonts, vendored gsap and three,
  catalog.json (props from the declarations, beat types from tokens, sound events with frame offsets and cue types,
  demo props, stills, frame-match results; `python pipeline/lib/motion catalog [--write]`), index.html the showreel
  generated from the catalog. Tools under pipeline/lib/motion/ (run as `python pipeline/lib/motion <command>`):
  harness.py (Playwright, seeks the component's timeline frame by frame and dispatches hf-seek), framematch.py with
  expectations.py and strips.py (`bash pipeline/bin/frame-match`: 1 frame, 10 percent, strip correlation r >= 0.5,
  `--apply` moves failures to candidates/; motion-lib/gallery/frame-match.md and .json), gallery.py
  (`bash pipeline/bin/gallery`: stills, players, gallery/index.html, the showreel), webgl.py
  (`bash pipeline/bin/webgl-test`: motion-lib/webgl.json, hardware ANGLE and SwiftShader both work here), captions.py
  (the chunker), goldenplan.py and golden.py (`bash pipeline/bin/render-golden [--make-plan]`: golden/test-idea/
  plan.json from the frozen script and words with the hand-made DESIGN, the project built from the library, check,
  render, ffprobe, contact-sheet.png, README.md). The merged plan schema is pipeline/stages/09-plan/schema.json.
  `bash pipeline/bin/setup-node` installs the pinned packages (package.json), refreshes the vendored copies, checks
  Chrome and ffmpeg and installs the HyperFrames skills. Earlier milestones touched: config.json (a warn-level
  preflight entry for tokens.json), .gitignore. Hooks for M10: catalog.json is the director's and builder's index
  (props, beat_types, sound_events, demo, placement conventions); golden.py build_project is a plan-to-project
  compiler S10 can start from; apply_transitions turns 9c's transitions into exit props; captions.chunk_words is 9b's
  baseline; hero-3d needs clip_start; the brand paths convention brand/<path> and research/<file>; webgl.json
  render_flag for 3D renders; events are declared in the catalog and registered at runtime (window.__pcEvents).
  DECISIONS.md 192 to 214. Report: build/M9/report.md.

## M10 Visual stages (S9, S10)
- Status: done (2026-11-01). The test has four sections: 1 the units (the validator fixtures: good.json passes, each
  bad-<rule>.json fails naming its rule; the caption chunker's width limit; the pass schemas are current; the
  preflight's brand check: 30 checks, seconds), 2 the four stages through the runner with the fake director from the
  frozen M7 outputs (the plans validate, the merged plan passes the validator, the check passes, draft.mp4 540x960 30
  fps silent within 0.2 s of the voice, hook2.mp4 3.2 s, events.json verified on screen, the timeline cross-check,
  the activities and terminal lines; then the branding with a flashfx and an external solution.json, the flashfx reel
  built and its logos measured as images with their aspect ratio locked: 92 checks in about 15 minutes, two builds with
  renders; 2r the builder's repair loop with a planted broken component, the fake builder asked twice, then a code
  error: 12 checks, about 3 minutes), 3 the real visual director and the build (43 checks; the real S9a, S9b, S9c and
  S10 took 7 min 48 s: three director calls without a retry, 27 component instances, 46 caption chunks, the check ok
  at once with no builder repair, 120 events with 79 of 79 verified, the draft rendered in 86 s), 4 the em dash scan.
  178 checks pass in about 30 minutes. M1 (96 checks), M9 (80 checks), M2 and the em dash scan pass with it.
- Test command: `bash pipeline/tests/test-m10.sh` (`M10_SECTIONS="1 2"` for the fake-only sections; `M10_FREEZE=1`
  also refreshes the frozen 09a/09b/09c plans, the 10-build outputs and the fake director's answers under
  pipeline/tests/fixtures/); `bash pipeline/tests/run-all.sh` runs M1 to M10, limits and the em dash scan (about
  2 hours).
- Notes: pipeline/stages/{09a-animations,09b-text,09c-transitions} (run.sh over pipeline/lib/visual.sh, prompt.md,
  model.schema.json, schema.json from pipeline/stages/09-plan/pass-schemas.py, CONTRACT.md, dummy.sh) and
  pipeline/stages/10-build (run.sh, prompt.md for the builder's repair, schema.json, CONTRACT.md, dummy.sh) on the
  package pipeline/lib/visual/ (`python pipeline/lib/visual <command>`: digest, animations, text, transitions, merge,
  validate, build, events, contact-sheet). The director designs, the code composes (plan9.py: times from words.json,
  the branding by the solution, the chunks from the real words, the transitions' durations) and validates
  (plan_validate.py: 19 named rules, thresholds from tokens.json, catalog.json, brand.json, config visual.*); one
  retry with the exact problems, then the review path. S10 compiles the plan with motion/golden.py build_project,
  checks it, calls the builder model only to repair a failing check (inside the project folder, visual.build_fix_rounds
  rounds; builder_escalation for visual.three_d_heavy_objects 3D objects or state.json rounds.review >= 2), reads
  events.json from the mounted components (events.py: absolute ms, the catalog's cue, verified one frame before and
  after; the scene changes from the transitions; `npx hyperframes timeline` cross-check), renders the silent draft
  (native render, ffmpeg to 540x960), the hook 2 clip and the contact sheet (pipeline/bin/contact-sheet). WebGL
  missing: hero-3d becomes a card plus a NEEDS REVIEW flag. Config: visual.*, timeouts plan_seconds, build_seconds,
  check_seconds, events_seconds, render_draft_seconds, the preflight entries (brand, tokens.json, catalog.json,
  node_modules/hyperframes, all hard). Earlier milestones touched: motion/golden.py (an optional voice, folder, meta
  id, title, REELS_NODE_PREFIX), motion/captions.py (max_width, width_fn), motion/goldenplan.py (width-aware chunks,
  push 267 ms), tokens.py BEAT_TYPES (window-card for comparison and before-after) with tokens.json, tokens.css and
  catalog.json rebuilt, motion/harness.py (the element's tag), motion-lib/compositions/headline.html (word span ids),
  golden/test-idea regenerated (42 chunks), the M2 dummies, schemas and contracts of the four stages, config.json,
  preflight.sh, tests/lib.sh (--with-visual; every --with-pipeline sandbox gets tokens.json, catalog.json, the brand
  kit and node_modules/hyperframes/package.json so the earlier tests' preflight still passes). Fixtures: the frozen
  09a/09b/09c plan.json, 09c merged.json, 10-build/{events.json,plan.json,build.json,check.json,contact-sheet.png,
  project/index.html,project/instances.json,hook2/index.html,hook2/plan.json} under
  pipeline/tests/fixtures/runs/test-idea/; the fake director's answers pipeline/tests/fixtures/fake/m10/
  (09a-animations.json, 09b-text.json, 09c-transitions.json); the validator fixtures pipeline/tests/fixtures/plans/;
  the solution fixtures pipeline/tests/fixtures/solutions/. Hooks for M11: 10-build/events.json is S11's input
  (events with ms, type, cue, component, instance, scene, beat, scene_change, transition_ms, transition_type,
  next_beat_type; the catalog's cue is a suggestion, the S11 rules decide; `end` on typing events), 10-build/plan.json
  the compiled plan (the components' boxes and texts for S12's checks), 10-build/project/ the composition S12's
  Puppeteer opens (index.html, compositions/, assets/, instances.json), draft.mp4 the silent 540x960 draft, the
  review loop's fix routing reopens 09a/09b/09c or 08 through reopen.txt and S10 merges the pass files again;
  state.json rounds.review drives the builder escalation. DECISIONS.md 215 to 233. Report: build/M10/report.md.

## M11 Sound effects pass and review loop (S11, S12)
- Status: done (2026-11-01). The test has five sections: 1 the units (S11 on the frozen build: 17 sounds from 40 candidates, every rule of the spec and the verification on the rendered stem, the detector on a planted shift and a planted extra sound, an [sfx] review note changing the next pass, the voice-only path, the mechanical, style and audio checks on the clean draft, the seven planted faults each caught by its kind, the routing rules, the dummies: 89 checks, about 8 minutes), 2 S11 and S12 through the runner with the fake editor (the pass: the lines, the activities, review.json, the filmstrips and the prompt; then the planted [text] issue: 09b, 09c, S10, S11 and S12 run again with the review's notes and round 2 passes, the state and the log show it: 110 checks, about 11 minutes, two builds with renders), 3 the cap (an editor that always fails with an [sfx] issue: five rounds with the activities "fixing [sfx] issues (round 2, opus)" to "(round 5, fable)", the NEEDS REVIEW flag with the notes, the export: 28 checks, about 5 minutes), 4 the real editor and the real faster-whisper on the frozen draft (26 checks, about 5 minutes, 1 model call; the editor scored the test idea 3 on most criteria and listed 16 tagged issues, the code checks passed, the outputs are frozen), 5 the em dash scan (1 check). 254 checks pass (the sections were run separately, about 30 minutes in all). M1 (96 checks), M2 (220), M7's fake sections (116), M9 (80) and M10's fake sections (134) pass after the touches to their code; M9's run rendered the golden reel again with the fixed caption line.
- Test command: `bash pipeline/tests/test-m11.sh` (`M11_SECTIONS="1 2 3"` for the fake-only sections; `M11_FREEZE=1` also
  copies the real 11-sfx and 12-review JSON outputs into pipeline/tests/fixtures/runs/test-idea/); `bash
  pipeline/tests/run-all.sh` runs M1 to M11, limits and the em dash scan (about 2.5 hours).
- Notes: S11 is pipeline/stages/11-sfx/run.sh over pipeline/lib/sfx/{assign,pick,place,level,render_stem,verify,audioio,
  mixsfx}.py (pipeline/bin/mix-sfx by hand): the cue rules of the spec on 10-build/events.json with the density read of
  DECISIONS.md 235 (typing beds are not hits, a checklist's ticks count once, a hero on the scene change pops at its
  landing), seeded per reel; the pools in rotation with logs/sfx-usage.json; whooshes by their measured peak, the rest by
  their onset, typing trimmed, tails cut 50 ms before the next sound; gains from the map's normalization plus config
  sfx.base_gain_db, capped 8 dB under the voice's local peak (floor: the overall peak minus 12 dB); the stem and the mix
  in numpy, verified on the rendered files (33 ms, the whoosh plateau rule, the strongest-rise onset over a bed, no
  unplanned sound, the 8 dB rule, -14 LUFS plus or minus 1, -1.5 dBTP) and corrected up to 3 passes; cues.json,
  sfx_stem.wav, mix.wav, draft_mixed.mp4, sound-map.txt, the hook 2 clip's sounds; voice only plus a flag without a map;
  the review's [sfx] notes change the next pass. S12 is pipeline/stages/12-review/run.sh over pipeline/lib/review/
  (`python pipeline/lib/review mechanical|style|audio|filmstrips|prompt|verdict|feedback|strip`): the mechanical checks in
  the Playwright harness host by host from the project's index.html (zones with the caption band exception, the right
  rail, fonts and sizes, overlaps, off-canvas, contrast 4.5:1 and 2.7:1 for the style's accent words from the pixels
  behind the glyphs, emphasis within 80 ms from the caption line's events, the branding rules with the surface measured
  behind the hidden logo), the style check with tools/analyze_refs.py (cadence against the references, delta E 5 palette
  share, accent share, loudness), the audio check (S11's verification, the mix transcribed, WER under 5), the editor
  (config models.qa, a fresh session, Read and Glob on the contact sheet, the filmstrips, three reference stills, the
  scene table and sound-map.txt; eight scores, branding_natural, tagged issues), the verdict and routing (pass at every
  check and every score 4 or more; else the earliest owner and everything after it reopened through reopen.txt, S12
  included; 3 opus rounds then 2 fable; then the export with NEEDS REVIEW; [voice] routes only with a quoted word), the
  feedback to the re-run passes ({{REVIEW}} in the director prompts, S8's respelling, S11's adaptation), a result cache
  for the unchanged checks. Earlier milestones touched: caption-line.html (M9: every chunk was scaled to 60 percent, found
  by the new check; the drafts and the contact sheet of the frozen test idea were rendered again), card.html (a logo keeps
  its aspect ratio), state.py (self reopen), visual.sh and the three director prompts, voiceover.py, config.json (sfx.*,
  review.*, timeouts, models.visual_director_escalation), tests/lib.sh (--with-review). Fixtures: the fake editor's
  answers pipeline/tests/fixtures/fake/{m11,m11-text,m11-sfx}/; the frozen projects are rebuilt from the plans by
  pipeline/tests/materialize-project.py. Hooks for M12: 11-sfx/mix.wav and mix_hook2.wav are the audio S13 muxes (48 kHz
  mono, -14 LUFS), 12-review/review.json and notes.md the review's verdict and notes (state.json flags carry the NEEDS
  REVIEW text for the captions file), 10-build/project and hook2 the compositions to render at 1080x1920. DECISIONS.md
  234 to 260. Report: build/M11/report.md.

## M12 Final render, caption, export, end to end (S13, S14)
- Status: done (2026-11-02). The test has five sections: 1 the units (solution.py, the expansion's decision and keyword rule, the gate's H, the script's solution checks, the history line with the solution type, the SOLUTION block, S13's checks on the golden render, the mux with a mix shorter than the clip, the post-pass at 1080x1920, the style check run twice into one folder, the model-limit fallback in ai.sh, the caption composer and its refusals, the dummies and schemas), 2 S11 real, S12 dummy, S13 and S14 through the runner on the frozen build with the fake caption model (exports/1 with every ffprobe and loudness check, the captions file in the spec's format with SOLUTION and a planted NEEDS REVIEW flag, the history line, the idea gone; about 10 minutes, two renders), 3 the honesty loop with the fake claude (a forced FlashFX solution fails H, S4 decides the external skill, the gate passes on round 2, never a drop), 4 the test idea from scratch with the real models and the real voice (exports/1/1.mp4, 1captions.txt, 1hook2.mp4; 168 minutes, 5 edit review rounds, exported with NEEDS REVIEW), 5 the em dash scan. Results: sections 1 and 5 96 passed, section 2 56, section 3 28, section 4 33 (its log after the captions printout is not valid: test-m12.sh was edited while the 3-hour run was executing it; see build/M12/report.md). After the touches to their code: test-m2 207, test-m3 fake sections 374, test-m4 fake 202, test-m5 fake 198, test-m6 fake 147, test-m11 fake 227, all passing.
- Test command: `bash pipeline/tests/test-m12.sh` (`M12_SECTIONS="1 2 3 5"` for the fake-only sections, about 20 minutes;
  section 4 is the real end to end run, 1 to 3 hours: `bash build/M12/run-s4.sh` starts it detached; `M12_FREEZE=1`
  copies its solution.json, render.json and 14-export outputs into the frozen fixtures); `bash pipeline/tests/run-all.sh`
  now includes test-m12.
- Notes: the problem-first solution (pipeline/lib/solution.py) runs through S1 (solution candidates), S2
  (02-expansion/solution.json with the keyword that follows the type), S3 (the honesty check H; a fail goes to S4,
  never a drop), S4 (decides again), S7 and S14 (the FlashFX rules), the SOLUTION block of Ncaptions.txt and the
  history lines (`date | idea | solution | exported N`). S13 is pipeline/stages/13-render/run.sh over
  pipeline/lib/finalrender.py (HyperFrames renders silent at 1080x1920, ffmpeg muxes 11-sfx/mix.wav with the audio
  padded, ffprobe and loudnorm checks, one post-pass). S14 is pipeline/stages/14-export/run.sh with prompt-caption.md
  over pipeline/lib/caption.py (hook 1 as the first line, one ask, 3 to 5 hashtags, humanize.py, the caption.py lint,
  export.json); the runner's export.py writes exports/N/. Earlier milestones touched: M2 (runner.sh exporting #N,
  history.sh, export.py, dummies), M3 (ai.sh: a model at its own limit falls back to opus), M4, M5, M6 (the solution
  retrofit), M11 (style_check.py: the hang in later review rounds). DECISIONS.md 261 to 275. Hooks for M13: the real run
  takes about 2 to 3 hours per idea, most of it in the 5 edit review rounds; the 03-gate autofix (b7ea7e3) came from
  test-m2's dummy run reaching the real reviewer. Report: build/M12/report.md.

## M13 Hardening
- Status: done (2026-11-02). The fault injection (REELS_FAULT in ai.sh: a CLI-shaped session limit once, or the runner
  and the stage killed), the rotation of logs/runner.log at 50 MB, status.txt written aside and renamed,
  pipeline/lib/logcheck.py (status lines and the runner.log story against spec sections 6 and 7, the activity table
  included), pipeline/bin/doctor, build-voice-profile --force keeping the hand-written parts of the profile, and the
  fixes the real runs surfaced: S8 and S12 pass the reel's names to faster-whisper as hotwords (it blocked a reel for a
  correct "Claude"), S7's one-line rewrite refuses a respelled name, S8 accepts "130" heard for "one thirty", S8's
  "fixing pronunciation (line N)" activity, the 09b zones check and the 09c rerun of 09b (ported from the runner's own
  autofix), the heartbeat counters with the review issue, S7's share-identity check on word stems, S8's comparison
  accepting more transcription spellings ("10.30", "docks", "FFM"). Results: section 3, 33 passed, on the second real run (build/M13/real2: run 1 killed at the second idea's first S3 call as planned after the simulated limit at its S2 call, the restart resumed S3 and finished the queue, idea 1 exported #1 after 124 minutes, idea 2 blocked at S8 by the spec's voice rule, idea 3 blocked at S7 by the share-identity check fixed afterwards, decision 286; 503 status samples all valid; the forever mode's IDLE line and its SIGTERM stop). Fake-only sections 1, 2, 4: 100
  passed. After the touches to their code: test-m1 96, test-m2 207 (a first run under the load of two real pipelines failed
  its heartbeat timing check once), test-m3 fake sections 373 plus section 10 again 34 (a timing flake under load:
  the fake reviewer now waits 90 s), test-m5 fake 198, test-m6 fake 147 (twice), test-m7 fake 116 (three times), test-m10 fake 133
  plus section 2 again 104 (an M12 fixture change had broken its no-solution scenario), test-m11 fake: sections 1
  and 2 in one run (4 failures in section 2 from a one-off empty export.json of the S14 dummy under heavy load, not
  reproduced), then section 2 again 110, section 3 28 and section 1 again 89, test-limits 94, test-no-emdash 1, all passing.
- Test command: `bash pipeline/tests/test-m13.sh` (`M13_SECTIONS="1 2 4"` for the fake-only sections, about 20 minutes;
  section 3 runs three ideas with the real models, several hours: start `bash pipeline/tests/m13-run.sh real
  build/M13/real2` detached, then `M13_REAL_DIR=build/M13/real2 M13_SECTIONS=3 bash pipeline/tests/test-m13.sh`);
  `bash pipeline/tests/run-all.sh` includes it.
- Notes: the first real run (build/M13/real) had every idea blocked within 74 minutes (two S8 bugs, fixed, and an S7
  facts block by the spec's rule); the rerun of its first idea with the fixes exported (build/M13/rerun, 141 minutes);
  the second three-idea run (build/M13/real2) is the one section 3 passes on. Earlier milestones touched: M3 (a test
  timing), M6 (script_checks.py, the rewrite prompt), M7 (voiceover.py, whisper_worker.py), M10 (plan_validate.py,
  plan9.py, visual.sh, test-m10.sh), M11 (audio_check.py). DECISIONS.md 276 to 287. Report: build/M13/report.md.

## M14 Motion grammar and energy meter
- Status: done (2026-11-07). The test has five sections: 1 the energy meter (the nine reference videos reproduced from
  styles/paper-cards/analysis/energy.json with a worst difference of 0.0; the M13 reel build/M13/rerun/1.mp4 fails all five
  targets and measures the spec's 16, 15, 1.2, 29 percent and 2.8 s; tokens.json energy.targets 41, 46, 3.3, 15 and 2
  derived from the look medians; the Energy override line; tokens.css's --m-* variables; the schema and the source check),
  2 the library (frame-match on the 28 components with the life checks: every main animation still within 1 frame and 10
  percent of its reference numbers, every strip at r 0.62 or more, no visible element still for 0.5 s, the inertia 2 to
  2.6 s after the landing, every component's energy measured alone; catalog.json with icon-3d; no tween or ease outside
  pc-motion.js; `npx hyperframes lint` and `check` clean; the gallery with the energy line), 3 icon-3d with WebGL and with
  its CSS fallback, the canvas layers for three seeds out of every text zone, without text, 30 to 70 percent outside, under
  20 px per second, 4 the golden reel rendered again from the same plan (every energy measure better than before, the
  moving share doubled: 13.0 to 28.1 percent), 5 the em dash scan. Results: the full run (build/M14/test-m14.log) 71 passed, 0
  failed in 37 minutes (section 1: 25, section 2: 24, section 3: 10, section 4: 11, section 5: 1); the partial runs
  before it (build/M14/tmp/) found the fit's end frame, the bar baseline and the caption chunk's first frame. After the touches to their code:
  test-m9 section 1 27 passed (its sandbox re-proposes the six accepted tweaks lines), test-m10 fake sections 134 passed;
  the full reruns of the fake-only tests of M9 to M13 are listed at the end of this section.
- Test command: `bash pipeline/tests/test-m14.sh` (no model call, about 35 minutes: frame-match on every component and
  the golden render; `M14_SECTIONS="1 3"` the quick sections, about 3 minutes); `bash pipeline/tests/run-all.sh` includes it.
- Notes: the meter is pipeline/lib/review/energy.py (`python pipeline/lib/review energy <video> [--plan merged.json]`,
  `energy calibrate --refs ... --out analysis/energy.json`); the grammar is motion-lib/assets/pc-motion.js (PCM.life: main
  animation, inertia, hold, exit, with E2's zoom and parallax rotation; PCM.canvas: the edge and ambient layers; PCM.idle,
  PCM.depth, PCM.camera, PCM.scroll, setter-driven count-ups and typing) and every composition was rewritten on it; icon-3d
  is the new component; tokens.json gained motion.grammar and energy (pipeline/lib/tokens.py GRAMMAR, the calibration
  file as a third source, the `- **Energy:** ...` override); frame-match measures 4.33 s per component at a quarter scale
  with the life and energy checks; golden.py seeds the canvas per reel and copies pc-motion.js. Earlier milestones touched:
  M9 (test-m9's sandbox, harness.py's tag and 3D-aware measures, golden.py, gallery.py, catalog.py), M10 (project.py,
  visual/common.py, plan_validate.py, plan9.py, events.py, the frozen index.html canvas hosts), M11 (mechanical.py).
  DECISIONS.md 288 to 300. Report: build/M14/report.md.
