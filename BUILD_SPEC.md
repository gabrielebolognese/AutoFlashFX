# BUILD_SPEC: Instagram reels autopilot

## 0. Mission and how the build works

You are building, inside this folder (instagramReels), a pipeline that turns a short video idea into a finished
Instagram reel with no human in the loop: fact research, idea expansion, hooks, script, voiceover, visuals
generated in code (motion graphics and 3D written as code, never AI video generation), sound effects, review,
render, export. A Git Bash runner processes ideas one after another, indefinitely, and stops on its own only for
a systemic failure (section 4).

Reels are problem-first, not ads: each reel solves one real problem for the viewer with the best solution available
(FlashFX, an external tool or GitHub repo, or a method with no product), chosen per reel in S2.

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

From M18 on (14.3). Before M18 the channel's folders sat at the root.

```
instagramReels/
  BUILD_SPEC.md  CLAUDE.md  PLAN.md  DECISIONS.md  CHANNELS.md
  build-runner.sh            builds the milestones (temporary)
  build/                     progress.md  HUMAN_TODO.md  M1/ M2/ ... (reports, reviews, fixes)
  run.sh                     the video runner: bash run.sh --channel <id> [--once] (14.6)
  config.json                engine settings: models, engines, caps, timeouts, paths (section 9)
  exports/                   every channel's finished videos: <id>-1/, <id>-2/ ... (section 8)
    <id>-N/project/          the editable Shorts Editor project (S15) (M21)
  channels/                  one folder per channel (14.3)
    flashfx/                 FlashFX: instagram-reels, problem-solution-reel
      channel.json           identity, platform, format, quota, config overrides (14.4)
      ideas.txt              the idea queue, I edit it (2.1)
      library/               everything I curate for this channel
        hooks.txt            my hook templates (2.2)
        profile/             account.md  voice.md  deliverables.txt  pronunciations.txt (2.3)
        voice/               engine.txt (the voice config) and memo.* (for building voice.md) (2.5)
        brand/               FlashFX brand kit: mark/ wordmark/ lockup/ reference/ palette.png BRAND.md brand.json
                             (2.7), curated by me, read-only at runtime
      styles/
        sfx/                 this channel's sound effects pack (2.6)
          sfx-map.json  SFX-MAP.md  overrides.txt  previews/  .cache/   (generated, except overrides.txt)
        paper-cards/         style.md  tweaks.md  vocabulary.md  tokens.json  refs/  analysis/ (2.4)
      motion-lib/            approved HyperFrames components, plus candidates/ and gallery/
      golden/                1 or 2 golden reels (plan + render), examples for the visual director
      runs/                  one working folder per idea (machine only)
      logs/                  runner.log  status.txt  history.txt  blocked.txt  suggested-ideas.txt  sfx-usage.json
                             editor-gaps.md (M21)
      .locks/                the runner lock and the ideas lock
    lifeofgabry/             Life of Gabry: youtube-shorts, scenario-story (14.10); the same layout, with
                             library/character/ (Gabry) and styles/gabry-2d/
  pipeline/
    lib/                     bash and Python libraries; paths.sh and paths.py are the only code that knows this
                             layout (14.5); heavy.sh (14.6); timeline/ (14.8)
    stages/                  the stage library: one folder per stage: run script, prompt.md, CONTRACT.md, schema.json
                             s15-project/ (the editable project, S15) (M21)
    formats/                 one folder per format: format.json, prompts/, template/ (14.7)
    platforms/               one folder per platform: platform.json and its exporter (section 8)
    schemas/                 channel, format, platform and timeline schemas
    bin/                     add-idea.sh, new-channel, migrate-channels, index-hooks, build-sfx-map, mix-sfx,
                             screenshot, runner-status, doctor, helpers
                             rebuild-project.sh  editor-stable.sh (M21)
    vendor/ig-agent-skill/   MIT scripts from Jakeschincariol/instagram-agent-skill, with its LICENSE (section 10)
    knowledge/known-issues.md   symptom -> fix lines, written by the fixer (4.2)
    tests/
  tools/analyze_refs.py      reference video analyzer
  logs/                      engine-wide only: limits.log  engine.log (14.6)
                             editor-capabilities.json  editor-upgrade.json  editor-gaps-all.md (M21)
  .locks/                    global locks: heavy.lock  editor.lock  limit.json (14.6)
```

