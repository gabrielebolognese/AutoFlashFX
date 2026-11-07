# Role: script
# Stage: 07-script
# Task: write

Write draft {{DRAFT_LABEL}} of the reel's script in the **{{TONE}}** tone ({{TONE_GUIDE}}). You get the brief, the
facts, the winning hook, how the creator sounds and the style's beat map. Answer with only the JSON object described
at the end. A cut pass removes about 20 percent of the words after you, scripted checks then verify the length, the
timing, the structure, the human feel, the placeholders and every claim against facts.md, and a judge compares your
draft with a second one written in another tone.

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
## Structure (in this order; one idea per beat)

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
- Never 3 beats in a row without something concrete: a number, a name or an exact value.

## How to write it

- Plain spoken English, one thought per sentence, as the excerpts sound. Contractions (don't, it's, you're), talk to
  "you", say "I" where the creator would.
- Rhythm, and this is checked by a sentence-length statistic (the variation across sentences must be high): beats
  come in two shapes and alternate, A B A B. Shape A is one sentence of 12 or 13 words ("With it on, Claude plans
  4 to 6 colours, reviews them, and only then codes."). Shape B is two or three sentences of 3 or 4 words each
  ("Rounded cards again. Same grey shadow. Every single time."). The hook is the only sentence of 5 to 11 words
  in the script: that middle length is the machine rhythm and fails the check, so split such a sentence in two
  or stretch it to 12.
- Something concrete in every beat where the facts allow it: a number, an exact value, or a capitalized name that
  is not the beat's first word (the checker counts digits and mid-sentence capitalized names; a bare command line
  counts as abstract, so say "Claude" or a number near it).
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
