# M9 Motion library: build report (2026-11-01)

## What was built

1. **tokens.json** (`bash pipeline/bin/build-tokens`, pipeline/lib/tokens.py, pipeline/lib/tokens.schema.json):
   styles/paper-cards/tokens.json derived from style.md plus tweaks.md by explicit rules (one regex per field over the
   markdown with its wrapped lines joined), with a cross-check that every number and hex in it appears in the two
   source files, the in-force tweaks.md lines winning and PROPOSED lines ignored until the word is removed (an accepted
   proposal changes the tokens by itself), the 15 open questions of style.md decided with the DECISIONS.md 32 rule
   and recorded in the file, the tracker off, the beat map for the validators, and motion-lib/assets/tokens.css (the
   same values as CSS variables). No model call: the parser is deterministic (DECISIONS.md 192 to 196).
2. **The motion library** motion-lib/, a HyperFrames project: 27 components in compositions/ (the 24 items of
   vocabulary.md plus paper-canvas, the DM notification card for the CTA and hero-3d, the Three.js object through the
   hf-seek protocol), each a scene file with declared variables (props), a paused GSAP timeline, the moves of the style
   (enter, pop, fly-in, exits, count-up, typing, strike) from the shared assets/paper-cards.js and the look from
   assets/paper-cards.css over tokens.css and the five OFL fonts; vendored gsap and three; catalog.json (props from the
   declarations, beat types from tokens, sound events with frame offsets and cue types, demo props, stills,
   frame-match results); index.html, the showreel generated from the catalog (DECISIONS.md 197 to 205).
3. **Branding** (BUILD_SPEC.md 2.7, tweaks.md): dm-card (a surface card with the round avatar-dark.png at 112 px or
   more, the sender and one message line), and an image prop on every logo spot (end-card lockup, logo-tile image and
   second_image, headline kicker_mark, table-card logos) that takes a brand.json or research path and renders an
   `<img>` with object-fit contain, aspect ratio locked, never redrawn (DECISIONS.md 201).
4. **Frame-matching** (`bash pipeline/bin/frame-match`, pipeline/lib/motion/{harness,expectations,strips,framematch}.py):
   a Playwright harness mounts each component, seeks its timeline frame by frame and measures the tracked elements;
   the checks compare with vocabulary.md and style.md through tokens.json (1 frame, 10 percent, durations by curve
   fitting) and correlate the component's per-frame change curve with the reference 30 fps strips in
   styles/paper-cards/analysis (shape correlation, r >= 0.5). motion-lib/gallery/frame-match.md and .json; `--apply`
   moves failures to candidates/. All 27 pass; the 25 with a strip correlate at 0.57 to 0.99 (DECISIONS.md 206 to 209).
5. **The gallery** (`bash pipeline/bin/gallery`, pipeline/lib/motion/gallery.py): motion-lib/gallery/index.html with one
   540x960 still per component, its props, sound events, beat types, frame-match result and a Play button (an inline
   player per component), plus the showreel (DECISIONS.md 210).
6. **The WebGL test** (`bash pipeline/bin/webgl-test`, pipeline/lib/motion/webgl.py): hardware ANGLE (D3D11 on the AMD
   Radeon integrated GPU) and SwiftShader both draw the hero-3d canvas in the harness, and HyperFrames renders the 3D
   composition with `--browser-gpu` and `--no-browser-gpu`; motion-lib/webgl.json records harness_gpu hardware and
   render_flag --browser-gpu (DECISIONS.md 211).
