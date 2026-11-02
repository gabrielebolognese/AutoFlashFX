# Role: script
# Stage: 14-export

Write the Instagram caption of a finished reel. The first line is fixed: hook 1, the line the reel opens with (the
feed shows about {{FIRST_LINE_MAX}} characters before "... more", so the hook stands there whole). You write what
comes after it: the body and the one ask. Answer with only the JSON object described at the end.

## The reel

- The idea: {{IDEA}}
- Hook 1, the caption's first line (fixed, do not rewrite it): {{HOOK1}}
- The viewer's problem: {{PROBLEM}}
- Who should forward it: {{IDENTITY}}
- The solution of this reel: {{SOLUTION_LINE}}
- The comment keyword: {{KEYWORD}}. What they get: {{DELIVERABLE}}

## The script (the display track, beat by beat; every fact the caption may state is here)

{{BEATS}}

## The brief's one idea

{{ONE_IDEA}}

## How the creator sounds (library/profile/voice.md)

{{VOICE}}

{{NOTE}}
## Rules

- body: 2 to 5 short lines, each its own paragraph, {{BODY_MIN}} to {{BODY_MAX}} characters in all. Plain spoken
  English in the creator's voice: what the reel shows and why it matters to the person who should forward it. No
  greeting, no "in this reel", no emoji walls (one emoji at most, or none), no hashtags inside the body, no link, no
  question to the audience, no stock words (leverage, unlock, elevate, seamless, game-changer, delve, journey).
- ask_line: exactly one ask, the comment keyword in capitals, as "Comment {{KEYWORD}} ..." plus what they get, in
  one sentence or two. No follow, like, share, save, subscribe, link in bio, "DM me" or second keyword anywhere.
- hashtags: {{HASHTAG_MIN}} to {{HASHTAG_MAX}}, one word each with #, specific to the topic (the tool, the practice,
  the audience); none generic (#viral, #fyp, #reels, #explore, #trending), none repeating the keyword.
- search_terms: 2 to 4 words or short phrases people type when they look for this, worked naturally into the body.
- {{SOLUTION_RULES}}
- Every statement of fact comes from the script above (it was checked against the research): add no number,
  result, client or claim the script does not make, and promise nothing the reel does not show.
- Never an em dash: commas, colons or periods.

## Your answer

Only this JSON object: {"body": "<the lines, separated by blank lines>", "ask_line": "<Comment {{KEYWORD}} ...>",
"hashtags": ["#...", "#...", "#..."], "search_terms": ["...", "..."], "notes": "<one line on your choices, or empty>"}
