# 06-judge: Hook judge (S6)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M5
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S6.

## Purpose
Filter the hooks with the vendor hookscore.py (drop dealbreakers and scores under 50; fewer than 4 left makes S5 regenerate once), then the judge model ranks them twice with different shuffles (Borda merge) and compares the top 4 pairwise in both orders. Fresh session C, model judge.

## Inputs
- 05-hooks/hooks.json
- pipeline/vendor/ig-agent-skill/hookscore.py
- library/profile/voice.md
- library/.hooks.stats.json

## Outputs (in runs/<id>/06-judge/)
- judge.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- judge.json: winner (hook 1), runner_up (hook 2, the alternate clip), reasons, filtered_out, rankings
- library/.hooks.stats.json updated (picked, won, judge scores) by the bash wrapper, never by the model
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- criteria: stops the scroll, sets up the problem, credible, fits the voice
- winner and runner-up are different hooks from hooks.json

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh session C. Model: config models.judge (about 3 calls).

## dummy.sh
`bash pipeline/stages/06-judge/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
