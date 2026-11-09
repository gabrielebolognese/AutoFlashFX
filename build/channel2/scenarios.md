# Scenarios: channel master document

Version 1, 2026-11-08. Working id: `scenarios` (replaced once the channel name is chosen).

This document describes the channel, how the pipeline makes its videos, and what goes in every profile file.
Items marked "(my choice)" were decided by Claude on Gabriele's request and can be changed.
Open items are listed in section 9.

---

## 1. The channel in one paragraph

A YouTube Shorts channel of narrated, 2D animated, second-person stories that read like chapters torn out of a
novel. The viewer is "you", and "you" is always Gabry: same face, same voice, a different life in every story. Each
story runs 3 to 8 parts of 90 to 120 seconds, released on consecutive slots, and every part except the last ends on
a concrete cliffhanger. Stories live in two universes: Isolation (cut off from society, grounded survival with room
for the unexplained) and Entrepreneur (building a business from nothing, with real money, real people and real
consequences). Nothing carries over between stories: every story starts from Part 1 in a fresh world.

---

## 2. Fixed decisions

| Item | Decision |
| --- | --- |
| Platform | YouTube Shorts |
| Format family | generated (script, voice, code-drawn composition) |
| Language | English, American |
| Timezone | Europe/Rome |
| Part length | 90 to 120 s |
| Parts per story | 3 to 8, set at the story gate, changeable at part gates |
| Cadence | 1 part per day by default; 2 per day only as morning + evening; never more |
| Release order | one story at a time, its parts on consecutive slots |
| Protagonist | Gabry in every story: fixed look; personality, age, era, place and approach vary per story |
| Continuity | inside a story only; nothing carries over between stories |
| Voices | two Kokoro American voices: the narrator and Gabry |
| Hooks | written fresh for every idea; no template bank |
| On-screen apps | generic fictional UIs only (an average map, not Google Maps) |
| Crime | allowed as drama and consequence, never as a method or a get-rich message |
| Title limit | 100 characters |
| Visuals | drawn as code (HyperFrames: HTML, SVG, GSAP); never AI-generated images or video |

---

## 3. Gabry

"You" is Gabry. The narrator talks to the viewer as "you". When Gabry speaks out loud, he speaks with his own voice.

Fixed in every story:
- name: Gabry
- face, proportions, fixed colors, line style (defined in the style round)
- voice: the Gabry Kokoro voice, at every age
- point of view: the story is always his

Variable per story (set at the story gate, recorded in the story plan):
- age: a kid, a teen, 20s, 80 years old
- personality: calm, impatient, proud, reckless, ruthless
- approach: honest, desperate, "the most evil way possible"
- era and place: 1994 Ohio, northern Norway today, a bunker in 2031
- job, skills, starting resources, family and side characters

Rules:
- The narration never names Gabry. Other characters may call him Gabry in dialogue.
- An age or costume change keeps the face shape, eye style and fixed colors (the style round decides how aging is drawn).
- His personality stays consistent for the whole story. It can change through events, never at random.
- Flaws matter: in every story Gabry gets at least one decision wrong because of who he is in that story.

---

## 4. The two universes

### Isolation
Gabry is cut off from normal society: a cabin, a bunker, a station, an island, an empty town, a world where
something changed.
- Emotional engine: fear of the unknown, physical danger, scarce resources, paranoia.
- The viewer thinks: what is happening, and how do you get out alive?
- Supernatural events, monsters and anomalies are allowed, with consistent rules. Human behavior stays realistic.
- The environment (weather, distance, darkness, supplies) is an active obstacle.

### Entrepreneur
Gabry builds a business and a life from almost nothing, in whatever era and place the idea sets.
- Emotional engine: fear of failure, money pressure, ambition, difficult people.
- The viewer thinks: what would I do here, and can you actually pull this off?
- Money is tracked to the cent. Revenue is never profit. Every decision has a trade-off.
- Customers, suppliers, family and competitors behave like real people.
- It teaches through events, never through lectures.

### Crime and consequences (both universes)
- Gabry can cut corners, break rules, get scammed, be investigated or arrested.
- Consequences are realistic: police, fines, lost customers, family fallout, lost time.
- A story may teach something real: how a scam gets spotted, why a shortcut collapses.
- Methods stay vague: no step a viewer could copy (fraud mechanics, hacking steps, making drugs or weapons).
- No story frames crime or a get-rich shortcut as a win without cost.

---

## 5. Story structure

Per story:
- 3 to 8 parts. The count follows the plot: never padded, never crushed.
- The ending is planned before Part 1 is written. Details planted early pay off later.
- The final part resolves the central conflict. It may leave one small optional opening.

