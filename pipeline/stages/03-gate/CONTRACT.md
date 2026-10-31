# 03-gate: Idea gate (S3)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M4
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S3.

## Purpose
Score the expansion 0 to 3 on P (problem to solution), S (share driver), C (comment trigger) and check F (every claim the reel will make is in facts.md and the core fact is verified). Fresh session B, model gate.

## Inputs
- 02-expansion/expansion.md and expansion.json
- 01-research/facts.md

## Outputs (in runs/<id>/03-gate/)
- gate.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- gate.json: round, scores P S C, F (ok or fail), pass, decision (pass, angle or drop), quoted evidence, reason
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- pass: P, S and C at least 2 and F ok
- P, S or C failing: decision angle, at most caps.angle_rounds (2) rounds, then drop
- F failing: drop immediately
- an angle on a different topic drops the idea and writes logs/suggested-ideas.txt (never ideas.txt)
- the runner acts on decision: angle reopens 04-angle and 03-gate (state.py reopen), drop exits 10

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh session B every round. Model: config models.gate.

## dummy.sh
`bash pipeline/stages/03-gate/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
