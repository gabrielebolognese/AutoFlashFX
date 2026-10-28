# CHANNELS: one engine, many channels (milestones M17 to M24)

This file explains how this folder grows from one channel (FlashFX) to several fully separate channels that share
one engine, and it carries the exact text that goes into BUILD_SPEC.md.

- Part A explains the design in plain words (for me and for every session).
- Part B is BUILD_SPEC.md text, between `<!-- BEGIN ... -->` and `<!-- END ... -->` markers, copied by a script into
  BUILD_SPEC.md (new section 14, replacements of sections 1, 8, 13 and the M17 milestone, additions to sections 3,
  9, 11). After the merge, BUILD_SPEC.md is the source of truth; this file stays as the explanation.
- Part C lists the open questions and the defaults used until I answer.
- Part D lists the changes to build-runner.sh.

Numbering: this plan was first written as milestones M14 to M21. The motion milestones M14 to M16 (BUILD_SPEC.md
section 5, Motion and energy rules) came first, so the plan runs as M17 to M24: the control check is M17 and the
editable project (the old M17, S15) is M21.

Hard rule everywhere: never write an em dash.

---

## Part A. The design, explained

### A.1 Why not duplicate the folder

The plan is five channels: FlashFX (Instagram, faceless, problem and solution reels), Logs of Gabry (Instagram, my own
recorded videos and voice, edited by the runner), Life of Gabry (YouTube Shorts, fake scenario stories with a 2D
cartoon Gabry), an interactive story channel (YouTube Shorts, still to plan) and Gabriele Bolognese (YouTube long form,
my life vlog, many clips, simple editing).

Duplicating the folder per channel looks isolated but costs more every week: two copies of the runner, the limits
handling, the review loop, the renderer and the editor exporter drift apart; every fix has to be made twice; and two
copies running on one CPU-only laptop with one Claude Max account fight over the CPU and the usage limits without
knowing about each other. So: one engine, many channels, with isolation enforced by code and by tests.

### A.2 Three layers

| Layer | What it is | Where | Examples |
|---|---|---|---|
| Engine | the machinery every channel uses | run.sh, pipeline/, tools/, config.json | the runner loop, ai(), limits, the error and fix loop, TTS and Whisper workers, HyperFrames rendering, ffmpeg, the review framework, the platform exporters, the editor project exporter |
| Format | a recipe for one kind of video | pipeline/formats/<format>/ | problem-solution-reel (FlashFX): research, gate, hooks, script, voice, motion cards, sound, review. scenario-story (Life of Gabry): premise, beats, script, voice, 2D shots, sound, review |
| Channel | one account's identity and memory | channels/<id>/ | voice, profile, audience, hooks, style, motion library, sound pack, ideas, runs, logs, history, quota |

A platform (Instagram Reels, YouTube Shorts, later YouTube long form) is a small fourth piece: aspect, length limits,
safe zones, caption rules and what the export contains. Each channel picks exactly one format and one platform.

### A.3 "They must not even know the other exists"

At runtime a channel's run sees only three things: the engine, its own format, and its own channel folder. Concretely:

- every path to channel data is built by one module (paths.sh and paths.py), which refuses any path into another
  channel's folder
- every prompt is composed from the format's prompt files plus this channel's files plus this run, nothing else
- history, blocked ideas, hook statistics, sound rotation, golden reels, review notes and editor gaps are per channel
- a test plants a unique canary word in every curated file of two fixture channels and proves that no prompt and no
  file read of one channel ever contains the other's canary

The engine code obviously knows that several formats exist; the content never crosses.

### A.4 Two families of formats

- Generated: the video is made from nothing (idea, research, script, voice, composition written as code, sound,
  review, render). FlashFX and Life of Gabry.
- Footage: the video is cut from my recordings (Logs of Gabry, the vlog). The model never watches video: code turns
  the footage into a compact text index (word timed transcript, shots, silences, loudness, small contact sheets) and
  the model writes cut decisions from that index. An hour of footage becomes a few hundred short lines, not millions
  of image tokens. Only the design hooks are built now (a dummy footage format in the tests); the real footage formats
  come later.

