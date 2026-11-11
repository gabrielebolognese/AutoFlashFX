# AutoFlashFX

An unattended pipeline that turns a short video idea into a finished Instagram reel.

It takes an idea through research, expansion, hooks, script, voiceover, visuals, sound effects, review, render and export, without anyone at the keyboard. The visuals are motion graphics written as code (HyperFrames, GSAP, Three.js), never AI-generated video.

## How it works

A run moves through a fixed list of stages defined by a **format** (`pipeline/formats/<format>/format.json`). Each stage has its own prompt, schema and output folder, and the runner reads the stage order from the format, so a new kind of video is a new format file rather than new runner code.

Every run ends with a `timeline.json` describing the final composition, which is checked against the plan, the spoken words, the cues and the rendered `final.mp4`.

Exports land in `exports/<id>-N/` with the video and its caption text.

## Repository layout

| Path | What it holds |
| --- | --- |
| `pipeline/` | The runner, stage scripts, libraries, prompts, schemas, formats and tests |
| `channels/` | Per-channel configuration and brand files |
| `tools/` | Helper scripts, including the voice script |
| `build/` | Reports, reviews and test logs from each build milestone |
| `BUILD_SPEC.md` | The full specification |
| `PLAN.md` | The build plan, one milestone per batch |
| `DECISIONS.md` | Every choice the spec left open, and what was chosen |
| `CHANNELS.md` | How channels are set up |

## Stack

- **Runner and stages:** Bash (Git Bash on Windows)
- **Helpers:** Python 3.13 (`requirements.txt`: `jsonschema`, `playwright`)
- **Rendering:** Node 22 with HyperFrames, GSAP and Three.js (`package.json`)
- **Voice:** Kokoro text to speech; transcription with faster-whisper in a separate Python 3.11 environment
- Everything runs on CPU

## Setup

```bash
bash pipeline/bin/setup-python   # Python packages
bash pipeline/bin/setup-node     # Node packages and vendored motion libraries
bash pipeline/bin/setup-venv     # transcription environment
```

`BUILD_SPEC.md` and `PLAN.md` cover the conventions, the stages and how to run each milestone's tests.

## Status

Built milestone by milestone; the current state is tracked at the top of `CLAUDE.md`. This is a personal tool built for the [FlashFX](https://flashfx.app) channels, so expect paths and defaults that assume that setup.
