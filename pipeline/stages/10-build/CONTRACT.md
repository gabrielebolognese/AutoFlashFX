# 10-build: Build visuals and draft render (S10)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M10
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S10.

## Purpose
A HyperFrames composition made from motion-lib components (captions per the style, tokens as CSS variables, Three.js only where allowed), events.json with every sound event in absolute ms, the hook 2 alternate clip (3.5 s at most) and a silent full-resolution draft render. Model builder (Opus), builder_escalation (Fable) for 3D-heavy plans or after 2 failed review rounds.

## Inputs
- the three 09 plans, 07-script/script.json, 08-voiceover/words.json
- motion-lib/, styles/paper-cards/tokens.json

## Outputs (in runs/<id>/10-build/)
- events.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- project/ (the HyperFrames project), hook2/ (the alternate clip project)
- events.json: duration_ms, events (ms, type, component, scene, scene_change, transition_ms)
- draft.mp4: silent draft at full resolution
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- npx hyperframes lint and check --json pass
- a new component goes to motion-lib/candidates/ with a NEEDS REVIEW flag
- events.json matches what is on screen (checked by the M10 test)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh builder session per build round. Models: config models.builder, models.builder_escalation.

## dummy.sh
`bash pipeline/stages/10-build/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
