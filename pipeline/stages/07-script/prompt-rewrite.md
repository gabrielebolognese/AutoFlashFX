# Role: script
# Stage: 07-script
# Task: rewrite

Draft {{DRAFT_LABEL}} ({{TONE}}) went through the cut pass and the scripted checks, and some checks failed. Rewrite
it: fix exactly the points below, keep everything else as it is, and answer with the complete JSON object (every
beat, not only the changed ones).

{{NOTE}}
## The failing checks (round {{ROUND}} of {{ROUNDS}})

{{FEEDBACK}}

## The current version (after the cut pass and the clean-up; start from this one)

{{DRAFT_JSON}}

## Rules that still hold

- Beat 1's display is hook 1's line word for word: {{HOOK_SPOKEN}}
- One ask only, the last beat, with the keyword {{KEYWORD}} and one word repeated from the hook.
- The final script must run {{FINAL_LO}} to {{FINAL_HI}} words in total (no cut pass follows this rewrite), no beat
  over {{BEAT_MAX_WORDS}} words, every factual statement from facts.md in the claim's own strength, numbers written
  out in the spoken track, never an em dash, no placeholder.
- Above everything, a viewer who has never heard of the tool must get the point on one listen: full sentences with
  a subject and a verb, plain words, every beat following from the one before (so, because, but, then). Fixing a
  check never turns sentences into fragments and never adds a term the viewer cannot place.
- The solution rules still hold: FlashFX is named only when it is the reel's solution, never pitched, and nothing
  says or implies this reel was made in FlashFX.

## Your answer

Only the JSON object: {"tone": "{{TONE}}", "beats": [{"id", "type", "display", "spoken", "emphasis", "importance", "card", "facts"}, ...],
"ask": {"keyword": "{{KEYWORD}}", "line": "..."}, "hook2": {"spoken": "..."}, "notes": "<what you changed, one line>"}
