# Role: script
# Stage: 14-export

Write the YouTube Shorts text of a finished video for the channel {{BRAND_NAME}}: its title, its description, its pinned
comment and its hashtags. The video itself is done; you only write the words around it. Answer with only the JSON object
described at the end.

## The video

- What it is about: {{SUMMARY}}
- Hook 1, the line it opens with: {{HOOK1}}

{{SERIAL_BLOCK}}

## What the video says (the script, line by line)

{{SCRIPT}}

## The beats (a short label, then the narration)

{{BEATS}}

## Facts the video states (each one was checked)

{{FACTS}}

## The channel's earlier descriptions ({{EARLIER_COUNT}}, newest last)

Your description must be new. Its first line must match none of these first lines, and it may share at most
{{OVERLAP_PERCENT}} percent of its three-word runs with any one of these descriptions (the hashtag line is left out of
the count). Do not reuse their sentences, their list wording or their closing question.

First lines so far:

{{EARLIER_OPENERS}}

{{EARLIER_DESCRIPTIONS}}

{{NOTE}}
## Rules (every one is checked by code, and a failure sends you back to rewrite)

Every limit counts every character, spaces and line breaks included. No em dash anywhere (use commas, colons, periods or
parentheses). No stock words (leverage, unlock, elevate, seamless, game-changer, delve, journey, tapestry). No links, no
promotion, no emoji walls. Write plain spoken English for a viewer who has not seen the video. State nothing the script and
the facts above do not say.

- title: {{TITLE_RULE}}
- description: at most {{DESCRIPTION_MAX}} characters in total, counting every character, line break and hashtag. Write it
  for this video only.
  - The first line is a one-sentence summary of what this video is about. It is never the title repeated, and never the title's
    hook phrase repeated. One sentence only.
  - Short lines. No paragraph (consecutive lines that are not list items) longer than {{PARAGRAPH_MAX}} characters.
  - At least one list of 3 to 6 items, one per line, each line starting with "- " (a hyphen and a space), for example the
    story, the part, the universe and the place. Use no other bullet sign.
  - {{PART_RULE}}
  - It ends with {{HASHTAG_RULE}}.
  - No links, no promotion.
- pinned_comment: {{PINNED_RULE}}
- hashtags: the same hashtags as the description's last line, in the same order.

## Shape of a description (a serial part)

```
You have 212 dollars, a borrowed car and an idea everyone at the diner laughed at.

This part:
- Story: The Website Kid
- Part: 1
- Universe: Entrepreneur
- Where: Columbus, Ohio, March 1994

Would you have named a price on the spot?

#shorts #businessstory #1990s #storytime
```

Notice what makes it work: one plain sentence first, short lines, a small list of facts about this video, one closing
question, and the hashtags alone on the last line. Write your own words and your own list for this video; do not copy the
example's sentences.

## Your answer

Only this JSON object: {"title": "<one line>", "description": "<the lines, with \n between them>", "pinned_comment": "<one or two
lines, with \n between them>", "hashtags": ["#...", "#..."]}
