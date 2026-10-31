# instagramReels

An unattended pipeline that turns a short video idea into a finished Instagram reel: research, expansion, hooks,
script, voiceover, visuals written as code (HyperFrames motion graphics, never AI video), sound effects, review,
render, export. The full spec is BUILD_SPEC.md; the build plan is PLAN.md; choices are in DECISIONS.md.

## Build status
- M0 Plan: done (2026-10-31). Next: M1 Skeleton. The build is driven by `bash build-runner.sh`; its log is
  build/build.log and its per-milestone reports are in build/M<n>/.
- Nothing below "How to start the runner" exists yet; the folder map shows where things will land.

## Folder map
- `ideas.txt`: the idea queue (one idea per `{...}` block). `run.sh`: the video runner. `config.json`: models, engines,
  caps, paths.
- `exports/N/`: finished reels (`N.mp4`, `Ncaptions.txt`, `Nhook2.mp4`).
- `library/`: curated by the user: hooks.txt, profile/ (account.md, voice.md, deliverables.txt, pronunciations.txt),
  voice/ (reference.wav, memo.*).
- `styles/paper-cards/`: the look (style.md, tweaks.md, vocabulary.md, tokens.json, refs/, analysis/).
  `styles/sfx/`: the sound effects pack and its map (sfx-map.json, SFX-MAP.md, overrides.txt).
- `motion-lib/`: approved HyperFrames components, candidates/, gallery/. `golden/`: example reels for the visual
  director.
- `pipeline/`: lib/ (bash libraries), stages/ (one folder per stage), bin/ (scripts), vendor/ (MIT scripts from
  instagram-agent-skill), knowledge/known-issues.md, tests/.
- `runs/`: one working folder per idea. `logs/`: runner.log, status.txt, history.txt, blocked.txt, limits.log,
  suggested-ideas.txt, sfx-usage.json, STOPPED.md.
- `tools/analyze_refs.py`: reference video analyzer. `build/`, `build-runner.sh`: the automated build (temporary).

## How to start the runner (from M2 on)
- `bash run.sh` processes ideas forever; `bash run.sh --once` stops when the queue is empty. Results appear in
  `exports/N/`. Stop it with Ctrl+C; restarting resumes the unfinished run.

## Rules for Claude Code sessions in this folder
- **Braces rule:** when the user's message contains text in `{...}`, append each braced block to ideas.txt by
  running `bash pipeline/bin/add-idea.sh` (never by editing the file), then confirm in one line. Until M1 lands,
  say the script does not exist yet.
- **"What is the runner doing?":** read `logs/status.txt` and the end of `logs/runner.log`.
- **Curated by the user, do not edit without asking:** `library/`, `styles/`, `ideas.txt` (only through
  add-idea.sh). The runner's own fixer may edit only `pipeline/` and `motion-lib/candidates/`.
- **Reading the logs:** `logs/history.txt` has one line per finished idea (`date | idea | exported N`, `dropped:
  reason` or `blocked: reason`); `logs/blocked.txt` lists blocked ideas with the reason so they can be re-added;
  `logs/STOPPED.md` exists only after a systemic stop and contains the diagnosis and the exact fix.
- **Never write an em dash** in any file, prompt, caption, script or terminal message. Use commas, colons, periods
  or parentheses.
- **Python:** `python3` is the Windows Store stub and does nothing. Always run `python` (3.13). Text to speech and
  transcription use `.venv-tts/Scripts/python.exe` (Python 3.11).
- **Shell:** Git Bash. Scripts use LF endings (.gitattributes) and GNU date.

## Skills
The `/ig-*` skills from github.com/Jakeschincariol/instagram-agent-skill are installed globally in `~/.claude/skills/`
and read the voice profile in `~/.claude/instagram/voice.md`. The pipeline uses its own copy of the profile in
`library/profile/voice.md` and vendored copies of the scripts in `pipeline/vendor/ig-agent-skill/`.
