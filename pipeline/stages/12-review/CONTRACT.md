# 12-review: Review and fix loop (S12)

Built in M11 (the folder set, the first schema and dummy.sh came from M2). Spec: BUILD_SPEC.md section 5, S12;
DECISIONS.md M11. Code: pipeline/lib/review/{common,mechanical,style_check,audio_check,filmstrip,edit,route}.py behind
`python pipeline/lib/review <command>`; the prompt pipeline/stages/12-review/prompt.md with model.schema.json.

## Purpose
One review round of the complete draft: the energy check (M16: no model; the reel and every scene against tokens.json energy, a
failing scene back to 9a with its numbers), the mechanical checks on the built composition, the style conformance check
on the mixed draft, the audio checks, then the edit review by a fresh qa session; a verdict that passes the reel to
the render or sends each issue back to the step that owns it, every later step running again; caps, then the export
with NEEDS REVIEW. The runner never stops here.

## Inputs
- 10-build/project/ (index.html is the source of truth for what is on screen), 10-build/plan.json (scenes, emphasis
  hits, landings), 10-build/events.json (the scene changes for the filmstrips), 10-build/contact-sheet.png, draft.mp4
- 11-sfx/cues.json (S11's verification), draft_mixed.mp4, sound-map.txt
- 08-voiceover/words.json (the spoken words, the intelligibility reference), 07-script/script.json, 02-expansion/expansion.json
  (the requirements: the problem, the share line, the keyword), 02-expansion/solution.json when it exists
- styles/paper-cards/tokens.json and analysis/ (the reference numbers and stills; tokens.json pacing when the analysis
  folder is missing), library/brand/brand.json, motion-lib/catalog.json, tools/analyze_refs.py
- config review.* (thresholds), caps.review_rounds_opus and review_rounds_fable, models.qa, timeouts
- state.json rounds.review (the rounds done so far)

## Outputs (in runs/<id>/12-review/)
- review.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done. Fields: round, pass, verdict (pass | fix | cap | flag | stop), energy (the energy check's summary), early_stop,
  mechanical, style and audio summaries, edit_review
  (scores, issues, branding_natural, summary), issues[] (every issue with tag, text, stage, source), routing (owners,
  reopen, the next activity and model), cap, flags.
- energy.json (M16: the meter's numbers of the reel and of every scene, the targets, the per-scene bounds, the failing scenes and
  their [animation] issues), review-r<n>.json and edit-r<n>.json per round, mechanical.json, style.json (with analysis/ from the analyzer),
  audio.json (with transcribe/), filmstrips/ (hook.png, transition-NN.png), digest/ and prompt-r<n>.md (what the qa
  model read), calls/ (the model's raw output), notes.md (the round in prose), feedback.json (what the re-run stages read:
  the issues by stage; written only when the verdict is fix), reopen.txt (consumed by state.py stage-done).
- state.json: rounds.review set to the failed round's number; the issue counters (a failed round opens one issue, a later
  pass fixes it); the flags of a cap or flag verdict.
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).

## Invariants
- pass only when the energy, mechanical, style and audio checks pass and every edit-review score is at least 4 (nine scores since
  M16: energy is the ninth; an answer without it counts 5 on it)
- the energy check measures the mixed draft (else the silent draft): the reel meets every target of tokens.json energy; a scene
  reaches 80 percent of each lower bound and stays within 1 / 0.8 of each upper bound (config review.energy_scene_share); the ask
  scene is left out of the per-scene routing (its content is fixed by the branding rules) and counts in the reel's numbers
- the mechanical checks add (M16, review/liveness.py): no element static for more than 0.5 s, the edge layer present; both [animation]
- early stop (M16, E9): this round's scores and issue keys (tag, scene or instance, kind) equal the previous round's: verdict stop,
  no reopen, a NEEDS REVIEW flag; config review.early_stop false switches it off
- every issue carries one of [voice], [animation], [text], [transition], [sfx]; the fix routing reopens the earliest owner
  (08-voiceover, 09a-animations, 09b-text, 09c-transitions or 11-sfx), every stage after it and this stage
- a [voice] issue routes only when it names a word in quotes (the voice is deterministic); otherwise it is a flag
- caps: review_rounds_opus (3) rounds with the main director and builder (the passes run again after a failed round
  are fine tuned by models.visual_director_fix, sonnet), then review_rounds_fable (2) escalated rounds (the
  visual passes switch to models.visual_director_escalation when rounds.review reaches review_rounds_opus: opus,
  fable only on an idea marked [important], DECISIONS.md 324 and 325; S10's
  builder switches at 2, DECISIONS.md 225); the round after the last cap exports with NEEDS REVIEW and the notes
- every pixel-based threshold is applied at the composition's size in the harness (exact) and scaled to the draft's
  540x960 in the video checks

## Exit codes
0 done (whatever the verdict: the review loop is not an error), anything else a code error for the review and fix loop
(BUILD_SPEC.md 4.2): a missing input, the harness or ffmpeg failing, no whisper interpreter, the qa call failing after
ai()'s own retries.

## Model and session
The edit review: config models.qa (opus), a fresh session per round, tools config review.qa_tools (Read, Glob: it reads
the images), --json-schema model.schema.json, timeout timeouts.edit_review_seconds. Never the builder. The code checks
call no model. REELS_REVIEW_SKIP_EDIT=1 (tests) skips the call: the code checks alone decide.

## dummy.sh
`bash pipeline/stages/12-review/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
