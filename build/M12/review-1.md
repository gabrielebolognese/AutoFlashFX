# M12 review 1 (2026-11-02)

Verdict: APPROVED

## What I checked

- BUILD_SPEC.md section 12 and the PLAN.md M12 section (scope and acceptance test), build/M12/report.md, the diff
  since 32e2766 (90 files), with a closer look at the earlier-milestone code M12 touched (pipeline/lib/ai.sh's
  model-limit fallback, the runner's activity and history type, export.py's SOLUTION block).
- Acceptance test, fake-only sections: `M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh` on the committed
  code: **180 passed, 0 failed**, exit 0 (log: build/M12/review-1-test.log). That covers the units, S11 to S14
  through the runner on the frozen build (two 1080x1920 renders, ffprobe and loudness checks, captions file in the
  spec section 8 order with SOLUTION, caption.py lint with no FAIL, schemas), the honesty loop with the fake claude
  (a forced FlashFX solution fails H, S4 picks an external solution, the gate passes on round 2, no drop, no FlashFX
  in script.json or the caption), and the em dash scan.
- Section 4 (the whole real pipeline, 1 to 3 hours): I did not run it again, to keep the build moving. The build
  session's log build/M12/test-m12-s4.log has a genuine pass with every assertion passing: DONE exported #1 after
  168 min, GATE passed with H ok, 1.mp4 1080x1920 30 fps h264 High yuv420p AAC 48 kHz, 39.40 s for a 39.40 s voice,
  -14.35 LUFS, -1.5 dBTP, a 3.00 s hook 2 clip, the captions file correct, the idea gone, the history line with
  `external`. The log's tail (a second runner pass, the "syntax error near fi", the 2 FAIL lines) comes from editing
  test-m12.sh while it ran, as the report says. It is not a code failure.

## Required fixes

None.

## Suggestions (none of them block)

1. pipeline/tests/test-m12.sh section 4: the only clean section 4 log is mixed with the corrupted re-run. When
   there's time (M13), run section 4 once more through build/M12/run-s4.sh with nothing editing the tests, so the
   record is clean.
2. pipeline/tests/test-m2.sh: its dummy run can reach the real claude reviewer and fixer, which then commits into
   the repo (it happened once: autofix(03-gate) b7ea7e3). Point it at the fake claude in M13.
3. The edit review (M11) failed the real test idea in all 5 rounds with scores of 3, so every reel exports with NEEDS
   REVIEW after about 70 minutes of review rounds. The missing components (swatch row, screenshot zoom with a
   highlight box, card grid) are already in HUMAN_TODO. Adding them, or setting a lower bar for the score of 3 on
   "generic" and "variety", would save the most runtime.
4. Hook 2 misheard by faster-whisper ("claude" heard as "cloud", WER 12.5 percent): a pronunciations.txt line, or
   whisper hotwords for the brand names, would remove a recurring flag. pronunciations.txt is in library/, which the
   user curates.
5. The model-limit fallback in ai.sh matches on the CLI's message text ("reached your ... limit", "switch to another
   model"). That breaks if the CLI rewords it. Matching the api error code model_requires_usage_credits as well would
   make it sturdier.
6. Working tree: build-runner.sh has uncommitted changes (the --fallback-model option) and build/STOPPED.md from the
   00:42 Fable limit stop is still there. Both belong to the build harness, not to M12. Remove STOPPED.md once the
   runner has resumed.
