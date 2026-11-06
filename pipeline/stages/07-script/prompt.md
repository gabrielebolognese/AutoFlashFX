# Role: script
# Stage: 07-script
# Task: write

Write draft {{DRAFT_LABEL}} of the reel's script in the **{{TONE}}** tone ({{TONE_GUIDE}}). You get the brief, the
facts, the winning hook, how the creator sounds and the style's beat map. Answer with only the JSON object described
at the end. A cut pass removes about 20 percent of the words after you, scripted checks then verify the length, the
timing, the structure, the human feel, the placeholders and every claim against facts.md, and a judge compares your
draft with a second one written in another tone. The judge's first question is whether a stranger gets the point.

{{EXTRA}}
## The idea

{{IDEA}}

## Hook 1 (the judge's winner: the first beat says exactly this line)

- spoken: {{HOOK_SPOKEN}}
- on screen: {{HOOK_ON_SCREEN}}
- family: {{HOOK_FAMILY}}

Hook 2, for the alternate clip (write only its spoken track, in hook2): {{HOOK2_SPOKEN}} (on screen: {{HOOK2_ON_SCREEN}})

## The brief (05-hooks/brief.md)

{{BRIEF}}

## The facts (01-research/facts.md: the only source of every factual statement; cite claims by number)

{{FACTS}}

## How the creator sounds (library/profile/voice.md; a [FILL IN] means unknown: never invent it)

{{VOICE}}

Verbatim excerpts of the creator's real speech (match this register):
{{EXCERPTS}}

## Pronunciations (library/profile/pronunciations.txt: apply them in the spoken track)

{{PRONUNCIATIONS}}

## The style's beat map (styles/paper-cards/style.md: what each beat can show on screen)

{{BEAT_MAP}}

## The solution (02-expansion/solution.json; the rules of BUILD_SPEC.md S7)

{{SOLUTION_RULES}}

{{NOTE}}
## Above everything: the viewer understands it on one listen

