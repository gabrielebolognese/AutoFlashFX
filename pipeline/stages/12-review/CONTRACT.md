# 12-review: Review and fix loop (S12)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M11
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S12.

## Purpose
Mechanical checks with Puppeteer at every beat and emphasis time, style conformance with tools/analyze_refs.py against the reference analysis, audio checks, then the edit review by a fresh qa session scoring 1 to 5 on eight criteria with tagged issues. Issues route back to the step that owns them.

## Inputs
- 10-build/project/, 11-sfx/draft_mixed.mp4 and sound-map.txt
- styles/paper-cards/tokens.json and analysis/
- 07-script/script.json, 08-voiceover/words.json

## Outputs (in runs/<id>/12-review/)
- review.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- review.json: round, mechanical, style, audio, edit_review (scores, issues with tags), pass
- contact sheet, filmstrips and the check reports next to it
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- pass when every score is at least 4
- issues carry [voice], [animation], [text], [transition] or [sfx]
- caps: 3 Opus rounds, 2 Fable rounds, then export with NEEDS REVIEW (never stop)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh qa session per round (never the builder). Model: config models.qa.

## dummy.sh
`bash pipeline/stages/12-review/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
