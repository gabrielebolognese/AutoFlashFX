# M0 report: Plan

## What this batch did
- Read BUILD_SPEC.md in full (752 lines), CLAUDE.md, build-runner.sh, the style files (style.md version 2,
  tweaks.md, vocabulary.md, the analysis index and sources), the sound pack layout (106 files) and the hooks file.
- Checked the machine and the external facts the plan depends on: Python 3.13 only (no 3.11 or uv), Node 22.16,
  ffmpeg and ffprobe 9.0.2, gh 2.103 logged in, Claude Code 2.1.316 (permission flags, effort levels, json schema,
  resume verified in `claude --help`), no NVIDIA GPU, 174 GB free, the repo inside a OneDrive folder.
- Verified that a headless `claude -p` call works from inside a Claude Code session (needed by every later test).
- Looked up the toolchain versions and constraints: `hyperframes` 0.8.223 on npm (Node 22+, FFmpeg, Apache-2.0,
  HTML compositions with data-start and data-duration, GSAP timelines, Three.js through hf-seek, CLI lint, check,
  snapshot, timeline, render), chatterbox-tts 0.1.7 (torch 2.6 pin, tested on Python 3.11), kokoro 0.9.4 (Python
  below 3.13, espeak-ng optional), faster-whisper 1.2.1, and the instagram-agent-skill repo layout for vendoring.
- Wrote PLAN.md: conventions shared by every milestone (interpreters, roots, stage contract, test harness, logs,
  git), then M1 to M13 with the files each creates, one exact acceptance test command each, dependencies, a
  dependency graph and the risks.
- Wrote DECISIONS.md (35 decisions under M0) and CLAUDE.md per BUILD_SPEC.md section 11.
- Created build/progress.md (one section per milestone, M0 marked done) and added 5 M0 lines to build/HUMAN_TODO.md.
- Merged .gitignore to the spec's list so no reference video, analysis frame, sound file or build runtime file
  enters git (DECISIONS.md item 1).
- No pipeline code was written.

## Files
- New: PLAN.md, DECISIONS.md, build/progress.md, build/M0/report.md.
- Rewritten: CLAUDE.md, .gitignore.
- Appended: build/HUMAN_TODO.md.
- Newly tracked (existed before, untracked): BUILD_SPEC.md, .gitattributes, styles/paper-cards/style.md,
  tweaks.md, vocabulary.md, tools/analyze_refs.py.

## How to test
No code, so no test command. Review PLAN.md against BUILD_SPEC.md section 12: every milestone lists its files,
its acceptance test command (`bash pipeline/tests/test-m<n>.sh`) and its dependencies. Checks that can be run now:

```
grep -c '^## M' PLAN.md                 # 13 (M1 to M13)
grep -n $'\xe2\x80\x94' PLAN.md DECISIONS.md CLAUDE.md build/progress.md build/HUMAN_TODO.md   # no output
git log --oneline -n 3
```

## Test output summary
The em dash scan over the new files returned nothing; the files are LF only; the staging preview listed exactly the
intended files (no media, no analysis frames).

## Known gaps
- M9's test needs the frozen M7 fixtures (script, voice, words) for the golden reel, so the build order stays
  numeric even though M8 and M9 do not depend on M4 to M7 otherwise.
- The qwen3-tts engine is declared in config but not installed in version 1 (no verified package).
- The 15 open questions in style.md are not decided yet; the decision rule is fixed (DECISIONS.md item 32) and M9
  applies it, unless the user resolves the PROPOSED lines in tweaks.md first.
- hooks.txt keeps its em dashes and broken blanks (the spec forbids editing it); the hooks lint reports them in M5.

## HUMAN_TODO items added
- Read PLAN.md and DECISIONS.md (the build continues without you).
- Exclude the folder from OneDrive sync or move it.
- Decide the PROPOSED lines in styles/paper-cards/tweaks.md before M9 if possible.
- Fix the em dashes and the lost blanks in hooks.txt when you like.
- Record library/voice/reference.wav and library/voice/memo.* when you can.

## Commits
- 1c83195 chore: track spec, style files and analyzer
- 529f9d0 docs(M0): plan
- (added after the commits above) chore(M0): LF for every text file and tool notes: .gitattributes widened to
  `* text=auto eol=lf`, DECISIONS.md items 36 and 37, CLAUDE.md tool-limit note.