7. **The golden reel** (`bash pipeline/bin/render-golden`, pipeline/lib/motion/{goldenplan,golden,captions}.py,
   pipeline/stages/09-plan/schema.json): golden/test-idea/plan.json (the merged plan, written from the frozen
   script.json and words.json with a hand-made design per beat: the hook headline on the spoken words and the 3D card
   landing in the breath, a hero component per body beat with an element landing on its key word, real screenshots
   labelled real, the CTA with the FlashFX DM card landing on the word TELLS and the lockup under the mascots, no
   FlashFX asset elsewhere since the solution is external), the project built from the library, `npx hyperframes
   check` passing, golden.mp4 rendered with the frozen voice (1080x1920, 30 fps, the voice's length, audio),
   contact-sheet.png and README.md (DECISIONS.md 212, 213).
8. **Node setup**: package.json at the root with hyperframes 0.8.226, gsap 3.15.0 and three 0.159.0 pinned;
   `bash pipeline/bin/setup-node` (npm ci, the vendored copies, chrome-headless-shell through `browser ensure`, the
   HyperFrames skill pack for the M10 builder sessions).

## Files

- pipeline/lib/tokens.py, pipeline/lib/tokens.schema.json, pipeline/bin/build-tokens, styles/paper-cards/tokens.json
- motion-lib/: compositions/*.html (27), assets/{paper-cards.css, paper-cards.js, tokens.css, fonts/, vendor/, brand/, demo/},
  catalog.json, index.html, hyperframes.json, meta.json, webgl.json, gallery/{index.html, frame-match.md, frame-match.json,
  stills/, play/}, candidates/ (empty)
- pipeline/lib/motion/{__main__,common,harness,expectations,strips,framematch,catalog,gallery,webgl,captions,goldenplan,golden}.py
- pipeline/bin/{frame-match, gallery, webgl-test, render-golden, setup-node}
- pipeline/stages/09-plan/schema.json
- golden/test-idea/{plan.json, project/, contact-sheet.png, README.md} (golden.mp4, check.json, render.json, probe.json and
  the project's copied fonts, vendor files and voice are rebuilt, ignored by git)
- package.json, package-lock.json; config.json (a warn-level preflight entry for tokens.json); .gitignore
- pipeline/tests/test-m9.sh; DECISIONS.md 192 to 214; build/progress.md; build/HUMAN_TODO.md; CLAUDE.md

## How to run the test

`bash pipeline/tests/test-m9.sh` (about 8 minutes: 80 checks; `M9_SECTIONS="1 2"` for the quick sections). Section 4
needs the frozen voice pipeline/tests/fixtures/runs/test-idea/08-voiceover/vo.wav, which test-m7 section 3 writes
(git ignores wav files). No model call.

## Test output (summary)

```
== 1. tokens.json from style.md plus tweaks.md ==         27 PASS (build, schema, cross-check, no-op rebuild, touched tweaks.md, accepted proposal, the repo's tokens)
== 2. the library: lint, check, catalog, logo spots, stills ==   18 PASS (lint 0 errors, check ok with the browser audits, catalog items 1 to 24 plus dm-card, aspect ratios, 27 stills)
== 3. frame-match against the style's numbers and the reference strips ==   12 PASS (27 pass, 0 fail; strip correlation 0.57 to 0.99; gallery with a still and a player per component)
== 4. the golden reel ==   17 PASS (plan validates; render 66.6 s: 1080x1920, 30 fps, 41.47 s against the 41.46 s voice, AAC; contact sheet; CTA branding)
== 5. the WebGL test ==   5 PASS (hardware ANGLE and SwiftShader both draw; HyperFrames renders 3D with --browser-gpu and --no-browser-gpu)
== 6. no em dash in the files M9 wrote ==   1 PASS
test-m9.sh: 80 passed, 0 failed (470 s)
```

frame-match.md (the run inside the test): every component passes its checks (enter 5 opacity frames, rise 38 px, 8
position frames by fit, expo.out; pops with their overshoots and frames; count-up 27 frames; typing 2 frames per
letter and 1.15 per chat character; the fall over 10 frames leaving the frame; the mascot 4 frames after the landing;
caption words over 4 frames, the chunk swap with a frame of air; the end card's 6-frame fades 6 frames apart; the 3D
shadow's 12 frames with a WebGL context), and the 25 components with a reference strip correlate at r 0.57 (stat
number, against busy count-up strips) to 0.99 (the exit fall). The golden project's `npx hyperframes check` reports
no error (its warnings: craft notes on short reads and the accent contrast, see Known gaps).

## Known gaps

- The looks have been judged by numbers and by contact sheets, never by a human eye at full speed: the card shadow
  alpha, the dot grid opacity, the mascot's pixel art, the 3D card's lighting and the exact caption box padding are
  tuned by eye only as far as a still shows (HUMAN_TODO: review the gallery and the golden reel).
- The accent orange on paper measures under 3:1 contrast (kicker, the stat unit word), as in the reference videos.
  HyperFrames' check reports it as a warning; S12's 4.5:1 rule (M11) will have to exempt accent words or the style
  changes (HUMAN_TODO).
- The reference strips (styles/paper-cards/analysis) are not in git: on another machine frame-match decides on the
  numbers alone and says so in frame-match.md.
- The strip correlation compares shapes (an ease-out decay, a pop, a plateau); it cannot tell a 7-frame enter from
  an 8-frame one. The numbers do.
- hero-3d is the one 3D object (a card, a box or an icosahedron); it is deliberately simple. Three.js r159 is the last
  UMD build, so its console prints a deprecation notice (harmless, filtered by frame-match).
- The caption-line scales a chunk wider than 620 px down instead of refusing it; the 9b validator (M10) should keep
  chunks inside the width so the scale never triggers.
- `npx hyperframes` prints a telemetry notice on every call; the tools strip it from JSON output. The first render on
  a machine downloads chrome-headless-shell (about 150 MB, slow here); setup-node does it up front.
- The gallery's inline player drives the timeline with a clock (for eyes only); renders never use it.

## HUMAN_TODO items added

- Review the gallery (motion-lib/gallery/index.html) and how to change a component.
- Review the golden reel (golden/test-idea/golden.mp4, contact-sheet.png) and how to change its design.
- Accept or change the open-question defaults (DECISIONS.md 194): remove the word PROPOSED in tweaks.md to accept a
  proposal; build-tokens follows.
- The accent contrast warning and the HyperFrames telemetry notice.

## Earlier milestones touched

config.json (M1: the warn-level tokens.json preflight entry), .gitignore (M0). No stage code changed.
