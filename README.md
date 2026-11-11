# AutoFlashFX

AutoFlashFX is an unattended pipeline that turns a one-line video idea into a finished vertical reel. A runner takes each idea from a queue through research, fact checking, hooks, script, voiceover, visuals, sound effects, review, render and caption, with nobody at the keyboard, and writes the video and its caption text into `exports/`. The visuals are motion graphics written as code (HyperFrames compositions animated with GSAP and Three.js), never AI-generated video. The writing and review steps are calls to the Claude Code CLI.

It is a personal tool, built for the Instagram channel of [FlashFX](https://flashfx.app), and it is designed so that further channels, formats and platforms can be added as data rather than new runner code. Internally the project is called `instagramReels` (the name in `package.json` and `CLAUDE.md`).

## Features

### The runner
- Processes a channel's idea queue forever (`ideas.txt`, one idea per `{...}` block), or until the queue is empty with `--once`.
- Resumes the unfinished run after a stop or a crash; every run keeps its state in `channels/<id>/runs/<run>/state.json`.
- Preflight checks before the loop (commands, versions, Python modules, disk space, the channel's files). A missing hard dependency writes `logs/STOPPED.md` with the exact fix.
- One runner per channel; runners of different channels can run side by side. A global lock serialises the heavy steps (text to speech, transcription, render, encode, analysis).
- Waits out usage limits and retries temporary errors inside the stage. A code error in a stage goes to a reviewer and fixer loop that may edit only `pipeline/` and the channel's `motion-lib/candidates/`, and records each fix in `pipeline/knowledge/known-issues.md`.
- Optional daily quota per channel, status lines for every step, a rotated `runner.log`, and a one-line-per-idea `history.txt`.

### The stages of the `problem-solution-reel` format
The stage list is read from `pipeline/formats/problem-solution-reel/format.json`:

| Stage | What it does |
| --- | --- |
| S1 research | Researches the facts and takes screenshots and short scroll recordings of real pages with headless Chromium |
| S2 expansion | Expands the idea and decides the solution the reel presents (FlashFX, an external tool or a method) |
| S3 gate | Scores the idea; the code, not the model, decides whether it continues, gets a new angle or is dropped |
| S4 angle | Looks for a better angle for an idea that failed the gate |
| S5 hooks, S6 judge | Shortlists hooks from the channel's hook library and judges them |
| S7 script | Writes the script, with checks on claims, length and wording |
| S8 voiceover | Voices the script with Kokoro, transcribes it with faster-whisper to measure the word error rate, and writes word timings |
| S9a, S9b, S9c | Plans animations, on-screen text and captions, and transitions, then merges and validates one plan |
| S10 build | Compiles the plan into a HyperFrames project and renders a 540x960 draft |
| S11 sfx | Assigns, places and levels sound effects from the channel's sound pack and mixes them under the voice |
| S12 review | Mechanical checks in the browser (zones, overlaps, contrast, fonts), style, audio and energy checks, plus an edit review; issues are routed back to the stage that owns them |
| S13 render | Renders 1080x1920 at 30 fps, muxes the mix with ffmpeg and checks loudness and duration |
| timeline | Writes `timeline.json`, a description of the final composition, and checks it against the plan, the words, the cues and `final.mp4` |
| S14 export | Writes the caption (first line, body, ask, hashtags) and lints it |

A reel that still fails review after the capped number of rounds is exported with a `NEEDS REVIEW` flag instead of being lost.

### Motion library
- 38 HyperFrames components in `channels/flashfx/motion-lib/compositions/` (cards, chips, charts, chat and terminal windows, a mascot, word and group captions, screenshot zoom, video card, cursor, 3D hero and icon, and more), listed in `catalog.json`.
- A shared motion grammar (`assets/pc-motion.js`) and design tokens generated from the style documents (`pipeline/bin/build-tokens`).
- A gallery page that plays every component, a frame-by-frame check of each component against the style's numbers (`frame-match`), a WebGL capability test, and a golden reference reel (`render-golden`).

### Channels, formats and platforms
- `channels/<id>/` holds everything a channel owns: `channel.json`, the idea queue, the hook library, voice and account profile, brand kit, style, sound pack map and motion library. One channel exists today: `flashfx`.
- `pipeline/bin/new-channel` creates a channel from a format's template; it starts disabled with `[FILL IN]` placeholders.
- Two platform definitions in `pipeline/platforms/`: `instagram-reels` (which also exports an alternate hook clip) and `youtube-shorts` (title, description and pinned comment).
- The engine refuses to read or write another channel's folder.

### Tooling
- `doctor` (read-only health report), `runner-status`, `preflight`, and a dummy mode that exercises the whole loop without real model or render work.
- A test suite per build milestone in `pipeline/tests/`, with a fake `claude` and fake voice workers for the tests that make no model call.

## Getting started

### Prerequisites
From `config.json` (`preflight.require`) and the setup scripts:

- Git Bash on Windows. The scripts are Bash and assume Windows conventions (for example `python`, not `python3`).
- Python 3.11 or newer on `PATH` as `python` (the project uses 3.13).
- Node.js 22 or newer.
- `ffmpeg` and `ffprobe`.
- The Claude Code CLI (`claude`), installed and logged in.
- `git` and the GitHub CLI (`gh`).
- At least 10 GB of free disk space (`runner.min_free_gb`).

### Download

```bash
git clone https://github.com/gabrielebolognese/AutoFlashFX.git
cd AutoFlashFX
```

### Install dependencies

```bash
bash pipeline/bin/setup-python   # jsonschema, playwright and Playwright's Chromium (requirements.txt)
bash pipeline/bin/setup-node     # hyperframes, gsap and three at the versions pinned in package.json
bash pipeline/bin/setup-venv     # reports the voice environments and creates what is missing
```

`setup-venv` uses `uv` to create Python 3.11 environments, CPU only: `--kokoro` for the Kokoro text to speech environment and `--whisper` for `.venv-tts/` with faster-whisper. `--check` only reports.

### Configuration
There is no `.env` file. Settings live in JSON:

- `config.json`: the engine (model per role, text to speech, caps, timeouts, render, preflight, paths). `tts.whisper_python` and `paths.kokoro_python` are absolute paths on the author's machine; change them, or let `setup-venv` create the environments.
- `pipeline/formats/<format>/format.json`: the format's stages and its own settings.
- `channels/<id>/channel.json`: the channel's identity, platform, format, quota and channel-owned settings.

Files that git does not track and that you must supply yourself (see `.gitignore`):

- `channels/<id>/library/voice/engine.txt`, which names the voice engine and its interpreter (the fields are listed in the format's `required_files`), plus any reference recordings.
- The sound effects audio in `channels/<id>/styles/sfx/`. Run `bash pipeline/bin/build-sfx-map` after adding it. Without a map the sound stage renders the voice alone and flags the reel.
- The reference videos in `channels/<id>/styles/<style>/refs/`.

Check that everything is in place:

```bash
bash pipeline/bin/preflight --channel flashfx
bash pipeline/bin/doctor --channel flashfx
```

### Run

```bash
bash run.sh --channel flashfx          # process the channel's ideas forever
bash run.sh --channel flashfx --once   # stop when the queue is empty
```

Stop it with Ctrl+C; starting it again resumes the unfinished run. `bash run.sh` without a channel lists the channels and exits.

To exercise the loop with dummy stages, without real model calls or renders:

```bash
REELS_DUMMY=all bash run.sh --channel flashfx --once
```

This removes the processed ideas from `ideas.txt` and writes dummy files into `exports/`, so point `REELS_ROOT` at a temporary copy or add the idea again afterwards.

## Output

There is no build step. Each finished reel is a folder `exports/<channel>-N/` containing:

- `<channel>-N.mp4`, the 1080x1920 reel
- `<channel>-Ncaptions.txt`, the caption and notes for posting
- `<channel>-Nhook2.mp4`, an alternate hook clip (instagram-reels only)

Posting is done by hand. Working files for each idea stay in `channels/<id>/runs/`.

## Usage

| Command | What it does |
| --- | --- |
| `bash pipeline/bin/add-idea.sh --channel <id> "{an idea}"` | Appends an idea to the queue through the queue lock. `{[important] ...}` marks an idea whose escalations may use the larger model |
| `bash run.sh --channel <id> [--once]` | Starts the runner for a channel |
| `bash pipeline/bin/runner-status [--channel <id>]` | Shows whether a runner is alive, its latest status line and the log tail |
| `bash pipeline/bin/preflight --channel <id>` | Runs the startup checks alone |
| `bash pipeline/bin/doctor [--quick] [--channel <id>]` | Read-only health report: versions, disk, voice environments, each channel's files and logs |
| `bash pipeline/bin/new-channel <id> --format problem-solution-reel --platform <platform> [--name "..."]` | Creates a new, disabled channel from the format's template |
| `bash pipeline/bin/index-hooks` | Rebuilds the hooks index after `hooks.txt` changed |
| `bash pipeline/bin/build-voice-profile [--force]` | Rebuilds the voice and account profile files |
| `bash pipeline/bin/build-sfx-map [--check]` | Measures the sound pack and writes the sound effects map |
| `bash pipeline/bin/build-tokens [--force] [--check] [--verify]` | Derives `tokens.json` and `tokens.css` from the style documents |
| `bash pipeline/bin/gallery` | Builds the motion library gallery |
| `bash pipeline/bin/frame-match [--only id,id]` | Measures every component frame by frame against the style |
| `bash pipeline/bin/webgl-test` | Tests WebGL for Three.js in headless Chrome and records the result |
| `bash pipeline/bin/render-golden` | Builds and renders the golden reference reel |
| `python tools/voice.py say "text" --out out.wav` | Standalone text to speech with silence tightening |
| `bash pipeline/tests/run-all.sh` | Runs every test (hours; some sections call the real models) |

The tools that work on one channel's data read `REELS_CHANNEL`; with exactly one channel it is the default. Each script prints its options with `--help` or documents them in its header. The `npm` scripts in `package.json` (`gallery`, `frame-match`, `golden`) wrap the same commands; `check` and `lint` still point at the pre-channels `motion-lib` path.

Where to look while it runs, inside `channels/<id>/logs/`: `status.txt` (latest line), `runner.log` (the whole story), `history.txt` (one line per finished, dropped or blocked idea), `blocked.txt`, `suggested-ideas.txt` and `STOPPED.md`.

## Project structure

| Path | What it holds |
| --- | --- |
| `run.sh` | The video runner |
| `config.json` | Engine settings |
| `pipeline/bin/` | Command line tools |
| `pipeline/lib/` | Bash and Python libraries (runner, state, model calls, limits, visual, motion, sfx, review, timeline, tts) |
| `pipeline/stages/` | One folder per stage: contract, schema, prompts, `run.sh`, dummy |
| `pipeline/formats/` | Formats: stage order, settings, prompt overrides, channel template |
| `pipeline/platforms/` | Platform definitions and exporters |
| `pipeline/schemas/` | JSON schemas for channels, formats, platforms and the timeline |
| `pipeline/vendor/ig-agent-skill/` | Vendored MIT scripts from instagram-agent-skill (hook scoring, beats, humanize, caption lint) |
| `pipeline/tests/` | Milestone tests, fakes and fixtures |
| `channels/flashfx/` | The FlashFX channel: queue, library, brand kit, style, motion library, golden reel |
| `tools/` | `voice.py` (text to speech) and `analyze_refs.py` (reference video analyzer) |
| `build/`, `build-runner.sh` | The automated milestone build: reports, reviews and test logs |

## Tech stack

- **Runner and stages:** Bash (Git Bash on Windows)
- **Helpers:** Python 3.13 with `jsonschema` and `playwright` (headless Chromium)
- **Rendering:** Node 22 with HyperFrames 0.8.226, GSAP 3.15.0 and Three.js 0.159.0; ffmpeg and ffprobe
- **Models:** the Claude Code CLI, with a model and effort per role in `config.json`
- **Voice:** Kokoro text to speech and faster-whisper transcription, each in a Python 3.11 environment, on CPU

## Further documentation

- [BUILD_SPEC.md](BUILD_SPEC.md): the full specification
- [PLAN.md](PLAN.md): the build plan, one milestone per batch
- [DECISIONS.md](DECISIONS.md): every choice the spec left open, and what was chosen
- [CHANNELS.md](CHANNELS.md): the channels design
- [CLAUDE.md](CLAUDE.md): build status, folder map and working rules
- [build/progress.md](build/progress.md), [build/open-issues.md](build/open-issues.md), [build/HUMAN_TODO.md](build/HUMAN_TODO.md)
- [pipeline/knowledge/known-issues.md](pipeline/knowledge/known-issues.md)
- `CONTRACT.md` in each `pipeline/stages/<stage>/` folder

## Status

In development, built milestone by milestone by `build-runner.sh`. Milestones M0 to M20 are recorded as done in `CLAUDE.md` and `build/progress.md`; M21 to M27 are planned (an editable project export, learning from feedback, and a second channel). Code for the editable project stage exists in `pipeline/stages/s15-project/` and `pipeline/lib/s15/` but the stage is not in the format's stage list yet.

This is a personal tool for one Windows machine and one channel. Defaults, absolute paths in `config.json` and the untracked voice, sound and reference files assume that setup, so a fresh clone will not produce a reel without them. `package.json` marks the project as `UNLICENSED`; no license file is included.
