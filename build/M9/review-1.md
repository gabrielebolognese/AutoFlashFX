# M9 review 1 (Motion library)

## Verdict: APPROVED

## What was checked

- BUILD_SPEC.md section 12 (M9), PLAN.md M9 and the M10 dependencies, build/M9/report.md, the commits since afb3757
  (5 commits, 189 files).
- The acceptance test, run once: `bash pipeline/tests/test-m9.sh` (full log in build/M9/review-1-test.log):
  80 passed, 0 failed, exit 0. Sections 1 (tokens), 2 (lint, check, catalog, logo spots, 27 stills), 3 (frame-match,
  the reference strips correlated), 4 (golden reel: plan validates, `hyperframes check` passes, render 1080x1920 at
  30 fps, 41.47 s against the 41.46 s voice, AAC audio, contact sheet), 5 (WebGL: hardware ANGLE D3D11, HyperFrames
  renders 3D with --browser-gpu), 6 (no em dash).
- What M10 needs from M9 exists: motion-lib/catalog.json (27 components with props, beat_types, sound_events,
  still, frame_match), pipeline/stages/09-plan/schema.json (golden/test-idea/plan.json validates against it),
  styles/paper-cards/tokens.json, golden/test-idea/{plan.json, contact-sheet.png, README.md}, package.json with the
  pinned hyperframes, pipeline/bin/setup-node.
- Earlier features: the only earlier-milestone change is a warn-level tokens.json entry in config.json's preflight
  list and .gitignore lines. `bash pipeline/bin/preflight` still ends READY (exit 0). No stage code changed.

## Required fixes

None.

## Suggestions

1. The test rewrites tracked files: after a run, `git status` shows golden/test-idea/contact-sheet.png,
   motion-lib/gallery/frame-match.json, frame-match.md and motion-lib/webgl.json modified (timestamps or re-encoded
   pixels). Harmless, but a dirty tree after every test can confuse the autofixer's commits. Either make these
   outputs deterministic (no timestamps) or write the test's copies to a temporary folder.
2. Paths differ slightly from PLAN.md: the token schema is pipeline/lib/tokens.schema.json (PLAN: 
   styles/paper-cards/tokens.schema.json) and frame-match lives in pipeline/lib/motion/ (PLAN:
   pipeline/lib/framematch.py). M10 should use the real paths; the report and CLAUDE.md name them correctly.
3. Section 4 depends on the frozen vo.wav that test-m7 section 3 writes (wav files are ignored by git). On a fresh
   clone test-m9 cannot pass without running test-m7 first; a clear skip or error message pointing at test-m7 would
   help.
4. The accent orange under 3:1 contrast (already in HUMAN_TODO): M11's S12 contrast rule must exempt accent words
   or it will flag every reel.
5. The caption-line scales chunks wider than 620 px instead of refusing them; make sure M10's 9b validator enforces
   the width so this never triggers.