### A.5 The timeline file

Every format ends with the same file: timeline.json, the final video described as layers in time (visual layers,
captions with word timings, voice, sounds, footage audio, markers). The editor project exporter reads only that file,
so one exporter serves every channel: FlashFX reels and Life of Gabry shorts both open in the Shorts Editor, and so
will footage videos later. Footage formats also render from it with ffmpeg.

### A.6 What changes for me day to day

- Start a channel: `bash run.sh --channel flashfx` or `bash run.sh --channel lifeofgabry` (one terminal each; heavy
  steps like voice, transcription and renders take turns automatically; a usage limit pauses every runner together).
- Ideas: each channel has its own queue, channels/<id>/ideas.txt. In Claude Code I write `{...} for life of gabry`.
- Exports: still in exports/ at the root, shared, now named by channel: exports/flashfx-12/flashfx-12.mp4,
  flashfx-12captions.txt, flashfx-12hook2.mp4, project/. Life of Gabry: exports/lifeofgabry-3/lifeofgabry-3.mp4 and
  lifeofgabry-3captions.txt (caption, description, pinned comment). N counts each channel's videos in build order.
- My curated files move into the channel: channels/flashfx/library/, channels/flashfx/styles/, and so on. Same
  structure as today, one level deeper.
- A new channel of an existing format: `bash pipeline/bin/new-channel <id> --format <format> --platform <platform>`,
  then fill in the files it lists. A new kind of video (a new format) is engine work: new stages plus a format.json.

### A.7 The order of work

| Milestone | What | Why at this point |
|---|---|---|
| M17 Control check | inventory, test baseline, move manifest, reference index; no behavior change | nothing moves before every file has a planned destination and the tests have a baseline to compare with |
| M18 Channels | the path module, --channel, channel.json, FlashFX moved into channels/flashfx/ | refactoring is cheapest now, with one channel and no editor exporter yet |
| M19 Exports and channels side by side | the `<id>-N` exports, old exports renamed, platform exporters (Instagram, YouTube Shorts), heavy lock, shared limits, quotas, the canary test | the shared export folder and the shared machine need rules before a second channel exists |
| M20 Formats and the timeline | format.json drives the runner, timeline.json, a dummy footage format | the editor exporter is built once, on the timeline, for every channel |
| M21 Editable project export | the old M17 (S15), rebuilt on the timeline | both styles must open in the Shorts Editor |
| M22 Life of Gabry: the story | the channel, its story stages, its voice, the YouTube Shorts export with placeholder visuals | the story machine is proven before the art is built |
| M23 Life of Gabry: the look | style bible, the Gabry rig, the 2D library, shots and build, golden reel | the look is the biggest piece and needs the stories to test against |
| M24 Life of Gabry: end to end | sound pack, review rubric, three real videos next to a FlashFX runner | the proof that both channels run side by side without touching each other |

### A.8 How the moves are done without mistakes

I never move, rename or edit anything by hand. Claude does every move, with these safety rails:

1. M17 writes a move manifest: one line per move (old path, new path, tracked or not, method, file count, bytes,
   how it is verified). Nothing moves that is not in it, and every file in the folder has a line or is engine.
2. A script (migrate-channels) executes the manifest. It has a dry run, refuses to run while a video runner is alive,
   uses `git mv` for tracked files and same-drive renames for everything else, never copies-then-deletes unless it
   has verified the copy, and writes an undo script.
3. It rehearses first on a fixture copy of the folder structure (migrate, undo, migrate again), and only then runs on
   the real folder.
4. After the real run it verifies every file by checksum or count and size and compares a full before and after
   listing. If anything is off, it undoes itself and the build stops with the reason.
5. The manifest is generated again right before the moves (the video runner keeps adding runs between M17 and M18),
   with the same rules, and the difference from M17's plan is written down.
6. The build pauses after M17 (a build/PAUSE file), so I can read build/M17/report.md and stop the video runner before
   anything moves. Deleting the file and starting the build again continues with M18.