Per part: 90 to 120 s, about 225 to 300 words at 2.5 words per second (recalibrated once the voice pace is measured).

| Time | Function |
| --- | --- |
| 0 to 10 s | hook (from Part 2 on: the recap fused into the hook) |
| 10 to 30 s | situation and context |
| 30 to 60 s | main scene, played in real time |
| 60 to 85 s | complication or new information |
| 85 to 110 s | escalation |
| last 5 to 10 s | cliffhanger (resolution in the final part) |

- Recap: from Part 2 on, the part opens with a 3 to 7 s recap that already contains the new problem.
  Example: "Yesterday, you got your first client. Today, he sent you 14 messages. None of them are good."
- Cliffhanger types: every non-final part ends on exactly one of revelation, unexpected arrival, immediate
  consequence, impossible discovery, irreversible decision. It is a concrete event, and the next part follows from it.
- Pacing: new information or a visual change every 3 to 5 seconds.

---

## 6. How the pipeline makes a story (gated workflow)

Unlike a plain idea queue, this channel's format stops at gates and waits for Gabriele.
- Every gate holds with no timeout.
- At any gate he can reply "you decide": the pipeline takes the option it marked as recommended and continues.
- At any gate he can discuss: the pipeline answers, revises the options, and keeps holding until he decides.

Story state lives in one folder per story (proposal for BUILD_SPEC): `channels/<id>/stories/<story-slug>/` with
- `research.md`: facts and sources
- `plan.md`: the chosen storyboard, Gabry's variables, the part count, the sealed ending
- `bible.md`: timeline, locations and distances, characters, inventory or money ledger, threat rules, open threads,
  pronunciations of new names
- `gates/`: every proposal and every decision, in order
- `parts/NN/`: script, audio, composition, review notes

When a story ends its folder is closed. The next story reads nothing from it.

### Stage 0: seed
- Input: a seed from Gabriele (free text, for example "you want to start a business in the 1990s in America"),
  a block from `ideas.txt`, or the request "propose ideas".
- On "propose ideas": the pipeline proposes 5 seeds, each with its own hook line, universe and Gabry variables.
  Gate G0: he picks one or writes his own.

### Stage 1: research
- Web research on everything the story must get right: era facts (prices, technology, laws, slang), places and
  distances, business economics, survival and physical facts.
- Output: `research.md` with sources. Facts in scripts come from here.

### Stage 2: story gate (G1)
The pipeline proposes 3 storyboards. Each one has:
- title, universe, and the exact hook line (the first spoken sentence of Part 1)
- Gabry's variables for this story (age, personality, approach, situation, starting resources)
- the part count, with one line on why it needs that many
- one line per part: what happens and which cliffhanger type closes it
- the ending
- the research facts that make it credible

One is marked recommended. Gabriele picks one, mixes them or discusses. The decision writes `plan.md` and the first
`bible.md`.

### Stage 3: part gate (G2, once per part)
Before writing Part N, the pipeline proposes 2 or 3 approaches. Each one has:
- the exact opening line (with the recap hook from Part 2 on)
- 3 to 6 scene beats
- the cliffhanger type and its exact last line (or the resolution, in the final part)
- how it moves the story toward the planned ending

One is marked recommended. Gabriele picks, edits or discusses. If his steering changes the ending or the part
count, the pipeline shows the updated outline of the remaining parts before writing.

### Stage 4: script
- Writes Part N in the speaker-tagged script format (section 7.3), inside the word window.
- Checks: continuity against `bible.md`, the part approval checklist (section 7.4), banned phrasings, word count.
- Fixes and rechecks automatically until it passes.

### Stage 5: production
- Two-voice voiceover, code-drawn composition, sound effects, automatic review loop, render at 1080x1920, 90 to 120 s.

### Stage 6: export
- The video, the post text (title, description, hashtags, pinned comment) and the editable editor project, per the
  engine's export convention.
- The post text file starts with the story title and the part number, so parts get uploaded in order.

### Stage 7: bible update, then hold
- Records what Part N changed: events, objects used, money in and out, injuries, who knows what, threads opened or
  closed.
- Opens gate G2 for Part N+1 and holds. To keep up with the cadence, the next G2 proposals may be prepared as soon as
  Part N's script passes, while it renders.
- After the final part the story closes and the next one starts at Stage 0.

Gabriele's time per story: one G1 decision, plus one G2 decision per part. At 1 part per day, about one decision a day.

---

## 7. Profile files

All paths are inside `channels/<id>/`.

