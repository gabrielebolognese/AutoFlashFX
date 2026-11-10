# M20 Formats and the timeline: report

Built 2026-11-10 (one batch, Sonnet 5.5). The gate of 14.13 ran first: `preflight --channel flashfx` passes (READY, 8 tools, 2 python packages, 9 files).

## What I built

- **format.json and the runner reading it (14.7, DECISIONS 365).** `pipeline/formats/problem-solution-reel/format.json` (today's S1 to S13 in today's order, then the new
  `timeline` stage, then S14), `pipeline/schemas/format.schema.json`, `pipeline/lib/formats.py` (load, validate, stage table, stage folder lookup, routes, session groups,
  prompt overrides, required files, template; `python pipeline/lib/formats.py list|validate|stages|routes|session|prompt|...`). state.py's stage table is the channel's format
  (a run stores `format` and `stage_order`), the runner takes every stage's folder from it, stage_begin gives S1, S2, S4 and S5 their session key (group A), state.py enforces the
  reopen routes (gate -> angle, angle -> gate, review -> its owners), the review's STAGE_ORDER is the routes of 12-review, new-channel reads the template and the platforms from it.
- **The format keys moved (14.4, DECISIONS 366).** research, hooks, judge, script, visual, caption and review (minus the four safety keys) are the format's `config` block, values
  unchanged (the resolved config of flashfx equals the old one; build/M20/format-keys-before.json). The channel-file checks of preflight (voice, sound map, style files, tokens,
  catalog, brand kit, hooks, fill_in) are the format's `required_files`; config.py puts them into the resolved preflight.require, so a missing file stops that channel only.
- **The timeline (14.8, DECISIONS 367).** `pipeline/schemas/timeline.schema.json` (version 1), `pipeline/lib/timeline/` (common.py, compose.py, check.py, render_ffmpeg.py,
  `python pipeline/lib/timeline build|check|render|validate`), the stage `pipeline/stages/timeline/` (run.sh builds and checks, dummy.sh, schema.json, CONTRACT.md). check.py compares
  the timeline with final.mp4 (within 1 frame), words.json, cues.json, the composition (every host has a layer, every selector is a host), the plan's components, the captions and
  the sources (size, sha256).
- **The footage family (DECISIONS 368).** `pipeline/stages/timeline-render/` (check, then ffmpeg render of timeline.json inside heavy_run), render_ffmpeg.py, and the test-only
  format `pipeline/tests/formats/footage-dummy/` (ingest, cut, timeline-render, 14-export; footage.py; the 3 clips are made by the test with ffmpeg because *.mp4 is not in git).
- **FlashFX names out of the shared stages (14.5, 14.12, DECISIONS 369).** 12-review's branding paragraph is the format's prompt override
  (`prompts/12-review-rules.md`, `{{BRAND}}`), `pipeline/lib/review/` reads the brand name and `review.branding.own_solution_type` (config), other shared files lost their examples;
  `isolation_scan.py` has the names check, test-isolation part 1 runs it and plants a name.
- **Smaller changes:** logcheck.py knows the new activities; test sandboxes put the energy keys in the sandbox channel.json; test-m2 counts 17 stages.

## Files

New: pipeline/lib/formats.py, pipeline/lib/timeline/*, pipeline/schemas/format.schema.json and timeline.schema.json, pipeline/formats/problem-solution-reel/format.json and
prompts/12-review-rules.md, pipeline/stages/timeline/*, pipeline/stages/timeline-render/*, pipeline/tests/formats/footage-dummy/*, pipeline/tests/test-m20.sh,
build/M20/format-keys-before.json, build/M20/fingerprint/, DECISIONS.md 365 to 370.
Changed: config.json, pipeline/lib/{state.py, runner.sh, stage.sh, config.py, common.sh, newchannel.py, history.sh, status.sh, logcheck.py, platform_lib.py, voiceover.py},
pipeline/lib/review/{common, edit, mechanical, route, energy, style_check, __main__}.py, pipeline/stages/{01-research, 02-expansion, 04-angle, 05-hooks}/run.sh (session key),
pipeline/stages/12-review/{prompt.md, run.sh, model.schema.json, CONTRACT.md}, pipeline/platforms/instagram-reels/render.py (a comment),
pipeline/tests/{lib.sh, sandbox-config.py, isolation_scan.py, test-isolation.sh, test-m2.sh}, CLAUDE.md, build/progress.md, build/HUMAN_TODO.md.
Earlier milestones touched: M1 (preflight config), M2 (state, runner, test-m2), M4 (session key), M11 (12-review), M13 (logcheck), M18 (config.py, newchannel.py, test lib), M19 (new-channel).

## How to run the test

`bash pipeline/tests/test-m20.sh` (sections 1 to 8, about 25 minutes, no model call; `M20_SECTIONS="1 2"`; `M20_RECORD=1` rewrites build/M20/fingerprint/).

## Test result

See the final lines of this report (written after the last run).

## An incident worth knowing

My first run of test-m20 section 3 did not have the fake claude on. The footage render failed (a real bug), the runner's error system called the real reviewer and fixer, and the
fixer's commit `autofix(timeline-render)` swept my uncommitted pipeline/ work into the repository (and the tree guard put back CLAUDE.md and DECISIONS.md, which I rewrote).
Its two findings were right and are kept: the timeline's sources were never loaded into the render's registry, and ffmpeg 9 wants `-/filter_complex` instead of
`-filter_complex_script`. test-m20 now turns the fake claude on for every section. The known-issues.md line the fixer wrote stays.

## Known gaps

- `bash pipeline/tests/run-fake.sh --compare build/M17/baseline` (the baseline rule, about 7 hours) was not run in this batch. The earlier tests M20 touches were run in part
  (see the result lines); tests that were already failing before (test-m2, m3, m6, m7) are unchanged in kind.
- No finished real FlashFX run folder exists (the M12 and M13 runs were made in temporary roots), so "a copy of a finished real run folder" is the frozen test-idea run, which is
  a frozen copy of the real M12 run; test-m20 also checks every `channels/*/runs/*` that has a final.mp4, and finds none today.
- S13 was not rendered for the timeline test: final.mp4 is made from the frozen draft and the frozen voice (the timeline needs only its length, size and rate).
- The sound files in the timeline are `base: abs` when the pack is outside the channel folder (only in the tests); in the real channel they are `base: channel`.

## HUMAN_TODO items added

- M20: nothing to do (an information line: the format settings are now in pipeline/formats/problem-solution-reel/format.json).
