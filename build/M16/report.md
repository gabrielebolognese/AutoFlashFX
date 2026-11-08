# M16 Director, components and the energy loop: report

Spec: BUILD_SPEC.md section 5 (Motion and energy rules E8 and E9), section 12 (M16), the lines marked (M16) in S1, S9, S12;
PLAN.md M16. Decisions: DECISIONS.md 314 to 320. Test: `bash pipeline/tests/test-m16.sh`.

## What was built

- **Nine components on pc-motion.js**, each with a catalog entry (beats, sound events, demo props), frame-match expectations, a gallery
  still and a play page: `screenshot-zoom` (a camera over a real page: focus boxes as fractions of the page, 18-frame power3.inOut travel,
  a highlight box that draws itself, a creep between points), `video-card` (a recording or clip playing in a window or a bare frame, drawn
  from the hf-seek time through `waitUntil`, `clip_start` like the 3D components), `card-fan`, `card-grid`, `timeline-scrubber`, `cursor`,
  `mock-site-card`, `swatch-row`, `swatch-card`. The moves they share are PCM.move, run, appear, vanish, pulse, press, glideProp and readout
  in pc-motion.js (test-m14 bans a tween in a composition). `end-card` gained an optional confetti (`confetti_count`, default none).
- **S1's page recordings**: pipeline/lib/screenshot.py records a 5 to 8 s scroll video next to every screenshot that scrolls (NN-name.mp4,
  H.264, 1080 wide, 30 fps, no sound, a key frame every 6 frames so a render can seek it); assets.json carries `recording` and
  `recording_seconds`; the visual stages list them (`research/<file>.mp4` in a video prop). motion/demo_assets.py builds the demo clips of
  the library and the recordings of the frozen test run's screenshots when they are missing (*.mp4 is not in git).
- **The validator rules of E9** (visual/plan_validate.py): hero_motion, hero_fill, layers, camera, hook_frame0, empty_paper, list_entry,
  transition_variety, and the warning real_motion; numbers in tokens.json motion.grammar.composition; config visual.energy_rules error,
  warn or off. Two are also repaired by the pipeline (plan9.hook_moves_from_frame0, plan9.vary_transitions).
- **The 9a and 9c prompts** rewritten around the rules (what the validator checks, the levers, a hold level per scene, recordings and
  zooms first, stacks and fans for lists, varied transitions); the assets digest lists the recordings.
- **The new golden reel** (golden/test-idea, planned by hand in pipeline/lib/motion/goldenplan.py): measured with the E0 meter its numbers
  are in golden/test-idea/energy.json; every target is met and every scene except the CTA reaches 80 percent of each (the CTA is exempt,
  see below).
- **S12**: the energy check first (review/energy_check.py: the reel and every scene against tokens.json energy, a failing scene an
  [animation] issue with its numbers routed to 9a, the ask scene left out of the per-scene routing), the liveness checks in the mechanical
  step (review/liveness.py: no element static for 0.5 s, the edge layer present; and a clip-aware visible rect in mechanical.py: an
  element inside an overflow:hidden ancestor is judged where it shows), the ninth edit-review score `energy`, the early stop (verdict
  `stop`), the review.json schema and the contract updated.
- **Tests**: pipeline/tests/test-m16.sh with m16-lib.py (each component's behavior in the harness), m16-recording.py (S1), m16-plans.py
  (the golden plan passes, one planted plan per rule fails, the levels), m16-review.py (S12), sandbox-config.py (see below).

## Files

New: motion-lib/compositions/{screenshot-zoom,video-card,card-fan,card-grid,timeline-scrubber,cursor,mock-site-card,swatch-row,swatch-card}.html,
pipeline/lib/motion/demo_assets.py, pipeline/lib/review/{energy_check,liveness}.py, pipeline/tests/{test-m16.sh,m16-lib.py,m16-plans.py,
m16-recording.py,m16-review.py,sandbox-config.py}, golden stills of the nine under motion-lib/gallery/stills/.
Changed: motion-lib/assets/pc-motion.js, motion-lib/compositions/end-card.html, motion-lib/{catalog.json,gallery/,index.html},
pipeline/lib/{screenshot.py,research.py,tokens.py}, pipeline/lib/motion/{catalog,expectations,framematch,gallery,golden,goldenplan,harness,common}.py,
pipeline/lib/visual/{common,plan9,plan_validate,events}.py, pipeline/lib/review/{mechanical,route,edit,__main__}.py,
pipeline/stages/{01-research,09a-animations,09c-transitions,12-review} (prompts, schemas, contracts, run.sh), config.json,
styles/paper-cards/tokens.json and motion-lib/assets/tokens.css (regenerated), golden/test-idea/, pipeline/tests/{lib.sh,test-m11.sh},
CLAUDE.md, DECISIONS.md, build/progress.md, build/HUMAN_TODO.md.

## Earlier milestones touched (M16 depends on them)

M9 (harness.py and gallery.py wait for waitUntil promises, catalog.py, expectations.py, frame-match keeps the other components' results
under --only, goldenplan.py, golden.py, end-card.html, tokens.py), M10 (visual/common.py, plan9.py, plan_validate.py, events.py),
M11 (review/mechanical.py, route.py, edit.py, the 12-review stage), M12 (research.py, screenshot.py), tests/lib.sh (the sandbox turns the
energy rules, the energy check, the liveness checks and the early stop off for the milestones before M16: SANDBOX_ENERGY=on keeps them
on) and test-m11 (the scores line gained `, energy 5`).

## How to run the test

`M16_SECTIONS="1 2 3 4 5 7" bash pipeline/tests/test-m16.sh` (no model call, about 35 minutes, the golden render is reused when
golden.mp4 is newer than the plan and the library; `M16_RERENDER=1` forces it); `M16_SECTIONS=6 bash pipeline/tests/test-m16.sh` is the
test idea with the real models (2 to 4 hours).

## Test results

(filled in below by the final runs)

## Known gaps

- Nobody has judged the new components and the golden reel by eye (HUMAN_TODO).
- The CTA scene's energy is limited by the branding rules; it only counts in the reel's numbers (its scene numbers: moving 70 percent,
  pixels changing 1.9 percent against a bound of 2.64).
- The golden reel uses five of the nine new components (screenshot-zoom, video-card, mock-site-card, swatch-row, cursor); card-fan,
  card-grid, timeline-scrubber and swatch-card are in the gallery and the catalog but not in the example.
- The text sizes baked into the library stay under the caption size (a warning since M15).

## HUMAN_TODO items added

Four lines (build/HUMAN_TODO.md, "M16:"): look at the components and the golden reel; the recordings in the first real reel; the energy
rules are errors now (the switches); the CTA scene's energy.
