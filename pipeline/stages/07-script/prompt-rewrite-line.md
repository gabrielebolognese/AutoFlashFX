# Role: script
# Stage: 07-script
# Task: rewrite-line

The voice engine could not say one line of the script clearly ({{REASON}}). Rewrite beat {{BEAT_ID}}'s spoken track in
simpler words. Answer with only the JSON object described at the end.

{{NOTE}}
## The line

- display: {{DISPLAY}}
- spoken (what the voice tried to say, {{WORDS}} words): {{SPOKEN}}
- card: {{CARD}}

## The whole script, spoken track (for context; change only beat {{BEAT_ID}})

{{ALL}}

## Pronunciations to apply

{{PRONUNCIATIONS}}

## Rules

- Same meaning, same facts, same numbers (written out in words); nothing new.
- {{MAX_WORDS}} words or fewer: shorter or equal, never longer.
- Words that are easy to say: no hex code read letter by letter, no slash, no at-sign, no abbreviation, no symbol;
  name the thing instead ("the install command", "Anthropic's terracotta") when the display carries the exact value.
- Plain spoken English, contractions welcome, never an em dash, no placeholder.
- Never respell a word to change how it sounds ("Clawed" for "Claude", "Klod"): every name stays spelled as the
  spoken track spells it now, because the captions are built from the spoken words and the voice check compares the
  transcription with them. The voice step handles pronunciation itself; you may only choose other words around a
  name, or say the thing without the name.
- Give the display track too: the same line as the display shows it (digits and exact values allowed there), changed
  only where a word changed.

## Your answer

Only this JSON object: {"spoken": "...", "display": "...", "notes": "<what you simplified, one line>"}
