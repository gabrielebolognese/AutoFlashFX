# 03-gate: Idea gate (S3)

Built in M4 (the folder, this contract, schema.json and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S3.

## Purpose
Score the expansion 0 to 3 on P (problem to solution), S (share driver) and C (comment trigger) and check F (every
claim the reel will make is in facts.md and the core fact is verified), quoting the evidence. A fresh session B
with the gate model every round, no tools. The model scores (model.schema.json); pipeline/lib/gate.py decides, so
the rules of spec S3 never depend on the model.

## Inputs
- 02-expansion/expansion.md and expansion.json (the keyword and its deliverable status)
- 01-research/facts.md and research.json (the core claim's status: a false or unverified core claim fails F
  whatever the model says)
- config caps.angle_rounds (2); the angle rounds done so far (04-angle/angle-*.json) give the gate round number
- the earlier gate verdicts (03-gate/gate-*.json) and angle changes, summarized in the prompt from round 2 on

## Outputs (in runs/<id>/03-gate/)
- gate.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). Fields: round, scores {P, S, C}, F (ok or fail), F_kind (""
  when F is ok, "core" when the idea does not hold, "wording" when a statement of the expansion is not in
  facts.md while the idea holds), pass, decision (pass, angle or drop), evidence {P, S, C, F} (quotes), reason
  (the pass note or the drop reason with the scores), model_reason, model_F, model_F_kind, failing (for example
  ["S1"], or ["F"] when F fails), angle_hint, different_topic, suggested_idea, angles_done, angle_cap,
  core_claim_status, checked, decided_at.
- gate-<round>.json: a copy per round (the history the next rounds and the angle stage read).
- prompt-gate-rN.md: the rendered prompt; calls/: the model calls (ai.sh).
- reopen.txt naming 04-angle when the decision is angle (consumed by state.py stage-done).
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop): the reason carries the scores, for example
  "facts don't hold (P2 S2 C2 F fail): the flag does not exist ..." or "still failing after 2 angle rounds
  (P3 S1 C3 F ok): ...".

## Invariants
- F fails with kind core when the research found the core claim false or unverified, whatever the model answered;
  an F fail of kind core (the idea does not hold: the tool does not do what the idea assumes, it is deprecated,
  the core claim cannot be verified) drops the idea at once (exit 10)
- an F fail of kind wording (a statement of the expansion that facts.md does not back, while the core claim is
  verified and the idea holds without it) is treated like a failing P, S or C: an angle round while rounds are
  left (the ANGLE line "gate failed (F wording): finding a better angle, round 1/2"; the angle stage removes or
  rewords the quoted statements), else a drop "still failing after N angle rounds" (DECISIONS.md 112); a fail
  without a kind is read as core
- pass: P, S and C at least 2 and F ok: the GATE line "passed (P3 S2 C3 F ok)"
- P, S or C failing with angle rounds left (angles done below caps.angle_rounds): decision angle, the ANGLE line
  "gate failed (S1): finding a better angle, round 1/2", 04-angle reopened through reopen.txt; the gate runs again
  after the angle stage (which reopens this stage the same way)
- P, S or C still failing with no angle round left: drop ("still failing after N angle rounds")
- the model says only a different topic would work (different_topic true with a suggested_idea): drop, and the
  suggestion goes to logs/suggested-ideas.txt (never to ideas.txt)
- dropping means: the runner deletes the idea from ideas.txt and writes a history line with the scores and the
  reason (result.json's reason)
- no em dash in any output file (gate.py cleans every text)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the
review and fix loop (BUILD_SPEC.md 4.2).

## Model and session
Fresh session B every round (no --session). Model: config models.gate. Timeout config timeouts.gate_seconds.

## dummy.sh
`bash pipeline/stages/03-gate/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
