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

## M1 (2026-10-31)

### Paths and interpreters
38. **Paths cross into Python in mixed form (C:/Users/...).** Git Bash converts command-line arguments that look
    like POSIX paths (/c/...) before a Windows program sees them, but it does not convert environment variables.
    common.sh therefore exports REELS_REPO, REELS_ROOT and friends through `cygpath -m`, a form both bash and
    Windows Python accept, and ideas.py converts a /c/... argument itself (winpath) as a second net.
39. **Python output is forced to LF and UTF-8.** Windows Python writes CRLF to pipes by default and uses cp1252
    when piped. Every helper calls `sys.stdout.reconfigure(encoding="utf-8", newline="\n")` (the inline snippets
    in config.sh too) and common.sh exports PYTHONUTF8=1. Bash command substitution happens to strip a trailing
    CR, but `while read` loops over Python output would not, so the fix is at the source. Correction to item 36:
    the user's files may stay CRLF in the working copy; every reader of a user-edited text file (ideas.py now,
    the hooks, profile, tweaks and overrides readers later) strips CR itself.
40. **LANG defaults to C.UTF-8** in common.sh and the test harness when it is unset (the Bash tool starts bash
    without a locale), so `${#text}` and `${text:0:60}` count characters, not bytes.

### Queue (ideas.txt)
41. **Nested or unclosed braces:** a second { before the } restarts the block (the earlier, unclosed brace becomes
    a note) and a warning goes to stderr; a } without an open block is a note; {} is ignored. The spec forbids
    nesting, so this only decides what happens on a typo, and restarting protects the common case (a brace that
    was never closed must not swallow the ideas after it).
42. **Writes keep the file's newline style** (a CRLF file is written back as CRLF, LF otherwise) and keep every
    note outside braces; a removed block that stood alone on its lines takes those lines with it. UTF-8 with or
    without BOM is read; the BOM is not written back.
43. **Lock details:** `.locks/ideas` holds a `pid` file (pid and epoch); waiters poll every 50 ms for up to
    runner.lock_wait_seconds (30); a lock whose directory mtime is older than runner.lock_stale_seconds (60) is
    removed after a second mtime check (a fresh lock taken in between is left alone) and the removal is logged as
    a WARN line in runner.log. The remaining race (two breakers in the same microseconds) is accepted on a
    single-user machine.
44. **Similarity fallback** uses difflib.SequenceMatcher on the normalized texts with the spec's 0.9 threshold;
    the runner passes the text it started with on stdin (`--text-stdin`); exit 3 and a WARN line when nothing
    matches, and the file is not rewritten.
45. **add-idea.sh records every addition in logs/.new-ideas** (epoch, id, queue size, source) and prints its own
    confirmation line; the runner (M2) reads and clears that file to print the NEW line, and clears it at startup
    because the banner already shows the queue (the M0 review's suggestion 5). Text without braces given to
    add-idea.sh is wrapped in braces, so a note pasted without them still becomes one idea.
46. **ideas.py exit codes:** 0 ok, 1 usage, 2 file error, 3 not found or empty queue, 4 lock timeout. JSON on
    stdout unless --plain, so M2's state code can read `first` directly.

### Config and preflight
47. **Effort levels per role:** high for research, script, visual_director, builder and reviewer; medium for
    gate, judge, qa, cut, checks and fixer; xhigh for the two fable escalations; low for indexer and probe.
    config.json also carries `version` (shown in the banner), `runner.lock_stale_seconds`,
    `runner.lock_wait_seconds`, `runner.min_free_gb`, `lengths.default_s` and `lengths.list_s`. The tts engine
    parameters and the sfx base gains are starting values for M7, M8 and M11 to tune.
48. **preflight.require entries** have a `check` type (command, python_module, file, disk, shell), an optional
    `min_version` (the first X.Y[.Z] of `--version`, compared with sort -V), `in_root` for files under the state
    root, `level: warn` for soft checks (the gh login) and a `fix` string that goes verbatim into logs/STOPPED.md.
    A hard failure makes preflight_run return 3 and run.sh exits with it. A successful preflight deletes a
    leftover logs/STOPPED.md (the runner is running, so it is not stopped) and says so.
49. **log.sh ships in M1** with `say` only (the format of spec section 6, colors on a terminal, runner.log append,
    status.txt overwrite for every tag); M2 adds the heartbeat and the per-tag status rules. READY, INFO, QUEUE and
    WARN are extra tags for the startup lines, next to the spec's list.
50. **Tests:** run-all.sh runs every `test-*.sh` (the milestone tests in order, then the unit tests), so
    test-limits.sh (M3) and test-no-emdash.sh are always included (the M0 review's suggestion 6);
    `pipeline/tests/fixtures/ideas/crlf.txt` is marked `-text` in .gitattributes so git never normalizes its CRLF
    bytes; `library/voice/` is ignored as `library/voice/*` with README.txt re-included (suggestion 9).
51. **Folders git cannot hold empty** (motion-lib/candidates, motion-lib/gallery, golden, pipeline/stages,
    pipeline/vendor, pipeline/knowledge) carry a .gitkeep until their milestone fills them.

## M2 (2026-10-31)

### Runner loop and state
52. **The stage table lives in state.py** (key, label, default activity, primary output, initial status); bash loads
    it once per start with `state.py stages`, and state.json copies the order at creation so a run keeps its order
    even if the table changes later. 04-angle starts as `skipped`: the gate reopens it (`state.py reopen 04-angle
    03-gate`) when an angle round is needed (M4). The same `reopen` serves the review loop's fix routing (M11).
53. **One primary JSON output per stage, and the .done marker is written by the runner, never by the stage.**
    `state.py stage-done` validates `<stage>/<primary>` against `pipeline/stages/<stage>/schema.json` in the same
    Python process (jsonschema is imported there, the slowest part of a stage transition at about 0.35 s) and writes
    `.done`; an invalid output leaves the stage `failed` and goes to the code error path. `state.py next` re-checks
    the marker on resume. Extra outputs (facts.md, wav, mp4) are the stage's business and its CONTRACT.md lists them.
54. **Stage scripts run as background children and the runner polls them** (`kill -0` every REELS_TICK_SECONDS,
    default 1 s), so the heartbeat and the NEW lines print during long stages. A stage's stdout and stderr go to
    `<stage>/stage.log`; the runner's terminal is its fd 3 (REELS_SAY_FD=3), so `say` lines from a stage still
    reach the screen, runner.log and status.txt. The child pid is written to `<stage>/.pid`; on resume a still
    running orphan is waited for and judged by its outputs instead of being started twice.
55. **Resume order:** every loop iteration first looks for an unfinished run (status running, oldest first) and only
    then takes the first idea, so a restart finishes the interrupted run even when the idea was removed from
    ideas.txt by hand meanwhile (the removal at the end then logs a WARN). The runner lock `.locks/runner` holds the
    pid; a live pid (`ps -p`) refuses a second runner with exit 1, a dead one is taken over.
56. **Work time, not wall time:** state.json `timing` keeps `session_started`, `accumulated` and `last_seen`
    (refreshed at every state write and by the heartbeat through `state.py touch`); `pickup` adds the previous
    session's `last_seen - session_started` to `accumulated`. "minute N" in the heartbeat and the duration in the
    DONE line therefore skip the hours the PC was off, at the heartbeat's granularity.
57. **Idea position i/n:** i is this session's idea count; n is (i - 1) plus the ideas still in ideas.txt (the
    current one included). START 2/5 and NEXT 3/5 then keep the denominator of spec section 7 while the queue
    shrinks, and new ideas raise it.
58. **The heartbeat's stage timer** counts from the start of the current stage attempt, not from the last
    `set_activity` (stages may change their activity text every few seconds, as the voiceover does per beat).
59. **status.txt** is overwritten by every line except the tags in REELS_STATUS_SKIP_TAGS (default QUEUE, the banner
    listing, and INFO, chatter). The IDLE tag is used both for the summary line when the queue empties and for the
    idle heartbeat, so `--once` ends on an IDLE line and status.txt always reads as a status.
60. **Until M3 a code error blocks the idea.** A non-zero exit (other than 10 and 20) or an invalid output prints the
    ERROR line, counts an open issue and blocks the idea with the reason "code error, ... (no automatic fix before
    M3)": the idea lands in logs/blocked.txt for a re-add and the runner moves on, as rule zero demands. M3 replaces
    the body of `runner_code_error` with the review and fix loop. A stage whose run.sh does not exist yet is a
    systemic stop instead (STOPPED.md names the stage and the REELS_DUMMY=all alternative) and the idea stays in
    ideas.txt: blocking every idea at a stage that is not built would empty the queue for nothing.
