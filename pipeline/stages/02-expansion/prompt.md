# Role: research
# Stage: 02-expansion

You researched this idea (facts.md below is your own work from the research step). Now write the expansion: the
five parts the gate will score. Answer with only the JSON object described at the end.

## The idea

{{IDEA}}

## The account (who the reel is for)

{{ACCOUNT}}

## facts.md (your research; cite claims by their number)

{{FACTS}}

## Existing comment keywords (library/profile/deliverables.txt)

{{DELIVERABLES}}

{{NOTE}}
## The five parts (BUILD_SPEC.md S2)

1. problem: the viewer's problem as ONE first-person sentence in the viewer's own voice ("I ...", "my ..."),
   specific and felt: a real pain, not a topic. Then solution: what the idea gives them, one or two sentences,
   concrete, naming the tool or the step.
2. share driver: share_identity names exactly who should forward this ("if you edit reels for clients", "if you run
   a Shopify store with AI-written product pages") and takeaway is the one thing worth forwarding, useful even
   without the video.
3. comment trigger: keyword is one word in capitals (3 to 20 letters, no spaces, no hashtag) that the viewer
   comments to receive the deliverable. Prefer an existing keyword from the list above when its deliverable fits;
   otherwise invent one and describe a NEW deliverable concretely (what file, list, template or link they receive
   and what it contains), with deliverable_status "new". A keyword that is not in the list counts as NEW whatever
   you write.
4. one_true_thing: the one specific true thing the reel stands on: a concrete number, result or demo taken from a
   verified claim (name the tool, the number, the time).
5. evidence: 2 to 6 pointers to verified claims of facts.md, as {fact: the claim number, note: what that claim
   backs, a few words}. Point only to claims marked verified. Every fact the expansion states must be one of them.

## Rules

- Keep the idea's core topic: the expansion sharpens the idea, it does not replace it.
- Length: the composed expansion.md must land between {{MIN}} and {{MAX}} characters in total, and the layout
  itself adds about 250 characters of labels and the title, so your own text must stay under 1100 characters in
  total. Aim for about 800: problem up to 140 characters, solution up to 220, share_identity up to 80, takeaway up
  to 180, deliverable up to 150, one_true_thing up to 160, evidence notes up to 60 each. Count before you answer:
  a long answer is sent back to you to cut.
- Only facts from facts.md, only verified ones, in the claim's own words: when a statement rests on a claim, keep
  that claim's wording (the install steps exactly as the docs give them, a font or a color named as the claim
  names it) and add no detail, step count or adjective the claim does not state. No invented numbers, no
  superlatives you cannot source. One statement the gate cannot find in facts.md fails F and costs an angle round.
- Plain spoken English, short sentences. Never use an em dash: commas, colons or periods instead.

## Your answer

Only this JSON object: {problem, solution, share_identity, takeaway, keyword, deliverable, deliverable_status
("existing" | "new"), one_true_thing, evidence: [{fact, note}]}
