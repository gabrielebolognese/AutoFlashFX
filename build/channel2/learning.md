# Learning: adjustments, conflicts and error correction

Version 1, 2026-11-08. Input for the spec rewrite at the M18 pause (BUILD_SPEC.md new section and PLAN.md milestone
M22 "Learning", for every channel). Written from Gabriele's rules in the chat of 2026-11-08:
- the pipeline must learn from his feedback, for anything (ideas, hooks, story, script, voice, style, sound, post text)
- one adjustments file per channel, with topic sections
- the adjustment always wins over the base documents
- a conflict is always said in chat first; with his approval the base document is rewritten and the adjustment
  deleted, so adjustments.md only holds things the base documents do not say (additions and specifics, such as
  "houses are always brown")

---

## 1. The files

Per channel, inside `channels/<id>/`:

| File | Who writes it | What it holds |
| --- | --- | --- |
| base documents (below) | Gabriele, or a chat session with his approval | what the channel is: the rulebooks |
| `library/profile/adjustments.md` | a chat session, only on Gabriele's word, through `pipeline/bin/adjust` | learned rules the base documents do not contain |
| `library/adjust-map.json` | the build (Gabriele may edit) | which sections each stage reads, which base document owns each topic, what must be rebuilt when a base document changes |
| `logs/adjustments.log` | `pipeline/bin/adjust` | one line per event: added, replaced, merged, removed, undone, suggested, rework |
| `logs/adjustments-suggested.md` | the pipeline | candidate rules found by the pipeline itself, never active until approved |
| `logs/adjustments-stats.json` | the runner | per rule: runs that used it, review checks passed and failed |

Base documents per channel (the base document map in adjust-map.json names them):
- FlashFX: styles/paper-cards/style.md and tweaks.md (style changes go into tweaks.md, its existing override layer,
  which build-tokens already reads), library/profile/voice.md, account.md, pronunciations.txt, deliverables.txt,
  library/hooks.txt, the brand section of tweaks.md.
- Second channel: styles/inkhead/style.md, library/profile/account.md, voice.md, storytelling.md,
  library/character/gabry.md, pronunciations.txt, channel.json (export text settings).

No file is shared between channels. A rule Gabriele wants for both channels is saved twice, once per channel, and
each copy is conflict-checked against its own channel's base documents.

## 2. The shape of adjustments.md

Fixed sections, in this order: General, Ideas and premises, Hooks, Story and structure, Script and dialogue,
Voice and pronunciation, Visuals and style, Sound, Captions and post text, Inbox.
Each section holds at most 8 rules (the Inbox has no limit): at 5 it is marked for merge, at 8 it is full
(section 5).

One rule per entry:

```
## Hooks
- A-0012 | 2026-11-09 | scope: Isolation | Open on a sound or a physical detail, never on a time stamp; the tone is quiet dread.
  source: "good, but start with the knock instead of 'Day 43'" (chat 2026-11-09, the-last-weather-station, G1)
```

- id: A-NNNN, never reused.
- date: when it was saved (or last changed).
- scope: `all`, or tags the runner knows (FlashFX: solution type flashfx, external, method; second channel:
  Isolation, Entrepreneur, part 1, middle part, final part, recap, a premise kind), or free text ("1920s stories")
  that the stage's model judges.
- the instruction: one or two sentences, imperative, concrete enough to check (section 6 refuses vague ones),
  at most 300 characters, no em dash.
- source: Gabriele's own words, verbatim, with where they were said.
- an optional status tag: `[pending-merge: styles/inkhead/style.md 4.1]`, `[blocked: rework failed, see logs]`.

The Inbox section holds feedback that could not be processed yet (section 7): Gabriele's words verbatim, never
lost. Hand edits are allowed: the stages read each section as text, so a line that does not parse still reaches
the model; `adjust lint` reports it.

## 3. Capture: what happens when Gabriele gives feedback in chat

A rule in CLAUDE.md sends every chat session in the folder to `pipeline/knowledge/adjustments-procedure.md`, the
procedure below. The judgment (what kind of feedback, how to generalize, is there a conflict, which lines of the
base documents must change) is made by one pipeline command, `adjust propose`, so every session behaves the same
way and the behavior is versioned and tested. The chat session gives it the feedback and the item it refers to,
then shows Gabriele the result and carries out his answer.

