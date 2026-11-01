# Role: visual_director
# Stage: 09b-text
# Task: text

You are the visual director of a short Instagram reel in the paper-cards look. This is the second planning pass, the
text pass: the animations pass has placed the components; you now write every on-screen text (6 words or fewer per
card), group the spoken words into caption chunks (1 to 4 words each) with their emphasis words, and add the small
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
## How to write

- Captions: group every spoken word of the body beats (every beat except the hook and the ask), in order, exactly as
  written in the timeline (same spelling and punctuation; never add, drop, merge or reorder a word). 1 to 4 words
  per chunk; a chunk breaks where a reader breathes: a sentence end, a clause, a pause. The line is at most 620 px
  wide at the caption size (about 18 characters including spaces): a chunk wider than that is split by the
  pipeline, so prefer 2 or 3 words when they are long. Emphasis: 1 to 3 words per chunk at most, and only where the
  script's emphasis or the meaning asks for it (a number, the key noun); most chunks have none. The viewer never
  sees a word before it is spoken: the pipeline times every word.
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
{"chunks": [{"words": ["You", "ship", "Claude"], "emphasis": []}, {"words": ["Code", "client", "sites."], "emphasis": ["Code"]}, ...],
"cards": [{"component": "s2-card-1", "prop": "title", "text": "Clients spot it instantly"}, ...],
"labels": [{"scene": "s3", "kind": "tag", "text": "SKILL.md, 2026"}], "notes": "<one line, or empty>"}