61. **The export runs in Python under the exports lock** (`export.py run`): N = highest number in exports/ plus 1,
    `runs/<id>/export/` is assembled (N.mp4 and Nhook2.mp4 copied from the files named in 14-export/export.json,
    Ncaptions.txt rendered from export.json in the format of spec section 8, because the HOOKS lines need N), then
    one rename into exports/N/. state.json records `export.intent` before the move and `export.number` after; after
    a crash in between, the RUN section of every `Ncaptions.txt` identifies an export that was moved but not
    recorded, so there is never a duplicate or a gap. A leftover `.locks/exports` is removed at startup: only a
    runner takes it and only one runner exists. 14-export therefore produces export.json (caption, hashtags,
    keyword, deliverable and its status, link, hooks, needs_review, facts, files) rather than the captions file.
62. **History and blocked formats:** `YYYY-MM-DD HH:MM | <normalized idea> | exported N` (or `dropped: reason`,
    `blocked: reason`); an exported line is not repeated for the same idea and number on a restart.
    logs/blocked.txt gets two lines per idea: `# date | blocked at S10 | reason | runs/<id>` and the idea in braces,
    ready for add-idea.sh. The IDLE line's "today" counts come from history.txt lines that start with today's date.
63. **Dummy stages** share pipeline/lib/dummy.sh: REELS_DUMMY_SECONDS (default 1) and the planted lists
    REELS_DUMMY_FAIL, DROP, BLOCK, FLAG and INVALID plus REELS_DUMMY_ONCE_FILE (a planted event fires once per
    kind), so the tests cover every outcome without a model. REELS_DUMMY accepts `all`, stage keys or bare numbers.
    The 48 stage files (CONTRACT.md, schema.json, dummy.sh for 16 stages) were produced from one table and are
    committed as plain files; the schemas are first versions that each stage's milestone refines.
64. **Test knobs are literal seconds and are never scaled:** REELS_POLL_SECONDS, REELS_STATUS_EVERY,
    REELS_TICK_SECONDS. REELS_SLEEP_SCALE (0 = log the wait and skip it) applies only to waits that come from
    config: the idle poll in M2, the limit and backoff waits from M3 on.
65. **The Bash tool collapses a double backslash into one inside heredocs** (found while patching files with inline
    Python): write single backslashes in heredocs, or write the file with the Write tool. Also: a `&` after an `&&`
    chain backgrounds the whole chain, including `export`s made earlier in it.
66. **Earlier milestones touched by M2:** ideas.py's lock class got a `name` parameter (the exports lock reuses it,
    the ideas lock is unchanged); add-idea.sh records "Claude Code" as the source when CLAUDECODE is set, for the NEW
    line; tests/lib.sh fast_mode adds REELS_TICK_SECONDS and REELS_DUMMY_SECONDS; test-m1 section 7 runs the banner
    with an empty queue because run.sh now processes the queue; log.sh builds its line with `printf -v` instead of a
    command substitution (one fork less per line) and writes to fd 3 inside stages.
