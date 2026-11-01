# M11 review 1 (Sound effects pass and review loop)

Verdict: APPROVED

## Acceptance test

`bash pipeline/tests/test-m11.sh`, run once by the reviewer (log: build/M11/review-1-test.log), exit 0:
`test-m11.sh: 253 passed, 0 failed` (the report says 254; one check fewer here, no failure).

- 1 units: the sound pass on the frozen build, the detector (shifted and extra sound), the review notes, the voice-only
  path, the mechanical, style and audio checks on the clean draft, every planted branding fault caught (FlashFX logo
  outside the CTA, black lockup on ink, stretched logo, lockup under 300 px, CTA without the avatar), the routing units.
- 2 runner with the fake editor: a passing round, then the planted [text] issue routed to 09b with 09c, 10, 11 and 12
  run again and round 2 passing.
- 3 the cap: 3 opus rounds plus 2 fable rounds, then the export with NEEDS REVIEW and the notes.
- 4 the real editor (1 model call) and the real faster-whisper: verdict fix, scores mostly 3, 15 tagged issues; the
  mechanical checks (branding included) and the style check pass on the frozen draft, WER 0.0 percent.
- 5 em dash scan: pass.

The working tree was unchanged by the run (no fixture drift in git).

## Required fixes

None.

## Suggestions

1. PLAN.md names `pipeline/bin/filmstrip`; it does not exist (the filmstrips come from
   `python pipeline/lib/review filmstrips`). Nothing later depends on it, but a thin wrapper would match the plan.
2. The frozen fixture `pipeline/tests/fixtures/runs/test-idea/11-sfx/` holds cues.json and the sound maps but not
   mix.wav or mix_hook2.wav (audio is not in git). M12's S13 tests will need them: rebuild them with
   `bash pipeline/bin/mix-sfx` (or extend materialize-project.py) rather than expecting them in the fixture.
3. The real editor's first verdict on the test idea is harsh (mostly 3s, 11 [animation] issues: empty first frame,
   small cards in the top third, repetitive entrances). Under the real loop this test idea would likely hit the cap
   and export with NEEDS REVIEW. That is the visual director's quality, not an M11 defect, but worth watching in M12's
   end to end run (time and cost of 5 rounds).
4. PLAN.md said Puppeteer and mechanical.mjs; the build uses Playwright in Python (mechanical.py), consistent with M9's
   harness. Fine; DECISIONS.md should keep recording it.
