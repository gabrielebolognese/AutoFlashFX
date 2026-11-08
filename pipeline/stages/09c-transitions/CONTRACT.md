# 09c-transitions: Visual plan, transitions pass (S9c)

Built in M10. Spec: BUILD_SPEC.md section 5, S9 9c; DECISIONS.md 215 to 232.

## Purpose
How each scene leaves and the next arrives, following the style's transition rules (tokens.json transitions: an
animated exit then the next scene enters; fade-blur, fall, push or cut, with the style's durations). The
visual_director chooses the type per scene pair; pipeline/lib/visual/plan9.py sets the durations, writes the
merged plan and validates the whole.

## Inputs
- 09a-animations/plan.json, 09b-text/plan.json
- styles/paper-cards/tokens.json (transitions), style.md; the golden reel's transitions
- the digests in 09c-transitions/digest/ (transitions.md: the scene list; golden.md)

## Outputs (in runs/<id>/09c-transitions/)
- plan.json is the primary output (schema.json from pass-schemas.py): pass transitions, transitions[] (from, to,
  type, duration_ms), notes.
- merged.json: the whole visual plan (pipeline/stages/09-plan/schema.json), what S10 compiles; S10 merges the three
  pass files itself as well, so a re-run of one pass after a fix is picked up.
- plan.candidate.json, prompt.md, prompt-retry.md, calls/, digest/, stage.log as in 09a.

## Invariants (plan_validate.py, every rule)
- one transition per consecutive scene pair, only allowed types, the style's duration per type, at most a third
  hard cuts
- no transition type more than 3 times in the reel (E8, rule transition_variety; the pipeline changes the later occurrences of an
  over-used type itself, plan9.vary_transitions, and notes it)
- the merged plan passes every rule of BUILD_SPEC.md S9 (the scene, caption and branding rules of 9a and 9b again)

## Exit codes
0 done, 10 drop, 20 block, anything else a code error.

## Model and session
Fresh visual_director session (config models.visual_director, opus, for the first plan; models.visual_director_fix, sonnet, when the pass runs again after a failed review round; models.visual_director_escalation from caps.review_rounds_opus failed rounds on: opus, fable only on an idea marked [important]; DECISIONS.md 324 and 325), one retry with the exact errors.

## dummy.sh
Writes a small valid transitions plan; honors the planted REELS_DUMMY_* lists.
