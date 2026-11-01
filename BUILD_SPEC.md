# BUILD_SPEC: Instagram reels autopilot

## 0. Mission and how the build works

You are building, inside this folder (instagramReels), a pipeline that turns a short video idea into a finished
Instagram reel with no human in the loop: fact research, idea expansion, hooks, script, voiceover, visuals
generated in code (motion graphics and 3D written as code, never AI video generation), sound effects, review,
render, export. A Git Bash runner processes ideas one after another, indefinitely, and stops on its own only for
a systemic failure (section 4).

I am the only user. It runs on my Windows PC with Git Bash. I start the runner and walk away.

### Hardware

My PC is CPU-only: an integrated GPU, no NVIDIA card, no CUDA.
- Never install CUDA builds of PyTorch, never assume a GPU, never use device "cuda".
- Heavy steps (text to speech, transcription, renders) are slower than real time: use generous timeouts and print
  progress instead of treating a slow step as a hang.

### Build mode

The build is automated by build-runner.sh (in the root). It runs one milestone (section 12) per batch, each batch a
fresh Claude Code session: a build batch, then at most 2 lenient review batches, with a fix batch after each rejected
review. After the second review the build moves on to the next milestone whatever the verdict, and the fixes nobody
re-checked are listed in build/open-issues.md. Coding (build and fix batches) runs on Fable, and on Opus while Fable
is at its usage limit. Speed matters more than polish: a review rejects only for a failing acceptance test, a crash
or lost data, or something a later milestone needs. So in every batch:

1. Read this file, CLAUDE.md, PLAN.md, DECISIONS.md, build/progress.md, build/HUMAN_TODO.md, build/open-issues.md
   and pipeline/knowledge/known-issues.md (when they exist). These files are your memory between batches.
2. Do only the milestone you were given. Touch earlier milestones only when this one depends on it, and say so in
   your report.
3. Never wait for me and never ask questions: nobody is watching. When something needs me (recordings, approvals,
   links, choices), use the default given in this spec, keep going, and add a line to build/HUMAN_TODO.md
   (milestone, what I need to do, where).
4. Run the milestone's acceptance test until it passes. Commit with clear messages. Every commit is pushed to
   GitHub (origin, branch main) automatically by a git hook, so stay on main: never create or switch branches, and
   never rewrite pushed history (no commit --amend, no rebase, no reset of commits, no force push).
5. Decide everything else yourself and record each decision in DECISIONS.md.
6. Keep CLAUDE.md (section 11) current.
7. Never write an em dash in any file, prompt, caption, script or terminal message. Use commas, colons, periods or
   parentheses.

The batch prompt tells you which result line to end with.

## 1. Folder layout

```
instagramReels/
  BUILD_SPEC.md  CLAUDE.md  PLAN.md  DECISIONS.md
  build-runner.sh            builds the milestones (temporary)
  build/                     progress.md  HUMAN_TODO.md  M1/ M2/ ... (reports, reviews, fixes)
  run.sh                     the video runner: bash run.sh [--once]
  config.json                models, engines, caps, paths (section 9)
  ideas.txt                  the idea queue, I edit it (2.1)
  exports/                   finished reels: 1/, 2/, 3/ ... (section 8)
  library/                   everything I curate
    hooks.txt                my hook templates (2.2)
    profile/                 account.md  voice.md  deliverables.txt  pronunciations.txt (2.3)
    voice/                   reference.wav (and memo.* for building voice.md) (2.5)
  styles/
    sfx/                     my full sound effects pack, shared by every style and reel (2.6)
      sfx-map.json  SFX-MAP.md  overrides.txt  previews/  .cache/   (generated, except overrides.txt)
    paper-cards/             style.md  tweaks.md  vocabulary.md  tokens.json  refs/  analysis/ (2.4)
  motion-lib/                approved HyperFrames components, plus candidates/ and gallery/
  golden/                    1 or 2 golden reels (plan + render), examples for the visual director
  pipeline/
    lib/                     bash: ai.sh limits.sh review.sh state.sh ideas.sh status.sh log.sh
    stages/                  one folder per stage: run script, prompt.md, CONTRACT.md, schema.json
    bin/                     add-idea.sh, index-hooks, build-sfx-map, mix-sfx, screenshot, helpers
    vendor/ig-agent-skill/   MIT scripts from Jakeschincariol/instagram-agent-skill, with its LICENSE (section 10)
    knowledge/known-issues.md   symptom -> fix lines, written by the fixer (4.2)
    tests/
  tools/analyze_refs.py      already exists: reference video analyzer
  runs/                      one working folder per idea (machine only)
  logs/                      runner.log  status.txt  history.txt  blocked.txt  limits.log  suggested-ideas.txt  sfx-usage.json
```

Git: initialize a repo (if build-runner.sh has not). Track code and the text files in library/ and styles/. Ignore
runs/, exports/, logs/, styles/*/refs/, styles/*/analysis/, styles/sfx/ audio files and .cache/, library/voice/,
.env. Add .gitattributes so *.sh always uses LF line endings.

## 2. Inputs I edit

### 2.1 ideas.txt (create it, in the root)

- An idea is any text between { and }. It can span several lines. Text outside braces is ignored (I may leave
  notes there). No nested braces.
- The runner always takes the first idea in the file. New ideas are appended at the end.
- When an idea is exported, or dropped because no angle works, the runner deletes it from ideas.txt and writes a
  line to logs/history.txt. A blocked idea (4.2) is deleted too and copied to logs/blocked.txt with the reason,
  so I can re-add it.
- Handle CRLF line endings and UTF-8 (I may write in Italian).
- In an interactive Claude Code session in this folder, when my message contains text in braces, append each
  braced block to ideas.txt by running pipeline/bin/add-idea.sh (never by editing the file directly), then
  confirm in one line. This rule goes in CLAUDE.md.
- Every write to ideas.txt goes through one lock (a lock directory, .locks/ideas, created with mkdir, with a
  60-second stale timeout) and an atomic rewrite (write a temp file, then mv). The runner identifies its idea by
  a hash of the normalized text. If I edited that idea meanwhile, remove the closest match only if similarity is
  at least 0.9; otherwise leave the file alone and log it.
