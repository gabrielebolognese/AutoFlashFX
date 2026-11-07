# Role: visual_director
# Stage: 09b-text
# Task: text

You are the visual director of a short Instagram reel in the paper-cards look. This is the second planning pass, the
text pass: the animations pass has placed the components; you now write every on-screen text (6 words or fewer per
card), cover the spoken words with caption chunks (word runs of 1 to 4 words with their emphasis words, or groups of 2 to 6), and add the small
labels. Answer with only the JSON object described at the end.

## The idea

{{IDEA}}

## The script and the voice (07-script/script.json, 08-voiceover/words.json)

{{TIMELINE}}

## The scenes of the animations pass (09a-animations/plan.json), with their first-draft texts

{{SCENES}}

## The baseline caption chunks

{{CHUNKS}}

## The look's caption and text rules (styles/paper-cards/style.md, Captions; tweaks.md)

{{STYLE}}

{{TWEAKS}}

{{NOTE}}
{{REVIEW}}
## How to write

- Captions: cover every spoken word of the body beats (every beat except the hook and the ask), in order, exactly as
  written in the timeline (same spelling and punctuation; never add, drop, merge or reorder a word). Two modes (the
  caption modes list above gives each scene's importance, its text and graphics, and the pipeline's own choice):
  **word mode** shows one word at a time on its spoken time (the emphasis words larger, in the serif italic on the
  accent box); write its chunks as runs of 1 to 4 words where a reader breathes (a sentence end, a clause, a
  pause). **Group mode** shows 2 to 6 words together as kinetic typography filling the hero zone: say `"mode":
  "group"` on that chunk and name its `"anchor"` word (the most important one, drawn biggest; the pipeline lays
  every word out, never position words yourself). Use a group where the voice says something that matters (a key
  claim, a number, the payoff, the line before the ask) and where the scene has no graphic or text worth showing;
  use word mode in normal talk and always while any card, chip or code text is on screen (captions never compete
  with other text). Leave `mode` out where the pipeline's choice is fine. Emphasis (word mode): 1 to 3 words per
  chunk at most, only where the script's emphasis or the meaning asks for it; most chunks have none. The viewer
  never sees a word before it is spoken: the pipeline times every word.
- Text on screen is the last resort (graphics first): at most 100 characters of card, label, chip and code text
  on screen at any moment, and no graphic text below the caption size (67 px), so a card that would need small text
  needs fewer words. Cut a card text wherever the picture or a number already says it.
- Cards: for each instance in the scenes list, keep or rewrite its text props. A title, a chip text, a kicker or a
  keyword has 6 words or fewer; quote the script's display line or its card text, keep digits, names, commands and
  values exactly as the script writes them. Body text (body, message, line1, line2) stays under 14 words. Write only
  the ones you change, as {"component": "<instance id>", "prop": "<prop>", "text": "..."}; lines_json and items_json
  take the lines separated by |.
- Labels: a tag only when it tells the viewer something the card does not (the source, the date, "real"); the
  honesty labels (real, illustrative) come from the components themselves.
- Sentence case, no ALL CAPS captions (the kicker is the one upper-case line), no emoji, no hashtags, no em dash.

## Your answer

Only this JSON object:
{"chunks": [{"words": ["You", "ship", "Claude"], "emphasis": []}, {"words": ["Code", "client", "sites."], "emphasis": ["Code"]}, {"words": ["four", "thousand", "dollars", "a", "month"], "mode": "group", "anchor": "thousand"}, ...],
"cards": [{"component": "s2-card-1", "prop": "title", "text": "Clients spot it instantly"}, ...],
"labels": [{"scene": "s3", "kind": "tag", "text": "SKILL.md, 2026"}], "notes": "<one line, or empty>"}
