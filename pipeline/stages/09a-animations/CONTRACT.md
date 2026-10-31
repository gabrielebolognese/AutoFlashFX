# 09a-animations: Visual plan, animations pass (S9a)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M10
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S9a.

## Purpose
Scenes and their components per beat: start and end ms snapped to word boundaries, the component (from motion-lib only) and its props, entrance and exit, emphasis hits, set pieces, honesty labels. Fresh visual_director session.

## Inputs
- 07-script/script.json, 08-voiceover/words.json
- styles/paper-cards/{style.md,tweaks.md,tokens.json,vocabulary.md}
- motion-lib/catalog.json with stills, golden/ plan and contact sheet, 01-research/assets/

## Outputs (in runs/<id>/09a-animations/)
- plan.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- plan.json: pass animations, scenes (id, beat, start_ms, end_ms, component, props, enter, exit, emphasis_hits, set_piece, honesty_label)
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- components only from motion-lib (or a candidate flagged NEEDS REVIEW in S10)
- timings snap to words.json
- one validator retry with the errors, then the review path

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh session per pass. Model: config models.visual_director.

## dummy.sh
`bash pipeline/stages/09a-animations/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
