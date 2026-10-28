# M14 Motion grammar and energy meter: build report (2026-11-07)

The lines of BUILD_SPEC.md marked (M14) and the Motion and energy rules E0, E1, E2, E5, E6 and E7 at the motion
library level. The reels' look stays the style's: every number of the look still comes from style.md and tweaks.md
through tokens.json; the motion grammar adds the phases, curves, edges, background life and depth on top of it.

## What was built

1. **The energy meter, E0** (pipeline/lib/review/energy.py, `python pipeline/lib/review energy <video> [--plan
   merged.json] [--out energy.json]`). 30 fps, 108x192 grayscale, the mean absolute change per frame; frozen, subtle,
   medium and big frames; the moving share, the middle band, the pixels changing, the still stretches (frames below
   medium, 1 s or more) and the longest still, for the whole video and scene by scene. `energy calibrate` measured the
   nine references into styles/paper-cards/analysis/energy.json. The M13 reel measures 15.9, 15.1, 1.21, 31.9 percent
   and 2.8 s (the spec: 16, 15, 1.2, 29, 2.8) and fails every target; the meter reproduces the reference numbers
   exactly on a second run.
2. **tokens.json `motion.grammar` and `energy`** (pipeline/lib/tokens.py, TOKENS_VERSION 2, the schema). The grammar
   holds the spec's values (the combined main animation, the inertia, the three hold levels, the exit, the edge and
   ambient layers, the camera and depth, the mascot idle, E3 and E4's numbers for M15, E8's for M16, the text zones
   derived from the zones); the energy targets are 70 percent of the look references' medians for the lower bounds
   (41, 46, 3.3) and the medians rounded up to 5 percent and 0.5 s for the upper bounds (15, 2), overridable by an
   `- **Energy:** ...` line in tweaks.md. motion-lib/assets/tokens.css exposes them as `--m-*`.
3. **motion-lib/assets/pc-motion.js, the shared grammar.** PCM.life gives every element the four phases of E1 (the
   style's measured main animation, 2 to 4 s of decelerating inertia on the closed-form glide curve, the calm, normal
   or lively hold, the exit) with the combined zoom and 3D parallax rotation of E2 (the rotation 3 frames late), a
   per-element perspective, PCM.depth for the 2.5D parts (E6), PCM.canvas for the edge filler and the ambient layer
   (E5, E7), PCM.idle for the mascot, PCM.camera, PCM.bubble, PCM.confetti, PCM.grow, PCM.draw, PCM.scroll, PCM.wobble
   and setter-driven count-ups and typing (HyperFrames seeks GSAP timelines with events suppressed, so nothing relies
   on a callback any more). All 28 compositions were rewritten on it: no composition keeps a tween, an ease or an
   onUpdate of its own (test-m14 greps for them); every element component has a `hold` prop.
4. **paper-canvas with life.** A timeline, `seed` and `duration` props (golden.py seeds it from the idea id and runs it
   for the reel's length; the showreel uses seed 7), 6 edge elements 30 to 70 percent outside the frame at most 20 px
   per second, 16 ambient stars, dots and clouds drifting and twinkling, all out of the text zones and carrying no text.
5. **icon-3d.** A Three.js extrusion of an SVG path (a small parser) or a primitive, low poly, turning slowly from the
   hf-seek time on the WebGL backend of webgl.json, with the CSS-extruded fallback (8 to 16 depth layers under a
   turning stage) and `mode` auto|webgl|css; kind 3d with `fallback: css` (S10 never replaces it); allowed in the hook
   and the ask beats (tweaks.md's 3D line).
6. **frame-match** (pipeline/lib/motion/framematch.py, expectations.py, harness.py): every component measured for
   4.33 s; the fits read their end at the expected landing and positions from the element's own translation; the life
   checks (never static for 0.5 s on any visible tracked element, the inertia ending 2 to 4 s after the landing, the
   pixels of a canvas); each component's energy measured alone (catalog.json `energy`, the gallery's energy line); the
   strip correlation finds the reference move anywhere in the move's frames; quarter-scale screenshots (12 minutes
   for the 28 components instead of over 30).
7. **The golden reel rendered again from the same plan**: moving share 13.0 to 28.1 percent, middle band 12.0 to
   29.8, pixels changing 1.0 to 1.6, still stretches 49.5 to 29.9 percent, longest still 2.8 to 2.43 s
   (golden/test-idea/energy.json against build/M14/golden-energy-before.json).

## Files

- New: pipeline/lib/review/energy.py, motion-lib/assets/pc-motion.js, motion-lib/compositions/icon-3d.html,
  pipeline/tests/test-m14.sh, styles/paper-cards/analysis/energy.json (not in git: analysis/ is ignored),
  golden/test-idea/energy.json, build/M14/golden-energy-before.json, build/M14/report.md.
