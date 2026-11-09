# 09b-text: Visual plan, text pass (S9b)

Built in M10, the caption modes and the text budget in M15. Spec: BUILD_SPEC.md section 5, S9 9b and Motion and energy rules
E3 and E4; DECISIONS.md 215 to 232 and 306 to 312.

## Purpose
Every on-screen card's text (6 words or fewer, 100 characters of text on screen at most), the caption entries (word-mode
runs of 1 to 4 words, each word timed to words.json, the emphasis words; group-mode groups of 2 to 6 words with an anchor),
the labels and tags. The visual_director covers the words and writes the texts; pipeline/lib/visual/plan9.py times the
chunks from words.json (the words and their order never change), decides each entry's mode with the choice rule
(finalize_captions: word mode under any text, groups where the hero zone holds no text and the beat is important or has no
graphic; a director's `mode` and `anchor` hint wins where the rules allow), has pipeline/lib/visual/kinetic.py lay out every
group and set every entry's motion, turns the texts into prop overrides of the 9a instances and derives the honesty labels.

## Inputs
- 09a-animations/plan.json, 07-script/script.json, 08-voiceover/words.json
- styles/paper-cards/tokens.json (caption limits, the font for the width), style.md and tweaks.md
- the digests in 09b-text/digest/ (timeline.md, scenes.md, chunks.md: the baseline chunks and, per scene, its importance,
  its text and graphics and the pipeline's own choice of mode)

## Outputs (in runs/<id>/09b-text/)
- plan.json is the primary output (schema.json from pass-schemas.py): pass text, captions[] (scene, start_ms,
  end_ms, mode word | group, importance, words[] with word, start_ms, end_ms, emphasis; groups also anchor and layout; every
  entry its motion), overrides[] (scene, component, prop, text: the card texts
  the pass changed), cards[] (every on-screen text after the overrides: scene, component, prop, text, zone, words),
  labels[] (honesty, tag, kicker), notes.
- plan.candidate.json, prompt.md, prompt-retry.md, calls/, digest/, stage.log as in 09a.

## Invariants (plan_validate.py, parts captions)
- word runs of 1 to 4 words, groups of 2 to 6, at most 3 emphasis words, every caption word a spoken word of words.json at that
  time, in order, none during the hook headline or on the end card; a word-mode word fits the caption line (tokens.json
  zones.caption.max_width) at its own size
- rule caption_modes (E3, E4): word mode whenever any other text is on screen, a group over no text and no graphic, a group laid
  out by kinetic.py (at least 3 fonts from 3 words, the anchor 2 to 3 times the caption size, the stacked words as tall as the
  anchor within 2 px, no word under the caption size, inside the group caption zone, clear of the right rail, asymmetric), every
  caption moving (a rise of 8 to 16 px or a turn of 2 to 4 degrees per word; a group's rise of 20 to 40 px or turn of 3 to 6)
- rule text_budget: at most 100 characters of non-caption text on screen at any moment (the CTA scene aside); rule text_size:
  no graphic text under the caption size (a size the plan chooses is an error, a size the library bakes in a warning)
- title-like props 6 words or fewer (config visual.title_max_words), body props 14 or fewer
- a component showing mock or sourced data has its honesty label in labels

## Exit codes
0 done, 10 drop, 20 block, anything else a code error.

## Model and session
Fresh visual_director session (config models.visual_director, opus, for the first plan; models.visual_director_fix, sonnet, when the pass runs again after a failed review round; models.visual_director_escalation from caps.review_rounds_opus failed rounds on: opus, fable only on an idea marked [important]; DECISIONS.md 334 and 335), one retry with the exact errors.

## dummy.sh
Writes a small valid text plan; honors the planted REELS_DUMMY_* lists.
