# 07-script: Script (S7)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M6
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S7.

## Purpose
Write two drafts in two tones (hook, stake, body beats with a type each, payoff, one ask that repeats a hook word), cut about 20% of the words, run every scripted check, pick the draft a friend would hear out loud, up to 3 rewrite rounds. Fresh session D, model script; cut pass with model cut.

## Inputs
- 05-hooks/brief.md, 06-judge/judge.json (hook 1), 01-research/facts.md
- library/profile/voice.md and pronunciations.txt, the style's beat map, the length rules in tweaks.md

## Outputs (in runs/<id>/07-script/)
- script.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- script.json: tone, video_type, target_seconds, beats (id, type, display, spoken, emphasis, card of 6 words or fewer), ask (keyword and line), the check results
- drafts and check reports next to it (draft-a.json, draft-b.json, checks-*.json)
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- 25 to 40 s, or 45 to 75 s for list and explainer videos; words = seconds x wpm / 60
- beats.py, humanize.py then detect.py PASS, zero {{placeholders}}, every claim in facts.md, one ask
- hard failures after 3 rounds block (exit 20); soft failures continue with a NEEDS REVIEW flag

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
Fresh session D. Models: config models.script, models.cut, models.checks.

## dummy.sh
`bash pipeline/stages/07-script/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
