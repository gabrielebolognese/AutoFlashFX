# M10 Visual stages (S9, S10): build report (2026-11-01)

## What was built

1. **The three passes of the visual plan, S9a, S9b, S9c** (pipeline/stages/09a-animations, 09b-text, 09c-transitions:
   run.sh over the shared pipeline/lib/visual.sh, prompt.md, model.schema.json for the structured answer, schema.json
   for the pass's plan.json generated from pipeline/stages/09-plan/schema.json by pass-schemas.py, CONTRACT.md,
   dummy.sh). A fresh visual_director session per pass gets digests of the run (the timeline of beats and words, the
   motion library's catalog, the golden reel, the research screenshots, the solution and the branding it implies; for
   the later passes the 9a instances, the baseline caption chunks and the scene list), style.md, tweaks.md and
   tokens.json, and answers with a design; pipeline/lib/visual/plan9.py composes the plan from it: every start
   snapped to a spoken word of words.json (`at`: scene, breath, word:<word>, ms:<offset> snapped to the nearest word
   boundary; `word_props` for strike_at and ticks_at), the headline's words from the beat, the hook's set piece
   landing in the breath, the CTA's FlashFX DM card and lockup from brand.json, the brand slot by the solution
   (the bolt for FlashFX, the tool's logo from the research, else the component's neutral icon; FlashFX assets
   outside the CTA removed for other solutions), the caption chunks timed from words.json and never wider than the
   style's line, the card texts as prop overrides, the honesty labels from the components, the transitions with the
   style's durations and the merged plan (09c-transitions/merged.json). One retry with the exact problems in the same
   session, then the review path (DECISIONS.md 215 to 224).
2. **The validator** pipeline/lib/visual/plan_validate.py: 19 named rules (schema, components, times, first_change,
   breath, max_gap, distinct, repeat, beat_map, three_d, set_pieces, zones, captions, cards, assets, honesty,
   branding, transitions, hook2), every threshold from tokens.json, catalog.json, brand.json or config visual.*,
   reported as `rule=<name>: <message>` lines; `python pipeline/lib/visual validate <plan> --run-dir DIR`.
   pipeline/lib/visual/plan_merge.py merges the pass files; pipeline/lib/visual/common.py holds the timeline, the text
   widths measured with the library's font files and the approximate footprints of the zone check.
3. **S10, build visuals and draft render** (pipeline/stages/10-build: run.sh, prompt.md for the builder's repair call,
   schema.json, CONTRACT.md, dummy.sh) over pipeline/lib/visual/project.py: the merged plan validated once more,
   compiled into 10-build/project/ with motion/golden.py build_project (the library's compositions and assets, one
   host per instance, the captions once, the logos as image files with their aspect ratio locked, the transitions as
   exit props, no audio: a silent draft), 3D replaced by 2D cards with a NEEDS REVIEW flag when motion-lib/webgl.json
   says WebGL is missing, `npx hyperframes check --json` (the builder model, Opus, or builder_escalation for 3D-heavy
   plans or after 2 review rounds, repairs the project inside its folder only when the check reports errors, up to
   config visual.build_fix_rounds times), the draft rendered at the composition's size with `--quality draft` and
   scaled to 540x960 with ffmpeg (silent, 30 fps, the plan's length within 0.2 s), the hook 2 alternate clip (the hook
   scene with hook 2's headline and words_hook2.json, 3.5 s at most), the contact sheet (pipeline/bin/contact-sheet,
   one still per beat plus the breath), build.json and check.json (DECISIONS.md 225 to 231).
4. **events.json** (pipeline/lib/visual/events.py): every sound event of the built visuals read from the components
   themselves (they register what they do and when on their mount; the harness of M9 mounts every instance with its
   resolved props), in absolute ms with the catalog's cue type, the scene changes from the transitions with their
   duration, and each event that starts a visible change verified on screen by a seek one frame before and one after
   (DOM state, or pixels for a canvas); `npx hyperframes timeline --json` cross-checks the hosts' starts. On the test
   idea: 108 events, 10 scene changes, 69 of 69 verified.
