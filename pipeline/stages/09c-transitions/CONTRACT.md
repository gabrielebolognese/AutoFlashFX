# 09c-transitions: Visual plan, transitions pass (S9c)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M10
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S9c.

## Purpose
How each scene leaves and the next arrives, with its duration, following the style's transition rules (allowed types, frequency, hard cuts versus motion).

## Inputs
- 09a-animations/plan.json, 09b-text/plan.json
- styles/paper-cards/tokens.json (transition rules)

## Outputs (in runs/<id>/09c-transitions/)
- plan.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- plan.json: pass transitions, transitions (from, to, type, duration_ms)
- the merged plan is validated by pipeline/lib/plan_validate.py against tokens.json
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- only the style's allowed transition types
- the merged plan passes every rule of BUILD_SPEC.md S9

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh session. Model: config models.visual_director.

## dummy.sh
`bash pipeline/stages/09c-transitions/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
