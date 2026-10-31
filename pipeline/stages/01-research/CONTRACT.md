# 01-research: Research (S1)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M4
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S1.

## Purpose
Get the facts right as of today (not virality: the user validated the idea before writing it). Session A, model research. Tools: WebSearch, WebFetch, Bash for the gh CLI and pipeline/bin/screenshot.

## Inputs
- the idea text (<run>/idea.txt, state.json idea.text)
- library/profile/account.md (topics in and out)

## Outputs (in runs/<id>/01-research/)
- research.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- research.json: idea_id, checked date, claims (each with url and checked date), numbers, pitfalls, one_true_thing candidates, assets list
- facts.md: every claim with its source URL and the date checked, primary sources first
- numbers.json: stars, versions, prices, dates, each with its source
- assets/ plus assets.json: screenshots of the real pages (Playwright, 1080 px wide) with URL and date
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- never invent anything; a key fact that cannot be verified is said to be unverified
- primary sources first: official repo and docs, then the vendor's blog, then press, forums last
- no getting around sites that block automated access

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Session A (shared with S2, S4 and S5, resumed with --resume). Model: config models.research.

## dummy.sh
`bash pipeline/stages/01-research/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
