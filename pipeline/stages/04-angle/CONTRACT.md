# 04-angle: Angle research (S4)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M4
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S4.

## Purpose
When the gate fails on P, S or C: research more, rewrite expansion.md with a better angle that keeps the idea's core topic, then the idea goes back to S3. Skipped unless the gate asks for it.

## Inputs
- 03-gate/gate.json (the failing scores and the evidence)
- 01-research/facts.md
- 02-expansion/expansion.md

## Outputs (in runs/<id>/04-angle/)
- angle.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- angle.json: round, previous_scores, change (what the new angle does differently), keeps_core_topic
- 02-expansion/expansion.md and expansion.json rewritten
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- the core topic stays; if only a different topic works the stage says so and the gate drops the idea
- at most caps.angle_rounds rounds per idea (state.json rounds.angle)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Session A resumed. Model: config models.research.

## dummy.sh
`bash pipeline/stages/04-angle/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