5. **The branding placement of S9 and S10** (BUILD_SPEC.md 2.7, tweaks.md "Branding (FlashFX account)"): applied by
   code in 9a (apply_branding), checked by the validator's branding rule (the CTA's avatar and lockup, no FlashFX asset
   outside the CTA unless the solution is FlashFX, every logo path in brand.json with a use_on matching its surface),
   placed as `<img>` files by the compiler, and the preflight check `brand` (brand.json parses and every file it lists
   exists with use_on, width and height) plus tokens.json, motion-lib/catalog.json and node_modules/hyperframes as
   hard requirements.
6. **The test** pipeline/tests/test-m10.sh with the validator fixtures (pipeline/tests/fixtures/plans: good.json, one
   bad-<rule>.json per rule from make-bad.py), the fake director's answers (pipeline/tests/fixtures/fake/m10), the
   solution fixtures (pipeline/tests/fixtures/solutions: flashfx.json, external.json), the sandbox option
   `sandbox_init --with-visual` (the library, the brand kit, the golden and the stills copied in; the Node packages
   stay in the repo through REELS_NODE_PREFIX) and the frozen outputs of the real run under
   pipeline/tests/fixtures/runs/test-idea/{09a-animations,09b-text,09c-transitions,10-build}/.

## Files

- pipeline/lib/visual/{__init__,__main__,common,plan9,plan_merge,plan_validate,project,events}.py, pipeline/lib/visual.sh
- pipeline/stages/09a-animations/{run.sh,prompt.md,model.schema.json,schema.json,CONTRACT.md,dummy.sh}, the same in
  09b-text/ and 09c-transitions/; pipeline/stages/09-plan/{schema.json,pass-schemas.py}
- pipeline/stages/10-build/{run.sh,prompt.md,schema.json,CONTRACT.md,dummy.sh}, pipeline/bin/contact-sheet
- config.json (visual, timeouts plan_seconds, build_seconds, check_seconds, events_seconds, render_draft_seconds, the
  preflight entries), pipeline/lib/preflight.sh (the brand check)
- pipeline/tests/test-m10.sh, pipeline/tests/lib.sh (--with-visual and the hard-check files in every sandbox),
  pipeline/tests/fixtures/{plans,solutions,fake/m10}/, pipeline/tests/fixtures/runs/test-idea/{09a-animations,09b-text,09c-transitions,10-build}/
- Earlier milestones touched (M10 depends on them): pipeline/lib/motion/golden.py (build_project with an optional
  voice, folder, meta id, title; the npx prefix), pipeline/lib/motion/captions.py (the width limit),
  pipeline/lib/motion/goldenplan.py (width-aware chunks, push 267 ms), pipeline/lib/motion/harness.py (the element's
  tag), pipeline/lib/tokens.py BEAT_TYPES and the rebuilt styles/paper-cards/tokens.json, motion-lib/assets/tokens.css
  and motion-lib/catalog.json, motion-lib/compositions/headline.html (word span ids), golden/test-idea (plan, project,
  contact sheet, README regenerated), the M2 dummies, schemas and contracts of the four stages
- DECISIONS.md 215 to 233; build/progress.md; build/HUMAN_TODO.md; CLAUDE.md; build/M10/patch-events.py (a record)

## How to run the test

`bash pipeline/tests/test-m10.sh` (about 25 minutes; section 3 calls the real visual director three times and the
builder only if the check needs a repair). `M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh` runs the fake-only
sections (about 12 minutes, two builds with renders). `M10_FREEZE=1` makes section 3 refresh the frozen plans, the
project files and the director's answers in pipeline/tests/fixtures/.

## Test output (summary)

