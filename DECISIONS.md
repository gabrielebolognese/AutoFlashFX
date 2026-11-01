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
2026-11-01: reel voice = Kokoro af_bella, single voice, no fallback; silence tightened per beat (-40 dB, pauses of 0.3s or more cut to 0.1s, 1.0s breath after the hook). am_puck saved in library/voice/engine-puck.txt for later.
2026-11-01: reels are problem-first; the solution is FlashFX, an external tool or repo, or a method, chosen per reel by the pipeline (rules in account.md).
2026-11-01: FlashFX brand kit in library/brand/ (from the 2026 brand guide). The reel style is unchanged; the FlashFX lockup and DM avatar appear at every CTA, other FlashFX branding only when FlashFX is the solution.

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
    timeout kill is a transient error with its three retries. The gh rules of this item were narrowed to the
    read-only forms, with the writing forms denied, by item 111 (M4 review 1).
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

### M4 review 1 fixes (2026-11-01)
110. **The angle stage cleans the model's `change` text before anything is composed from it (M4 review 1, fix
    1).** 04-angle/run.sh read the model's `change` field with json_file_field (json_field does not clean) and the
    Python heredoc wrote it verbatim into angle.json and angle-<n>.json; the drop reason and the INFO line were
    cleaned by stage_drop and say, and the next round's prompt by prompt.py, so the two JSON files were the one
    path where a model's em dash reached a file (the rule of item 95 and CLAUDE.md; the gate and research models
    do write them, item 107). The fix is `reels_undash change` right after the field is read, so every use (the
    files, the drop reason, the "Earlier angle rounds" section of the next prompt) gets the cleaned text.
    test-m4 section 2 plants two em dashes in the sandbox copy of the 04-angle fixture's change (chr(0x2014) in
    the test, so the repo file stays clean) and asserts that angle-1.json holds the comma form and that
    angle.json, angle-1.json, angle-2.json and prompt-angle-r2.md hold no U+2014.
111. **The research model's gh access is read-only by rule, with the writing forms denied (M4 review 1, fix 2).**
    Item 104's `Bash(gh *)` pre-approved every gh subcommand with the user's logged-in gh account (token scopes
    gist, repo, workflow) for a model that reads untrusted pages through WebFetch: a prompt injected in a fetched
    page could have published a gist or opened an issue, and an explicit allow rule skips auto mode's classifier.
    Now config research.allowed lists only the read-only forms spec S1 names, `Bash(gh repo view *)` (the README
    too, without --json), `Bash(gh release list *)`, `Bash(gh release view *)` and `Bash(gh api repos/*)`, plus
    WebSearch, WebFetch, Read and the screenshot tool; the new config research.denied lists the forms that act on
    the account or the disk: `gh auth`, `gh gist`, `gh repo clone`, `gh release download`, the verbs that write as
    `Bash(gh * <verb> *)` (create, delete, edit, comment, merge, close, reopen, review, fork, sync, transfer, lock,
    upload, run, rerun, cancel, set, add, archive, rename) and `gh api` with a method or a field flag as
    `Bash(gh api* -X*)`, `--method`, `-f`, `-F`, `--field`, `--raw-field` and `--input` (the flag in any position:
    `gh api* -X*` needs the space before the flag, so a repository named foo-Xbar is not caught, and `* create *`
    needs the space after the verb, so `--json createdAt` is not caught). Both lists travel through
    research_call_args (stage.sh, shared by S1 and S4, with the same lists as defaults when config lacks them) and
    ai()'s new repeatable `--deny RULE` option (the space-separated `--disallow` cannot carry a rule with spaces,
    item 104). Deny rules although the allow list is narrow: in auto mode a command outside the rules goes to the
    classifier, which is a judgement, while a deny rule resolves first in every mode and applies to every
    subcommand of a compound command (the Claude Code permissions reference: a `*` matches any text, a rule
    matches the whole command, deny wins over allow, and `:*` is the same as a trailing ` *`, so the colon forms
    of item 104 were dropped). Probed on 2026-11-01 with pipeline/tests/probe-gh-rules.sh (haiku, 16 commands,
    each harmless even if executed: a missing file, a missing endpoint, a repository that does not exist). In
    auto mode through ai(), the production path, the six read-only forms ran (`gh repo view cli/cli --json
    stargazerCount` gave 46828 stars, `gh release list`, `gh release view`, `gh api repos/cli/cli`, `gh api
    repos/cli/cli/commits?per_page=1` quoted and unquoted) and the ten writing forms were refused by the
    permission system ("Permission to use Bash with command gh gist create ... has been denied": gist create,
    api -X POST, api -f, api --method DELETE, auth status, label create, repo clone, release download, workflow
    run, and the compound `gh repo view ... && gh gist create ...`), all listed in the result's permission_denials.
    In manual mode with the same rules (anything outside the allow rules refused) the same ten were refused and
    the read-only forms ran, except the quoted endpoint `gh api "repos/cli/cli/commits?per_page=1"`, which
    `Bash(gh api repos/*)` does not match because the quote comes before repos/ (in auto mode the classifier had
    let it through): the research prompt's example is the unquoted form and says so. Known limits, from the same
    reference: a deny rule does not match the program by path or inside `sh -c`, so a wrapper falls to the
    classifier; the prompt keeps forbidding every other command and the protected files stay denied and guarded
    by protect.py. test-m4 section 2 asserts from the fake claude's log that the research call and both angle
    calls carry the read-only allow rules and none of `Bash(gh *)`, `Bash(gh:*)` or a bare Bash, and that the deny
    rules are passed; section 3 prints the Bash calls the real research call had refused and asserts that none of
    them was a read-only gh form.

