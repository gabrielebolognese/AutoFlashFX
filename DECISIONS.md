# DECISIONS.md

Every choice the spec left open, with the reason. Newest at the bottom of each milestone section. Later batches
append; they do not rewrite earlier entries (add a dated correction instead).

## M0 (2026-10-31)

### Repository
1. **.gitignore merged now, not in M1.** The user's .gitignore lacked the spec's list (runs/, exports/, logs/,
   styles/*/refs/, styles/*/analysis/, the sound pack audio, build/ runtime files). Without it the first commit
   would have carried the analysis PNGs, the reference videos and the sound pack, and the runner's approval commit
   (`git add -A build`) would carry state.env and batch logs. The user's own entries are kept.
2. **Two commits in M0:** `chore: track spec, style files and analyzer` (files that existed but were untracked:
   BUILD_SPEC.md, the three style text files, tools/analyze_refs.py, .gitignore, .gitattributes), then
   `docs(M0): plan` (PLAN.md, DECISIONS.md, CLAUDE.md, build/progress.md, build/HUMAN_TODO.md). Reviews diff from
   the milestone's start commit, so the docs commit stays readable.
3. **build/M0/report.md is written after the commit**, as the batch prompt orders; build-runner.sh commits build/
   when the review approves.
4. **hooks.txt moves to library/hooks.txt in M1 with `git mv`, unchanged.** The spec says never edit hooks.txt.
   The file has 4 lines with em dashes (lines 43, 64, 73, 80) and 2 lines whose blank was lost (lines 53, 54);
   the hooks lint (M5) reports them and the user fixes them. The no-em-dash test excludes library/hooks.txt and
   pipeline/vendor/ for this reason.

### Interpreters and packages
5. **`python` (3.13) for every helper, never `python3`** (the Windows Store stub). Packages on the system Python
   are limited to pure or well-supported wheels: jsonschema, playwright, numpy and pillow (already installed).
6. **Text to speech and transcription live in `.venv-tts/` on Python 3.11, created with uv.** kokoro 0.9.4
   declares `requires_python <3.13`; chatterbox-tts 0.1.7 pins torch 2.6.0 and was tested on 3.11; faster-whisper
   1.2.1 runs anywhere. uv is installed with `python -m pip install uv` and downloads CPython 3.11 itself, so no
   admin rights or winget are needed. The machine has no NVIDIA GPU (nvidia-smi absent): CPU inference.
7. **qwen3-tts is a config option, not installed in version 1.** No verified pip package; chatterbox is primary and
   kokoro is the fallback as the spec's default. The M7 blind test asks the user which won.
8. **faster-whisper model `small.en` on CPU with int8**, configurable in config.json (`tts.whisper_model`). Enough
   for word timestamps and WER on clean synthetic speech; `medium.en` is one config edit away.
9. **Audio measurement uses ffmpeg plus numpy only** (loudness and true peak via the ebur128 filter, loudnorm for
   normalization, decoded PCM for onset, peak, attack, tail, centroid). No librosa or numba on Python 3.13; fewer
   install risks and ffmpeg is already a hard dependency.
10. **Playwright (Python) for research screenshots**, as the spec names it; Chromium is installed by
    `pipeline/bin/setup-python`. The mechanical checks of S12 use Node `puppeteer` (full package, its own Chrome
    for Testing) because they run against the HyperFrames composition in the same Node toolchain.

### Claude Code calls
11. **Permission flags: `--permission-mode auto --permission-prompts none`.** Verified in `claude --help` of
    version 2.1.316: `auto` is a listed mode and `none` means anything that would prompt is denied. Tools a stage
    needs are pre-approved with `--allowedTools`. `--effort` accepts low, medium, high, xhigh, max. `--json-schema`,
    `--output-format json` and `--resume` exist. `--bare` is never used (it skips the subscription login path).
