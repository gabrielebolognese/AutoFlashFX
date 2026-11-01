# 06-judge: Hook judge (S6)

Built in M5 (the folder, the first schema and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S6.

## Purpose
Scripts plus the judge model (config models.judge) in fresh sessions:
1. Filter with the vendor's hookscore.py (pipeline/vendor/ig-agent-skill, run through pipeline/lib/judge.py): a
   hook with a dealbreaker or a score under config judge.min_hookscore (50) is out. Fewer than judge.min_survivors
   (4) left: 05-hooks regenerates once (`run.sh <run_dir> --regenerate feedback.json`, session A with the failures
   as feedback), then the judge continues with the best available (the survivors when at least 2, else the top 4
   by score).
2. Two full rankings by the judge model with different shuffles (two independent calls, so the second ranking
   never sees the first: that is what cancels position bias), merged by Borda count (a hook at position p of n
   earns n - 1 - p points per ranking; ties by the first ranking), then the top judge.top_n (4) compared pairwise
   in both orders in one call (12 comparisons for 4 hooks). Criteria: stops the scroll, sets up the problem,
   credible, fits the voice (library/profile/voice.md).
3. The winner is the hook with most pairwise wins (ties: Borda points, then hookscore); the runner-up the next
   one. judge.json is written by judge.py compose and library/.hooks.stats.json is updated by hooks.py (picked
   for every template used in hooks.json, won for the winner's template, the normalized Borda score per template).

## Inputs
- 05-hooks/hooks.json (and 02-expansion/expansion.json for the reel's context in the prompts)
- pipeline/vendor/ig-agent-skill/hookscore.py
- library/profile/voice.md, library/.hooks.stats.json
- config: judge.min_hookscore, judge.min_survivors, judge.top_n, timeouts.judge_seconds, models.judge

## Outputs (in runs/<id>/06-judge/)
- judge.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). The model's answers are validated against rank.schema.json and
  pair.schema.json by ai()'s one schema retry; a ranking with missing or unknown labels is read leniently (unknown
  labels ignored, missing ones appended in label order), a comparison with a winner outside its pair is ignored.
- judge.json: winner (hook 1: the full hook object plus hookscore, borda_points, pairwise_wins), runner_up (hook 2,
  the alternate clip), reasons (the model's pairwise reasons and ranking notes for both, plus the counts), criteria,
  filtered_out (id, spoken, score, flags, weakest, reason), hookscore per hook, candidates and candidates_mode,
  rankings (shown order, ranking, notes, complete), borda, top, pairwise (n, first, second, winner, why),
  pairwise_wins, regenerated, calls, checked
- scores.json (hookscore per hook), labels-1.json, labels-2.json, ranking-1.json, ranking-2.json, borda.json,
  pairs.json, tally.json, regenerate-feedback.json and regenerated.json (after a regeneration), prompt-*.md, calls/
- library/.hooks.stats.json updated by the bash wrapper through hooks.py stats-update, never by the model
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 20 (block: fewer than 2 hooks to judge).

## Invariants
- criteria: stops the scroll, sets up the problem, credible, fits the voice
- winner and runner-up are different hooks from hooks.json
- the two ranking calls are independent sessions with different shuffles; the pairwise call sees every pair twice
- the stats file is written only after judge.json, so a crash never counts a pick without its verdict

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(not used), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and
fix loop (BUILD_SPEC.md 4.2).

## Model and session
Fresh sessions (no --session): two ranking calls and one pairwise call, model config models.judge, no tools.

## dummy.sh
`bash pipeline/stages/06-judge/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
