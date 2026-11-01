# 05-hooks: Hooks (S5)

Built in M5 (the folder, the first schema and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S5, and 2.2.

## Purpose
Session A resumed (the research and the expansion are in its context; a run without a stored session, for example
one started from frozen fixtures, gets a new session seeded with facts.md, expansion.md and the gate verdict):
pipeline/bin/index-hooks rebuilds the hooks index when library/hooks.txt changed, pipeline/lib/hooks.py builds a
shortlist of templates (config hooks.shortlist, default 24: the user's hooks plus the 26 vendor formulas, every
family represented, weighted by win rate from library/.hooks.stats.json once there is data and uniform at first,
fit-for-problem-solution templates preferred), the model writes 12 to 20 hooks from at least 3 families (one per
template: a spoken line, an on-screen line, a concrete marker), hooks.py checks them and composes hooks.json, and
the same session then writes brief.md (2 to 3 thousand tokens: everything the script needs). Session A's job ends
here.

## Inputs
- 01-research/facts.md, 02-expansion/expansion.md and expansion.json, 03-gate/gate.json (the seed when the session is new)
- library/hooks.txt through library/.hooks.index.json and library/.hooks.stats.json (pipeline/bin/index-hooks)
- pipeline/vendor/ig-agent-skill/hooks.json (26 formulas, as extra shapes; mapped to the six families in hooks.py)
- library/profile/voice.md (how the user sounds; its measured pace wins over config voice.wpm), deliverables.txt
- config: hooks.*, voice.wpm, timeouts.hooks_seconds and brief_seconds, models.research

## Outputs (in runs/<id>/05-hooks/)
- hooks.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). The model's answers are validated against model.schema.json
  (hooks) and brief.schema.json (the brief) by ai()'s one schema retry; the rules below are checked by hooks.py and
  asked again in the same session up to config hooks.tries times (a quality loop, never an error). The last try
  writes what is valid with a NEEDS REVIEW flag; fewer than hooks.min_for_judge (4) valid hooks blocks the idea.
- hooks.json: idea_id, wpm, max_spoken_words, templates_considered, families, hooks[] (id h01.., template_id,
  template, template_source library|vendor, family, spoken, on_screen, marker, marker_kind, spoken_words,
  spoken_seconds, on_screen_words), rule_errors, dropped, notes, regenerated (after a judge-triggered regeneration)
- brief.md: a header (idea, keyword, deliverable, identity, video type, tones) plus the model's brief (tokens are
  measured as words x 1.3; config hooks.brief_tokens, default 2000 to 3000, up to hooks.brief_tries tries, then
  written with a NEEDS REVIEW flag)
- shortlist.json (the templates offered), prompt-*.md, calls/ (every model call), index-hooks.log
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 20 (block).

## Invariants
- 12 to 20 hooks from at least 3 families, one per template, every template_id from the index or the vendor list
- spoken: 8 words or fewer and under 3 s at the user's wpm (the cap is min(8, ceil(wpm x 3 / 60) - 1) words: 7 at 150 wpm)
- on-screen: 6 words or fewer
- every hook carries a concrete marker quoted from the spoken line: a named tool, a number or a time
- no em dash anywhere (the model's text is cleaned; an em dash in a template is read as a comma)
- the stage never edits library/hooks.txt; it writes only under runs/<id>/05-hooks/ and, through index-hooks, the
  derived files library/.hooks.index.json, hooks.lint.txt, .hooks.stats.json (created empty) and hooks.suggested.txt

## Regeneration (called by 06-judge)
`bash pipeline/stages/05-hooks/run.sh <run_dir> --regenerate <feedback.json>`: when the judge's hookscore filter
leaves fewer than config judge.min_survivors hooks, the judge calls this once. Session A is resumed with the
survivors and the failures (score, flags, weakest property), the model writes replacements, hooks.py merges the
survivors with the valid new hooks and rewrites hooks.json (the previous file is kept as
hooks-before-regenerate.json); the brief is not rewritten.

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(reason in result.json; not used by this stage), 20 block the idea (fewer than 4 valid hooks), anything else is a
code error and goes to the review and fix loop (BUILD_SPEC.md 4.2).

## Model and session
Session A resumed (pipeline/lib/session.sh session_call with --seed-if-new). Model: config models.research. Two
calls (hooks, brief) plus one per quality retry; no tools.

## dummy.sh
`bash pipeline/stages/05-hooks/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