- Rewritten: every file in motion-lib/compositions/ (28), motion-lib/assets/paper-cards.js (the moves delegate to
  pc-motion.js, the mascot's eyes and prop are groups), pipeline/lib/motion/framematch.py, expectations.py.
- Changed: pipeline/lib/tokens.py and tokens.schema.json (grammar, energy, the css variables, the calibration as a
  third source), styles/paper-cards/tokens.json and motion-lib/assets/tokens.css (rebuilt), pipeline/lib/review/__main__.py
  (the energy command), pipeline/lib/motion/{harness,catalog,gallery,golden,strips}.py, motion-lib/catalog.json,
  index.html, gallery/ (stills, index.html, frame-match.md and .json), motion-lib/assets/paper-cards.css (the layers),
  pipeline/lib/visual/{project,common,plan_validate,plan9,events}.py and pipeline/lib/review/mechanical.py (icon-3d as
  hero-3d; the css fallback never replaced), pipeline/tests/test-m9.sh (the sandbox re-proposes the accepted lines),
  pipeline/tests/fixtures/runs/test-idea/10-build/{project,hook2}/index.html (the canvas host), DECISIONS.md 288 to
  300, CLAUDE.md, build/progress.md, build/HUMAN_TODO.md.
- Earlier milestones touched (M14 depends on them): M9 (the test's sandbox, harness, golden.py, gallery.py,
  catalog.py), M10 (project.py, visual/common.py, plan_validate.py, plan9.py, events.py, the frozen index.html),
  M11 (mechanical.py). Their fake-only tests were run again (below).

## How to run the test

`bash pipeline/tests/test-m14.sh` (no model call; about 35 minutes: frame-match on the 28 components and the golden
render; `M14_SECTIONS="1 3"` are the quick sections, about 3 minutes). Sections: 1 the meter, the calibration and the
tokens; 2 the library (frame-match with the life checks, the catalog, no tween outside pc-motion.js, lint, check, the
gallery); 3 icon-3d with WebGL and with its fallback, the canvas layers for three seeds; 4 the golden reel again; 5 the
em dash scan. The recorded full run: build/M14/test-m14.log (71 passed, 0 failed, 37 minutes).

## Test output, in short

- Section 1: the nine references reproduced with a worst difference of 0.0; the M13 reel fails all five targets and
  measures the spec's numbers; tokens.json energy.targets 41, 46, 3.3, 15, 2 from the calibration; the Energy line
  overrides; the tokens validate and verify.
- Section 2: frame-match 28 pass (every main animation within 1 frame and 10 percent of its reference numbers, every
  strip at r 0.62 or more, no still window of 0.5 s on any visible element, the inertia 2.0 to 2.6 s on the main
  elements); catalog.json with icon-3d approved and every component's energy; lint and check clean (the same craft and
  contrast warnings as M9).
- Section 3: icon-3d draws with WebGL (data-webgl 1, 16 percent of its area) and with the fallback (data-webgl 0,
  12 layers, turning); the layers for three seeds stay out of the text zones over 40 s, hold no text, sit 30 to 70
  percent outside and move under 20 px per second.
- Section 4: the golden builds, checks and renders in about 2 to 3 minutes; every energy measure better than before, the moving
  share doubled (13.0 to 28.1).
- The full run: 71 passed, 0 failed (section 1: 25, section 2: 24, section 3: 10, section 4: 11, section 5: 1).
  Earlier partial runs (build/M14/tmp/) found the fit's end frame, the bar baseline and the caption chunk's first frame,
  all fixed before the full run.
- Earlier milestones, fake-only tests after the changes: test-m10 sections 1 and 2, 134 passed (run once before the
  last component touches and again after); the others are listed in build/progress.md with their counts.

## Found on the way

- The caption line still sat at y 1480 although the user accepted the caption position of 1332 on 2026-11-07 (the
  tokens, tokens.css and the review followed, the component's default did not): every reel's captions would have
  failed S12's band check. caption-line now takes the style's position from tokens.css unless the plan gives one
  (DECISIONS.md 301). Found by the M11 fake test's rerun; the fixtures and the golden were rebuilt.
- The same acceptance left the CTA's DM card (y 1305) ending below the safe bottom once the caption band's exception
  was gone: the director's default, the golden plan, the fixtures and the frozen run now place it at y 1266 with the
  lockup at 1146, and the validator's CTA exemption follows the band exception (DECISIONS.md 302). The window card's
  screenshot scrolls by its object-position (the image box stays inside the window; the review's off-canvas rule had
  flagged the transformed image).

## Known gaps

- The golden still misses every energy target: the holds the spec prescribes (2 to 8 px per second) are subtle at
  108x192 by construction; they removed the frozen frames and halved the still stretches, the moving share comes from
  entrances, exits and the scrolling screenshots. M15 (caption words moving on every frame, groups as the graphic) and
  M16 (content motion, the camera every third scene, layered scenes, the energy loop in the review) are where the
  targets are meant to be met.
- Small components rendered alone (chips, the pop, a badge, a strike) show pixel-still stretches of 2 to 4 s at
  108x192 although their transforms move every frame; frame-match reports it as a warning, not a failure, and the
  gallery shows the numbers.
- icon-3d stays in the hook and the ask beats until the user relaxes tweaks.md's 3D line (HUMAN_TODO).
- The gallery stills were regenerated once; nobody has looked at the new motion by eye (HUMAN_TODO).
- frame-match takes about 12 minutes (130 frames per component); the M9 test, which runs it too, grew by as much.

## HUMAN_TODO items added

- M14: look at the gallery and the golden with the new grammar (tilt amounts, hold speeds, the edge layer's opacity).
- M14: the energy targets and the `- **Energy:** ...` override line in tweaks.md.
- M14: 3D icons in body scenes need the 3D line of tweaks.md relaxed (E6).