Git: a repo exists. Track code, channel.json, ideas.txt, the text files in each channel's library/ and styles/,
motion-lib/, the golden plan files, and the FlashFX brand kit (its PNGs included). Ignore /exports/, /logs/,
/.locks/, .env, and the channel rules of 14.3: channels/*/runs/, channels/*/logs/, channels/*/.locks/,
channels/*/library/voice/* with !channels/*/library/voice/README.txt, channels/*/library/character/photos/,
channels/*/styles/*/refs/, channels/*/styles/*/analysis/, the audio files, .cache/ and previews/ of
channels/*/styles/sfx/, and the generated files of motion-lib/ and golden/ under channels/*/. Add .gitattributes so
*.sh always uses LF line endings.

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

- account.md: who the account is for, the audience's problems, topics in and out, what I sell, the Brand section
  (pointers into library/brand/, 2.7), and the content strategy ("Content strategy": the problem-first rules and the
  balance target between FlashFX, external tools and methods).
- voice.md: built from the template in the instagram-agent-skill repo (templates/voice.md): who I am, what I sound
  like, my positions, off limits, proof I can use, how I promote, the ask. Plus 3 to 5 verbatim excerpts of my real
  speech and my measured words per minute. Build it from library/voice/memo.* (a 5 to 10 minute voice memo,
  transcribed with faster-whisper). Keep my real English (I am not a native speaker): fix only real errors, never
  polish my phrasing into native idioms. If there is no memo yet, draft it from the template with clear placeholders
  and add a HUMAN_TODO.
- deliverables.txt: one per line, `KEYWORD | what they get | link`, or `to create` instead of a link.
- pronunciations.txt: one per line, `word = how to say it`, for example `FlashFX = flash F X`.

If a profile file is missing at runtime, continue with defaults and add a NEEDS REVIEW flag to the export.

These files are mine: rebuilding them (pipeline/bin/build-voice-profile --force) keeps every section I wrote by
hand (account.md's Brand and Content strategy, voice.md's How I promote and the FlashFX spelling line) and only
refills the generated parts.

### 2.4 styles/paper-cards/

- style.md is the look contract, tweaks.md overrides it, vocabulary.md lists the components to build.
- Derive tokens.json from style.md plus tweaks.md: colors, fonts, type scale, zones, margins, border and shadow
  sizes, motion timings, caption rules, pacing limits. Regenerate it whenever either file's hash changes.
  Validators and checks read tokens.json and never hardcode style numbers.
- tokens.json also holds `motion` and `energy` (Motion and energy rules E9). (M14)
- All of this is read-only at runtime.

### 2.5 library/voice/

The reels use a Kokoro stock voice, af_bella. There is no cloning: exactly one voice per reel, and no fallback
voice. tools/voice.py already does text in, audio out with Kokoro, including the silence tightening (function
tighten) and the breath after the first paragraph (the hook).

- engine.txt: the voice config, written by me, one `key = value` per line:

```
engine = kokoro
python = C:/Users/there/venvs/kokoro/Scripts/python.exe
voice = af_bella
lang = a
speed = 1.0
silence_threshold_db = -40
min_pause_s = 0.3
keep_pause_s = 0.1
breath_after_hook_s = 1.0
```

  Every voice setting comes from this file. The preflight (section 3) checks that its interpreter exists and can
  import kokoro.
- engine-puck.txt: the same format with voice am_puck, saved for a future video type. Not used in version 1.
- memo.*: the voice memo used to build voice.md (my own speech, for how I write, never for the audio).
- Build S8 on top of tools/voice.py (its Engine class and tighten function), calling the engine through its own
  interpreter (the `python` line of engine.txt).

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

### 2.7 library/brand/: the FlashFX brand kit

The reels go to the FlashFX brand account. library/brand/ holds the FlashFX brand kit, extracted from the official
brand guide (FlashFX Brand ID 2026) as trimmed, transparent PNGs: mark/ (the bolt in five versions, plus
avatar-dark.png), wordmark/, lockup/ (bolt plus wordmark), palette.png and reference/ (8 guide pages). It is curated
by me and read-only at runtime: never modify, regenerate or redraw these files.

- BRAND.md: the rules (the name's spelling, which file on which background, clear space, minimum sizes, the never
  list, and the brand colors and fonts, which matter only for logo placement and FlashFX product depictions).
- brand.json: the same kit as data: colors (primary and secondary), the signature gradient, fonts, defaults, the
  reel rules, and one entry per logo asset with path, type (mark, wordmark, lockup, avatar), variant, width, height,
  use_on (light, dark or both), its visible content box and the bolt's height in the file. Logo files come only
  from brand.json.
- Where the brand appears in reels: styles/paper-cards/tweaks.md, section "Branding (FlashFX account)". The reel
  style does not change: no brand colors or fonts go into tokens.json, and FlashFX branding appears only as these
  logo files.

## 3. The video runner

- `bash run.sh [--once]`. The loop:
  1. take the first idea
  2. create its run, or resume an unfinished one
  3. run the stages in order (section 5)
  4. on export, drop or block: update ideas.txt and logs/history.txt
  5. take the next idea

  When ideas.txt has no idea: with --once, exit; otherwise check again every 120 seconds, forever.
- From M18 on: `bash run.sh --channel <id> [--once]` runs one channel (14.6). Every path in this section is inside
  channels/<id>/ (14.3), the stage order comes from the channel's format (14.7), and runners of different channels
  may run at the same time (heavy steps take turns, usage limits are shared, 14.6).
- Between ideas, never during a run: advance the stable editor copy and run the capability upgrade when the (M21)
  editor's capabilities changed (S15). run.sh also keeps the stable copy's server on port 5310 running. (M21)
- Startup preflight: claude, ffmpeg, ffprobe, python, node, gh, the Python packages, disk space, engine.txt and its
  interpreter importing kokoro (2.5), style files, tokens.json, the sfx map, library/brand/brand.json and every file
  it lists (2.7). A missing hard dependency is a systemic failure: write logs/STOPPED.md with the exact fix and exit.
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
- logs/history.txt: `date | idea | solution | exported N`, or `dropped: reason`, or `blocked: reason` in place of
  `exported N`. solution is the reel's solution type (flashfx, external or method; `-` when the idea ended before S2
  chose one), so S2 can see the balance.
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
6. **Then the editable project** (S15): built from the final composition after the export is assembled; it never (M21)
   changes the MP4. (M21)

### Motion and energy rules (M14 to M16)

Why: the reels built through M13 copied the references' individual moves (enters, pops, count-ups, scene changes) and
their rhythm (new motion starts about 1.5 times a second, as in the references), but not their energy. Measured on
the M13 reel against the two look references: 16% of frames carry medium or big motion against 55 to 64%; the
middle of the screen moves 15% of the time against 58 to 74%; 1.2% of the pixels change per frame against 4.6 to
4.9%. In the references the content itself keeps moving: video plays inside window cards, numbers count, code types,
cards fan out and tilt, and nothing stops between events. These rules make energy a requirement that the pipeline
builds (M14, M15), plans (M16), measures and fixes (M16). They hold for FlashFX's format (problem-solution-reel) and
its styles; the style supplies the values (fonts, sizes, colors, speeds) through tokens.json. They do not apply to
other formats: Life of Gabry (14.10) follows only its own style bible, and nothing of this section transfers to it.
M14 builds E0, E1, E2, E5, E6 and E7 in the motion library; M15
builds E3 and E4; M16 builds E8 and E9 in the director, the new components, the golden reel and the review loop.
Earlier milestones are not reviewed against this section.

**E0. Energy, measured.**
- `pipeline/lib/review/energy.py` measures a video as a whole and scene by scene (scene times from the plan): 30 fps,
  a 108x192 grayscale copy, and for every frame the mean absolute change against the previous frame (0 to 255). A
  frame is frozen below 0.05, subtle from 0.05 to 0.6, medium from 0.6 to 4, big from 4.
- The measures: the moving share (medium plus big frames); the middle-band moving share (the middle third of the
  screen, where the hero content sits); the pixels changing per frame (the share of pixels that change by more than 8);
  the share of time inside still stretches of 1 s or more; the longest still stretch.
- It is calibrated once on the style's reference videos (styles/<style>/refs/) and the reference numbers are written
  to styles/<style>/analysis/energy.json. The targets are 70% of the look references' median, kept in tokens.json
  (energy) and overridable by an "Energy" line in tweaks.md. For paper-cards: moving share at least 42%, middle band
  at least 46%, at least 3.3% of the pixels changing per frame, still stretches at most 15% of the time, the longest
  at most 2 s.
- The M13 reel (build/M13/rerun/1.mp4) measures 16%, 15%, 1.2%, 29% and 2.8 s: it fails every target, as it should.

**E1. The life of every element: main animation, inertia, hold, exit. Nothing ever stops moving.**
- An animation is not 0.5 s long; it lasts 2 to 4 s and more. The 0.3 to 0.6 s everyone sees as "the animation" is
  only its main part. Every element on screen (cards, chips, icons, logos, images, numbers, caption words and caption
  groups) lives through four phases:
  1. **Main animation** (0.3 to 0.6 s): the visible event, for example a pop in, a fly-in or a zoom in. Its opacity and
     position frames still follow the style's measured enters (style.md Motion: opacity over 5 frames, position over
     8 frames, the pops' overshoot).
  2. **Inertia** (the next 2 to 4 s): the motion does not stop when the main animation lands. It carries on in the same
     direction and slows down, like an object with mass: a card that rose keeps rising, a card that zoomed in keeps
     growing (for example scale 1.00 to 1.04), a card that turned keeps settling its rotation. The inertia follows a
     decelerating ease-out (cubic or quart) whose speed never reaches zero.
  3. **Hold**: until the element leaves, it keeps a slow, steady motion in the same direction: a drift of 2 to 8 px per
     second, a parallax rotation of 0.2 to 0.6 degrees per second, or a scale creep of 0.2 to 0.5% per second. Three
     hold levels (calm, normal, lively) set the speed; the director picks one per scene.
  4. **Exit** (0.2 to 0.4 s, ease-in), or the scene change carries the element out.
- Rule: no visible element is ever static. At every frame each element moves at least at the calm hold speed, either
  through its inertia or through its hold (measured from the composition, E9). Elements that form a group (a card and
  its children, a caption group) hold in one shared direction.

**E2. Combined animations, never a single property.**
- A main animation combines at least two properties at once, never a bare pop or a bare fade: for example a zoom in
  (scale 0.85 to 1.0, or 1.15 to 1.0 from a close start) together with a 3D parallax rotation (rotateY or rotateX from
  8 to 15 degrees down to 0 to 2, inside a perspective of 1200 to 1600 px) and a short move.
- The curve: the main animation uses an ease-in-out of power 3 or 4 (GSAP power3.inOut or power4.inOut: it starts
  slowly, does the middle fast), and the inertia then continues on a decelerating ease-out, so the move ends slower
  and slower and never stops dead.
- The rotation is slightly slowed: it lags the scale and the position by 2 to 4 frames and settles last.
- The style's own enter timings (E1 step 1) stay the reference for the opacity and position frames; the combined
  properties ride on top of them.

**E3. Captions: two modes, always moving.**
- **Word mode** (normal talk): one word at a time, on its spoken word time (words.json), in the style's caption font
  and size. The emphasis words (script.json's emphasis list) change font and size: the style's emphasis font
  (paper-cards: Instrument Serif italic) at 1.25 to 1.5 times the caption size, with the style's accent box where the
  style has one. Every word drifts while it is on screen (it rises 8 to 16 px over its life, or turns 2 to 4 degrees of
  parallax rotation) and never stands still.
- **Group mode** (the captions become the graphic): used when the voice says something important (the hook, a key
  claim, a number, the payoff, the line before the ask) and above all when the beat has no clear or relevant graphic to
  show. A group of 2 to 6 words fills the hero zone as kinetic typography:
  - **Different fonts:** at least 3 fonts in any group of 3 words or more (paper-cards: Inter Tight at a heavy weight,
    Instrument Serif italic, and Caveat or Space Grotesk; tokens.json lists the caption fonts).
  - **Different sizes and lines, never one line:** the anchor word (the most important one) is the biggest, at 2 to 3
    times the caption size. The other words stack beside it so that their lines together match the anchor's height.
    Example, "the quick brown fox": "the" is big; "quick" sits right of it at half the size of "the", top aligned;
    "brown" sits under "quick" at the same size, so "quick" plus "brown" are as tall as "the"; "fox" goes on the next
    line, offset to one side; at least three different fonts across the four words.
  - **Never symmetric:** lines start at different x, there is no centered stack of equal lines, and the group's
    bounding box leans to one side and leaves air on the other.
  - **Timing and motion:** each word appears on its spoken word time with the combined animation of E2 at word scale
    and stays until the group leaves. The group moves as one block in one direction (a slow rise of 20 to 40 px over
    its life, or a parallax rotation of 3 to 6 degrees), and leaves together.
  - No word in a group is smaller than the caption size.
- One mode at a time: word mode whenever any other text is on screen (E4); group mode only in beats whose hero zone
  holds no other text.
- A deterministic layout engine (`pipeline/lib/visual/kinetic.py`) places every group from its words, their roles
  (anchor, secondary, connector) and the zone, so the result fits the text zones and the right-rail rule. The
  director chooses the mode and the anchor; the engine places the words; no model positions words by hand.

**E4. Text discipline: graphics first.**
- The goal is graphics and animation, not text. On-screen text (cards, labels, chips, code) appears only when strictly
  necessary; an icon, a number, an image, a logo or a motion that shows the idea comes first. Cut text wherever a
  graphic can carry the meaning.
- At most 100 characters of non-caption text on screen at any moment (every visible card, label, chip and code line
  together).
- No text on a graphic is smaller than the caption font size (paper-cards: the 67 px caption size at 1080 wide). A
  graphic that would need smaller text needs less text.
- When a graphic carries text, the captions are in word mode, never in group mode.

**E5. Edges: the frame is a window, not a box.**
- Animations must not look confined by the frame. At the very edges, above all the left and right sides, a filler
  layer of slow elements sits partly behind the borders (30 to 70% of each element outside the frame): soft cards,
  chips, thumbnails, shapes, dots or stars in the style's palette, behind the content and quieter than it (lower
  contrast or opacity, smaller motion).
- They are slow (at most 20 px per second, moving with a parallax slower than the content), change little through the
  reel (the same set drifts; it may be swapped at the major scene changes), carry no text, and never cover a text zone
  or the hero element.
- The references show the effect: tilted cards and thumbnails running off the sides, stars drifting off frame.

**E6. The center: clean, but deep.**
- The center holds one clear idea at a time, uncluttered, yet with depth: a 2.5D parallax scene (layers at different
  depths in a CSS 3D space under a slowly moving camera, each layer moving at its own speed) or a 3D icon (a low-poly
  object turning slowly).
- HyperFrames does both on this PC, so no other renderer is needed: CSS 3D transforms (perspective, rotateX, rotateY,
  translateZ, preserve-3d) render in the headless Chrome that draws every frame, and Three.js scenes run through the
  hf-seek adapter on the WebGL backend M9 found (motion-lib/webgl.json: hardware ANGLE on the AMD GPU, SwiftShader as
  the fallback). 3D icons are built in code: Three.js objects from extruded SVG paths and primitives (never generated
  images or video), or, without WebGL, CSS-extruded icons (an SVG repeated in 8 to 16 depth layers).
- 3D stays light (low poly, few objects, one 3D object in focus at a time) so the CPU renders keep their timeouts.

**E7. Background life.**
- The paper canvas carries an ambient layer like the look references: floating stars, dots and small clouds in the
  style's palette, with a slow drift and twinkle, seeded per reel, never on a text zone.
- The mascot idles in every scene it is in (a bob, a blink, a wiggle of its prop), on top of E1's hold.

**E8. Composition and camera.**
- The hero content fills 70 to 85% of the frame width; every scene layers at least 2 elements (the hero plus a
  supporting chip, badge, stack or number); empty paper in the hero zone lasts at most 1 s.
- A camera move (a push-in, a pull-back, a pan, or a slow orbit of the 2.5D scene) in at least 1 of every 3 scenes.
- Scene changes vary: no transition type more than 3 times in a reel.
- The hook moves from frame 0: its hero element is moving by frame 4, never empty paper waiting for it.
- Lists and groups enter as stacks, fans or grids with staggers, not one card after another in the same spot.
- Real motion inside the content wherever it exists: screen recordings of the real pages (S1), typing, counting, a
  cursor that moves and clicks, a playhead that runs, bars that fill.

**E9. How it is enforced.**
- tokens.json gains `motion` (the phases' durations, the eases, the hold levels' speeds, the 3D angles and
  perspective, the edge layer's speed and coverage, the caption modes' fonts and size ratios) and `energy` (E0's
  targets), with this section's values unless tweaks.md overrides them.
- The motion library implements E1, E2, E5, E6 and E7 once, in a shared helper (motion-lib/assets/pc-motion.js) that
  every component uses; no component hand-rolls its own phases or curves.
- The plan validator (S9) checks: every scene keeps a moving element in the hero zone; caption modes and E4's limits
  (characters, sizes, word mode under text); E8's fill, layers, camera frequency, transition variety and the hook's
  frame 0.
- S12 runs the energy check (E0, whole reel and per scene) first and routes the failing scenes to 9a with their
  numbers as [animation] issues; its mechanical checks add "no element static for more than 0.5 s" (transforms
  sampled from the composition), E4's character count and minimum text size, and the edge layer's presence; the edit
  review scores energy explicitly.
- Early stop: when two review rounds in a row end with the same scores and the same issues, the loop stops and the
  reel exports with NEEDS REVIEW instead of repeating itself.

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
  - solution candidates: the best available ways to solve the idea's problem (external tools and GitHub repos with
    name and URL, methods with no product), each with its sources. When the idea names its solution, research that
    one first.
  - recordings: a 5 to 8 s scroll video of each key page (Playwright, 1080 wide) next to its screenshot, for the (M16)
    video and window cards (Motion and energy rules E8). (M16)
- Rules: never invent anything; if a key fact cannot be verified, say so; do not get around sites that block
  automated access.

### S2 Expansion (session A, model: research)
- Write 02-expansion/expansion.md, 500 to 1500 characters, containing:
  - the viewer's problem as one first-person sentence, and the solution
  - the solution decision with its reason: `flashfx`, `external` (name and URL from facts.md) or `method` (also
    written to 02-expansion/solution.json: type, name, url, reason, for the later stages and the history line)
  - the share driver: a specific identity ("if you edit reels for clients") plus a takeaway worth forwarding
  - the comment keyword and its deliverable, following the solution: FLASH for FlashFX, LINK for an external tool
    or repo (the deliverable is its link), otherwise the deliverable that fits, from deliverables.txt or a
    concretely described new one marked NEW
  - the one specific true thing
  - evidence lines pointing to facts.md
- Choosing the solution follows account.md's content strategy:
  - if the idea names the solution, use it
  - FlashFX only when it genuinely solves the problem and every FlashFX claim is in voice.md "Proof I can use"
  - otherwise the best solution in facts.md: an external tool or repo, or a method
  - read the recent lines of logs/history.txt (their solution types) to keep the balance target in account.md
  - when account.md has no content strategy yet, use these rules with no balance target

### S3 Idea gate (fresh session B, model: gate)
- Score 0 to 3, quoting the evidence:
  - **P**, problem to solution
  - **S**, share driver
  - **C**, comment trigger (keyword plus a realistic deliverable)
  - **F**, facts: every claim the reel will make is in facts.md (claims about FlashFX: in voice.md "Proof I can
    use"), and the core fact is verified
  - **H**, honesty (pass or fail): the chosen solution really solves the stated problem, and FlashFX is not forced
    (it fails when FlashFX is chosen where it does not solve the problem, or with a claim missing from "Proof I can
    use")
- Pass: P, S and C at least 2, F passes and H passes.
- P, S or C failing: go to S4, at most 2 rounds.
- H failing: not a drop. Go to S4 to pick the better solution, inside the same 2 angle rounds.
- F failing (the tool does not do what the idea assumes, it is deprecated, or the claims cannot be verified): drop
  immediately.
- Still failing after 2 angle rounds: drop.
- The angle must keep the idea's core topic. If the only working angle is a different topic: drop, and write the
  suggestion to logs/suggested-ideas.txt (never to ideas.txt).
- Dropping means: delete the idea from ideas.txt, and write a history line with the scores and the reason.
- Output: 03-gate/gate.json.

### S4 Angle research (session A resumed, model: research)
- Gets gate.json. Can research more. Rewrites expansion.md, then the idea goes back to S3.
- When H failed, it decides the solution again with the S2 rules (the better solution for the problem, and the
  keyword that follows it) and rewrites solution.json.

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
- Inputs: brief.md, facts.md, solution.json, hook 1, voice.md, pronunciations.txt, the style's beat map, the length
  rules in tweaks.md.
- **The solution:**
  - when the solution is not FlashFX, the script does not mention FlashFX
  - when it is FlashFX, show it solving the problem with no ad language (no pitch, no hype), the way any other tool
    would be shown
  - never say or imply the reel itself was made in FlashFX (reels are rendered with HyperFrames)
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
  - every claim maps to facts.md, or to voice.md "Proof I can use" for FlashFX (checks model)
  - one ask only, and all 3 requirements present
  - the solution rules: no FlashFX mention unless the solution is flashfx (scripted); no ad language and nothing
    implying the reel was made in FlashFX (checks model)
- **Pick:** a pairwise judge chooses between the two drafts ("would he say this out loud to a friend?"), with the
  voice.md excerpts as reference.
- **Loop:** up to 3 rewrite rounds with the failing checks as feedback. Hard failures still there after 3 rounds
  (facts, placeholders, a missing requirement, a broken solution rule): block the idea. Soft failures (detect
  score, timing within 15%): continue with a NEEDS REVIEW flag.
- Output: 07-script/script.json. Each beat has: type, display, spoken, emphasis words, and the on-screen card text
  (6 words or fewer).
- Each beat also carries its importance (hook, key claim, number, payoff, pre-ask or normal), which picks the (M15)
  caption mode (Motion and energy rules E3); card texts are written for E4 (graphics first). (M15)

### S8 Voiceover (no model)
- **Engine:** only the one in library/voice/engine.txt (2.5): kokoro with voice af_bella, called through engine.txt's
  interpreter, building on tools/voice.py (its Engine class and tighten function), with engine.txt's settings.
  Kokoro is deterministic (seeds change nothing) and fast on CPU. Exactly one voice per reel and no fallback engine
  or voice: never switch voice or engine.
- **Pronunciations first:** apply pronunciations.txt to the spoken text before generating: a respelling, or Kokoro's
  inline phoneme syntax `[word](/phonemes/)` when a respelling is not enough.
- **Generate beat by beat.**
- **Silence tightening, per beat, before alignment:** every pause of min_pause_s or longer (below
  silence_threshold_db) is shortened to keep_pause_s; shorter pauses (commas, the tiny stops inside words) stay.
  Join the beats with keep_pause_s, except after the hook beat, where the gap is breath_after_hook_s. Leading silence
  0.05s, trailing 0.2s.
- **Align** the tightened audio with faster-whisper word timestamps into words.json: word, start ms, end ms, beat id,
  so the timestamps match the audio the reel uses. faster-whisper runs on CPU with compute_type int8 (no CUDA
  libraries). Never tighten after alignment.
- **Speakability:** compare each line's transcription with its spoken text (word error rate). Never switch voice or
  engine:
  - A line fails the check (word error rate over 3%): fix the pronunciation of the misheard words (a respelling or
    inline phonemes, applied to this reel's spoken text; pronunciations.txt itself is mine and never edited) and
    regenerate that line.
  - Still failing: rewrite that line once through S7 in simpler words, then regenerate it.
  - Still failing: if the error rate is 8% or less, continue with a NEEDS REVIEW flag; above that, block the idea
    (logs/blocked.txt). Never voice it with anything else.
  - A line running more than 15% over its estimated time is also flagged for rewrite.
- **Engine failures:** the engine itself crashing or hanging is a code error: retries and the review and fix path of
  section 4.2, then block the idea. Never a different engine.
- **The hook breath** is silence in the audio, never a static frame on screen: S9 fills it with motion (9a).
- **Loudness:** -14 LUFS integrated, true peak at most -1.5 dBTP (two-pass ffmpeg loudnorm).
- **Hook 2:** also generate its voice, for the alternate clip (same voice, same tightening).
- **Speed:** Kokoro generates a reel in well under a minute on this CPU; alignment takes longer. At M7, measure the
  real speed and the voice's words per minute after tightening, record both in DECISIONS.md, and write the pace to
  config.json voice.wpm (S5 and S7 time the hooks and the script with it).
- Outputs: vo.wav, vo_hook2.wav, words.json, words_hook2.json.

### S9 Visual plan (fresh sessions, model: visual_director), in three passes

Shared inputs: script.json and words.json; style.md and tweaks.md (tweaks win), tokens.json, vocabulary.md; the
motion-lib catalog (each component's props, its sound events and a preview still); the golden reels (plan plus
contact sheet); the research assets; library/brand/brand.json and the reel's solution (02-expansion/solution.json).

Every pass follows the Motion and energy rules: 9a plans E1, E2 and E5 to E8 (the hold level of each scene, the (M16)
combined main animations, the camera, the layers, the edges, the depth at the center); 9c varies the transitions (M16)
(E8). (M16)
9b plans E3 and E4: the caption mode of each beat, each group's words and anchor, and the text budget. (M15)

1. **9a Animations** (09a-animations/plan.json): scenes and their components. Per beat: start and end ms snapped to
   word boundaries, the component (from motion-lib only) and its props, the entrance and exit motion, emphasis hits
   (word, ms, effect), the progress tracker's state (list items, or beats when there is no list), set pieces, an
   honesty label when the data shown is mock or sourced. The hook breath (S8: breath_after_hook_s of silence after
   the hook beat) is never a static frame: the hook's set piece or the first scene change lands inside it.
2. **9b Text** (09b-text/plan.json): every on-screen card's text (6 words or fewer), the caption chunks (1 to 4
   words) with their emphasis word, labels and tags, each placed inside tokens.json zones and timed to words.json.
3. **9c Transitions** (09c-transitions/plan.json): how each scene leaves and the next arrives, with its duration,
   following the style's transition rules (allowed types, frequency, hard cuts versus motion).

**Branding**, placed in 9a following tweaks.md "Branding (FlashFX account)" (2.7):
- the CTA beat always gets the FlashFX DM notification card (sender "FlashFX", mark/avatar-dark.png as its round
  avatar) and the FlashFX lockup on the end card
- FlashFX logos anywhere else only when the reel's solution is FlashFX (a run without solution.json counts as not
  FlashFX)
- the brand slot follows the solution: the FlashFX bolt, the tool's logo from the research assets, or a neutral icon
  from the style when there is none (style version 2 has no tracker: its brand slots are the hook's kicker mark,
  logo tiles and logo badges)
- logo assets come only from brand.json, with the variant chosen by the surface it sits on: its use_on must match
  (light: paper and surface cards; dark: ink)

A validator script checks the merged plan against tokens.json:
- the first visual change happens before the style's limit
- a visual change lands inside the hook breath
- the gap between visual changes never exceeds the style's maximum
- a minimum number of distinct components, and no component 3 times in a row
- each beat type uses only the components the beat map allows
- caption chunk rules, text zones, words per card
- real assets only for real claims: no invented UI values
- branding: the CTA has the DM avatar and the lockup; no FlashFX asset outside the CTA unless the solution is
  flashfx; every logo path is in brand.json and its use_on matches its surface

An invalid pass gets one retry with the validator errors, then the review path.

### S10 Build visuals and draft render (model: builder, Opus; builder_escalation, Fable, for 3D-heavy plans or after 2 failed review rounds)
- A HyperFrames composition made from motion-lib components:
  - captions per the style: chunks of 1 to 4 words, gray turning to ink as each word is spoken, accent on the
    emphasis word
  - from M15 the captions follow Motion and energy rules E3 instead: word mode and group mode, never chunks (M15)
  - every component's phases, curves, edges, background and depth come from motion-lib/assets/pc-motion.js (M14)
    (Motion and energy rules E1, E2, E5 to E7) (M14)
  - the progress tracker
  - tokens.json as CSS variables
  - 3D through the Three.js adapter, only where the style allows it and only with the WebGL backend that M9 found
    working in headless Chrome (recorded in DECISIONS.md). Keep 3D scenes light: low poly, few objects. If WebGL is
    not available, replace 3D beats with 2D components and flag NEEDS REVIEW.
- Every motion-lib component declares its sound events (for example card enter at frame 0, stamp landing at frame 3,
  typing from frame 5 to 40). The build exports 10-build/events.json: every event's absolute time in ms, its type, the
  component, the scene, and whether it is a scene change (with the transition's duration).
- Logos are placed as image files from library/brand/ (the paths in brand.json), never redrawn, retyped, recolored,
  distorted or given effects (outline, shadow, glow, filters); their aspect ratio is locked (sized from brand.json's
  width and height, object-fit contain). The card around a logo keeps the style's shadow; the logo itself gets none.
- A new component only when the plan needs one the library lacks. Write it to motion-lib/candidates/, use it in this
  reel only, and flag NEEDS REVIEW. Candidates join the library only with my approval.
- Editor annotations: every component part that should become its own layer in the editable project (card, (M21)
  title, body, icon, chip, tag, stamp, tracker cell, logo, caption box) carries `data-ed-layer`, a readable (M21)
  `data-ed-name`, and `data-ed-kind` (text, shape, image, group, dynamic, background, tracker, caption) when the (M21)
  kind is not obvious. Annotations never change how anything looks. New candidates in motion-lib/candidates/ (M21)
  follow the same rule. (M21)
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
   cues.json records for each sound: the event, the cue type, the file, the start time in ms, the trim in and out (M21)
   points in ms within the file, the fade-out in ms and the final gain in dB, so S15 can rebuild the sound edit (M21)
   exactly (the sound itself does not change). (M21)
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
  - the edge and ambient layers (Motion and energy rules E5, E7) are exempt from the off-canvas and overlap (M14)
    checks: they sit behind the content and never under text (M14)
  - E4: at most 100 characters of non-caption text on screen, no graphic text below the caption size, word mode (M15)
    under any other text; no caption word or group static (M15)
  - no element static for more than 0.5 s (transforms sampled from the composition, E1), and the edge layer (M16)
    present (E5) (M16)
  - branding (tweaks.md "Branding (FlashFX account)"): the CTA beat contains the FlashFX lockup, at least 300px wide,
    and the DM card's FlashFX avatar
  - no FlashFX logo outside the CTA when the solution is not FlashFX
  - each logo variant matches the luminance of the surface under it (light: gradient or black; dark: gradient or
    white) and its contrast is readable
  - every logo keeps its aspect ratio; the bolt is at least 64px tall (the DM avatar at least 112px across, which
    keeps its bolt at 64px; bolt sizes from brand.json's bolt_height); clear space of at least a quarter of the
    bolt's height around marks and lockups
- **Energy check** (Motion and energy rules E0; it runs first, needs no model): the reel and each scene against (M16)
  tokens.json energy; the failing scenes go back to 9a with their numbers as [animation] issues. (M16)
- **Style conformance.** Run tools/analyze_refs.py on draft_mixed.mp4 and compare with styles/paper-cards/analysis:
  - visual-change median and maximum within the reference range (plus or minus 20%)
  - at least 90% of non-image pixels within ΔE 5 of a token color (logo PNGs count as image pixels)
  - accent share under the tweaks.md limit (logos excluded)
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
  (the problem, the share line, the keyword). It also checks that the branding feels natural, not like an ad (an
  issue tagged [animation]). It passes when every score is at least 4. Every issue it lists carries a
  tag: [voice], [animation], [text], [transition] or [sfx].
  It also scores energy: does every scene keep moving, with inertia, depth and edges (E1 to E8). (M16)
- **Fix routing:** each issue goes back to the step that owns it (S8, 9a, 9b, 9c or S11), then S10, S11 and S12 run
  again as needed.
- **Loop caps:** at most 3 rounds with the Opus builder, then 2 rounds with the Fable builder. Still failing: export
  anyway, with NEEDS REVIEW and the review notes in the captions file. Never stop.
- **Early stop** (Motion and energy rules E9): two rounds in a row with the same scores and the same issues (M16)
  end the loop, and the reel exports with NEEDS REVIEW. (M16)

### S13 Final render
- Render with HyperFrames: 1080x1920, 30 fps, H.264 high profile, yuv420p, AAC 48 kHz, with the approved mix.
- Check with ffprobe: duration equals the voice within 0.2s, plus resolution, fps, codecs, audio present, loudness.
- Same for the hook 2 clip (with its own voice and sounds).

### S14 Caption and export
- Write the caption from the brief and the script: the first line is the hook, in 125 characters or fewer (where the
  feed cuts it off); one ask (the keyword); at most 5 hashtags.
- The caption follows the same solution rules as S7 (no FlashFX mention unless the solution is FlashFX, no ad
  language, never implying the reel was made in FlashFX).
- Run the vendor caption.py lint and humanize.py on it.
- Export as described in section 8.

### S15 Editable project (M21; scripts in pipeline/stages/s15-project/; no model call except the upgrade in step 8)

Runs after S14 has assembled the export in runs/<id>/export/ and before the move to exports/N/. It never changes
N.mp4, Nhook2.mp4 or the existing sections of Ncaptions.txt. Nhook2.mp4 gets no project.

**Goal.** exports/N/project/ is a Shorts Editor project folder (the FlashFXeditor repo) that opens as the reel's
layers, each one as editable as the editor allows today, and that looks like N.mp4 when nothing is changed.

**Inputs.** The final HyperFrames composition S13 rendered; words.json and vo.wav; 11-sfx/cues.json and the sound
files; the 09a, 09b and 09c plans; 10-build/events.json; tokens.json; the brand assets; the font files the
composition loads; the stable editor copy's capabilities.json.

**Stable editor copy** (pipeline/bin/editor-stable.sh; run between ideas, never during a run).
- editor.stable_dir is a separate git clone of editor.repo (`git clone <editor.repo> <editor.stable_dir>` on first
  use). S15 reads capabilities.json and runs the editor's CLI only there, never in editor.repo, which the editor's
  own runner changes all the time.
- Advancing, at most once an hour: `git fetch`, then find the newest commit whose subject is `batch-NN: review` and
  whose docs/PROGRESS.md at that commit (`git show <commit>:docs/PROGRESS.md`) has `in_progress_batch: none` and,
  in the entry of its `last_completed_batch`, a last `- review:` line that reads `accepted`. If that commit is newer
  than the current one: check it out (detached), run `npm ci` when package-lock.json changed, `npm run build`, and
  `npm run build:cli` when package.json has that script. On any failure, go back to the previous commit, rebuild it
  and log why.
- Serving: `npx vite preview --port 5310 --strictPort` in editor.stable_dir. run.sh starts it when it is not
  running and restarts it after an advance. editor.url (http://localhost:5310/) is where I open reel projects.

1. **Capabilities.** Read `<editor.stable_dir>/capabilities.json`; when it is missing, use
   pipeline/stages/s15-project/baseline-capabilities.json (the editor v1.1.0 manifest at the end of this stage,
   copied verbatim). Write the project at exactly the manifest's schemaVersion; when the manifest has
   `cli.normalize`, always finish with normalize (step 5), which also fills any field newer than S15's mappings
   with the editor's defaults. Use a clip kind, field, ease, transition, effect or value only when the manifest
   lists it: lists are exhaustive, and a key that is false or absent is unsupported. The stable copy's
   docs/INTEROP.md (from the editor's Batch 54) gives the exact JSON of each supported feature; until it exists,
   its src/core/document/types.ts and validate.ts are the reference, and §21 of its docs/PLAN_V1_2.md gives the
   JSON of planned features.

2. **Capture** (15-project/layers.json). Open the final composition in the browser harness that S12's mechanical
   checks use (Puppeteer), seek every frame, and record every layer, without inserting anything into the page:
   - Layers: elements with `data-ed-layer` (the S10 annotations). An annotated element inside another one is its
     child layer (the outer one is a group); unannotated elements belong to their nearest annotated ancestor; an
     element with no annotated ancestor counts as one layer per top-level HyperFrames clip element.
   - Placement per frame: for HTML elements, the border quad from the DevTools protocol (`DOM.getBoxModel`,
     Puppeteer's `ElementHandle.boxModel()`), whose four corners include every CSS transform on the element and its
     ancestors; for SVG elements, `getScreenCTM()` with `getBBox()`. Three corners give the 2D affine transform; a
     fourth corner that does not fit it means a 3D transform. The placement relative to the parent layer is the
     parent's inverse times the layer's.
   - Opacity per frame: the product of the computed opacities from the layer up to its parent layer.
   - Signature per frame: computed colors, borders, radii, shadows, filters, clip paths, box size and text content,
     and for canvas, video and animated SVG content a hash of a screenshot of the layer's area (CDP
     `Page.captureScreenshot` with a clip), because a WebGL canvas cannot be read back reliably.
   - Per layer: whether its look is static, changes instantly (the signature jumps, then holds) or changes
     continuously (over consecutive frames); and what a native clip needs: the kind (text, shape, image, svg,
     video, canvas, group), the text with its computed font and style, the box, background, border, radius,
     box-shadow, gradients and image source.

3. **Map every layer to the most editable level the manifest allows:**
   1. **Native**: the editor's own clip with the captured motion as keyframes: text, solid, image (PNG, JPEG, SVG),
      video, caption, audio, and more kinds as the manifest adds them (shape, compound, null, lottie). Allowed when
      the look is static, when its changes are on keyable props (`keyframes.props`, with `vectorValues` for
      colors), or when every change is instant: then the clip is split at each change into static segments.
   2. **Sprite**: the layer rendered once at rest and isolated in place (everything else hidden, its own and its
      ancestors' transforms and opacity neutralized, a transparent background), at the largest scale it reaches on
      screen (capped at 2x) and trimmed, with its anchor offset recorded; an image clip whose keyframes carry the
      captured motion (scale divided by the render scale). Used for static looks the manifest cannot express (for
      example a stroke or a hard shadow before the editor supports them).
   3. **Overlay**: a continuous look change the editor cannot key (a counter, a line drawing itself, a 3D canvas, a
      morph): the layer rendered isolated with transparency over its interval and cropped to the union of its
      visible pixels: a VP9 alpha WebM when `media.videoAlpha`; else a PNG image sequence when
      `media.imageSequence`; else animated WebP within `media.animatedImage` (per clip, frames x width x height x 4
      x 4/3 bytes at most `textureBudgetBytes` and sides at most `maxSide`; a longer overlay becomes several
      consecutive clips). Animated WebP frame durations are 33, 33, 34 ms repeating, so frame k starts at
      floor(k x 1000 / 30) ms: at timeline frame k the editor shows the last animation frame that starts at or
      before round(k x 1000000 / 30) microseconds, and a unit test reproduces that.
   4. **Plate**: only when no level above works: the scene's layers at and below that layer are rendered as one
      opaque video (one plates MP4 per reel, one clip per scene segment with in and out points); the layers above
      it stay separate.
   - Z-order: sprites and overlays are transparent, so native layers keep their exact order around them; a layer
     below a plate goes into the plate.
   - Groups: a compound clip when `compositing.compound`; else a parent with children when
     `transform.parenting`; else flattened (children get world-space keyframes, exact for transforms; when the
     group's own opacity is below 1 while its children overlap, the group becomes one sprite or overlay).
   - Keyframes: keep the fewest keys that reproduce every captured frame within 0.25 px, 0.1 degree, 0.002 scale
     and 0.004 opacity, using the manifest's eases (GSAP eases map to the Penner names once the manifest lists
     them; otherwise linear keys); jumps become hold keys.
   - Text is native only when its font is available (the editor's library, public/fonts/library/catalog.json,
     copied into fonts/ with fonts.json version 2 entries, or the composition's own font files as
     `source: "user"`) and when its fill, stroke, shadow and background are in the manifest. It uses box mode
     `auto`, so only the composition's explicit line breaks (written as \n) wrap, and it is placed by its alignment
     from the measured text bounds (left, center or right edge; top, middle or bottom by its vertical anchor).
   - Captions are native (the caption track: cues from the 09b chunks, word timings from words.json, emphasis
     words) only when the manifest has everything the style uses (the `progressive` highlight, `wordEmphasis`, a
     box border and a hard shadow, cue fades). Otherwise they are baked: one PNG per word state (the box with its
     words gray or ink), image clips on a "Captions (baked)" track with the style's 2-frame fades; plus the native
     caption track, hidden, with the closest style, so I can switch with two clicks.
   - Stand-ins: when `interop.fallbackOf` is true, every sprite and overlay that has a native equivalent in the
     editor's JSON (INTEROP.md, or §21 of PLAN_V1_2.md for planned features) carries
     `fallbackOf: { kind, reason, schemaVersion, data }` with that native clip (sparse is fine), so the editor can
     make it editable later.

4. **Audio.** vo.wav and every sound effect become audio clips at their exact times, with the trims, fades and gains
   of cues.json, converted to 48 kHz WAV in media/audio/. The final render's master gain (the loudness
   normalization) is folded into each clip's gain, so the project's playback and mix match N.mp4 within 0.5 LU.
   When `audio.loudness` is true, also set the project's loudness target to -14 LUFS with a true peak of -1.5 dBTP
   (as S8 and S11). The voice goes on the first audio track, sound effects on the second (and a third when two
   overlap).

5. **Write** runs/<id>/export/project/:
   ```
   project.json      the manifest's schemaVersion; name "N <title>"; 1080x1920, 30 fps; background = the paper color
   media/            audio/, images/ (background, logos, icons), sprites/, overlays/, plates/
   fonts/            fonts.json (version 2) and the font files used
   layers.json       the capture, for rebuilds
   FALLBACKS.md      every baked layer: scene, time range, layer name, level, the missing manifest key
   OPEN.txt          how to open the project (the link and the folder)
   ```
   - Tracks from the bottom: the background (the paper and dot grid as one image clip, unless they animate), the
     layers in z-order (tracks reused across scenes; one compound clip per scene when `compositing.compound`), the
     baked captions, the caption track, then the audio tracks.
   - Names a person can read: "S03 card: <its text>", "Caption 12", "SFX whoosh_fast". Label colors: violet for
     sprites, orange for overlays, red for plates. Bins: Audio, Images, Sprites, Overlays, Plates.
   - Markers: one at each scene start, labeled with its beat type, and one at the comment keyword.
   - `meta.generator` (when `interop.generatorMeta`): name "instagramReels", version (the git short hash), source
     "runs/<id>".
   - When `cli.normalize` is true, write the sparse form and always run `npm run cli -- normalize <dir> --write` in
     the stable copy; otherwise write every field.

6. **Check.**
   - Validate with `npm run cli -- validate <dir> --json` in the stable copy when `cli.validate` is true (strict:
     it checks every field); otherwise with the S15 validator, which mirrors every rule of the editor's validate.ts
     and every field of types.ts (types, required fields, no unknown fields; sorted, non-overlapping clips; media in
     and out points inside the media; caption track rules; integer frames and microseconds; unique ids; files
     present).
   - Parity, when `cli.render` and `cli.compare` are true: render the project with the stable copy's CLI and
     compare it with N.mp4 (SSIM at least editor.parity_ssim on every frame). Layers inside failing regions drop
     one level (native to sprite, sprite to overlay) and the project is written again, at most twice; what still
     fails goes to FALLBACKS.md and NEEDS REVIEW.
   - Without `cli.render`, a layout check at the middle frame of every scene: composite the sprites, overlays and
     plates with their keyframes in the browser harness and compare their regions with the composition (SSIM at
     least 0.95); and measure each native text with Canvas2D in the same font and size, as the editor does, and
     compare its box with the composition's text box (within 2 px). This catches placement, anchor and wrapping
     errors.
   - The project lasts as long as N.mp4 within 1 frame, and the voice and sounds sit at their times in the mix
     within 1 frame.

7. **Export.** The project moves with the rest to exports/N/project/. Ncaptions.txt gets the EDITOR section
   (section 8). logs/editor-gaps.md gets one line per missing manifest key with a running count, the reel elements
   it affected and the latest reel, sorted by count: the to-do list for the editor's next batches.

8. **Capability upgrade** (between ideas, never during a run). When the capability content of the stable copy's
   manifest (everything except `lastBatch` and `appVersion`) differs from logs/editor-capabilities.json, the runner
   logs the added keys and, before taking the next idea:
   - a build session (model: builder) reads the stable copy's docs/INTEROP.md and extends S15's mappings for the
     new keys (and checks any mapping written earlier from the plan against INTEROP.md), with tests: a fixture
     project validated by the editor CLI, and rendered and compared when `cli.render`;
   - a review session (model: reviewer) checks the change against INTEROP.md and runs the tests, answering
     accepted or a list of problems; the builder gets at most 2 fix rounds;
   - accepted: commit `s15: editor capabilities <keys>` and save the manifest to logs/editor-capabilities.json;
   - not accepted: revert every file the upgrade changed, record the manifest's capability hash and the reasons in
     logs/editor-upgrade.json, and go on with those keys on fallback. A failed hash is tried again only when the
     capabilities change again or 24 hours later. logs/status.txt shows the upgrade while it runs.
   pipeline/stages/s15-project/CAPABILITIES.md lists every manifest key S15 knows: mapped or not, and which reel
   elements use it.

**Rebuild.** `bash pipeline/bin/rebuild-project.sh N` rebuilds exports/N/project/ from its run folder with the
current manifest, without touching anything else. If the editor changed the project since it was written
(project.json newer than layers.json), the old folder is kept as project.edited-<date>/.

**Failure and time.** S15 has a cap of editor.cap_minutes (25). On an error or at the cap it writes the minimal
project: the visuals without captions as one plate, the voice and sound effect clips, the baked captions and the
hidden caption track. If even that fails: project/FAILED.md with the error, and a NEEDS REVIEW line. The export
goes on in every case.

The baseline manifest (the editor v1.1.0, before its Batch 54), copied verbatim to
pipeline/stages/s15-project/baseline-capabilities.json:

```json
{
  "manifestVersion": 1,
  "app": "shorts-editor",
  "appVersion": "1.1.0",
  "lastBatch": 53,
  "schemaVersion": 3,
  "project": { "file": "project.json", "fontsManifest": "fonts/fonts.json", "fontsManifestVersion": 2, "sampleRate": 48000 },
  "media": {
    "video": ["mp4", "mov", "m4v", "webm"],
    "audio": ["mp3", "m4a", "aac", "wav", "ogg"],
    "image": ["png", "jpg", "jpeg", "webp", "gif", "svg"],
    "animatedImage": { "formats": ["gif", "webp"], "alpha": true, "maxSide": 2048, "textureBudgetBytes": 134217728 },
    "videoAlpha": false,
    "imageSequence": false,
    "lottie": false
  },
  "trackKinds": ["video", "audio", "caption"],
  "clipKinds": ["video", "audio", "image", "text", "solid", "caption"],
  "transform": { "rotation3d": false, "parenting": false, "motionPaths": false, "autoOrient": false },
  "keyframes": {
    "props": ["transform.x", "transform.y", "transform.scale", "transform.scaleY", "transform.rotation", "opacity", "volume.gainDb"],
    "eases": ["linear", "easeIn", "easeOut", "easeInOut", "hold", "smooth", "snap", "overshoot"],
    "bezier": false,
    "spring": false,
    "vectorValues": false
  },
  "solid": { "shapes": ["rect", "roundedRect", "ellipse", "line"], "fills": ["color", "gradient2"], "stroke": false, "shadow": false, "cornerRadii": false },
  "mediaFrame": { "stroke": false, "shadow": false, "cornerRadius": false },
  "text": {
    "fills": ["color", "gradient2"],
    "stroke": true,
    "shadow": true,
    "background": { "modes": ["line", "block"], "stroke": false, "shadow": false },
    "anims": ["fade", "slideUp", "slideDown", "slideLeft", "slideRight", "pop", "typewriter", "wordPop", "wordFade", "lineReveal", "blurIn", "scaleBounce"],
    "animUnits": ["char", "word", "line"],
    "spans": false,
    "counter": false,
    "animators": false
  },
  "captions": {
    "highlightModes": ["none", "color", "background", "scale", "colorAndScale"],
    "perCueStyle": true,
    "wordEmphasis": false,
    "cueAnims": [],
    "boxModes": ["line", "block"],
    "wordsImport": false
  },
  "transitions": ["crossDissolve", "dipToBlack", "dipToWhite"],
  "compositing": { "compound": false, "blendModes": ["normal"], "trackMatte": false, "masks": false, "adjustment": false },
  "vector": { "shapes": false, "trimPaths": false, "svgImport": false },
  "effects": [],
  "audio": { "clipGainDb": [-60, 12], "fades": true, "trackGain": false, "pan": false, "loudness": false },
  "time": { "speedRange": [0.25, 4], "freeze": true, "reverse": false, "remap": false, "frameBlend": false },
  "templates": false,
  "export": { "containers": ["mp4"], "videoCodecs": ["h264", "hevc", "av1"], "alpha": false, "imageSequence": false, "gif": false, "stems": false },
  "cli": { "validate": false, "normalize": false, "info": false, "render": false, "compare": false },
  "interop": { "openLink": false, "externalReload": false, "repairOnOpen": false, "fallbackOf": false, "generatorMeta": false }
}
```

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
| S8 | generating voiceover (beat 4/9), tightening silences, aligning words, fixing pronunciation (line 4), rewriting line 4 |
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
[14:09] GATE   passed (P3 S2 C3 F ok H ok)
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

- exports/ stays at the root of this folder and is shared by every channel (from M19). Every exported video gets its
  own folder exports/<id>-N/: <id> is the channel id (14.1) and N counts that channel's exports in build order (1, 2,
  3, ... for each channel).
- N is assigned at export time: N = 1 + the highest number of this channel found in exports/ (folders named
  <id>-<number>) and in this channel's history.txt (lines "exported <id>-<number>"). Dropped or blocked ideas leave no
  gaps, and deleting a posted folder never reuses its number. Assemble everything in runs/<run>/export/ first, then
  move it into exports/<id>-N/ in one step.
- Files, every name starting with <id>-N:
  - <id>-N.mp4: the video
  - <id>-Ncaptions.txt: the captions file of the channel's platform (below)
  - <id>-Nhook2.mp4: the alternate hook clip, instagram-reels only: up to 3.5 seconds, hook 2 in the same style
  - project/: the editable project (S15); the EDITOR section of the captions file says how to open it (M21)
- After the export: delete the idea from the channel's ideas.txt and write the channel's history line.
- Exports made before M19 (exports/N/) are renamed by migrate-channels (14.13).
- Each platform's rules and its exporter live in pipeline/platforms/<platform>/ (platform.json: size, fps, length
  limits, safe zones, text limits, whether there is a hook 2 clip, the captions file sections). A channel overrides
  them in channel.json `export`.

Captions file, instagram-reels (FlashFX):

```
CAPTION
<the caption, first line = the hook, ready to paste>

HASHTAGS
#one #two #three

COMMENT KEYWORD
<KEYWORD> -> DM them: <deliverable> <link>
<only when the deliverable doesn't exist yet: NEW deliverable to create before posting: ...>

SOLUTION
<flashfx | external: name link | method>

HOOKS
<id>-N.mp4 uses: "<hook 1>"
<id>-Nhook2.mp4 uses: "<hook 2>"

NEEDS REVIEW
<only when flagged: what and why>

FACTS AND SOURCES
- <claim>: <url> (checked <date>)

RUN
channels/<id>/runs/<run>

EDITOR (M21)
Project: exports/<id>-N/project (open <editor.url>?open=exports/<id>-N/project, or Open project and pick that folder) (M21)
Layers: <native> native, <baked> baked (see project/FALLBACKS.md) (M21)
```

Captions file, youtube-shorts (Life of Gabry):

```
CAPTION
<the caption: one line, at most export.caption_max characters (150), no hashtags, no links>

DESCRIPTION
<what this video is about, written for this video only, at most export.description_max characters (1000) in total>

PINNED COMMENT
<one line that invites replies; only when export.pinned_comment is true>

HOOKS
<id>-N.mp4 uses: "<hook 1>"

NEEDS REVIEW
<only when flagged: what and why>

FACTS AND SOURCES
- <claim>: <url> (checked <date>)   (only when the video states facts)

RUN
channels/<id>/runs/<run>

EDITOR (M21)
Project: exports/<id>-N/project (open <editor.url>?open=exports/<id>-N/project, or Open project and pick that folder) (M21)
Layers: <native> native, <baked> baked (see project/FALLBACKS.md) (M21)
```

youtube-shorts text rules, checked in code by the exporter (a failing check gets one rewrite with the failures listed;
a second failure exports with NEEDS REVIEW):
- CAPTION: one line, at most caption_max characters (150 by default), no hashtags, no links; it is the hook as a
  title, written for a viewer who has not seen the video.
- The exporter reads runs/<run>/export/input.json (schema pipeline/platforms/youtube-shorts/input.schema.json): the
  premise summary, hook 1, the script lines, the beats (a short label and the narration of each), the facts with
  their sources, the channel's brand and export settings, and the channel's earlier descriptions (from
  descriptions.jsonl). The format writes it through the adapter named in format.json `export_input`; the M19 test
  fixtures follow the same schema.
- DESCRIPTION: at most description_max characters (1000), counting every character, line break and hashtag.
  - It says what this video is about: the first line is a one-sentence summary of this scenario, never the caption
    repeated.
  - It is not one chunky paragraph: short lines; no paragraph (consecutive lines that are not list items) longer than
    200 characters.
  - It contains at least one list of 3 to 6 items, one per line, each starting with "- " (a hyphen and a space; for
    example the moments of a timeline premise, the rules of the new world, what Gabry tries). humanize.py turns other
    bullet signs into "- ", so the check runs after it; detect.py's uniform-bullets warning is ignored for this list.
  - It ends with exactly 4 hashtags (export.hashtags), all on the last line, separated by spaces, each relevant to
    this video; export.required_hashtags (default none) count among the 4.
  - It is different every video: its first line matches no earlier description of this channel, and against each of
    the channel's last 30 descriptions the overlap is at most 30 percent. Overlap = the word trigrams (lowercase,
    punctuation removed, the hashtag line left out) this description shares with the earlier one, divided by this
    description's trigrams. Every exported description is stored in the channel's logs/descriptions.jsonl.
  - No links, no promotion; it goes through humanize.py and the slop list like every other text.
- PINNED COMMENT: one line, at most 200 characters, a question or a choice that invites replies, no links.

Shape of a description:

```
What if the dinosaur asteroid hit Earth today, with Gabry watching from his balcony?

Second by second:
- 0 s: a second sun appears over the city
- 1 s: the shockwave flattens everything for miles
- 10 s: burning rock starts to rain down
- 1 hour: the sky turns black

Would you have made it past the first minute?

#whatif #dinosaurs #asteroid #animation
```

## 9. config.json

- **models**, one per role, with an effort level each (Claude Code model names and effort levels):
  - research, gate, judge, script, visual_director, builder, qa, reviewer: opus
  - cut, checks, fixer: sonnet
  - builder_escalation, reviewer_escalation: fable
  - indexer, probe: haiku
- **tts:** device cpu. Every voice setting (engine, interpreter, voice, lang, speed, the silence tightening values)
  comes from library/voice/engine.txt, never from config.json. No fallback engine, and no chatterbox, turbo or qwen
  settings.
- **voice:** wpm (the pace of the reel voice, af_bella after tightening, measured at M7; until then the value from
  voice.md), loudness target.
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
- **editor:** repo (the FlashFXeditor folder: /c/Users/there/OneDrive/Desktop/editor), stable_dir (the stable (M21)
  copy S15 uses: next to repo, named like it with -stable added), port (5310), url (http://localhost:5310/, where I (M21)
  open reel projects), projects_root (this instagramReels folder: the projects folder I choose in the editor, so (M21)
  `?open=exports/N/project` works), project (true), cap_minutes (25), parity_ssim (0.97). (M21)
- **Channels and formats (M18, M20):** config.json holds the engine settings. Each run reads the resolved config:
  config.json, then the format's `config` block in format.json (from M20), then the channel's `config` block in
  channel.json, deep-merged in that order (14.4). M18 moves style, voice, sfx, lengths and the channel data paths of
  `paths` into channels/flashfx/channel.json; M20 moves research, hooks, judge, script, visual, review and caption
  into pipeline/formats/problem-solution-reel/format.json. Values do not change in either move. build/M17/
  config-keys.tsv lists every key with its destination.
- **heavy (M19):** stale_seconds for the global heavy lock and the list of step kinds that take it (14.6).
- Platform settings live in pipeline/platforms/<platform>/platform.json, not in config.json (section 8).

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
- the channels (from M18): their ids, names, platforms and formats, how to start each (`bash run.sh --channel <id>`),
  where each one's files are (channels/<id>/), and that exports/ is shared with `<id>-N` names
- the braces rule with channels: add with `bash pipeline/bin/add-idea.sh --channel <id> "{...}"`. The channel comes
  from my words around the braces ("for life of gabry", "lifeofgabry:", "flashfx idea"). When I name none and more
  than one channel is enabled, ask me which one in one short question before adding
- how to add a channel (`bash pipeline/bin/new-channel ...`) and that one channel's session never edits another
  channel's files

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
  - Builds: S8 on top of tools/voice.py (Engine class, tighten function): pronunciations, beat by beat generation,
    silence tightening, alignment, the word error rate ladder, loudness. Remove the chatterbox, turbo and qwen
    settings from config.json.
    - When library/voice/engine.txt exists, use exactly its engine, interpreter and settings, and install nothing.
    - Otherwise install kokoro, CPU-only, in a virtual environment outside the project, use the settings shown in
      2.5, and add a HUMAN_TODO asking me to write engine.txt.
    - Update the preflight to check only engine.txt's interpreter: it exists and can import kokoro (a one-line import
      test).
  - Test, with only the engine in engine.txt: the test idea's script produces vo.wav and words.json; no pause longer
    than keep_pause_s remains except the hook breath (and the 0.2s tail); 5 spot-checked word timestamps line up
    with the audio; the preflight checks that engine.txt's interpreter can import kokoro; the failure ladder ends in
    a flag or a block, never in another voice or engine; the measured speed and pace are recorded in DECISIONS.md.
- **M8 Sound effects memory map (2.6).**
  - Builds: build-sfx-map over styles/sfx/, sfx-map.json, SFX-MAP.md, the pools, previews, overrides.txt handling,
    HUMAN_TODO to listen to the previews.
  - Test: every audio file is either in the map or listed as excluded with a reason; every cue type has a pool of at
    least 3 sounds (or a HUMAN_TODO saying which cue types are short); a rebuild with an override keeps it.
- **M9 Motion library.**
  - Builds:
    - tokens.json
    - every component in vocabulary.md as a HyperFrames component with its declared sound events
    - for the branding (2.7, tweaks.md "Branding (FlashFX account)"): a DM notification card for the CTA in the
      style's look (a surface card with a round avatar image, the sender name and one message line), and an image
      prop on every logo spot (end card, logo tile, logo badge, kicker mark) that takes a file path from brand.json
      or the research assets, with its aspect ratio locked
    - a gallery page that plays each one
    - frame-matching against the reference filmstrips in styles/paper-cards/analysis
    - components that pass the frame-match go into motion-lib/, with a HUMAN_TODO for me to review the gallery
    - a golden reel built from the test idea, following the branding rules, with a HUMAN_TODO for me to review it
    - a WebGL test for Three.js in headless Chrome on this PC: hardware ANGLE first (the integrated GPU), then
      SwiftShader software rendering. Record which works in DECISIONS.md. Keep 3D scenes light (low poly, few
      objects). If WebGL is not available, 3D beats are replaced with 2D components and flagged NEEDS REVIEW.
- **M10 Visual stages (S9, S10).**
  - Builds also: the branding placement of S9 and S10 and the preflight check of brand.json (2.7).
  - Test: the three plan passes validate, the draft renders, events.json matches what is on screen. Branding, with a
    fixture solution.json for flashfx and one for external: both CTAs have the FlashFX DM avatar and the lockup;
    FlashFX logos in the body and the brand slot only in the flashfx reel, the tool's logo or a neutral icon in the
    other; every logo path comes from brand.json with a use_on that matches its surface; every logo is an image
    with its aspect ratio locked.
- **M11 Sound effects pass and review loop (S11, S12).**
  - Test: on the test idea's draft, every sound lands within 1 frame of its event, loudness passes, the edit review
    runs, and a planted [text] issue routes back to 9b and the stages after it run again. The branding checks pass on
    the test idea's draft, and each planted branding fault is caught: a FlashFX logo in the body of a non-FlashFX
    reel, a black lockup on ink, a stretched logo, a lockup under 300px, a CTA without the DM avatar.
- **M12 Final render, caption, export, end to end (S13, S14).**
  - Also builds the problem-first solution choice into the stages built in M4 and M6: S1's solution candidates, S2's
    solution decision and keyword, S3's honesty check H, S4's new pick, S7's solution rules; plus the SOLUTION block
    (section 8) and the solution type in history lines (4.3).
  - Test: the test idea produces exports/1/1.mp4, 1captions.txt and 1hook2.mp4, every ffprobe check passes, and the
    idea is gone from ideas.txt. 1captions.txt has the SOLUTION block and the history line has the solution type. A
    fixture idea with a forced FlashFX solution goes to S4 and comes back with another solution (not dropped); with
    a non-FlashFX solution, script.json and the caption never mention FlashFX.
- **M13 Hardening.**
  - Also builds: pipeline/bin/build-voice-profile --force keeps the hand-written sections of account.md and
    voice.md (2.3) instead of rebuilding them from the template.
  - Test: 3 ideas back to back, unattended; a simulated limit in the middle of a run; the logs and status lines tell
    the full story; build-voice-profile --force on a copy of the profile keeps its hand-written Brand section.
- **M14 Motion grammar and energy meter** (section 5, Motion and energy rules E0, E1, E2, E5, E6, E7; the motion
  library level). The lines of this spec marked (M14) are built and reviewed here; the reels' look stays the style's.
  - Builds:
    - `pipeline/lib/review/energy.py` (E0), run as `python pipeline/lib/review energy <video> [--plan merged.json]`:
      the whole-reel and per-scene measures; its calibration on the style's reference videos into
      styles/paper-cards/analysis/energy.json; the targets in tokens.json `energy`.
    - tokens.json `motion` and `energy` (pipeline/lib/tokens.py), with E1 to E9's values unless tweaks.md overrides
      them; motion-lib/assets/tokens.css exposes them.
    - `motion-lib/assets/pc-motion.js`, the shared motion grammar every component uses: the four phases of E1 (main
      animation on the style's measured enter frames, 2 to 4 s of decelerating inertia, the calm, normal and lively
      holds, the exit), the combined main animations of E2 (zoom plus 3D parallax rotation plus move, power3 or power4
      in-out, the rotation lagging by 2 to 4 frames, the decelerating tail), the 2.5D scene container with a slowly
      moving camera and layers at their own depths (E6). Every existing component is moved onto it; no component
      keeps its own phase or curve code.
    - the edge filler layer (E5) and the ambient layer (E7) in paper-canvas, seeded per reel, with the mascot's idle.
    - `icon-3d`: a Three.js component (low poly, built in code from extruded SVG paths and primitives, turning slowly,
      on the WebGL backend of motion-lib/webgl.json) with a CSS-extruded fallback (an SVG in 8 to 16 depth layers).
    - the gallery shows each component's energy measures; frame-match keeps checking the main animation against the
      references and a new check measures the inertia and the hold; the golden reel is rendered again with the new
      library (same plan) and its numbers recorded.
  - Test: the meter reproduces the reference numbers of energy.json within 1 point and fails the M13 reel
    (build/M13/rerun/1.mp4) on every target; every component rendered alone for 4 s is never static (no 0.5 s
    window without motion), its main animation still frame-matches its reference, and its inertia lasts 2 to 4 s;
    icon-3d renders with WebGL and with its fallback; the edge and ambient layers stay out of every text zone and
    hold no text; the re-rendered golden reel measures higher than before on every energy measure, its moving share
    at least doubled; the earlier milestones' fake-only tests still pass.
- **M15 Kinetic captions and text discipline** (section 5, Motion and energy rules E3 and E4). The lines of this spec
  marked (M15) are built and reviewed here.
  - Builds:
    - the two caption modes as components on pc-motion.js, replacing caption-line: `caption-word` (one word at a time
      on its spoken time, emphasis words in the emphasis font at 1.25 to 1.5 times the size with the accent box,
      every word drifting) and `caption-group` (the group as the graphic: at least 3 fonts, the anchor at 2 to 3 times
      the caption size, the stacked lines matching the anchor's height, asymmetric, each word on its spoken time, the
      group moving as one block and leaving together).
    - `pipeline/lib/visual/kinetic.py`, the deterministic group layout engine (word roles, fonts, size ratios, stacked
      lines, asymmetry, the fit inside the group caption zone, no word below the caption size, the right-rail rule);
      tokens.json gains the caption fonts, the size ratios and the group caption zone (the hero zone).
    - script.json's per-beat importance (S7) and 9b's plan fields: the caption mode of each beat, the group's words,
      anchor and layout; the choice rule (group mode on important beats and on beats without a clear graphic, word
      mode under any other text).
    - the plan validator and S12 mechanical rules of E4 (100 characters of non-caption text on screen, no graphic
      text below the caption size, word mode under text) and "no caption word or group static".
  - Test: kinetic.py on "the quick brown fox" gives the E3 example (three fonts; "quick" and "brown" stacked at half
    the anchor's size, their combined height equal to the anchor's within 2 px; asymmetric; inside the zone); a group
    of 6 long words fits or splits into two groups; no group word is below the caption size; on the golden plan the
    captions run one word at a time in normal talk and as groups on the important beats, and every caption word
    moves on every frame; the planted faults are caught (a card with 120 characters, a 40 px label, a group caption
    over a text card, a static caption word); the earlier milestones' fake-only tests still pass.
- **M16 Director, components and the energy loop** (section 5, Motion and energy rules E8 and E9; the stage level).
  The lines of this spec marked (M16) are built and reviewed here.
  - Builds:
    - new components on pc-motion.js, each in the gallery and frame-matched where a reference exists: screenshot pan
      and zoom with a highlight box, card fan or deck, card grid, video card (a recording or a clip playing inside a
      card), timeline scrubber (a playhead running over thumbnails), cursor (moves and clicks), mock website card,
      color swatches (a row filling in on spoken words, and a single swatch card). The catalog, the beat map and the
      director's component list gain them.
    - S1's page recordings: a 5 to 8 s scroll video of each key page (Playwright, 1080 wide) next to its screenshot,
      played by the video and window cards.
    - the 9a, 9b and 9c prompts rewritten around the Motion and energy rules (hold level per scene, combined main
      animations, camera every 3 scenes, at least 2 layers, the hero filling 70 to 85% of the width, the edges, the
      depth at the center, varied transitions, the hook moving by frame 4, text only when strictly necessary); the
      validator rules of E9.
    - a new golden reel (golden/test-idea/), planned by hand to meet every energy target, with a HUMAN_TODO to review
      it; the director copies it.
    - S12: the energy check first with per-scene routing to 9a, the "no element static" and edge layer checks, the
      energy score in the edit review, and the early stop.
  - Test: the new golden reel meets every energy target of tokens.json, and every scene reaches at least 80% of each
    target; the validator fails one fixture plan per new rule and passes the golden plan; the test idea, run from
    scratch with the real models (as test-m12 section 4), gives a reel that meets the energy targets, or exports after
    the loop with its numbers in NEEDS REVIEW, and the edit review's scores on stopping the scroll, motion variety and
    nothing generic are above the M13 reel's 3; the early stop fires with a fake qa that repeats its verdict; the
    earlier milestones' fake-only tests still pass; the time per reel grows by at most 20%.
- **M17 Control check.** No behavior change: nothing the runner uses is changed. It prepares M18 and M19 so that every
  file can be moved without a mistake (14.13).
  - Must not change: run.sh, pipeline/ (new files under pipeline/tests/ only), config.json, ideas.txt, library/,
    styles/, motion-lib/, golden/, exports/, runs/, logs/. The video runner may keep running during M17: read its
    files, never write them. Everything that runs the pipeline's own code (preflight, doctor, the dummy run, the
    tests) runs with REELS_ROOT set to a temp copy of the state files, never on the real folder.
  - Produces:
    - build/M17/inventory.md and inventory.tsv: every top-level item and every file in the folder, whatever its git
      state (tracked, untracked, ignored), with its size; the big data folders (runs/, exports/, logs/, library/voice/,
      styles/*/refs/, styles/*/analysis/, styles/sfx/ audio, render outputs) also summed per folder; the state of the
      machine: is a video runner alive, the ideas queued, unfinished runs (a state.json with a stage not done), the
      exports present, free disk, whether the folder is synced by OneDrive.
    - build/M17/refindex.tsv, written by pipeline/tests/refindex.py (deterministic, sorted): every occurrence, in
      tracked text files, of a path that moves (library/, styles/, motion-lib/, golden/, ideas.txt, runs/, logs/,
      exports/, .locks/), of the export names (N.mp4, Ncaptions.txt, Nhook2.mp4, exports/N) and of the config keys
      that move (14.4), each with file, line, the match, its kind (path built in code, prompt text, doc, test,
      comment) and the planned change (a paths module call, a channel path in docs, an export name). Plus the counts of
      old paths inside ignored data (run files such as state.json, captions files, history.txt) in every form
      (root-relative, C:/, /c/, backslashes), per pattern, with examples.
    - pipeline/tests/make-manifest.py (the rules of 14.13, deterministic) and its output build/M17/move-manifest.tsv:
      every move M18 and M19 will execute, in order, with the export renames for every existing exports/N/; and
      build/M17/config-keys.tsv: every config.json key and its destination (engine, format or channel; the four safety
      keys of review are engine, 14.4).
    - pipeline/tests/check-manifest.py: every old path exists; no two lines collide; every new path is inside
      channels/<id>/ or exports/, or stays; every file of the inventory, whatever its git state, is covered exactly
      once (by its own line or a containing folder's line) or is engine; the files and bytes add up to the inventory.
      With `--after` it checks the folder after a migration: every new path present, no moved folder left at its old
      path.
    - build/M17/baseline/: pipeline/tests/run-fake.sh, written in M17, runs every fake-only test (the list in
      CLAUDE.md: test-m1, test-m2, test-m8, test-m9, test-limits, test-no-emdash and the fake-only sections of the
      others); its result per test (pass or fail, duration, log); the output of preflight and doctor --quick; and the
      dummy fingerprint: `REELS_DUMMY=all bash run.sh --once` in the temp copy, with the tree of the run folder and of
      the export it produced (names, not contents; the timestamp in run folder names replaced by <ts>).
    - The baseline rule, used by M18 to M24: no test that passed in the baseline fails (a known failure that now passes
      is fine). Durations are recorded, not compared: the video runner may share the CPU.
    - build/M17/risks.md: everything that can break a move, each marked BLOCKER or NOTE: a video runner alive, an
      unfinished run, uncommitted changes, open or locked files, OneDrive sync, old paths inside data, paths longer
      than 200 characters, symlinks, files the manifest cannot place, disk space.
    - build/M17/report.md, written for me: what moves where (counts and sizes per destination), the 10 riskiest
      moves, the BLOCKERs, the baseline results, M18's size (the refindex counts per kind), and what I must do before
      M18 (stop the video runner). Unfinished runs need nothing from me: they move with their channel and resume.
  - Test: check-manifest.py passes; make-manifest.py and refindex.py each give identical files when run twice;
    run-fake.sh's results are recorded (a test that already failed is recorded as a known failure, not fixed);
    `git diff --name-only <start>..HEAD` (start = MS_START_SHA in build/state.env), leaving out autofix commits and the
    two runner-written files (library/.hooks.stats.json, library/hooks.suggested.txt), lists only files under build/
    and pipeline/tests/ and the build's memory files (CLAUDE.md, PLAN.md, DECISIONS.md).
  - End BLOCKED only when the manifest cannot place some file, or a check fails that only I can fix. A running video
    runner is not a reason in M17 (it goes in report.md and HUMAN_TODO: stop it before M18).
- **M18 Channels.** 14.3, 14.4 (the channel keys and the safety keys), 14.5 (without the canary part), 14.6
  (--channel and the channel lock), 14.13 (the moves marked M18).
  - Builds: pipeline/lib/paths.sh and paths.py; every path to channel data through them (the refindex lines of kind
    code); channel.json with its schema and the config merge in config.sh and config.py;
    channels/flashfx/channel.json with the keys moved from config.json; the review safety keys and protect.py resolved
    for every channel (14.4); run.sh --channel and REELS_CHANNEL; per-channel locks, logs, history and status;
    add-idea.sh --channel; preflight, runner-status and doctor per channel; pipeline/bin/migrate-channels with
    --dry-run, the rehearsal fixture and the undo; the new .gitignore (14.3) and the snapshot of the runner-written
    files, each committed before the first move; the regenerated manifest (14.13) and its M18 lines executed on the
    real folder (git mv of tracked files, renames of untracked and ignored data, the rewrites); the no_emdash.py skip
    path moved to channels/*/library/hooks.txt (my curated hooks file is never edited to pass a test);
    test-isolation.sh part 1 with its allowlist; CLAUDE.md's folder map and rules (section 11).
  - Not in M18: the export names (M19), format.json (M20).
  - Before the real migration: if a video runner is alive, end BLOCKED with "stop the video runner (Ctrl+C in its
    window), then run bash build-runner.sh again".
  - Tests:
    - run-fake.sh meets the baseline rule of M17. Test edits allowed: the channel argument, channel paths and the
      no_emdash skip path, each listed in the report
    - migrate-channels on the rehearsal fixture: the dry run lists every M18 line; the run verifies; the undo brings
      back an identical tree (checksums); a second run verifies; a run killed halfway is undone by the next start
    - the real migration: the dry run's output and manifest-diff.md saved in build/M18/; the run's verification passes
      (checksums, only renames in git status, git check-ignore for every formerly ignored file, no old path left in the
      rewritten files); check-manifest.py --after passes; preflight --channel flashfx and doctor --quick pass
    - the dummy fingerprint: `REELS_DUMMY=all bash run.sh --channel flashfx --once` in a temp REELS_ROOT gives the
      baseline's run folder tree (names normalized), inside channels/flashfx/runs/
    - an unfinished fixture run moved by the rehearsal resumes at the same stage
    - a fake model edit of channels/flashfx/library/hooks.txt during a stage is refused and the file restored
    - run.sh without a channel exits 2 and lists the channels; an unknown id exits 2; a second runner of the same
      channel refuses; dummy runners of two fixture channels run at the same time
    - test-isolation.sh part 1 passes
