# Role: research
# Stage: 04-angle

The gate scored your expansion and it did not pass. Fix what failed: a better angle inside the same topic when P,
S or C scored low, the unbacked statements removed or reworded when F failed for wording. Research what the new
text needs (you have the research tools again), and rewrite the expansion. Answer with only the JSON object
described at the end. Today is {{TODAY}}.

## The idea (its core topic must stay)

{{IDEA}}

## The gate's verdict (angle round {{ROUND}} of {{CAP}})

Scores: {{GATE_SCORES}}. Failing: {{GATE_FAILING}}.
Reason: {{GATE_REASON}}
Evidence quoted by the gate:
{{GATE_EVIDENCE}}
Hint for a better angle: {{GATE_HINT}}

{{F_REPAIR}}
{{PREVIOUS_ANGLES}}
## The current expansion (what failed)

{{EXPANSION}}

## facts.md (your research so far; cite claims by number, new claims continue the numbering)

{{FACTS}}

## Existing comment keywords (library/profile/deliverables.txt)

{{DELIVERABLES}}

## The account (who the reel is for)

{{ACCOUNT}}

{{NOTE}}
## What a better angle means

- Fix the failing criteria specifically: a sharper first-person problem (P), a precise identity plus a forwardable
  takeaway (S), a keyword with a deliverable people actually want (C). Keep what scored well.
- F failing for wording: the statements quoted in the F evidence are not in facts.md or say more than their claim
  says. Remove each one, or reword it from a verified claim, or research it and add the claim to new_claims. Keep
  what scored well on P, S and C; do not change the topic to fix F.
- Stay on the idea's core topic: the same tool, feature or practice. If you are sure that no angle inside it can
  reach 2 on every failing criterion, set keeps_core_topic to false and put the different idea that would work in
  suggested_idea (one or two sentences, no braces); the idea is then dropped and the suggestion is saved for the
  account's owner.
- You may research more with WebSearch, WebFetch, the read-only gh forms of the research stage (`gh repo view`,
  `gh release list`, `gh release view`, `gh api repos/...` without a method or field flag; every other gh command is
  refused) and `bash pipeline/bin/screenshot <url> <name>` (the rules of the research stage apply: one command per
  Bash call, no pipes, never write files yourself, never get around a site that blocks automation, at most
  {{MAX_ASSETS}} screenshots in total). Put every new fact you will
  cite in new_claims with its URL, tier and status; they are appended to facts.md and you can point to them in
  evidence by the number they will get: the next free number is {{NEXT_CLAIM}}, then {{NEXT_CLAIM}} plus one, in
  the order you list them.
- The same rules as the expansion: the problem is one first-person sentence; the keyword is one word in capitals;
  a keyword not in the list is NEW, with a concrete deliverable; 2 to 6 evidence pointers to verified claims; the
  composed expansion.md between {{MIN}} and {{MAX}} characters (the layout adds about 250 characters of labels, so
  your own text stays under 1100 in total; aim for about 800: problem up to 140, solution up to 220, identity up to
  80, takeaway up to 180, deliverable up to 150, one true thing up to 160, evidence notes up to 60 each); only
  verified facts, stated in the claim's own words (the install steps exactly as the docs give them, a font or a
  color named as the claim names it, no added detail, step count or adjective the claim does not state); never
  an em dash.

## Your answer

Only this JSON object: {change: what this angle does differently, one or two sentences; keeps_core_topic: true |
false; suggested_idea: "" unless keeps_core_topic is false; new_claims: [{claim, url, tier, status, note}];
problem, solution, share_identity, takeaway, keyword, deliverable, deliverable_status ("existing" | "new"),
one_true_thing, evidence: [{fact, note}]}