### M4 review 2 fixes (2026-11-01)
112. **An F fail of the expansion's wording is repaired by an angle round; only an F fail of the idea's facts
    drops at once (M4 review 2, fix 1).** Spec S3 says "F failing (the tool does not do what the idea assumes, it
    is deprecated, or the claims cannot be verified): drop immediately", and items 95 and 100 read it literally:
    any F fail the model gave dropped the idea. In review 2's run the gate model failed F on the test idea because
    the expansion said "serif" (the article names Inter, a sans-serif) and "one command adds" (the docs describe a
    scope step): two slips of the pipeline's own writing model (S2), while the research had verified the core
    claim; the same idea had passed F in the report's run, in review 1 and in fixes 1. The idea was deleted from
    ideas.txt over a sentence S4 exists to rewrite, and the acceptance test passed or failed by chance. The
    reading recorded here: the spec's three reasons are faults of the idea (the tool, its status, its
    verifiability), a statement that can simply be removed from the expansion is not one, so "drop immediately"
    applies to the idea's facts and not to a wording slip the pipeline can fix. If the user wants the literal
    reading, the change is one line in gate.py (read kind wording as core; build/HUMAN_TODO.md M4).
    How: the gate model now says what kind of F failure it found (F_kind in model.schema.json and the prompt):
    "core" when the idea does not hold (the tool does not do what the idea assumes, it is deprecated, the core
    claim is unverified or false, or the solution or the one specific true thing rests on a false or unverified
    claim that no verified claim could replace), "wording" when a statement of the expansion is not in facts.md
    or says more than its claim says while the idea holds without it, "none" when F is ok. gate.py decide: a false
    or unverified core claim is still code-forced to F fail with kind core, and an F fail of kind core drops at
    once ("facts don't hold (P S C F fail): ...") exactly as before; an F fail of kind wording with the core
    verified is treated like a failing P, S or C: decision angle while angle rounds are left (the ANGLE line
    "gate failed (F wording): finding a better angle, round 1/2", or "S1 F wording" when both fail), else a drop
    "still failing after N angle rounds (P3 S3 C3 F fail): ...". A fail without a kind (a malformed answer; the
    schema requires the field) is read as core, the spec's strict default. The repair runs in S4 and not in a new
    step because S4 is the spec's own "rewrites expansion.md, then the idea goes back to S3", it already has
    session A, the research tools and the gate's quoted evidence, and caps.angle_rounds bounds it without a new
    counter: the angle prompt gets a section "F failed for wording: fix this first" (remove each quoted
    statement, or reword it from a verified claim, or research it and add the claim to new_claims), its verdict
    line reads "Failing: F (wording)", the gate's angle_hint names the statements (gate.py builds one from the F
    evidence when the model left it empty), gate.json carries F_kind and model_F_kind and lists F in failing,
    angle.json records previous_F_kind, the next gate round's history shows "F fail (wording)" and the reseed's
    gate section says what F failed for. The S2 and S4 prompts now ask for the claim's own wording (the install
    steps exactly as the docs give them, a font or a color named as the claim names it, no added detail, step
    count or adjective), so the slip happens less often in the first place. Tests: test-m4 section 1 (gate.py:
    wording with the core verified is an angle, no round left a drop with the scores, a false or unverified core
    drops whatever the kind, kind core drops, no kind drops, S1 plus wording names both, the built angle hint),
    section 2 (the fake gate fails F for wording on round 1 and passes on round 2: ANGLE, GATE "passed (P3 S3 C3
    F ok) after 1 angle round", DONE, no DROP; the angle prompt holds the repair section and the quoted
    statement; the run folder is taken from the START line because ls here sorts "<id>-2" before "<id>"), and
    section 3 run three times in a row with the real models (build/M4/fixes-2.md has the lines of each run).

## M5 (2026-11-01)

### Vendored tools
113. **Vendored at commit d03c56bb598be770c60b201f94237e5d1a4268a6 (2026-09-13)**, fetched with `gh api` (raw
    content at that commit) rather than copied from ~/.claude/skills: the installed skills hold the same bytes with
    CRLF endings, and the pinned fetch is what VERSION records. LICENSE and templates/voice.md come along.
    pipeline/bin/vendor-run runs a vendored script with `python -I -X utf8 <script>`: isolated mode so a stray
    module next to the input can never shadow a standard one, and UTF-8 forced on the command line because -I
    implies -E, which ignores PYTHONUTF8. detect.py, humanize.py and slop.json contain em dashes; the scan skips
    pipeline/vendor/ (item 4) and nothing of theirs is copied into a file of ours.