| File | Status |
| --- | --- |
| `channel.json` | partial (name, handle, sources, style open) |
| `library/profile/account.md` | complete draft (7.2) |
| `library/profile/voice.md` | rules complete; voices and samples pending approval |
| `library/profile/storytelling.md` | complete draft (7.4) |
| `library/hooks.txt` | not used (hooks come with each idea) |
| `ideas.txt` | format set; seeds to pick |
| `library/profile/pronunciations.txt` | partial |
| `library/voice/engine.txt` | pending the voice audition |
| `library/character/gabry.md` | rules complete; visual identity pending |
| `styles/<style id>/style.md` | pending the style round |
| sound | pending |

### 7.1 channel.json (draft; key names follow BUILD_SPEC's schema)

```json
{
  "id": "scenarios",
  "name": "TBD",
  "platform": "youtube_shorts",
  "format": "TBD: the gated serialized story format (section 8)",
  "language": "en",
  "timezone": "Europe/Rome",
  "daily_quota": 1,
  "brand": { "display_name": "TBD", "handle": "TBD" },
  "export": {
    "title_max_chars": 100,
    "description_max_chars": 1000,
    "hashtag_count": 4,
    "required_hashtags": [],
    "pinned_comment": true
  },
  "sources": { "refs": "TBD", "sfx": "TBD" },
  "config": { "style": "TBD", "length_s": [90, 120], "voice_pace_wps": null }
}
```

`daily_quota` is 1. Set it to 2 only for a morning + evening schedule.

### 7.2 library/profile/account.md (complete draft)

````markdown
# Account

## What this channel is
Narrated, 2D animated, second-person stories for YouTube Shorts that read like chapters of a novel.
The viewer is "you", and "you" is always Gabry: one recognizable protagonist living a different life in every story.
Each story runs 3 to 8 parts of 90 to 120 seconds, released back to back.
Every part except the last ends on a concrete cliffhanger.
Two universes: Isolation and Entrepreneur. No story carries over into another.

## Audience (my choice; revisit after 30 days of data)
- Age 16 to 34, English speaking: mostly US, UK, Canada and Australia, plus English speakers worldwide.
- They already watch: narrated story Shorts, "what would you do" scenarios, horror and mystery narrations,
  survival content, rags-to-riches and business stories, survival and management sim games.
- Why they follow: an unfinished story (the next part is coming), a protagonist they recognize (Gabry),
  and writing that feels like a book instead of a summary.

## Pillars: the two universes

### Isolation
- Gabry is physically cut off from society: cabins, bunkers, stations, islands, empty towns, changed worlds.
- Engine: fear of the unknown, physical danger, scarce resources, paranoia.
- Supernatural events allowed, with consistent rules. Human behavior always realistic.
- Example premises: a weather station that prints a warning dated tomorrow; day 43 in a bunker when the radio
  says not to open the door; a rescue team that sees more people in your cabin than you do.

### Entrepreneur
- Gabry builds a business from almost nothing, in the era and place the idea sets.
- Engine: fear of failure, money pressure, ambition, difficult people.
- Money tracked to the cent, real trade-offs, real customers, nuanced family pressure.
- Example premises: starting a business in 1990s America with $212; asking a bank for a loan at 80;
  building a business the most evil way possible, and paying for it.

## Story variables (chosen per story, never carried over)
- universe
- era and place
- Gabry's age, personality and approach
- situation, starting resources, side characters
- part count (3 to 8)

## Topics in
- survival, isolation, mystery, the unexplained, grounded supernatural
- business building in any era: money, customers, suppliers, competitors, family, failure, small wins
- crime as drama and consequence: scams, shortcuts, police, investigations, fallout
- real facts woven into events: era details, business mechanics, survival and physical facts

## Topics out (hard limits)
- real brand logos and real app interfaces: every on-screen app is a generic fictional UI
- methods for crimes, or anything a viewer could copy step by step (fraud, hacking, drugs, weapons)
- crime or get-rich shortcuts framed as a win without cost; any "anyone can do this" message
- motivational speeches and tutorials
- real living people, named or shown (my choice)
- sexual content (my choice)
- suicide and self-harm (my choice)
- real tragedies, politics and religion as the subject of a story (my choice)
- gore: no blood, wounds or bodies on screen; death and violence happen off screen (my choice, pending confirmation)

## Tone
- Grounded, cinematic, novel-like: short sentences, real-time scenes, concrete details.
- Isolation: restraint and dread; quiet moments before the shock; the unexplained stays unexplained until it pays off.
- Entrepreneur: pressure and momentum; dry humor allowed; small wins land hard.
- Never: motivational, lecturing, sarcastic toward the viewer, or a summary-style "AI storyteller" voice.

## Goal (my choice; review at day 30 and day 90)
Success means viewers come back for the next part and subscribe to get it.
- Part 1 viewed rate (viewed vs swiped away, YouTube Studio): 70% or more.
- Average percentage viewed, per part: 50% or more.
- Continuation: Part 2 views at least 30% of Part 1 views; final part views at least 15% of Part 1 views.
- Subscribers: 1,000 within 90 days of the first upload.

