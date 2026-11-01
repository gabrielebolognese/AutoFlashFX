# M4 fixes 2: Research, expansion, gate, angle (S1 to S4)

Fixed 2026-11-01 after build/M4/review-2.md (REJECTED, 1 required fix), in a fresh session. Read BUILD_SPEC.md
(sections 3, 4, 5 S1 to S4, 7, 12), CLAUDE.md, PLAN.md (M4), DECISIONS.md (95 to 111), build/progress.md,
build/HUMAN_TODO.md, pipeline/knowledge/known-issues.md, build/M4/report.md, review-1.md, fixes-1.md and
review-2.md. Only the required fix was applied; the optional suggestions of reviews 1 and 2 were left alone. The
pre-existing uncommitted changes in the working tree (build-runner.sh, tools/voice.py) are not part of this batch
and were not touched.

## Required fix 1: an F fail caused only by the expansion's wording dropped a true idea at once

The reading, recorded in DECISIONS.md 112: spec S3's "F failing (the tool does not do what the idea assumes, it is
deprecated, or the claims cannot be verified): drop immediately" names faults of the idea. A statement of the
expansion that facts.md does not back, while the research verified the core claim, is a slip of the pipeline's own
writing model (S2 or S4), and S4 exists to rewrite the expansion. So "drop immediately" applies to the idea's
facts, and a wording slip is repaired by an angle round inside the same cap. The HUMAN_TODO line the reviewer left
now says where to flip this if the user wants the literal reading (one line in gate.py).

What changed:
- pipeline/stages/03-gate/model.schema.json and prompt.md: the model also answers `F_kind`: "none" when F is ok,
  "core" when the idea itself does not hold (the tool does not do what the idea assumes, it is deprecated, the
  core claim is unverified or false, or the solution or the one specific true thing rests on a false or unverified
  claim that no verified claim could replace), "wording" when a statement of the expansion is not in facts.md or
  says more than its claim says while the idea holds without it. The F criterion now also fails a statement that
  goes beyond its claim (an added detail, a skipped step, a count or an adjective) and asks for every failing
  statement quoted word for word; angle_hint covers the wording case (which statements to remove or reword and
  which claim to use); the rules say to answer "core" only when the idea cannot stand on the verified claims.
- pipeline/lib/gate.py decide: a false or unverified core claim is still code-forced to F fail with kind core,
  and an F fail of kind core drops at once ("facts don't hold (P S C F fail): ..."), exactly as before. An F fail
  of kind wording with the core verified is treated like a failing P, S or C: decision angle while angle rounds
  are left, else a drop "still failing after N angle rounds (P3 S3 C3 F fail): ...". The order of the rules is
  core fail, pass, different topic, angle, drop. A fail without a kind (a malformed answer; the schema requires
  the field) is read as core, the spec's strict default. gate.json gains `F_kind` ("" when F is ok) and
  `model_F_kind`, `failing` lists "F" when F fails, the printed failing_text reads "F wording" (or "S1 F wording"
  when both fail) so the ANGLE line is `gate failed (F wording): finding a better angle, round 1/2`, and when the
  model left angle_hint empty on a wording fail gate.py builds one from the F evidence. schema.json (gate.json)
  declares the two new optional fields; the frozen fixture and the dummy stay valid.
- pipeline/stages/03-gate/run.sh: the header comment, and the history given to the next gate round shows the
  kind ("gate round 1: P3 S3 C3 F fail (wording), decision angle, ...").
- pipeline/stages/04-angle/run.sh and prompt.md: the stage reads F_kind from gate.json; on a wording failure the
  verdict line reads "Failing: F (wording)" and the prompt gets a section "F failed for wording: fix this first"
  right after the gate's verdict (remove each quoted statement, or reword it to say exactly what a verified claim
  says, or research it now and add the claim to new_claims; add no statement that no verified claim backs). The
  intro and the "What a better angle means" list cover the wording case ("keep what scored well on P, S and C; do
  not change the topic to fix F"); angle.json and angle-<n>.json record `previous_F_kind`.
- pipeline/stages/02-expansion/prompt.md and 04-angle/prompt.md: the wording rule is tightened as the review
  asked: only verified facts, in the claim's own words (the install steps exactly as the docs give them, a font
  or a color named as the claim names it), no added detail, step count or adjective the claim does not state;
  one statement the gate cannot find in facts.md fails F and costs an angle round.
