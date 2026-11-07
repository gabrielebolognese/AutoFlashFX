# instagramReels

An unattended pipeline that turns a short video idea into a finished Instagram reel: research, expansion, hooks,
script, voiceover, visuals written as code (HyperFrames motion graphics, never AI video), sound effects, review,
render, export. The full spec is BUILD_SPEC.md; the build plan is PLAN.md; choices are in DECISIONS.md.

## Build status
- M13 Hardening: done (2026-11-02). Next: M14 Motion grammar and energy meter, M15 Kinetic captions and text
  discipline, M16 Director, components and the energy loop (BUILD_SPEC.md section 5, Motion and energy rules), then
  M17 Editable project export (S15): pending. The build is driven by `bash build-runner.sh` (`--until M16` stops
  after M16); its log is build/build.log and its per-milestone reports are in build/M<n>/.
- What exists: config.json, ideas.txt, the queue library (pipeline/lib/ideas.py and ideas.sh), add-idea.sh, the
  preflight (with the `voice` check: engine.txt's interpreter imports kokoro, one interpreter imports
  faster_whisper), the runner loop (run.sh with pipeline/lib/runner.sh, state.py, status.sh, export.py,
  history.sh), one folder per stage under pipeline/stages/ with CONTRACT.md, schema.json and dummy.sh,
  pipeline/bin/runner-status, the error system (pipeline/lib/ai.sh for every model call, limits.py and limits.sh
  for usage limits, errors.py for the classifier, review.sh with pipeline/bin/review-cycle for the reviewer and
  fixer loop, the prompts in pipeline/stages/_prompts/, pipeline/knowledge/known-issues.md), the tests in
  pipeline/tests/ (with a fake claude and fake voice workers in tests/fakes/), the real stages S1 to S8
  (pipeline/stages/01-research, 02-expansion, 03-gate, 04-angle, 05-hooks, 06-judge, 07-script, 08-voiceover:
  run.sh, prompt*.md where a model is called, model schemas, schema.json for the stage's file) on the shared stage
  library pipeline/lib/stage.sh, session.sh (session A, reseeded when lost or when no id is stored), prompt.py,
  research.py, expansion.py, gate.py, hooks.py (the hooks index, lint, stats, shortlist and checks), judge.py
  (hookscore filter, Borda, pairwise), script_checks.py (the script stage: the plan, the drafts, the cut, every
  check, the claims merge, the pick, script.json, S8's one-line rewrite), voiceover.py (the voiceover stage:
  engine.txt, pronunciations, the word error rate, the ladder, the assembly, loudness, words.json) with the
  workers pipeline/lib/tts/kokoro_worker.py (Kokoro through tools/voice.py, under engine.txt's interpreter) and
  whisper_worker.py (faster-whisper, CPU int8), voiceprofile.py, pipeline/bin/screenshot (Playwright, headless
  Chromium), pipeline/bin/index-hooks (library/.hooks.index.json, hooks.lint.txt, .hooks.stats.json,
  hooks.suggested.txt), pipeline/bin/build-voice-profile (library/profile/voice.md and account.md),
  pipeline/bin/build-sfx-map with pipeline/lib/sfx/ (the sound effects memory map of styles/sfx/: measure.py,
  classify.py, overrides.py, pools.py, previews.py, writemap.py, sfxmap.py; it writes styles/sfx/sfx-map.json,
  SFX-MAP.md, overrides.txt once, previews/ and .cache/; the indexer prompt _prompts/classify-sfx.md; a no-op
  when the folder, overrides.txt and the settings are unchanged, so S11 can run it at every start),
  pipeline/bin/setup-venv (the whisper venv or the kokoro venv when one is missing; `--check` only reports),
  the motion library of M9: pipeline/bin/build-tokens (styles/paper-cards/tokens.json and motion-lib/assets/tokens.css
  from style.md plus tweaks.md, pipeline/lib/tokens.py), motion-lib/ (a HyperFrames project: compositions/<id>.html for
  the 24 vocabulary items plus paper-canvas, dm-card and hero-3d, assets/, catalog.json, the showreel index.html,
  gallery/ with the stills, the players, index.html and frame-match.md, webgl.json), the tools under
  pipeline/lib/motion/ run as `python pipeline/lib/motion <command>` behind pipeline/bin/frame-match, gallery,
  webgl-test and render-golden (golden/test-idea/: plan.json, project/, contact-sheet.png, README.md; golden.mp4 is
  rebuilt), the merged plan schema pipeline/stages/09-plan/schema.json, package.json with the pinned hyperframes,
  gsap and three (pipeline/bin/setup-node),
  pipeline/bin/vendor-run and the vendored instagram-agent-skill scripts in pipeline/vendor/ig-agent-skill/ (MIT,
  pinned in its VERSION file; beats.py, humanize.py and detect.py are also imported as modules by
  script_checks.py), the visual stages of M10: S9a, S9b, S9c (pipeline/stages/09a-animations, 09b-text,
  09c-transitions: run.sh over the shared pipeline/lib/visual.sh, prompt.md, model.schema.json, schema.json generated
  from pipeline/stages/09-plan/schema.json by pass-schemas.py) and S10 (pipeline/stages/10-build: run.sh, prompt.md
  for the builder's repair call, schema.json) on the package pipeline/lib/visual/ (run as `python pipeline/lib/visual
  <command>`: digest, animations, text, transitions, merge, validate, build, events, contact-sheet; common.py the
  timeline, text widths and footprints, plan9.py the three compositions, plan_merge.py, plan_validate.py the 19 named
  rules, project.py the compile, check, draft render, hook 2 clip and contact sheet, events.py the events read from the
  mounted components and verified on screen), pipeline/bin/contact-sheet, the preflight check `brand` (brand.json and
  every file it lists), the sound pass of M11: S11 (pipeline/stages/11-sfx/run.sh over pipeline/lib/sfx/assign.py the
  cue rules, pick.py the pool rotation with logs/sfx-usage.json, place.py, level.py, render_stem.py, verify.py,
  audioio.py, mixsfx.py the orchestrator; pipeline/bin/mix-sfx runs it by hand), the review loop of M11: S12
  (pipeline/stages/12-review/run.sh, prompt.md and model.schema.json for the qa editor, over the package
  pipeline/lib/review/: `python pipeline/lib/review <command>`: mechanical (the built composition opened host by host in
  the Playwright harness: zones, the right rail, fonts, overlaps, contrast, emphasis timing, the branding rules), style
  (tools/analyze_refs.py on the mixed draft against styles/paper-cards/analysis: cadence, token colors, accent share,
  loudness), audio (S11's verification, the voice transcribed from the mix, WER under 5 percent), filmstrips, prompt,
  verdict and feedback (route.py: pass when every check passes and every score is at least 4, else each tagged issue
  back to its owner through reopen.txt, every later stage again, 3 opus rounds then 2 fable rounds, then the export with
  NEEDS REVIEW), the review notes the re-run passes read ({{REVIEW}} in the director prompts, S8's respelling of a quoted
  word, S11's fewer and softer sounds), pipeline/tests/materialize-project.py (the frozen project folders rebuilt from
  the plans), M12: the problem-first solution (pipeline/lib/solution.py: S1's solution candidates, S2's decision and
  keyword in 02-expansion/solution.json, S3's honesty check H, S4's new pick, S7's and the caption's FlashFX rules, the
  SOLUTION block, the solution type in history lines), S13 (pipeline/stages/13-render/run.sh over
  pipeline/lib/finalrender.py: HyperFrames renders 1080x1920 silent, ffmpeg muxes 11-sfx/mix.wav as AAC 48 kHz, ffprobe
  and loudnorm checks, one post-pass) and S14 (pipeline/stages/14-export/run.sh, prompt-caption.md, model.schema.json over
  pipeline/lib/caption.py: hook 1 as the first line, the model's body, ask and hashtags, the checks, humanize.py and the
  vendor caption.py lint, export.json; the runner's export.py then writes exports/N/), M13: the fault injection in
  ai.sh (`REELS_FAULT=limit:<stage>[@n]` makes that stage's next call a CLI-shaped session limit once,
  `REELS_FAULT=kill:<stage>[@n]` kills the runner and the stage there; logs/.faults/ remembers what fired;
  `REELS_FAULT_WAIT=fast` fast-forwards the injected wait; never set in normal use), the rotation of logs/runner.log
  at 50 MB (config logs.rotate_mb and rotate_keep: runner.log.1 to .3), status.txt written aside and renamed (a reader
  may find it missing for a moment, never empty), pipeline/lib/logcheck.py (checks a status line, status.txt, a
  sampler file and the whole story of runner.log against spec sections 6 and 7, the activity table included),
  pipeline/bin/doctor (read-only health report), build-voice-profile --force keeping the hand-written parts of the
  profile (voiceprofile.py merge_keep), S8 and S12 passing the reel's names to faster-whisper as hotwords (DECISIONS.md
  283; S8 also accepts "130" heard for "one thirty", S7's rewrite refuses a respelled name, S7's share-identity check
  compares word stems, 09b checks the zones rule, S8 accepts more transcription spellings: DECISIONS.md 284 to
  287), pipeline/tests/m13-run.sh (the three-idea driver) and pipeline/tests/fixtures/ideas/three-ideas.txt. Run every
  test with `bash pipeline/tests/run-all.sh` (about 2.5 hours plus test-m12 section 4, the whole pipeline on the test
  idea with the real models, 1 to 3 hours, and test-m13 section 3, three ideas with the real models, several hours;
  test-m3 section 4, test-m4
  sections 3 and 4, test-m5 sections 3 and 4, test-m6 section 3, test-m7 section 3, test-m10 section 3 and test-m11
  section 4 make real model or engine calls, test-m8 and test-m9 make none, test-m9 takes about 8 minutes, test-m10
  about 25 minutes, test-m11 about 40 minutes; `M7_SECTIONS="1 2" bash pipeline/tests/test-m7.sh`,
  `M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh`, `M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh` and
  `M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh` and `M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh`
  (about 20 minutes) are the fake-only tests).
- Every stage is real from M12 on: `bash run.sh` turns each idea into exports/N/ (N.mp4, Ncaptions.txt, Nhook2.mp4).
  `REELS_DUMMY=all bash run.sh --once` runs the whole loop with dummy stages; `REELS_DUMMY=13,14 bash run.sh --once`
  skips the final render and the caption. S13 writes runs/<id>/13-render/final.mp4, hook2.mp4, video.mp4 (the silent
  render) and render.json (every check with want, got, ok; the post-pass); S14 writes 14-export/export.json (what the
  export renders into Ncaptions.txt), caption.txt and caption-data.json. S2 writes 02-expansion/solution.json (type
  flashfx, external or method, name, url, reason, keyword), which S3 to S14, the captions file and history.txt read. The sound stage (S11) writes
  runs/<id>/11-sfx/cues.json (every sound: cue type, file, the event it sits on, placement, gains, the verification),
  sfx_stem.wav, mix.wav (the audio S13 muxes), draft_mixed.mp4 (for the review), sound-map.txt (one readable line per
  sound), and sfx_stem_hook2.wav, mix_hook2.wav for the alternate clip; it refreshes styles/sfx/sfx-map.json at its
  start and records its picks in logs/sfx-usage.json. The review stage (S12) writes runs/<id>/12-review/review.json
  (round, pass, verdict pass | fix | cap | flag, the scores, every tagged issue, the routing), mechanical.json,
  style.json, audio.json, edit-r<n>.json, filmstrips/, prompt-r<n>.md, notes.md and feedback.json (what the re-run
  stages read); state.json rounds.review counts the failed rounds. The visual stages (S9a, S9b, S9c) write
  runs/<id>/09a-animations/plan.json (the scenes and components on the spoken words, the branding by the solution),
  09b-text/plan.json (the caption chunks and card texts), 09c-transitions/plan.json and merged.json (the whole plan,
  pipeline/stages/09-plan/schema.json), each with its prompt digests under digest/; S10 writes
  runs/<id>/10-build/project/ (the HyperFrames project compiled from the plan), events.json (every sound event in
  absolute ms, verified on screen), draft.mp4 (540x960, 30 fps, silent), hook2.mp4 (3.5 s at most), contact-sheet.png,
  plan.json, build.json and check.json. The voiceover stage (S8) writes runs/<id>/08-voiceover/vo.wav
  (48 kHz mono, -14 LUFS), vo_hook2.wav, words.json (every spoken word with start and end ms and its beat; the
  beats' windows; the breath after the hook), words_hook2.json and voiceover.json (the trail: every line's
  attempts, transcriptions, word error rates, respellings and rewrites, the timings, the pace). The voice is
  Kokoro af_bella from library/voice/engine.txt (the defaults of BUILD_SPEC.md 2.5 when that file is missing or
  names another engine), never another engine or voice; config voice.wpm (186, at engine.txt speed 1.1) is its measured pace.

## Folder map
- `ideas.txt`: the idea queue (one idea per `{...}` block). `run.sh`: the video runner. `config.json`: models, engines,
  caps, paths.
- `exports/N/`: finished reels (`N.mp4`, `Ncaptions.txt`, `Nhook2.mp4`).
- `library/`: curated by the user: hooks.txt, profile/ (account.md, voice.md, deliverables.txt, pronunciations.txt),
  voice/ (reference.wav, reference_long.wav, engine.txt, memo.*). Derived by the pipeline, never edited by hand:
  .hooks.index.json and hooks.lint.txt (ignored by git), .hooks.stats.json (the judge's picks and wins; commit it
  when you want a snapshot), hooks.suggested.txt (new hook shapes the model noticed; move them into hooks.txt
  yourself). `bash pipeline/bin/index-hooks` rebuilds the index when hooks.txt changed;
  `bash pipeline/bin/build-voice-profile [--force]` rebuilds voice.md and account.md (from library/voice/memo.*
  when it exists, else the template with [FILL IN] placeholders plus the pace measured from the reference
  recordings).
- `styles/paper-cards/`: the look (style.md, tweaks.md, vocabulary.md, tokens.json, refs/, analysis/).
  `styles/sfx/`: the sound effects pack (the user's audio files, ignored by git) and its memory map: sfx-map.json,
  SFX-MAP.md, previews/<cue type>.wav with .txt and .cache/ are generated by `bash pipeline/bin/build-sfx-map`
  (measurements, pools of 5 to 8 per cue type, one indexer call for new files with unclear names; a no-op when
  nothing changed; `--check` says whether the map is current); overrides.txt is the user's (`ban: path`,
  `pin: cue type: path`, kept on every rebuild).
- `motion-lib/`: approved HyperFrames components, candidates/, gallery/. `golden/`: example reels for the visual
  director.
- `pipeline/`: lib/ (bash and Python libraries), stages/ (one folder per stage: CONTRACT.md, schema.json, dummy.sh,
  and from its milestone on run.sh and prompt.md), bin/ (scripts), vendor/ (MIT scripts from
  instagram-agent-skill), knowledge/known-issues.md, tests/.
- `runs/`: one working folder per idea (state.json, its lock file state.lock, idea.txt, one subfolder per stage with
  its outputs, stage.log, .done and calls/ with every model call's raw output; errors/E<n>.md and fixes/F<n>.md
  from the review and fix loop). `logs/`: runner.log (rotated at 50 MB into runner.log.1 to .3), status.txt, history.txt, blocked.txt, limits.log,
  suggested-ideas.txt, sfx-usage.json, STOPPED.md.
- `tools/analyze_refs.py`: reference video analyzer. `build/`, `build-runner.sh`: the automated build (temporary).

## How to start the runner (from M2 on)
- `bash run.sh` processes ideas forever; `bash run.sh --once` stops when the queue is empty. Results appear in
  `exports/N/`. Stop it with Ctrl+C; restarting resumes the unfinished run.
- A missing hard dependency writes logs/STOPPED.md with the exact fix. `bash pipeline/bin/preflight` runs the
  checks alone. Every stage is real (M12): one idea takes 1 to 3 hours on this PC;
  `REELS_DUMMY=all bash run.sh --once` exercises the loop with dummy stages (it removes the processed ideas from
  ideas.txt and writes dummy files into exports/, so use it in a copy or re-add the idea afterwards).
- `bash pipeline/bin/runner-status` prints whether a runner is alive, the latest status line and the log tail.
- `bash pipeline/bin/doctor` (read-only, about 30 s; `--quick` skips the voice check) reports versions, the Node
  packages against their pins, disk, the voice interpreters, the freshness of the sfx map, tokens and hooks index, the
  runner and its status line, the last session's story, blocked ideas, STOPPED.md and limits; exit 1 on a FAIL line.
- The terminal lines: REEL (heartbeat every 5 minutes), IDLE, START, STEP, GATE, ANGLE, DONE, DROP, BLOCK, NEW,
  NEXT, FLAG, STOP, and the error lines LIMIT, RESUME, RETRY, ERROR, FIXED, ESCAL.

## Rules for Claude Code sessions in this folder
- **Braces rule:** when the user's message contains text in `{...}`, append each braced block to ideas.txt by
  running `bash pipeline/bin/add-idea.sh "{...}"` (never by editing the file), then confirm in one line with the
  script's own output ("added 1 idea to ideas.txt (queue: N)").
- **"What is the runner doing?":** read `logs/status.txt` and the end of `logs/runner.log`, or run
  `bash pipeline/bin/runner-status`.
- **Curated by the user, do not edit without asking:** `library/`, `styles/`, `ideas.txt` (only through
  add-idea.sh). The runner's own fixer may edit only `pipeline/` and `motion-lib/candidates/`.
- **Reading the logs:** `logs/history.txt` has one line per finished idea (`date | idea | solution | exported N`,
  `dropped: reason` or `blocked: reason`; solution is flashfx, external, method, or `-` before S2 decided); `logs/blocked.txt` lists blocked ideas with the reason so they can be re-added;
  `logs/STOPPED.md` exists only after a systemic stop and contains the diagnosis and the exact fix;
  `logs/limits.log` has every usage limit wait with its target time; `logs/suggested-ideas.txt` holds the ideas
  the gate suggested instead of a dropped one (in braces, ready for add-idea.sh; never read by the runner).
- **The gate (S3):** a dropped idea's history line carries the scores, for example `dropped: facts don't hold (P2
  S2 C2 F fail H ok): ...` or `dropped: still failing after 2 angle rounds (P3 S1 C3 F ok H ok): ...`. The model only scores;
  pipeline/lib/gate.py decides (a false or unverified core claim always fails F with kind core and drops at once;
  an F fail of kind wording, a statement of the expansion that facts.md does not back while the core claim is
  verified, goes to S4 like a failing P, S or C, DECISIONS.md 112; so does a failing honesty check H, the solution
  not solving the problem or FlashFX forced, and S4 then decides the solution again, DECISIONS.md 264 and 265). The angle loop hands over through
  `<stage>/reopen.txt`, applied by state.py stage-done.
- **Automatic fixes (BUILD_SPEC.md 4.2):** a code error in a stage is reviewed and fixed by the runner itself: the
  report is `runs/<id>/errors/E<n>.md`, the verdict `runs/<id>/fixes/F<n>.md`, the fix a commit `autofix(<stage>):
  ...` plus a line in pipeline/knowledge/known-issues.md. The fixer may edit only pipeline/ and
  motion-lib/candidates/. Usage limits and temporary errors never reach the reviewer: a failed model call is
  waited out and retried inside the stage (ai.sh), a failed stage script by the runner itself (LIMIT, RESUME,
  RETRY lines; DECISIONS.md 88). A runner restarted during a review cycle resumes that cycle (DECISIONS.md 89).
- **Never write an em dash** in any file, prompt, caption, script or terminal message. Use commas, colons, periods
  or parentheses. External text that the runner prints or writes (a CLI message, a tool's stderr, a model's words)
  may contain one: `say` cleans every terminal line, and anything else composed from such text goes through
  `reels_undash VAR` or `undash TEXT` (pipeline/lib/log.sh) or errors.py's `undash()` first.
- **Python:** `python3` is the Windows Store stub and does nothing. Always run `python` (3.13). Text to speech runs
  under the interpreter named in library/voice/engine.txt (the kokoro venv, Python 3.11; the defaults of
  BUILD_SPEC.md 2.5 point at C:/Users/there/venvs/kokoro/Scripts/python.exe) and transcription under config
  tts.whisper_python (the user's chatterbox venv, Python 3.11, which has faster-whisper), else the first of the
  voice interpreter, `.venv-tts/Scripts/python.exe` and `python` that imports faster_whisper; `bash
  pipeline/bin/setup-venv --check` reports both. `bash pipeline/bin/setup-python` installs the packages (jsonschema,
  playwright) and Playwright's Chromium. The vendored scripts run through `bash pipeline/bin/vendor-run <script.py>
  ...` (python -I -X utf8). A Windows Python's bare `bash` is the WSL launcher: run.sh exports REELS_BASH for
  Python code that must call a bash script.
- **Shell:** Git Bash. Every text file is LF (.gitattributes: `* text=auto eol=lf`); scripts use GNU date.
- **Tool limits:** the Bash tool's command string fails above roughly 8 KB here, so write long files with the
  Write tool instead of a heredoc; the tool also collapses `\\` to `\` inside heredocs. Check line endings with
  Python on bytes, not with grep. A `C:/...` entry in PATH is invisible to Git Bash: use `/c/...`.
- **Windows paths and Python output:** every script sources pipeline/lib/common.sh, which exports the roots in
  `C:/...` form (cygpath -m) and PYTHONUTF8; environment variables are not path-converted by Git Bash, arguments
  are. Python helpers must print LF (`sys.stdout.reconfigure(newline="\n")`), because Windows Python writes CRLF
  to pipes. See DECISIONS.md 38 to 40.

## Skills
The `/ig-*` skills from github.com/Jakeschincariol/instagram-agent-skill are installed globally in `~/.claude/skills/`
and read the voice profile in `~/.claude/instagram/voice.md`. The pipeline uses its own copy of the profile in
`library/profile/voice.md` and vendored copies of the scripts in `pipeline/vendor/ig-agent-skill/`.
