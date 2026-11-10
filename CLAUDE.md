# instagramReels

An unattended pipeline that turns a short video idea into a finished Instagram reel: research, expansion, hooks,
script, voiceover, visuals written as code (HyperFrames motion graphics, never AI video), sound effects, review,
render, export. The full spec is BUILD_SPEC.md; the build plan is PLAN.md; choices are in DECISIONS.md.

## Build status
- M20 Formats and the timeline: done (2026-11-10): `pipeline/formats/<format>/format.json` (schema pipeline/schemas/format.schema.json, loader pipeline/lib/formats.py) holds a format's
  stages in order (folder, label, activity, output, session group, caps, reopen routes, prompt overrides), its `config` block, the required channel files (preflight rows) and the
  template folder; state.py, the runner, the review's stage order, the session keys and new-channel read it, nothing keeps a stage list of its own. problem-solution-reel is today's S1 to S13, then the new
  stage `timeline` (label TL), then S14; the keys research, hooks, judge, script, visual, caption and review (minus its four safety keys) moved from config.json into its format.json
  `config` (values unchanged, build/M20/format-keys-before.json), and the channel file checks of preflight into its `required_files`. Every run ends its production with
  runs/<id>/timeline/timeline.json (pipeline/schemas/timeline.schema.json, version 1; `python pipeline/lib/timeline build|check|render|validate`: compose.py describes the HyperFrames
  composition, check.py compares it with the plans, words.json, cues.json, the composition and final.mp4, render_ffmpeg.py renders a footage format's timeline). The test-only format
  footage-dummy (pipeline/tests/formats/footage-dummy/: ingest, cut, timeline-render, 14-export, with 3 clips the test makes) runs through the same runner. The FlashFX text of the shared
  stages (12-review's prompt, pipeline/lib/review/) moved into problem-solution-reel's prompt overrides and config (`{{BRAND}}`, review.branding.own_solution_type), and
  isolation_scan.py (test-isolation part 1) now fails on a channel, brand or style name in a shared stage. `bash pipeline/tests/test-m20.sh`, build/M20/fingerprint/. DECISIONS.md 365 to 370.
  Next: M21 (the editable project, S15), then M22 to M27.
- M19 Exports and channels side by side: done (2026-11-09): every export is `exports/<id>-N/` with `<id>-N.mp4`, `<id>-Ncaptions.txt` and (instagram-reels only)
  `<id>-Nhook2.mp4`, N counted per channel from exports/ and the channel's history.txt (`exported <id>-N`); the DONE line is `exported <id>-N -> exports/<id>-N/ (...)`.
  New: pipeline/platforms/<platform>/ (platform.json, schema pipeline/schemas/platform.schema.json; instagram-reels with render.py, youtube-shorts with exporter.py,
  input.schema.json, prompt.md, run.sh: title, description and pinned comment with every check of spec section 8, one rewrite, NEEDS REVIEW, logs/descriptions.jsonl),
  pipeline/lib/platform_lib.py, pipeline/lib/heavy.sh (`heavy_run <kind> <label> -- cmd`: the global `.locks/heavy.lock`, one WAIT line per wait, config `heavy`;
  `editor_run` for the editor copy from M21; `engine_log` writes logs/engine.log), the shared `.locks/limit.json` (every runner waits for the same reset, no model call)
  and the root logs/limits.log with the channel id, pipeline/lib/quota.py (channel.json daily_quota: `IDLE   quota 2/2 today, next idea after 00:00`),
  `bash pipeline/bin/new-channel <id> --format problem-solution-reel --platform <platform> [--name "..."]` (template in pipeline/formats/problem-solution-reel/template/,
  the channel starts disabled; preflight's `fill_in` check lists files that still say [FILL IN]), runner-status and doctor for every channel (quota, heavy lock, limit
  file, platforms), test-isolation.sh part 2 (the canary test, recorder FAKE_CLAUDE_RECORD_DIR), `bash pipeline/tests/test-m19.sh`, build/M19/fingerprint/.
  The real folder had no export yet, so the real export migration is empty (build/M19/real-migration.txt); the rehearsal covers the renames. DECISIONS.md 355 to 364.
  (Next after M19 was M20, above.)
- M18 Channels: done (2026-11-09): FlashFX's data moved into channels/flashfx/ (verified, undo script kept in build/M18/), every path to
  channel data goes through pipeline/lib/paths.sh and paths.py, `bash run.sh --channel <id>` (see "The channels" below). Next (after M19): M20 to M27, the rest of the channels plan: the channels plan (BUILD_SPEC.md section 14, explained in
  CHANNELS.md; the editable project is M21; M22 learning from feedback for every channel, 14.14; M23 to M27 the second channel
  `scenarios`, 14.10, from the user's documents in build/channel2/). The build is driven by `bash build-runner.sh` (a build/PAUSE
  file stops it between milestones; every milestone to M27 is specified, so no pause is needed); its log is build/build.log and its per-milestone reports are in build/M<n>/.
  M16 (Director, components and the energy loop) is done too (2026-11-08); M17 (control check) is done (2026-11-08).
- M18 added: pipeline/lib/paths.sh and paths.py (the one module that knows the layout: REELS_CHANNEL, REELS_CHANNEL_ROOT, REELS_IDEAS, REELS_LOGS,
  REELS_LOCKS, REELS_RUNS, REELS_LIBRARY, REELS_STYLES, REELS_MOTIONLIB, REELS_GOLDEN, REELS_EXPORTS, REELS_GLOBAL_LOCKS; `chpath <rel>`, `chcfg <key>`,
  paths.ch(rel); another channel's folder or export folder is refused with exit 3), pipeline/lib/config.py (config.json + the format's config + channel.json,
  deep-merged; REELS_CONFIG is the resolved file channels/<id>/.cache/config.resolved.json that common.sh makes again whenever a source is newer,
  REELS_CONFIG_ENGINE is config.json), pipeline/schemas/channel.schema.json, channels/flashfx/channel.json (style, voice, sfx, lengths and the 14
  channel paths moved out of config.json, values unchanged), run.sh --channel and --allow-disabled, per-channel runner locks, logs, history and
  status, add-idea.sh --channel, preflight --channel (checks the channel's files, channel.json validated first), runner-status (one block per
  channel, --channel), doctor (the engine once, then every channel, --channel; prints the engine keys a channel overrides), the review safety
  keys per channel (config review.protected_paths channels/*/ideas.txt, channels/*/library, channels/*/styles, exports; fixer_paths with {channel};
  protect.py walks every channel), pipeline/bin/migrate-channels with pipeline/lib/migrate.py (dry run, rehearsal fixture, undo, kill recovery,
  verification), pipeline/tests/isolation_scan.py with isolation-allowlist.txt, test-isolation.sh part 1 and test-m18.sh (DECISIONS.md 344 to 354).
  The tests build their sandboxes with channels/flashfx/ inside (lib.sh: SANDBOX_CH, SANDBOX_CH_M, resolved_config); the numbering lock of exports/
  is global (REELS_GLOBAL_LOCKS) until M19.
- M17 added only tools and records, nothing the runner uses: pipeline/tests/manifestlib.py, inventory.py, refindex.py, make-manifest.py,
  check-manifest.py, risk-scan.py, run-fake.sh (every fake-only test in a throwaway copy, `--compare DIR` is the baseline rule), fakeresults.py,
  make-test-copy.sh, m17-baseline.sh, m17-fixture.py, m17-simulate.py, m17-summary.py and test-m17.sh (`bash pipeline/tests/test-m17.sh`, about 5
  minutes), and under build/M17/: inventory.md and .tsv, refindex.tsv, refindex-data.tsv, move-manifest.tsv (the moves of M18 and M19),
  config-keys.tsv, risks.md, riskiest-moves.md, baseline/ (results.tsv, failures.tsv, logs, preflight, doctor, the dummy fingerprint) and report.md.
  Baseline rule for M18 to M27: no test that passed in build/M17/baseline fails (known failures: test-m2, test-m3, test-m6, test-m7).
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
  287), pipeline/tests/m13-run.sh (the three-idea driver) and pipeline/tests/fixtures/ideas/three-ideas.txt, M14: the
  energy meter pipeline/lib/review/energy.py (`python pipeline/lib/review energy <video> [--plan merged.json]`: the
  moving share, the middle band, the pixels changing, the still stretches and the longest still of a reel and of each
  scene against tokens.json energy.targets; `energy calibrate --refs styles/paper-cards/refs --out
  styles/paper-cards/analysis/energy.json` measures the nine references), tokens.json `motion.grammar` (the Motion and
  energy rules as values: pipeline/lib/tokens.py GRAMMAR, exposed as `--m-*` in motion-lib/assets/tokens.css) and
  `energy` (the targets: 70 percent of the look references' medians, 41, 46, 3.3, 15 percent and 2 s on this PC; an
  `- **Energy:** moving 45, still 12` line in tweaks.md overrides them), the shared motion grammar
  motion-lib/assets/pc-motion.js (PCM.life: main animation, inertia, hold, exit; the combined zoom and parallax
  rotation; PCM.canvas: the edge and ambient layers; PCM.idle: the mascot; PCM.depth: the 2.5D parts; count-ups and
  typing as setter tweens because HyperFrames seeks with GSAP events suppressed) that every component uses (every
  element component has a `hold` prop: calm, normal, lively), paper-canvas with a timeline, `seed` and `duration` props
  and the layers, icon-3d (Three.js extruded SVG paths and primitives, a CSS-extruded fallback, `mode` auto|webgl|css),
  frame-match's life checks (never static for 0.5 s, the inertia 2 to 4 s) and per-component energy (catalog.json
  `energy`, the gallery's energy line), golden/test-idea/energy.json and build/M14/golden-energy-before.json, the
  review's reading of the grammar's transients (PCM.mark sets `data-pcm-main` and `data-pcm-exit` on every element,
  the review reads the scale in 3D, does not judge an element while it arrives or leaves and samples "landed" after
  the combined animation: DECISIONS.md 303), the hold's room (PCM.room: the inertia and the drift fit the room from
  the element's rest box to the safe edges, `--m-safe-*` in tokens.css, over its life or room_life_s 8 s: near an
  edge the element turns and creeps instead of drifting; DECISIONS.md 304), M15: the two caption modes of E3 as
  components on pc-motion.js (motion-lib/compositions/caption-word.html: one word at a time on its spoken time, the
  emphasis words in the serif italic at 1.4 times on the accent box, every word rising 8 to 16 px over its life;
  caption-group.html: 2 to 6 words as kinetic typography in the hero zone, drawn from a layout it is given; caption-line is
  retired into motion-lib/retired/), pipeline/lib/visual/kinetic.py (the deterministic group layout engine: roles, at least 3
  fonts, the anchor at 2 to 3 times the caption size, the words beside it stacked to its height, asymmetry, the group caption
  zone `motion.grammar.captions.group_zone`, the right rail, splitting what does not fit, avoiding graphics on screen;
  `python pipeline/lib/visual kinetic "the quick brown fox" --anchor 0 --png out.png`), script.json's per-beat `importance`
  (hook, key-claim, number, payoff, pre-ask, normal: script_checks.derive_importance), 9b's caption entries with `mode`
  (word | group), `anchor`, `layout`, `motion` and `importance` and its choice rule (plan9.finalize_captions: word mode under
  any text, groups where the hero zone holds no text; the digest lists each scene's importance, text and graphics), the plan
  validator's rules `caption_modes`, `text_budget` (100 characters of non-caption text on screen) and `text_size` (a size the
  plan chooses under the caption size is an error, a size the library bakes in a warning: DECISIONS.md 308), S12's
  mechanical rules `caption_mode`, `caption_static`, `text_budget` and the baked-size warnings, the golden plan with groups on
  its number and payoff beats, pipeline/tests/m15-mkrun.py and m15-frames.py (DECISIONS.md 306 to 312), M16: nine components on
  pc-motion.js with real motion inside the content (motion-lib/compositions/screenshot-zoom.html: a camera over a real page with focus
  points and a highlight box; video-card.html: a recording or clip playing in a window or a bare frame, drawn from the hf-seek time through
  `waitUntil` with clip_start like the 3D components; card-fan.html, card-grid.html, timeline-scrubber.html, cursor.html, mock-site-card.html,
  swatch-row.html, swatch-card.html), the moves they share as PCM.move, run, appear, vanish, pulse, press, glideProp and readout in
  pc-motion.js (test-m14 bans a tween in a composition), pipeline/lib/motion/demo_assets.py (the demo clips of the library and the
  recordings of the frozen test run's screenshots, built when missing: *.mp4 is not in git), S1's page recordings (pipeline/lib/screenshot.py
  records a 5 to 8 s scroll video next to every screenshot that scrolls: NN-name.mp4, H.264, 1080 wide, key frame every 6 frames;
  assets.json: recording, recording_seconds; `--no-record` skips it; research/<file>.mp4 in a video prop), the validator rules of E9
  in visual/plan_validate.py (hero_motion, hero_fill, layers, camera, hook_frame0, empty_paper, list_entry, transition_variety, and the
  warning real_motion; config visual.energy_rules error | warn | off; tokens.json motion.grammar.composition holds the numbers), the
  director's repairs in visual/plan9.py (hook_moves_from_frame0, vary_transitions), the 9a and 9c prompts around the Motion and energy
  rules, the new golden reel (golden/test-idea: its energy in energy.json meets every target of tokens.json), S12's energy loop
  (pipeline/lib/review/energy_check.py: the energy check first, a failing scene routed to 9a with its numbers, the ask scene left out
  of the per-scene routing; review/liveness.py: no element static for 0.5 s and the edge layer present, in the mechanical checks; the
  ninth edit-review score `energy`; the early stop in route.py: the same scores and issues twice in a row give the verdict `stop` and a
  NEEDS REVIEW flag; config review.energy_check, liveness, early_stop, energy_scene_share, min_edge_elements), end-card's optional
  confetti, pipeline/tests/test-m16.sh with m16-lib.py, m16-recording.py, m16-plans.py, m16-review.py and sandbox-config.py (the test
  sandboxes of the milestones before M16 turn the energy rules, the energy check, the liveness checks and the early stop off:
  SANDBOX_ENERGY=on keeps them on; ai.sh waits for a Claude Code launcher that an update replaced for a moment; DECISIONS.md 314 to 324). Run every
  test with `bash pipeline/tests/run-all.sh` (about 2.5 hours plus test-m12 section 4, the whole pipeline on the test
  idea with the real models, 1 to 3 hours, and test-m13 section 3, three ideas with the real models, several hours;
  test-m3 section 4, test-m4
  sections 3 and 4, test-m5 sections 3 and 4, test-m6 section 3, test-m7 section 3, test-m10 section 3 and test-m11
  section 4 make real model or engine calls, test-m8 and test-m9 make none, test-m9 takes about 8 minutes, test-m10
  about 25 minutes, test-m11 about 40 minutes; `M7_SECTIONS="1 2" bash pipeline/tests/test-m7.sh`,
  `M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh`, `M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh` and
  `M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh` and `M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh`
  (about 20 minutes) are the fake-only tests; `M16_SECTIONS="1 2 3 4 5 7" bash pipeline/tests/test-m16.sh` makes no model call, about 40 minutes
  (its section 6 is the test idea with the real models, 2 to 4 hours); `bash pipeline/tests/test-m14.sh` makes no model call, about 30 minutes:
  frame-match on every component and the golden render; `bash pipeline/tests/test-m15.sh` makes no model call, about 15 minutes:
  the layout engine, the plan rules with planted faults, the golden captions frame by frame, S12's checks on planted copies; the tests never assert on the user's profile: test-m12 and
  test-m13 use drafts of their own, pipeline/tests/fixtures/profile/, DECISIONS.md 305).
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
- `run.sh`: the video runner (`bash run.sh --channel <id>`). `config.json`: the engine's settings (models, tts, caps, errors, timeouts, runner,
  render, preflight, logs, the engine paths, the review safety keys, and until M20 the format's keys). `pipeline/`, `tools/`: the engine.
- `channels/<id>/`: one folder per channel (BUILD_SPEC.md 14.3): `channel.json` (identity, platform, format, quota, the channel-owned config: style,
  voice, sfx, lengths, paths), `ideas.txt` (the idea queue, one idea per `{...}` block), `library/`, `styles/`, `motion-lib/`, `golden/`, `runs/`,
  `logs/`, `.locks/`, `.cache/` (the resolved config). Today one channel exists: `channels/flashfx/`. Everything below that names library/, styles/,
  motion-lib/, golden/, runs/, logs/ or ideas.txt means the same path inside the channel's folder.
- `exports/`: finished reels of every channel, one folder `<id>-N/` each (`<id>-N.mp4`, `<id>-Ncaptions.txt`, `<id>-Nhook2.mp4` on instagram-reels; section 8). `logs/` and
  `.locks/` at the root: only what is shared (limits.log with the channel id, engine.log, editor files; the global locks heavy.lock, limit.json, exports, editor.lock).
- `library/` (in the channel): curated by the user: hooks.txt, profile/ (account.md, voice.md, deliverables.txt, pronunciations.txt),
  voice/ (reference.wav, reference_long.wav, engine.txt, memo.*), brand/ (FlashFX's brand kit). Derived by the pipeline, never edited by hand:
  .hooks.index.json and hooks.lint.txt (ignored by git), .hooks.stats.json (the judge's picks and wins; commit it
  when you want a snapshot), hooks.suggested.txt (new hook shapes the model noticed; move them into hooks.txt
  yourself). `REELS_CHANNEL=<id> bash pipeline/bin/index-hooks` rebuilds the index when hooks.txt changed;
  `REELS_CHANNEL=<id> bash pipeline/bin/build-voice-profile [--force]` rebuilds voice.md and account.md (from library/voice/memo.*
  when it exists, else the template with [FILL IN] placeholders plus the pace measured from the reference
  recordings). The tools that work on one channel's data take REELS_CHANNEL (with exactly one channel folder it is the default for them).
- `styles/paper-cards/` (in the channel): the look (style.md, tweaks.md, vocabulary.md, tokens.json, refs/, analysis/).
  `styles/sfx/`: the sound effects pack (the user's audio files, ignored by git) and its memory map: sfx-map.json,
  SFX-MAP.md, previews/<cue type>.wav with .txt and .cache/ are generated by `bash pipeline/bin/build-sfx-map`
  (measurements, pools of 5 to 8 per cue type, one indexer call for new files with unclear names; a no-op when
  nothing changed; `--check` says whether the map is current); overrides.txt is the user's (`ban: path`,
  `pin: cue type: path`, kept on every rebuild).
- `motion-lib/` (in the channel): approved HyperFrames components, candidates/, gallery/, assets/pc-motion.js (the motion grammar
  every component uses: M14). `golden/`: example reels for the visual director (energy.json: the golden's energy).
- `pipeline/`: lib/ (bash and Python libraries, paths.sh and paths.py first), schemas/ (channel.schema.json), stages/ (the stage library: one folder per stage: CONTRACT.md,
  schema.json, dummy.sh, and from its milestone on run.sh and prompt.md), formats/ (one folder per format: format.json, prompts/, template/; M20), bin/ (scripts), vendor/ (MIT scripts from
  instagram-agent-skill), knowledge/known-issues.md, tests/.
- `runs/` (in the channel): one working folder per idea (state.json, its lock file state.lock, idea.txt, one subfolder per stage with
  its outputs, stage.log, .done and calls/ with every model call's raw output; errors/E<n>.md and fixes/F<n>.md
  from the review and fix loop). `logs/` (in the channel): runner.log (rotated at 50 MB into runner.log.1 to .3), status.txt, history.txt, blocked.txt,
  suggested-ideas.txt, sfx-usage.json, STOPPED.md.
- `tools/analyze_refs.py`: reference video analyzer. `build/`, `build-runner.sh`: the automated build (temporary).

## The channels (from M18)
- One engine, several channels, each with exactly one format and one platform (BUILD_SPEC.md section 14; CHANNELS.md explains the design). Channel ids are
  lowercase letters and digits. Today: `flashfx` (FlashFX, instagram-reels, problem-solution-reel). Planned: `scenarios` (Gabryverse, youtube-shorts,
  serial-story, M23 to M27), later ones in 14.11.
- Start one: `bash run.sh --channel flashfx [--once]` (or REELS_CHANNEL=flashfx). `bash run.sh` alone exits 2 and lists the channels; an unknown or
  disabled id exits 2 (`--allow-disabled` is for tests). One runner per channel; runners of different channels may run side by side (each in its own terminal).
- Where a channel's files are: `channels/<id>/` (the folder map above). `exports/` is shared (numbered per channel). Status per channel:
  `bash pipeline/bin/runner-status [--channel <id>]`, `bash pipeline/bin/doctor [--quick] [--channel <id>]`, `bash pipeline/bin/preflight --channel <id>`.
- A channel's session never reads or edits another channel's folder: the paths module refuses it (exit 3), model calls may not write to any channel's
  ideas.txt, library/ or styles/ (config review.protected_paths), the fixer edits only pipeline/ and the run's channels/<id>/motion-lib/candidates/.
- The files moved in M18 by `bash pipeline/bin/migrate-channels` (the log, the dry run, the executed manifest and `undo-migration.sh` are in build/M18/).

## How to start the runner (from M2 on)
- `bash run.sh --channel flashfx` processes the channel's ideas forever; add `--once` to stop when the queue is empty. Results appear in
  `exports/N/`. Stop it with Ctrl+C; restarting resumes the unfinished run.
- A missing hard dependency writes the channel's logs/STOPPED.md with the exact fix. `bash pipeline/bin/preflight --channel flashfx` runs the
  checks alone. Every stage is real (M12): one idea takes 1 to 3 hours on this PC;
  `REELS_DUMMY=all bash run.sh --channel flashfx --once` exercises the loop with dummy stages (it removes the processed ideas from
  ideas.txt and writes dummy files into exports/, so use it in a copy (a temp REELS_ROOT) or re-add the idea afterwards).
- `bash pipeline/bin/runner-status [--channel <id>]` prints, per channel, whether a runner is alive, the latest status line and the log tail, and the global locks.
- `bash pipeline/bin/doctor [--quick] [--channel <id>]` (read-only, about 30 s; `--quick` skips the voice check) reports the engine once (versions, the Node
  packages against their pins, disk, the voice interpreters), then for every channel: channel.json, the engine keys it overrides, the freshness of the sfx map, tokens and
  hooks index, the runner and its status line, the last session's story, blocked ideas, STOPPED.md and limits; exit 1 on a FAIL line.
- The terminal lines: REEL (heartbeat every 5 minutes), IDLE, START, STEP, GATE, ANGLE, DONE, DROP, BLOCK, NEW,
  NEXT, FLAG, STOP, and the error lines LIMIT, RESUME, RETRY, ERROR, FIXED, ESCAL.

## Rules for Claude Code sessions in this folder
- **Braces rule:** when the user's message contains text in `{...}`, append each braced block to the channel's ideas.txt by
  running `bash pipeline/bin/add-idea.sh --channel <id> "{...}"` (never by editing the file), then confirm in one line with the
  script's own output ("added 1 idea to ideas.txt (queue: N)"). Keep a `[important]` label inside the braces as the
  user wrote it (`{[important] ...}`, at the start or the end): the script then says "marked important". The channel comes from the user's
  words around the braces ("for scenarios", "scenarios:", "flashfx idea"). With one enabled channel (today flashfx) it is that one; when the user
  names none and more than one channel is enabled, ask which one in one short question before adding.
- **Models (DECISIONS.md 333 to 335):** Sonnet is the main model of the reels (research, hooks, gate, judge, script,
  the builder, the code error reviewer, and the visual director's fine tuning after a failed review round); Opus makes
  the first plan of each visual pass (the design) and the edit review (qa). The escalations (visual director and
  builder after 3 failed review rounds, the error reviewer's last cycle) run on Opus, and on Fable only for an idea
  marked `[important]`: no other idea ever runs Fable (pipeline/lib/model_choice.py enforces it in ai()). An
  `"important"` override in config.json models.<role> applies to the marked ideas only.
- **"What is the runner doing?":** read `channels/<id>/logs/status.txt` and the end of `channels/<id>/logs/runner.log`, or run
  `bash pipeline/bin/runner-status` (one block per channel).
- **Curated by the user, do not edit without asking:** `channels/*/library/`, `channels/*/styles/`, `channels/*/ideas.txt` (only through
  add-idea.sh). The runner's own fixer may edit only `pipeline/` and the run's `channels/<id>/motion-lib/candidates/`. A session working for one channel
  never edits another channel's folder.
- **Reading the logs** (each channel's own, in `channels/<id>/logs/`): `logs/history.txt` has one line per finished idea (`date | idea | solution | exported N`,
  `dropped: reason` or `blocked: reason`; solution is flashfx, external, method, or `-` before S2 decided); `logs/blocked.txt` lists blocked ideas with the reason so they can be re-added;
  `logs/STOPPED.md` exists only after a systemic stop and contains the diagnosis and the exact fix;
  the root `logs/limits.log` has every usage limit wait with its channel id and target time (M19); `logs/suggested-ideas.txt` holds the ideas
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
  channels/<id>/motion-lib/candidates/. Usage limits and temporary errors never reach the reviewer: a failed model call is
  waited out and retried inside the stage (ai.sh), a failed stage script by the runner itself (LIMIT, RESUME,
  RETRY lines; DECISIONS.md 88). A runner restarted during a review cycle resumes that cycle (DECISIONS.md 89).
- **Never write an em dash** in any file, prompt, caption, script or terminal message. Use commas, colons, periods
  or parentheses. External text that the runner prints or writes (a CLI message, a tool's stderr, a model's words)
  may contain one: `say` cleans every terminal line, and anything else composed from such text goes through
  `reels_undash VAR` or `undash TEXT` (pipeline/lib/log.sh) or errors.py's `undash()` first.
- **Python:** `python3` is the Windows Store stub and does nothing. Always run `python` (3.13). Text to speech runs
  under the interpreter named in the channel's library/voice/engine.txt (the kokoro venv, Python 3.11; the defaults of
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
