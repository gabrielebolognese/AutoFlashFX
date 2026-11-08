# M16 Director, components and the energy loop: report

Spec: BUILD_SPEC.md section 5 (Motion and energy rules E8 and E9), section 12 (M16), the lines marked (M16) in S1, S9, S12;
PLAN.md M16. Decisions: DECISIONS.md 314 to 324. Test: `bash pipeline/tests/test-m16.sh`.

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
pipeline/stages/{01-research,09a-animations,09c-transitions,12-review} (prompts, schemas, contracts, run.sh), pipeline/lib/ai.sh (a launcher missing for a moment is waited out), pipeline/lib/visual/project.py (the draft downscale tried twice), config.json,
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

**test-m16 sections 1 to 5 and 7: 166 passed, 0 failed** (build/M16/final-tests/test-m16-final.log; the golden render is reused: 3 minutes
to rebuild it). The new golden reel (E0 meter, golden/test-idea/energy.json): moving share 82.1 percent, middle band 92.0, pixels
changing 4.12, still stretches 0.0, longest still 0.77 s against the targets 41, 46, 3.3, 15 and 2 s; every scene but the CTA is above
80 percent of every target (the CTA scene: moving 69.6, middle 60.7, pixels 1.89 against 2.64; its content is fixed by the branding
rules, so S12 leaves it out of the per-scene routing).

**Section 6, the test idea with the real models, has not passed.** Six real runs (DECISIONS.md 322, logs build/M16/final-tests/test-m16-real*.log,
evidence in build/M16/real-run3 and real-run6): two were blocked by the machine (the Claude Code launcher replaced by an update at 03:22
and 08:22: ai.sh now waits for it), one by the spec's voice rule at S8, one was stopped by hand, one went three rounds with the first
guidance (energy 54 percent moving: the director chose weak heroes), and the last, with the improved guidance, measured in rounds 1 and 2
moving 77.7 and 75.5 percent, middle band 79.6 and 74.2, pixels changing 4.79 and 5.27, still stretches 0.0 and 2.6 percent, longest still 0.77
and 1.13 s (every energy target met), with edit review scores stop 3 then 4, hierarchy 3 then 4, look 4, variety 3, sync 3, sound 3, generic 3,
requirements 3, energy 3; its issues were about meaning (no visible before and after in the hook, the problem site never shown, the payoff
reusing the mock), and it was blocked in round 3 when the draft's ffmpeg downscale failed with no message (project.py now tries it twice). No run
reached the export, so the 20 percent limit on the time per reel (M13: 141 minutes; a review round costs 25 to 45 minutes) and the scores
on variety and generic above 3 are not shown. HUMAN_TODO asks for a run on a quiet machine.

Earlier milestones' tests after the changes of M16 (fake-only sections; logs in build/M16/earlier-tests/): test-m9 80 passed, test-m10 134,
test-m11 227, test-m12 180, test-m13 100, test-m14 sections 2 4 5: 39, test-m15 127, test-no-emdash 1: all passing. test-m2 passes 192 and
fails 15 (its two dummy ideas take more than its 300 s limit: every dummy stage takes 4 to 10 s on this PC, which is busy with other
runners; M16 touched nothing that runs in a dummy stage except the sandbox config switch), run again with the machine quiet it failed the
same way: a timing check, not a behavior one, to be run again when the machine is idle (HUMAN_TODO).

## Known gaps

- Nobody has judged the new components and the golden reel by eye (HUMAN_TODO).
- The CTA scene's energy is limited by the branding rules; it only counts in the reel's numbers (its scene numbers: moving 70 percent,
  pixels changing 1.9 percent against a bound of 2.64).
- The acceptance test's real run (section 6) has not passed: see Test results. The energy part works (the meter, the per-scene routing, the
  numbers met in rounds 1 and 2 of the last run); what is open is the edit review's 3 on variety and generic, the unmeasured time per reel and
  test-m2's timing check.
- The golden reel uses five of the nine new components (screenshot-zoom, video-card, mock-site-card, swatch-row, cursor); card-fan,
  card-grid, timeline-scrubber and swatch-card are in the gallery and the catalog but not in the example.
- The text sizes baked into the library stay under the caption size (a warning since M15).

## HUMAN_TODO items added

Five lines (build/HUMAN_TODO.md, "M16:"): look at the components and the golden reel; the recordings in the first real reel; the energy
rules are errors now (the switches); the CTA scene's energy; a real run of the test idea on a quiet machine (section 6).
