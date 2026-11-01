# Role: cut
# Stage: 07-script
# Task: cut

You are the cut pass of a reel script. Delete about 20 percent of the words without losing a fact. Answer with only
the JSON object described at the end.

{{NOTE}}
## The script (one beat per line: id, type, the display track, the spoken track, the card)

{{TEXT}}

## The numbers

- The display track has {{WORDS}} words now. Bring it to about {{TARGET}} words: between {{MIN_AFTER}} and {{MAX_AFTER}}
  words, never under {{FLOOR}}.
- Cut the spoken track the same way, sentence by sentence, so the two tracks keep saying the same thing.

## What must survive

- Every number, name, command, value and claim: {{MUST_KEEP}}. Deleting any of them fails the cut.
- Every beat, with its id and its order ({{HOOK_ID}} first, {{ASK_ID}} last). Shorten beats, never merge or drop one.
- Beat {{HOOK_ID}} is the hook the judge chose: copy its display and spoken tracks unchanged.
- The last beat keeps the keyword {{KEYWORD}} and its word repeated from the hook.
- The contractions, the "you" and "I", the short punchy sentences: cut filler, repeated ideas, throat-clearing,
  adjectives that add nothing, a second example where one does the job. Keep the sentence lengths uneven.
- Cards stay as they are unless a word you removed was in the card too.
- Never an em dash, no placeholder, nothing new added.

## Your answer

Only this JSON object: {"beats": [{"id": "<as listed>", "display": "...", "spoken": "...", "card": "..."}, ...],
"ask_line": "<the last beat's display line>", "notes": "<what you cut, one line>"}