## Content strategy
- Release: one story at a time, its parts on consecutive slots; the next story starts on the slot after the finale.
- Cadence: 1 part per day; 2 per day only as a morning and an evening slot; never more.
- Universe mix (my choice): alternate Isolation and Entrepreneur for the first 6 stories, then lean 2 to 1 toward
  the universe with the better Part 1 viewed rate and Part 2 to Part 1 ratio, never dropping the other.
- Story length mix (my choice): the first 2 stories run 3 parts each, for fast feedback; after that most stories run
  3 to 6 parts; 7 or 8 only when the plot earns it.
- Variety (my choice): two consecutive stories in the same universe differ in at least 2 variables
  (era, place, Gabry's age, approach).
- Part 1 is the subscribe engine: the strongest hook and a setup a cold viewer fully understands.
- From Part 2 on, the recap hook makes each part watchable for a viewer who lands on it first.
- Throughput: at 1 part per day and an average of 5 parts, about 6 stories per month.
````

### 7.3 library/profile/voice.md (rules complete; voices and samples pending approval)

Speakers:
- NARRATOR: American Kokoro voice (from the audition, 7.8). Narrates everything in second person, present tense.
  Reads every other character's dialogue too (my choice, pending: see section 9).
- GABRY: American Kokoro voice (from the audition), young male. Speaks only Gabry's own lines, in first person.
  Same voice at every age.

Point of view:
- The viewer is "you", and "you" is Gabry.
- Narration never says "Gabry", never uses "he" for the protagonist, never uses "I".
- Other characters may say "Gabry" in their dialogue.

Tense: present. Past tense only for backstory, one or two sentences at a time.

Energy and pace:
- The narrator is calm, low and controlled, like reading a thriller at night. Never excited, never hyped.
- Tension comes from the words and the pauses, not from the delivery.
- Gabry sounds natural and a little understated.

Sentence rules (checkable):
- average sentence length 12 words or fewer; no sentence over 22 words
- one sentence per script line; a new line is a beat
- at least one short beat (4 words or fewer) every 10 seconds: "Nothing." "Three knocks." "He hangs up."
- concrete nouns and numbers over adjectives: "$4.10 left" over "almost no money"

Dialogue rules:
- lines sound like real people: short, interrupted, unfinished, sometimes unanswered
- characters never explain their feelings; a pause or an action does that
- Gabry's spoken lines: 12 words or fewer each
- no shouting in capitals, no speeches

Banned phrasings:
- announced cliffhangers: "little did you know", "everything was about to change", "things were about to get worse",
  "you had no idea what was coming", "this was only the beginning", "tomorrow would be different"
- feeling labels: "you feel scared", "terrified", "you feel lonely", "a chill runs down your spine",
  "your heart pounds", "you can't believe your eyes"
- atmosphere words doing all the work: eerie, ominous, mysterious, strange (at most once per part, never as the only
  description)
- "suddenly": at most once per part
- motivational words: journey, hustle, grind, mindset, dream big, never give up
- summary phrasings for important events: "you decide to", "you manage to", "eventually you", "after a while"
  (allowed only for unimportant transitions)

Numbers: subtitles show digits ("$212", "9:16 PM"); the voice says them the way a person would
("two hundred twelve dollars", "nine sixteen p.m.").

Signature lines (my choice): none spoken. "End of Part N" appears on screen only, so the cliffhanger is always the
last thing the viewer hears.

Call to action (my choice): none spoken. The end card and the pinned comment point to the next part.

Script format (one sentence per line, speaker first; other characters' lines go inside NARRATOR lines, in quotes):

```
NARRATOR: Day 43 in the bunker.
NARRATOR: A man's voice, very calm: "Do not open the door."
GABRY: Mom?
```

Sample passages (for approval):

Sample A, Isolation:
```
NARRATOR: Day 43 in the bunker.
NARRATOR: You open the last can of tuna and set it next to the radio.
NARRATOR: The radio has been silent for nine days.
NARRATOR: Tonight, it clicks on by itself.
NARRATOR: A man's voice, very calm: "If someone knocks, do not open. No matter who it is."
NARRATOR: Static.
NARRATOR: You almost laugh. Nobody knows where you are.
NARRATOR: Twenty seconds later, something walks across the hatch above your head.
NARRATOR: Slow. Heavy. It stops right over the ladder.
NARRATOR: Three knocks.
NARRATOR: Then a voice you know better than your own.
NARRATOR: "Gabry? It's me. Open up, it's freezing out here."
GABRY: Mom?
NARRATOR: Your mother died six years ago.
```

Sample B, Entrepreneur:
```
NARRATOR: March 1994. Columbus, Ohio.
NARRATOR: You have $212, a borrowed car with a cracked windshield, and an idea everyone at the diner laughed at.
NARRATOR: Businesses are going to need websites.
NARRATOR: Most of them don't know what a website is.
NARRATOR: You print 40 flyers at the library. Ten cents a page.
NARRATOR: Four dollars you didn't really have.
NARRATOR: By Friday, one person calls. A dry cleaner named Walt.
NARRATOR: "So what is it, like a TV ad?"
GABRY: Kind of. But people find you on their computer.
NARRATOR: A long silence.
NARRATOR: "Kid, my customers don't have computers."
NARRATOR: He's about to hang up.
GABRY: Your customers' kids do.
NARRATOR: Another silence. Then: "How much?"
NARRATOR: You never decided on a price.
```

Sample C, Entrepreneur:
```
NARRATOR: You are 80 years old, and the bank manager is explaining the word "loan" very slowly.
NARRATOR: You took out your first loan before he was born.
NARRATOR: You slide a folder across his desk.
NARRATOR: Inside: one recipe card, handwritten in 1961, and a list of 14 cafes that already said yes.
NARRATOR: He reads the list twice.
NARRATOR: Then he asks the question you came here for.
NARRATOR: "Sir... and if something happens to you before it's paid off?"
GABRY: Then you'd better approve it fast.
NARRATOR: He doesn't laugh.
NARRATOR: He slides the folder back.
NARRATOR: Then he stops, and turns the recipe card over.
NARRATOR: On the back, in your handwriting: his grandmother's name.
```

### 7.4 library/profile/storytelling.md (complete draft)

````markdown
# Storytelling rules

These rules steer every proposal, outline and script.
The bar is a novel read aloud, not a plot summary.
If a scene could be replaced by "something bad happened", it is not developed enough. Rewrite it.

## Universal rules
1. Dramatize the events that define the story; never summarize them. Unimportant transitions may be one line.
   Bad: "The next morning, you decided to find a job."
   Good: "7:12 AM. You're outside a bakery. The owner looks at your shoes, then your face. 'Experience?'
   You say no. He starts closing the door."
2. Be specific: numbers, times, objects, distances, amounts, sensory details, exact dialogue.
   Every detail serves the scene, the stakes or the atmosphere. No random numbers.
3. Second person, present tense: "You open the door." Never "Gabry opens the door."
4. Every scene does at least one job: introduce a problem, reveal information, establish a relationship, force a
   decision, create a consequence, raise tension, change the situation, set up a later event. No job, cut it.
5. Every problem has consequences that come back. Lost money stays lost. An injury slows you down later.
6. Dialogue sounds like real people. No speeches, no shouting in capitals, no characters explaining their feelings.
7. Never explain what the viewer can understand. Not "you're terrified someone is inside", but
   "The kitchen light is on. You turned it off before going upstairs."
8. Make ordinary things important: a can of tuna, a 12 dollar order, a dead charger, a message from your mother.
   The ordinary sets up the extraordinary.
9. Escalate naturally. Alternate normal moments, small problems, odd details, serious complications, brief relief and
   big revelations. If everything is urgent, nothing is.
10. Objects tell the story: a receipt, a footprint, a bank statement, a half-eaten meal.
11. No convenient solutions. A solution costs something, creates a new problem, or comes from an earlier decision.
12. Every part has its own arc: a starting situation, a development, a complication, a meaningful change, and an
    ending that makes the next part necessary.
13. Cliffhangers are concrete events (see Cliffhangers).
14. Gabry's personality for this story (from plan.md) drives his choices, including the bad ones.

## Isolation rules
- Establish the physical reality first: where you are, for how long, what you have, what is broken, how far help is.
- Survival details are real: food, water, warmth, batteries, injuries and exhaustion run out and matter.
- The unknown arrives gradually, starting with something that doesn't fit: a locked door now open, footprints that
  lead in but not out.
- Every threat has rules and keeps them. No new powers when the plot needs help.
- Isolation is shown, not stated: "You haven't spoken to anyone in 19 days. Yesterday you explained your dinner to
  the empty chair."
- The environment is an antagonist: storms, frozen rivers, fog, darkness, power cuts.
- Gabry reacts like a real person: he thinks about doors, windows, noise and supplies before acting. He never walks
  into the dark alone without a reason.

Isolation techniques:
- A. Ordinary action interrupted by the impossible (the tuna can and the radio).
- B. Information that arrives too late ("Never sleep facing the door." You have, for two weeks.)
- C. The false sense of safety (the generator finally works; the lights show muddy footprints on the kitchen floor).
- D. Contradictory evidence (the calendar says October 12; the radio says October 19).
- E. The human threat (a stranger knows exactly how much food you have left).

## Entrepreneur rules
- Open on a concrete situation, never a dream: "11:46 PM. Your account has 183 dollars. Tomorrow is your first
  client meeting. You haven't decided what to charge."
- Progress is earned: a problem worth solving, customers, an offer, delivery, acquisition, objections, cash flow,
  competition, reinvestment. Each one shown through events.
- The money ledger is exact: starting capital, revenue, expenses, profit, unpaid invoices, debt, inventory, cash.
  Revenue is never called profit. No money appears or disappears without a scene.
- Every business decision has a trade-off with numbers: "80 dollars on ads leaves 40 for the month."
- Customers are real people: demanding, late to pay, indecisive, sometimes genuinely helpful.
- Gabry makes mistakes with real consequences. Not every failure becomes a lesson.
- Family pressure is nuanced: worried, tired of waiting, comparing. Never cartoon villains.
- Small wins feel big: the first paid invoice, the first repeat customer.
- Teach through events, never lectures: 38 emails, 30 no replies, 5 already have someone, 2 not interested,
  1 asks for a portfolio.
- The era sets the tools and the prices (1994 means flyers, fax machines and landlines). research.md is the source.

Entrepreneur techniques:
- A. Money on the table (73 dollars and 20 cents left; the subscription renews tomorrow).
- B. The client conversation ("My nephew makes websites. Why should I pay you?").
- C. The family confrontation (your father reads the electricity bill, then your sales: zero).
- D. The opportunity at the worst time (the big client calls the day your laptop dies).
- E. The unexpected consequence (lower prices bring more orders, and every order loses money).

## Crime and consequences
- Allowed as drama: shortcuts, scams, rule-breaking, police, investigations, arrests.
- Consequences are realistic and come back later.
- Methods stay vague. Nothing a viewer could copy step by step.
- A story can teach something real: how a scam is spotted, why a shortcut collapses.
- No crime or get-rich shortcut ends as a win without cost.

## Hooks
- Every idea has its own hook: the first spoken line of Part 1. Never reuse a hook or fill a template.
- The first sentence puts the viewer inside the situation. No introduction, no "imagine".
- Shapes to draw from, never to copy: an ordinary action interrupted; a specific amount and a deadline; an era or
  identity drop ("March 1994. You have 212 dollars."); a rule or a warning; a contradiction (a warning dated
  tomorrow); an offer with a condition; a dare premise ("the most evil way possible"); a message that shouldn't exist.
- From Part 2 on, the recap hook (3 to 7 s) reminds the viewer and adds the new problem in the same breath.

## Cliffhangers
Every non-final part ends on exactly one of:
1. Revelation: new information changes what was happening.
2. Unexpected arrival: someone or something appears.
3. Immediate consequence: something goes wrong at the worst moment.
4. Impossible discovery: something that shouldn't exist.
5. Irreversible decision: a choice with heavy consequences.
The cliffhanger is a concrete event, and the next part follows from it.
Never: "little did you know", "everything was about to change", "things were about to get worse",
"you had no idea what was coming", "this was only the beginning", "tomorrow would be different".

## The final part
Resolves the central conflict. It may end on one small optional detail that opens a door, never on another cliffhanger.

## Plan and bible
- Never write Part 1 before plan.md holds the sealed ending.
- bible.md tracks: Gabry's variables for this story, timeline, locations and distances, characters and motivations,
  open mysteries, planned revelations, consequences already set in motion.
- Isolation adds: survival inventory and threat rules.
- Entrepreneur adds: the money ledger.
- Nothing from a previous story is ever read or reused.

## Part approval checklist
A part passes only when every line is true:
1. The first sentence creates curiosity.
2. The viewer is "you" throughout; the narration never names Gabry.
3. Important events are real-time scenes, not summaries.
4. Details are concrete and serve the scene.
5. Dialogue sounds human; each Gabry line is 12 words or fewer.
6. Every scene has a job.
7. Gabry acts consistently with this story's personality and situation.
8. Money, resources, injuries, locations and knowledge match bible.md.
9. The part moves the story toward the planned ending.
10. It ends on one concrete cliffhanger type, or resolves the story if it is the final part.
11. Spoken length is 90 to 120 s (225 to 300 words until the voice pace is measured).
12. No needless repetition and no banned phrasing.
13. From Part 2 on: the recap lasts 3 to 7 s and contains the new problem.
````

### 7.5 library/hooks.txt

Not used. Every idea carries its own hook, and the hook rules live in `storytelling.md`.
Engine requirement: the generated format takes the hook from the idea instead of picking from `hooks.txt`.
If the engine needs the file to exist, it holds a single comment line pointing to `storytelling.md`.

### 7.6 ideas.txt

Each `{...}` block is a seed for Stage 0, not a finished idea: the story gate expands it.
Block format (my choice), one line per block: `{Universe | hook | optional notes}`.
Universe is `Isolation`, `Entrepreneur` or `Either`.

Starting seeds (proposals: pick 10 to 20 and add yours; the first three are yours, with hooks I wrote):

```
{Entrepreneur | It's 1994 in America, and you want to start a business. You have $212 and a borrowed car.}
{Entrepreneur | You're 80 years old, and you just asked a bank for a five-year loan.}
{Entrepreneur | You decide to build a business the most evil way possible. Your first victim is your neighbor.}
{Entrepreneur | You wake up on a bench with $17 and one shoe. In 30 days, you need an address.}
{Entrepreneur | Your father gives you one year and $500. If the business fails, you take the factory job he already found you.}
{Entrepreneur | You inherit your uncle's dying hardware store. It has $3,000 of debt and one loyal customer.}
{Entrepreneur | Your first order arrives at 11:38 PM. 47 units. You have 6 in stock.}
{Entrepreneur | Chicago, 1926. Your bakery is doing well. Too well: a man in a gray coat wants a weekly fee.}
{Entrepreneur | You sell your laptop to pay for your first 100 products. They arrive broken.}
{Isolation | You've worked alone at a weather station in northern Norway for 26 days. This morning, it prints a warning dated tomorrow.}
{Isolation | Day 43 in the bunker. You open the last can of tuna, and the radio says: if someone knocks, do not open.}
{Isolation | You're the last person in your apartment building. Every night, one more window lights up.}
{Isolation | You wake up on a cargo ship in the middle of the Pacific. The engines are running. Nobody else is aboard.}
{Isolation | You're stranded in the Arctic with food for 30 days. Rescue is 90 days away.}
{Isolation | You keep a lighthouse running after the whole coast was evacuated. Tonight, a ship answers your light.}
{Isolation | The rescue team finally answers your radio. They ask how many people are in your cabin.}
{Isolation | You find a staircase in the forest. You've been walking down it for six hours.}
{Isolation | Your camera shows someone entering your cabin every night at 3:17 AM. The door never opens.}
```

### 7.7 library/profile/pronunciations.txt (partial)

```
Gabry = GAH-bree
```

Confirm the pronunciation. New names in a story go into that story's `bible.md`, and the engine applies them for that
story only (engine requirement).

### 7.8 library/voice/engine.txt (pending the audition)

Shape (engine requirement: two voice keys):

```
engine = kokoro
lang = a
voice_narrator = (from the audition)
voice_gabry = (from the audition)
speed = (set by the build)
```

Candidates (af_bella is excluded, already taken):
- Narrator: am_onyx, am_michael, af_heart, af_nicole. A female narrator against a male Gabry makes every speaker
  change instantly audible, which matters here because the narrator says "you" and Gabry says "I".
- Gabry: am_puck, am_liam, am_echo, am_eric.

Audition request for Claude Code (paste in the repo folder):

```
Render with Kokoro (lang a, speed 1.0) the sentence "Day forty-three in the bunker. The radio clicks on by itself, and a calm voice says: do not open the door." once each with am_onyx, am_michael, af_heart and af_nicole, and the sentence "Mom? Is that you? I'm not opening until you tell me my middle name." once each with am_puck, am_liam, am_echo and am_eric, saving each file as <voice>.wav in build/voice-audition/scenarios/.
```

### 7.9 library/character/gabry.md (rules complete; visual identity pending)

Contents:
- Role: the protagonist of every story, always "you".
- Fixed: name, face, proportions, fixed colors, line style, voice (section 3).
- Variable per story: age, personality, approach, era, place, job, outfit, resources, family (section 3).
- Never: narrated in third person; a personality switch without a cause; superpowers outside a story's rules.
- Age variants: how the same design reads as a kid, a teen, an adult and an 80 year old (style round).
- Outfits: one default, plus per-story outfits generated from the era and job.
- Expressions: a fixed set (neutral, alarmed, determined, smug, exhausted, devastated) reused everywhere.
- Side characters: created per story in `bible.md`, drawn from a shared set of body and face templates (style round).
- Visual identity: pending (a cartoon version of Gabriele from photos, or an original design; see section 9).

### 7.10 styles/<style id>/style.md (pending the style round)

Known constraints:
- Code-drawn: flat vector shapes, clean outlines, limited gradients, hard-edged shadow shapes, vignettes,
  silhouettes, particles (rain, snow, dust, smoke, flicker). No painterly textures, realistic lighting, or complex
  hair and cloth physics.
- Pacing: a visual change every 3 to 5 s means 18 to 40 visual beats per part.
- One style for the channel. Whether the two universes differ by palette and lighting inside it is decided in the round.
- Generic UI library: map, phone lock and home screens, chat app, email, bank app, store dashboard, ad dashboard,
  calendar, security camera feed, radio and printed weather report, newspaper. Era devices: landline, pager, fax,
  CRT monitor, paper ledger.
- Subtitles must tell the narrator and Gabry apart.
- On-screen elements to define: story title card, part badge, "End of Part N" card.
- References: the reference videos, each with what to take and what not.

### 7.11 Sound (pending)

- The pack's folder path and what's inside.
- Isolation needs: room tones and ambience (wind, hum, rain), radio static, knocks, footsteps, creaks, metal,
  breathing, low stingers.
- Entrepreneur needs: notification pings, phone buzz, typing, mouse clicks, doors, cash register, street and office
  ambience, small comic stings.
- Music bed: yes or no, and from where.

### 7.12 Platform text (YouTube Shorts)

- Title, 100 characters max (my choice): `<hook phrase> | <Story title>, Part <N>`.
  Example: `The warning was dated tomorrow | The Last Weather Station, Part 1` (65 characters).
  The hook phrase changes every part and never spoils the cliffhanger.
  No "of M": the part count can change at a gate after earlier parts are already published.
- Description, 1000 characters max: what this part is about without spoiling its ending; different every part;
  short lines; at least one list (lines starting with "- "), for example story, part and universe; from Part 2 on,
  a line saying Part 1 is on the channel; ends with exactly 4 hashtags.
- Hashtags: required tags pending. Default (my choice): #shorts plus 3 topical tags, one of them a universe tag
  (#survivalstory or #businessstory).
- Pinned comment (my choice: yes): one question tied to the cliffhanger that invites replies
  ("Would you open the door?"), plus a line saying the next part is coming.
- Hand steps at upload: set the related-video link to the previous part, and add the part to the story's playlist.
  The export cannot know published URLs.

---

## 8. Engine requirements (for BUILD_SPEC)

1. A gated, conversational story format: gates G0, G1 and G2 (section 6), holding with no timeout, resuming after
   a decision, accepting "you decide", and keeping every proposal and decision in the story folder.
2. A surface where the gates are discussed (pending, section 9).
3. Story-level state: research, plan with a sealed ending, bible, ledger or inventory, per-story pronunciations.
   Cleared between stories: nothing carries over.
4. A research stage per story, with web search and sources.
5. Two-voice text to speech driven by speaker tags (NARRATOR, GABRY), with two voice keys in `engine.txt`.
6. Spoken-form normalization for numbers, money, times and dates (subtitles keep digits).
7. Shorts up to 120 s on the platform config.
8. Hooks taken from the idea and the plan; `hooks.txt` not required.
9. Release order: one story at a time, parts in order; exports labeled with story title and part number.
10. A reusable Gabry character rig (age variants, outfits, expression set) and shared side-character templates.
11. A reusable generic UI component library (section 7.10), including era devices.
12. Script checks: continuity against `bible.md`, the 13-line part approval checklist, banned phrasings, word window.
13. Lookahead: the next part's G2 proposals prepared while the current part renders.

---

## 9. Open items

1. Channel name and handle (shortlist in section 10).
2. Intensity ceiling: confirm "death and violence off screen, no blood or bodies shown".
3. Other characters' dialogue: read by the narrator (current default) or by extra voices.
4. A script approval gate before voice and render: yes or no.
5. Where the gates happen (a Claude Code chat in the repo, a local page, or something else).
6. Gabry's visual identity: a cartoon version of Gabriele from photos, or an original design.
7. Voice audition: pick the narrator and Gabry voices.
8. Pronunciation of Gabry.
9. Style round: art style, palette, outlines, camera, pacing, subtitles, cards, references.
10. Sound: the pack path, contents, music bed.
11. Required hashtags, if any.
12. Final pick of 10 to 20 seeds for `ideas.txt`.

---

## 10. Name candidates

| Name | Id | Why | Watch out |
| --- | --- | --- | --- |
| Gabryverse | gabryverse | every story is a different Gabry in a different world; unique and searchable | doesn't say "stories" by itself |
| Lives of Gabry | livesofgabry | says exactly what the channel is: one protagonist, many lives | longer handle |
| If You Were Gabry | ifyouweregabry | states the second-person mechanic | long |
| Chapter Gabry | chaptergabry | the book feel, the protagonist's name | weaker on what happens |
| Torn Pages | tornpages | the "page torn out of a bigger book" feel | generic, likely taken, drops Gabry |

Recommended: Gabryverse. Check that the handle is free on YouTube before deciding.
