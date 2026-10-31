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
