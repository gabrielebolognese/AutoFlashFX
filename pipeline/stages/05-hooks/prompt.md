# Role: research
# Stage: 05-hooks

You researched this idea and wrote its expansion, and the gate passed it. Now write the hooks: the first spoken
line of the reel and the first line on screen, one pair per template, from the templates below. Answer with only
the JSON object described at the end.

## The idea

{{IDEA}}

## The expansion (what the reel is about; the gate passed it)

{{EXPANSION}}

## How I sound (library/profile/voice.md; a [FILL IN] means unknown: never invent it)

{{VOICE}}

{{NOTE}}
## The templates (write {{MIN}} to {{MAX}} hooks, one per template, from at least {{MIN_FAMILIES}} families)

Each line gives the template_id, the family, whether the template fits a problem-to-solution reel, its win rate
so far (uniform until there is data) and the template itself: `__` or {braces} mark what you fill. Choose the
templates that can carry this idea. Prefer the ones that fit problem to solution, unless the angle is a personal
story. Skip a template that cannot carry this idea without bending the facts. Spread the hooks over several
families so the judge has a real choice.

{{TEMPLATES}}

## Writing each hook

- spoken: the first line I say. {{MAX_WORDS}} words or fewer, which keeps it under {{MAX_SECONDS}} seconds at my
  {{WPM}} words per minute. Fill the blank naturally and fix the grammar so the line reads as one sentence I would
  say out loud; the template's shape must still be recognisable.
- on_screen: the line on screen at frame 1. 6 words or fewer, blunter than the spoken line, no punctuation it does
  not need.
- marker: every hook contains a concrete marker, quoted exactly from the spoken line: a named tool ("Claude Code",
  "frontend-design", "/plugin install"), a number ("5", "1,134,112", "two") or a time ("30 seconds", "overnight").
  marker_kind says which: tool, number or time. A marker must be true per facts.md: no invented number or name.
- Only facts from the research. Plain spoken English, contractions welcome, no greeting, no "in this video", no
  hashtags, no emoji. Never an em dash: write a comma instead.
- Every spoken line differs from the others in wording and in angle. One hook per template_id, the template_id
  copied exactly from the list.

## Your answer

Only this JSON object: {"hooks": [{"template_id": "<as listed>", "family": "<the template's family>", "spoken":
"...", "on_screen": "...", "marker": "...", "marker_kind": "tool" | "number" | "time"}], "notes": "<one line on
what you optimised for, or empty>", "suggested_shapes": ["<optional, 0 to 3: a new hook shape you wanted for this
idea and no template offered, written as a template line with __ for the blank; it goes to the owner's suggestions
file, not into this reel>"]}