---

## Part B. BUILD_SPEC.md text

### B.1 New section 14 (appended after section 13)

<!-- BEGIN SECTION 14 -->
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
<!-- END SECTION 14 -->

### B.2 Section 1 (replaces the whole section)

<!-- BEGIN SECTION 1 -->
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

<!-- END SECTION 1 -->

### B.3 Section 3 (inserted after the line "When ideas.txt has no idea: ...")

<!-- BEGIN SECTION 3 ADD -->
- From M18 on: `bash run.sh --channel <id> [--once]` runs one channel (14.6). Every path in this section is inside
  channels/<id>/ (14.3), the stage order comes from the channel's format (14.7), and runners of different channels
  may run at the same time (heavy steps take turns, usage limits are shared, 14.6).
<!-- END SECTION 3 ADD -->

### B.4 Section 8 (replaces the whole section)

<!-- BEGIN SECTION 8 -->
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

<!-- END SECTION 8 -->

### B.5 Section 9 (appended at the end of the section)

<!-- BEGIN SECTION 9 ADD -->
- **Channels and formats (M18, M20):** config.json holds the engine settings. Each run reads the resolved config:
  config.json, then the format's `config` block in format.json (from M20), then the channel's `config` block in
  channel.json, deep-merged in that order (14.4). M18 moves style, voice, sfx, lengths and the channel data paths of
  `paths` into channels/flashfx/channel.json; M20 moves research, hooks, judge, script, visual, review and caption
  into pipeline/formats/problem-solution-reel/format.json. Values do not change in either move. build/M17/
  config-keys.tsv lists every key with its destination.
- **heavy (M19):** stale_seconds for the global heavy lock and the list of step kinds that take it (14.6).
- Platform settings live in pipeline/platforms/<platform>/platform.json, not in config.json (section 8).
<!-- END SECTION 9 ADD -->

### B.6 Section 11 (appended at the end of the section)

<!-- BEGIN SECTION 11 ADD -->
- the channels (from M18): their ids, names, platforms and formats, how to start each (`bash run.sh --channel <id>`),
  where each one's files are (channels/<id>/), and that exports/ is shared with `<id>-N` names
- the braces rule with channels: add with `bash pipeline/bin/add-idea.sh --channel <id> "{...}"`. The channel comes
  from my words around the braces ("for life of gabry", "lifeofgabry:", "flashfx idea"). When I name none and more
  than one channel is enabled, ask me which one in one short question before adding
- how to add a channel (`bash pipeline/bin/new-channel ...`) and that one channel's session never edits another
  channel's files
<!-- END SECTION 11 ADD -->

### B.7 Section 12 (replaces the old M17 entry, from its first line to the end of section 12)

<!-- BEGIN MILESTONES -->
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
<!-- END MILESTONES -->

### B.8 Section 13 (replaces the section's text under its heading)

<!-- BEGIN SECTION 13 -->
## 13. Not in version 1

Posting (I post manually from exports/); music; series; processing two ideas of the same channel in parallel; the
footage formats (Logs of Gabry, the Gabriele Bolognese vlog) and the interactive story format, beyond the design hooks
of 14.11; FlashFX-v2 (.ffx) projects as a target (the Shorts Editor project of S15 is in). (M21)
<!-- END SECTION 13 -->

### B.9 Everywhere else in BUILD_SPEC.md

- Every `(M17)` tag and the `(M17;` of the S15 heading become `(M21)` and `(M21;`: the editable project is now M21.
- Nothing else in sections 2 to 7 and 10 changes: section 14's first paragraph tells every reader how their paths and
  export names map to channels.

---

## Part C. Open questions (defaults until I answer)

The merge session asks me these. An answer replaces the default in section 14.10 (or section 8 for question 4) and
gets a line in DECISIONS.md.

