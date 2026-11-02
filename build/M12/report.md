# M12 Final render, caption, export, end to end (S13, S14): build report (2026-11-02)

The batch was interrupted once (the Fable usage limit, 2026-11-02 00:42) after most of the code was written; this
session (Opus) continued from the working tree: it fixed the hook 2 clip's length, the "exporting #N" activity and two
test assertions, ran every test, wrote the docs and committed.

## What was built

1. **The problem-first solution, retrofitted into S1 to S4 and S7** (BUILD_SPEC.md section 0, S1 to S4, S7; one module,
   pipeline/lib/solution.py, owns the rules; DECISIONS.md 261 to 267).
   - S1: research's model schema requires solution_candidates (external tools and repos with a verified URL, methods);
     facts.md lists them under their own heading.
   - S2: the model answers solution_decision {type, name, url, reason}; expansion.py normalizes it against facts.md and
     sets the keyword from the type (FLASH for flashfx, LINK for external with the tool's link as the deliverable, the
     deliverable that fits for a method). The prompt carries account.md's content strategy, the candidates, voice.md's
     usable proof lines and the solution types of the last 10 exported reels. Output: 02-expansion/solution.json, read
     by every later stage (S9's branding already read it since M10).
   - S3: the honesty check H (pass or fail, with evidence and a fix). gate.py forces a fail for a flashfx solution
     while voice.md "Proof I can use" has no usable line. An H fail goes to S4 inside the angle rounds, never a drop by
     itself. The score text is now `P3 S2 C3 F ok H ok`.
   - S4: after an H fail it decides the solution again with the S2 rules and rewrites solution.json and the keyword.
   - S7: the writer gets the rules for the reel's type; a FlashFX mention in a non-FlashFX script is a scripted hard
     failure, ad language and "made in FlashFX" are judged by the checks model (hard), with a scripted phrase floor.
   - History lines: `date | idea | solution | exported N` (dropped and blocked too; `-` before S2).
2. **S13, the final render** (pipeline/stages/13-render/run.sh over pipeline/lib/finalrender.py; no model;
   DECISIONS.md 268, 269). HyperFrames renders 10-build/project at 1080x1920, 30 fps, silent; ffmpeg muxes
   11-sfx/mix.wav as AAC 48 kHz mono with the video copied (HyperFrames' own audio path doubled the mono voice and
   measured 3 LU louder). ffprobe and loudnorm check size, rate, h264 High, yuv420p, AAC 48 kHz, audio present, the
   duration against vo.wav within 0.2 s, -14 LUFS plus or minus 1, true peak at most -1.5 dBTP plus 0.5 dB of AAC room.
   A failing check gets one ffmpeg post-pass that fixes only what differs; still failing is a code error. The hook 2
   clip takes the same path with mix_hook2.wav (3.5 s at most, loudness a soft check). Outputs: final.mp4, hook2.mp4,
   video.mp4, render.json.
3. **S14, caption and export** (pipeline/stages/14-export/run.sh, prompt-caption.md, model.schema.json over
   pipeline/lib/caption.py; DECISIONS.md 270, 271). The script model writes the body, the ask line, 3 to 5 hashtags and
   search terms; caption.py puts hook 1 first, word for word (125 characters or fewer), and checks one ask with the
   keyword once, no second ask, no link, hashtags (one word, not generic, none in the body), body length and the
   solution rules; humanize.py cleans it, the vendor caption.py lints it (no FAIL). One retry in the same session with
   the exact problems; then written anyway with a NEEDS REVIEW flag. export.json feeds the runner's export step
   (pipeline/lib/export.py), which renders Ncaptions.txt in the format of spec section 8 with the new SOLUTION block,
   numbers, moves in one step, removes the idea and writes the history line.
4. **Fixes found by the tests and the real run** (DECISIONS.md 273 to 275): the hook 2 clip's mix is shorter than its
   composition, so `-shortest` cut the clip (the mux now pads the audio); the "exporting #N" activity was never shown;
   M11's style check hung in every second review round (the analyzer's ffmpeg waited at an overwrite prompt for 20
   minutes, then three "temporary" retries: about an hour of this run); a model at its own usage limit ("You've
   reached your Fable limit", api error 429) was retried as a rate limit and then a code error, so every escalated call
   from review round 4 on would have blocked the reel (ai.sh now falls back to opus for that call). test-m2's dummy run
   reached the real reviewer when the 03-gate dummy lacked the new H field: the runner's own fixer repaired it and
   committed `autofix(03-gate)` (b7ea7e3) in this repo.
5. **The runner**: every stage is real by default; the activity "exporting #N" (spec section 7) is set before the
   export and shows in the STEP line (`writing caption done (12s) -> exporting #1`).

## Files

- New: pipeline/lib/solution.py, finalrender.py, caption.py; pipeline/stages/13-render/run.sh;
  pipeline/stages/14-export/run.sh, prompt-caption.md, model.schema.json; pipeline/tests/test-m12.sh;
  pipeline/tests/fixtures/fake/m12/ (the fake research, expansion, gate rounds, angle and caption answers);
  pipeline/tests/fixtures/runs/test-idea/02-expansion/solution.json (hand-written for the frozen M4 outputs);
  build/M12/patch-tests.py (the record of the earlier tests' patched assertions), build/M12/run-s4.sh (starts the real
  run detached).
- Changed: pipeline/lib/research.py, expansion.py, gate.py, script_checks.py, history.sh, runner.sh, export.py; the S1
  to S4 and S7 prompts, schemas and run.sh files, the S5 run.sh (the brief names the solution); the 13-render and
  14-export CONTRACT.md and schema.json, the 02-expansion and 14-export dummies; config.json (render.*, caption.*, four
  timeouts); the fake M4 fixtures and the frozen gate files (the decision and H fields); test-m2, test-m3, test-m4 and
  test-m6 assertions (history line, score text, keyword, S7 plan line, the exporting #N STEP).

## How to run the test

- `bash pipeline/tests/test-m12.sh`: every section; section 4 runs the whole pipeline on the test idea with the real
  models and the real voice (1 to 3 hours).
- `M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh`: the fake-only sections (about 20 minutes, two final
  renders).
- Section 4 alone, detached so it outlives a 2-hour tool call: `bash build/M12/run-s4.sh` (writes
  build/M12/test-m12-s4.log). Do not edit test-m12.sh while it runs.
- `M12_FREEZE=1` also copies the real run's solution.json, render.json and the 14-export outputs into the frozen
  fixtures.

## Test output (summary)

All on the final code (build/M12/*.log):

- test-m12 section 1 (units: solution.py, the expansion's decision and keyword, the gate's H, the script's solution
  checks, the history line, the SOLUTION block, S13's checks on the golden render, the mux with a short mix, the
  post-pass, the style check run twice into one folder, the model-limit fallback, the caption composer, the dummies)
  and section 5 (the em dash scan): 96 passed, 0 failed (test-m12-s15.log).
- Section 2 (S11 real, S12 dummy, S13 and S14 through the runner on the frozen build, the fake caption model):
  56 passed, 0 failed (test-m12-s2b.log, about 10 minutes, two 1080x1920 renders). Before the fix the hook 2 clip
  failed its duration check three times and the idea was blocked (test-m12-s23.log).
- Section 3 (the honesty loop with the fake claude: a forced FlashFX solution fails H, S4 decides the external skill,
  the gate passes on round 2, the run reaches the export): 28 passed, 0 failed (test-m12-s23.log, test-m12-s135.log).
- Section 4 (the test idea from scratch with the real models and the real Kokoro voice, test-m12-s4.log): exported #1
  after 168 minutes, and its genuine evaluation ran all 33 checks with every one passing: DONE, no BLOCK, DROP or STOP,
  `GATE passed (P3 S3 C3 F ok H ok)`, solution external (the frontend-design plugin with its GitHub URL), keyword LINK,
  1.mp4 1080x1920 30 fps h264 High yuv420p AAC 48 kHz, 39.40 s for a 39.40 s voice, -14.35 LUFS and -1.5 dBTP, 1hook2.mp4
  3.00 s with audio, the captions file in the spec's order with SOLUTION and NEEDS REVIEW (17 flags), first line hook 1
  (47 characters), 5 hashtags, caption.py lint without FAIL (REVIEW: one search term missing), no FlashFX in
  script.json or the caption, the idea gone from ideas.txt, `| external | exported 1` in history.txt, no em dash.
  The edit review failed all 5 rounds (scores of 3 on stop, hierarchy, variety, generic), so the reel exported with
  NEEDS REVIEW as the spec says. Two bugs surfaced during the run and were fixed (DECISIONS.md 274 and 275, below). The
  live run got the same fixes by hand (copied into its sandbox; a hung ffmpeg killed). Caveat: the log after the
  captions printout is not valid. I committed edits to test-m12.sh while this 3-hour bash process was still executing
  it, so bash resumed at a shifted offset, ran the runner again on the empty queue (28 s, overwriting real.out) and
  stopped with "command not found" (exit 2). Every assertion of the genuine pass ran before that point. The sandbox
  ran the final code: the two fixed files copied into it are byte-identical to the committed ones, and the later
  commits only touched tests and docs.
- Earlier tests after the touches to their code: test-m2 207/207, test-m3 fake sections 374/374 (twice: after the
  known-issues assertion fix and after the ai.sh change), test-m4 fake 202/202, test-m5 fake 198/198, test-m6 fake
  147/147, test-m11 fake 227/227, test-no-emdash 1/1.

## Known gaps

- voice.md "Proof I can use" holds only [FILL IN] lines, so H fails any FlashFX solution today and every reel uses an
  external tool or a method; account.md has no "Content strategy" section, so the balance target is the default rules
  plus the history (HUMAN_TODO).
- The predicted export number in "exporting #N" is the highest number in exports/ plus 1, read before export.py takes
  the lock; with one runner (version 1) it is always the number the export gets.
- The hook 2 clip's loudness is a soft check (a 3 s clip measures unreliably): a miss is a flag, not a failure.
- The caption's tone is the model's; only its rules are checked by code and the vendor lint.
- The edit review (M11) failed the test idea in all 5 rounds with scores of 3 (the director keeps asking for color
  swatch and screenshot-zoom components the library lacks), so today's reels export with NEEDS REVIEW and spend about
  70 minutes in review rounds. That is the review loop's cap working as specified, not an M12 defect.
- test-m2's dummy run calls the real claude reviewer when a dummy fails, and that fixer commits into this repo
  (it did once, correctly). A dummy that matches its schema avoids it; making test-m2 use the fake claude there is M13
  material.
- The transient classifier still waits out a 429 of another kind (a real rate limit), as the spec says.

## HUMAN_TODO items added

- M12: fill voice.md "Proof I can use" with real FlashFX facts (FlashFX solutions fail H until then).
- M12: add "## Content strategy" with the balance target to account.md.
- M12: watch the first real export (reel, hook 2 clip, captions file) before posting.
- M12: the components the visual director asks for again and again (swatch-row, color swatch card, screenshot zoom
  with a highlight box): the edit review keeps failing reels without them.

## Earlier milestones touched

M3 (ai.sh: the model-limit fallback), M11 (review/style_check.py: the analysis folder cleared, no stdin), M2 (runner.sh: the exporting #N activity and the history type; history.sh; export.py: the SOLUTION block; the dummies
and the 13/14 schemas), M4 (research, expansion, gate, angle: code, prompts, schemas, fixtures), M5 (the S5 brief
header), M6 (script_checks.py and the S7 prompts, schemas and run.sh), and the assertions of test-m2, test-m3, test-m4
and test-m6 that read what changed. DECISIONS.md 272 lists them.
