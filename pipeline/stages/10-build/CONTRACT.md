# 10-build: Build visuals and draft render (S10)

Built in M10. Spec: BUILD_SPEC.md section 5, S10; DECISIONS.md 215 to 232.

## Purpose
The merged visual plan compiled into a HyperFrames project built from the motion library (captions per the style,
tokens.json as CSS variables, the logos as image files with their aspect ratio locked, 3D through hero-3d only
where the style allows and only when WebGL works here), checked, measured for its sound events, rendered as a
silent draft at 540x960 with the hook 2 alternate clip, and summarized in a contact sheet. The builder model is the
repair step when the check fails.

## Inputs
- 09a-animations/plan.json, 09b-text/plan.json, 09c-transitions/plan.json (merged by pipeline/lib/visual/plan_merge.py)
- 07-script/script.json, 08-voiceover/words.json and words_hook2.json, 01-research/assets/, library/brand/
- motion-lib/ (compositions, assets, catalog.json, webgl.json), styles/paper-cards/tokens.json, node_modules/hyperframes

## Outputs (in runs/<id>/10-build/)
- events.json is the primary output (schema.json): duration_ms, fps, counts, verified {checked, changed, failed},
  timeline_check, events[] with ms, frame, type (the move's event: enter, pop, exit, typing, count_start, strike,
  check, notification, word, caption_word, scene_change ...), cue (the catalog's cue type, transition, or null),
  component, instance, scene, beat, el, scene_change, transition_ms (and transition_type, from_scene,
  next_beat_type on a scene change), verified. Read by S11 (the sound pass) and S12.
- plan.json: the merged plan as compiled (the transitions as exit props); build.json: the builder role, the WebGL
  verdict, the check result, the render numbers, the flags.
- project/ (the HyperFrames project: index.html, compositions/, assets/, instances.json), check.json
- draft.mp4 (540x960, 30 fps, silent, the plan's length within 0.2 s), render.json
- hook2/ (the alternate clip's project and plan.json), hook2.mp4 (3.5 s at most), render-hook2.json
- contact-sheet.png (one still per beat plus the breath)
- stage.log; prompt-repair-r<n>.md and calls/ when the builder repaired the project

## Invariants
- `npx hyperframes check --json` reports no error on project/ (warnings are allowed)
- events.json matches what is on screen: every event that starts a visible change is verified by a seek one frame
  before and one after in the harness (pipeline/lib/visual/events.py); every host starts where the plan says
  (`npx hyperframes timeline --json`)
- logos come only from brand.json or the research assets, placed as images (object-fit contain), never redrawn
- WebGL missing (motion-lib/webgl.json webgl false): 3D beats become 2D cards and the run is flagged NEEDS REVIEW
- the builder model edits only the project folder (its working directory); candidates for motion-lib/candidates/
  are not written in this version (DECISIONS.md)

## Exit codes
0 done, anything else a code error (the check still failing after config visual.build_fix_rounds repairs, a render
failure, a validator failure of the merged plan).

## Model and session
The builder repair call: config models.builder (sonnet), or models.builder_escalation (opus; fable only on an idea
marked [important], DECISIONS.md 324) when the plan has
config visual.three_d_heavy_objects 3D objects or more, or state.json rounds.review is 2 or more (S12's rounds,
M11). Fresh session per repair round, tools Read, Glob, Grep, Edit, Write and `npx hyperframes` in the project
folder, timeout timeouts.build_seconds. No call when the check passes at once.

## dummy.sh
Writes a small valid events.json, an empty project/ and hook2/, draft.mp4 and hook2.mp4 placeholders; honors the
planted REELS_DUMMY_* lists.
