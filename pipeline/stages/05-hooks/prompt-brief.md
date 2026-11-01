# Role: research
# Stage: 05-hooks

Last task of this session: write the brief for the script writer. The script model starts a fresh session with
only this brief, facts.md, the winning hook, my voice profile and the style rules, so the brief must hold
everything you know that the script needs, and nothing the script could not verify in facts.md. Answer with only
the JSON object described at the end.

## The idea

{{IDEA}}

## The expansion (the gate passed it)

{{EXPANSION}}

## The hooks you just wrote (the judge picks hook 1 and hook 2 among them; the brief must work with any of them)

{{HOOKS}}

## Existing comment keywords (library/profile/deliverables.txt)

{{DELIVERABLES}}

{{NOTE}}
## What the brief contains (markdown, these sections in this order, each with its heading)

1. **The one idea**: two or three sentences: what the reel says, the one specific true thing it stands on (with its
   claim number), and what it must not claim.
2. **The viewer**: who exactly (the share identity), their problem in their own words (first person), and the moment
   they feel it.
3. **The promise and the payoff**: what the hook promises and the exact beat that pays it.
4. **Facts to use**: 8 to 15 bullets. Each bullet is one fact with its claim number (facts.md#n), the exact wording
   to keep (numbers, names, commands, colors as the source gives them) and what it is good for (a number beat, a
   proof beat, a mechanism beat, a comparison, a step). Only verified claims.
5. **Facts to avoid and pitfalls**: what is unverified, outdated or easy to get wrong (from the research's pitfalls),
   and the claims the reel must not make.
6. **Suggested beat sheet**: 6 to 10 beats for a {{LENGTH_RULE}} reel. Each beat has a type (number, tool, step,
   comparison, proof, mechanism, before-after or pain-payoff), the fact it uses and a one-line draft of what is
   said. Hook first (leave the exact words to the judge's winner), then the stake (the viewer's pain with the
   identity), the body, the payoff, then the single ask.
7. **The ask**: the comment keyword {{KEYWORD}} and its deliverable ({{DELIVERABLE}}). Write two candidate closing
   lines that repeat a word from the hooks so the replay loops. No second ask anywhere.
8. **On-screen material**: the screenshots that exist (each asset file and what it shows) and the numbers that
   deserve a card.
9. **Words and tone**: words to use and words to avoid for this topic, how the tool names are spelled and said, and
   two or three tones among warning, insider, contrarian, calm expert and confession that fit this angle, one line
   each on why.

Length: between {{MIN_WORDS}} and {{MAX_WORDS}} words (about {{MIN_TOKENS}} to {{MAX_TOKENS}} tokens). Dense, no
filler, no repetition of the expansion word for word. Plain English. Never an em dash.

## Your answer

Only this JSON object: {"brief_markdown": "<the brief as markdown, starting with the first section heading>",
"video_type": "default" | "list", "suggested_tones": ["...", "..."]}