1. Classify the feedback (adjust propose returns one of):
   - one-off: about this proposal only ("make Walt grumpier in this one"). Applied to the item, nothing saved.
   - story: true for the rest of this story only. Saved in the story's bible.md (second channel), never in
     adjustments.md.
   - rule: true for future content of a kind. Goes on to step 2.
   - base edit: Gabriele is changing what the channel is ("faces are white from now on"). Goes to the conflict path
     (section 4 A) directly.
   - hard limit: asks for something the engine forbids (section 4 C). Explained, never saved as asked.
2. Generalize: write the rule in the shape of section 2, with the narrowest scope that matches what he said
   (a remark about an Isolation hook is scoped to Isolation unless he says "always" or "all").
3. Check, before saving: the command gathers the candidate lines with `adjust candidates` (deterministic: the
   sections of the base documents the map links to this topic, plus every line sharing key terms with the rule,
   plus every adjustment in the same section and overlapping scopes) and the model compares the rule with each
   candidate: same, refines, narrows, contradicts, unrelated.
4. Act and say it in one line:
   - no conflict: save, and show `Saved A-0012 (Hooks, Isolation): ...`
   - duplicate: keep the old rule, add the new source to it, show `Already a rule (A-0007); added your words to it.`
   - refines an existing rule: one combined rule replaces both (new id, both sources), shown as a before and after.
   - narrows a broader rule: saved; the broader rule keeps applying outside the new scope; shown once:
     `A-0003 still applies to Entrepreneur hooks; Isolation hooks now follow A-0012.`
   - contradicts a rule or a base document: section 4.
5. Gabriele can always answer: "just this once" (the saved rule is removed: it becomes a one-off), "make it a
   rule" (a one-off becomes a rule), "for both channels", "undo", or discuss.

## 4. Conflict handling

### Precedence (the order every stage follows, highest first)

1. Hard limits: the platform (length, safe zones, title and description limits), channel isolation, the engine
   rules of the spec (never AI images or video, the voice engine, no em dash, timings the format needs).
2. Gabriele's explicit words for this item: a gate decision ("B, but with the knock first"), the idea's own text
   and hook.
3. The story's plan.md and bible.md (second channel), for that story.
4. Adjustments: a narrower scope beats a broader one; with the same scope, the newer beats the older.
5. Base documents (for FlashFX, tweaks.md beats style.md, as today).
6. The engine's defaults.

Every stage prompt states this order in one line above the rules block: "These are your channel's learned rules.
When they differ from the documents above, follow these."

### A. Adjustment against a base document (Gabriele's example: a white face, the style bible says an ink face)

