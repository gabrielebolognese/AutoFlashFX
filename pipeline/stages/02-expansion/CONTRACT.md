# 02-expansion: Expansion (S2)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M4
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S2.

## Purpose
Turn the researched idea into the viewer's problem and the solution, the share driver, the comment keyword with its deliverable, the one specific true thing and the evidence lines (BUILD_SPEC.md S2).

## Inputs
- 01-research/facts.md, research.json
- library/profile/deliverables.txt (KEYWORD | what they get | link)
- library/profile/account.md

## Outputs (in runs/<id>/02-expansion/)
- expansion.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- expansion.json: problem, solution, share_identity, takeaway, keyword, deliverable, deliverable_status (existing or new), one_true_thing, evidence (pointers into facts.md)
- expansion.md: the same as prose, 500 to 1500 characters
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- the problem is one first-person sentence
- the share driver names a specific identity
- a deliverable not in deliverables.txt is concretely described and marked NEW
- every evidence line points to facts.md

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Session A resumed. Model: config models.research.

## dummy.sh
`bash pipeline/stages/02-expansion/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