```
== 1. units: the validator fixtures, the caption width, the pass schemas, the preflight's brand check ==   30 PASS
   (good.json passes; 18 bad-<rule>.json files each fail naming their rule; the plain chunker leaves 16 of 32 chunks
   wider than 620 px, the width-limited one none of 42; the pass schemas are current; the preflight passes in the repo
   and stops a sandbox whose brand.json lists a missing file, STOPPED.md naming the file and the fix)
== 2. S9a, S9b, S9c and S10 through the runner with the fake visual director, from the frozen M7 outputs ==   92 PASS
   (the runner resumes at S9a and exports; the S9 and S10 lines: 11 scenes, 22 instances, 13 distinct, brand slot
   neutral, hook set piece true; 42 caption chunks; 10 transitions; 24 hosts, check ok with 9 warnings, 108 events with
   10 scene changes and 69 of 69 verified; draft.mp4 540x960 30 fps silent 41.47 s against the 41.46 s voice; hook2.mp4
   3.20 s; 3 model calls, no builder call; the activities; the plans validate and the merged plan passes the validator;
   the CTA branding; the timeline cross-check; the contact sheet. Branding: with solution flashfx the brand slot is
   brand/mark/mark-gradient.png and a bolt on a body card passes while a white bolt on a light card is rejected
   (use_on); with solution external the slot is the neutral icon and no FlashFX asset leaves the CTA; the flashfx
   reel built: 3 logos measured in the harness as images with object-fit contain at the file's aspect ratio)
== 2r. the builder's repair loop ==   12 PASS
   (a component that throws at mount: the check names the planted error, the builder is asked in rounds 1/2 and 2/2
   with a prompt quoting the errors, exactly two builder calls, state.json rounds.build 2, no draft, exit 1)
== 3. the real visual director and the build on the frozen inputs ==   43 PASS, 468 s
   (3 director calls without a retry; 11 scenes, 27 instances, 14 distinct components; 46 caption chunks, 6 card
   texts changed, 10 labels; 10 transitions (1 cut, 5 fade-blur, 2 fall, 2 push); 29 hosts, check ok with 12
   warnings, 120 events, 79 of 79 verified; draft.mp4 rendered in 86 s, hook2.mp4 3.20 s; one NEEDS REVIEW flag: the
   director wanted a color-swatch-card the library lacks; the outputs frozen under pipeline/tests/fixtures/runs/test-idea/)
== 4. no em dash in the files M10 wrote ==   1 PASS
test-m10.sh: 178 passed, 0 failed (sections run separately, about 30 minutes in all)
```

The frozen real reel's contact sheet is pipeline/tests/fixtures/runs/test-idea/10-build/contact-sheet.png: the hook
headline with the 3D card in the breath, a thumb grid of client sites labelled illustrative, the SKILL.md and blog
screenshots labelled real, cards with chips landing on their words, the strike-through, the terminal typing the
install command, the end card with the FlashFX DM card. After M10 the other milestones' tests were re-run where their
code changed: test-m1.sh 96 passed, test-m9.sh 80 passed, test-m2.sh 220 passed (on a quiet machine), and the
repository-wide em dash scan passes.

## Known gaps

- The builder model writes no candidates: a component the director wants and the library lacks becomes a NEEDS REVIEW
  flag (the wishlist) and the reel uses library components; adding components stays a human step with the M9 tools
  (DECISIONS.md 225, HUMAN_TODO).
- The builder repair path is exercised only with the fake builder (section 2r: a planted broken component, two
  rounds, then a code error). The compiled project of the test idea passes the check at once, so no real builder has
  repaired a project yet; the prompt and the tool rules are untested against a real repair.
- The zone check at plan level works on approximate footprints (text widths from the font files, card heights
  estimated); the exact pixel checks are S12's (M11). The hero bottom under the style's 1176 px is a warning.
- The verification of events compares DOM state (or canvas pixels) one frame before and after inside the harness,
  where the component's own timeline is seeked; the real runtime's placement is checked through the timeline
  command's clip starts, not by re-rendering frames.
- The draft is a second encode (a native 1080x1920 render scaled by ffmpeg) because the CLI renders presets only;
  about 60 s plus 20 s for the hook 2 clip on this PC.
- HyperFrames' check reports craft warnings on short chip reads ("line_unread") and the accent contrast, as in M9;
  they are warnings and the stage records their count.
- The real director's plans are judged by the validator and the check, not by eye: the HUMAN_TODO asks the user to
  look at the first drafts and contact sheets.

## HUMAN_TODO items added

- Review the first visual plans and drafts (contact-sheet.png, draft.mp4, the three plan.json files) and where to
  change the design (the prompts, the golden plan).
- The director's wishlist: how to add a component the library lacks.
- The caption line width and the choppier chunks it implies, and the levers (tweaks.md, style.md).
- The preflight's new hard checks (brand kit, tokens.json, catalog.json, node_modules/hyperframes) and their fixes.

## Earlier milestones touched

M9 (the compiler, the chunker, the golden plan and render, the beat map and tokens, the harness, the headline
component), M2 (the dummies, schemas and contracts of 09a, 09b, 09c and 10), M1 (config.json, preflight.sh,
tests/lib.sh). No stage of M4 to M8 changed.
