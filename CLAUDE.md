# instagramReels

An unattended pipeline that turns a short video idea into a finished Instagram reel: research, expansion, hooks,
script, voiceover, visuals written as code (HyperFrames motion graphics, never AI video), sound effects, review,
render, export. The full spec is BUILD_SPEC.md; the build plan is PLAN.md; choices are in DECISIONS.md.

## Build status
- M1 Skeleton: done (2026-10-31). Next: M2 Runner core. The build is driven by `bash build-runner.sh`; its log is
  build/build.log and its per-milestone reports are in build/M<n>/.
- What exists: config.json, ideas.txt, the queue library (pipeline/lib/ideas.py and ideas.sh), add-idea.sh, the
  preflight, run.sh (preflight and banner only, the loop arrives in M2), the test harness in pipeline/tests/.
  Run every test with `bash pipeline/tests/run-all.sh`. Stages, runs and exports do not exist yet.

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
- Today (M1) `bash run.sh` runs the preflight, prints the banner and the queue, and exits. A missing hard
  dependency writes logs/STOPPED.md with the exact fix. `bash pipeline/bin/preflight` runs the checks alone.

## Rules for Claude Code sessions in this folder
- **Braces rule:** when the user's message contains text in `{...}`, append each braced block to ideas.txt by
  running `bash pipeline/bin/add-idea.sh "{...}"` (never by editing the file), then confirm in one line with the
  script's own output ("added 1 idea to ideas.txt (queue: N)").
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
- **Shell:** Git Bash. Every text file is LF (.gitattributes: `* text=auto eol=lf`); scripts use GNU date.
- **Tool limits:** the Bash tool's command string fails above roughly 8 KB here, so write long files with the
  Write tool instead of a heredoc. Check line endings with Python on bytes, not with grep.
- **Windows paths and Python output:** every script sources pipeline/lib/common.sh, which exports the roots in
  `C:/...` form (cygpath -m) and PYTHONUTF8; environment variables are not path-converted by Git Bash, arguments
  are. Python helpers must print LF (`sys.stdout.reconfigure(newline="
")`), because Windows Python writes CRLF
  to pipes. See DECISIONS.md 38 to 40.

## Skills
The `/ig-*` skills from github.com/Jakeschincariol/instagram-agent-skill are installed globally in `~/.claude/skills/`
and read the voice profile in `~/.claude/instagram/voice.md`. The pipeline uses its own copy of the profile in
`library/profile/voice.md` and vendored copies of the scripts in `pipeline/vendor/ig-agent-skill/`.