12. **Nested headless calls work.** A `claude -p` call from inside a Claude Code session (CLAUDECODE=1 in the
    environment) returned normally in M0, so the build batches can run tests that call models without environment
    tricks.
13. **Protected files are enforced twice:** `--disallowedTools` rules for Edit on ideas.txt, library/**, styles/**,
    exports/** and Read on .env, plus a hash snapshot before every call in ai(); if a call changed a protected file,
    ai() restores the snapshot and reports a code error. Bash inside a session could otherwise write anywhere.
14. **Model aliases** (opus, sonnet, haiku, fable) and efforts come from config.json only, as the spec requires;
    build-runner.sh already proves the aliases resolve.

### Runner design
15. **State root and repo root are separate** (`REELS_ROOT`, `REELS_REPO`) so every test runs in a temporary root and
    never touches the real ideas.txt, runs/ or exports/. Tests that exercise the fixer get a copy of pipeline/ in a
    sandbox git repository.
16. **Stage exit codes:** 0 done (flags recorded in state.json), 10 drop, 20 block, anything else is a code error.
    Every stage has `dummy.sh` for fast tests next to `run.sh`.
17. **Idea id** = sha1 of the normalized text (NFC, whitespace collapsed, trimmed), first 12 hex characters. Run
    folder `runs/<YYYY-MM-DD_HHMM>_<slug>` with a slug from the first five ASCII words.
18. **The ideas lock** is the directory `.locks/ideas` (mkdir is atomic on NTFS), holding a pid file; locks older than
    60 s are removed as stale. Exports use `.locks/exports` the same way for the number.
19. **Error signature** = the error message with digits, paths, hex ids and timestamps stripped, lower-cased,
    whitespace collapsed, sha1, first 12 characters.
20. **Fast test mode** is a sleep multiplier (`REELS_SLEEP_SCALE`, 0 means fast-forward: log the wait, do not sleep),
    the same pattern build-runner.sh uses, plus shorter poll and heartbeat intervals.
21. **Status line format** `[HH:MM] TAG    details` with the tag padded to 6 characters; ANSI colors only when stdout
    is a terminal and NO_COLOR is unset.
22. **Sessions:** A (S1, S2, S4, S5) resumed with `--resume`; B (S3) fresh each round; C (S6) fresh; D (S7) fresh; the
    visual director fresh per pass; the builder fresh per build round; qa fresh per review round. Session ids live
    in state.json so a restart can resume them.
23. **Preflight is table-driven** (`preflight.require` in config.json). M1 lists what exists at M1; M7 adds the venv
    and the voice reference or kokoro fallback, M8 the sfx map, M9 tokens.json and node modules. A missing hard
    dependency writes logs/STOPPED.md and exits, per spec section 3.
24. **OneDrive.** The repository sits in a OneDrive-synced folder. Every mv in the runner retries up to 5 times with
    200 ms pauses (OneDrive briefly holds handles); a HUMAN_TODO asks the user to exclude the folder from sync.

### Vendored tools
25. **All seven files plus LICENSE are vendored in M5 in one go** from github.com/Jakeschincariol/instagram-agent-skill
    (paths: skills/ig-reel/hookscore.py, beats.py, hooks.json; skills/ig-human/humanize.py, detect.py, slop.json;
    skills/ig-caption/caption.py; LICENSE; templates/voice.md), at a pinned commit recorded in
    pipeline/vendor/ig-agent-skill/VERSION. Wrappers call them with `python`; their behavior is never changed.
    Checked in M0: beats.py takes `--wpm` and `--json`; detect.py's PASS is overall 70 or more with no check under
    55 (the spec's thresholds); hookscore.py prints dealbreakers and `--json` scores; caption.py enforces the
    5-hashtag cap.

### Video toolchain
26. **HyperFrames = the npm package `hyperframes`** (github.com/heygen-com/hyperframes, Apache-2.0, 0.8.223 on
    2026-10-31, Node 22 or newer, FFmpeg). Pinned in package.json; upgraded only by hand. Compositions are HTML with
    `data-composition-id`, `class="clip"`, `data-start` and `data-duration` in seconds, GSAP timelines registered on
    `window.__timelines`, `<audio id=...>` clips for sound; Three.js draws from the `hf-seek` event. CLI used:
    `init`, `lint`, `check --json`, `snapshot --at`, `timeline --json`, `render --output --quality --fps`,
    `browser ensure`, `doctor --json`. The HyperFrames core skills are installed for the builder sessions with
    `npx hyperframes skills update` in M9.
27. **motion-lib is itself a HyperFrames project**: one template sub-composition per vocabulary.md component, props
    as composition variables, tokens.json as CSS variables, sound events declared in catalog.json as frame offsets.
28. **Fonts** are downloaded once as OFL files into motion-lib/assets/fonts (Inter Tight, Instrument Serif, Space
    Grotesk, JetBrains Mono, Caveat, the style.md suggestions) and referenced with `@font-face`, which HyperFrames
    lint requires for non-bundled families.
29. **Frame matching** compares motion, not pixels: the reference filmstrips show different content, so a component
    passes when its measured timing and distances match vocabulary.md and the measurements within 1 frame and 10%,
    and its per-frame change curve correlates with the reference strip of the same move. The gallery plus HUMAN_TODO
    covers the look.
30. **Final container:** HyperFrames renders the MP4 with the mix; ffprobe checks the spec's codecs; only when a
    detail differs (audio rate, profile) an ffmpeg post-pass fixes it, re-encoding audio only where possible.

### Style
31. **style.md version 2 is the look; tweaks.md lines in force win; PROPOSED lines are ignored** until the user
    removes the word PROPOSED (tweaks.md says so). Where the spec's stage text mentions a progress tracker or boxed
    captions (version 1 elements), the style wins: tokens.json sets `tracker.enabled: false` and the caption is the
    bare line with accent boxes. The plan schema keeps an optional tracker field for a future style.
32. **The 15 open questions of style.md are decided in M9** with one rule: take what 5 of the 7 motion references do;
    otherwise what both look references agree on; otherwise v02 (the later, cleaner reference). Each decision is
    written to DECISIONS.md under M9, and a HUMAN_TODO asks the user to accept or change them.
33. **Honesty labels** (open question 13): kept, because the spec's S9 requires an honesty label when the data shown
    is mock or sourced; the style decides the label's look (a small light chip), M9 designs it.

### Tracked and generated files
34. **Tracked generated text:** styles/paper-cards/tokens.json, styles/sfx/sfx-map.json, styles/sfx/SFX-MAP.md,
    pipeline/knowledge/known-issues.md. **Ignored:** library/.hooks.index.json and library/hooks.lint.txt (derived
    from hooks.txt), styles/sfx/.cache/ and previews/, library/voice/, media renders. library/.hooks.stats.json is
    neither ignored nor committed by the runner: the user commits it when they want a snapshot.
35. **Frozen fixtures** of the test idea per stage under pipeline/tests/fixtures/runs/test-idea/ keep later tests fast
    and deterministic; audio and video fixtures stay out of git and are regenerated by the test that needs them.
36. **Every text file is LF in the working copy** (`* text=auto eol=lf` in .gitattributes, added after the M0
    commits). core.autocrlf is true on this machine, so without it a checkout would turn the extension-less bash
    scripts the spec names in pipeline/bin (index-hooks, build-sfx-map, mix-sfx, screenshot) into CRLF and break
    them. Checked in M0: files written by the Bash tool's heredocs and by the Write tool are LF already.
37. **Big files are written with the Write tool, not heredocs.** On this Windows setup the Bash tool's command
    string fails above roughly 8 KB (ENAMETOOLONG or a truncated heredoc). Small edits with sed and short heredocs
    are fine.
