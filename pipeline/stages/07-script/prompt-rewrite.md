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
- The rhythm rule still holds: beats alternate between one sentence of 12 or 13 words and two or three sentences
  of 3 or 4 words; apart from the hook, no sentence of 5 to 11 words.

## Your answer

Only the JSON object: {"tone": "{{TONE}}", "beats": [{"id", "type", "display", "spoken", "emphasis", "card", "facts"}, ...],
"ask": {"keyword": "{{KEYWORD}}", "line": "..."}, "hook2": {"spoken": "..."}, "notes": "<what you changed, one line>"}
