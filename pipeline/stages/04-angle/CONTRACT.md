# 04-angle: Angle research (S4)

Built in M4 (the folder, this contract, schema.json and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S4.

## Purpose
When the gate fails on P, S or C: research more, rewrite expansion.md with a better angle that keeps the idea's
core topic, then the idea goes back to S3. The stage starts as "skipped" in state.json and runs only when the gate
reopened it (03-gate/reopen.txt, applied by state.py stage-done). Session A resumed with the research tools
(config research.tools and research.allowed) and the gate's verdict in the prompt.

## Inputs
- 03-gate/gate.json (the failing scores, the quoted evidence, the reason, the angle hint) and the earlier
  gate-*.json files (the round number is the count of gate rounds that decided "angle")
- 01-research/facts.md and research.json
- 02-expansion/expansion.md and expansion.json (the previous expansion is kept as expansion-r<round-1>.md)
- the earlier angle-*.json files (what previous rounds changed, so the model does something different)
- library/profile/deliverables.txt and account.md, config research.expansion_chars, research.expansion_tries,
  research.max_assets, caps.angle_rounds

## Outputs (in runs/<id>/04-angle/)
- angle.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). Fields: round, gate_round, previous_scores {P, S, C, F},
  previous_failing, change (what the new angle does differently), keeps_core_topic (true: a false answer drops the
  idea instead), new_claims (how many claims were appended to facts.md), expansion_chars, written, checked.
- angle-<round>.json: a copy per round.
- 02-expansion/expansion.md and expansion.json rewritten (written_by "04-angle round N", round N), the previous
  version kept as 02-expansion/expansion-r<N-1>.md.
- 01-research/research.json, facts.md, numbers.json and assets.json updated when the model added claims or
  screenshots (research.py append-claims: the numbering continues, nothing is renumbered).
- reopen.txt naming 03-gate (consumed by state.py stage-done): the gate scores the rewritten expansion next.
- prompt-angle-rN.md and prompt-angle-rN-fixM.md: the rendered prompts; calls/: the model calls (ai.sh).
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop): "no angle keeps the core topic (P3 S1 C3 F ok):
  <change>; suggestion written to logs/suggested-ideas.txt".

## Invariants
- the core topic stays; when the model says only a different topic works (keeps_core_topic false) the stage drops
  the idea, writes the suggestion to logs/suggested-ideas.txt (never to ideas.txt) and exits 10
- at most caps.angle_rounds rounds per idea: the gate counts the angle rounds done (04-angle/angle-*.json) and
  drops instead of asking for a third; state.json rounds.angle holds the current round number
- the rewritten expansion obeys the same rules as S2 (expansion.py: first-person problem, named identity, keyword
  in capitals, NEW deliverable described, 2 to 6 pointers to verified claims, 500 to 1500 characters), asked again
  with the exact problems up to research.expansion_tries times, then written anyway with a NEEDS REVIEW flag
- the activity text is "finding a better angle (round N/2)"
- no em dash in any output file

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the
review and fix loop (BUILD_SPEC.md 4.2).

## Model and session
Session A resumed (session_call reseeds a lost session with facts.md, expansion.md and the latest gate feedback).
Model: config models.research. Timeout config timeouts.angle_seconds.

## dummy.sh
`bash pipeline/stages/04-angle/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
