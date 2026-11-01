# 09b-text: Visual plan, text pass (S9b)

Built in M10. Spec: BUILD_SPEC.md section 5, S9 9b; DECISIONS.md 215 to 232.

## Purpose
Every on-screen card's text (6 words or fewer), the caption chunks (1 to 4 words, each word timed to words.json,
the emphasis words), the labels and tags. The visual_director groups the words and writes the texts;
pipeline/lib/visual/plan9.py times the chunks from words.json (the words and their order never change; a chunk
wider than the caption line is split), turns the texts into prop overrides of the 9a instances and derives the
honesty labels from the components.

## Inputs
- 09a-animations/plan.json, 07-script/script.json, 08-voiceover/words.json
- styles/paper-cards/tokens.json (caption limits, the font for the width), style.md and tweaks.md
- the digests in 09b-text/digest/ (timeline.md, scenes.md, chunks.md: the baseline chunks)

## Outputs (in runs/<id>/09b-text/)
- plan.json is the primary output (schema.json from pass-schemas.py): pass text, captions[] (scene, start_ms,
  end_ms, words[] with word, start_ms, end_ms, emphasis), overrides[] (scene, component, prop, text: the card texts
  the pass changed), cards[] (every on-screen text after the overrides: scene, component, prop, text, zone, words),
  labels[] (honesty, tag, kicker), notes.
- plan.candidate.json, prompt.md, prompt-retry.md, calls/, digest/, stage.log as in 09a.

## Invariants (plan_validate.py, parts captions)
- chunks of 1 to 4 words, at most 3 emphasis words, never wider than tokens.json zones.caption.max_width, every
  caption word a spoken word of words.json at that time, in order, none during the hook headline or on the end card
- title-like props 6 words or fewer (config visual.title_max_words), body props 14 or fewer
- a component showing mock or sourced data has its honesty label in labels

## Exit codes
0 done, 10 drop, 20 block, anything else a code error.

## Model and session
Fresh visual_director session (config models.visual_director), one retry with the exact errors.

## dummy.sh
Writes a small valid text plan; honors the planted REELS_DUMMY_* lists.