- Create ideas.txt with one test idea:

```
{Claude Code's frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it.}
```

### 2.2 library/hooks.txt

- One hook per line, not numbered, in this format: `5 small habits that improved my __ instantly.`
- `__` marks the blank. Surrounding quotes are optional. Empty lines and lines starting with # are ignored.
  Hooks without a blank are allowed. I add and delete lines freely, so never assume a count.
- pipeline/bin/index-hooks runs before every hooks stage and rebuilds library/.hooks.index.json whenever the
  file's hash changed:
  - id: first 10 hex characters of sha1 of the normalized text, so stats survive adding and deleting other lines
  - family: tools-listicle, how-to-system, mistake-warning, myth-contrarian, story-confession or transformation
  - fits_problem_solution: true or false
  - blanks: how many
  Family and fit come from one batched call to the indexer model. Never edit hooks.txt.
- It also writes library/hooks.lint.txt: lines with a broken blank (for example "changed everything in ." where
  the blank was probably lost), grammar problems, duplicates, em dashes.
- library/.hooks.stats.json, keyed by id: times picked, times won, judge scores.
- New hook shapes noticed during research go to library/hooks.suggested.txt. I move them into hooks.txt myself.

### 2.3 library/profile/

- account.md: who the account is for, the audience's problems, topics in and out, what I sell, my brand mark file.
- voice.md: built from the template in the instagram-agent-skill repo (templates/voice.md): who I am, what I sound
  like, my positions, off limits, proof I can use, the ask. Plus 3 to 5 verbatim excerpts of my real speech and my
  measured words per minute. Build it from library/voice/memo.* (a 5 to 10 minute voice memo, transcribed with
  faster-whisper). Keep my real English (I am not a native speaker): fix only real errors, never polish my phrasing
  into native idioms. If there is no memo yet, draft it from the template with clear placeholders and add a
  HUMAN_TODO.
- deliverables.txt: one per line, `KEYWORD | what they get | link`, or `to create` instead of a link.
- pronunciations.txt: one per line, `word = how to say it`, for example `FlashFX = flash F X`.

If a profile file is missing at runtime, continue with defaults and add a NEEDS REVIEW flag to the export.

### 2.4 styles/paper-cards/

- style.md is the look contract, tweaks.md overrides it, vocabulary.md lists the components to build.
- Derive tokens.json from style.md plus tweaks.md: colors, fonts, type scale, zones, margins, border and shadow
  sizes, motion timings, caption rules, pacing limits. Regenerate it whenever either file's hash changes.
  Validators and checks read tokens.json and never hardcode style numbers.
- All of this is read-only at runtime.

### 2.5 library/voice/

I set up the voice myself: Chatterbox Turbo, which clones my voice and runs on CPU. tools/voice.py already does
text in, audio out with it (subcommands: say, words, blindtest). There is no fallback voice: every reel uses only
my cloned voice. A reel with a different voice is worse than no reel.

- reference.wav: 10 to 20 seconds of my clean speech at reel energy, the voice every reel is cloned from. Required:
  there is no stock voice to use instead, so a missing reference.wav fails the preflight (section 3).
- reference_hook.wav (optional): the same voice with hook-level energy, used for hook beats by engines that have no
  energy setting.
- memo.*: the voice memo used to build voice.md.
- engine.txt: written by me after my blind test, one `key = value` per line, for example:

```
engine = turbo
python = C:/Users/<me>/venvs/chatterbox/Scripts/python.exe
seed = 7
```

- Build S8 on top of tools/voice.py, calling the engine through its own interpreter (the `python` line of
  engine.txt).

### 2.6 styles/sfx/: the sound effects memory map

My full sound effects pack lives in styles/sfx/: sorted subfolders (swooshes, UI sounds and more) plus a
miscellaneous folder where the file names describe the sound. It is shared by every style and every reel. You
cannot hear audio, so sounds are never generated or judged by ear at runtime: a script picks them from a map
built once, and picking costs zero tokens.

**pipeline/bin/build-sfx-map** builds the memory map:

1. **Measure every audio file** (wav, mp3, aif, aiff, ogg, flac), no model needed:
   - path, folder names and filename words as tags
   - duration, channels, sample rate
   - integrated loudness (LUFS), peak (dBFS), true peak, noise floor
   - onset (when the attack starts), peak time (the loudest moment), attack (onset to peak), tail (peak to -40 dB)
   - brightness (spectral centroid)
   - silence padding at the start and end, clipping, decode errors
2. **Classify whooshes by speed** from duration and attack: fast (about 0.35s or shorter, or a sharp attack),
   medium, slow (about 0.8s or longer, a gradual swell). Tune the thresholds on the actual pack and record them
   in DECISIONS.md.
3. **Classify unclear files by name** (the miscellaneous folder, ambiguous names): one batched call to the indexer
   model with each file's folder, filename and measured features (no audio). It assigns cue types and tags plus a
   confidence. Low-confidence files stay out of the pools until I approve them in overrides.txt.
4. **Loudness:** compute a gain for each file that brings its peak to a common reference (-12 dBFS), so sounds
   from different packs sit at the same level. Never modify the originals; keep normalized 48 kHz WAV copies
   in .cache/.
5. **Quality filter:** leave out clipped files, decode failures, files far too long for their cue type, and files
   with a high noise floor. List them in SFX-MAP.md with the reason.
6. **Pools:** for every cue type, rank the matching files by fit (category, duration window, attack shape) and keep
   the best 5 to 8.
7. **Write** styles/sfx/sfx-map.json (everything above) and styles/sfx/SFX-MAP.md (readable: counts per category,
   the pools, excluded files).
8. **Previews:** render styles/sfx/previews/<cue type>.wav, the pool's sounds spaced 1 second apart, with a text
   file listing them in order. Add a HUMAN_TODO for me to listen. To ban or pin a sound I write a line in
   styles/sfx/overrides.txt (`ban: path` or `pin: cue type: path`). The map respects overrides and keeps them on
   every rebuild.