1. Said in chat at once, never silently resolved. The session shows:
   - the new rule and the conflicting lines, quoted with file and section
     (style bible 4.1 "Head: circle, ink fill", 4.1 eyes "2 white ovals", 3.1 token ink "heads",
     5 "the ink face system")
   - the rewrite it proposes: every affected line of every base document (the ripple: the eyes need a new color on
     a white face, gabry.md's fixed traits change too), as a before and after
   - the assets this touches, from adjust-map.json: tokens.json (rebuilt automatically), components that need
     code changes (Gabry's rig and model sheet, the side character templates, the golden video): a rework
     (section 4 F), with its size
   - the question: approve the rewrite / not now / drop my rule.
2. Approve: the base documents are rewritten with exactly the shown edits, build-tokens runs, the adjustment is
   deleted (the base document now says it), one commit `adjust(<channel>): ...` holds the whole change, the log
   gets one line, and a rework starts when assets need it.
3. Not now: the rule is saved with `[pending-merge: <file> <section>]` and it wins from the next stage that runs
   (precedence 4 over 5). Every later chat that starts with "anything waiting?" lists the pending merges first.
4. Drop my rule: nothing is saved.
5. The rule of thumb for what stays in adjustments.md: anything that changes what a base document says goes into
   that base document, a scoped exception included (written there as "except in Isolation stories: ..."). Only
   what no base document covers stays as an adjustment. The pending-merge state is the only time a conflicting
   rule lives in adjustments.md.
6. Gabriele may also edit a base document by hand. The next `adjust lint --deep` (section 6) finds the
   adjustments the edit made redundant or contradicted, and the next chat proposes removing them.

### B. Adjustment against adjustment

- Same scope, opposite instructions: the newer wins at once. The chat says
  `This replaces A-0007 (2026-11-09): "...". Remove A-0007?` On yes the old rule goes to the history (git and the
  log). On no, Gabriele says how they coexist (usually a narrower scope for one of them).
- Overlapping scopes: not a conflict; the narrower wins inside its scope (step 4 of section 3).
- Two rules that cannot both be met in one item (hooks under 8 words, and hooks that always name the era, the place
  and the amount): treated as a conflict, said in chat, with a proposed combined rule.

### C. Adjustment against a hard limit

The session explains the limit and proposes the nearest allowed rule ("subtitles in the bottom 10%" falls in
YouTube's title zone; nearest allowed: the lowest safe line, 70%). Nothing is saved until Gabriele picks. A limit
that he wants changed is a code or spec change, not a rule: the session says so and offers to do it as normal work
in that chat.

### D. Adjustment against the story (second channel)

A rule saved in the middle of a story applies from the next part, unless it would break continuity inside the
running story (a new rule "Gabry never owns a car" while the story's bible has his car): the chat asks whether it
starts with the next story or changes this one too (then the bible is updated in the same step).

### E. Conflicts found at run time

The capture check stops almost every conflict, but hand edits can create new ones. Every stage follows the
precedence above, and the review stage reports any pair of rules it found contradictory (`rule_conflicts` in its
output). They are logged and shown at the top of the next chat, with a proposed fix.

### F. Rework: when a base document change needs new assets

A merged style change that tokens alone cannot carry (a white face, a new hair shape) needs component code. The
runner does it between ideas, before any new visual stage, in the same pattern as S15's capability upgrade:
a builder session updates the channel's components to the new base document, frame-match and the gallery stills
run, the golden video is rendered again, a reviewer session checks, at most 2 fix rounds. The builder may edit only
that channel's motion-lib (and its candidates), never a base document or adjustments.md.
- Success: one commit, and the before and after stills wait in chat for Gabriele ("anything waiting?"). He approves
  (done) or rejects (the rework is reverted and the chat discusses what to change).
- Failure: the components and the base document edit are reverted together, the rule goes back to adjustments.md
  as `[blocked: rework failed]` with the reason in the log, and the chat shows it first. A blocked rule is still
  given to the stages as a wish but the review does not fail a video on it.

## 5. Error correction: rules that turn out wrong

- Over-generalized ("I meant only that one"): "just this once" or "undo" removes it at once. Every change is its own
  commit, so `adjust undo` restores the files exactly as before (byte for byte), including a merge.
- A rule that makes results worse ("the quiet hooks are not working"): removed or replaced like any rule. "What
  changed this week" in chat lists every rule added, replaced or merged in that time with the videos made since,
  to find the culprit.
- A rule the pipeline ignored (Gabriele sees a finished video that breaks it): the session checks the run folder:
  was the rule in the stage's prompt (calls/ keeps every prompt, adjustments-used.json lists the ids), and did the
  review check it. Then it fixes the cause: a wrong scope, a section the stage does not read (adjust-map.json), or
  a rule too vague to follow (rewritten more concretely, with his approval). The rule then gets a review check.
- A rule broken again and again: adjustments-stats.json counts the review checks per rule. A rule failed in 3
  videos out of the last 5 is shown in chat with a proposed rewrite.
- A vague rule ("make it better"): `adjust propose` refuses to save it and asks one question that makes it
  concrete ("better how: shorter, scarier, more specific numbers?").
- Growth, counted in rules, not characters (Gabriele, 2026-11-08): each section holds at most 8 rules. The Inbox
  has no limit; pending-merge and blocked rules count.
  - At 5 rules the section is marked for merge: the next chat, and every "anything waiting?", proposes moving
    rules into the base documents (the structure) to free slots. The proposal shows each rule with the exact
    file, section and before and after lines it would become, the oldest rules that have held in the reviews
    first; near duplicates are combined into one; rules never matched in 60 days are offered for removal. A rule
    saved in the same chat is never proposed. Approved, it runs like a conflict merge (section 4 A): the base
    documents are rewritten, build-tokens runs when a style file changed, the merged rules are deleted, one
    commit, a rework when assets need it. "Not now" keeps the mark; it is asked again at the next chat, never
    in the middle of a gate.
  - At 8 the section is full: a 9th rule cannot be saved until a slot frees. The chat says so in the same
    reply and offers three choices: merge now (recommended, the proposal above), replace one of the 8, or keep
    the new feedback in the Inbox verbatim, not active yet, until a slot frees.
  - Each rule stays at most 300 characters (section 2), so 8 rules never grow into a page.

## 6. Protection and file safety

- Models cannot write adjustments.md or a base document: protect.py (M18) covers them, and a fake model edit is
  reverted. Only `pipeline/bin/adjust` writes them, run by a chat session on Gabriele's word.
- Writes are atomic (a temp file renamed) under the channel's adjust lock; a reader never sees half a file.
- Each stage copies the sections it reads into its own folder when it starts (`adjustments-used.json` with the ids
  and the text). A change made during a run applies from the next stage, and every run records exactly which rules
  it followed.
- `adjust lint` (deterministic, in preflight and doctor, a WARN never a stop): ids unique, known sections, dates,
  length, em dashes, statuses pointing at real files and sections, malformed lines.
- `adjust lint --deep` (one model call, run before a merge proposal or on request): redundant or contradicted rules after
  a hand edit of a base document.

## 7. When the machinery itself fails

- The model call of `adjust propose` fails or hits a limit: ai.sh waits and retries as for every call; if the chat
  cannot wait, Gabriele's words go to the Inbox verbatim and the next chat processes them first.
- A proposed base document edit no longer applies (the file changed since the proposal): the proposal is made
  again from the current file, never forced.
- build-tokens fails after a merge: the merge is reverted and the rule stays as pending-merge, with the error.
- A rework fails: section 4 F.
- The lock is held (a runner stage is copying the sections): the writer waits up to 30 s, then retries.
- adjustments.md missing: the stages run without rules and preflight warns; `adjust init` writes the empty template.

## 8. Where the rules are used

- Every stage that builds a prompt reads the sections adjust-map.json (or, from M20, the stage's entry in
  format.json, key `adjustments`) lists for it, always plus General, filtered by scope against the run's tags.
  - FlashFX: S1 to S4 Ideas and premises; S5 and S6 Hooks; S7 Script and dialogue, Voice and pronunciation;
    S9a to S10 Visuals and style; S11 Sound; S14 Captions and post text; S12 all sections it can check.
  - Second channel: the seed proposals (G0) Ideas and premises; the storyboards (G1) and the part approaches (G2)
    Story and structure, Hooks; the script Script and dialogue, Voice and pronunciation; the shots and the build
    Visuals and style; the sound Sound; the export Captions and post text; the review all it can check.
- The review checks the rules: the edit review gets the active rules of the sections it judges and reports a
  violation as a tagged issue `[rule A-0012]`, routed back to the stage that owns the section, like every issue.
  Rules with a mechanical form (a color, a count, a word list) get a mechanical check when adjust-map.json names
  one. Each check updates adjustments-stats.json.

## 9. Suggestions: the pipeline proposing rules itself

Never active until Gabriele approves. Written to logs/adjustments-suggested.md, shown in chat at "anything
waiting?" or at the next gate, at most 2 at a time:
- choice patterns: every 10 gate decisions, one cheap model call reads the options and the picks ("you picked the
  quieter hook 5 times out of 6, against the recommended one").
- recurring review issues: the same issue tag in 3 videos out of the last 5.
- recurring corrections: the same kind of one-off asked 3 times ("you have asked to shorten the recap in 3 parts").
Approved, a suggestion goes through section 3 like any feedback (conflict check included).

## 10. In chat

- "anything waiting?" lists, in this order: blocked rules and run-time conflicts, pending merges, rework results to
  approve, full sections and sections marked for merge (section 5), open gates, suggestions, the Inbox.
- Natural requests: "show the rules", "show the hook rules", "remove the rule about the knock", "undo", "what
  changed this week", "merge the hook rules", "for both channels".
- Every change ends with one line saying exactly what was saved, replaced, merged or removed.

---

## 11. The batch: M22 Learning (every channel)

Placement: after M21, before the second channel's milestones (which follow as M23 onward in the rewritten plan).
Not before the channel separation: M18 moves the library into channels/<id>/ under the move plan M17 just wrote,
and M18 to M20 compare tight fingerprints, so the learning would be built on paths that then move and would disturb
the riskiest milestones. Not at the end: the second channel's stages would be built without it and fixed up later,
and its first stories, where most feedback comes, would not be learned.

Depends on: M18 (channel paths, protect.py, per-channel locks), M20 (format.json for the per-stage sections, the
review moved behind the formats), M21 (the capability upgrade pattern the rework reuses), M12 and M11 (the stages and
the review loop).

Creates:
- `pipeline/lib/adjust/` (parse, lint, candidates, add, replace, remove, undo, merge with the base document edits,
  snapshot, stats, suggest, init) and `pipeline/bin/adjust` (one subcommand each, `--channel` required, JSON out
  for the chat session, readable lines for Gabriele).
- `adjust propose`: one model call (config models.adjust, sonnet, medium) with
  `pipeline/stages/_prompts/adjust-propose.md` and its schema: the classification, the generalized rule, the
  comparison with every candidate line, the proposed base document edits with the ripple, the assets touched.
- `pipeline/knowledge/adjustments-procedure.md` (sections 3, 4, 5 and 10 as steps a chat session follows) and the
  CLAUDE.md rule pointing at it, next to the braces rule.
- The template `library/profile/adjustments.md` and `library/adjust-map.json` for flashfx and for the
  problem-solution-reel and the second channel's format templates (new-channel copies them).
- The rules block in every prompt-building stage (one shared helper), filtered by scope, with the precedence line;
  `adjustments-used.json` in every stage folder; format.json key `adjustments` per stage.
- The review: the rules check, the `[rule A-NNNN]` tag and its routing, `rule_conflicts`, adjustments-stats.json.
- The rework step between ideas (builder, frame-match, gallery, golden, reviewer, 2 fix rounds, commit or revert
  with the base document edit, the status line, logs/rework.json, the before and after stills for the chat).
- Suggestions (choice patterns, recurring review issues, recurring corrections) into logs/adjustments-suggested.md.
- protect.py covering adjustments.md and every base document of the map; preflight, doctor and runner-status
  showing lint warnings, pending merges, blocked rules, rework results waiting, the rules per section (marked
  at 5, full at 8) and the Inbox count.
- `pipeline/tests/test-m22.sh` with a fixture channel (base documents with known lines, a small library, a golden)
  and planted feedback.

Acceptance test: `bash pipeline/tests/test-m22.sh`
- Capture, with a fake model and then one section with the real model on 20 planted feedback messages: each is
  classified as planted (one-off, story, rule, base edit, hard limit); every planted contradiction (10 against base
  documents, 5 between rules) is found and none of 10 harmless rules is flagged; the vague one is refused with a
  question; the hard-limit one gets the nearest allowed rule.
- `adjust candidates` returns the conflicting base document line for every planted contradiction (deterministic,
  same output twice).
- Merge: the white-face case on the fixture rewrites exactly the shown lines, rebuilds tokens, deletes the rule,
  makes one commit and queues a rework; `adjust undo` restores every file byte for byte.
- Pending merge: a saved conflicting rule reaches the stage prompt above the base document with the precedence
  line, and "anything waiting?" (the procedure's listing command) shows it first.
- Rules between rules: same scope, the newer one is the only one in the prompt; a narrower scope wins only inside
  it; a duplicate adds a source instead of a rule.
- Run time: a Hooks rule reaches the hooks stage's prompt and not the script's; a rule scoped to Isolation reaches
  an Isolation run and not an Entrepreneur one; adjustments-used.json lists the ids; a rule saved while a stage runs
  applies from the next stage.
- The review (fake editor) reports a planted violation as `[rule A-NNNN]`, routed to the owning stage; the stats
  count it; 3 failures out of 5 produce the rewrite proposal.
- Rework (dummy sessions): success gives one commit and the stills; a forced failure reverts the components and the
  base document edit and marks the rule blocked; the review then does not fail a video on it.
- Safety: a fake model edit of adjustments.md and of a base document is refused and the file restored; a
  malformed hand-written line still reaches its stage and lint warns; a missing file runs without rules with a
  preflight WARN; two channels' rules never appear in each other's prompts (test-isolation.sh); the Inbox keeps
  the words when the model call fails.
- Growth: a 5th rule in a section marks it for merge and the next chat's proposal lists the rules with their
  before and after lines; an approved merge rewrites the base documents and deletes the rules in one commit; a
  9th rule is refused with the three choices, and the Inbox choice keeps the words inactive; the Inbox has no
  limit; nothing changes without the approval step.
- run-fake.sh meets the baseline rule; the dummy fingerprint of flashfx only gains adjustments-used.json files.
- Runtime: 3 to 6 hours.

---

## 12. Open questions for Gabriele

1. Answered 2026-11-08: a rule limit, not a character limit: at most 8 rules per section, marked for merge at 5
   (section 5).
2. Suggestions every 10 decisions, at most 2 shown at a time: fine?
3. Item 4 of the channel document: a script approval gate before voice and render (still waiting).
