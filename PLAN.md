# PLAN.md: Instagram reels autopilot, build plan

Written in M0 (2026-10-31) from BUILD_SPEC.md. One milestone per build batch, in this order, each with the files
it creates, its acceptance test (one exact command) and what it depends on. Decisions behind this plan are in
DECISIONS.md. Nothing here changes the spec; where the spec leaves a choice, the choice is named and recorded.

## 0. Conventions every milestone follows

These are fixed now so that 13 fresh sessions build one coherent system.

### Languages and interpreters
- Runner, libraries and stage scripts: bash for Git Bash (`#!/usr/bin/env bash`, `set -u`, LF endings via
  .gitattributes). GNU date, grep, sed and awk as shipped with Git Bash.
- Helpers that need real parsing, JSON, audio math or similarity: Python 3.13, always invoked as `python`
  (`python3` is the Windows Store stub). Packages listed in `requirements.txt`, installed by
  `pipeline/bin/setup-python`.
- Text to speech: tools/voice.py (the user's script), which runs the one engine named in `library/voice/engine.txt`
  (Kokoro with the stock voice af_bella, no cloning; one voice, no fallback voice) through its own interpreter, in
  the user's virtual environment outside the project. Transcription (faster-whisper): a separate virtual environment
  `.venv-tts/` on Python 3.11 (created by `pipeline/bin/setup-venv` with uv). Scripts call it by path:
  `.venv-tts/Scripts/python.exe`. Everything runs on CPU (BUILD_SPEC section 0, Hardware).
- Video: Node 22 with the npm package `hyperframes` (pinned in `package.json`) and `puppeteer` for the mechanical
  checks. `pipeline/bin/setup-node` runs `npm ci` and `npx hyperframes browser ensure`.
- Nothing calls a model except through `ai()` in `pipeline/lib/ai.sh`.

### Paths and roots
- `REELS_REPO`: the folder that holds run.sh (resolved by every script from its own location).
- `REELS_ROOT`: the state root that holds ideas.txt, runs/, exports/, logs/, .locks/ and library/. Defaults to
  `REELS_REPO`. Tests point it at a temporary folder so no test ever touches the real queue or exports.
- `config.json` is read from `$REELS_ROOT/config.json`, falling back to `$REELS_REPO/config.json`. Its `paths`
  section holds every other location (styles, sfx map, motion-lib, golden, vendor, venv); relative paths resolve
  against `REELS_REPO`.

### Stage contract (`pipeline/stages/<NN-name>/`)
- Files: `run.sh <run_dir>` (the real stage), `dummy.sh <run_dir>` (writes fake outputs that validate against the
  schema, used by fast tests), `CONTRACT.md` (inputs, outputs, invariants), `prompt.md` (when a model is called),
  `schema.json` (the JSON outputs).
- Exit codes: 0 done (quality flags, if any, are appended to `state.json` `flags[]` and the stage still counts as
  done), 10 drop the idea (reason in `<stage>/result.json`), 20 block the idea (reason in `result.json`), any other
  code is a code error and goes to the review and fix loop (spec 4.2).
- A stage is done when its JSON outputs validate (`python pipeline/bin/validate-json <schema> <file>`) and
  `<stage>/.done` exists. The runner never re-runs a done stage unless a fix routes back to it.
- Stage folders in a run: `01-research 02-expansion 03-gate 04-angle 05-hooks 06-judge 07-script 08-voiceover
  09a-animations 09b-text 09c-transitions 10-build 11-sfx 12-review 13-render 14-export`.

### Test harness (`pipeline/tests/`)
- `lib.sh`: `sandbox_init` (temporary `REELS_ROOT` with a copy of config.json, fixtures and an empty queue;
  `--with-pipeline` also copies `pipeline/` and runs `git init` so a fixer can commit without touching the real
  repo), `fast_mode` (`REELS_SLEEP_SCALE=0.001`, `REELS_STATUS_EVERY=2`, `REELS_POLL_SECONDS=1`),
  `assert_*` helpers, `PASS`/`FAIL` lines, a non-zero exit on any failure.
- `test-mN.sh`: the acceptance test of milestone N, exactly the command written in PLAN.md and build/progress.md.
- `run-all.sh`: runs every `test-m*.sh` that exists plus `test-no-emdash.sh` (greps tracked text files for U+2014,
  excluding library/hooks.txt, which is the user's file, and pipeline/vendor/).
- Frozen fixtures: each stage milestone freezes the test idea's outputs under
  `pipeline/tests/fixtures/runs/test-idea/<stage>/`, so later tests start from real data without re-running the
  earlier stages (set `REELS_FROM_SCRATCH=1` to re-run everything instead).
- Fast mode: `REELS_SLEEP_SCALE` multiplies every sleep; `0` means fast-forward (log the wait with its target time,
  do not sleep). `REELS_DUMMY=all` or a comma list of stage numbers runs `dummy.sh` instead of `run.sh`.
- Fake model: `pipeline/tests/fakes/claude`, placed first on PATH by a test, answers according to
  `FAKE_CLAUDE_MODE` (ok, each limit format, transient, bad-json, fixture:<file>).

### Terminal and logs
- `pipeline/lib/log.sh`: `say TAG text` prints `[HH:MM] TAG    text` (TAG padded to 6 characters), colored with
  ANSI when stdout is a terminal and NO_COLOR is unset, and appends the line to logs/runner.log. Heartbeat, IDLE
  and the latest event line also overwrite logs/status.txt.
- Stages publish their activity text through `set_activity "<text>"` (file `logs/.activity`), read by the heartbeat.

### Git
- Commits per batch: `feat(Mn): ...`, `fix(Mn): ...`, the fixer at runtime: `autofix(<stage>): <cause>`.
- Generated text files that are tracked: `styles/paper-cards/tokens.json`, `styles/sfx/sfx-map.json`,
  `styles/sfx/SFX-MAP.md`, `pipeline/knowledge/known-issues.md`. Ignored: runs/, exports/, logs/, .locks/,
  `.venv-tts/`, node_modules/, `.hyperframes/`, media files, caches, previews, `library/.hooks.index.json`,
  `library/hooks.lint.txt`.

### Stage to milestone map
| stage | milestone |
|---|---|
| ideas.txt, lock, add-idea.sh, config, preflight | M1 |
| runner loop, state, resume, exports numbering, status lines | M2 |
| ai(), limits, classifier, review and fix loop, block, systemic stop | M3 |
| S1 research, S2 expansion, S3 gate, S4 angle | M4 |
| hooks index and lint, voice.md, account.md, S5 hooks, S6 judge | M5 |
| S7 script | M6 |
| S8 voiceover | M7 |
| sfx memory map (spec 2.6) | M8 |
| tokens.json, motion-lib, gallery, frame match, golden reel | M9 |
| S9a, S9b, S9c, S10 | M10 |
| S11 sfx pass, S12 review loop | M11 |
| S13 render, S14 caption and export, end to end | M12 |
| hardening | M13 |

## M1 Skeleton

Depends on: M0 (this plan). Tools already present: git, python 3.13, node 22, ffmpeg 9, gh (logged in).

Creates:
- Folders: `library/profile/`, `library/voice/` (ignored, with a README.txt saying what goes there), `motion-lib/`,
  `motion-lib/candidates/`, `motion-lib/gallery/`, `golden/`, `pipeline/{lib,stages,bin,vendor,knowledge,tests}/`.
  `runs/`, `exports/`, `logs/`, `.locks/` are created by the runner at startup.
- `config.json`: every key of spec section 9 (models with effort levels, tts, voice, sfx, lengths, caps, runner,
  style, paths) plus `preflight.require` (the hard dependencies checked at startup; later milestones append to it)
  and `runner.sleep_scale` defaults. Values that later milestones refine (tts engines, sfx gains) start with the
  spec's numbers.
- `ideas.txt` with the one test idea from spec 2.1.
- `library/hooks.txt`: `git mv hooks.txt library/hooks.txt`, content untouched (the spec forbids editing it).
- `library/profile/deliverables.txt` and `library/profile/pronunciations.txt`: header comments explaining the
  format, no entries (HUMAN_TODO to fill them). account.md and voice.md come in M5.
- `pipeline/lib/config.sh` (`cfg <dotted.key>` through a Python one-liner), `pipeline/lib/ideas.sh` and
  `pipeline/lib/ideas.py` (parse braces across lines, CRLF and UTF-8, ignore text outside braces, normalized text,
  id = sha1 of the normalized text, first idea, append, remove by id with the 0.9 similarity fallback, every write
  through the lock `.locks/ideas` (mkdir, 60 s stale timeout) and a temp file plus mv), `pipeline/bin/add-idea.sh`
  (appends every braced block from its arguments or stdin, prints one confirmation line with the queue size),
  `pipeline/bin/validate-json`, `pipeline/bin/preflight` and `pipeline/lib/preflight.sh` (claude, ffmpeg, ffprobe,
  python, node, gh, the Python packages, disk space, style files; writes logs/STOPPED.md with the exact fix on a hard
  failure), `pipeline/bin/setup-python`, `requirements.txt` (jsonschema).
- `run.sh`: runs preflight, prints the banner (version, queue size, style, voice engine, sfx map file count or
  "not built") and the queue, then exits with "the loop arrives in M2". M2 replaces the body.
- Tests: `pipeline/tests/lib.sh`, `pipeline/tests/run-all.sh`, `pipeline/tests/test-no-emdash.sh`,
  `pipeline/tests/test-m1.sh`, fixtures under `pipeline/tests/fixtures/ideas/` (multi-line idea, CRLF file, Italian
  accents, notes outside braces, empty file, braces inside a note).
- `.gitignore` is already the spec's list (done in M0). `.gitattributes` exists.

Acceptance test: `bash pipeline/tests/test-m1.sh`
- Parser fixtures: the right count and the exact text for each fixture (accents intact, CRLF normalized, text outside
  braces ignored); ids are stable when other lines are added or deleted.
- Remove: the exact idea, a lightly edited idea (similarity at least 0.9) and an unrelated edit (left alone, logged).
- Concurrency: 20 `add-idea.sh` processes in the background while the library removes the first idea; afterwards the
  file holds exactly 20 ideas, each intact, and the lock directory is gone. A stale lock (older than 60 s) is removed
  and logged.
- `bash run.sh` prints the banner and exits 0; preflight fails with STOPPED.md when a required tool is hidden from
  PATH in the sandbox.
- No model calls. Runs in under a minute.

## M2 Runner core and terminal output

Depends on: M1.

Creates:
- `run.sh` (the loop of spec section 3: `--once`, poll every `runner.poll_seconds`, take the first idea, create or
  resume its run, run the stages in order, export, drop or block, next idea; the preflight and banner from M1).
- `pipeline/lib/state.sh` and `pipeline/lib/state.py`: `runs/<YYYY-MM-DD_HHMM>_<slug>/state.json` (idea id and
  text, run id, created, per stage status with attempts and session ids, flags, issue counters, round counters,
  export number), stage order, `.done` markers, resume of an unfinished run, detection of a run that was mid-export.
- `pipeline/lib/runner.sh`: the stage loop, exit code handling (0, 10, 20, other), the dummy switch
  (`REELS_DUMMY`), activity updates, event lines.
- `pipeline/lib/log.sh` and `pipeline/lib/status.sh`: every message of spec sections 6 and 7: the heartbeat every
  `runner.status_every_seconds` with `#idea i/n`, the idea text cut at 40 characters, the activity, minute, stage
  time and issue counters; the IDLE line with the idle minutes and the day's counts; the banner; the summary line when
  the queue empties; the event lines START, STEP, GATE, ANGLE, FLAG, DONE, DROP, BLOCK, NEW, NEXT (LIMIT, RESUME,
  RETRY, ERROR, FIXED, ESCAL, STOP are wired in M3 but the formatting lives here); logs/status.txt overwritten.
- `pipeline/lib/export.sh`: assemble in `runs/<id>/export/`, compute N under `.locks/exports` as the highest number
  in exports/ plus 1, move the folder into `exports/N/` in one step, write the history line, remove the idea.
- `pipeline/lib/history.sh`: logs/history.txt lines (`date | idea | exported N`, `dropped: reason`,
  `blocked: reason`; M12 adds the solution type, spec 4.3), logs/blocked.txt.
- `pipeline/stages/<every stage>/dummy.sh`, a first `CONTRACT.md` and `schema.json` per stage (the real content
  arrives with each stage's milestone, but the folder set and the schema file names are fixed here).
- `pipeline/bin/runner-status` (prints logs/status.txt and the last 20 lines of runner.log).
- `pipeline/tests/test-m2.sh`.

Acceptance test: `bash pipeline/tests/test-m2.sh`
- In a sandbox with `REELS_DUMMY=all` and fast mode: start `run.sh`, kill it with SIGKILL while a dummy stage is
  sleeping, restart it, and the log shows the same stage resuming with the earlier stages skipped (state.json agrees).
- Two dummy ideas produce `exports/1/` and `exports/2/` with `1.mp4`, `1captions.txt`, `1hook2.mp4` (dummy content)
  and two history lines; ideas.txt is empty afterwards; a crash planted between assembling and moving the export
  does not produce a duplicate or a gap on restart.
- The heartbeat prints on the scaled schedule with every field (checked by regex), IDLE appears once the queue is
  empty with the right counts, the banner prints at startup, logs/status.txt always holds the latest line, and
  NO_COLOR output has no escape codes.
- No model calls. Runs in a few minutes.

## M3 Error system

Depends on: M2. Real model calls (Opus reviewer, Sonnet fixer) in one part of the test.

Creates:
- `pipeline/lib/ai.sh`: `ai <role> <stage_dir> <prompt_file> [options]` runs
  `claude -p --model <model> --effort <effort> --output-format json --permission-mode auto --permission-prompts none`,
  adds `--resume <session id>`, `--json-schema <file>`, `--allowedTools <list>` and `--disallowedTools` (no writes
  to ideas.txt, library/, styles/, exports/; no reading .env) as requested, saves the raw output to
  `<stage_dir>/calls/NNN.json`, returns the session id and the result, snapshots the protected files before the call
  and restores them (and raises a code error) if a call changed them, and on failure runs the classifier. Model names
  and efforts come from config.json only.
- `pipeline/lib/limits.sh`: detection and parsing of every limit format of spec 4.1 (time only, weekday and time,
  date and time, timezone in parentheses, epoch after `|`), past-time rollover (+1 day, +7 days), the wait with the
  120 s margin in 60 s chunks that re-check the clock, logs/limits.log, the 30-minute probe loop when nothing parses.
- `pipeline/lib/errors.sh`: the classifier (limit, transient with 60 s, 4 min, 16 min backoff, code error, quality),
  the normalized error signature (numbers, paths and timestamps stripped, hashed).
- `pipeline/lib/review.sh`: `runs/<id>/errors/E<n>.md` with every part listed in spec 4.2, the reviewer call
  (read-only tools plus WebSearch and WebFetch, reads known-issues.md, writes `fixes/F<n>.md` with root cause, class,
  exact changes, verify command, auto_apply), the fixer call (may edit only pipeline/ and motion-lib/candidates/,
  applies, verifies, commits `autofix(<stage>): <cause>`, appends to known-issues.md), stage restart with a resume
  note, caps (3 Opus cycles, the repeated-signature shortcut, 1 Fable escalation), blocking (ideas.txt, blocked.txt,
  run kept), the systemic stop (3 ideas in a row blocked by the same signature, or preflight) writing logs/STOPPED.md.
- `pipeline/stages/_prompts/reviewer.md` and `fixer.md`, `pipeline/knowledge/known-issues.md` (header only).
- Event lines LIMIT, RESUME, RETRY, ERROR, FIXED, ESCAL, BLOCK, STOP and the activity replacements of spec 7.
- Tests: `pipeline/tests/fakes/claude`, `pipeline/tests/test-limits.sh` (unit tests of the parser with fake
  messages for every format, including weekly), `pipeline/tests/test-m3.sh`, fixture stages
  `pipeline/tests/fixtures/stages/buggy/` (a planted bug a reviewer can find: a wrong key in a Python helper) and
  `pipeline/tests/fixtures/stages/unfixable/` (needs a key file that does not exist).

Acceptance test: `bash pipeline/tests/test-m3.sh`
- With the fake claude first on PATH, every limit format yields the right reset epoch and the runner logs the right
  wait target in fast-forward mode (`REELS_SLEEP_SCALE=0`); an unparseable limit enters the probe loop; a transient
  error backs off 60 s, 4 min, 16 min (scaled) and then becomes a code error.
- In a sandbox git repo: the buggy stage fails, E1.md contains the stage, command, exit code, last log lines, input
  files, CONTRACT.md, git diff and earlier files; the Opus reviewer writes F1.md with all five parts; the Sonnet
  fixer applies it, the verify command passes, the commit `autofix(...)` exists, known-issues.md gained one line, the
  stage restarts and passes; the log shows ERROR then FIXED.
- The unfixable stage blocks the idea: gone from ideas.txt, in blocked.txt with the reason, run folder kept, the
  runner continues with the next idea (BLOCK then NEXT in the log).
- Three identical blocks in a row write logs/STOPPED.md with the diagnosis and the exact fix, and the runner exits
  (STOP line). The repeated-signature rule skips the remaining Opus cycles before escalation.
- Runtime: 10 to 20 minutes, dominated by the real reviewer and fixer calls.

## M4 Research, expansion, gate, angle (S1 to S4)

Depends on: M3 (ai, sessions, errors). Network, gh login, Playwright Chromium (installed by setup-python).

Creates:
- `pipeline/stages/01-research/{run.sh,prompt.md,CONTRACT.md,schema.json}`: session A with the research model,
  tools WebSearch, WebFetch, Bash restricted to `gh` and `pipeline/bin/screenshot`, writes facts.md (claims with
  source URL and date checked, primary sources first), numbers.json, assets/ plus assets.json, pitfalls and the
  "one specific true thing" candidates (as sections of facts.md and fields of research.json).
- `pipeline/bin/screenshot` (Playwright, 1080 px wide, PNG plus a JSON sidecar with URL and date; never bypasses
  sites that block automation).
- `pipeline/stages/02-expansion/...`: session A resumed, expansion.md 500 to 1500 characters with the five parts of
  spec S2, plus expansion.json for the checks.
- `pipeline/stages/03-gate/...`: fresh session B with the gate model, gate.json (P, S, C, F with quoted evidence,
  pass or fail, reason), the decision rules (pass; P, S or C failing goes to S4 for at most 2 rounds; F failing drops
  at once; a different-topic angle drops and writes logs/suggested-ideas.txt). Since M4 review 2: F failing drops
  at once when the idea's facts fail (kind core); an F fail caused by a statement of the expansion that facts.md
  does not back, with the core claim verified (kind wording), goes to S4 like a failing P, S or C (DECISIONS.md 112).
- `pipeline/stages/04-angle/...`: session A resumed with gate.json, rewrites expansion.md, back to S3.
- `pipeline/lib/session.sh`: session ids per run in state.json, resume, and the reseed fallback (a new session
  seeded with facts.md, expansion.md and the latest gate feedback) when resuming fails.
- `requirements.txt` adds playwright; `pipeline/bin/setup-python` installs Chromium.
- Event lines GATE and ANGLE, activities "researching facts", "expanding idea", "checking idea (gate)",
  "finding a better angle (round 1/2)".
- Tests: `pipeline/tests/test-m4.sh`, fixture `pipeline/tests/fixtures/ideas/false-idea.txt` (a deliberately
  false claim about a tool feature that does not exist), the frozen outputs of the test idea under
  `pipeline/tests/fixtures/runs/test-idea/{01-research,02-expansion,03-gate}/`.

Acceptance test: `bash pipeline/tests/test-m4.sh`
- The test idea, in a sandbox: facts.md exists and every claim line carries a URL and a checked date; numbers.json
  and assets.json validate and each asset file exists; expansion.md is 500 to 1500 characters and contains the
  problem sentence, the share identity, the keyword with its deliverable, the one specific true thing and evidence
  lines; gate.json validates with scores 0 to 3 and quoted evidence.
- The false idea: dropped with a reason and the scores in the history line, its block gone from ideas.txt, nothing
  written to ideas.txt by the model.
- With the fake claude returning a gate.json where S is 1: S4 runs, the round counter reaches 2, then the idea is
  dropped (the angle loop and its cap, without burning real calls).
- Runtime: 10 to 25 minutes.

## M5 Profile and hooks (S5, S6)

Depends on: M4 (brief context, session A), network for the vendor copy. The hooks index needs the indexer model.

Creates:
- `pipeline/vendor/ig-agent-skill/`: hookscore.py, beats.py, hooks.json, caption.py, humanize.py, detect.py,
  slop.json and LICENSE copied from github.com/Jakeschincariol/instagram-agent-skill at a pinned commit, plus
  `VERSION` (commit, date). Behavior untouched; wrappers live in pipeline/lib.
- `pipeline/bin/index-hooks` and `pipeline/lib/hooks.py`: `library/.hooks.index.json` (id = first 10 hex of sha1
  of the normalized line, family, fits_problem_solution, blanks; family and fit from one batched indexer call), the
  hash cache, `library/hooks.lint.txt` (broken blanks, grammar, duplicates, em dashes),
  `library/.hooks.stats.json` (picked, won, judge scores), `library/hooks.suggested.txt` (created empty).
- `library/profile/voice.md`: built from `library/voice/memo.*` when it exists (transcribed with faster-whisper in
  `.venv-tts`, created by `pipeline/bin/setup-venv` in its first, whisper-only form), keeping the user's real
  English, with 3 to 5 verbatim excerpts and the measured words per minute; otherwise the vendor template
  (templates/voice.md) with clear placeholders and a HUMAN_TODO. `library/profile/account.md`: a draft with
  placeholders and a HUMAN_TODO. `pipeline/bin/build-voice-profile` does both and is re-runnable.
- `pipeline/stages/05-hooks/{run.sh,prompt.md,CONTRACT.md,schema.json}`: session A resumed; template choice
  (12 to 20 from at least 3 families, fit preferred unless the angle is a personal story, win-rate weighting once
  stats exist, uniform at first); hooks.json (spoken line of 8 words or fewer and under 3 s at the user's wpm,
  on-screen line of 6 words or fewer, a concrete marker, no em dash); then brief.md (2 to 3 thousand tokens).
- `pipeline/stages/06-judge/{run.sh,prompt.md,CONTRACT.md,schema.json}` and `pipeline/lib/judge.py`: the
  hookscore.py filter (dealbreakers and scores under 50; a single S5 regeneration when fewer than 4 survive), two
  shuffled rankings merged by Borda count, pairwise top 4 in both orders, judge.json (hook 1, hook 2, reasons),
  stats update.
- Activities "picking hooks", "judging hooks".
- Tests: `pipeline/tests/test-m5.sh`, frozen `05-hooks/` and `06-judge/` fixtures.

Acceptance test: `bash pipeline/tests/test-m5.sh`
- `index-hooks` over library/hooks.txt: one entry per hook line with id, family, fit and blanks; the lint names the
  broken-blank lines and the em-dash lines of the user's file; a second run with no change makes no model call.
- Starting from the frozen M4 outputs (which also exercises the reseed path, since no session exists):
  hooks.json validates, 12 to 20 hooks from at least 3 families, every spoken line 8 words or fewer and under 3 s at
  the configured wpm, every on-screen line 6 words or fewer, every hook with a concrete marker, no em dash;
  brief.md within the token range; judge.json holds a winner and a runner-up with reasons; stats show the picks and
  the win.
- Runtime: 10 to 20 minutes.

## M6 Script (S7)

Depends on: M5 (brief, hook 1, vendor scripts, voice.md).

Creates:
- `pipeline/stages/07-script/{run.sh,prompt.md,prompt-cut.md,prompt-claims.md,prompt-pick.md,
  prompt-rewrite-line.md,CONTRACT.md,schema.json}`: fresh session D with the script model; two drafts in two tones;
  the structure of spec S7 (hook with spoken and on-screen lines, stake 2 to 7 s, body beats with types, payoff, one
  ask that repeats a hook word); display and spoken tracks per beat; the cut pass with the cut model (about 20%
  fewer words, no fact lost); the pick (pairwise, voice.md excerpts as reference); up to 3 rewrite rounds; hard
  failures block, soft failures flag; `prompt-rewrite-line.md` serves S8's one-line rewrite.
- `pipeline/lib/script_checks.py`: beats.py with `--wpm` from config (hook 3 s or less, no beat over 4 s, no 3
  abstract beats in a row, loop present, target length by video type), humanize.py then detect.py (PASS: overall 70
  or more, no check under 55), zero `{{placeholders}}`, the claims check through the checks model against facts.md,
  one ask and the 3 requirements present; one JSON report per draft.
- `pipeline/bin/vendor-run` (runs a vendored script with `python` and the vendored lexicon paths).
- Activities "writing script (draft 2/2, round 1/3)", "cutting script", "checking script"; the FLAG line.
- Tests: `pipeline/tests/test-m6.sh`, fixtures `pipeline/tests/fixtures/scripts/{good,placeholder,two-asks,
  abstract-run,long-beat}.json`, frozen `07-script/script.json`.

Acceptance test: `bash pipeline/tests/test-m6.sh`
- Unit: each bad fixture fails exactly its check and the good fixture passes every check.
- Real: from the frozen M5 fixtures, script.json validates against the schema (type, display, spoken, emphasis
  words and on-screen card text of 6 words or fewer per beat), passes every check listed above, the cut pass removed
  10 to 30% of the words, two drafts and the pick decision are recorded, no em dash anywhere in the outputs.
- Runtime: 10 to 20 minutes.

## M7 Voiceover (S8)

Depends on: M6 (script.json), tools/voice.py and library/voice/engine.txt (both set up by the user). No model calls.
The PC is CPU-only (integrated GPU, no NVIDIA, no CUDA): every engine runs on CPU, never with device "cuda". When
engine.txt exists, no TTS engine is installed. Without it: kokoro, CPU-only, and its small model weights (once). The
voice is Kokoro's stock af_bella, no cloning. There is no fallback voice or engine: every reel is voiced only with
af_bella.

Creates:
- `pipeline/bin/setup-venv`: installs uv with `python -m pip install uv` when missing, keeps `.venv-tts/` on Python
  3.11 for faster-whisper, soundfile and numpy (no TTS engine, no CUDA libraries); only when engine.txt is missing,
  also creates one virtual environment outside the project with kokoro, CPU-only (torch from the CPU wheel index);
  idempotent; records versions in `pipeline/knowledge/venv-versions.txt`.
- `pipeline/lib/tts/`: `engine.py` (reads library/voice/engine.txt: engine, python, voice, lang, speed and the
  tightening values; the defaults of spec 2.5 when it is missing; calls tools/voice.py's Engine class through the
  engine's own interpreter; kokoro only, no other engine), `synth.py` (pronunciations.txt applied first, as a
  respelling or Kokoro's inline phonemes `[word](/phonemes/)`; beat by beat; tools/voice.py's tighten on each beat,
  pauses of min_pause_s or longer below silence_threshold_db cut to keep_pause_s; beats joined with keep_pause_s,
  breath_after_hook_s after the hook beat; leading silence 0.05s, trailing 0.2s), `align.py` (faster-whisper word
  timestamps on CPU with compute_type int8, on the tightened audio, into words.json with beat ids; nothing is
  tightened after alignment), `wer.py`, `loudness.py` (two-pass ffmpeg loudnorm to -14 LUFS, true peak at most
  -1.5 dBTP, measurement with ffmpeg ebur128).
- `pipeline/stages/08-voiceover/{run.sh,CONTRACT.md,schema.json}`: the one engine of engine.txt, the speakability
  ladder that never switches voice or engine (WER over 3%: the misheard words' pronunciation fixed in this reel's
  spoken text and the line regenerated, then one rewrite of the line through S7 in simpler words and a
  regeneration, then a NEEDS REVIEW flag at 8% or less or a block above 8%), engine crashes and hangs as code errors
  (spec 4.2, then block), the 15% overrun flag, hook 2's voice; outputs vo.wav, vo_hook2.wav, words.json,
  words_hook2.json.
- When engine.txt is missing: the HUMAN_TODO asking the user to write it.
- config.json `tts`: device cpu and the whisper model only (every voice setting comes from engine.txt; the
  chatterbox, turbo and qwen settings and gap_ms are removed); `voice.wpm` set to af_bella's measured pace after
  tightening; `preflight.require` gains engine.txt and its interpreter (exists and imports kokoro in a one-line
  test) and the venv.
- Activities "generating voiceover (beat 4/9)", "tightening silences", "aligning words", "fixing pronunciation (line
  4)", "rewriting line 4".
- Tests: `pipeline/tests/test-m7.sh`, a fake engine for the loop tests, frozen `08-voiceover/` fixtures (words.json
  and the wav files, the wavs kept out of git and regenerated by the test when missing).

Acceptance test: `bash pipeline/tests/test-m7.sh`
- From the frozen script.json: vo.wav and vo_hook2.wav exist (48 kHz, mono); words.json and words_hook2.json validate,
  cover every beat with monotonic timestamps; every line's WER is 3% or under, or the pronunciation fix and rewrite
  path is visible in the stage log; integrated loudness -14 LUFS plus or minus 1 and true peak at most -1.5 dBTP; no
  pause longer than keep_pause_s remains except the hook breath (breath_after_hook_s) and the 0.2s tail; 5
  spot-checked word timestamps line up with the audio; total length within 15% of the script estimate or flagged.
- The preflight checks that engine.txt's interpreter can import kokoro.
- Unit: wer.py on known pairs; with a fake engine that returns garbage, the ladder runs in order and ends in a NEEDS
  REVIEW flag (WER 8% or less) or a block (above 8%), never in another voice or engine; a fake engine that crashes
  goes to the code error path.
- The measured generation speed and af_bella's pace after tightening are recorded in DECISIONS.md.
- Runtime: Kokoro generates a reel in well under a minute on CPU and alignment takes a few minutes, so 5 to 15
  minutes for the test; without engine.txt the installs add 10 to 30 minutes to the first run.

## M8 Sound effects memory map (spec 2.6)

Depends on: M1 (config), M3 (ai for the indexer call). Independent of M4 to M7. The pack is already in styles/sfx/
(106 files: Click, Pop, Swoosh, Free Woosh folders plus loose files).

Creates:
- `pipeline/bin/build-sfx-map` and `pipeline/lib/sfx/{measure.py,classify.py,pools.py,previews.py,
  overrides.py,writemap.py}`: measurements with ffmpeg plus numpy (duration, channels, sample rate, integrated
  LUFS and true peak via ffmpeg ebur128, peak dBFS, noise floor, onset, peak time, attack, tail to -40 dB, spectral
  centroid, silence padding, clipping, decode errors), whoosh speed classes with thresholds tuned on this pack and
  written to DECISIONS.md, the batched indexer call for unclear files (cue types, tags, confidence; low confidence
  stays out until overrides.txt approves it), the normalization gain to a -12 dBFS peak with 48 kHz WAV copies in
  `styles/sfx/.cache/`, the quality filter, pools of 5 to 8 per cue type ranked by fit, the folder hash for rebuilds.
- `styles/sfx/sfx-map.json`, `styles/sfx/SFX-MAP.md` (counts per category, pools, excluded files with reasons),
  `styles/sfx/overrides.txt` (header explaining `ban: path` and `pin: cue type: path`), `styles/sfx/previews/<cue
  type>.wav` plus `.txt` (ignored by git).
- config.json `sfx` section completed (map path, base gain per cue type, thresholds), `preflight.require` gains the
  map.
- Tests: `pipeline/tests/test-m8.sh`, a tiny synthetic pack generated with ffmpeg (a click, a short noise swoosh, a
  long swell, a clipped file) for deterministic unit checks.

Acceptance test: `bash pipeline/tests/test-m8.sh`
- Every audio file under styles/sfx/ (wav, mp3, aif, aiff, ogg, flac) is in the map or in the excluded list with a
  reason; every measured field is present for every mapped file.
- Every one of the 12 cue types has a pool of at least 3 sounds, or build/HUMAN_TODO.md names the short cue types;
  no pool exceeds 8.
- Previews exist with their text listing; the synthetic pack classifies as expected (fast, slow, clipped excluded).
- A rebuild after adding `ban:` for a pooled file drops it and keeps the ban through another rebuild; `pin:` puts
  the file first; an unchanged folder is not re-measured (the rebuild is fast and makes no model call).
- Runtime: a few minutes.

## M9 Motion library

Depends on: M1 (config), M7 fixtures (script.json, vo.wav, words.json for the golden reel), Node 22, network for
npm, Chrome and fonts. The HyperFrames CLI is `npx hyperframes` (package `hyperframes`, pinned version).

Creates:
- `package.json` and `package-lock.json` (hyperframes pinned, puppeteer, gsap if not provided by the HyperFrames
  scaffold), `pipeline/bin/setup-node` (`npm ci`, `npx hyperframes browser ensure`, `npx hyperframes skills update`
  for the builder sessions), `.hyperframes/` ignored.
- `pipeline/bin/build-tokens`, `pipeline/lib/tokens.py`, `styles/paper-cards/tokens.schema.json` and the generated
  `styles/paper-cards/tokens.json`: colors, fonts, type scale, zones, margins, border and shadow sizes, motion
  timings, caption rules, pacing limits, accent cap, transition rules, the tracker switch (off for this look), and the
  source hashes of style.md and tweaks.md; the structured tables are parsed by script, the rest is extracted by the
  checks model into the schema and cross-checked (every hex and every number must appear in the two source files).
  Regenerated whenever either hash changes. In-force tweaks.md lines win over style.md; PROPOSED lines are ignored
  until the user removes the word; the open questions of style.md are decided with the rule in DECISIONS.md and
  written there.
- `motion-lib/`: a HyperFrames project. `index.html` (the gallery root), `compositions/<component>.html` (one
  template sub-composition per component of vocabulary.md, items 1 to 24, with `data-composition-variables` for its
  props, a GSAP timeline registered as `window.__timelines[id]`, tokens.json exposed as CSS variables through a
  generated `tokens.css`), the paper canvas (glows, dot grid), the caption line (chunks of 1 to 4 words, words
  appearing when spoken, accent boxes on emphasis words), one Three.js component through the `hf-seek` protocol for
  the hook and end card 3D objects, `assets/fonts/` (Inter Tight, Instrument Serif, Space Grotesk, JetBrains Mono,
  Caveat as OFL files with `@font-face`), `catalog.json` (per component: name, props and their types, beat types
  allowed by the beat map, sound events with frame offsets, preview still path, frame-match result). For the FlashFX
  branding (spec 2.7, tweaks.md "Branding (FlashFX account)"): a DM notification card component for the CTA (a
  surface card with a round avatar image, the sender name and one message line; vocabulary.md does not list one),
  and an image prop on every logo spot (end card, logo tile, logo badge, kicker mark) taking a path from
  `library/brand/brand.json` or the research assets, aspect ratio locked, never a drawn or recolored logo. No brand
  colors or fonts go into tokens.json.
- `pipeline/bin/frame-match` and `pipeline/lib/framematch.py`: renders each component at 30 fps with
  `npx hyperframes snapshot` and `render --format png-sequence`, measures the element's opacity and position per frame
  through Puppeteer, compares with the numbers in vocabulary.md and `analysis/vXX/measurements.md` (1 frame and 10%
  distance tolerance) and correlates the per-frame change curve with the reference filmstrip of the same move
  (`styles/paper-cards/analysis`); writes `motion-lib/gallery/frame-match.md`. Components that pass live in
  `motion-lib/compositions/`; the others stay in `motion-lib/candidates/`.
- `pipeline/bin/gallery`: `motion-lib/gallery/index.html` that plays each component, plus one still per component.
- `pipeline/stages/09-plan/schema.json`: the merged visual plan schema (scenes, components and props, timings
  snapped to words, entrances and exits, emphasis hits, set pieces, honesty labels, caption chunks, transitions),
  defined here so the golden reel and M10 share it.
- `pipeline/bin/render-golden` and `golden/test-idea/{plan.json,project/,contact-sheet.png,README.md}` (the render
  `golden.mp4` is ignored by git and regenerated by the test): a golden reel planned by hand from the frozen
  script.json and words.json, built from the library, rendered with the frozen vo.wav; its CTA follows the branding
  rules (the FlashFX DM avatar and the lockup).
- HUMAN_TODO lines: review the gallery, review the golden reel, accept or change the open-question defaults.
- Tests: `pipeline/tests/test-m9.sh`.

Acceptance test: `bash pipeline/tests/test-m9.sh`
- tokens.json validates against its schema, every color and number in it appears in style.md or tweaks.md, the
  tracker switch is off, a rebuild with unchanged sources is a no-op and a touched tweaks.md triggers one.
- `npx hyperframes lint` and `npx hyperframes check --json` pass on motion-lib/; catalog.json lists every component
  of vocabulary.md items 1 to 24 with props, beat types and sound events, plus the DM notification card; every
  component renders a still; every logo spot takes an image path and keeps its aspect ratio.
- frame-match.md shows a pass for every component in `motion-lib/compositions/` and lists the candidates that failed
  with their numbers; the gallery page exists with one still per component.
- golden/test-idea/plan.json validates against the plan schema; golden.mp4 renders at 1080x1920, 30 fps, with a
  duration within 0.2 s of vo.wav; the contact sheet exists.
- Runtime: 20 to 40 minutes (renders).

## M10 Visual stages (S9, S10)

Depends on: M9 (library, tokens, plan schema, golden), M7 fixtures (words.json, vo.wav), M4 fixtures (assets).

Creates:
- `pipeline/stages/09a-animations/`, `09b-text/`, `09c-transitions/` (each with run.sh, prompt.md, CONTRACT.md,
  schema.json): fresh visual_director sessions with the shared inputs of spec S9 (script.json, words.json, style.md,
  tweaks.md, tokens.json, vocabulary.md, catalog.json with stills, the golden plan and contact sheet, the research
  assets); one validator retry with the errors, then the review path.
- `pipeline/lib/plan_merge.py` and `pipeline/lib/plan_validate.py`: the merged plan and every rule of spec S9
  (first visual change before the style's limit, maximum gap, minimum distinct components, no component 3 times in a
  row, beat types to allowed components, caption chunk rules, text zones, words per card, real assets only for real
  claims, branding), all thresholds read from tokens.json and catalog.json.
- Branding in 9a (spec S9, tweaks.md "Branding (FlashFX account)"): the CTA always gets the FlashFX DM card avatar
  (`mark/avatar-dark.png`) and the lockup; FlashFX logos elsewhere only when `02-expansion/solution.json` says
  flashfx (a run without it counts as not FlashFX, since S2 writes it from M12 on); the brand slot (the kicker mark,
  logo tiles and badges, as the look has no tracker) shows the FlashFX bolt, the tool's logo from the research
  assets, or a neutral icon; every logo path comes from `library/brand/brand.json` with a use_on matching its
  surface. In S10 logos are image files with their aspect ratio locked and no effects. The preflight gains
  brand.json and every file it lists.
- `pipeline/stages/10-build/{run.sh,prompt.md,CONTRACT.md,schema.json}`: the builder model (Opus, Fable for
  3D-heavy plans or after 2 failed review rounds) writes `10-build/project/` (a HyperFrames project that mounts
  library components with the plan's props, the caption line, tokens as CSS variables, Three.js only where the style
  allows), `npx hyperframes lint` and `check --json` must pass, `pipeline/lib/events.py` exports `events.json`
  (every declared sound event in absolute ms with type, component, scene, scene-change flag and transition
  duration, computed from `npx hyperframes timeline --json` and catalog.json), the hook 2 alternate clip project
  (`10-build/hook2/`, 3.5 s at most), the silent draft render `draft.mp4` at 540x960 (`render.draft_resolution`:
  half resolution, same timing and fps; 1080x1920 only in S13), candidates in
  `motion-lib/candidates/` with a NEEDS REVIEW flag when the plan needs a missing component.
- `pipeline/bin/contact-sheet` (one still per beat with ffmpeg).
- Activities "planning animations", "planning text", "planning transitions", "validating plan", "building visuals",
  "rendering draft".
- Tests: `pipeline/tests/test-m10.sh`, validator fixtures (one failing plan per rule, one good plan), frozen
  `09a/09b/09c` plans, `10-build/events.json` and the project folder.

Acceptance test: `bash pipeline/tests/test-m10.sh`
- Unit: every validator rule fails its fixture and the good plan passes.
- Real, from the frozen script and words: the three plan.json files validate against their schemas and the merged
  plan passes the validator; `check --json` passes on the built project; draft.mp4 is 540x960 at 30 fps with no
  audio stream and a duration within 0.2 s of vo.wav; the hook 2 clip renders at 3.5 s or less; events.json validates
  and matches what is on screen: for every scene change and every stamp, typing and count event, a Puppeteer seek one
  frame before and one frame after the event time shows the element's state change.
- Branding, with fixture solution.json files (flashfx and external): both CTAs have the FlashFX DM avatar and the
  lockup; FlashFX logos in the body and the brand slot only in the flashfx reel, the tool's logo or a neutral icon in
  the other; every logo path is in brand.json with a use_on matching its surface; every logo is an image with its
  aspect ratio locked.
- Runtime: 20 to 40 minutes.

## M11 Sound effects pass and review loop (S11, S12)

Depends on: M8 (map), M10 (project, draft, events.json), M7 (vo.wav), tools/analyze_refs.py.

Creates:
- `pipeline/bin/mix-sfx` and `pipeline/lib/sfx/{assign.py,pick.py,place.py,level.py,render_stem.py,verify.py}`:
  cue assignment with the deterministic rules of spec S11 (mandatory cues, scene changes slow or fast, hero and
  ui_click, attention gaps, density and spacing, the trimming priority), seeded per reel; pool rotation with
  `logs/sfx-usage.json`; placement (peak time on the event for whooshes, onset for the rest, typing trimmed, 30 ms
  fades); levels (map gain plus cue base gain, 8 dB under the local voice peak); the stem and the mix with ffmpeg;
  verification by onset detection (every planned sound within 33 ms, no unplanned sound) and loudness (-14 LUFS plus
  or minus 1, true peak at most -1.5 dBTP, the 8 dB rule), automatic correction and re-check.
- `pipeline/stages/11-sfx/{run.sh,CONTRACT.md,schema.json}`: cues.json, sfx_stem.wav, draft_mixed.mp4,
  sound-map.txt; voice-only with a NEEDS REVIEW flag when the map is missing or empty.
- `pipeline/stages/12-review/{run.sh,prompt-edit-review.md,CONTRACT.md,schema.json}` and
  `pipeline/lib/review/{mechanical.mjs,style_check.py,audio_check.py,route.py}` (every pixel-based check scaled to
  the 540x960 draft): Puppeteer checks at every beat and emphasis time (zones with the caption band exception, the
  right 230 px of the lower half, fonts and minimum sizes, overlaps, off-canvas, contrast 4.5:1, emphasis within
  80 ms, and the branding checks of spec S12: the CTA's lockup at least 300 px wide and the DM avatar, no FlashFX
  logo outside the CTA unless the solution is FlashFX, the variant matching the surface's luminance, aspect ratio,
  bolt at least 64 px, avatar at least 112 px, clear space a quarter of the bolt's height); style conformance by
  running tools/analyze_refs.py on draft_mixed.mp4 and comparing cadence, token colors (90% of non-image pixels within
  delta E 5, logos counted as image pixels), accent share (logos excluded) and loudness against
  styles/paper-cards/analysis and tokens.json; audio checks (S11 verification plus a transcription of the mix with
  WER under 5%); the edit review by a fresh qa session (contact sheet, 10 fps filmstrips of the hook and transitions,
  look-reference stills, sound-map.txt next to the scene list; scores 1 to 5 on the eight criteria, tagged issues; it
  also flags branding that feels like an ad); fix routing to S8, 9a, 9b, 9c or S11 and the re-run of every later
  step; caps (3 Opus rounds, 2 Fable rounds, then export with NEEDS REVIEW).
- `pipeline/bin/filmstrip`.
- Activities "adding sound effects (14 sounds)", "verifying sound sync and loudness", "reviewing: mechanical
  checks", "reviewing: style check", "reviewing: edit review (round 1/5)", "fixing [text] issues (round 2, opus)".
- Tests: `pipeline/tests/test-m11.sh`, a planted [text] issue fixture (a caption chunk placed outside its zone in a
  copy of the frozen 9b plan), a fake qa verdict that always fails for the cap test, frozen `11-sfx/` outputs.

Acceptance test: `bash pipeline/tests/test-m11.sh`
- On the frozen draft: cues.json validates; every mandatory cue present for the events that exist; density, spacing,
  first-word and ask rules hold; onset detection finds every planned sound within 33 ms of its event and no extra
  sound; every sfx peak sits at least 8 dB under the local voice peak; the mix measures -14 LUFS plus or minus 1 and at
  most -1.5 dBTP; sound-map.txt has one line per cue.
- The mechanical, style and audio checks run and write their JSON reports; the edit review runs and returns scores
  and tagged issues.
- The planted [text] issue is detected, routed to 9b, and 10, 11 and 12 run again (state.json and the log show the
  second pass and the "fixing [text] issues" activity).
- With the always-failing fake qa: 3 Opus rounds, 2 Fable rounds, then the run continues to export with the NEEDS
  REVIEW flag and the review notes.
- The branding checks pass on the frozen draft, and each planted branding fault is caught: a FlashFX logo in the
  body of a non-FlashFX reel, a black lockup on ink, a stretched logo, a lockup under 300 px, a CTA without the DM
  avatar.
- Runtime: 20 to 40 minutes.

## M12 Final render, caption, export, end to end (S13, S14)

Depends on: M11 and everything before it.

Creates:
- `pipeline/stages/13-render/{run.sh,CONTRACT.md,schema.json}`: the final HyperFrames render with the approved mix
  (voice and sfx stem as `<audio>` clips), ffprobe checks (duration equal to the voice within 0.2 s, 1080x1920, 30
  fps, H.264 High, yuv420p, AAC 48 kHz, audio present, loudness), an ffmpeg post-pass only when a container detail
  differs (audio re-encode to AAC 48 kHz, profile), the same for the hook 2 clip with its voice and sounds.
- `pipeline/stages/14-export/{run.sh,prompt-caption.md,CONTRACT.md,schema.json}`: the caption from brief.md and
  script.json (first line the hook in 125 characters or fewer, one ask, at most 5 hashtags), caption.py lint and
  humanize.py, `Ncaptions.txt` in the exact format of spec section 8 (NEEDS REVIEW only when flagged), the export
  through M2's export.sh (assemble, number, move in one step, delete the idea, history line).
- `run.sh` wired end to end with the real stages as the default (`REELS_DUMMY` unset).
- Activities "rendering final video", "rendering hook 2 clip", "writing caption", "exporting #7"; the DONE line.
- Problem-first reels (spec section 0, S1 to S4, S7, S14), retrofitted into the stages of M4 and M6: S1's solution
  candidates in facts.md; S2's solution decision with its reason in expansion.md and `02-expansion/solution.json`
  (type flashfx, external or method, name, url, reason), chosen by account.md's content strategy and the recent
  solution types in logs/history.txt, with the keyword that follows it (FLASH, LINK, or the deliverable that fits);
  S3's honesty check H (the solution solves the problem, FlashFX not forced; a fail goes to S4 inside the 2 angle
  rounds, never a drop); S4's new pick; S7's and the caption's solution rules (no FlashFX mention unless chosen, no
  ad language, never implying the reel was made in FlashFX) as checks; the SOLUTION block in Ncaptions.txt;
  history.sh lines with the solution type (`date | idea | solution | exported N`, `-` before S2).
- Tests: `pipeline/tests/test-m12.sh`.

Acceptance test: `bash pipeline/tests/test-m12.sh`
- In a sandbox with the test idea in ideas.txt, `bash run.sh --once` runs every real stage from scratch and produces
  `exports/1/1.mp4`, `exports/1/1captions.txt` and `exports/1/1hook2.mp4`.
- ffprobe: 1080x1920, 30 fps, h264 High profile, yuv420p, aac at 48000 Hz, duration equal to vo.wav within 0.2 s;
  loudness -14 LUFS plus or minus 1 and true peak at most -1.5 dBTP; the hook 2 clip is 3.5 s or shorter with audio.
- 1captions.txt has the sections CAPTION, HASHTAGS (5 or fewer), COMMENT KEYWORD, SOLUTION, HOOKS, FACTS AND
  SOURCES and RUN in order, NEEDS REVIEW only when state.json has flags, the first line is hook 1 and is 125
  characters or fewer, caption.py reports no FAIL, no em dash anywhere.
- The idea is gone from ideas.txt, history.txt has its exported line with the solution type, the run folder is kept.
- With the fake claude: an idea with a forced FlashFX solution fails H, goes to S4 and comes back with another
  solution (never dropped for it); with a non-FlashFX solution, script.json and the caption never mention FlashFX.
- Runtime: 1 to 3 hours (the full pipeline, CPU voice, real reviews).

## M13 Hardening

Depends on: M12.

Creates:
- Fault injection in ai.sh (`REELS_FAULT=limit:<stage>` makes the next call in that stage return a session-limit
  message once, with a reset time a few minutes ahead, so a real run meets a simulated limit), `REELS_FAULT=kill:<stage>`
  for the restart test.
- `pipeline/bin/doctor` (versions, disk, venv, node packages, map and tokens freshness, last status, blocked and
  STOPPED summaries), log rotation for logs/runner.log at 50 MB, the final pass over every status line of spec
  sections 6 and 7 against a real multi-idea run, fixes for everything the long run surfaces, cleanup of
  known-issues.md, DECISIONS.md and CLAUDE.md.
- `pipeline/bin/build-voice-profile --force` keeps the hand-written sections of account.md and voice.md (spec 2.3:
  Brand, Content strategy, How I promote, the FlashFX spelling line) and refills only the generated parts; tested on
  a copy of the profile.
- `pipeline/tests/fixtures/ideas/three-ideas.txt` (three distinct ideas on tools the research can verify),
  `pipeline/tests/test-m13.sh`.

Acceptance test: `bash pipeline/tests/test-m13.sh`
- In a sandbox with three ideas, `bash run.sh --once` runs unattended to the end: every idea ends exported, dropped
  or blocked with a reason, never with a crash or a hang; the exports are numbered without gaps.
- A simulated limit injected during the second idea is handled: the LIMIT line names the reset time, limits.log has
  the target, the RESUME line follows, and the same session continues (fast-forward wait).
- The runner is killed during the second idea and restarted; it resumes the same stage.
- runner.log tells the full story: banner, START, STEP per stage, GATE, DONE or DROP or BLOCK, NEXT, the heartbeat
  lines with correct counters, IDLE and the summary at the end; status.txt is valid at every sampled moment; no em
  dash in any export or log.
- Runtime: several hours.

## M14 Motion grammar and energy meter (spec section 5, Motion and energy rules E0, E1, E2, E5, E6, E7)

Depends on: M9 (the motion library, tokens, frame-match, the gallery, webgl.json), M13 (a real reel to measure:
build/M13/rerun/1.mp4), the style's reference videos in styles/paper-cards/refs/.

Creates:
- `pipeline/lib/review/energy.py` and the `energy` command of `python pipeline/lib/review`: 30 fps, 108x192 grayscale,
  the per-frame mean change, frozen, subtle, medium and big frames, the moving share, the middle band, the pixels
  changing per frame, the still stretches, whole reel and per scene (scene times from a merged plan);
  `styles/paper-cards/analysis/energy.json` (the nine references measured; the look references' median).
- `pipeline/lib/tokens.py`: tokens.json `motion` (phase durations, eases, hold speeds, 3D angles and perspective, the
  edge layer, the caption fonts and ratios for M15) and `energy` (70% of the look references' median), tweaks.md
  overrides; motion-lib/assets/tokens.css.
- `motion-lib/assets/pc-motion.js`: main animation, inertia, hold (calm, normal, lively), exit; combined main
  animations (zoom, 3D parallax rotation, move; power3 or power4 in-out; the rotation 2 to 4 frames late; the
  decelerating tail that never reaches zero); the 2.5D scene container and its camera. Every component in
  motion-lib/compositions/ rewritten on it.
- paper-canvas: the edge filler layer (elements 30 to 70% outside the frame, at most 20 px per second, no text) and the
  ambient layer (stars, dots, small clouds); the mascot's idle.
- `motion-lib/compositions/icon-3d.html` (Three.js, low poly, extruded SVG and primitives, on webgl.json's backend)
  with its CSS-extruded fallback.
- frame-match: the main animation against the references as before, plus an inertia and hold check; the gallery with
  each component's energy; golden.mp4 rendered again from the same plan.
- Tests: `pipeline/tests/test-m14.sh`.

Acceptance test: `bash pipeline/tests/test-m14.sh`
- energy.py reproduces energy.json within 1 point and fails the M13 reel on every target.
- Every component, rendered alone for 4 s: never static for 0.5 s, its main animation still frame-matches, its inertia
  lasts 2 to 4 s.
- icon-3d renders with WebGL and with the fallback; the edge and ambient layers stay out of every text zone.
- The re-rendered golden reel beats its old numbers on every measure, its moving share at least doubled.
- The fake-only tests of M9 to M13 still pass.
- Runtime: 30 to 60 minutes (renders).

## M15 Kinetic captions and text discipline (spec section 5, Motion and energy rules E3, E4)

Depends on: M14 (pc-motion.js, tokens `motion`), M10 (9b and the plan schema), M6 (script.json), M7 (words.json).

Creates:
- `motion-lib/compositions/caption-word.html` and `caption-group.html` on pc-motion.js (caption-line retired from the
  catalog).
- `pipeline/lib/visual/kinetic.py`: the group layout engine (roles, at least 3 fonts, the anchor at 2 to 3 times the
  caption size, the stacked lines matching the anchor's height, asymmetry, the group caption zone, the right rail).
- S7: each beat's importance in script.json; 9b: the caption mode per beat, the group's words, anchor and layout; the
  plan schema fields; the validator and S12 mechanical rules of E4 and "no caption static".
- Tests: `pipeline/tests/test-m15.sh`, kinetic.py fixtures, planted-fault plans.

Acceptance test: `bash pipeline/tests/test-m15.sh`
- "the quick brown fox" lays out as spec E3 (three fonts, "quick" and "brown" at half the anchor's size with their
  combined height equal to the anchor's within 2 px, asymmetric, inside the zone); 6 long words fit or split; no group
  word below the caption size.
- On the golden plan: word mode in normal talk, groups on the important beats, every caption word moving on every frame.
- The planted faults are caught: 120 characters on a card, a 40 px label, a group caption over a text card, a static
  caption word.
- The fake-only tests of M9 to M14 still pass.
- Runtime: 20 to 40 minutes.

## M16 Director, components and the energy loop (spec section 5, Motion and energy rules E8, E9)

Depends on: M14, M15, M12 (the whole pipeline for the real test run), M11 (S12).

Creates:
- New components on pc-motion.js: screenshot-zoom (pan, zoom, highlight box), card-fan, card-grid, video-card,
  timeline-scrubber, cursor, mock-site-card, swatch-row and swatch-card; their catalog entries, beat map lines and
  gallery stills; frame-match where a reference exists.
- S1: the page recordings (Playwright, 5 to 8 s scroll, 1080 wide) next to the screenshots; assets.json lists them.
- The 9a, 9b and 9c prompts around the Motion and energy rules; the validator rules of E9 (a moving element in every
  scene's hero zone, the fill, the layers, the camera frequency, transition variety, the hook's frame 0).
- A new golden reel (golden/test-idea/) meeting every energy target, with a HUMAN_TODO to review it.
- S12: the energy check first, per-scene routing to 9a, the "no element static" and edge checks, the energy score in
  the edit review, the early stop.
- Tests: `pipeline/tests/test-m16.sh`, one failing fixture plan per new rule, a fake qa that repeats its verdict.

Acceptance test: `bash pipeline/tests/test-m16.sh`
- The new golden reel meets every energy target, every scene at least 80% of each target.
- Each new validator rule fails its fixture; the golden plan passes.
- The test idea from scratch with the real models gives a reel that meets the targets (or exports after the loop with
  its numbers in NEEDS REVIEW), with edit review scores on stopping the scroll, motion variety and nothing generic
  above the M13 reel's 3.
- The early stop fires on the repeating fake qa; the fake-only tests of M9 to M15 still pass; the time per reel grows
  by at most 20%.
- Runtime: 2 to 4 hours (one real reel, renders).

## M17 Editable project export (spec S15)

Depends on: M16 (the motion and caption components the project mirrors), M12 (the export, the final composition,
cues.json, words.json), M13 (the hardened runner loop), M9 (the motion-lib components to annotate), the editor repo at /c/Users/there/OneDrive/Desktop/editor (config.json
`editor.repo`; read only) and its stable copy next to it (`editor.stable_dir`, created by editor-stable.sh), Node 22
and the Puppeteer harness of M11. S15 and every spec line marked (M17) are built and reviewed here only.

Creates:
- `pipeline/stages/s15-project/` (run.sh, CONTRACT.md, schema files): the capture (`capture.mjs`: Puppeteer seeks
  every frame of the final composition, reads the `data-ed-layer` tree, border quads through `DOM.getBoxModel`,
  `getScreenCTM()` with `getBBox()` for SVG, opacity products, look signatures and clipped screenshots for canvas,
  video and animated SVG; writes `15-project/layers.json`), the mapping to native, sprite, overlay or plate by the
  manifest (keyframe reduction within 0.25 px, 0.1 degree, 0.002 scale and 0.004 opacity, eases from the manifest,
  hold keys for jumps; groups as compound, parented or flattened; native text only with an available font and
  supported fill, stroke, shadow and background; captions native or baked plus the hidden caption track; `fallbackOf`
  stand-ins when the manifest allows), sprite, overlay (VP9 alpha WebM, PNG sequence or animated WebP with the 33,
  33, 34 ms frame rule, split by the texture budget) and plate rendering, the audio clips from vo.wav and cues.json
  with the master gain folded in (48 kHz WAV), the writer (project.json at the manifest's schemaVersion, media/,
  fonts/ with fonts.json version 2, layers.json, FALLBACKS.md, OPEN.txt; readable names, label colors, bins,
  markers, `meta.generator`), the S15 validator (every rule of the editor's validate.ts and every field of
  types.ts), the parity check (editor CLI render and compare when the manifest has them) and the layout check
  (sprites, overlays and plates composited in the harness, SSIM at least 0.95 per scene; native text measured with
  Canvas2D within 2 px), the 25-minute cap and the minimal project or FAILED.md on failure.
- `pipeline/stages/s15-project/baseline-capabilities.json` (the editor v1.1.0 manifest of spec S15, verbatim) and
  `CAPABILITIES.md` (every manifest key S15 knows: mapped or not, and which reel elements use it).
- `pipeline/bin/editor-stable.sh`: clone `editor.repo` into `editor.stable_dir` on first use; advance at most once an
  hour to the newest `batch-NN: review` commit whose docs/PROGRESS.md has `in_progress_batch: none` and an accepted
  last review for its `last_completed_batch` (detached checkout, `npm ci` when package-lock.json changed,
  `npm run build`, `npm run build:cli` when present; back to the previous commit on failure, with the reason logged);
  the server (`npx vite preview --port 5310 --strictPort`).
- `pipeline/bin/rebuild-project.sh N`: rebuilds exports/N/project/ from its run folder with the current manifest,
  keeping an edited project aside as project.edited-<date>/.
- `run.sh` and `pipeline/lib/runner.sh`, between ideas only: advance the stable copy, keep its server on port 5310
  running (restart after an advance), and the capability upgrade of spec S15 step 8 (a builder session, a reviewer
  session, at most 2 fix rounds, commit `s15: editor capabilities <keys>` or a full revert recorded in
  logs/editor-upgrade.json with a 24-hour retry rule; the upgrade shown in logs/status.txt).
- S14's export calls S15 after assembling `runs/<id>/export/` and before the move; the EDITOR section in
  Ncaptions.txt; logs/editor-gaps.md (one line per missing manifest key, with a running count, the reel elements and
  the latest reel, sorted by count); logs/editor-capabilities.json.
- Editor annotations (`data-ed-layer`, `data-ed-name`, `data-ed-kind`) on every motion-lib component and in the
  builder's rules for new candidates, without changing how anything looks.
- cues.json gains the trim in and out points, the fade-out and the final gain of each sound (S11's sound unchanged).
- config.json `editor` block: repo, stable_dir, port 5310, url, projects_root, project true, cap_minutes 25,
  parity_ssim 0.97.
- Mappings for §21.7 and §21.8 of the editor's docs/PLAN_V1_2.md, used only when the manifest announces them; skipped
  when that file is not in the editor repo (it was not on 2026-11-02), and the capability upgrade adds them later.
- Tests: `pipeline/tests/test-m14.sh`, `pipeline/tests/manifest-plus.json` (the baseline plus the Batch 58 and 59
  keys of the editor plan), a golden project JSON, a scratch git repo with fake `batch-NN: review` commits.

Acceptance test: `bash pipeline/tests/test-m14.sh`
- The golden reel (or the test idea) gives exports/K/project/ that passes validation (the editor CLI when the manifest
  has cli.validate, otherwise the S15 validator), with FALLBACKS.md, OPEN.txt and the EDITOR section.
- With the baseline manifest: the background, the voice and every sound effect are native clips at the right times;
  every text whose style the baseline supports is a native text clip; the captions are baked, plus the hidden native
  caption track; the layout check passes.
- With manifest-plus.json the cards become native solids and the captions native cues (the JSON matches the golden
  file); with the baseline again they go back to sprites and baked captions.
- The animated WebP timing test: every timeline frame of a 90-frame overlay shows its own WebP frame under the
  editor's frame rule.
- The stable copy, in the scratch repo: it advances only to a `batch-NN: review` commit whose batch is accepted, a
  failing build puts it back on the previous commit, and the server answers on port 5310.
- The project lasts as long as N.mp4 within 1 frame, and its mix is within 0.5 LU of N.mp4.
- A forced failure still exports N.mp4, with the minimal project and NEEDS REVIEW.
- rebuild-project.sh rebuilds a project and keeps an edited one aside.
- In the runner's fast test mode, a changed manifest between two dummy ideas triggers exactly one capability upgrade
  (dummy sessions) with its status line; a failed upgrade is not retried for the same manifest.
- S15 takes at most 15 minutes for a 60-second reel on this laptop (the time goes in build/progress.md).
- Runtime: 1 to 2 hours (renders, the capture of every frame).

## Dependency graph

```
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M10 -> M11 -> M12 -> M13 -> M14 -> M15 -> M16 -> M17
                    \-> M8 ------------------------/
                    \-> M9 (needs M7 fixtures) ---/
```

M8 could run any time after M3, M9 any time after M7; the runner builds them in numeric order anyway.

## Risks and how the plan handles them

- The repo lives inside a OneDrive-synced folder: runs/ and exports/ will grow to gigabytes and OneDrive can hold
  file handles during renames. Every mv in the runner retries briefly; a HUMAN_TODO asks to exclude the folder from
  sync.
- CPU-only PC (integrated GPU, no NVIDIA, no CUDA): Kokoro and faster-whisper run on CPU (Kokoro is fast, alignment
  takes a few minutes per reel), and renders are slow. Acceptable for an unattended runner: drafts render at
  540x960, every step has a generous timeout and prints progress, and the engine choice is the user's, in
  library/voice/engine.txt.
- Python version split: the TTS engine runs in the user's own virtual environment (engine.txt), faster-whisper in
  `.venv-tts` (3.11 via uv), everything else on the system 3.13.
- Single voice: no fallback voice or engine, so a reel af_bella cannot speak cleanly (after the pronunciation fix
  and one rewrite) is flagged (WER 8% or less) or blocked, never voiced with something else.
- HyperFrames moves fast (0.8.x): the version is pinned in package.json and upgraded only by hand.
- Style conflicts: style.md version 2 (no tracker, bare captions) wins over the spec's examples that mention a
  tracker; the plan schema keeps an optional tracker field for other styles.