- **M19 Exports and channels side by side.** Section 8, 14.6, 14.5's canary part, 14.7's new-channel, 14.13 (the moves
  marked M19). Starts with the gate of 14.13.
  - Builds: the export folder and file names and the numbering of section 8; the M19 lines of the manifest
    (regenerated first: old exports/N/, their captions files, history lines) executed through migrate-channels with the
    same rehearsal, verification and undo; pipeline/platforms/instagram-reels/ (today's export behind the platform
    interface) and pipeline/platforms/youtube-shorts/ (platform.json with the limits and safe zones; input.schema.json;
    the exporter: its prompt for caption, description and pinned comment, the checks of section 8, one rewrite, NEEDS
    REVIEW, descriptions.jsonl); pipeline/schemas/platform.schema.json; heavy.sh around every heavy step; the shared
    limit file; the daily quota; the editor lock (used from M21); logs/engine.log; runner-status and doctor for all
    channels; pipeline/bin/new-channel with the template of problem-solution-reel; test-isolation.sh part 2 (two
    problem-solution-reel fixture channels until scenario-story exists).
  - Tests:
    - two dummy exports of a fixture channel give exports/<id>-1/ and exports/<id>-2/ with the right file names; the
      first export of a second channel is <id2>-1 in the same exports/; after deleting exports/<id>-2/ the next
      export is <id>-3 (from history)
    - the export migration on the rehearsal fixture, the undo, again; then on the real folder with verification: every
      old exports/N/ is exports/flashfx-N/ with renamed files and updated HOOKS, RUN and EDITOR lines, and history
      lines are updated
    - the youtube-shorts exporter on 6 fixture input.json files (section 8's schema, two per premise kind of 14.10):
      every check passes; a planted 1100-character description, a line of 5 hashtags, a 400-character paragraph, a
      description without a list and a copy of an earlier description each fail their check and get rewritten; no
      caption is ever longer than caption_max
    - the heavy lock: dummy runners of two fixture channels with fake heavy steps never overlap a heavy step
      (timestamps in the logs), and each wait prints one WAIT line
    - limit sharing: a fake limit hit by channel A makes channel B wait for the same reset time without a model call
    - quota: daily_quota 1 makes the second dummy idea wait with the IDLE line (fast clock)
    - new-channel creates a channel that preflight lists as incomplete; with the fixture files filled in, it runs in
      dummy mode
    - test-isolation.sh (both parts) passes
    - run-fake.sh meets the baseline rule. Test edits allowed: the export names and the DONE line (test-m2 and any test
      that asserts exports/N), each listed in the report
    - the dummy fingerprint with the new export names is recorded in build/M19/fingerprint/ (names normalized); M20
      compares against it
- **M20 Formats and the timeline.** 14.7, 14.8, the format keys of 14.4. Starts with the gate of 14.13.
  - Builds: pipeline/formats/problem-solution-reel/format.json (today's stages and order, session A as a session
    group, the reopen routes of the gate, the angle loop and the review, the format keys moved from config.json) and
    the runner reading it; pipeline/schemas/format.schema.json and timeline.schema.json; the timeline stage after
    13-render; pipeline/lib/timeline/ (check.py, render_ffmpeg.py); the footage-dummy test format with 3 fixture clips;
    the template folder of problem-solution-reel; the required channel files in preflight; the FlashFX-only text of the
    shared stages (12-review's prompt, pipeline/lib/review/) moved into problem-solution-reel's prompt overrides and
    config, and those allowlist entries removed (14.12).
  - Tests:
    - the dummy fingerprint of flashfx equals build/M19/fingerprint/, plus the timeline/ folder
    - timeline.json of the golden reel (or the test idea's run) validates, lasts as long as final.mp4 within 1 frame,
      and check.py finds every word, cue and composition layer
    - a copy of a finished real FlashFX run folder (from the M12 or M13 runs, migrated in M18) gets a timeline with no
      check failure
    - the footage-dummy channel runs end to end with its 3 clips: the export lasts as long as its timeline within 1
      frame, and its captions appear where the timeline says (sampled frames)
    - a format.json with a stage removed or moved changes the runner's order in dummy mode, with no code change
    - test-isolation.sh part 1 finds no FlashFX name in a shared stage
    - run-fake.sh meets the baseline rule
- **M21 Editable project export (S15).** S15, 14.9 and every line of this spec marked (M21) are built and reviewed in
  M21 only; earlier milestones are not reviewed against them. Starts with the gate of 14.13.
  - Builds: pipeline/stages/s15-project/ (capture, mapping, sprite, overlay and plate rendering, writing,
    validation, parity and layout checks) reading timeline.json (14.9), baseline-capabilities.json, the S15
    validator, pipeline/bin/editor-stable.sh (clone, advance, build, the server on port 5310, under the global editor
    lock), pipeline/bin/rebuild-project.sh <id>-N, the between-ideas steps in run.sh (stable copy, capability
    upgrade), CAPABILITIES.md, editor annotations on every component of channels/flashfx/motion-lib/ (the M9
    frame-match tests still pass), the cues.json trim and fade fields (S11's sound unchanged), the EDITOR section,
    the per-channel logs/editor-gaps.md and the root roll-up, the config.json editor block; s15-project as the last
    stage of problem-solution-reel and of footage-dummy.
  - Also: mappings for the editor's next two planned feature sets, read from §21.7 and §21.8 of the editor's
    docs/PLAN_V1_2.md (strokes, shadows and corner radii on solids, bordered text and caption boxes, progressive
    captions with emphasis words and cue fades), used only when the manifest announces them. Skip this item if
    PLAN_V1_2.md is not in the editor repo; the capability upgrade adds them later.
  - Tests:
    - the golden reel (or the test idea) gives exports/flashfx-K/project/ that passes validation (the editor CLI when
      the manifest has cli.validate, otherwise the S15 validator), with FALLBACKS.md, OPEN.txt and the EDITOR section
    - with the baseline manifest: the background, the voice and every sound effect are native clips at the right
      times; every text whose style the baseline supports is a native text clip; the captions are baked, plus the
      hidden native caption track; the layout check passes
    - with pipeline/tests/manifest-plus.json (the baseline plus the Batch 58 and 59 keys of the editor plan), the
      cards become native solids and the captions native cues (the JSON matches a golden file); with the baseline
      again they go back to sprites and baked captions
    - the animated WebP timing test: every timeline frame of a 90-frame overlay shows its own WebP frame under the
      editor's frame rule
    - the stable copy: in a scratch git repo with fake commits it advances only to a `batch-NN: review` commit whose
      batch is accepted, a failing build puts it back on the previous commit, and the server answers on port 5310
    - the project lasts as long as flashfx-K.mp4 within 1 frame, and its mix is within 0.5 LU of it
    - a forced failure still exports flashfx-K.mp4, with the minimal project and NEEDS REVIEW
    - rebuild-project.sh rebuilds a project and keeps an edited one aside
    - in the runner's fast test mode, a changed manifest between two dummy ideas triggers exactly one capability
      upgrade (dummy sessions) with its status line, also with two channels' runners alive; a failed upgrade is not
      retried for the same manifest
    - the footage-dummy channel's project passes validation, with its clips as native video clips and a native
      caption track
    - S15 takes at most 15 minutes for a 60-second reel on this laptop (the time goes in build/progress.md)
- **M22 Life of Gabry: the story.** 14.10 up to the voice, with placeholder visuals, and the youtube-shorts export for
  real. Starts with the gate of 14.13.
  - Builds: channels/lifeofgabry/ through new-channel: channel.json (youtube-shorts, scenario-story, en, lengths 45 to
    75, daily_quota 0, the export settings, enabled false until M24; the tests use --allow-disabled),
    library/profile/account.md and voice.md for the narration (drafted from 14.10, [FILL IN] where my taste decides,
    plus HUMAN_TODO), library/hooks.txt (a seed of 40 story hook templates in this channel's voice, marked as a draft
    for me to curate), library/character/gabry.md, library/voice/engine.txt (am_puck, one voice for the narrator and
    Gabry's rare lines) and pronunciations.txt, ideas.txt with 3 test premises (one per kind); the reference videos and
    the sound pack copied from channel.json sources.refs and sources.sfx when they are set (copied, never moved,
    checked by checksum); pipeline/formats/scenario-story/ (format.json, prompts, rubric, template, the export_input adapter) with
    the stages story-premise, story-facts, story-expansion, story-gate, story-hooks (with S6's judge), story-beats,
    story-script, then 08-voiceover, story-build in placeholder mode, 13-render, timeline, the youtube-shorts exporter
    and s15-project (11-sfx and 12-review join in M24); the new voice's measured pace in this channel's config
    voice.wpm; test-isolation.sh part 2 with a scenario-story fixture as channel B, plus the real-names check of 14.5.
  - The tests run in a temp REELS_ROOT holding a copy of channels/lifeofgabry/: the real exports/ and this channel's
    real history get nothing from M22, so its first real video is lifeofgabry-1 (M24).
  - Tests:
    - the 3 test premises (real models) each give the premise, the beats (a beat every 2 to 3 seconds), a script of 45
      to 75 seconds at the measured pace, words.json, a placeholder render and an export folder <id>-N with a captions
      file that passes every youtube-shorts check, and a project that passes validation
    - the gate drops one fixture premise per reason: not visual, respect, a false fact (timeline), a duplicate of an
      exported premise
    - every number in the timeline premise's script traces to a fact with a source
    - the scripts are narrated in the third person; every line carries its speaker, and Gabry's own lines are at most
      8 words and at most about 10% of a script (a script with none passes)
    - the same premise exported twice gets two descriptions that pass the difference rule
    - test-isolation.sh passes, real-names check included; FlashFX's run-fake.sh meets the baseline rule
- **M23 Life of Gabry: the look.** 14.10's Gabry and Look. Starts with the gate of 14.13.
  - If channels/lifeofgabry/styles/gabry-2d/refs/ has no reference videos when M23 starts (and channel.json
    sources.refs names no folder that has them), end BLOCKED with the HUMAN_TODO line saying where to put them: the
    style bible comes only from my references, never from a default.
  - Builds: the style bible channels/lifeofgabry/styles/gabry-2d/ from the references (analyze_refs.py, build-tokens),
    with nothing taken from FlashFX's style, motion library or section 5's Motion and energy rules; Gabry's rig and
    the gabry component (model sheet, parts, expressions, mouth shapes, poses, cycles, idle motion, the costumes
    caveman, astronaut, suit and pajamas); the 2D library in
    channels/lifeofgabry/motion-lib/ (the counts of 14.10) with catalog.json, gallery stills, players and frame-match
    notes, every component with S15's editor annotations; story-shots and the full story-build (the placeholder mode
    stays for tests); jump captions (at most 3 words on screen, a long word alone, hard cuts); lip sync on Gabry's own
    lines only; the shot plan validator (only catalog items, the safe zones, a new
    visual event at least every 3 seconds, Gabry on screen in at least half of the frames); this channel's golden
    video.
  - Tests:
    - the model sheet renders, and frame-match of every pose and expression against it holds (exact token colors, head
      to body ratio within 3 percent)
    - the walk and run cycles loop without a jump (first and last frames within the frame-match threshold)
    - on a fixture words.json with one Gabry line, the mouth shapes change within 2 frames of that line's word starts
      and the mouth rests during the narration
    - the captions of a fixture script never show more than 3 words, show a long word alone and change by hard cuts
    - every library item renders in the gallery with no console error, and the backgrounds and effects pass
      frame-match against the references
    - the golden video: a test premise end to end to a 1080x1920 render, with Gabry in at least half of the frames, a
      new visual event at least every 3 seconds (events.json) and all text inside the safe zones
    - a shot plan with an unknown item reopens story-shots instead of crashing story-build
- **M24 Life of Gabry: end to end.** The sound, the review, three real videos. Starts with the gate of 14.13.
  - Builds: this channel's sound map (build-sfx-map on channels/lifeofgabry/styles/sfx/, this format's cue types);
    the scenario-story rubric in 12-review; the full stage list of 14.10; channel.json enabled true at the end.
  - If channels/lifeofgabry/styles/sfx/ has no audio files when M24 starts, end BLOCKED with the HUMAN_TODO line (the
    pack is the one thing M24 cannot make).
  - Tests:
    - in the real folder, the 3 test premises of channels/lifeofgabry/ideas.txt back to back, unattended
      (`bash run.sh --channel lifeofgabry --once`): exports/lifeofgabry-1 to lifeofgabry-3, each with a project that
      passes validation. At the same time a dummy runner of a fixture channel runs in a temp REELS_ROOT whose
      REELS_GLOBAL_LOCKS points at this folder's .locks/: no overlap of heavy steps, no cross-channel path in either
      path trace. The real flashfx channel, its ideas and its history are not touched
    - every captions file passes the youtube-shorts checks, and the 3 descriptions pass the difference rule
    - the real-names check of 14.5 on every prompt recorded during the 3 runs (shared stages included)
    - the review rejects a planted off-model frame, a 4-second span with no visual event and a missing loop, each sent
      back to its owner stage
    - build/M24/report.md lists, per video: the length, the review rounds and scores, the time per stage, and what
      NEEDS REVIEW said

## 13. Not in version 1

Posting (I post manually from exports/); music; series; processing two ideas of the same channel in parallel; the
footage formats (Logs of Gabry, the Gabriele Bolognese vlog) and the interactive story format, beyond the design hooks
of 14.11; FlashFX-v2 (.ffx) projects as a target (the Shorts Editor project of S15 is in). (M21)

## 14. Channels, formats and platforms (M17 to M24)

From M18 on, this folder runs several channels on one engine. Sections 1 to 13 describe the engine and the FlashFX
channel. Where they name library/, styles/, motion-lib/, golden/, ideas.txt, runs/ or logs/, read the same path inside
the channel's folder, channels/<id>/ (14.3). Where they name N.mp4, Ncaptions.txt, Nhook2.mp4 or exports/N/, read the
names of section 8 (<id>-N). This section wins where it disagrees with sections 1 to 13. CHANNELS.md explains the
design; this section is the spec.

### 14.1 Terms

- **Engine:** everything shared: run.sh, pipeline/ (lib, bin, stages, formats, platforms, schemas, vendor, knowledge,
  tests), tools/, config.json, package.json and node_modules, the build tooling. It knows formats and platforms and
  never hard-codes a channel.
- **Format:** a recipe for one kind of video: an ordered list of stages from the stage library, with its own prompts,
  checks, review rubric, default settings and the list of files a channel of that format must have.
  pipeline/formats/<format>/. Two families: generated (made from nothing: research, script, voice, composition) and
  footage (cut from my recordings).
- **Platform:** where the video is posted: aspect, size, length limits, safe zones, caption rules, what the export
  contains. pipeline/platforms/<platform>/.
- **Channel:** one account: identity, audience, voice, look, hooks, sounds, ideas, runs, logs, history.
  channels/<id>/. A channel has exactly one format and one platform.
- **Channel id:** lowercase letters and digits only, starting with a letter, 2 to 24 characters
  (`^[a-z][a-z0-9]{1,23}$`), so `<id>-N` always splits at its last hyphen. In use: flashfx, lifeofgabry. Reserved:
  logsofgabry, gabrielebolognese; the interactive story channel gets its id when it is planned.
- **Format ids:** problem-solution-reel, scenario-story; reserved: footage-short, vlog-long, interactive-story.
  **Platform ids:** instagram-reels, youtube-shorts; reserved: youtube-long.

### 14.2 The channels

| id | name | platform | format | family | built in |
|---|---|---|---|---|---|
| flashfx | FlashFX | instagram-reels | problem-solution-reel | generated | M0 to M16, moved in M18 |
| lifeofgabry | Life of Gabry | youtube-shorts | scenario-story | generated | M22 to M24 (14.10) |
| logsofgabry | Logs of Gabry | instagram-reels | footage-short | footage | later (14.11) |
| (to name) | interactive stories | youtube-shorts | interactive-story | to plan | later (14.11) |
| gabrielebolognese | Gabriele Bolognese | youtube-long | vlog-long | footage | later (14.11) |

### 14.3 The channel folder

```
channels/<id>/
  channel.json      identity, platform, format, quota, config overrides (14.4)
  ideas.txt         this channel's idea queue, same format as 2.1
  library/          curated by me: hooks.txt, profile/, voice/, plus what the format needs
                    (brand/ for FlashFX, character/ for Life of Gabry)
  styles/           <style>/ (style.md, tweaks.md, vocabulary.md, tokens.json, refs/, analysis/) and
                    sfx/ (this channel's sound pack and its map, 2.6)
  motion-lib/       this channel's approved components, candidates/, gallery/
  golden/           this channel's golden videos
  runs/             one working folder per idea (machine only)
  logs/             runner.log status.txt history.txt blocked.txt suggested-ideas.txt sfx-usage.json STOPPED.md
                    descriptions.jsonl (youtube-shorts) editor-gaps.md (M21)
  .locks/           this channel's runner lock and ideas lock
```

- Inside a channel folder the layout is the old root layout, so every rule of sections 2 to 13 keeps its meaning with
  the channel folder in place of the old root.
- Shared, at the root: exports/ (section 8); logs/ with limits.log, engine.log, editor-capabilities.json,
  editor-upgrade.json and editor-gaps-all.md only (14.6, 14.9); .locks/ with the global locks (14.6); config.json and
  everything of the engine.
- Git: track channel.json, ideas.txt, the text files of library/ and styles/, motion-lib/, the golden plan files and
  the FlashFX brand kit, as today. The old .gitignore rules for these folders match only at the root (`/runs/`,
  `library/voice/*`, `styles/sfx/**/*.mp3`, `motion-lib/renders/`, `golden/*/...`), so M18 rewrites each of them
  for channels/*/ and commits the new .gitignore before the first move: channels/*/runs/, channels/*/logs/,
  channels/*/.locks/, channels/*/library/voice/* with !channels/*/library/voice/README.txt,
  channels/*/library/.hooks.index.json, channels/*/library/hooks.lint.txt, channels/*/library/character/photos/,
  channels/*/styles/*/refs/, channels/*/styles/*/analysis/, every audio extension of the old list plus .cache/ and
  previews/ under channels/*/styles/sfx/, channels/*/motion-lib/renders/, .harness/ and .hyperframes/, and the
  golden rules as channels/*/golden/*/.... The root /exports/, /logs/ and /.locks/ stay ignored. Every file that is
  ignored today must still be ignored at its new path (checked with `git check-ignore`, 14.13).

### 14.4 channel.json

Schema pipeline/schemas/channel.schema.json, validated at every start of run.sh, preflight and doctor.

- `id` (equal to the folder name), `name`, `platform`, `format`, `language` (en), `timezone` (optional, else config
  runner.timezone), `enabled` (false makes run.sh refuse the channel with one line, unless `--allow-disabled` is
  given, which tests and checks use).
- `daily_quota`: exports per calendar day in the channel's timezone; 0 means no limit.
- `brand`: display_name, handle, and anything the format's prompts may name. Never another channel's name.
- `export`: platform settings this channel overrides (section 8), for youtube-shorts: caption_max, description_max,
  hashtags, required_hashtags, pinned_comment.
- `sources` (optional): folders M22 copies curated material from on first setup: `refs` (reference videos) and
  `sfx` (a sound pack), written in Windows form (C:/Users/..., like config.json, because Windows Python reads them).
  Copied, never moved, checked by checksum.
- `config`: a partial config.json for this channel.

The resolved config has three levels, deep-merged in this order (objects merge key by key; arrays and scalars
replace): config.json (engine), the format's `config` block in format.json (from M20), the channel's `config` block.
Every script reads the resolved config through config.sh or config.py; nothing reads config.json directly.

- Channel-owned keys live only in channel.json: style, voice, sfx, lengths, and the paths in config `paths` that
  point at channel data (resolved against the channel folder, 14.5). M18 moves them from config.json into
  channels/flashfx/channel.json with their values unchanged.
- Format-owned keys move into format.json in M20: research, hooks, judge, script, visual, caption, and review except
  its four safety keys (for problem-solution-reel). Until M20 they stay in config.json.
- Engine keys stay in config.json: models, tts (device, whisper settings), caps, errors, timeouts, runner, render,
  preflight, logs, editor, the engine paths, and the safety keys of review: reviewer_tools, fixer_tools, fixer_paths
  and protected_paths. From M18 the protected paths are resolved for every channel (channels/*/ideas.txt,
  channels/*/library/, channels/*/styles/) plus exports/, and fixer_paths for the run's channel (pipeline/ and
  channels/<id>/motion-lib/candidates/); protect.py snapshots and restores those. A channel may override any key
  except the safety keys; doctor prints every engine key a channel overrides.

FlashFX after M18 (shape; the values are the ones config.json has today):

```json
{
  "id": "flashfx", "name": "FlashFX", "platform": "instagram-reels", "format": "problem-solution-reel",
  "language": "en", "enabled": true, "daily_quota": 0,
  "brand": { "display_name": "FlashFX" },
  "config": { "style": "paper-cards", "voice": { "wpm": 186 }, "lengths": { "default_s": [25, 40] }, "sfx": {} }
}
```

### 14.5 Paths and isolation

- One module knows the layout: pipeline/lib/paths.sh and pipeline/lib/paths.py, with the same answers (a test
  compares them). They set REELS_REPO (the engine), REELS_ROOT (the state root, as today: the repo unless set; tests
  point it at a temp folder), REELS_CHANNEL (the id), REELS_CHANNEL_ROOT (REELS_ROOT/channels/<id>), REELS_EXPORTS
  (REELS_ROOT/exports) and REELS_GLOBAL_LOCKS (REELS_ROOT/.locks unless set: a test in a temp REELS_ROOT may point it
  at the real folder's .locks/ to share the heavy lock with a real runner), and provide `chpath <relative>` (bash) and
  `paths.ch(relative)` (Python) for channel data. REELS_IDEAS, REELS_LOGS and REELS_LOCKS keep their names and now
  point inside the channel folder. The relative paths in config `paths` are resolved against the channel folder for
  channel data and against REELS_ROOT for exports.
- Every stage, script and helper builds paths to channel data only through this module. pipeline/tests/
  test-isolation.sh part 1 (static) fails on any literal path to library/, styles/, motion-lib/, golden/, ideas.txt,
  runs/, logs/ or exports/ in pipeline/, run.sh or tools/ outside paths.sh and paths.py. Exceptions (comments, docs,
  test fixtures) are listed one by one, with the reason, in pipeline/tests/isolation-allowlist.txt.
- Engine code never names a channel id, a brand or a style. FlashFX names are allowed only inside the
  problem-solution-reel format folder (14.12); the ones that sit today in shared stages (for example the DM card and
  lockup rules in 12-review's prompt and in pipeline/lib/review/) move into that format's prompt overrides and config
  in M20. Until they move they are listed in the allowlist; new code gets no such entry.
- A channel never reads another channel's folder:
  - model calls: a prompt is built only from the format's prompt files, its channel's files and its own run. Sessions
    (session A, review and judge sessions) belong to one run and are never resumed by another channel's run.
  - code: while REELS_CHANNEL is set, the path module refuses (exit 3, an ERROR line) any resolved path inside
    channels/<another id>/ and any export folder of another channel.
  - the reviewer and fixer of 4.2 get the engine, the failing run and its channel; their prompts name no other channel
    folder; the fixer may edit only pipeline/ and channels/<id>/motion-lib/candidates/ (fixer_paths), model calls may
    not write to any protected path (14.4), and an autofix commit that touches any other path under channels/ is
    refused.
  - memory files are per channel: history.txt, blocked.txt, hook statistics, sfx-usage.json, suggested ideas, golden
    videos, review notes, descriptions.jsonl, editor-gaps.md.
- test-isolation.sh part 2 (canary): two fixture channels in a temp REELS_ROOT, each with a unique canary word in
  every curated file (profile, voice.md, hooks.txt, style files, brand or character files, ideas.txt, channel.json
  brand). For every model-calling stage of each channel's format, the prompt the stage would send is composed through
  the stage's own code with the model call replaced by a recorder (which also records every file path passed, such as
  screenshots). Pass: no canary of B in anything recorded for A, and the reverse. With REELS_PATH_TRACE=1 the path
  module logs every path it resolves; during A's dummy run every logged path is inside the engine, channels/A/ or
  exports/A-*/.
- Once two real channels exist (M22, M24), the real-names check joins part 2: each real channel's id, brand name and
  style id (flashfx, FlashFX, paper-cards; lifeofgabry, Life of Gabry, gabry-2d) are canaries in every recorded prompt
  of the other channel, shared stages included, plus lines picked from each channel's curated files.

### 14.6 Running channels side by side

- `bash run.sh --channel <id> [--once]`, or REELS_CHANNEL=<id> (the tests use it). Without a channel: exit 2 and print
  the channels with their status. An unknown id, or a disabled one without --allow-disabled: exit 2.
- One runner per channel at a time (the channel's runner lock, as M1's lock today). Runners of different channels may
  run at the same time, each in its own terminal.
- Heavy steps take turns: text to speech, transcription, every HyperFrames render, ffmpeg encodes longer than 10
  seconds, analyze_refs, frame-match and S15's capture run inside `heavy` (pipeline/lib/heavy.sh), which holds the
  global lock .locks/heavy.lock (the same lock mechanism as M1, with stale lock detection by pid). A runner that waits
  prints one WAIT line ("WAIT heavy: lifeofgabry S13 render holds it since 14:02"), and its heartbeat shows the wait.
- Usage limits are account-wide: when a runner hits a limit (section 4) it writes the reset time to .locks/limit.json;
  every runner reads that file before each model call and waits for the same time instead of calling. logs/limits.log
  at the root keeps every wait with its channel id.
- Daily quota: when a channel has exported daily_quota videos today, its runner goes idle with an IDLE line ("IDLE
  quota 2/2 today, next idea after 00:00") and checks again after midnight in the channel's timezone.
- The stable editor copy (S15) is advanced between ideas by whichever runner gets there first, under the global lock
  .locks/editor.lock, so two runners never advance or rebuild it at once.
- runner-status without arguments prints one block per channel (alive or not, the latest status line, today's exports
  against the quota) and the global locks; `--channel <id>` prints one channel. doctor checks the engine once, then
  every channel (or one, with --channel).
- logs/engine.log at the root holds global events only: heavy lock waits over 10 minutes, shared limit waits, the
  editor copy advancing or rolling back.

### 14.7 Formats and the stage library

- pipeline/stages/ is the stage library: one folder per stage, as today (run.sh, CONTRACT.md, schema.json, prompts,
  dummy.sh). A stage used by more than one format is generic (08-voiceover, 11-sfx, 12-review, 13-render, timeline,
  the exporters, s15-project): it reads what differs from the resolved config, the format and the channel's files,
  never from a test on the channel id.
- pipeline/formats/<format>/format.json (schema pipeline/schemas/format.schema.json): id, family (generated or
  footage), the platforms it supports, its `config` block (14.4), the stages in order (each with its stage folder,
  optional prompt overrides from pipeline/formats/<format>/prompts/, its session group, its caps and its reopen
  routes), the review rubric file, the required channel files, and the template folder
  (pipeline/formats/<format>/template/: the files new-channel copies, with [FILL IN] markers).
- Preflight checks the required channel files of the channel's format; a missing one is a systemic stop for that
  channel only (STOPPED.md in the channel's logs).
- The runner takes the stage order, the session groups and the reopen routes from format.json, never from a
  hard-coded list. The run folder has one subfolder per stage named like the stage folder (as today), so
  problem-solution-reel runs look exactly as before, plus timeline/.
- problem-solution-reel = today's S1 to S13 in today's order, then timeline (M20), then S14, then s15-project (M21),
  which runs on the assembled export before the move to exports/ (S15).
- scenario-story: 14.10.
- A test-only footage format, footage-dummy (pipeline/tests/formats/footage-dummy/), proves that the footage family
  runs through the same runner: ingest (dummy), cut (dummy: writes timeline.json from fixture clips), render from the
  timeline (real, ffmpeg), export, project.
- `pipeline/bin/new-channel <id> --format <format> --platform <platform> [--name "..."]` checks the id, creates
  channels/<id>/ from the format's template and the platform's defaults, an empty ideas.txt and channel.json with
  enabled false, and prints what I must fill in; `preflight --channel <id>` lists every missing file. A channel of an
  existing format and platform needs no engine change; a new format or platform is engine work.

### 14.8 The timeline

- Every run of every format ends its production stages with runs/<run>/timeline/timeline.json (schema
  pipeline/schemas/timeline.schema.json, version 1): the final video as layers in time. Footage formats render from
  it; the exporters read the length and times from it; S15 builds the editor project from it (14.9). For generated
  formats the HyperFrames composition stays the render source and the timeline describes it.
- Content:
  - settings: width, height, fps (num, den), duration in frames, sample rate, background color
  - sources: every media file used (path relative to the run or the channel folder, kind video, image, audio or
    composition, duration, size, sha256)
  - visual layers, bottom to top: id, name, kind (composition-scene, footage, still, sprite, text, caption-burn),
    source with in and out, start and end frame, transform keys, opacity keys; for composition layers the element's
    selector in the composition (S15's data-ed-layer) and its component id in the channel's motion library
  - captions: chunks with text, start and end, each word with start, end and emphasis, the caption style id from the
    channel's style
  - audio: the voice (file, gain), every sound effect (file, start, trim, fades, gain, cue type), footage audio (clip,
    in and out, gain, fades); music is reserved
  - markers: scene and beat starts with labels, the hook end, the loop point (scenario-story), the keyword moment
    (problem-solution-reel)
  - provenance: the stage that produced each item
- The timeline is a record, not a new decision: nothing in it may contradict the plans, words.json, cues.json or the
  composition it came from. pipeline/lib/timeline/check.py compares them: duration within 1 frame of final.mp4, every
  word and cue present at its time, every composition layer found in the composition.
- Footage formats write it from their cut decisions (14.11) and render it with pipeline/lib/timeline/render_ffmpeg.py
  (trims, concatenation, crossfades, burned captions, the audio mix, loudness).

### 14.9 The editable project on the timeline (S15, built in M21)

S15 (section 5) is built in M21 as written, with these changes:
- Its single input index is timeline.json: the composition, words, cues, plans, events, tokens, brand assets and fonts
  S15 lists are reached through it, not by name.
- It runs for every format as the last stage of format.json. Footage layers (clips, stills) map to native clips;
  composition layers use S15's capture and its fallback levels (native, sprite, overlay, plate) as written.
- The project goes to exports/<id>-N/project/. The EDITOR section of the captions file names that path, and the editor
  link is `<editor.url>?open=exports/<id>-N/project`.
- Editor annotations go on every component of every channel's motion library (channels/<id>/motion-lib/); Life of
  Gabry's library (M23) is built with them from the start.
- logs/editor-gaps.md is per channel; S15 also rewrites the root roll-up logs/editor-gaps-all.md (the gaps of all
  channels, for the editor's backlog; no channel reads it).
- The editor block, the stable copy, port 5310 and the capability upgrade stay engine-level (config.json, root logs/).

### 14.10 Life of Gabry (lifeofgabry): scenario-story on youtube-shorts

**Identity**
- Fake scenario stories for pure entertainment, all lived by one 2D cartoon character, Gabry: "What if the dinosaur
  asteroid hit Earth today, minute by minute", "What if you were the only man in a women's world", "What if you could
  hear everyone's thoughts for a day".
- youtube-shorts, 9:16, 1080x1920, 30 fps, 45 to 75 seconds (config lengths), English.
- Audience: a broad audience, mostly 16 to 34, who watch what-if and animated story Shorts with the sound on and swipe
  fast: the premise must land in the first 2 seconds.
- Tone: curious, playful, a little dramatic. The jokes come from the situation, never from putting a group of people
  down. No promotion, no products, no links, no real people or brands, nothing from any other channel.
- Visuals: 2D animation written as code (SVG and HyperFrames with GSAP), never AI video or AI images, never motion
  graphics cards. Its own voice, its own sound pack, its own look.

**Gabry**
- The one character of every video, always on model. His bible: channels/lifeofgabry/library/character/gabry.md:
  personality (curious, optimistic, reacts big, a bit clumsy, brave at the end), what he never does (mean jokes,
  swearing), how the narration refers to him, recurring gags (used sparingly).
- His rig, built as code in M23 in channels/lifeofgabry/library/character/gabry/ (curated by me once M23 is approved):
  - a model sheet (front, three quarter, side) with fixed proportions (head to body ratio, eye size, line weight) and
    fixed colors from tokens.json
  - parts as separate SVG groups: head, hair, brows, eyes (open, half, closed, looking left, right, up, down), mouth,
    torso, upper and lower arms, hands (open, fist, point, thumbs up, holding), legs, feet
  - 8 expressions: neutral, happy, excited, surprised, scared, sad, angry, thinking
  - 8 mouth shapes: rest, A/I, E, O, U, M/B/P, F/V, L/TH (lip sync is used only when Gabry speaks, see Narration)
  - poses: stand, walk cycle (8 drawings), run cycle (6), sit, point, shrug, jump, fall, panic, think, wave, look at
    camera
  - costume layers per scenario (caveman, astronaut, suit, pajamas, more as scenarios need them); the face, colors and
    proportions never change
  - one HyperFrames component `gabry` with props: pose, expression, facing, costume, position, scale, mouth track
    (from words.json), and idle motion (a blink every 3 to 5 seconds, breathing)
- His look (open question 3): an original cartoon design, not a likeness of me, so Logs of Gabry (the real me) and
  Life of Gabry stay separate worlds. "Gabry" is only a name; it could as well be John. What matters is that he is
  recognizable at a glance and the same in every video: a distinctive silhouette, hair and outfit, and colors that
  never change (the model sheet fixes them).

**Narration** (open question 1): one narrator voice tells the story in the third person ("Gabry wakes up and the sky
is orange"), about 90% of every video. Occasionally, and not in every video, Gabry says a short line himself (about
10% of the lines at most, many videos with none, each line at most 8 words), in the same Kokoro voice as the narrator;
story-script marks who says each line (narrator or gabry). Otherwise he reacts with expressions, gestures and short
speech bubbles (at most 4 words). Lip sync is used only for his own lines.

**Voice**: Kokoro, this channel's own channels/lifeofgabry/library/voice/engine.txt: default voice am_puck, speed
1.1, one voice for the narrator and for Gabry's rare lines; M22 measures its pace into this channel's config
voice.wpm. Its own pronunciations.txt. Never the voice of another channel.

**Ideas**: channels/lifeofgabry/ideas.txt, braces format of 2.1: one premise per idea, optional notes. Three premise
kinds (story-premise decides): timeline (a real event or process told minute by minute or day by day; needs facts),
world rule (the world changes one rule, social or physical), personal power (Gabry gets an ability or a constraint for
a day).

**Stages** (stage folders in pipeline/stages/; generic stages marked)
1. story-premise: the premise card: the question as a hook line, the kind, the setting, Gabry's starting situation,
   the rule or event, the payoff idea, the loop idea (the last line leads back into the first frame).
2. story-facts: timeline premises only, or any premise that states real numbers: light research with sources, like
   S1 but smaller (at most 8 facts, each with a source). Every number in the script must come from here. Other kinds
   skip it (done with `skipped: true`).
3. story-expansion: the stakes, Gabry's goal, the escalation ladder (5 to 8 steps, each bigger than the last), one
   twist, the payoff, the loop; 600 to 1500 characters.
4. story-gate: scores 1 to 5 for: premise clear in one line, escalation, visual potential (can be drawn with the
   library plus a few new props), payoff, freshness against this channel's history; plus two pass or fail checks:
   respect (no humor that puts a group down, no real people or brands, nothing gory or sexual) and facts (timeline
   premises). Pass: every score at least 3 and both checks pass. A low score gets one rework round from
   story-expansion; a second failure drops the idea with the scores in the history line; a respect or facts failure
   drops it at once. A dropped idea may leave a sibling premise in suggested-ideas.txt.
5. story-hooks: candidates from this channel's hooks.txt (its own library: question hooks, countdown hooks, "you wake
   up and" hooks, stakes hooks), filled for the premise, each with a one-line first-frame idea; S6's judge machinery
   picks two with this format's rubric (clear in 2 seconds, curiosity, matches its first frame).
6. story-beats: the timed beat sheet, a beat every 2 to 3 seconds (18 to 30 beats): index, target time, the line and
   who says it (the narrator, or rarely Gabry), action, Gabry's pose and expression, setting, props, camera (static,
   push in, pan, shake, zoom punch),
   on-screen text (for timeline premises a counter such as "T+00:01" or "DAY 3"), the sound idea. Beat 1 is the hook;
   the last beat sets up the loop.
7. story-script: the narration from the beats in this channel's voice (voice.md), in the third person, at its
   measured pace; each line marked with its speaker (narrator or gabry). Checks: the length range, the words of each
   beat fit its time, every number traced to story-facts, no line over 18 words, Gabry's own lines at most 8 words and
   at most about 10% of the lines (none is fine), the loop line present, plain words, no promotion, humanize.py and
   the slop list as in S7.
8. 08-voiceover (generic): this channel's engine.txt and pronunciations; words.json as today.
9. story-shots: the shot plan from the beats and words.json: per shot the background, every character and prop with
   position, pose, expression and facing, effects, camera move, text overlays, caption chunks, transitions in and out,
   all on the spoken words' times. Only items from this channel's motion-lib catalog; a missing item follows the
   candidates rule of S10.
10. story-build: compiles the shot plan into a HyperFrames composition with the gabry component, backgrounds, props,
    effects, text, transitions and captions (jump captions: at most 3 words on screen at a time, a long word alone
    (8 letters or more by default, set in the style bible), each chunk replaced by a hard cut on the next spoken words,
    no fades, in this channel's caption style); lip sync from words.json on Gabry's own lines only (the lines
    story-script marks as gabry); the 540x960 draft, the contact sheet and events.json (every visual event, for the
    sound stage). Until M23, a placeholder mode renders each beat as a plain card with its narration.
11. 11-sfx (generic): this channel's pack and map; this format's cue types (impact, whoosh, pop, boing, rumble, riser,
    sting, an ambience bed per setting); density, spacing and levels from this channel's config sfx.
12. 12-review (generic): this format's rubric (below), the same loop as today (3 opus rounds, then 2 fable rounds, then
    the export with NEEDS REVIEW).
13. 13-render (generic), then timeline (generic).
14. The youtube-shorts exporter (section 8), then s15-project (generic, M21).

**Review rubric**
- The premise is clear by 2 seconds: the hook line is spoken or on screen, and the first frame shows the situation.
- A new visual event at least every 3 seconds (from events.json: a cut, a camera move, a pose or expression change, a
  prop or an effect).
- Gabry on model in every frame he is in: sampled frames frame-matched against the model sheet (exact token colors,
  head to body ratio within 3 percent).
- Text readable inside the youtube-shorts safe zones, at the minimum sizes, with enough contrast.
- Lip sync, only on Gabry's own lines: mouth shape changes within 2 frames of word starts; his mouth rests during the
  narration.
- Captions: jump captions only (at most 3 words on screen, a long word alone, hard cuts, no fades).
- Audio: the voice transcribed from the mix with a word error rate under 5 percent, sounds under the voice by the
  config margin, loudness -14 LUFS.
- The loop: the last second leads into the first, in words and image (judged on the first and last filmstrips).
- The story: escalation felt, payoff lands, nothing confusing; the respect check again on the final script and frames.
- Length in range; every number traced to story-facts.

**Look (M23)**
- Style bible from my reference videos only: channels/lifeofgabry/styles/gabry-2d/ (style.md, tweaks.md,
  vocabulary.md, tokens.json, refs/, analysis/), the same structure and tools as paper-cards (analyze_refs.py,
  build-tokens): palette, outline weight, shading, shot length, cuts per 10 seconds, camera habits, text and caption
  style, effects. The style is simpler than FlashFX's: nothing from FlashFX's motion graphics, its motion library or
  the Motion and energy rules of section 5 transfers to this channel. When something in the look is wrong, I correct
  the style bible itself (style.md, tweaks.md), and the library follows it.
- References (open question 2): 5 to 10 videos in channels/lifeofgabry/styles/gabry-2d/refs/ (the folder M22
  creates), which I add after M22, or copied by M22 or M23 from channel.json sources.refs when I name a folder
  (copied, never moved, checked by checksum). Without references M23 builds no default bible: it stops before the
  style bible with a HUMAN_TODO line saying where to put them, and the build continues when they are there.
- The 2D library in channels/lifeofgabry/motion-lib/ (HyperFrames components, catalog.json, gallery, frame-match, as
  M9), every component with S15's editor annotations:
  - backgrounds: at least 12 settings (bedroom, kitchen, city street, office, school, park, beach, desert, prehistoric
    jungle, space orbit, Earth from space, a TV news studio), each with 2 or 3 parallax layers and day and night
    variants through tokens
  - props: at least 30 (phone, clock, calendar, TV, car, asteroid, rocket, food, money, signs, ...)
  - effects: impact flash, screen shake, dust puff, speed lines, explosion, smoke, sweat drop, question marks, hearts,
    anger mark, sparkles, fire, rain, snow
  - text: time counter, big title, label with arrow, speech bubble, thought bubble, caption chunk
  - transitions: cut, iris wipe, whip pan, zoom through, match cut on Gabry, fade to black
  - camera: push in, pull out, pan, tilt, shake, zoom punch, slow drift
  - other characters: a crowd (simple figures in 3 variants and token colors) and 4 generic side characters built from
    the rig parts with other hair and clothes; never real people
- A golden video in channels/lifeofgabry/golden/: one test premise end to end (plan and render), the example the shot
  director reads.

**Sound pack**: channels/lifeofgabry/styles/sfx/, cartoon and cinematic sounds (impacts, whooshes, pops, boings,
rumbles, risers, stings, ambiences), mapped by build-sfx-map like FlashFX's pack. M22 copies it from channel.json
sources.sfx when I name a folder; otherwise I put the files there before M24.

**Safe zones** (pipeline/platforms/youtube-shorts/platform.json, adjustable): keep text and Gabry's face out of the
bottom 20 percent (title and channel row), the right 12 percent of the lower half (the buttons) and the top 6 percent.

### 14.11 Later channels (requirements only, so the engine stays ready)

- logsofgabry (footage-short, instagram-reels): I record myself, with my own voice. The runner edits: transcript, cuts
  of dead air, retakes and setup moments, captions, punch-ins, simple overlays, its own sounds. No TTS, no script
  writing: the script is what I said.
- Interactive stories (format to plan, youtube-shorts): nothing is built until it is planned.
- gabrielebolognese (vlog-long, youtube-long): my life vlog. Many clips, long footage, simple editing: cut the setup
  moments (setting up the camera, walking to it, silence), keep the highlights, make short montages, add captions. No
  hook, script or research.
- How the footage family stays cheap in tokens (built with the first footage channel; the engine is ready from M20):
  1. Ingest, code only, no model: per clip ffprobe metadata, faster-whisper word timings with confidence, the silence
     and loudness profile, shot boundaries (ffmpeg scene score), motion energy per second, one small thumbnail (320 px)
     per shot and one every 10 seconds, tiled into contact sheets of 12.
  2. The clip index: one text line per shot or per 5 to 15 second segment (clip, in, out, the words said, loudness,
     motion, flags such as silence or a suspected camera setup: a long static start, "ok" said to the camera, walking
     away), about 15 to 30 tokens per line. An hour of footage is a few hundred lines.
  3. Cut decisions: code first drops the obvious (silence, setup patterns); the model reads the index plus only the
     contact sheets it asks for (never the video, never every frame) and writes JSON decisions (keep, drop, montage
     group, highlight score, caption on or off), in passes from coarse to fine.
  4. Code turns the decisions into timeline.json and renders it; the review checks filmstrips and the transcript.
  5. Ingest results are cached per clip by hash, so a re-run or an edit costs no new transcription and no new tokens.

### 14.12 FlashFX names inside problem-solution-reel (deferred)

The problem-solution-reel format names FlashFX in places (the solution type flashfx, the brand rules of S7 and S14,
its prompts). Those names are allowed only in the format's own stages (S1 to S7, S9a to S9c, S10, S14) and in
pipeline/formats/problem-solution-reel/; the ones in shared stages move there in M20 (14.5). That is fine while FlashFX
is the format's only channel. When a second channel uses this format, the names move into channel.json `brand`
(solution type `own`) as engine work. Until then they are listed in pipeline/tests/isolation-allowlist.txt.

### 14.13 Moving files (M17 plans, M18 and M19 execute)

Rules for every move in this folder, tracked or not, so nothing I made is lost:
- The move manifest decides everything: one line per move, in execution order, with old path, new path, git state
  (tracked, untracked, ignored), method (git-mv, fs-mv, rename-in-place, rewrite, stays), files, bytes, check (sha256
  or count-and-bytes), reason and milestone (M18 or M19). pipeline/tests/make-manifest.py writes it from the folder as
  it is, by fixed rules (deterministic). M17 writes build/M17/move-manifest.tsv as the plan.
- Coverage: every file in the folder, whatever its git state, is covered by exactly one line (its own, or the line of
  a folder that contains it), or belongs to the engine. Ignored files inside a moved folder (engine.txt and the voice
  references, the sound pack's audio, refs/, analysis/, renders) are covered by their folder's line and move with it.
- Fresh before executing: the video runner keeps adding runs, logs and exports after M17. Right before its moves, with
  the runner stopped, M18 (and M19 for its lines) runs make-manifest.py again, checks the result with
  check-manifest.py, and writes build/<milestone>/manifest-diff.md (what changed since M17's plan, and why). The
  executed manifest is build/<milestone>/move-manifest.tsv.
- Unfinished runs always move with their channel and resume after the move; nothing waits for my decision.
- Tracked files the runner writes (library/.hooks.stats.json, library/hooks.suggested.txt) change on every real run:
  M18 commits them as they are ("chore: snapshot runner-written files before the move") before migrating.
- pipeline/bin/migrate-channels executes the manifest:
  - `--dry-run` prints every step and every check and changes nothing
  - first, when build/<milestone>/migration-log.tsv shows an earlier attempt without its final "verified" line (a kill
    or crash during the moves), it runs that attempt's undo, checks the folder against that attempt's before-listing,
    and only then starts again
  - it refuses to start while any video runner is alive (any channel lock, or the old root lock), while git has
    uncommitted changes outside the current milestone's files, or with less than 2 GB free
  - tracked files: `git mv`; untracked and ignored files: a rename on the same drive; never copy then delete, except
    when a rename is impossible: then copy, verify the checksum, delete the original, and log it; retries for
    OneDrive file handles, like the runner's moves
  - rewrites: in every text file under the moved runs/ folders (except the raw model outputs, calls/*.json), in every
    captions file and in the history lines, every old path is replaced in all its forms: root-relative
    (styles/paper-cards/...), absolute in C:/ and /c/ form, and with backslashes (styles/paper-cards\\analysis). Each
    rewritten file is first copied, at its relative path, under build/<milestone>/premigrate/. Tracked test fixtures
    (pipeline/tests/fixtures/) are rewritten only where a test needs it, each listed in the report.
  - it writes build/<milestone>/migration-log.tsv (every step with its result, and a final "verified" line on
    success) and build/<milestone>/undo-migration.sh (the exact reverse)
  - after the moves it verifies:
    - every new path exists with the same checksum, or the same count and bytes; no moved folder exists any more at
      its old path; a full listing of the folder (paths and sizes) taken right before and right after differs only by
      the manifest's lines
    - `git status --porcelain` shows only renames (R) of the moved tracked files (the new .gitignore was committed
      before), and `git check-ignore` passes at the new path for every file that was ignored at the old one
    - no old path, in any of the forms above, is left in the rewritten files
  - on any failed check it runs the undo, verifies that the folder is back as it was, and the batch ends BLOCKED with
    the reason
- Rehearsal first: the script runs on a fixture tree built from the inventory (the same names and structure with
  small files, set up as a git repo with the same .gitignore and the same tracked files, plus one finished and one
  unfinished run copied from the test fixtures), then the undo, then again. Only after the rehearsal passes does it run
  on the real folder.
- The gate: M19 to M24 each start by checking that the moves done so far still hold (check-manifest.py --after on the
  executed manifests) and that `preflight --channel flashfx` passes. If not, the batch ends BLOCKED with the failures:
  the milestone before may have moved on without approval (build/open-issues.md).
- Old exports (M19): exports/N/ becomes exports/flashfx-N/, with N.mp4, Ncaptions.txt and Nhook2.mp4 renamed to
  flashfx-N.mp4, flashfx-Ncaptions.txt and flashfx-Nhook2.mp4, project/ unchanged; inside the captions file the HOOKS
  names, the RUN path and the EDITOR path follow; history lines "exported N" become "exported flashfx-N".