67. **A state.json that cannot be read or written mid-run is a systemic stop, after one retry** (M2 review 1, fix 1).
    Every state.py call on the stage path (`stage-start`, `stage-done`, `next`) goes through `runner_state` in
    runner.sh: an exit code outside the expected set (0, plus 5 for `stage-done`, which is a validation result and
    not a failure) is retried once after STATE_RETRY_SECONDS (3 s, scaled like the configured waits; OneDrive and
    antivirus scans hold files briefly, and state.py's own save already retries its rename for a second), then the
    runner prints WARN, ERROR and STOP, writes logs/STOPPED.md naming runs/<id>/state.json, state.py's message and
    the two fixes (unlock the file and restart, or move the folder out of runs/), and exits 3. The idea stays in
    ideas.txt. Blocking the idea instead would hide an environment problem that hits every idea, and going on
    without a trusted state.json could repeat a stage or duplicate an export. `runner_main` adds a guard: a run
    that ends with "stop" without STOPPED.md gets a generic one, so the runner never exits on its own without a
    diagnosis (BUILD_SPEC.md section 4). `runner_adopt_orphan` now returns 3 for "run the stage" so the stage's
    real result (0 continue, 1 run ended, 2 stop) propagates; before, a run that ended inside the orphan path ran
    the stage once more. `runner_systemic_stop` takes several fix lines, numbered in STOPPED.md. state.py's
    `state_path` uses forward slashes, so its messages match the runner's paths in the logs.
68. **Every state.json write holds an OS file lock on runs/<id>/state.lock** (M2 review 2, fix 1). Two processes
    write state.json while a stage runs: the stage (`flag`, and from M3 on `issue`, `round`, `set`) and the
    runner's heartbeat (`touch`). Each one loaded, changed and saved the whole file, so when two overlapped the
    later save won and the earlier change vanished with exit 0 on both sides: a stage's NEEDS REVIEW flag could
    disappear before the export (20 flags against 40 touches kept 17). Now every state.py command that may write
    (pickup, next, stage-start, stage-done, stage-fail, reopen, flag, issue, round, set, touch, finish) runs inside
    `StateLock`, which holds one locked byte of `state.lock` (msvcrt.locking on Windows, fcntl.flock elsewhere)
    from its load to its save; export.py updates its export record the same way, from a fresh load. An OS lock
    rather than the mkdir lock of ideas.txt (item 18) because the OS releases it when the holder exits, a kill -9
    included, so there is no stale lock to detect and no wait before breaking one; the ideas and exports locks stay
    as they are. Waiters poll every 20 ms for up to 30 s (REELS_STATE_LOCK_WAIT overrides it, for tests) and then
    fail with exit 2, which `runner_state` turns into the systemic stop of item 67; EACCES when opening the lock
    file (OneDrive or an antivirus holding it) is retried the same way. Read-only commands (summary, get,
    unfinished) stay unlocked, because os.replace keeps every read whole. The lock file is never written and stays
    in the run folder.

## M3 (2026-10-31)

### Usage limits
69. **The limit parser is Python with zoneinfo (pipeline/lib/limits.py), not GNU date.** The GNU date shipped with
    Git Bash has no zoneinfo database (there is no /usr/share/zoneinfo), so `TZ=Europe/Rome date -d 3pm` silently
    computes 3pm UTC: the spec's "timezone in parentheses" format would come out wrong by the zone's offset.
    zoneinfo (Python 3.13 with the tzdata package) handles IANA names, UTC and a table of common abbreviations
    (PST, EST, CET...), and aware datetime arithmetic keeps the wall clock across a DST change (checked:
    "resets Mon 12:00am (America/New_York)" across the US switch of Nov 1, 2026). The default zone is
    config runner.timezone, then the PC's zone (its Windows name mapped to an IANA zone, so DST rules apply),
    then the fixed offset the C runtime reports. Rollovers: +1 day for a time, +7 days for a weekday, next year
    for a date. "try again in 2 hours" (relative) is parsed too, as an extra. GNU date and bash's `printf %()T`
    still format the times that are printed.
70. **Limit detection only runs on failed calls** (non-zero exit, is_error, no JSON): a successful answer that
    happens to contain the word "limit" is never a limit. The detector phrases: "hit your (session|weekly) limit",
    "limit reached", "usage limit", "reached your limit", "out of extra usage"; the kind is weekly, session or
    usage from the same line; the time comes from "resets ..." or an epoch after a "|" (13 digits = milliseconds).
71. **The wait (limits.sh):** the target is the reset plus runner.limit_margin_seconds (120); the sleep goes in 60 s
    chunks that re-read EPOCHSECONDS, and the activity text is rewritten each chunk ("waiting for usage limit
    (weekly) until Mon 00:02 (5h41m left)"), so a PC that slept still resumes on time. REELS_SLEEP_SCALE=0 logs one
    INFO line with the target and sleeps nothing (the fast-forward test mode of the spec); 0.001 keeps the chunks.
    logs/limits.log gets one line per wait (kind, reset, target with the margin, the message) and one per resume;
    an unparseable limit sleeps errors.unparsed_limit_sleep_seconds (1800), then probes the probe model ("reply
    ok") every errors.probe_every_seconds (1800) until it answers, forever (REELS_PROBE_MAX caps it in tests).
    The retry is the same command with the same --resume, so a resumed session stays the session.

### ai() and the classifier
72. **The prompt travels on stdin, never on the command line.** Windows has a 32 KB command line, and the CLI's
    variadic flags (--allowedTools, --tools) swallow a positional prompt that follows them (seen in the first M3
    probe: "Input must be provided either through stdin or as a prompt argument"). The JSON schema does go on the
    command line, compacted and without its "$schema" and "$id" keys: the CLI's validator rejects a schema that
    names the 2020-12 meta-schema ("no schema with key or ref"), while the local jsonschema validation of the
    same files handles it. Every call saves NNN.json (raw output), NNN.err (stderr), NNN.meta (role, model,
    effort, the exact command, timing, the class) and NNN.out.json (the structured output) under <stage>/calls/.
73. **Tool lists:** `--tools` restricts the available set and the same names are pre-approved with
    `--allowedTools` (so nothing prompts under --permission-prompts none); the fixer's Edit, Write and MultiEdit
    are approved only under pipeline/** and motion-lib/candidates/**. The protected files are denied with
    `--disallowedTools` rules (Edit, Write, MultiEdit and NotebookEdit on ideas.txt, library/**, styles/** and
    exports/**; Read on .env and .env.*). Verified with a haiku probe in M3: the path rules deny the edit ("File
    is in a directory that is denied by your permission settings") and Read outside the working directory works
    in auto mode without --add-dir, so the reviewer needs no extra directory to read the run folder.
74. **The second net, pipeline/lib/protect.py:** before every call a snapshot (sha1 and a copy) of the protected
    text files (ideas.txt, .md .txt .json under library/ and styles/, minus voice recordings, refs, analysis,
    caches and previews) and a listing of exports/; after the call a changed, added or removed file is restored
    from the snapshot and the call becomes a code error naming the file. exports/ is only listed (renders are too
    big to copy): a change there is reported, not restored.
75. **Classes and order (pipeline/lib/errors.py):** ok (exit 0 and a JSON result with is_error false), limit,
    transient, error. Transient: the api_error_status 408, 409, 425, 429, 5xx and 529; an exit 124 or 137 (the
    call killed by `timeout -k 15 <timeouts.*>`); overloaded, rate limits, timeouts, ECONNRESET and the other
    network errors, server errors and "temporarily unavailable" in the text; a retry-after value larger than the
    backoff replaces it. The backoff table errors.transient_backoff_seconds is 60, 240, 960: three retries, the
    fourth failure is a code error. Fatal texts (not logged in, invalid key, unknown option, unrecognized model,
    billing) are code errors flagged `fatal`: a review cycle whose own call fails fatally blocks the idea at once,
    because the reviewer would hit the same wall. "No conversation found with session ID" is `resume_failed`:
    ai() returns 3 and clears the session stored by --session, so M4's session code can reseed.
76. **ai() does the stage's one schema retry itself:** an answer whose structured output fails the schema is
    re-asked once in the same session (`--resume` the answer's session id) with the validation errors; a second
    failure is a code error ("output did not match the schema after one retry"). Stages therefore never implement
    the retry of BUILD_SPEC.md section 5 themselves.
77. **Sessions:** `--session KEY` reads sessions.KEY from state.json for `--resume` and stores the answer's session
    id there; `--resume SID` is the raw form. The reseed fallback of spec section 3 (a new session seeded with
    facts.md and friends) is M4's, built on the exit code 3.

### The review and fix loop
78. **Each review cycle runs in a child process** (pipeline/bin/review-cycle), started and polled by the runner
    exactly like a stage (fd 3 for its say lines, errors/E<n>.log for its output), so the heartbeat keeps printing
    during the model calls and a usage limit inside the reviewer's own call is handled by the same ai() code. The
    cycle's verdict comes back in fixes/F<n>.result.json (outcome fixed, no_auto, failed or error).
79. **E<n> numbering is per run** (E1, E2... across stages, the stage in the header `- stage:`); F<n> fixes E<n>.
    "All previous error and fix files for this stage" are included as the first 40 lines of each earlier E file
    (they contain the ones before them recursively, and the full files sit next to it), plus the earlier F files,
    their outcomes and the last 40 lines of their verify logs, whole. "The git diff since the last successful
    run" diffs pipeline/ and motion-lib/ from logs/.last-good-sha (HEAD at the last export, written by
    runner_finalize, or HEAD at the first start) and adds the uncommitted changes. The input files are the run
    folder's files (minus calls, errors and fixes) with their sizes, capped at 300.
80. **The reviewer and the fixer answer with structured output** (pipeline/stages/_prompts/reviewer.schema.json
    and fixer.schema.json), and F<n>.md is rendered from the verdict, so the five parts (root cause, class,
    changes, verify command, auto_apply) are always present and in the same place. The reviewer has
    config review.reviewer_tools (Read, Glob, Grep, WebSearch, WebFetch) and gets E<n>.md and known-issues.md
    inline in its prompt; the escalation reviewer gets the same prompt plus an escalation note. The fixer does
    not commit: review-cycle runs the verify command itself (timeouts.verify_seconds), appends the known-issues
    line `- <date> | <stage> | <symptom -> fix> (F<n>, runs/<id>)` and makes one `autofix(<stage>): <summary>`
    commit holding the code change and the line (a sha in the line would not exist yet). When the fixer changed
    nothing but the verify passes, the restart still happens (with an empty commit field).
81. **The caps, precisely:** `repeats` counts consecutive stage failures with the same signature, the first one
    included, so a fix that leaves the error unchanged escalates after one Opus cycle ("skip the remaining Opus
    cycles" when the signature appears errors.repeated_signature_skip = 2 times in a row); a failed verification
    counts as a used cycle but not as a repeat (the stage did not run); after the escalation cycle any failure
    blocks. A verdict with auto_apply no blocks at once with "<class>: <root cause>. Needs you: <user action>".
82. **The block streak** (logs/.block-streak: signature, count, label) counts only code-error blocks; an export
    or a drop clears it, a quality block (a stage's exit 20) leaves it alone, and a systemic stop clears it so the
    next start after the user's fix begins fresh. The third identical block goes to blocked.txt like the others,
    then the STOP line and logs/STOPPED.md (the error, the F files to read, how to re-add the ideas) and the
    runner exits 3 without starting the next idea.
83. **The working tree guard** (pipeline/lib/treeguard.py) protects the user's uncommitted work from the fixer:
    `git status` with content hashes before the fixer call and copies of the modified or untracked files outside
    the allowed paths; afterwards a file changed outside pipeline/ and motion-lib/candidates/ goes back (a tracked
    file to its copy or to HEAD, a new file is deleted); nothing already modified before the call is reverted to
    HEAD. Side effect seen in the tests: any file written inside the repo during the fixer call is put back too,
    so the fake claude's log lives outside the sandbox.
84. **Restart after a fix:** the runner writes <stage>/restart-note.md (what failed, which fix, which commit); a
    stage that resumes a model session reads and removes it with `ai_restart_note` (M4+); the INFO line reads
    "attempt N after the fix" instead of "(the previous one was interrupted)". A failed export goes through the
    same loop (stage 14-export, the export command in the report) and is tried again after a fix.

### Config, tests and Windows notes
85. **Config additions:** `errors` (transient_backoff_seconds, unparsed_limit_sleep_seconds, probe_every_seconds,
    repeated_signature_skip, log_tail_lines), `timeouts` (model_call_seconds 3600, reviewer_seconds 2400,
    fixer_seconds 2400, verify_seconds 900, probe_seconds 300; later milestones add tts, align and render) and
    `review` (reviewer_tools, fixer_tools, fixer_paths, protected_paths). Test knobs: REELS_SLEEP_SCALE,
    REELS_PROBE_MAX, REELS_LIMIT_MARGIN, REELS_CLAUDE (the binary) and the FAKE_CLAUDE_* variables of the fake.
86. **The fake claude** (pipeline/tests/fakes/claude, a bash shim over claude.py) answers by mode: ok, echo, every
    limit format on three channels (the JSON result, stderr, plain text), transient failures with a counter,
    hang (for the timeout), bad-json (the schema retry), fatal, resume-missing, tamper (the protected files guard)
    and the reviewer and fixer verdicts by policy (FAKE_CLAUDE_REVIEW yes, no, verify-fails; FAKE_CLAUDE_FIX ok,
    fail), detected from the "# Role:" line of the prompt; a script file gives one mode per call. It logs every
    call (flags, prompt head, model, the limit's moment) so the tests assert the exact command line. Real models
    run only in test-m3 section 4 (the planted bug), runnable alone with M3_SECTIONS=4.
87. **Windows notes found in M3:** a `C:/...` entry in PATH is invisible to Git Bash (use `/c/...`: the first fake
    probe silently reached the real CLI); the fake takes `/c/...` paths in its environment variables for the
    same reason; `$(( 008 + 1 ))` is an octal error in bash, so call numbers are read with `10#`; the Bash tool
    collapses `\\` to `\` inside heredocs, so inline Python that needs a backslash is written to a file first.

2026-10-31: CPU-only PC; voice = Chatterbox Turbo + Kokoro fallback, set by Gabriele in library/voice/engine.txt.
2026-10-31: no fallback voice. Only Gabriele's cloned voice; failures retry, then block the idea.

### M3 review 1 fixes (2026-10-31)
88. **A failed stage script is classified before any review (M3 review 1, fix 2).** BUILD_SPEC.md section 4 says
    "on any failed call or script"; until this fix only the model calls inside ai() were classified, so a stage
    that exited non-zero after a network reset, or after a tool printed a usage limit, went straight to the
    reviewer (who would most likely answer "external outage, auto_apply no" and block the idea). Now
    runner_stage_failed (runner.sh) runs errors.py on the exit code and the last errors.classify_tail_lines (40)
    of stage.log (the tail, not the whole log, so a benign old line that says "timeout" cannot turn a real bug
    into a transient): a limit waits with limit_wait (LIMIT, RESUME, logs/limits.log; an unparsed one sleeps and
    probes the probe model) and the stage runs again; a transient error prints RETRY and the stage runs again
    after 60 s, 4 min, 16 min (errors.transient_backoff_seconds, scaled by REELS_SLEEP_SCALE, a retry-after value
    larger than the step replaces it), and the fourth failure is a code error ("temporary error persisted after 3
    retries (<detail>): exit N: <last line>"); the counter is errors.<stage>.transient_tries in state.json, so a
    restart during a backoff keeps the ladder, and a success or a code error resets it. A stage whose own ai()
    call failed carries <stage>/error.json (the runner removes the file at every stage start, so it is this
    attempt's): that call was classified and retried inside ai(), so the stage is a code error at once. Exit 124
    and 137 count as a timeout (transient), as in ai(). The classifier's fatal flag is ignored for scripts (a
    missing tool is for the reviewer, not a login wall). The INFO line of the rerun says why: "attempt N after
    the temporary error" or "after the usage limit" (errors.<stage>.restart). The runner's own waits keep the
    heartbeat alive: limits.sh calls reels_wait_tick between its 60 s chunks when the caller defines it (runner.sh
    does, with runner_tick; stages and review-cycle do not define it). Tested by test-m3 section 9 with the
    fixture pipeline/tests/fixtures/stages/flaky/ (FLAKY_MODE reset, limit, error; FLAKY_FAILS) and the aicall
    fixture's AICALL_FAIL_NOTE (a transient-looking last line after a model call error: no second classification).
    The limit path is bounded since review 2 (item 91).
89. **The review loop survives a restart (M3 review 1, fix 1).** Before this fix review_note_failure stored the
    signature before the cycle ran and review_record counted the cycle after it, so a runner killed during
    cycle 1 ran the stage again on restart, counted the identical failure as the second repeat and escalated to
    Fable with zero Opus reviews (and counted the open issue twice). Now state.json errors.<stage>.review
    (active, rc, msg, cmd, activity) says a failure is in the loop and errors.<stage>.pending which cycle E<n>
    runs now; the cycle's child pid is errors/E<n>.pid (like a stage's .pid). A runner that finds a failed stage
    with an active review resumes the loop instead of running the stage again (runner_resume_review and
    runner_review_loop in runner.sh): a child that still runs is adopted (WARN, wait with the heartbeat, take its
    verdict); a finished child's F<n>.result.json is taken when it holds a verdict (fixed, no_auto, failed); a
    cycle that ended without one (killed with the runner) runs again under the same E<n> after an INFO line
    ("review cycle E1 (cycle 1/3, opus) was interrupted by the previous runner, resuming it: ..."), without a
    repeated ESCAL line and without a second ERROR line. So no Opus cycle is lost, the open-issue counter stays at
    one, and the failure is not a repeat: repeats grow only when the previous failure got its review
    (errors.<stage>.reviewed, false after review_note_failure, true after review_record), which is the spec's
    "twice in a row" across review attempts. A runner killed between the verdict fixed and the restart
    (last_outcome fixed, nothing pending) just runs the stage again. The INFO line of a rerun of a failed stage
    names the recorded reason ("after the fix" only when a fix was applied); a stage that was running when the
    runner died keeps "(the previous one was interrupted)". A cycle that crashes while the runner lives still
    counts as a used cycle (unchanged). Tested by test-m3 section 10: the whole tree killed while the fake
    reviewer hangs (FAKE_CLAUDE_MODE=hang), then only the runner killed while the fake reviewer is slow
    (FAKE_CLAUDE_DELAY, new) so the restart adopts the child.
90. **The classifier's text patterns are tightened for stage logs (M3 review 1, fix 2).** The same patterns now
    read the tail of a failed stage's log, which is far noisier than a CLI result, and the first dry run showed
    the unfixable fixture's "FileNotFoundError: library/keys/service.key is missing" classified as transient:
    ENOTFOUND matched inside FileNotFoundError, case-insensitively. So the error codes are word-bounded
    (ECONNRESET, ECONNREFUSED, EPIPE, EAI_AGAIN, ENOTFOUND, ENETUNREACH, ETIMEDOUT), an HTTP status number
    counts only next to a word that makes it one ("API Error: 503", "HTTP 502", "status 500", "error 429", not
    "wrote 503 bytes"; the JSON field api_error_status still counts on its own), and "temporary" alone is not
    an outage ("temporary file" is a code error, "temporary failure in name resolution" and "temporarily
    unavailable" are transient). test-limits.sh checks each of these texts; the detail label of a 529 found in
    text is "overloaded", like the one found in the JSON field.

### M3 review 2 fixes (2026-10-31)
91. **The limit path of a failed stage script is bounded (M3 review 2, fix 1).** Item 88 waited out every limit
    message a stage printed and ran the stage again, with no counter: a stage that kept printing the same text
    waited forever (a parsed "resets 3pm" rolled to the next day at every attempt; an unparsed one slept 30 minutes
    and probed, the probe answered at once, and the stage failed again), which breaks rule zero and keeps a code
    error away from the review. Now runner_limit_failed (runner.sh) keeps errors.<stage>.limit_tries,
    limit_message, limit_waited and limit_probes in state.json (a restart keeps them; a success or a code error
    resets them, like transient_tries). The first limit message always gets its wait (LIMIT, RESUME,
    logs/limits.log). The same failure is a code error for the review loop, with the message "usage limit message
    persisted after N wait(s) ...: exit N: <last line>", when (a) the message comes back unchanged right after a
    wait that completed (limit_waited; a runner killed during the wait and restarted before the reset reruns the
    stage, and the same real limit message earns its wait again): for a parsed limit the reset time it named has
    passed, so a genuine new limit would name a new time; for an unparsed
    limit only when the probe model answered on its first try, which showed no limit was active, so the text is
    not a limit (an unparsed limit whose probe needed several tries may come back with the same text, because the
    text has no time in it, and gets another wait); or (b) after errors.script_limit_retries waits (config, default
    2) whatever the message. The reviewer then sees the full log. Found while testing the cap: stage.log is
    appended across attempts and the limit detector takes the first limit line of the tail, so attempt 2 was
    classified from attempt 1's line; runner_log_mark now records the log's size at every stage start
    (<stage>/.log-offset) and runner_stage_failed classifies only this attempt's part of the log
    (runner_log_attempt), so an earlier attempt's limit line or network error is never read again. Model calls
    inside ai() are not affected: a limit the CLI reports is a real one, and its wait loop stays as it was.
    Tested by test-m3 section 9 with the flaky
    fixture (FLAKY_MODE limit with FLAKY_FAILS 99: one LIMIT, one RESUME, ERROR, one review, BLOCK, the runner
    ends by itself; limit-new, a new reset time each time: two waits then ERROR; quoted-limit, a log line quoting
    "hit its usage limit, it resets weekly" before a JSONDecodeError traceback: one LIMIT, the probe answers,
    ERROR, one review).
92. **Echoed source lines are not error messages, and a timeout has to look like one (M3 review 2, fix 2).** A
    Python traceback prints the source line of every frame, so a plain KeyError whose frames held
    `subprocess.run(cmd, check=True, timeout=600)` matched the bare word "timeout" and became transient (three
    retries, 21 minutes, and an ERROR line blaming a timeout). Most tracebacks from M4 on will hold such a line
    (ffmpeg, renders, TTS and alignment run through subprocess with the configured timeouts), and Node errors
    echo `page.setDefaultTimeout(120000)` and frames like `at Timeout._onTimeout (node:internal/timers)`. So
    errors.py strip_echo() removes, before any pattern runs, the lines indented deeper than a `File "...", line N`
    line (the code and its carets), caret-only lines with the code line above them (Node's uncaught-exception
    header) and JavaScript stack frames (`    at ...`); exception lines, chained causes ("cause: Error: read
    ECONNRESET", "The above exception was the direct cause") and ordinary log lines stay, and the message of the
    ERROR line still comes from the raw text. The timeout words are TIMEOUT_WORDS: "timed out", TimeoutError,
    TimeoutException, TimeoutExpired (and ReadTimeoutError and the like), ETIMEDOUT, ESOCKETTIMEDOUT, undici's
    UND_ERR_*_TIMEOUT, "timeout exceeded | expired | reached | elapsed | occurred | after N | of N | while |
    waiting", "Timeout 30000ms exceeded", "i/o timeout", "due to timeout", "deadline exceeded" and the noun phrases
    "request | connection | connect | read | handshake | navigation | socket | response | idle | operation |
    network | upstream | api timeout" when not followed by a number (a setting). The bare word "timeout", a
    keyword argument, a CLI flag or a config echo ("timeout 600 s") no longer count; exit 124 and 137 still do.
    The whole 40-line tail is still matched (a transient line early in the tail still wins over an exception at
    the end: the reviewer's optional note, left open). Tested by test-limits.sh (the KeyError traceback, the same
    traceback ending in TimeoutExpired, the Node setDefaultTimeout line, Node frames, an echoed `raise
    ConnectionError("read ECONNRESET")`, curl's "timed out", a config echo) and test-m3 section 9 (the traceback
    fixture: ERROR at once, no RETRY, one review).

### M3 review 3 fixes (2026-11-01)
93. **The classifier knows the network wordings this PC really produces (M3 review 3, fix 1).** The transient
    patterns knew Node's and Linux's wording (ECONNRESET, "connection reset", ENOTFOUND, getaddrinfo) but not
    Windows Python's, Chromium's, gh's, curl's or Claude Code's own, so a network blip in a stage script or a model
    call was a code error at once: a review (whose own call may fail the same way), most likely an "external
    outage, auto_apply no" verdict, a blocked idea, and three in a row a systemic stop. errors.py now groups the
    wordings by label: "connection reset" (ECONNRESET, "connection reset", "socket hang up", EPIPE,
    ConnectionResetError, ConnectionAbortedError, BrokenPipeError, RemoteDisconnected, "Connection aborted",
    "forcibly closed by the remote host", "remote end closed connection", WinError or Errno 10053 and 10054,
    "connection dropped"); "connection refused" (ECONNREFUSED, "connection refused", ConnectionRefusedError, the
    CLI's bare ConnectionRefused, "actively refused", WinError or Errno 10061, curl's "Couldn't connect to server"
    and "Failed to connect to"); "network error" (EAI_AGAIN, ENOTFOUND, getaddrinfo, "network error", "fetch
    failed", ENETUNREACH, EHOSTUNREACH, ENETDOWN, Claude Code's "No response from API", "Can't reach the API
    server", "Unable to connect to API", FailedToOpenSocket, the SDK's "Connection error." and "API Error:
    terminated", Chromium's net::ERR_CONNECTION_*, NAME_NOT_RESOLVED, INTERNET_DISCONNECTED, NETWORK_*, TIMED_OUT,
    ADDRESS_UNREACHABLE, EMPTY_RESPONSE, PROXY_CONNECTION_FAILED and SOCKET_NOT_CONNECTED, curl's "Could not
    resolve host", gh's "error connecting to" only together with its "check your internet connection" line,
    Python's ConnectionError, NewConnectionError and NameResolutionError, urllib3's "Max retries exceeded");
    "stream interrupted" gains the CLI's "Connection closed mid-response", "The response stopped arriving" and
    "response above may be incomplete". Every code is word-bounded and every phrase whole, so KeyError,
    FileNotFoundError, a plain "connection" in a log line or "error connecting to" without gh's second line stay
    code errors. The wordings come from this PC's own Claude Code session logs ("Can't reach the API server" 117
    times, "Unable to connect to API (ENOTFOUND)" 32, "(ConnectionRefused)" 13, "(FailedToOpenSocket)" 10,
    "Connection dropped (ECONNRESET)" 6, "No response from API", "Connection closed mid-response"). Tested by
    test-limits.sh section 3 (one check per wording, the CLI ones as a JSON result with exit 1, plus the negatives)
    and test-m3 section 3 ("No response from API" through ai(): RETRY, then the retry succeeds).
94. **No external text carries an em dash into a line or file the runner composes (M3 review 3, fix 2).**
    BUILD_SPEC.md 0.7 forbids the em dash in any file or terminal message, and the Claude CLI's network message on
    this PC contains one ("Can't reach the API server (em dash) check your internet or DNS (ENOTFOUND)"): copied
    verbatim it reached the ERROR and BLOCK lines, logs/runner.log, status.txt, history.txt, blocked.txt,
    state.json, E<n>.md and the reviewer prompt (F<n>.md and the known-issues line were already cleaned). Now
    log.sh defines REELS_EM_DASH and REELS_EN_DASH from their UTF-8 bytes (the source stays clean), reels_undash VAR
    (in place) and undash TEXT: an em dash becomes ", " whatever the spaces around it, one at either end is
    dropped, an en dash between spaces is treated the same and one inside a word (a range of numbers) becomes a
    hyphen. say() cleans every line it prints (terminal, runner.log, status.txt, a stage's own say lines
    included), and the composers clean their text before writing: runner_last_log_line (so the message that becomes
    the ERROR line, state.json, E<n>.msg, the fixer prompt and the restart note is clean), errors.py's undash() on
    the classifier's message (the same rules in Python; ai()'s AI_ERROR and error.json come from it, and
    ai_write_error and the schema-retry errors are cleaned as well), history_add and blocked_add (every field, the
    idea's braces copy included), runner_write_stopped (STOPPED.md), runner_drop and runner_block (the reason, which
    may be a model's text), review_error_file's "- error:" line, review_restart_note, review_write_result (a verify
    log line in F<n>.result.json) and limits_log. The verbatim log excerpts inside E<n>.md (the stage.log tail, a
    call's stderr) and the raw call files under calls/ stay as they are: they are evidence for the reviewer. Tested
    by test-m3 section 9 (the flaky fixture's netdash mode prints the CLI's message with a real U+2014 at every
    attempt: three RETRY lines, the ERROR line with a comma, BLOCK, then a byte scan of the runner output,
    runner.log, status.txt, history.txt, blocked.txt, state.json, E1.msg, F1.md, F1.result.json and E1.md's error
    line finds no U+2014 while stage.log and E1.md's log excerpt still hold it), test-m3 section 3 (the same message
    through ai(): AI_ERROR, runner.log and error.json clean) and test-limits.sh (the classifier's message).

## M4 (2026-11-01)

### Stages S1 to S4
95. **The model scores and writes fields; the code decides and renders the files.** Every M4 stage has two
    schemas: model.schema.json (what the model answers with `--json-schema`, kept to types, enums and required
    lists, because the CLI's structured-output validator is not given patterns or lengths) and schema.json (the
    stage's primary output, validated by the runner). pipeline/lib/research.py, expansion.py and gate.py render
    research.json, facts.md, numbers.json, assets.json, expansion.json, expansion.md and gate.json from the model's
    answer, so the format never depends on the model, every text is cleaned of em dashes at the source
    (errors.undash) and of CR characters, and the rules of spec S2 and S3 (the pass thresholds, F forced to fail on
    a false or unverified core claim, the angle cap, the different-topic drop) live in Python with unit tests
    (test-m4 section 1). A stage's own quality loop (an expansion that breaks a rule) asks the model again in the
    same session with the exact problems; only a model call that fails or an answer still invalid after ai()'s one
    schema retry is a code error.
96. **Session A and the reseed (pipeline/lib/session.sh).** `session_call KEY ROLE STAGE_DIR PROMPT [ai options]`
    wraps ai() with `--session A`; when ai() returns 3 (the stored session no longer exists) it forgets the id and
    calls again in a new session whose prompt starts with the prompt's own header lines (# Role, # Stage), then the
    run's memory (the idea, facts.md, expansion.md, the latest gate verdict as a list of scores, evidence and the
    angle hint), then the task itself. S1, S2 and S4 use it; S1 too, so a re-run after an automatic fix resumes the
    session with the restart note in the prompt instead of researching from zero. The gate (S3) never passes
    --session: a fresh session B each round, as the spec asks.
97. **facts.md numbering is stable and every numbered claim has a source.** research.py sorts the claims once
    (verified before unverified before false; within a status primary, vendor, press, forum; the model's order
    otherwise), numbers them, and the expansion's evidence pointers are facts.md#n. The angle stage's new claims are
    appended with the next numbers (research.py append-claims, deduplicated on the text, or the text plus the URL)
    and nothing is ever renumbered, so earlier pointers stay right. A claim without an http(s) URL is moved to the
    "Unverified or unsourced" section instead of being numbered, which is what makes "every claim line carries a
    URL and a checked date" true by construction; a number without a URL goes the same way.
98. **The angle loop is driven by files, not by counters, and handed over through reopen.txt.** The gate round is
    1 plus the number of 04-angle/angle-*.json files; the angle round is the number of 03-gate/gate-*.json files
    whose decision is angle; state.json rounds.angle is set (not incremented) by the angle stage. A stage run again
    after a crash or an automatic fix computes the same round and overwrites the same files. The handover: a stage
    that wants other stages to run again writes their keys to <stage>/reopen.txt and state.py stage-done reopens
    them (pending, .done removed, attempts back to 0, the round counted in the record's "reopened") in the same
    write that marks the stage done, so a crash between "gate done" and "angle pending" cannot happen; stage-start
    removes a reopen.txt left by an earlier attempt. The gate names 04-angle, the angle stage names 03-gate, and the
    runner needs no stage-specific code (M11's fix routing will use the same file). The runner's "attempt N (the
    previous one was interrupted)" line therefore counts the attempts of the current round only.
99. **expansion.md is composed, not written by the model.** One fixed layout (a title line, Problem, Solution,
    "Share driver: <identity>. Takeaway worth forwarding: <takeaway>", "Comment keyword: <KEYWORD>. Deliverable
    (existing): ... (link)" or "(NEW, to create)", One specific true thing, and one "- facts.md#n: note" line per
    pointer), so the gate always reads the same shape and the length is measured here. expansion.py checks: one
    first-person sentence for the problem (I, my, me; no second sentence), an identity of at least two words, a
    keyword of 3 to 20 letters or digits written in capitals, 2 to 6 pointers each naming a claim marked verified,
    and 500 to 1500 characters (config research.expansion_chars). A keyword that is not in deliverables.txt is NEW
    whatever the model said; one that is in the file is existing with the file's link and its "what". A failed
    check is asked again in the same session with the exact problems and numbers ("cut about 140 characters"),
    research.expansion_tries (3) times; the last try is written anyway with a NEEDS REVIEW flag (rule_errors in
    expansion.json), never an error.
100. **The gate's decision rules are code (gate.py decide).** F fails whatever the model answered when
    research.json says the core claim is false or unverified (the spec's "the tool does not do what the idea
    assumes, or the claims cannot be verified"), and F failing drops at once; pass is P, S and C at least 2 with F
    ok; a different_topic verdict with a suggested idea drops and writes the suggestion; otherwise an angle round
    while the angle rounds done are below caps.angle_rounds, else a drop. The model is told in its prompt that it
    does not decide, only scores with quoted evidence, and the score levels 0 to 3 are spelled out for each
    criterion so rounds are comparable. Drop reasons carry the scores in the spec's form: "facts don't hold (P2 S2
    C2 F fail): ...", "still failing after 2 angle rounds (P3 S1 C3 F ok): ...", "no angle keeps the core topic
    (...): ...; suggestion written to logs/suggested-ideas.txt" (the core claim's note is cut at 160 characters in
    the reason). The GATE line is "passed (P3 S2 C3 F ok)" plus "after N angle round(s)" when there were any, the
    ANGLE line "gate failed (S1): finding a better angle, round 1/2" (the letters below 2 with their scores).
101. **logs/suggested-ideas.txt** (gate.py suggest) gets a comment line (date, the stage, the idea it came from)
    and the suggestion in braces with inner braces turned into parentheses, so a block can be pasted into
    add-idea.sh as it is; the file is never read by the runner and ideas.txt is never written by a stage. Both the
    gate (different_topic) and the angle stage (keeps_core_topic false) write it before the drop.
102. **A missing profile file is a flag, recorded once.** library/profile/account.md does not exist yet (M5 drafts
    it): S1, S2 and S4 continue with default audience assumptions and call flag_once (stage.sh), which records the
    NEEDS REVIEW flag in state.json only when the same text is not there yet, so a run prints one FLAG line
    although three stages notice; the export's NEEDS REVIEW section carries it (M12). An empty or missing
    deliverables.txt means every keyword is NEW, without a flag (HUMAN_TODO M1 already asks for the file).

### Research tools
103. **Screenshots: pipeline/bin/screenshot over pipeline/lib/screenshot.py (Playwright 1.64, Chromium 156,
    installed by setup-python).** A 1080x1920 viewport by default (the reel's own aspect) and --full-page capped at
    4 screens; NN-name.png plus a NN-name.json sidecar (url, final_url, title, status, size, captured). The output
    folder must be inside the runs folder of the state root ($REELS_RUNS, else $REELS_ROOT/runs; the system temp
    folder only when neither is set), so the model cannot write anywhere else through it; the same URL in the same
    folder is reused (--again forces a new capture). A 401, 403, 429 or 503, or a bot-check page (title or body
    with "Just a moment", "Verify you are human", "Access denied", "captcha" and the like, on a short page) is
    reported as blocked and nothing is saved: plain headless Chromium, no user agent spoofing, no stealth plugin,
    as spec S1 demands. Exit codes 0 saved or reused, 2 blocked, 3 Playwright missing, 4 the page did not load, 1
    refused. Playwright is a warn-level preflight item: a PC without the browser makes worse reels (no real page
    to show), not a stopped runner; the research stage prints a WARN line when no screenshot was saved.
104. **Research tools and permission rules.** The research model (S1 and S4) gets `--tools "WebSearch WebFetch
    Read Bash"` and explicit allow rules from config research.allowed (WebSearch, WebFetch, Read, `Bash(gh *)`,
    `Bash(gh:*)`, `Bash(bash pipeline/bin/screenshot *)` and its colon form) through the new repeatable `--allow
    RULE` option of ai(): a rule with a space cannot travel in the space-separated --allowed string, and when
    --allow or --allowed is given the --tools list is no longer pre-approved wholesale, so a bare Bash is never
    approved. Probed with haiku on 2026-11-01: both rule syntaxes are accepted and gh runs without a prompt; auto
    mode's own classifier also lets a harmless `echo` through, so the rules guarantee gh and the screenshot tool
    rather than fence everything else, and the prompt forbids other commands (one command per call, no pipes, no
    writes, no clones) while the protected files stay denied and guarded by protect.py. Read is included so the
    model can open a screenshot it took and see that it shows the page. No --max-turns on the research call (a
    max-turns stop would come back as an error, not a result); timeouts.research_seconds (2700) bounds it, and a
    timeout kill is a transient error with its three retries.
105. **The expansion and the gate run without tools** (`--tools ""`): the research is in session A's context for
    S2 and facts.md is inlined for both, so a one-turn answer is enough and nothing can be fetched or written.
    Timeouts: research_seconds and angle_seconds 2700, expansion_seconds and gate_seconds 900.

### Tests and fixtures
106. **The false idea fixture** (pipeline/tests/fixtures/ideas/false-idea.txt) is an ffmpeg flag that does not
    exist (`--make-reel`), chosen so the core claim is false with no partial truth to angle toward: the research
    marks the core claim false, gate.py forces F to fail, and the drop happens at the first gate with "facts don't
    hold (P S C F fail)". An idea whose nearest true feature is a different topic would also drop, but through the
    slower angle path, which is not what the acceptance test wants to time.
107. **Frozen fixtures and the fake's stage fixtures.** pipeline/tests/fixtures/runs/test-idea/ (written by
    `M4_FREEZE=1 bash pipeline/tests/test-m4.sh`) holds the real outputs of the test idea: research.json,
    facts.md, numbers.json, assets.json with the PNG screenshots and their sidecars, expansion.json and .md,
    gate.json and gate-*.json, the model's structured answers (calls/*.out.json, cleaned of em dashes when frozen:
    the stages clean what they render, not the raw answers, and no file of the repo may hold one) and idea.txt;
    M5 starts from them (and exercises the reseed, since no session exists). .gitignore's runs/, exports/, logs/ and .locks/ are now
    anchored to the root (/runs/) so the fixtures folder is tracked. pipeline/tests/fixtures/fake/m4/ holds
    model-shaped answers (01-research.json, 02-expansion.json, 03-gate.json scoring S1, 04-angle.json, and the
    variants pass and false) that the fake claude serves by the prompt's "# Stage: <key>" line
    (FAKE_CLAUDE_FIXTURES=<dir>, with <key>.<n>.json for the n-th call of that stage), so the whole angle loop runs
    through run.sh in about a minute without a model: two rounds then the drop, a pass on round 2 that continues to
    the export, an F failure, a different-topic verdict.
108. **Earlier milestones touched by M4:** state.py (reopen.txt applied in stage-done, cleared in stage-start,
    reopen resets attempts; M2), ai.sh (--allow; M3), the fake claude (fixtures by stage; M3), tests/lib.sh (the
    profile's .md files copied into the sandbox, dummy_after; M1), config.json (research, the new timeouts, the
    playwright warn check; M1), setup-python and requirements.txt (playwright and its Chromium; M1), .gitignore
    (anchored folders; M0), the dummies of 01-research and 03-gate (the refined schemas; M2). One earlier test
    changed because its premise did: test-m2 section 7 expected the runner to stop at S1 ("not built yet") when
    run without REELS_DUMMY; with the real S1 in place that started a real research call and timed out. The
    section now finds the first stage without a run.sh (05-hooks today), runs the built stages as dummies and
    expects the stop there, and skips itself once every stage exists, so later milestones do not break it again.
    Everything else in M1 to M3 passes unchanged.
109. **Windows notes found in M4:** the Bash tool's heredoc backslash collapsing bit again (a Python patch with a
    literal `\r` became a carriage return and matched nothing), so patches that need a backslash go through the
    Edit tool; a `/dev/null` path handed to Windows Python is not a file, so "no file" is passed as /nonexistent
    and the readers treat any OSError as an empty list; `python -m http.server` in the test serves the local pages
    the screenshot checks need (no network in section 1).