The viewer is scrolling, has never heard of the tool or its terms, hears every line once at full speed and cannot
pause. If they cannot say the point back after one listen, the reel failed, however many facts it holds.
- Before writing, put the point in one plain sentence a 12-year-old would get (for example: "Claude Code makes every
  site look the same; this free skill fixes it; here is how to turn it on"). Every beat serves that sentence. A fact
  that does not serve it stays out, even a good one.
- Tell it as one thread: the problem, why it hits the viewer, the fix, what changes, how to get it. Each beat follows
  from the one before and the listener hears the link (so, because, but, that's why, here's the fix, then). A body
  beat may carry on the previous beat's idea (the why after the what): one thread, not one new fact per beat.
- Full sentences with a subject and a verb. No telegraph style and no strings of fragments: "All caps labels. Fake
  one, two, three." is a list of notes, not speech. One short punchline is fine where it lands a point.
- Plain words. A term the viewer would have to look up (distributional convergence, a design token, a hex code read
  out) is either explained in the same beat in everyday words or left out. Insider words count too: if the viewer
  would not say it to a friend (tells, non-steps, a scope, the brief, defaults, a plugin marketplace), say what it
  means instead. A name only when the viewer needs it.
- Examples: at most one beat lists them, with the one or two the viewer recognizes on sight. Three beats of
  examples in a row lose the thread.
- Use the 2 to 4 facts the point needs, explained, rather than squeezing them all in. A fact left out costs
  nothing; a line nobody understands costs the reel.

## Structure (in this order; one idea per beat, all of them one thread)

1. **hook** (beat 1, type hook): display is hook 1's spoken line, word for word; card is its on-screen line. Write
   only the spoken track yourself (numbers in words, pronunciations applied).
2. **stake** (type stake, right after the hook, seconds 2 to 7 of the reel, at most {{STAKE_MAX_WORDS}} words): the
   viewer's pain with the specific identity, so the right people stay and forward it. Identity: {{IDENTITY}}.
   Problem, in the viewer's words: {{PROBLEM}}
3. **body**: 4 to 7 beats, each with one idea and a type among number, tool, step, comparison, proof, mechanism,
   before-after, pain-payoff. Follow the brief's beat sheet unless the facts push you elsewhere.
4. **payoff** (type payoff): deliver what the hook promised.
5. **ask** (type ask, the last beat): one ask only, the comment keyword **{{KEYWORD}}** ({{DELIVERABLE}}), in a line
   that repeats one word of the hook so the replay loops. No follow, no like, no share, no save, no link in bio, no DM
   request, no second keyword, anywhere in the script.

## Two text tracks per beat

- **display**: what the captions and cards show: digits, names, exact commands and values as the source writes them
  (1,134,112; #D97757; /plugin install frontend-design@claude-plugins-official).
- **spoken**: the same sentence for the voice: every number written out in words, hex codes and commands said the
  way the brief says (or named instead of spelled), the pronunciations above applied, no symbols, no abbreviations.
- **card**: the big text on screen for the beat, 1 to 6 words (a value, a command, a label). For the hook it is the
  on-screen line above.
- **emphasis**: 1 to 3 words copied from the display line that get the accent box.
- **importance**: how much the line matters, one of hook (the first beat), key-claim (the claim the reel stands on),
  number (the beat that carries the number), payoff (the delivery of the hook's promise), pre-ask (the line right
  before the ask) or normal (everything else; most beats). It picks how the captions show the line: important lines
  become big kinetic typography, normal talk runs word by word. The pipeline fixes the structural ones itself (hook,
  number, payoff, the line before the ask), so mark a key-claim only where the line truly is the claim.
- **facts**: the facts.md claim numbers the beat rests on, as "facts.md#n" (empty for the stake and the ask).

## Length and timing

- The creator speaks at {{WPM}} words per minute. The final reel runs {{LENGTH_LO}} to {{LENGTH_HI}} seconds, which is
  {{FINAL_LO}} to {{FINAL_HI}} words after the cut pass.
- So write **{{WRITE_LO}} to {{WRITE_HI}} words** across the display track now: the cut pass trims it.
- No beat over {{BEAT_MAX_WORDS}} words on either track (4 seconds): a number written out or a command spelled out
  costs its spoken words, so keep such beats short. The hook stays under 3 seconds (it already does).
- Never 3 beats in a row without something concrete: a number, a name or an exact value the viewer understands.

## How to write it

- Plain spoken English, one thought per sentence, as the excerpts sound. Contractions (don't, it's, you're), talk to
  "you", say "I" where the creator would.
- Rhythm: the way people talk. Mostly full sentences of 6 to 12 words, now and then a short one of 2 to 4 words for
  punch. Clarity wins over rhythm every time: never break a sentence into fragments to vary the length.
- Concrete beats vague: a real example the viewer can picture, a number that matters, the tool's name. Never add a
  name or a number only to sound concrete, and never one the viewer cannot place.
- Every factual statement comes from a verified claim in facts.md, in the claim's own strength: no guarantee where
  the source says guidance, no invented number, client, result, hours saved or personal story. The viewer's pain,
  the creator's opinion and the ask are not claims and need no source.
- No stock words (leverage, unlock, elevate, seamless, robust, game-changer, delve, journey, landscape, ecosystem), no
  "in this video", no greeting, no hashtags, no emoji, no "stop scrolling", no list of exactly three joined by "and".
- Never an em dash: write a comma, a colon or a period. Never a double-brace placeholder or a bracketed blank.
- The keyword {{KEYWORD}} appears once, in the ask.

## Your answer

Only this JSON object:
{"tone": "{{TONE}}", "beats": [{"id": "b1", "type": "hook", "display": "...", "spoken": "...", "emphasis": ["..."],
"importance": "hook", "card": "...", "facts": []}, {"id": "b2", "type": "stake", ...}, ..., {"id": "bN", "type": "ask", ...}],
"ask": {"keyword": "{{KEYWORD}}", "line": "<the ask beat's display line>"}, "hook2": {"spoken": "<hook 2's spoken
track>"}, "notes": "<one line on the choices you made, or empty>"}
