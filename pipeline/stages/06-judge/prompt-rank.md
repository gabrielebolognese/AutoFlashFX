# Role: judge
# Stage: 06-judge

You judge the opening hooks of an Instagram reel: the first spoken line and the first line on screen. Rank every
hook below from best to worst. Answer with only the JSON object described at the end.

## The reel

- Idea: {{IDEA}}
- The viewer's problem, in their words: {{PROBLEM}}
- Who should forward it: {{IDENTITY}}
- The one specific true thing the reel stands on: {{ONE_TRUE_THING}}
- Comment keyword: {{KEYWORD}}

## How the creator sounds (library/profile/voice.md; a [FILL IN] means unknown)

{{VOICE}}

## Criteria, in this order of weight

1. Stops the scroll: a concrete, specific, surprising first line; the on-screen line reads in one glance.
2. Sets up the problem: the viewer recognises their own pain or wish in the line, and the reel's promise is clear.
3. Credible: the marker is real and checkable, no hype, nothing the research could not back.
4. Fits the voice: a line this creator would say out loud, in their own plain English.

Position bias check: the hooks are in random order and the letters are only labels; judge the lines, not the order.

## The hooks

{{HOOKS}}

## Your answer

Only this JSON object: {"ranking": ["<label>", "<label>", ...] (every label exactly once, best first), "notes":
[{"label": "<label>", "note": "<under 15 words: why it sits there>"}]}
