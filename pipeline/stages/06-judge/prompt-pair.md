# Role: judge
# Stage: 06-judge

Compare the four best opening hooks of an Instagram reel in pairs. Every pair appears twice, once in each order:
judge each numbered comparison on its own and pick the hook that would make more of the right viewers stay for
the reel. Answer with only the JSON object described at the end.

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

## The hooks and the comparisons

{{PAIRS}}

## Your answer

Only this JSON object: {"comparisons": [{"n": 1, "winner": "<the label of the better hook in that comparison>",
"why": "<under 20 words>"}, ...]}, one entry per comparison number, all of them.