- pipeline/lib/session.sh: the reseed's gate section says what F failed for (core or wording).
- The CONTRACT.md of 02-expansion, 03-gate and 04-angle, CLAUDE.md's gate paragraph, build/progress.md and
  build/HUMAN_TODO.md describe the new rule; DECISIONS.md 112 records the reading of spec S3 and the design (the
  repair runs in S4 and not in a new step because S4 is the spec's own "rewrites expansion.md, then back to S3",
  it already has session A, the research tools and the gate's quoted evidence, and caps.angle_rounds bounds it
  without a new counter).
- Fixtures: pipeline/tests/fixtures/fake/m4/03-gate.json and variants/03-gate.pass.json carry `F_kind: none`,
  variants/03-gate.false.json `F_kind: core`, and the new variants/03-gate.wording.json is an F fail of kind
  wording with P3 S3 C3 (its F evidence quotes the two statements to fix, its angle hint names the claims).

How verified (pipeline/tests/test-m4.sh):
- Section 1, gate.py units (13 new checks): a wording fail with the core verified and rounds left is decision
  angle with scores_text "P3 S3 C3 F fail" and failing_text "F wording", gate.json has F_kind wording and failing
  ["F"] and validates; the model's angle hint is kept; a wording fail with no round left drops with "still
  failing after 2 angle rounds (P3 S3 C3 F fail): ..."; a false or an unverified core claim drops at once
  whatever kind the model gave (F_kind core in the output); the kind-core fixture drops at once as before (the
  check was renamed) with F_kind core in gate.json; an F fail without a kind drops ("facts don't hold"); S1 plus
  a wording fail is one angle round with failing_text "S1 F wording"; a wording fail without an angle hint gets
  one built from the F evidence.
- Section 2, the loop through run.sh with the fake claude (21 new checks): the gate answers the wording fixture on
  round 1 and the pass fixture on round 2 (03-gate.2.json). Expected and seen: `ANGLE  gate failed (F wording):
  finding a better angle, round 1/2`, no DROP line, `GATE   passed (P3 S3 C3 F ok) after 1 angle round`, `DONE
  exported #2 -> exports/2/`, the event lines STEP, STEP, ANGLE, STEP, STEP, GATE, the 13 STEPs of the dummy
  stages, DONE; gate-1.json decision angle with F fail of kind wording and failing ["F"]; gate.json (round 2)
  pass; angle-1.json previous_F_kind wording and valid against schema.json; prompt-angle-r1.md holds the section
  "## F failed for wording: fix this first", the line "Scores: P3 S3 C3 F fail. Failing: F (wording).", the
  gate's F evidence (the quoted statement) and the gate's hint; prompt-gate-r2.md shows "gate round 1: P3 S3 C3 F
  fail (wording), decision angle"; expansion.json written by "04-angle round 1"; the history line says exported;
  the idea left ideas.txt after the export; no em dash in the gate and angle files. The run folder of this case is
  taken from the run's START line (new helper run_of), because `ls` on this machine sorts "<id>-2" before "<id>"
  and a fixed position in the listing picked the wrong run.
- The existing cases are unchanged and pass: the two S1 rounds then the drop, the pass on round 2, the false core
  claim (drop at once with F fail, 04-angle skipped), the different-topic verdict.
- `M4_SECTIONS="1 2" bash pipeline/tests/test-m4.sh`: 200 passed, 0 failed (166 before this batch, plus 34).
- Section 3 run three times in a row with the real models (the review asked for at least twice), see below.

## Test results

Real runs of section 3 (the test idea, `M4_SECTIONS=3 bash pipeline/tests/test-m4.sh`, then once more inside
run-all.sh), on 2026-11-01:
- Run 1 (343 s): 36 passed, 0 failed. S1 in 3m01s: 14 claims (all verified), 10 numbers, 5 screenshots, the core
  claim verified, no Bash call refused by the permission rules, 7 numbers with their source on github.com. S2 in
  31 s: 1293 characters, keyword TELLS, 5 evidence pointers. Gate round 1: `ANGLE  gate failed (F wording):
  finding a better angle, round 1/2`, the same kind of failure that dropped the idea in review 2. S4 in 32 s, 0
  new claims, 1305 characters: "The angle stays the same and only the two flagged statements change. I cut the
  unbacked "visitors dismiss it" from the p...". Gate round 2: `GATE   passed (P3 S3 C3 F ok) after 1 angle
  round`, then the dummy stages and `DONE   exported #1`. Without this fix the run would have ended in the DROP
  line of review 2.
