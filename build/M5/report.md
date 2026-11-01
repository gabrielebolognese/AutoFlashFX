# M5 report: Profile and hooks (S5, S6)

Built 2026-11-01 from BUILD_SPEC.md 2.2, 2.3, 2.5, section 5 (S5, S6), section 10 and section 12 (M5), and PLAN.md
(M5). Acceptance test green (numbers in "Test output summary" below); the M1, M2, M4 (fake sections) and limits
tests and the em dash scan pass with it. Two sections of the M5 test make real model calls (the indexer model over
library/hooks.txt, then the research and judge models on the frozen M4 outputs of the test idea); everything else
runs against the fake claude.

## What this batch built
- **The vendored tools** (pipeline/vendor/ig-agent-skill/): hookscore.py, beats.py, hooks.json, humanize.py,
  detect.py, slop.json, caption.py, LICENSE (MIT) and templates/voice.md from github.com/Jakeschincariol/
  instagram-agent-skill at commit d03c56bb (2026-09-13), recorded in VERSION; behavior untouched.
  `bash pipeline/bin/vendor-run <script.py> args` runs one of them with `python -I -X utf8`.
- **The hooks index** (pipeline/bin/index-hooks over pipeline/lib/hooks.py): library/.hooks.index.json with one
  entry per unique hook line of library/hooks.txt (id = first 10 hex of sha1 of the normalized text, family among
  the six of the spec, fits_problem_solution, blanks, the indexer's grammar note), rebuilt only when the file's hash
  changed and only for the ids not classified yet (one batched call to the indexer model, haiku; a second run with
  no change makes no call); library/hooks.lint.txt (the 6 problem lines of the user's file today: em dashes on
  lines 43, 64, 73 and 80, lost blanks on 53 and 54, which the indexer also noticed on its own);
  library/.hooks.stats.json (times picked, times won, judge scores per template, created empty);
  library/hooks.suggested.txt (new hook shapes the hooks model notices, in hooks.txt's format, never read by the
  runner). It ran once for real: 80 hooks classified (33 how-to-system, 20 story-confession, 10 mistake-warning, 7
  transformation, 6 myth-contrarian, 4 tools-listicle; 55 fit a problem-to-solution reel).
- **The profile** (pipeline/bin/build-voice-profile over pipeline/lib/voiceprofile.py): library/profile/voice.md
  and account.md. No library/voice/memo.* exists, so voice.md is the vendored template with [FILL IN]
  placeholders and account.md a placeholder draft that keeps the working assumption the research stages used so
  far; both are flagged NEEDS REVIEW by S5 until filled (HUMAN_TODO). The pace and the verbatim excerpts are
  measured anyway from the user's real speech: library/voice/reference_long.wav (66.6 s) transcribed with
  faster-whisper on CPU under the interpreter named in library/voice/engine.txt gives 195 words per minute and 5
  excerpts, written into voice.md, and config voice.wpm was set to 195. With a memo the same script transcribes it
  and has the script model draft both files from the transcript, keeping the user's English.
- **S5 Hooks** (pipeline/stages/05-hooks/run.sh, prompt.md, prompt-brief.md, prompt-regenerate.md,
  model.schema.json, brief.schema.json, schema.json): session A resumed, or started seeded with facts.md,
  expansion.md and the gate verdict when state.json holds no session id (pipeline/lib/session.sh
  `--seed-if-new`); index-hooks first; a template shortlist built by code (config hooks.shortlist 24: the user's
  hooks plus the 26 vendor shapes, every family represented, weighted by win rate once the stats have data and
  uniform at first, fit-for-problem-solution templates preferred, seeded by the idea id); the model writes 12 to
  20 hooks from at least 3 families, one per template (spoken line, on-screen line, a concrete marker); hooks.py
  checks the rules (the spoken cap min(8, ceil(wpm x 3 / 60) - 1) words, so 7 at 150 wpm and 8 at the measured
  195; 6 on-screen words; the marker quoted from the line and a tool, a number or a time; known template ids; no
  repeats) and the stage asks again in the same session with the exact problems, up to 3 times (the last try
  writes the valid hooks with a flag; fewer than 4 valid blocks the idea); then the same session writes brief.md
  (a header plus the model's brief, 2000 to 3000 tokens as words x 1.3, up to 3 tries, then a flag). New hook
  shapes the model noticed go to library/hooks.suggested.txt. `run.sh <run_dir> --regenerate feedback.json` is the
  judge's one regeneration (survivors kept, replacements merged, the brief untouched).
- **S6 Hook judge** (pipeline/stages/06-judge/run.sh, prompt-rank.md, prompt-pair.md, rank.schema.json,
  pair.schema.json, schema.json, with pipeline/lib/judge.py): the vendor hookscore.py on every spoken line (under
  50 or a dealbreaker is out; fewer than 4 left makes S5 regenerate once, then the judge continues with the best
  available); two full rankings by the judge model in two independent sessions with different seeded shuffles,
  merged by Borda count; the top 4 compared pairwise in both orders in one call (12 comparisons); the winner by
  pairwise wins (ties by Borda points, then hookscore), the runner-up next; judge.json with the winner (hook 1),
  the runner-up (hook 2), the reasons and the whole trail (filter, rankings, Borda, pairwise); then
  library/.hooks.stats.json updated by the wrapper (picked per template, won for the winner's, the normalized Borda
  score). Criteria: stops the scroll, sets up the problem, credible, fits the voice.
- **Config:** `hooks` (shortlist, per_family, fit_weight_other, min_hooks, max_hooks, min_families, min_for_judge,
  spoken_max_words, spoken_max_seconds, on_screen_max_words, tries, brief_tokens, brief_tries), `judge`
  (min_hookscore, min_survivors, top_n), the timeouts index_seconds, hooks_seconds, brief_seconds, judge_seconds,
  transcribe_seconds, profile_seconds; voice.wpm 195 (measured).
- **Tests:** pipeline/tests/test-m5.sh (four sections, see below), the fake fixtures pipeline/tests/fixtures/fake/m5
  (14 hooks, the two rankings, the pairwise answers, the brief as markdown) and fake/m5-regen (12 hooks of which 3
  pass hookscore, 10 replacements), and the frozen 05-hooks and 06-judge outputs of the test idea under
  pipeline/tests/fixtures/runs/test-idea/ (hooks.json, brief.md, shortlist.json, judge.json, scores, rankings,
  Borda, pairs, tally, the model answers under calls/), which M6 starts from.

## Files
- New: pipeline/vendor/ig-agent-skill/** (with VERSION), pipeline/lib/{hooks.py, judge.py, voiceprofile.py},
  pipeline/bin/{index-hooks, build-voice-profile, vendor-run}, pipeline/stages/_prompts/{index-hooks.md,
  index-hooks.schema.json, voice-profile.md, voice-profile.schema.json}, pipeline/stages/05-hooks/{run.sh,
  prompt.md, prompt-brief.md, prompt-regenerate.md, model.schema.json, brief.schema.json},
  pipeline/stages/06-judge/{run.sh, prompt-rank.md, prompt-pair.md, rank.schema.json, pair.schema.json},
  library/profile/{voice.md, account.md}, library/hooks.suggested.txt, pipeline/tests/test-m5.sh,
  pipeline/tests/fixtures/fake/{m5, m5-regen}/*, pipeline/tests/fixtures/runs/test-idea/{05-hooks, 06-judge}/**,
  build/M5/report.md.
- Changed: pipeline/stages/05-hooks/{CONTRACT.md, schema.json, dummy.sh}, pipeline/stages/06-judge/{CONTRACT.md,
  schema.json, dummy.sh}, pipeline/lib/session.sh (`--seed-if-new`), config.json, pipeline/tests/test-m4.sh
  (section 2), run.sh (the build status comment), CLAUDE.md, DECISIONS.md (items 113 to 138), build/progress.md,
  build/HUMAN_TODO.md, pipeline/tests/fixtures/runs/test-idea/README.txt; pipeline/vendor/.gitkeep removed.
- Earlier milestones touched, because M5 depends on them: M4's session.sh (a session key with no stored id is
  seeded at once, which is how a run started from frozen fixtures gets the research into S5's context) and
  test-m4.sh section 2 (it now removes the sandbox's library/profile/account.md before its run: M5 drafted that
  file, and the section asserts the NEEDS REVIEW flag for a missing one); M2's dummies and first schemas of
  05-hooks and 06-judge (refined for the real files); M1's config.json. M1, M2, M3 (limits) and M4 (fake sections)
  pass unchanged otherwise (see below). Not built from PLAN.md: pipeline/bin/setup-venv (the whisper-only
  .venv-tts): the interpreter named in library/voice/engine.txt already has faster-whisper and the small model
  cached, and spec M7 says to install nothing when engine.txt exists (DECISIONS.md 134); M7 decides.

## How to run the test
```
bash pipeline/tests/test-m5.sh                      # everything: 1 and 2 with the fake claude, 3 and 4 with the real models
M5_SECTIONS="1 2" bash pipeline/tests/test-m5.sh    # the units and the two fake runs (no model, about four minutes)
M5_SECTIONS="3 4" M5_FREEZE=1 bash pipeline/tests/test-m5.sh   # the real sections, and rewrite the frozen 05-hooks and 06-judge fixtures
bash pipeline/tests/run-all.sh                      # M1 to M5, limits and the em dash scan (about 65 minutes)
bash pipeline/bin/index-hooks                       # rebuild the real hooks index and lint (no call when hooks.txt is unchanged)
bash pipeline/bin/build-voice-profile [--force]     # rebuild library/profile/voice.md and account.md
```
KEEP_SANDBOX=1 keeps the temporary roots. The tests never touch the real ideas.txt, runs/, exports/ or logs/; the
runs happen in a sandbox copy of the repo (a fixer, none was needed, would commit there).

## Test output summary
`bash pipeline/tests/test-m5.sh`: 232 checks, 0 failed (sections 1 and 2: `198 passed, 0 failed` in about four
minutes; sections 3 and 4: `34 passed, 0 failed`, the index call 34 s, the real S5 and S6 run 6 min 24 s). The
sections, in the order of the test:

1. Units, no model (146 checks): hooks.py (quotes, em dashes, a lost blank, a duplicate and CRLF in a hooks file;
   the id stable across quotes and case; the index cache: 5 to classify, then unchanged, then one new line means
   one id to classify; the lint's four kinds of line; the 26 vendor formulas; the shortlist of 24 from every
   family with library and vendor templates, deterministic per seed, no broken-blank template, the win rate
   weighting the choice once there is data; the spoken cap 7, 8, 6 and 8 words at 150, 165, 140 and 195 wpm; the
   fixture answer passing every rule and a bad answer named problem by problem, nothing written without --force,
   the valid 4 written with --force, the regeneration merge; the brief measure in and out of range; the stats and
   the pace), index-hooks with the fake indexer (one call with the indexer model and no tools, the prompt lists
   every id, every hook classified, the files written, a second run with no call), judge.py (hookscore on the
   fixtures: 14 of 14 and 3 of 12; the feedback file; the candidates in both modes; labels and shuffles; a lenient
   ranking parse; Borda with ties; 12 comparisons in both orders; the tally with tie-breaks; judge.json valid),
   voiceprofile.py (the pace with a long pause removed, 3 excerpts, the template draft with the Pace line filled,
   the model-answer path, is-draft, set-wpm changing one line, the account draft, build-voice-profile in the
   sandbox measuring the pace from reference.wav, existing files kept), and session_call --seed-if-new (the first
   call is the seeded one with the INFO line; the next resumes).
2. S5 and S6 through run.sh with the fake claude (52 checks): a run built from the frozen M4 outputs resumes at
   S5 (`START ... (resumed at picking hooks, 3 stages done)`), session A is seeded, 14 hooks from 5 families,
   brief.md of 2461 tokens, 14 of 14 through hookscore, judge.json with a winner and a runner-up, two complete
   rankings with different shuffles, 12 pairwise results, the stats with one pick per template and the win, 6 model
   calls in order (indexer; research with a new session, research resuming it; three fresh judge calls), no tools,
   no em dash, the idea gone after the dummy export. Then the regeneration path: `WARN S6: only 3 of 12 hooks
   passed hookscore (min 50, no dealbreaker): asking S5 to regenerate once`, S5 regenerates in session A (3
   survivors plus 10 replacements, hooks-before-regenerate.json kept, regenerated.json written), the judge re-scores
   13 of 13 and finishes, `DONE exported #2`, 6 calls, no ERROR.
3. index-hooks with the real indexer over the real library/hooks.txt (12 checks): 80 hooks classified in 34 s,
   families how-to-system 32, story-confession 22, mistake-warning 9, transformation 7, tools-listicle 5,
   myth-contrarian 5 (the second real run; the first gave 33, 20, 10, 7, 4, 6), 55 fit; the lint names lines 53 and
   54 (broken blanks) and 43, 64, 73, 80 (em dashes); a second run makes no model call.
4. The test idea with the real models (22 checks): S5 in 4 min 44 s: the seeded session, one retry (a 9-word
   hook), 16 hooks from all 6 families (11 from the user's hooks.txt, 5 vendor shapes), spoken cap 8 words at 195
   wpm, 3 new hook shapes written to hooks.suggested.txt, the brief 2753 tokens after one retry (the first draft
   was 3214); S6 in 53 s: 8 of 16 hooks passed hookscore, hook 1 `Why your Claude Code cards all look identical.`
   (on screen `IDENTICAL CARDS LOOK AI`), hook 2 `5 AI looks to avoid. One is Anthropic's.`, four pairwise reasons
   for the winner; the brief resumed the hooks call's session, the judge calls were fresh; the stats record the
   picks and the win; no em dash. The frozen fixtures were written by this run (M5_FREEZE=1). The first real run,
   before two fixes of this batch, gave 14 hooks, a 2594-token brief and 5 of 14 through hookscore.

Earlier milestones, run after the changes: `test-m1.sh: 96 passed, 0 failed`, `test-limits.sh: 94 passed, 0
failed`, `test-m4.sh: 200 passed, 0 failed` (sections 1 and 2), `test-m2.sh: 220 passed, 0 failed`,
`no_emdash: clean`.

## Known gaps
- voice.md and account.md are placeholder drafts until the user fills them or records the memo; the hooks, the
  judge and the script run on default voice assumptions and every reel carries the two NEEDS REVIEW flags.
- The measured pace (195 wpm) comes from a reference read, not from a memo; if the user's reel delivery is slower
  the spoken cap (8 words) is one word too generous. HUMAN_TODO says where to change it.
- hookscore.py is strict: in the real runs 5 of 14 and 8 of 16 hooks passed its 50-point bar, so the judge usually
  ranks a third to a half of what S5 wrote; the regeneration path covers the case of fewer than 4. The vendor's
  word count treats "1.1.1" as three words, which the cap inherits.
- The brief's token count is an estimate (words x 1.3); the real model's first draft was over the range in both
  real runs and the retry brought it back. A model that misses three times gets a flag, not a block.
- The judge model answered every comparison and every label in the real runs; the lenient parse and the WARN lines
  cover a partial answer but were only exercised with the fake.
- The stats file starts empty, so the shortlist is uniform until a few reels have run; the weighting is unit-tested
  with a synthetic stats file.
- S1 to S4 do not write to library/hooks.suggested.txt (spec 2.2 says "noticed during research"); S5's hooks
  model does, which is where the templates are in front of a model.

## HUMAN_TODO items added
- M5: fill library/profile/voice.md and account.md (the [FILL IN] lines) or record library/voice/memo.* and run
  `bash pipeline/bin/build-voice-profile --force`; until then two NEEDS REVIEW flags per reel.
- M5: the measured pace is 195 words per minute (voice.md and config voice.wpm); change both if a reel is slower.
- M5: library/hooks.lint.txt lists the 6 problem lines of hooks.txt (em dashes on 43, 64, 73, 80; lost blanks on
  53, 54).
- M5: library/.hooks.stats.json and library/hooks.suggested.txt are written by the pipeline under library/; commit
  the stats when wanted, move the suggested shapes into hooks.txt by hand.
