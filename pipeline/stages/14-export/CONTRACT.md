# 14-export: Caption and export (S14)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M12
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S14.

## Purpose
Write the caption from the brief and the script (first line the hook in 125 characters or fewer, one ask, at most 5 hashtags), lint it with the vendor caption.py and humanize.py, and hand the runner everything the export needs. The runner's export step (pipeline/lib/export.py) then numbers, assembles and moves.

## Inputs
- 05-hooks/brief.md, 07-script/script.json, 06-judge/judge.json, 01-research/research.json
- 13-render/final.mp4 and hook2.mp4, state.json flags (NEEDS REVIEW)
- library/profile/deliverables.txt

## Outputs (in runs/<id>/14-export/)
- export.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- export.json: caption, hashtags (5 or fewer), keyword, deliverable, deliverable_status, link, hooks (hook1, hook2), needs_review, facts (claim, url, checked), files (reel, hook2: the rendered videos)
- the runner renders exports/N/Ncaptions.txt from export.json in the format of BUILD_SPEC.md section 8 (the number N exists only at export time) and moves N.mp4, Ncaptions.txt and Nhook2.mp4 into exports/N/
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- caption first line = hook 1, 125 characters or fewer
- one ask, at most 5 hashtags, no em dash
- NEEDS REVIEW lists every flag in state.json; the section is left out when there is none

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Model: config models.script for the caption text (one call).

## dummy.sh
`bash pipeline/stages/14-export/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