- Run 2 (296 s, sandbox kept and read): 36 passed, 0 failed. S1 in 2m34s: 13 claims (all verified), 10 numbers,
  5 screenshots, the core claim verified. S2 in 27 s: 1351 characters, keyword DESIGN, 5 evidence pointers. Gate
  round 1: `ANGLE  gate failed (F wording): finding a better angle, round 1/2`; gate-1.json has F fail, F_kind
  wording (the model's own kind), failing ["F"], decision angle, and its F evidence quotes the two statements:
  the one specific true thing wrote the hex values as exact where facts.md#5 says "near #F4F1EA" and "near
  #D97757", and the deliverable promised hex values for all five tells where the research gives them for some;
  the model's angle hint says how to reword both from claim 5. S4 (0 new claims, 1365 characters): "Same angle,
  with the wording fixed for F. The colours now carry 'near' exactly as facts.md#5 states them. The deliverable
  no longer promises a hex value for every tell, only the colour values the skill gives where it names them."
  angle-1.json previous_F_kind wording. Gate round 2: `GATE   passed (P3 S3 C3 F ok) after 1 angle round`, its F
  evidence maps every statement to a verified claim "now worded with 'near' as the claim states"; `DONE
  exported #1`. The final expansion.md reads as the gate describes it (the colours "near #F4F1EA" and "near
  #D97757", the deliverable "colour values where it gives them").
- Observation: in both real runs the gate failed F for wording on round 1, where the report's run, review 1 and
  fixes 1 had passed F at once and review 2 had dropped. The gate model is strict on F (the prompt asks it to be),
  and with F_kind it can say "wording" instead of choosing between a pass and a drop; the repair costs one S4 call
  and one more gate round (about a minute here) and ends in a pass with every statement matched to a claim. The
  tightened S2 wording rule should make the first expansion pass more often, but the acceptance test no longer
  depends on it.
- Run 3 (329 s, section 3 inside the full run-all.sh): 36 passed, 0 failed. S1 in 2m58s: 14 claims (all
  verified), 10 numbers, 4 screenshots, the core claim verified, no read-only gh command refused, 7 numbers with
  their source on github.com. S2 in 31 s: 1258 characters, keyword DESIGN, 4 evidence pointers. Gate round 1:
  `ANGLE  gate failed (F wording): finding a better angle, round 1/2`. S4 in 30 s, 0 new claims, 1298
  characters: "Same angle, with the wording fixed. The one true thing now calls cream plus terracotta one of five
  looks that AI-generat...". Gate round 2: `GATE   passed (P3 S3 C3 F ok) after 1 angle round`, then the dummy
  stages and `DONE   exported #1`. So the test idea reached GATE passed in three runs in a row, each time through
  one wording repair.
- Section 4 (the false idea, inside the same run-all, 356 s): 12 passed, 0 failed. S1 in 4m51s: 11 claims (all
  verified), 6 numbers, 4 screenshots, the core claim false. S2 wrote 1229 characters (keyword WHISPER). The gate
  dropped at once, unchanged by this fix: `DROP ... dropped: facts don't hold (P2 S2 C3 F fail): the idea's core
  claim is false (...)`; the model also suggested a different idea (written to logs/suggested-ideas.txt), the
  block left ideas.txt and the history line carries the scores.

Full suite (`bash pipeline/tests/run-all.sh`, 2026-11-01, started 07:28, finished 08:22): 6 test files, all
passed. test-m1.sh 96, test-m2.sh 220, test-m3.sh 424 (section 4 called the real Opus reviewer and Sonnet
fixer), test-m4.sh 248 (214 before this batch, plus 34), test-limits.sh 94, test-no-emdash.sh 1; 0 failed. No
earlier milestone's code changed in this batch (gate.py and session.sh are M4 files), so the M1 to M3 tests ran
only as part of the suite.

Note on the interrupted session: the fix batch was interrupted (the build runner's STOP line at 08:18) while
run-all.sh was in section 4 of test-m4. The suite's own process kept running and finished at 08:22 with the
result above. The resumed session read its log (/tmp/run-all-fix2.log), checked the diff against the review's
expected list, scanned the 23 files of this batch on bytes (no CR, no em dash, no BOM), ran `bash -n` on the
changed scripts and parsed the changed JSON files, then made the commits. The working tree's uncommitted
BUILD_SPEC.md (the build mode paragraph), build-runner.sh and tools/voice.py are the user's own edits and were
left out of the commits.
