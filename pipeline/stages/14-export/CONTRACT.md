# 14-export: Caption and export (S14)

Built in M12 (the folder, the first schema and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S14, and
section 8; DECISIONS.md (M12).

## Purpose
The caption from the brief and the script: the first line is hook 1 word for word (125 characters or fewer, where
the feed cuts), the script model writes the body and the one ask (the comment keyword) plus 3 to 5 hashtags and
the search terms; pipeline/lib/caption.py composes and checks it (one ask, the keyword once, no second ask, no
link, hashtags one word each and none generic, the solution rules of S7: no FlashFX mention unless the solution is
flashfx, nothing implying the reel was made in FlashFX, no ad language), runs humanize.py on it and the vendor
caption.py lint (no FAIL), and writes export.json: everything the runner's export step (pipeline/lib/export.py)
renders into Ncaptions.txt and copies into exports/N/. The export itself (the number, the move in one step, the
idea's removal, the history line with the solution type) is the runner's, after this stage.

## Inputs
- 07-script/script.json (hook 1, the beats' display lines, the ask, the cited facts), 06-judge/judge.json (hook 2),
  02-expansion/expansion.json and solution.json (the problem, the identity, the keyword and its deliverable, the
  solution), 05-hooks/brief.md (the one idea), 01-research/research.json (the claims' URLs and dates)
- 13-render/final.mp4 and hook2.mp4 (named in export.json files), state.json flags (NEEDS REVIEW)
- library/profile/voice.md (the voice hints), pipeline/vendor/ig-agent-skill/{caption.py, humanize.py, slop.json}
- config: caption.* (first_line_max_chars 125, hashtags [3, 5], body_chars, tries 2), timeouts.caption_seconds,
  models.script

## Outputs (in runs/<id>/14-export/)
- export.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). caption, hashtags (5 or fewer), search_terms, keyword,
  deliverable, deliverable_status, link, solution {type, name, url}, hooks {hook1, hook2}, needs_review (every
  flag as "<stage>: <text>"), facts (claim, url, checked: the claims the script cites), files {reel, hook2} (the
  rendered videos, relative to this folder), lint (caption.py's result), humanize, checks.
- caption.txt (the caption and the hashtags, ready to paste), caption-data.json (what the prompt got),
  prompt-caption.md (and the retry prompt), calls/
- the runner renders exports/N/Ncaptions.txt from export.json in the format of BUILD_SPEC.md section 8 (CAPTION,
  HASHTAGS, COMMENT KEYWORD, SOLUTION, HOOKS, NEEDS REVIEW only when flagged, FACTS AND SOURCES, RUN) and moves
  N.mp4, Ncaptions.txt and Nhook2.mp4 into exports/N/
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).

## Invariants
- caption first line = hook 1, 125 characters or fewer; one ask (the keyword, once, as "Comment KEYWORD"); at most 5
  hashtags; no em dash (humanize.py, then undash)
- the solution rules: FlashFX named only when solution.type is flashfx; never "made in FlashFX"; no sales phrase
- NEEDS REVIEW lists every flag in state.json; the section is left out when there is none
- a caption that still breaks a rule after config caption.tries answers is written anyway with a NEEDS REVIEW flag
  (a quality loop, never an error)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), anything else is a
code error and goes to the review and fix loop (BUILD_SPEC.md 4.2): a failed model call after ai()'s own retries,
a missing input, caption.py failing.

## Model and session
Model: config models.script, a fresh session for the caption; the one retry resumes it (a lost session gets the
full prompt with the problems appended). Tools: none.

## dummy.sh
`bash pipeline/stages/14-export/dummy.sh <run_dir>` writes fake outputs that validate against schema.json (its
solution comes from 02-expansion/solution.json when the run has one), sleeps REELS_DUMMY_SECONDS (default 1) and
honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK, REELS_DUMMY_FLAG and REELS_DUMMY_INVALID
lists (see pipeline/lib/dummy.sh). No model calls.
