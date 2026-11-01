# M10 Visual stages (S9, S10): review 1

Verdict: APPROVED

## Acceptance test

`bash pipeline/tests/test-m10.sh` ran once, in full, sections 1, 2, 2r, 3 and 4 (log: build/M10/review/test-m10.log).
Result: `test-m10.sh: 177 passed, 0 failed`, exit 0. The report says 178. The difference is one check that only runs in
some conditions; nothing failed.

- 1. Units: good.json passes, every bad-<rule>.json fails naming its rule, the caption width limit holds, the pass
  schemas are current, the preflight's brand check stops a sandbox whose brand.json lists a missing file.
- 2. Fake director through the runner, starting from the frozen M7 outputs: all three plans validate, the merged plan
  passes, `hyperframes check` passes, events.json is verified on screen, draft.mp4 is 540x960, 30 fps, silent and
  matches the voice's length, hook2.mp4 is under 3.5 s. Branding works for both the flashfx and the external
  solution fixture.
- 2r. Builder repair loop: two calls to the fake builder, then a code error, as specified.
- 3. Real director: 11 scenes, the check passes, events.json validates and its typing, count, strike and check events
  are verified. draft.mp4 is 41.47 s against a 41.46 s voice, hook2.mp4 is 3.20 s.
- 4. No em dash in the files M10 wrote.

## Required fixes

None.

## What M11 needs from M10 (checked)

- `10-build/events.json` lists every event with ms, frame, type, cue, component, instance, scene, beat,
  scene_change, transition_ms and a verified flag. A frozen copy is in
  pipeline/tests/fixtures/runs/test-idea/10-build/.
- draft.mp4, project/, hook2.mp4, contact-sheet.png and plan.json exist. The per-pass plans 09a, 09b and 09c can be
  re-run on their own, so S12 can send a [text] fix back to 9b.

## Suggestions (none of these block approval)

1. PLAN.md says S10 writes candidates into motion-lib/candidates/ when the plan needs a component the library lacks.
   The build writes only a NEEDS REVIEW flag (the wishlist) instead. This is documented (DECISIONS.md 225,
   HUMAN_TODO). M11 does not depend on it, but the gap should stay visible.
2. PLAN.md names the files pipeline/lib/plan_merge.py, plan_validate.py and events.py. The build put them in the
   package pipeline/lib/visual/ instead. Later milestones should call `python pipeline/lib/visual <command>`.
   CLAUDE.md already says this.
3. No real builder model has repaired a project yet (only the fake one in section 2r). Watch the first real repair
   in a live run.
4. build/M10/patch-*.py are one-off scripts the build used to edit files. Consider removing them once the build is
   finished.