9. **Rebuild** the map whenever the folder changes (a hash of file paths, sizes and dates).

**Cue types:**
- transition_slow: slow whoosh, for slower transitions (transitions of 400 ms or longer, or into calm beats)
- transition_fast: fast whoosh, for quick scene swaps
- attention: a random fast whoosh on a visual change that has no other sound, to keep attention up
- hero_enter: soft pop or click, only for hero cards and giant numbers, never for every element
- ui_click: a small UI click for chips, toggles and highlights changing state
- stamp: short thud or hit
- number: tick or short counter
- success: positive UI ding (checkmarks)
- typing: keyboard or UI typing (comment fields, terminals), trimmed to the typing duration
- negative: soft error or scratch (strike-throughs)
- hook_hit: impact with a whoosh, for the hook's set piece
- notification: message sound (the CTA's DM card)

Music is not in version 1. Later it follows the same pattern (a library with mood folders, a map, ducking under the
voice).

## 3. The video runner

- `bash run.sh [--once]`. The loop:
  1. take the first idea
  2. create its run, or resume an unfinished one
  3. run the stages in order (section 5)
  4. on export, drop or block: update ideas.txt and logs/history.txt
  5. take the next idea

  When ideas.txt has no idea: with --once, exit; otherwise check again every 120 seconds, forever.
- Startup preflight: claude, ffmpeg, ffprobe, python, node, gh, the Python packages, disk space, the voice reference,
  engine.txt's interpreter (2.5), style files, tokens.json, the sfx map. A missing hard dependency is a systemic
  failure: write logs/STOPPED.md with the exact fix and exit.
- Each idea gets runs/<YYYY-MM-DD_HHMM>_<slug>/ with state.json and one subfolder per stage
  (01-research/, 02-expansion/, ...).
  - A stage is done when its outputs validate against its schema and a .done marker exists.
  - On restart, the runner finishes the unfinished run first and skips stages that are already done.
  - Killing the runner or rebooting must never lose work or duplicate an export.
- One idea at a time.
- Every model call goes through ai() in pipeline/lib/ai.sh:
  - It runs `claude -p --model <model> --effort <effort> --output-format json`, adding `--resume <session id>` when
    continuing, `--json-schema` when the stage has a schema, and an explicit `--allowedTools` list for the stage.
  - Do not use `--bare`: bare mode does not use my subscription login.
  - Unattended permissions: `--permission-mode auto --permission-prompts none` (check `claude --help` and record
    the choice in DECISIONS.md).
  - It saves the raw output to runs/<id>/<stage>/calls/NNN.json and returns the session id and the result.
  - On failure it runs the classifier (section 4).
  - Model names and effort levels come from config.json, never from the code.
  - Note: claude -p currently draws from my Max subscription. Anthropic announced moving headless usage to separate
    credits, then paused that change. Keeping every call inside ai() means a billing change needs one edit.
- Permissions: model calls may not write to ideas.txt, library/, styles/ or exports/ (only the bash runner and its
  scripts touch those) and may not read .env (scripts that need keys read it themselves).
- Session A: stages S1, S2, S4 and S5 share one Claude session, continued with --resume, so the hooks are chosen with
  the research in context. If resuming fails, start a new session seeded with facts.md, expansion.md and the latest
  gate feedback.

## 4. Autonomy and error handling

Rule zero: the runner never stops for a single problem. It waits, retries, reviews, fixes, flags, drops or blocks
one idea, and moves on. It stops only for a systemic failure.

On any failed call or script, classify in this order:
1. Usage limit: wait (4.1). Never send a limit to the reviewer, because the reviewer would hit the same wall.
2. Transient (overloaded or 529, 5xx, timeouts, network resets, rate limits with retry-after): back off 60s, then
   4 minutes, then 16 minutes, then treat it as type 3.
3. Code or runtime error (non-zero exit, exception, output still invalid after the stage's one schema retry):
   review and fix (4.2).
4. Quality gate failure (the content is not good enough): this is not an error. The stage's own loop handles it
   (section 5 gives each loop and its cap).

### 4.1 Usage limits

- Detect in stdout, stderr and the JSON result: "hit your session limit", "hit your weekly limit", "limit reached",
  "usage limit", together with "resets"; also an epoch number after a "|".
- Parse every format:
  - time only: "resets 3:45pm", "resets 3pm (Europe/Rome)"
  - weekday and time: "resets Mon 12:00am"
  - date and time: "resets Nov 3, 10am"
  - a timezone in parentheses (default: the PC's local time, Europe/Rome)
  - an epoch
- Use GNU date, which ships with Git Bash. If the parsed moment is already past, add 1 day (time only) or 7 days
  (weekday).
- Wait until the reset plus 120 seconds, logging the target time in logs/limits.log, then retry the same call in the
  same session.
- Sleep in 60-second chunks and re-check the clock each chunk, so waits stay correct if the PC sleeps.
- If a limit is detected but nothing parses: sleep 30 minutes, then probe with the probe model ("reply ok") every 30
  minutes until it answers.
- Unit-test the parser with fake messages for every format above, including weekly.

### 4.2 Review and fix

1. **Error file.** On a code error, the runner writes runs/<id>/errors/E<n>.md containing:
   - the stage, command and exit code
   - the last 200 log lines and the list of input files
   - the stage's CONTRACT.md (inputs, outputs, invariants)
   - a git diff since the last successful run
   - all previous error and fix files for this stage
2. **Reviewer** (config: reviewer, Opus). It has read-only tools plus WebSearch and WebFetch, and reads E<n>.md and
   pipeline/knowledge/known-issues.md. It writes runs/<id>/fixes/F<n>.md containing:
   - the root cause
   - a class: pipeline bug, bad model output, environment problem, or external outage
   - the exact file changes and a command that verifies the fix
   - `auto_apply: yes` or `no`
3. **Fixer** (config: fixer, Sonnet). It may edit only pipeline/ and motion-lib/candidates/. It:
   - applies F<n>.md and runs the verify command
   - commits as `autofix(<stage>): <cause>`
   - appends one line to pipeline/knowledge/known-issues.md (symptom -> fix), so the next reviewer starts with that
     knowledge
4. **Restart.** The runner restarts the failed stage from its inputs. If the stage has a session, it resumes it with
   a short note saying what failed and what was fixed.
5. **Caps and escalation:**
   - Up to 3 review and fix cycles with the Opus reviewer, per stage per idea.
   - If the same normalized error signature (the message with numbers, paths and timestamps stripped, hashed) appears
     twice in a row, skip the remaining Opus cycles.
   - Then 1 escalation cycle with the escalation reviewer (Fable), fresh context, given every previous E and F file.
   - If that fails too, or the reviewer says `auto_apply: no` for something only I can fix (missing key, disk full),
     the idea is blocked: removed from ideas.txt, copied to logs/blocked.txt with the reason, run folder kept. The
     runner moves to the next idea.
6. **Systemic stop.** If the same error signature blocks 3 ideas in a row, or preflight fails, stop the runner and
   write logs/STOPPED.md with the diagnosis and the exact fix for me. This is the only way the runner stops by itself.

### 4.3 Logs

- logs/runner.log: the readable timeline (every terminal line from section 7, plus details).
- logs/status.txt: the latest status line, overwritten, so an interactive Claude Code session can answer "what is
  the runner doing?".
- logs/history.txt: `date | idea | exported N`, or `dropped: reason`, or `blocked: reason`.
- logs/limits.log: every limit wait with its target time.

## 5. Pipeline stages

Each stage folder has CONTRACT.md (inputs, outputs, invariants), prompt.md (the prompt template) and schema.json (its
JSON outputs). Every JSON output is validated. An invalid output gets one retry with the validation errors; after
that it counts as a code error.

### Editing order (the core of the edit)

1. **Voiceover first** (S8): the voice and its word timestamps are the timeline everything else snaps to.
2. **Then visuals** (S9 and S10), planned in three passes: animations, then text, then transitions. Then built and
   rendered as a silent draft.
3. **Then sound effects, only when the visuals are done** (S11): sounds attach to the events of the built visuals,
   not to the plan, so timing is exact.
4. **Then the review** (S12): every check on the complete draft. A fix goes back to the step that owns it, and every
   step after it runs again (a visual fix moves events, so S11 runs again).
5. **Then the final render and the export** (S13, S14).

### S1 Research (session A, model: research)
- Goal: get the facts right as of today. Not virality: I already validated the idea before writing it.
- Tools: WebSearch, WebFetch, Bash for the gh CLI (repo view, README, releases, stars, last commit) and for
  pipeline/bin/screenshot.
- Outputs in 01-research/:
  - facts.md: every claim with its source URL and the date checked. Primary sources first (official repo and docs,
    then the vendor's blog, then press, forums last).
  - numbers.json: stars, versions, prices, dates, each with its source.
  - assets/ plus assets.json: screenshots of the real pages (repo, docs, product), captured with Playwright at 1080px
    width, each with URL and date.
  - pitfalls: requirements, costs, what does not work.
  - "one specific true thing" candidates: the concrete number, result or demo the reel can stand on.
- Rules: never invent anything; if a key fact cannot be verified, say so; do not get around sites that block
  automated access.

### S2 Expansion (session A, model: research)
- Write 02-expansion/expansion.md, 500 to 1500 characters, containing:
  - the viewer's problem as one first-person sentence, and the solution
  - the share driver: a specific identity ("if you edit reels for clients") plus a takeaway worth forwarding
  - the comment keyword and its deliverable: from deliverables.txt, or a concretely described new one marked NEW
  - the one specific true thing
  - evidence lines pointing to facts.md

### S3 Idea gate (fresh session B, model: gate)
- Score 0 to 3, quoting the evidence:
  - **P**, problem to solution
  - **S**, share driver
  - **C**, comment trigger (keyword plus a realistic deliverable)
  - **F**, facts: every claim the reel will make is in facts.md, and the core fact is verified
- Pass: P, S and C at least 2, and F passes.
- P, S or C failing: go to S4, at most 2 rounds.
- F failing (the tool does not do what the idea assumes, it is deprecated, or the claims cannot be verified): drop
  immediately.
- Still failing after 2 angle rounds: drop.
- The angle must keep the idea's core topic. If the only working angle is a different topic: drop, and write the
  suggestion to logs/suggested-ideas.txt (never to ideas.txt).
- Dropping means: delete the idea from ideas.txt, and write a history line with the scores and the reason.
- Output: 03-gate/gate.json.

### S4 Angle research (session A resumed, model: research)
- Gets gate.json. Can research more. Rewrites expansion.md, then the idea goes back to S3.

### S5 Hooks (session A resumed, model: research)
- Inputs: library/.hooks.index.json, the stats file, and the vendor hooks.json (26 formulas, as extra shapes).
- Choosing templates: pick 12 to 20 templates from at least 3 families; prefer fits_problem_solution, unless the
  angle is a personal story; weight the choice by each template's win rate in the stats file once there is data
  (uniform at first).
- Writing each hook:
  - a spoken line (8 words or fewer, under 3 seconds at my words per minute)
  - an on-screen line (6 words or fewer)
  - every filled hook contains a concrete marker: a named tool, a number or a time
  - fill the blank naturally and fix grammar; rewrite any em dash as a comma
- Output: 05-hooks/hooks.json.
- Session A then writes 05-hooks/brief.md (2 to 3 thousand tokens: everything the script needs), and its job ends.

### S6 Hook judge (scripts plus fresh session C, model: judge)
1. Filter with the vendor hookscore.py: drop dealbreakers and scores under 50. If fewer than 4 hooks survive, S5
   regenerates once with the failures as feedback, then the judge continues with the best available.
2. Judge model, in about 3 calls: two full rankings with different shuffles (this cancels position bias), merged by
   Borda count, then pairwise comparisons of the top 4 in both orders, in one call. Criteria: stops the scroll, sets
   up the problem, credible, fits my voice.
3. Output 06-judge/judge.json: the winner (hook 1), the runner-up (hook 2, used for the alternate clip), and the
   reasons. Update the stats.

### S7 Script (fresh session D, model: script; cut pass: model cut)
- Inputs: brief.md, facts.md, hook 1, voice.md, pronunciations.txt, the style's beat map, the length rules in
  tweaks.md.
- **Structure:**
  1. hook, 0 to 2s, with the spoken line and the on-screen line written separately
  2. stake, 2 to 7s: the viewer's pain with a specific identity (this is the share driver)
  3. body: one idea per beat. Each beat has a type: number, tool, step, comparison, proof, mechanism, before-after or
     pain-payoff.
  4. payoff: deliver what the hook promised
  5. a single ask: the comment keyword, in a line that repeats a word from the hook, so the replay loops. No second ask.
- **Length:** 25 to 40 seconds; list and explainer videos 45 to 75 seconds (tweaks.md). Words = seconds x wpm / 60.
- **Two drafts**, each in a different tone chosen from: warning, insider, contrarian, calm expert, confession. The
  choice depends on the hook formula and the angle.
- **Two text tracks per beat:** display (captions and cards) and spoken (for TTS: numbers written out, pronunciations
  applied).
- **Cut pass** (cut model): delete about 20% of the words without losing a fact.
- **Checks, all scripted:**
  - vendor beats.py with my wpm: hook 3s or less, no beat over 4s, no 3 abstract beats in a row, loop present, target
    length
  - vendor humanize.py, then detect.py must PASS (overall 70 or more, no check under 55)
  - zero `{{placeholders}}`
  - every claim maps to facts.md (checks model)
  - one ask only, and all 3 requirements present
- **Pick:** a pairwise judge chooses between the two drafts ("would he say this out loud to a friend?"), with the
  voice.md excerpts as reference.
- **Loop:** up to 3 rewrite rounds with the failing checks as feedback. Hard failures still there after 3 rounds
  (facts, placeholders, a missing requirement): block the idea. Soft failures (detect score, timing within 15%):
  continue with a NEEDS REVIEW flag.
- Output: 07-script/script.json. Each beat has: type, display, spoken, emphasis words, and the on-screen card text
  (6 words or fewer).

### S8 Voiceover (no model)
- **Engine:** only the one in library/voice/engine.txt (2.5): turbo (Chatterbox Turbo), cloned from reference.wav,
  run through tools/voice.py with engine.txt's interpreter and settings. Use chatterbox original only if engine.txt
  names it. No qwen3-tts (GPU only). There is no fallback engine or voice: never switch voice or engine.
- **Generate beat by beat.** The hook gets higher energy, the body normal energy:
  - turbo has no energy setting, so hook beats are cloned from reference_hook.wav when it exists
  - chatterbox original: its exaggeration setting

  Stitch the beats with fixed gaps (config, 120 to 200 ms) and trim silences.
- **Align** with faster-whisper word timestamps into words.json: word, start ms, end ms, beat id. faster-whisper
  runs on CPU with compute_type int8 (no CUDA libraries).
- **Speakability:** compare each line's transcription with its spoken text (word error rate). Never switch voice or
  engine:
  - A line fails the check (word error rate over 3%): regenerate that line with a new seed, up to 3 times.
  - Still failing: regenerate the whole voiceover with a new seed, up to 2 times (keeps the delivery consistent).
  - Still failing: rewrite that line once through S7 in simpler words, then regenerate it.
  - Still failing: if the error rate is 8% or less, continue with a NEEDS REVIEW flag; above that, block the idea
    (logs/blocked.txt). Never voice it with anything else.
  - A line running more than 15% over its estimated time is also flagged for rewrite.
- **Engine failures:** the engine itself crashing or hanging is a code error: retries and the review and fix path of
  section 4.2, then block the idea. Never a different engine.
- **Loudness:** -14 LUFS integrated, true peak at most -1.5 dBTP (two-pass ffmpeg loudnorm).
- **Hook 2:** also generate its voice, for the alternate clip.
- **Speed:** expect about 1 to 3 minutes of generation per reel on this CPU. At M7, measure the real speed and record
  it in DECISIONS.md.
- Outputs: vo.wav, vo_hook2.wav, words.json, words_hook2.json.

### S9 Visual plan (fresh sessions, model: visual_director), in three passes

Shared inputs: script.json and words.json; style.md and tweaks.md (tweaks win), tokens.json, vocabulary.md; the
motion-lib catalog (each component's props, its sound events and a preview still); the golden reels (plan plus
contact sheet); the research assets.

1. **9a Animations** (09a-animations/plan.json): scenes and their components. Per beat: start and end ms snapped to
   word boundaries, the component (from motion-lib only) and its props, the entrance and exit motion, emphasis hits
   (word, ms, effect), the progress tracker's state (list items, or beats when there is no list), set pieces, an
   honesty label when the data shown is mock or sourced.
2. **9b Text** (09b-text/plan.json): every on-screen card's text (6 words or fewer), the caption chunks (1 to 4
   words) with their emphasis word, labels and tags, each placed inside tokens.json zones and timed to words.json.
3. **9c Transitions** (09c-transitions/plan.json): how each scene leaves and the next arrives, with its duration,
   following the style's transition rules (allowed types, frequency, hard cuts versus motion).

A validator script checks the merged plan against tokens.json:
- the first visual change happens before the style's limit
- the gap between visual changes never exceeds the style's maximum
- a minimum number of distinct components, and no component 3 times in a row
- each beat type uses only the components the beat map allows
- caption chunk rules, text zones, words per card
- real assets only for real claims: no invented UI values

An invalid pass gets one retry with the validator errors, then the review path.

### S10 Build visuals and draft render (model: builder, Opus; builder_escalation, Fable, for 3D-heavy plans or after 2 failed review rounds)
- A HyperFrames composition made from motion-lib components:
  - captions per the style: chunks of 1 to 4 words, gray turning to ink as each word is spoken, accent on the
    emphasis word
  - the progress tracker
  - tokens.json as CSS variables
  - 3D through the Three.js adapter, only where the style allows it and only with the WebGL backend that M9 found
    working in headless Chrome (recorded in DECISIONS.md). Keep 3D scenes light: low poly, few objects. If WebGL is
    not available, replace 3D beats with 2D components and flag NEEDS REVIEW.
- Every motion-lib component declares its sound events (for example card enter at frame 0, stamp landing at frame 3,
  typing from frame 5 to 40). The build exports 10-build/events.json: every event's absolute time in ms, its type, the
  component, the scene, and whether it is a scene change (with the transition's duration).
- A new component only when the plan needs one the library lacks. Write it to motion-lib/candidates/, use it in this
  reel only, and flag NEEDS REVIEW. Candidates join the library only with my approval.
- Also build the hook 2 alternate clip: the hook beat's visuals with hook 2's on-screen text and timing, 3.5 seconds
  at most.
- Render a silent draft at 540x960 (draft.mp4: half resolution, same timing and fps) for the next stages. Every
  review draft is 540x960; 1080x1920 is rendered only in S13.

### S11 Sound effects (no model; scripts pipeline/bin/mix-sfx)
1. **Assign cue types to events.json** (deterministic rules, randomness seeded per reel):
   - mandatory: hook_hit on the hook's set piece, notification on the DM card, stamp on stamps, typing on typing
     segments, success on checkmarks, negative on strike-throughs
   - scene changes: transition_slow when the transition lasts 400 ms or more or the next beat is calm (stake,
     pain, story); otherwise transition_fast
   - hero_enter on giant numbers and hero cards, at most 1 per scene; ui_click on chips and highlights
   - attention: when more than 6 seconds pass with no sound, add a fast whoosh on a visual change in that gap, at random
     intervals of 8 to 12 seconds, never in the first 2 seconds and never during the ask
   - density: at most 4 sounds per 10 seconds, never two within 250 ms, nothing on the hook's first word except
     hook_hit. When trimming, keep mandatory first, then scene changes, then hero, then attention.
2. **Pick files from sfx-map.json pools:** rotate within the pool, never the same file twice in a row, and avoid files
   used for the same cue in the last 2 reels (logs/sfx-usage.json).
3. **Place:** whooshes so their peak time lands on the event; everything else so its onset lands on it. Trim typing to
   its segment and trim tails that run into the next sound, with a 30 ms fade-out.
4. **Level:** the file's normalization gain from the map, plus the cue type's base gain from config. Every sound's peak
   sits at least 8 dB below the voice's peak around that moment.
5. **Verify accuracy and loudness** on the rendered sfx stem:
   - accuracy: onset detection finds every planned sound within 1 frame (33 ms) of its event (the peak for whooshes),
     and no unplanned sound
   - loudness: the 8 dB rule, the mix at -14 LUFS (plus or minus 1), true peak at most -1.5 dBTP
   - a failure is corrected automatically (offsets, gains) and verified again; if it persists, the review path
6. Outputs: 11-sfx/cues.json (event, cue type, file, time, gain), sfx_stem.wav, the mixed draft (draft_mixed.mp4), and
   11-sfx/sound-map.txt (one readable line per sound: time, cue type, file name, the visual event it sits on).
- If the sfx map is missing or empty, render voice only and add a NEEDS REVIEW flag.

### S12 Review and fix loop
- **Draft resolution.** Every draft reviewed here is 540x960 (half resolution, same timing); 1080x1920 is rendered
  only in S13. Scale every pixel-based check below to the draft resolution (zones, the right 230px, font sizes,
  positions and distances in the style conformance comparison).
- **Mechanical checks.** Puppeteer opens the composition and checks, at every beat and emphasis timestamp:
  - every text box is inside the zones in tokens.json (with the caption band exception from tweaks.md)
  - nothing in the right 230px of the lower half
  - only the fonts in tokens.json, at no less than its minimum sizes
  - no overlaps, nothing off-canvas, contrast at least 4.5:1
  - each emphasis lands within 80 ms of its word
- **Style conformance.** Run tools/analyze_refs.py on draft_mixed.mp4 and compare with styles/paper-cards/analysis:
  - visual-change median and maximum within the reference range (plus or minus 20%)
  - at least 90% of non-image pixels within ΔE 5 of a token color
  - accent share under the tweaks.md limit
  - loudness
- **Audio checks:** the S11 verification passes, and the voice is intelligible: transcribe the mixed draft and compare
  with the script (word error rate under 5%).
- **Edit review** (fresh session, model: qa, never the builder). It looks at:
  - a contact sheet with one still per beat
  - a 10 fps filmstrip of the hook and filmstrips of the transitions
  - 2 or 3 stills from the look references
  - sound-map.txt next to the scene list (does each sound fit its moment: slow whoosh on slow moves, nothing
    cluttering the voice)

  It scores 1 to 5: does frame 1 stop the scroll; hierarchy and legibility; does it match the look (would it sit on the
  same account); motion variety; sync with the voice; sound fit; nothing looks generic; the requirements are visible
  (the problem, the share line, the keyword). It passes when every score is at least 4. Every issue it lists carries a
  tag: [voice], [animation], [text], [transition] or [sfx].
- **Fix routing:** each issue goes back to the step that owns it (S8, 9a, 9b, 9c or S11), then S10, S11 and S12 run
  again as needed.
- **Loop caps:** at most 3 rounds with the Opus builder, then 2 rounds with the Fable builder. Still failing: export
  anyway, with NEEDS REVIEW and the review notes in the captions file. Never stop.

### S13 Final render
- Render with HyperFrames: 1080x1920, 30 fps, H.264 high profile, yuv420p, AAC 48 kHz, with the approved mix.
- Check with ffprobe: duration equals the voice within 0.2s, plus resolution, fps, codecs, audio present, loudness.
- Same for the hook 2 clip (with its own voice and sounds).

### S14 Caption and export
- Write the caption from the brief and the script: the first line is the hook, in 125 characters or fewer (where the
  feed cuts it off); one ask (the keyword); at most 5 hashtags.
- Run the vendor caption.py lint and humanize.py on it.
- Export as described in section 8.

## 6. Status lines (both runners print these)

Everything the runner prints goes to the terminal and to logs/runner.log, and the latest status line also overwrites
logs/status.txt. Format: `[HH:MM] TAG  details`. TAG is a fixed 6-character word so lines align. Use ANSI colors
(Git Bash's terminal supports them), and plain text when NO_COLOR is set or the output is not a terminal.

## 7. Terminal messages for the video runner

### Every 5 minutes, a heartbeat

```
[14:05] REEL   #idea 2/5 "Claude Code's frontend-design skill..." | <activity> | minute 12 | stage 3m10s | issues: 1 fixed, 0 open
```

- `#idea 2/5`: position in this session and ideas in the queue. The idea text is cut at 40 characters.
- minute: since this idea started. stage: since the current activity started.
- issues: errors and failed reviews for this idea, fixed and still open.

`<activity>` is one of:

| stage | activity text |
|---|---|
| S1 | researching facts |
| S2 | expanding idea |
| S3 | checking idea (gate) |
| S4 | finding a better angle (round 1/2) |
| S5 | picking hooks |
| S6 | judging hooks |
| S7 | writing script (draft 2/2, round 1/3), cutting script, checking script |
| S8 | generating voiceover (beat 4/9), regenerating line 4 (try 2/3), regenerating whole voiceover (try 1/2), rewriting line 4, aligning words |
| S9 | planning animations, planning text, planning transitions, validating plan |
| S10 | building visuals, rendering draft |
| S11 | adding sound effects (14 sounds), verifying sound sync and loudness |
| S12 | reviewing: mechanical checks, reviewing: style check, reviewing: edit review (round 1/5), fixing [text] issues (round 2, opus), fixing [animation] issues (round 4, fable) |
| S13 | rendering final video, rendering hook 2 clip |
| S14 | writing caption, exporting #7 |

These replace the activity whenever they apply:

```
waiting for usage limit (weekly) until Mon 00:02 (5h41m left)
retrying after temporary error (overloaded), next try in 4m (try 2/3)
error in S10: reviewing (cycle 1/3, opus)
error in S10: applying fix F2 (sonnet)
error in S10: escalated review (fable)
```

When there is no idea:

```
[15:20] IDLE   no ideas in ideas.txt, checking every 2 min (idle 14 min) | today: 3 exported, 1 dropped
```

### Event lines, printed immediately

```
[14:00] START  idea 2/5 "Claude Code's frontend-design skill..." -> runs/2026-10-31_1400_frontend-design
[14:03] STEP   researching facts done (2m51s) -> expanding idea
[14:09] GATE   passed (P3 S2 C3 F ok)
[14:09] ANGLE  gate failed (S1): finding a better angle, round 1/2
[14:23] FLAG   needs review: soft script check failed (detect 64)
[14:31] LIMIT  session limit hit, resuming at 15:47 (+2 min margin)
[15:49] RESUME limit reset, continuing: generating voiceover
[15:52] RETRY  temporary error (overloaded), retrying in 60s (try 1/3)
[15:58] ERROR  S10 building visuals: <one-line error>
[16:01] FIXED  S10: <cause> (commit 3f2a91c), restarting stage
[16:20] ESCAL  S10 still failing after 3 reviews, escalating to fable
[16:40] DONE   exported #7 -> exports/7/ (31 min, 2 issues fixed)
[16:40] DROP   idea "..." dropped: facts don't hold (<reason>). Removed from ideas.txt
[16:40] BLOCK  idea "..." blocked at S10: <reason>. Moved to logs/blocked.txt
[16:41] NEW    idea added from Claude Code (queue: 4)
[16:41] NEXT   idea 3/5 "..."
[17:02] STOP   systemic failure: <reason>. See logs/STOPPED.md
```

Also print a banner at startup (version, queue size, style, voice engine, the sfx map's file count) and a summary line
when the queue empties.

## 8. Exports

- The number is assigned at export time: N = the highest existing number in exports/ plus 1, so dropped or blocked
  ideas leave no gaps. Assemble everything in runs/<id>/export/ first, then move it into exports/N/ in one step.
- exports/N/N.mp4: the reel.
- exports/N/Ncaptions.txt: the captions file (format below).
- exports/N/Nhook2.mp4: the alternate hook clip, up to 3.5 seconds, using hook 2 in the same style.
- After the export: delete the idea from ideas.txt and write the history line.

Ncaptions.txt format:

```
CAPTION
<the caption, first line = the hook, ready to paste>

HASHTAGS
#one #two #three

COMMENT KEYWORD
<KEYWORD> -> DM them: <deliverable> <link>
<only when the deliverable doesn't exist yet: NEW deliverable to create before posting: ...>

HOOKS
N.mp4 uses: "<hook 1>"
Nhook2.mp4 uses: "<hook 2>"

NEEDS REVIEW
<only when flagged: what and why>

FACTS AND SOURCES
- <claim>: <url> (checked <date>)

RUN
runs/<id>
```

## 9. config.json

- **models**, one per role, with an effort level each (Claude Code model names and effort levels):
  - research, gate, judge, script, visual_director, builder, qa, reviewer: opus
  - cut, checks, fixer: sonnet
  - builder_escalation, reviewer_escalation: fable
  - indexer, probe: haiku
- **tts:** device cpu; the engine and its parameters (interpreter, seed, energy values) read from
  library/voice/engine.txt when it exists (engine.txt wins), no fallback engine; gap_ms.
- **voice:** wpm (from voice.md), loudness target.
- **sfx:** map path, base gain per cue type, max sounds per 10 seconds (4), minimum spacing in ms (250), minimum dB under
  the voice peak (8), attention interval (8 to 12 seconds), slow transition threshold (400 ms), sync tolerance (33 ms).
- **lengths:** default 25 to 40, list 45 to 75.
- **caps:** angle_rounds 2, script_rounds 3, review_rounds_opus 3, review_rounds_fable 2, error_review_cycles 3,
  escalation_cycles 1, systemic_block_streak 3.
- **runner:** poll_seconds 120, status_every_seconds 300, limit_margin_seconds 120, timezone Europe/Rome.
- **render:** draft_resolution 540x960 (S10 to S12; S13 renders 1080x1920).
- **timeouts:** one per step, in seconds, generous for a CPU-only PC (text to speech, alignment, renders, model
  calls), because heavy steps run slower than real time (section 0, Hardware).
- **style:** paper-cards. Plus paths.

## 10. Vendored tools

- Copy into pipeline/vendor/ig-agent-skill/, keeping the LICENSE (MIT), from
  github.com/Jakeschincariol/instagram-agent-skill: hookscore.py, beats.py, hooks.json, caption.py, humanize.py,
  detect.py, slop.json.
- Wrap them, do not change their behavior. beats.py gets --wpm from config. caption.py already enforces the 5-hashtag
  cap.

## 11. CLAUDE.md

Keep it short and current:
- what the project is
- the folder map
- how to start the runner, and where results appear
- the braces rule: when my message contains `{...}`, add it with pipeline/bin/add-idea.sh and confirm in one line
- when I ask what the runner is doing: read logs/status.txt and the end of logs/runner.log
- what is curated by me and must not be edited without asking: library/, styles/, ideas.txt (except through
  add-idea.sh)
- how to read logs/history.txt, logs/blocked.txt and logs/STOPPED.md
- the current build status (which milestone)

## 12. Milestones (one build batch each) and acceptance tests

- **M0 Plan.** Write PLAN.md (every milestone below: files it creates, its acceptance test, what it depends on),
  DECISIONS.md and CLAUDE.md. No code.
- **M1 Skeleton.**
  - Builds: folders, git, config.json, preflight, ideas.txt parsing, the lock, add-idea.sh, the test idea.
  - Test: parser fixtures (multi-line, CRLF, Italian accents, text outside braces); adding ideas concurrently while the
    runner deletes one loses nothing.
- **M2 Runner core and terminal output.**
  - Builds: the state machine with dummy stages, resume, export numbering, history, every message in sections 6 and 7
    (heartbeat every 5 minutes, events, idle, banner), logs/status.txt.
  - Test: kill the runner mid-stage, restart it, and it resumes the same stage; two dummy runs produce exports/1/ and
    exports/2/; in a fast test mode the heartbeat prints on schedule with the right fields.
- **M3 Error system.**
  - Builds: the classifier, limit parsing and waiting, the reviewer and fixer loop, escalation, blocking, the systemic
    stop.
  - Tests:
    - a fake `claude` placed first on PATH produces every limit format, and the runner computes the right wait (in a
      fast-forward test mode)
    - a dummy stage with a planted bug gets fixed by the reviewer and fixer, then passes
    - an unfixable error blocks the idea and the runner continues
    - 3 identical blocks in a row write STOPPED.md
- **M4 Research, expansion, gate, angle (S1 to S4).**
  - Test: the test idea produces facts.md with sources, an expansion of 500 to 1500 characters, and gate.json. A
    deliberately false idea fixture gets dropped with a reason, and its block disappears from ideas.txt.
- **M5 Profile and hooks (S5, S6).**
  - Builds: voice.md (from the memo, or a placeholder draft plus HUMAN_TODO), the hooks index and lint.
  - Test: S5 and S6 produce a winner and a runner-up for the test idea.
- **M6 Script (S7).**
  - Test: script.json passes every check for the test idea.
- **M7 Voiceover (S8).**
  - Builds: S8 on top of tools/voice.py, cloning, alignment, the word error rate gate, loudness.
    - When library/voice/engine.txt exists, use exactly its engine, interpreter and settings, and install nothing.
    - Otherwise install chatterbox-tts, CPU-only, in a virtual environment outside the project, and add a HUMAN_TODO
      asking me to write engine.txt.
    - Update the preflight to check only engine.txt's interpreter: it exists and can import its engine (a one-line
      import test).
  - Test, with only the engine in engine.txt: the test idea's script produces vo.wav and words.json in my cloned
    voice that pass every check; the failure ladder ends in a flag or a block, never in another voice or engine; the
    measured speed is recorded in DECISIONS.md.
- **M8 Sound effects memory map (2.6).**
  - Builds: build-sfx-map over styles/sfx/, sfx-map.json, SFX-MAP.md, the pools, previews, overrides.txt handling,
    HUMAN_TODO to listen to the previews.
  - Test: every audio file is either in the map or listed as excluded with a reason; every cue type has a pool of at
    least 3 sounds (or a HUMAN_TODO saying which cue types are short); a rebuild with an override keeps it.
- **M9 Motion library.**
  - Builds:
    - tokens.json
    - every component in vocabulary.md as a HyperFrames component with its declared sound events
    - a gallery page that plays each one
    - frame-matching against the reference filmstrips in styles/paper-cards/analysis
    - components that pass the frame-match go into motion-lib/, with a HUMAN_TODO for me to review the gallery
    - a golden reel built from the test idea, with a HUMAN_TODO for me to review it
    - a WebGL test for Three.js in headless Chrome on this PC: hardware ANGLE first (the integrated GPU), then
      SwiftShader software rendering. Record which works in DECISIONS.md. Keep 3D scenes light (low poly, few
      objects). If WebGL is not available, 3D beats are replaced with 2D components and flagged NEEDS REVIEW.
- **M10 Visual stages (S9, S10).**
  - Test: the three plan passes validate, the draft renders, events.json matches what is on screen.
- **M11 Sound effects pass and review loop (S11, S12).**
  - Test: on the test idea's draft, every sound lands within 1 frame of its event, loudness passes, the edit review
    runs, and a planted [text] issue routes back to 9b and the stages after it run again.
- **M12 Final render, caption, export, end to end (S13, S14).**
  - Test: the test idea produces exports/1/1.mp4, 1captions.txt and 1hook2.mp4, every ffprobe check passes, and the
    idea is gone from ideas.txt.
- **M13 Hardening.**
  - Test: 3 ideas back to back, unattended; a simulated limit in the middle of a run; the logs and status lines tell
    the full story.

## 13. Not in version 1

Posting to Instagram (I post manually from exports/); music; multiple accounts, each with its own voice (its own
reference and engine.txt), its own style folder and its own content, run by the same pipeline and chosen per idea;
series; FlashFX as a render target; processing ideas in parallel.