### The hooks index (pipeline/bin/index-hooks, pipeline/lib/hooks.py)
114. **The id hashes the normalized text:** NFC, em dash to comma, straight quotes, the surrounding quotes
    stripped, whitespace collapsed, lower case; sha1, first 10 hex. So fixing an em dash into a comma, a case fix
    or re-quoting a line keeps its stats, while any wording change gives a new id (the spec's "stats survive adding
    and deleting other lines"). A duplicate line is indexed once and listed in the lint.
115. **The cache:** the index keeps source_sha1 of the file (CR stripped) and the classification per id. An
    unchanged file with nothing unclassified means no model call and no rewrite ("a second run makes no model
    call"); a changed file sends only the ids not classified yet to one batched indexer call and keeps the rest by
    id; an id the model skipped stays "unclassified" and is asked again at the next run. The call's files live
    under logs/index-hooks/calls/, because ai() wants a stage folder and the index is not a run stage.
116. **The lint** (library/hooks.lint.txt, for the user, never read by the runner): a broken blank by heuristics
    (a preposition or article followed by punctuation or the end of the line, a preposition followed by an adverb
    and a word as in "progress in actually looks", a lone or triple underscore), em dash lines, duplicates, and
    the model's grammar note per hook (issue, under 15 words; the real indexer also named the two lost blanks).
117. **The stats** (library/.hooks.stats.json, keyed by template id: the hooks.txt ids and the vendor ids v01 to
    v26): picked, won, scores (the last 20 normalized Borda scores), last_picked, last_won, text. Win rate =
    (won + 1) / (picked + 2): 0.5 with no data, which is the spec's "uniform at first". The judge wrapper updates
    it after judge.json is written, never the model.
118. **The vendor's 26 formulas are mapped to the six families by judgment** (hooks.py VENDOR_FAMILY), with
    fits_problem_solution false for the pure story shapes (Cost Confession, Insider Leak, The Flop Record,
    Mid-Sentence Start, The Reveal, Someone Else's Result).

### S5 Hooks
119. **The shortlist is code, the hooks are the model's.** hooks.py shortlist offers config hooks.shortlist (24)
    templates: the hooks.txt lines (minus broken blanks and duplicates) plus the 26 vendor shapes; at least
    hooks.per_family (2) per family when the pool has them (a weighted sample inside the family), the rest a
    weighted sample without replacement; weight = win rate x (1 for a fit template, hooks.fit_weight_other 0.35
    otherwise); seeded by the idea id, so a restart offers the same list and different ideas get different ones.
    The model writes 12 to 20 hooks from the list (it may skip a template) and the code enforces the counts, the
    families and the template ids. A personal-story angle: the prompt tells the model to prefer the story
    families then; every family is on the list anyway.
120. **The spoken cap** is min(8, ceil(wpm x 3 / 60) - 1) words: "8 words or fewer, under 3 seconds" at 150 wpm
    means 7 words (8 words would take 3.2 s), at the measured 195 wpm 8. Words are counted as the vendor's
    hookscore counts them (letters, digits, $ % ' and hyphens; "1,134,112" is one word, "1.1.1" is three, as it is
    spoken). The cap, the wpm and the seconds per hook are written into hooks.json.
121. **The marker check:** the marker must be quoted from the spoken line and look like a number (a digit or a
    number word), a time (a time word) or a name (an uppercase letter or a non-letter character: Claude Code,
    frontend-design, SKILL.md, /plugin). marker_kind is recorded, but any passing rule accepts the hook.
122. **The quality loop:** hooks.py check returns the exact problems per hook (the cap with the wpm, the on-screen
    cap, the marker, an unknown template_id, an unknown family, a repeated line) and the global ones (count,
    families); the stage asks again in the same session up to hooks.tries (3) times; the last try writes the valid
    hooks with a NEEDS REVIEW flag, and fewer than hooks.min_for_judge (4) valid hooks blocks the idea (exit 20):
    a model that cannot write four valid hooks is not a code error for the reviewer.
123. **The brief** is a second call in session A with a structured answer (brief_markdown, video_type,
    suggested_tones). Tokens are measured as words x 1.3 against config hooks.brief_tokens (2000 to 3000); the
    stage composes a header (idea, keyword, deliverable, identity, video type, tones, where hook 1 comes from)
    that counts toward the total; up to hooks.brief_tries (3) asks, then written with a flag. The brief is written
    before the judge runs, so it is hook-agnostic: the script takes hook 1 from judge.json.
124. **A session key with no stored id is seeded at once** (session.sh session_call --seed-if-new): when state.json
    holds no sessions.A (the earlier stages ran in another process, the run was built from frozen fixtures as the
    test does, state.json was rebuilt), the first call is already the seeded one (facts.md, expansion.md, the gate
    verdict, then the task), with an INFO line, instead of talking to a blank session. S5 uses it; the reseed
    after a lost session (item 96) is unchanged.
125. **The regeneration is a call into S5, not a reopen.** When the judge's hookscore filter leaves fewer than
    judge.min_survivors hooks, 06-judge runs `05-hooks/run.sh <run_dir> --regenerate feedback.json` once (marker
    06-judge/regenerated.json, so a rerun never regenerates twice): S5 resumes session A with the survivors and
    the failures (score, dealbreakers, weakest check), asks for min_hooks - survivors + 4 replacements (capped by
    max_hooks), merges the survivors with the valid new hooks (the previous file kept as
    hooks-before-regenerate.json) and does not rewrite the brief. reopen.txt would have made S6 end its attempt
    and S5 run again as a stage; the spec wants the judge to continue in the same pass with the best available.
126. **Profile drafts are flags:** S5 records once per run that voice.md or account.md is still a draft (a [FILL IN]
    in its body; the intro paragraph that explains the placeholders does not count) and that a missing voice.md
    means default voice assumptions. The research stages keep their own flag for a missing account.md (item 102);
    the account.md draft carries the working assumption those stages used, so their prompts lose nothing.
127. **New hook shapes** the model notices while writing the hooks (an opening it wanted and no template offered)
    go to library/hooks.suggested.txt through the wrapper (suggested_shapes in the answer, optional, cleaned,
    deduplicated, with a dated comment line), never to hooks.txt; the user moves them by hand (spec 2.2).

### S6 Hook judge
128. **Three independent judge calls** (no --session): two rankings with different seeded shuffles (idea id plus
    ":1" and ":2") so the second ranking never sees the first, which is what cancels position bias, then the
    pairwise call. "Fresh session C" is read as fresh sessions: a resumed session would carry the first ranking
    into the second.
129. **Borda and pairwise, precisely:** a hook at position p of n earns n - 1 - p points per ranking, ties by the
    first ranking's order; the top judge.top_n (4) are labeled W, X, Y, Z and compared in both orders (12
    comparisons in one call); the winner has the most pairwise wins, ties by Borda points, then by hookscore; the
    runner-up is the next one. A ranking with missing or unknown labels is read leniently (unknown ignored, missing
    appended in label order, a WARN line); a comparison whose winner is not one of its two labels is ignored
    (a WARN line when not every comparison was answered). judge.py decides all of this; the model only ranks and
    compares.
130. **The hookscore filter:** a score under judge.min_hookscore (50) or any dealbreaker is out; fewer than
    judge.min_survivors (4) triggers the one regeneration; after it the judge continues with the survivors when at
    least 2 passed, else with the top 4 by score (dealbreaker-free first), the spec's "best available"; fewer than
    2 hooks at all blocks the idea. hookscore.py runs through `python -I -X utf8` on a temp file with one spoken
    line per line and the scores are mapped back by order (hookscore skips empty lines; a count mismatch falls
    back to matching by text).
131. **judge.json keeps the whole trail:** winner and runner_up (the full hook plus hookscore, Borda points and
    pairwise wins), reasons (the pairwise reasons the winner earned, the ranking notes on both, the counts),
    filtered_out with the filter's reason, hookscore per hook, candidates and how they were chosen, both rankings
    (the order shown, the ranking, the notes, complete or not), borda, top, pairwise, pairwise_wins, regenerated,
    calls and checked. The stats update comes after the file is written, so a crash never counts a pick without
    its verdict.

### Profile (pipeline/bin/build-voice-profile, pipeline/lib/voiceprofile.py)
132. **No memo yet, so voice.md is the vendor template with placeholders and account.md a placeholder draft.**
    voice.md keeps the template's headings and fields with `[FILL IN: hint]` after each (the vendor's intro
    replaced by ours, wrapped hints joined, the template's double-brace "your number" mention reworded so no file
    of ours holds a double-brace placeholder); account.md carries the spec's sections plus the working assumption
    the research stages used so far (a generic developer-tools audience), so their prompts keep a useful text while
    the user fills it in. HUMAN_TODO added. With a memo (library/voice/memo.wav, .m4a, .mp3, .ogg, .flac, .webm)
    the script transcribes it, the script model (opus) drafts both files from the transcript on the template (keep
    the user's English, fix only real errors, [FILL IN] for what the memo did not say) and the code appends the
    excerpts and the pace. The script is re-runnable and never overwrites an existing file without --force.
133. **The pace and the excerpts are measured anyway, from the user's real speech:** library/voice/reference_long.wav
    (66.6 s) transcribed with faster-whisper (small, CPU, int8, 23 s) gives 195 words per minute (216 words in
    66.4 s, no pause over 1.5 s) and 5 verbatim excerpts, written into voice.md; config voice.wpm was set to 195
    because at least 30 s of speech were measured. The spec's "measured words per minute" normally comes from the
    memo; the long reference is the same voice at reel energy, so the number is real, and HUMAN_TODO says how to
    override it if the read was faster than the user's reel delivery.
134. **The whisper interpreter is the one in library/voice/engine.txt; no .venv-tts is created.** That interpreter
    (C:/Users/there/venvs/chatterbox/Scripts/python.exe, Python 3.11) already has faster-whisper 1.2.1 and the
    small model cached, and spec M7 says to install nothing when engine.txt exists. build-voice-profile tries
    config paths.venv_python, then engine.txt's `python` line, then `python`, and uses the first that imports
    faster_whisper. The model: config tts.whisper_model (small.en) from the local cache, else "small" from the cache
    (what tools/voice.py uses), else a download of the configured one; never a surprise download when something
    is cached. PLAN.md's pipeline/bin/setup-venv (the whisper-only .venv-tts) is therefore not built in M5; M7
    decides whether it is needed at all. Correction to item 6 and CLAUDE.md: transcription runs under engine.txt's
    interpreter, .venv-tts is a fallback location when it exists.
135. **The pace measure:** words divided by the span from the first word to the last, minus the part of every
    pause over 1.5 s, per minute (the raw rate is kept next to it); the excerpts are whole whisper segments of 10
    to 45 words, 3 to 5 of them spread over the recording, verbatim. At runtime voice.md's Pace line wins over
    config voice.wpm (hooks.py wpm), and build-voice-profile also writes the measured value into config voice.wpm
    (a regex edit that keeps the file's layout), so beats.py (M6) and the hooks agree.

### Tests, fixtures and earlier milestones
136. **test-m5.sh:** sections 1 and 2 with the fake claude (the units; S5 and S6 through run.sh from the frozen M4
    outputs, with the run built by state.py new plus stage-start and stage-done per frozen stage, so the runner
    resumes it at S5; the regeneration path with a hooks fixture of which only 3 of 12 pass hookscore and a
    replacement fixture of 10), section 3 the real indexer over the real hooks.txt, section 4 the real S5 and S6
    (M5_FREEZE=1 adds 05-hooks and 06-judge to the frozen fixtures). pipeline/tests/fixtures/fake/m5 and
    m5-regen hold the model-shaped answers; the brief is kept as markdown (brief.md) and turned into the JSON
    answer at test time, the index answer is generated from the sandbox's hooks.txt ids. The fixture hooks have 7
    spoken words or fewer, so they pass at any measured pace.
137. **Earlier milestones touched by M5:** session.sh (--seed-if-new, M4); test-m4.sh section 2 removes the
    sandbox's account.md before its run, because M5 drafted the file and that section asserts the flag for a
    missing one (M4); config.json (hooks, judge, the new timeouts, voice.wpm 195; M1); the dummies and schemas of
    05-hooks and 06-judge (M2); pipeline/vendor/.gitkeep removed (M1). One real haiku call was wasted by a quoting
    bug in index-hooks found in the first real run (the hooks list rendered empty, the whole index came back
    unclassified); the test now asserts that the prompt lists every id and that nothing stays unclassified.
138. **Windows and bash notes found in M5:** a `python -` script fed by a heredoc cannot also read a pipe (the
    heredoc is its stdin), so a generator that needs both takes a file; `\"` inside a single-quoted `python -c`
    string reaches Python as a backslash and is a syntax error, so such strings are built by concatenation and the
    data travels as an argument; `python -I` ignores PYTHONUTF8 (it implies -E), hence `-X utf8` next to it; the
    Bash tool's command limit bit again when a 12 KB heredoc was pasted (the command was cut and nothing ran), so
    long appends go through a file written with the Write tool.

## M6 (2026-11-01)

### S7 Script: who decides what
139. **The model writes, cuts, maps and picks; pipeline/lib/script_checks.py decides and composes.** Like the M4
    and M5 stages (item 95): model.schema.json, cut.schema.json, claims.schema.json, pick.schema.json and
    rewrite-line.schema.json hold the model answers (types, enums and required lists only); schema.json is the
    stage's file. Every text from a model is cleaned (errors.undash, CR, curly quotes to straight) when it is read,
    so no file of the run holds an em dash, and the rules of spec S7 (the structure, the two tracks, the length,
    the hard and soft failures, the rounds) live in Python with unit tests (test-m6 section 1).
140. **The vendored scripts are imported as modules, not run as subprocesses.** beats.py's analyse, words,
    CONCRETE_RE and STOPWORDS, humanize.py's humanize and detect.py's run are called as they are (BUILD_SPEC.md
    section 10: wrap them, do not change them), which gives their results as data in one process instead of a
    dozen interpreter starts per draft; pipeline/bin/vendor-run stays for the command-line uses (hookscore in S6,
    caption.py in M12). Found while wiring humanize.py: its comma cleanup turns `rgba(0,0,0,.1)` into
    `rgba(0,0,0.1)`, so script_checks.humanize_text swaps code-like tokens (a digit followed by a comma, a dot or
    a parenthesis inside the token, or an @, / or # in it) for placeholders before the call and puts them back
    after, the way humanize.py itself protects URLs. The vendor's behavior is untouched; an exact value survives.
141. **Per-beat timing counts the longer of the two tracks.** The voice reads the spoken track, so "one million one
    hundred thirty-four thousand one hundred twelve" costs nine words there while the display shows 1,134,112; a
    beat's seconds are max(display words, spoken words) / (wpm / 60), and the script's total is the larger of the
    two track totals. beats.py's own analyse runs on the display track for the record (its notes are kept in the
    report) because its concreteness regex needs digits and capitalized names; the hook cap (3 s), the beat cap
    (4 s), the abstract run (3 beats with nothing concrete, by beats.py's CONCRETE_RE) and the loop (a non-stopword
    of the hook in the last line, by beats.py's STOPWORDS) are computed per beat in script_checks.py so a message
    can name the beat id; beats.py would have split a long beat at sentence ends and mis-numbered it. The
    prompt tells the writer that a number written out or a command spelled out costs its spoken words.
142. **Rounds: caps.script_rounds (3) counts the first write as round 1.** Spec S7's activity text "writing script
    (draft 2/2, round 1/3)" names the first writing as round 1, so rounds 2 and 3 are the rewrites ("up to 3
    rewrite rounds" read as 3 rounds in all). Round 1 writes both drafts, cuts each, humanizes and checks each
    (the local checks and the claims check); the pick comes after round 1, as the spec orders (checks, pick, loop);
    from round 2 only the picked draft is rewritten in session D with the failing checks as feedback, then
    checked again (no second cut: the rewrite prompt gives the final word budget and says no cut pass follows).
    A rewrite keeps the round-1 cut statistics of the draft it descends from (draft --previous), so script.json
    always shows the cut. If the picked draft still fails a hard check after the last round and the other draft
    passed every hard check in round 1, the other draft is used with a NEEDS REVIEW flag instead of a block; a
    block comes only when neither draft can pass.
143. **Hard and soft failures.** Hard (a block after the rounds): facts (an unsupported or overstated claim),
    placeholders ({{...}}, [FILL IN ...], [INSERT ...], TBD, lorem ipsum, XX), a missing requirement (no stake
    right after the hook, the share identity not named in the stake, the keyword missing from the ask or not the
    expansion's keyword, the hook line changed), a second ask (follow, like, share, save, link in bio, subscribe,
    notifications, tag, DM, or a second "comment"), the structure (no hook first, no ask last, too few body beats,
    an unknown beat type), and the length more than script.length_tolerance_pct (15) outside the range. Soft (a
    NEEDS REVIEW flag per check after the rounds, one FLAG line each): detect.py (overall under 70 or a check
    under 55), the beats timing (the hook over 3 s, a beat over 4 s, 3 abstract beats in a row, no loop), the
    stake over script.stake_max_s (5 s, the spec's seconds 2 to 7 after a hook of up to 3 s) or under 1 s, the
    length within the tolerance, a card over 6 words or empty, a missing payoff, and a cut pass that did not land.
    Spec S7 names facts, placeholders and a missing requirement as hard and detect and timing within 15 percent
    as soft; the rest is placed by the same logic (what a viewer would notice as wrong versus what a reviewer
    would polish). Rewrite rounds are triggered by any failure, hard or soft.

### The writing, the cut and the pick
144. **The writer overshoots by script.overshoot_pct (25) so the cut pass has something to cut.** From the
    length range (25 to 40 s, or the list range) and the pace: final words = range x wpm / 60 (81 to 130 at 195
    wpm), the write target = the range's middle x 1.25 (132) with a window of 8 percent either side (121 to 143).
    The cut model gets the listing, the word counts, the target (80 percent of the draft, never under the final
    minimum) and the tokens that must survive (every token with a digit, an @, a / or a #, a dotted name, plus the
    keyword); cut-apply accepts 10 to 30 percent removed (script.cut_range_pct; 5 to 10 percent when the floor
    stopped it), every beat kept in order, no empty track, no lost token; a miss is asked again once
    (script.cut_tries 2) in the cut call's own session, and cut-best keeps the attempt that kept every token and
    came closest to 20 percent, else the uncut draft with cut.ok false (a soft flag). The hook beat is never cut.
145. **Tones: the brief's suggestions first, then the hook's family.** choose_tones takes the first two valid
    tones of the brief header's "Suggested tones:" line (S5 writes it); with fewer than two, FAMILY_TONE maps hook
    1's family (mistake-warning: warning, myth-contrarian: contrarian, story-confession: confession,
    tools-listicle: insider, how-to-system: calm expert, transformation: insider) and the default order insider,
    calm expert, warning, contrarian, confession fills the rest. Each tone has a one-line guide in the prompt;
    confession asks for real first-person material and is only chosen when the brief suggests it or the hook is
    a story. Draft A and draft B get the two tones in that order.
146. **Session D holds both drafts and the rewrites.** Draft A opens the session with the self-contained prompt
    (the idea, hook 1 and hook 2, the brief, facts.md, voice.md with its excerpts, pronunciations.txt, the beat
    map, the rules); draft B resumes it with a short prompt (prompt-second.md: the other tone, "a different
    script, not a paraphrase"), so the second draft is written knowing the first; a rewrite resumes it with the
    failing checks and the current draft (prompt-rewrite.md). When the stored session is gone (ai() returns 3),
    d_call forgets it and sends the self-contained prompt instead (prompt.md with an EXTRA section: the second
    draft's note, or the rewrite's feedback and current draft), so nothing depends on the transcript. The cut
    (models.cut) and the claims check (models.checks) run in fresh sessions; a cut retry resumes the cut call's
    own session so "your previous answer" means something; the pick (models.judge) is fresh. Happy path: 7 calls.
147. **The hook beat is the judge's.** Whatever the model wrote for beat 1, the draft normalizer sets its display
    to hook 1's spoken line and its card to hook 1's on-screen line (judge.json winner); only its spoken track is
    the model's (numbers in words, pronunciations). Hook 2's tracks go into script.json for the alternate clip
    (display and card from judge.json's runner-up, the spoken track asked from the model in the same answer, with
    the normalizer's fallback over the judge's line), so S8 and S10 read one file.
148. **The spoken track is normalized by code after the model.** pronunciations.txt (`word = how to say it`,
    longest first, whole words, case-insensitive) is applied, then every number is written out: thousands with
    commas, decimals ("nine point one seven"), version strings, percentages, money ("four dollars ninety-nine"),
    ordinals, clock times, units (s, ms, min, h, px, fps, k, KB, MB, GB), "1080x1920" as "by", dashed ranges as
    "to", signed numbers, four-digit years 1900 to 2099 as years ("twenty twenty-six"), leading zeros digit by
    digit ("oh one"), hex colors letter by letter and digit by digit ("D nine seven seven five seven"). The model
    is told the same rules and does most of it; the normalizer catches leftovers and records every change
    (spoken_changes). Digits left in a spoken line are information, not a failure: the display may legitimately
    carry a value the voice names instead ("Anthropic's own terracotta" over #D97757), as the brief advised.
149. **The claims check is a fresh checks-model call with a narrow definition of a claim.** The prompt gives
    facts.md whole, the framing that needs no source (the viewer's problem, the share identity, the solution line,
    hook 1, the ask, opinions and transitions) and the beats on both tracks; it answers one entry per factual
    statement with supported (a verified claim says it in the same strength), overstated (facts.md backs a
    weaker version) or unsupported (nothing, or only an unverified claim, backs it). Unsupported and overstated
    are hard failures named by beat; the model's verdict is not used, only the statuses.
150. **The pick is one judge call in a seeded order.** pick-data shuffles the two drafts with the idea id as the
    seed (so no systematic position bias across reels), shows each as its display track with the beat types,
    its tone and a one-line summary of its checks (information, not the verdict), the voice excerpts and the
    profile, and asks the spec's question ("would he say this out loud to a friend?"). An answer that names no
    draft takes the first one, with a WARN line. S6's two-orders scheme was not repeated: two drafts are one
    comparison, and the loop fixes checks after the pick.

### Inputs and checks
151. **The length rule comes from tweaks.md's Length line when it is in force.** tweaks_length reads the first
    "Length" bullet without the word PROPOSED, takes the "N to Ms" pair of the sentence that mentions list or
    explainer as the list range and the other pair as the default (today 45 to 75 s and 25 to 40 s, the same as
    config lengths, which is the fallback); the video type is the brief header's "Video type:" (S5 writes it, from
    the brief model's answer), default when absent. plan.json records length_source.
152. **The stake and the share identity.** The stake is the run of stake beats right after the hook: it must
    exist (hard), last 1 to script.stake_max_s seconds (soft), and name the identity: at least two of the
    identity's content words (expansion.json share_identity minus stopwords and words under 3 letters) must
    appear in the stake beats (hard: the share line is one of the three requirements). The problem requirement is
    the stake's presence; the keyword requirement is the expansion's keyword in the ask beat.
153. **One ask, and the loop.** The ask beat (last, type ask) must say "comment" with the keyword; any beat with a
    call-to-action pattern (follow, link in bio, save this, share this, subscribe, like this video, double tap,
    notifications, tag someone, DM me) or a second "comment" is a second ask (hard). The loop word is the longest
    non-stopword the hook and the ask share (beats.py's word list and stopwords); none is a soft failure and the
    ask prompt asks for it.
154. **detect.py scores the display track; humanize.py cleans every text but the hook's.** The display track
    (one beat per line) is what a reader sees and what the vendor skill scores; the spoken track differs only by
    numbers and pronunciations. humanize.py runs on display, spoken, card and hook 2's spoken line of every beat
    except the hook beat's display and card (the judge's lines, already through hookscore), the changes are
    counted and listed, the structural tells it reports are kept in the report as information, and check --write
    stores the humanized draft so the claims check and the pick see the final text. The thresholds are config
    script.detect_min_overall (70) and detect_min_check (55), the vendor's PASS; a failure's feedback names the
    weak checks with a hint each (vary the sentence length, more names and numbers, the stock words, contractions
    and "you"). Found while writing the fixtures and confirmed by the first real run (burstiness 29 to 38 after
    three rounds, every sentence 8 to 12 words): detect.py's burstiness wants a variation of 0.55 across the
    sentences of more than 2 words, which a reel script with a 13-word beat cap and a fixed 8-word hook reaches
    only with a bimodal rhythm. So the prompt prescribes two beat shapes that alternate (shape A: one sentence of
    12 or 13 words; shape B: two or three sentences of 3 or 4 words; the hook the only sentence of 5 to 11 words),
    and when burstiness fails, script_checks.rhythm_advice names the beats whose sentences have the middle length
    and the beats of the same shape in a row, so the rewrite prompt says exactly what to reshape. The fixture
    script with that rhythm scores 75 on burstiness and 85 overall.
155. **Cards and emphasis.** A card is 1 to script.card_max_words (6) words (counted as tokens with a letter or a
    digit, like the hooks' on-screen cap); more or none is a soft failure, and schema.json's pattern rejects a
    card of 7 or more whitespace tokens so a bad file never counts as done. Emphasis words that are not in the
    display line are dropped at parse time, at most 3 kept.

### Session, files, helpers
156. **S8's one-line rewrite is `run.sh <run_dir> --rewrite-line <beat> [--reason ...]`** (prompt-rewrite-line.md,
    rewrite-line.schema.json): the script model, in session D when it still exists, rewrites the beat's spoken
    track in simpler, easier-to-say words (shorter or equal, no hex code read out, no slash or at-sign), the
    normalizer applies pronunciations and numbers again, the display is updated where a word changed, and the
    change is appended to script.json "rewrites" (beat, reason, before, after). Exit 0 rewritten, 4 when two
    answers were unusable (script.json untouched), 1 on a code error; the activity text is "rewriting line b9".
    The caller is M7's S8 ladder (BUILD_SPEC.md S8: "rewrite that line once through S7 in simpler words").
157. **script.json keeps the whole trail:** both drafts (tone, file, cut), the pick (order, winner, reason), the
    final checks report (hard, soft, info, detail per check with detect's five scores, the claims list, the
    stake measure, the loop word, the humanize counts), rounds and rounds_log, the stage's flags, the
    pronunciations and the spoken changes per beat, estimated_seconds (the longer track) next to target_seconds
    (the range's middle), hook and hook2. The runner validates it against schema.json (beats of at least 4, ids
    b<n>, the type enum, non-empty tracks, the card pattern, the tone enum, rounds at least 1).
158. **The fake claude serves fixtures by task.** A prompt whose header has "# Task: <name>" under "# Stage:" is
    answered from <dir>/<key>.<task>.<n>.json (n counted per stage and task) or <key>.<task>.json before the
    stage-level files; M4 and M5 prompts have no task line and behave as before. stage.sh write_retry_prompt
    takes an optional sixth argument, the task, for the same header. S7's prompts carry write, cut, claims,
    pick, rewrite and rewrite-line. Fixtures: pipeline/tests/fixtures/scripts/{good, placeholder, two-asks,
    abstract-run, long-beat}.json (model-shaped answers at their final length; the good one passes every check,
    each bad one fails exactly its check), pipeline/tests/fixtures/fake/m6 (the two pre-cut drafts, their cuts,
    the claims answer, the pick, the one-line rewrite), m6-rewrite (an overstated claim in round 1, fixed by the
    rewrite), m6-block (an unsupported claim nobody fixes), m6-soft (a 6 s beat left after 3 rounds).
159. **Config additions:** `script` (tones, overshoot_pct, cut_pct, cut_range_pct, cut_tries, detect_min_overall,
    detect_min_check, hook_max_s, beat_max_s, stake_max_s, abstract_run, length_tolerance_pct, card_max_words,
    min_body_beats) and the timeouts script_seconds 1800, cut_seconds 900, checks_seconds 900, pick_seconds 900.
160. **Earlier milestones touched by M6:** stage.sh write_retry_prompt's task argument (M4), the fake claude's
    task fixtures (M3), the first schema and dummy of 07-script refined (M2), config.json (M1). test-m2 section 7
    follows the first stage without a run.sh by itself (08-voiceover now). Bash note found in M6: in one `local a=$1
    b="x$a"` statement every word is expanded before any assignment, so `$a` is the outer value and, under set -u,
    an unbound variable; such a value gets its own line.

## M7 (2026-11-01)

### The voice config and the interpreters
161. **library/voice/engine.txt is the only source of voice settings, and kokoro af_bella the only engine and
    voice.** pipeline/lib/voiceover.py `engine` reads the file (`key = value`, comments, CRLF) and fills every
    missing line from the block of BUILD_SPEC.md 2.5 (engine kokoro, python C:/Users/there/venvs/kokoro/Scripts/
    python.exe, voice af_bella, lang a, speed 1.0, silence_threshold_db -40, min_pause_s 0.3, keep_pause_s 0.1,
    breath_after_hook_s 1.0). A missing file means the whole block (the spec's "otherwise" case) and a warning at
    preflight and in the stage log. A file that names another engine (today's file still says `engine = turbo`
    with the chatterbox venv, written before the spec moved to Kokoro) is treated the same way: this pipeline
    never runs chatterbox, turbo or qwen, so the kokoro defaults apply, the preflight prints the exact sentence to
    rewrite, and a HUMAN_TODO asks for the rewrite. Neither case stops the runner (the spec's build rule: use the
    default, keep going, ask in HUMAN_TODO); a missing or broken interpreter does (the next item). The default
    interpreter path lives in config paths.kokoro_python (where setup-venv --kokoro would install it), because it
    is an install location, not a voice setting. REELS_ENGINE_FILE overrides the file's path in tests.
162. **The preflight check `voice`** (config preflight.require, pipeline/lib/preflight.sh) runs `voiceover.py
    engine-check`: the effective interpreter exists and imports kokoro (a real `python -c "import kokoro"`, about
    10 s because it imports torch) and one interpreter imports faster_whisper. A failure is a systemic stop with
    the problem named ("C:/nowhere/python.exe does not exist", "... cannot import kokoro (ModuleNotFoundError)")
    and the fix from config.json; the notes of item 161 are warnings. With REELS_TTS_WORKER or
    REELS_WHISPER_WORKER set (the fakes) the import checks are skipped and announced.
163. **Transcription runs in the first interpreter that imports faster_whisper**, tried in this order: env
    REELS_WHISPER_PYTHON, config tts.whisper_python, the voice interpreter, config paths.venv_python (.venv-tts),
    `python`. config tts.whisper_python is set to the user's chatterbox venv (C:/Users/there/venvs/chatterbox/
    Scripts/python.exe, Python 3.11, faster-whisper 1.2.1, the "small" model cached), the interpreter M5 already
    used; the kokoro venv has no faster-whisper and spec M7 says to install nothing when engine.txt exists.
    `bash pipeline/bin/setup-venv` builds .venv-tts (uv, Python 3.11, faster-whisper only) when no interpreter
    has it, and `--kokoro` builds the default kokoro venv when engine.txt is missing and that interpreter does
    not exist; `--check` only reports. Neither install branch ran in this build (nothing was missing): they are
    straightforward uv commands but untested, which the report says.
164. **config tts shrank to the stage's own knobs:** device cpu, whisper_model "small" (what is cached; the
    worker tries the configured name from the cache, then "small" from the cache, then a download), whisper_python,
    whisper_pad_s 0.5, wer_fail_pct 3, wer_flag_max_pct 8, overrun_pct 15, overrun_min_s 0.4, lead_s 0.05, tail_s
    0.2. The chatterbox, turbo and qwen settings, gap_ms and voice.reference are gone (spec M7); the timeouts
    tts_seconds 1800, align_seconds 1800 and loudness_seconds 300 were added. The runner banner shows the engine
    and voice from engine.txt ("voice: kokoro af_bella"), no fallback.

### The stage
165. **Python orchestrates, bash relays.** pipeline/stages/08-voiceover/run.sh is thin: it runs `voiceover.py run`
    and turns its relay lines into runner actions ("@@ACTIVITY" to set_activity, also echoed as "activity: ..."
    into stage.log, "@@SAY TAG" to say, "@@FLAG" to flag_once, "@@ERROR" to the stage_fail message), then maps
    the exit code (0 done, 20 block with the reason from voiceover.json, else a code error). The ladder with its
    per-line loops and batches is far easier in Python than in bash; the engine and the transcriber are
    separate worker scripts (pipeline/lib/tts/kokoro_worker.py, whisper_worker.py) because they run in other
    interpreters (Python 3.11 venvs) than the stage (3.13). A worker gets a job JSON, prints progress lines
    (LINE i/n, TIGHTEN i/n, FILE i/n) that become the heartbeat's activity, and writes a result JSON; its stderr
    (torch warnings) goes to stage.log with a prefix. A worker is killed after the config timeout
    (tts_seconds, align_seconds) and that is a code error, like a non-zero exit.
166. **Generation, per line, exactly as tools/voice.py does it:** the text is split into sentences
    (voice.sentences), each sentence is one Engine.say call, the sentences are joined with min_pause_s + 0.05 s of
    silence so every sentence boundary is a pause the tightener catches, then voice.tighten runs on the line
    with lead 0 and tail 0 (pauses of min_pause_s or longer below silence_threshold_db cut to keep_pause_s,
    shorter pauses kept, the edges removed). The stage inserts the exact silences when it joins the lines: 0.05
    s lead, keep_pause_s between beats, breath_after_hook_s after the hook beat (the first beat, type hook), 0.2
    s tail, all from the 24 kHz 16-bit line files (numpy and the wave module, no soundfile on 3.13). Every
    attempt's line file is kept under 08-voiceover/lines/ (b9.a2.wav is the second attempt of b9).
167. **Pronunciations:** pronunciations.txt entries are applied to the spoken track as whole words in any case
    (the same rule as S7's), a value between slashes becoming Kokoro's inline phonemes `[word](/phonemes/)`
    (checked in the probe: `[Claude](/klɔd/)` is read as klɔd). S7's apply_pronunciations got the same slash
    rule and a guard against wrapping twice, so a reel's spoken track carries the markup from S7 on and S8's
    second application is a no-op. The markup is stripped for every comparison and never reaches words.json.
168. **The word error rate compares what the voice was told with what faster-whisper heard, after a normalizer
    built from what the first real run showed:** lowercase, punctuation and apostrophes dropped, hyphens, slashes
    and underscores split into words ("plug-in" and "plug -in" become "plug in"), digits written out (1,134,000
    as words; a year as "twenty twenty six" when the line says it that way, else the cardinal), ordinals, "%"
    and "$", a few aliases (ok, vs, etc), British spellings mapped to American and a few homophones to one
    form (grey/gray, their/there, your/you're), inline phonemes as the word. A block where the joined letters
    are equal on both sides counts as a match (plugin / plug in, F X / FX), and a one-to-one replacement that
    differs only by a plural or possessive s counts as a match too (whisper hears "Anthropic's" as "Anthropic"
    and "card" as "cards"). Everything else is an error (substitutions, deletions, insertions, standard WER over
    the reference words). The first real run (the frozen test-idea script, 12 lines) had exactly one failing
    line before this normalizer, b3 at 16.7 percent, both "errors" being grey/gray and Anthropic's/Anthropic;
    with it every line is at 0 percent. The alignment of the comparison also gives the timestamps: each
    reference word takes the time of the whisper word it matched, a joined block splits the span by letters,
    an unheard word gets the gap between its neighbours.
169. **The ladder, in the spec's order and never a different voice:** (1) the misheard words are respelled by
    rule (auto_respell: camelCase split, an acronym of 2 to 5 capitals letter by letter, digits in words, dots,
    slashes, at-signs and dashes named or dropped: FlashFX becomes Flash F X, GPT4 becomes G P T four,
    add-idea.sh becomes add idea dot sh); a plain word has no rule and the step is skipped with a log line. The
    respelling is applied to this reel's text only (voiceover.json keeps it); pronunciations.txt is never
    edited. (2) One rewrite through `07-script/run.sh --rewrite-line <beat> --reason ...` (the script model, in
    session D when it still exists), then a regeneration; exit 4 (no usable line) is logged and the line stays;
    any other failure is a code error of S8. (3) Still over 3 percent: a NEEDS REVIEW flag at 8 percent or
    under ("voice: line b9 is misheard by faster-whisper (WER 7.1%: scope -> xx) after no respelling rule,
    rewritten by S7: ...; listen to vo.wav"), a block above it ("voice: line b9 cannot be said clearly by
    af_bella (WER 14.3%: ...) after ..."). Hook 2 stops after step 1 with a flag (it has no beat to rewrite
    and the alternate clip is secondary). Every step is one batched worker call for all the lines it touches.
170. **The per-line estimate is spread by syllables, not words.** The 15 percent overrun check compares a beat's
    tightened length with words / config voice.wpm as the spec says, but a line of long words ("distributional
    convergence") runs 20 percent over that while the reel as a whole is on pace. So the estimate of a line is
    its syllables divided by the script's own average syllables per word, at voice.wpm: the total stays words /
    wpm and the time moves to the lines that need it (a vowel-group count with a silent-e rule, good enough for
    timing). A beat over by more than overrun_pct and by more than overrun_min_s (0.4 s) is rewritten once
    through S7 ("make it shorter"), regenerated (and respelled once if the new line is misheard), then flagged
    when it still runs over. A line is rewritten at most once in a run, by whichever check comes first.
171. **Loudness is gain plus a light limiter, re-measured.** Two-pass loudnorm alone lands at -15.1 LUFS on
    Kokoro's voice: its peaks sit 16 dB above its loudness, the true-peak ceiling binds and loudnorm drops into
    dynamic mode. So voiceover.loudness_normalize applies `volume=G dB, alimiter=limit=<-1.5 dBTP minus a
    margin>:attack=3:release=100:level=0` to the 24 kHz assembly, resamples to 48 kHz mono 16-bit, measures
    again (loudnorm's print_format=json as the meter) and repeats with the corrected gain, up to 5 passes,
    until the integrated loudness is within 0.4 LU of -14 and the true peak at or under -1.5 dBTP (3 passes on
    the test idea: -14.2 LUFS, -1.6 dBTP). A result outside 1 LU or over the ceiling is a flag, not a failure.
    Hook 2 goes through the same chain on its own file.
172. **words.json comes from the per-line transcriptions, offset by the timeline,** not from a second pass over
    the whole file: the assembly is a pure concatenation of the tightened line files plus exact silences, and
    the loudness chain changes gain only, so a line's timestamps plus its start in the assembly are the
    timestamps in vo.wav (nothing is tightened after the alignment). Each entry is the spoken track's word
    (not the respelled or phoneme form), with "heard" when whisper heard something else, its beat id and start
    and end in ms; beats[] gives every beat's window in vo.wav, breath the silence after the hook, loudness the
    measured values, wpm the pace measured on this reel. Every file given to whisper is padded with 0.5 s of
    silence at both ends (a line that starts at its first sample is heard better); the pad is subtracted.
173. **Measured on this PC (the frozen test-idea script, 11 beats plus hook 2, 118 spoken words):** Kokoro
    imports and loads in about 12 s (torch), then synthesizes at 0.40x real time (66.7 s of raw voice in 26.6 s;
    a 36 s reel takes about 25 s of synthesis plus the load), tightening is instant (the 12 lines went from
    66.7 s to 41.7 s, 14 pauses shortened). faster-whisper small (int8, CPU) loads in 2 s and takes about 3 s
    per line whatever its length (36 s for the 12 lines); the whole stage runs in about 2 minutes without a
    rewrite. af_bella's pace after tightening is 176 words per minute counting the 0.1 s gaps between beats
    (180 on the speech alone), against the user's own 195: config voice.wpm is now 176 (S5's spoken cap stays
    8 words, S7's word targets drop by a tenth), and voice.md's Pace line stays the user's.
174. **S5 and S7 now time with config voice.wpm first** (the reel voice), falling back to voice.md's Pace line
    only when the config has no value; until M7 voice.md won. The M5 and M6 tests pin the sandbox's voice.wpm
    to 195 (SANDBOX_WPM in pipeline/tests/lib.sh) because their frozen fixtures and asserted numbers were made
    at that pace.

### Tests, fakes, earlier milestones
175. **The fakes mirror the workers' job contract:** pipeline/tests/fakes/kokoro_worker.py turns every word
    into a tone burst (72 percent tone, 28 percent silence, a 0.45 s pause after a sentence end, 0.25 s of
    leading and 0.5 s of trailing silence) sized from the estimate the job carries, then runs the real
    tools/voice.py tighten, so the timeline, the tightening and the loudness chain are exercised for real;
    FAKE_TTS_MODE crash and hang, FAKE_TTS_SLOW per line. pipeline/tests/fakes/whisper_worker.py "hears" the
    text the job carries with evenly spaced timestamps, unless FAKE_WHISPER_GARBLE (id:target:attempts) replaces
    a word by "xx" for the first n transcriptions of that line. REELS_TTS_WORKER, REELS_TTS_PYTHON,
    REELS_WHISPER_WORKER and REELS_WHISPER_PYTHON plug them in. The sandbox of --with-pipeline tests now copies
    tools/ (voice.py is pipeline code since M7).
176. **test-m7.sh** has three sections: units (engine.txt, WER, respelling, pronunciations, silences, the
    preflight's voice check), the fake paths through the runner (the happy path with the exact timeline, the
    ladder with a respelled acronym, a rewritten word and a slow line, the flag path at 7.1 percent, the block
    path at 14.3 percent, the crash and the hang as code errors) and the real run on the frozen script (the
    files, loudness, words.json, the silence rule, 5 spot checks, the per-line WER, the speed and pace, the
    length against the estimate). The frozen 08-voiceover fixtures are the five outputs of one run (words.json,
    words_hook2.json, voiceover.json, vo.wav, vo_hook2.wav): M7_FREEZE=1 refreshes all five; the wavs stay out of
    git (*.wav) and section 3 adds them whenever they are missing, alone when the run's words.json equals the
    frozen one and together with the JSON otherwise, so the frozen audio and timestamps always come from the same
    run, and every full run asserts that both wavs are there and as long as their words.json says (M9 and M10
    render the golden reel against them; build/M7/review-1.md fix 1). The same-run rule is not theory: the fix
    batch's real run of the same script differed from the build's by 10 ms in total (b8 ended 10 ms earlier) and
    moved 58 of 118 word timestamps by up to 260 ms (faster-whisper's word boundaries), so audio and timestamps
    from different runs never mix. pipeline/tests/fixtures/fake/m7/07-script.rewrite-line.json is a 14-word
    rewrite so one garbled word stays under 8 percent.
177. **Earlier milestones touched by M7:** config.json (M1), the banner in status.sh and its assertions in
    test-m1 and test-m2 (M2), preflight.sh's new check type (M1), S5's and S7's pace source (M5, M6),
    script_checks.apply_pronunciations' slash rule and double-wrap guard (M6), tests/lib.sh (tools/ in the
    sandbox, SANDBOX_WPM), the 08-voiceover schema, dummy and contract (M2). Windows notes found in M7: a bare
    `bash` run from a Windows Python is System32\bash.exe (the WSL launcher, "Class not registered" without
    WSL), so run.sh exports REELS_BASH (its own $BASH in C:/ form) and voiceover.py falls back to Git's usual
    paths; a Windows Python cannot open /tmp/... paths (use C:/ forms in Python, /tmp only in bash); the kokoro
    venv's python needs PYTHONUTF8=1 to print phoneme strings (the workers' environment sets it).
