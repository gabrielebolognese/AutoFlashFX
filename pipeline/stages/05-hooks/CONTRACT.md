# 05-hooks: Hooks (S5)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M5
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S5.

## Purpose
Pick 12 to 20 hook templates from at least 3 families (weighted by win rate once there is data) and write each hook: a spoken line (8 words or fewer, under 3 s at the user's wpm), an on-screen line (6 words or fewer) and a concrete marker. Then write brief.md, and session A's job ends.

## Inputs
- library/.hooks.index.json, library/.hooks.stats.json (built by pipeline/bin/index-hooks)
- pipeline/vendor/ig-agent-skill/hooks.json (26 formulas, extra shapes)
- 02-expansion/expansion.md, 01-research/facts.md, library/profile/voice.md

## Outputs (in runs/<id>/05-hooks/)
- hooks.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- hooks.json: the chosen templates and the filled hooks (id, template_id, family, spoken, on_screen, marker)
- brief.md: 2 to 3 thousand tokens, everything the script needs
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- 12 to 20 hooks from at least 3 families
- spoken 8 words or fewer and under 3 s at voice.wpm
- on-screen 6 words or fewer
- every hook has a named tool, a number or a time
- no em dash

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Session A resumed. Model: config models.research.

## dummy.sh
`bash pipeline/stages/05-hooks/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