1. **Narration.** (a) Default: one narrator in the second person, Gabry plays "you" and speaks no lines (speech
   bubbles only). (b) Gabry narrates in the first person, lip-synced when he faces the camera. (c) A narrator plus
   short lines spoken by Gabry (two voices). Changes: the number of Kokoro voices, whether lip sync is built.
   Answered (2026-11-07): a narrator in the third person tells about 90% of every video; occasionally, and not in
   every video, Gabry says a short line himself (about 10%), in the same Kokoro voice; lip sync only for his lines.
2. **Reference videos and sound pack.** Where are the reference videos on my PC, how many are there, and is there a
   folder of cartoon or cinematic sound effects? Default: none given yet. M22 copies what I name (channel.json
   sources.refs and sources.sfx) into channels/lifeofgabry/styles/gabry-2d/refs/ and channels/lifeofgabry/styles/sfx/.
   The folders are written in Windows form (C:/Users/...). Without references M23 uses the default bible; without
   sounds M24 stops and asks for them.
   Answered (2026-11-07): no folder yet; I make the folders and add the files later. The reference videos must be in
   place before M23 (the look): without them M23 stops before the style bible and asks for them, it does not build a
   default bible. The sound pack must be in place before M24.
3. **Gabry's look.** (a) Default: an original cartoon, not my likeness. (b) A cartoon version of me (I provide 3
   photos: front, side, smiling). (c) A description I write.
   Answered (2026-11-07): (a), just an original cartoon, nothing like me; "Gabry" is only a name (it could as well be
   John). What matters is that he is recognizable at a glance, the same in every video.
4. **YouTube caption length.** YouTube's title field (the "caption" of a Short) keeps at most 100 characters. Keep my
   150 limit, or set export.caption_max to 100? Default: 150, as I asked.
   Answered (2026-11-07): default (150) for the title field. The on-screen captions of Life of Gabry are jump
   captions: at most 3 words on screen at a time, a long word alone, hard cuts between them (14.10, story-build).
5. **The motion rules** (added by the merge session). Do the Motion and energy rules of BUILD_SPEC.md section 5
   (milestones M14 to M16, written for FlashFX) apply to Life of Gabry?
   Answered (2026-11-07): no. Its style is simpler and comes only from its own references and style bible, which I
   correct directly; nothing from FlashFX's motion graphics transfers.

---

## Part D. build-runner.sh changes (only while the build runner is not running)

- `MS_IDS` keeps M0 to M16 (M14 to M16 are the motion milestones); the old `M17` (Editable project export) is replaced
  by `M17 M18 M19 M20 M21 M22 M23 M24`.
- `MS_TITLES` keeps every title up to "Director, components and the energy loop" (M16); the old "Editable project
  export" after it is replaced by "Control check" "Channels" "Exports and channels side by side" "Formats and the
  timeline" "Editable project export" "Life of Gabry: the story" "Life of Gabry: the look" "Life of Gabry: end to end".
- The two messages that say "M0 to M17" say "M0 to M24".
- A clean stop point between milestones: in the main loop, right after `say NEXT ...` (inside the `if` that starts the
  next milestone), the runner stops when build/PAUSE exists. An empty file pauses before the next milestone; a file
  that holds a milestone id (for example `M18`) pauses only before that one:

  ```bash
      if [ -f "$BUILD_DIR/PAUSE" ]; then
        pause_at=$(tr -d ' \r\n' < "$BUILD_DIR/PAUSE")
        if [ -z "$pause_at" ] || [ "$pause_at" = "${MS_IDS[$MS_INDEX]}" ]; then
          stop_ticker; save_state
          say STOP "paused before ${MS_IDS[$MS_INDEX]}: $BUILD_DIR/PAUSE exists. Delete it, then run: bash build-runner.sh"
          exit 0
        fi
      fi
  ```

  The saved state already points at the next milestone's build step, so `bash build-runner.sh` resumes there.
  .gitignore gets one line, `build/PAUSE`. The merge session writes `M18` into build/PAUSE, so the build runs the
  motion milestones M14 to M16 and the control check M17, then stops before M18, and I can read build/M17/report.md and
  stop the video runner before anything moves; any later pause works the same way.
- Nothing else changes: the build prompt already reads the full spec, and the milestones point at section 14.
