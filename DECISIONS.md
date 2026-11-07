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
2026-11-01: every reel also gets exports/N/project/, an editable Shorts Editor project (S15, milestone M14). The MP4 export is unchanged. A stable copy of the editor (moved only to reviewed versions, served on port 5310) decides what is native through its capabilities.json; anything else is baked (sprite, overlay, plate) and logged in logs/editor-gaps.md. Editor repo: C:\Users\there\OneDrive\Desktop\editor (/c/Users/there/OneDrive/Desktop/editor).
2026-11-07: reels must carry energy (BUILD_SPEC.md section 5, Motion and energy rules E0 to E9): every element lives through a 0.3 to 0.6 s main animation, 2 to 4 s of inertia and a hold that never stops; main animations combine a zoom with a 3D parallax rotation on a power3 or power4 in-out curve; captions run one word at a time in normal talk and become the graphic (at least 3 fonts, stacked sizes, asymmetric, moving as one block) on important beats and beats without a clear graphic; at most 100 characters of non-caption text on screen, none below the caption size; edge fillers run behind the frame's sides; the center stays clean with 2.5D or 3D depth (HyperFrames: CSS 3D and Three.js on the hardware WebGL M9 found); energy is measured against 70% of the look references' median. Built in M14 (motion grammar, energy meter), M15 (kinetic captions, text discipline), M16 (director, components, golden reel, energy loop with an early stop).
2026-11-07: the editable project milestone of the line above is now M17 (its spec lines are marked (M17)); it runs after M16.
2026-11-07: **The channels plan (CHANNELS.md, BUILD_SPEC.md section 14), numbered M17 to M24.** It was written as M14 to M21; the motion milestones M14 to M16 came first, so it runs as M17 Control check, M18 Channels, M19 Exports and channels side by side, M20 Formats and the timeline, M21 Editable project export, M22 to M24 Life of Gabry. This corrects the line above: the editable project is now M21, not M17.
2026-11-07: **One engine with formats, platforms and channels** (14.1 to 14.7) instead of one folder per channel: copies drift apart, every fix would be made twice, and two copies on one CPU-only laptop and one Claude account would fight over the CPU and the usage limits without knowing about each other.
2026-11-07: **Isolation is enforced by code and tests** (14.5): the paths module (paths.sh, paths.py) refuses any path into another channel's folder, and the canary test and the real-names check prove it; a channel's run sees only the engine, its format and its own folder.
2026-11-07: **exports/ stays shared at the root**, one folder exports/<id>-N/ per video with <id>-N file names, N counted per channel in build order (section 8); the old exports/N/ are renamed in M19.
2026-11-07: **The YouTube Shorts text** (section 8): the caption (the title field) at most 150 characters (the default kept), a description of at most 1000 characters with a list and exactly 4 hashtags, different every video, and the pinned comment.
2026-11-07: **The editable project (S15) is built after the channels, on timeline.json** (14.8, 14.9), so one exporter serves every channel; the channels plan starts with a control check (M17) that changes no behavior.
2026-11-07: **Every move goes through the manifest, the rehearsal, the verification and the undo** (14.13); build/PAUSE holds M18, so the build stops after the control check and before the first move.
2026-11-07: **Answers to CHANNELS.md Part C.** Narration: a narrator in the third person for about 90% of each video, occasional short Gabry lines (about 10%, not in every video) in the same Kokoro voice, lip sync only on his lines. References and sound pack: added by me later; M23 stops without references (no default bible), M24 without sounds. Gabry: an original cartoon, recognizable at a glance; the name is only a name. YouTube title: 150 (default). On-screen captions of Life of Gabry: jump captions, at most 3 words on screen, a long word alone, hard cuts. Section 5's Motion and energy rules do not apply to Life of Gabry: its simpler style comes only from its own references and style bible.
2026-11-07: **Build models from M14's restart on**: build batches on Opus 5.5 at xhigh effort, fix batches (only after a review found problems) at max, no Fable (build-runner.sh defaults).

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

## M8 Sound effects memory map (2026-11-01)

178. **The sfx map is built by pipeline/bin/build-sfx-map over pipeline/lib/sfx/** (common.py, measure.py,
    classify.py, overrides.py, pools.py, previews.py, writemap.py and sfxmap.py as the CLI). The same split as
    M7: Python does the work in four steps (plan, measure, classify-plan, build), bash relays their lines and
    makes the one indexer call through ai() between classify-plan and build (the call's files under
    logs/build-sfx-map/calls/). Exit 0 up to date or rebuilt, 1 when the model call failed (a code error for the
    stage that called it), 2 when the pack folder is missing or a step failed.
179. **Measurements with ffmpeg plus numpy, no other package:** ffprobe for codec, channels, rate and depth;
    ffmpeg decodes the first audio stream (cover art skipped) to 48 kHz float32 in memory; numpy computes the
    sample peak, the full-scale runs, the 5 ms RMS envelope (onset = the first frame within 30 dB of the loudest
    frame and 10 dB over the quietest 5 percent of frames, peak time = the loudest frame, attack, the tail to
    40 dB under, the end, the effective duration, the silence padding under -60 dBFS) and the spectral centroid;
    one more ffmpeg pass with ebur128 and 2 s of silence padding gives the integrated LUFS and the true peak
    (sounds shorter than the 400 ms gating block measure too; silence falls under the gate). The 106 files take 8
    to 12 s with 4 threads.
180. **The noise floor is measured where there is no sound:** the median 20 ms frame level of the lead-in before
    the onset (at least two frames) plus the last 50 ms when the sound ended 100 ms or more before the end of the
    file; unknown (null) when the sound fills the file, so a long fade or a trimmed tone never counts as noise.
    The first version used the 5th percentile of all frames and excluded two clean synthetic tones with linear
    fades; that number is kept as floor_p5_db for information only.
181. **Whoosh speed thresholds, tuned on the pack (spec 2.6 item 2):** fast when the effective sound is 0.35 s or
    shorter, or 0.6 s or shorter with an attack of 0.08 s or shorter; slow when it is 0.8 s or longer with an
    attack of 0.2 s or longer (a gradual swell), or 1.5 s or longer whatever the attack; medium otherwise. On this
    pack the fast ones measure 0.10 to 0.35 s with attacks of 0.02 to 0.12 s, the slow ones have attacks of 0.2 to
    0.8 s or run 1.5 s and longer (the SlowMo 05 and jet whooshes: a short attack and a 2.5 to 3 s tail); counts
    fast 17, medium 12, slow 29 (excluded files included). config sfx.build.whoosh holds the numbers.
182. **Quality filter thresholds (spec 2.6 item 5):** clipped = 10 or more runs of 3 consecutive samples at or
    over 0.985 of full scale (the four files with 19 to 46 runs go; 1 to 9 runs are noted, not excluded, so the
    hot mp3 masters with true peaks up to +2.9 dBTP stay); high noise floor = the floor within 30 dB of the peak
    on files of 0.5 s or longer (only the 16 s rewind); far too long = more than 5 s of effective sound (typing
    excepted) or more than twice a cue type's upper window; silent = peak under -60 dBFS; decode errors. A pinned
    file overrides every reason but a decode error. 13 of 106 files are excluded, each with its reason in
    SFX-MAP.md.
183. **Rules before the model (spec 2.6 item 3).** The file name's words (digits split from letters, camelCase
    split; the folder only as a hint for the model) map to nine categories: whoosh (whoosh, woosh, swoosh, swoos,
    swish, whip, wind, air, blow), click (click, mouse), pop, typing (typing, keyboard, writing), success (ding,
    chime, bell), notification (notification, message, discord, ping), negative (error, erro, buzz, scratch),
    impact (boom, thud, hit, impact, slam, punch, kick, bass), tick (tick, counter, count). Each category gives
    ranked cue type candidates with a category fit: whoosh by speed (fast: transition_fast 1.0 and attention 1.0;
    medium: transition_fast 0.6, transition_slow 0.6, attention 0.5; slow: transition_slow 1.0), any whoosh with
    0.5 s or more of sound and an attack of 0.2 s or less also hook_hit 0.5, a whip crack also stamp 0.5; click:
    ui_click 1.0, number 0.7, hero_enter 0.5; pop: hero_enter 1.0, ui_click 0.5, number 0.4; success: success 1.0,
    notification 0.5; notification: notification 1.0, success 0.4; negative 1.0; impact: stamp 1.0, hook_hit 0.9;
    tick: number 1.0, ui_click 0.6. classify.RULES_VERSION is part of the settings hash, so a rule change rebuilds
    the pools without a model call.
184. **Unclear files go to the indexer model in one batched call:** a name no rule understands (the Ui Sound
    folder, "sound-1", page flips, risers, the cash register) or one the measurements contradict (a 2.8 s "pop"),
    never a file a measurement already excludes. The prompt pipeline/stages/_prompts/classify-sfx.md lists folder,
    name, duration, effective sound, attack, tail, peak, LUFS, brightness (the centroid in words), channels and
    the rule guess; the answer (classify-sfx.schema.json) gives 0 to 3 cue types best first (category fit 1.0,
    0.8, 0.6), tags, a confidence and a note. Answers are cached in the map per file (kept while path, size and
    date are unchanged); an id the model skipped is asked once more in the same run, then at the next run.
    Confidence under 0.6 (config sfx.build.min_confidence) means waiting: out of every pool until the user pins
    the file. On this pack: 27 files asked in one 20 s haiku call, 12 waiting, 4 "fit nothing" (two risers, the
    drum roll, the page flip sequence), the rest placed.
185. **Fit and pools (spec 2.6 item 6):** fit = category fit x duration fit (1 inside the cue type's window, 0 at
    twice the upper bound and at zero length, linear between) x attack fit (sharp cue types hero_enter, ui_click,
    stamp, number: 1.0 under 30 ms, 0.8 under 80 ms, else 0.5; transition_slow: 1.0 from 200 ms, 0.8 from 100 ms,
    else 0.6; the rest any) x quality (minus 0.02 per full-scale run up to 0.15, minus 0.1 when the floor is
    within 45 dB of the peak) x the model's confidence (rules count 1.0). A pool keeps the files with fit 0.25 or
    more, best first, pinned files first of all, at most 8 (sfx.build.pool_size); under 3 is short (HUMAN_TODO:
    typing and negative on this pack). Windows in seconds of effective sound (sfx.build.cue_windows):
    transition_slow 0.4 to 2.5, transition_fast 0.08 to 0.8, attention 0.08 to 0.7, hero_enter 0.03 to 0.7,
    ui_click 0.01 to 0.4, stamp 0.05 to 1.0, number 0.01 to 0.35, success 0.1 to 1.8, typing 0.4 to 30, negative
    0.08 to 1.8, hook_hit 0.2 to 2.5, notification 0.15 to 2.5.
186. **Normalization and the cache (spec 2.6 item 4):** gain = -12 dBFS minus the sample peak (the true peak is
    in the map; 12 dB of headroom covers inter-sample peaks), the copy written straight from the decoded samples
    as 48 kHz 16-bit PCM with the file's channel count (1 or 2) under styles/sfx/.cache/<id>-<slug>.wav, on the
    same timeline as the original (onset and peak times apply to both; the silence padding is kept, S11 places by
    onset or peak). The originals never change; copies of removed files are pruned.
187. **Rebuild logic (spec 2.6 item 9):** the plan compares the folder hash (relative paths, sizes, dates), the
    hash of overrides.txt's effective lines and the settings hash (config sfx.build plus normalize_peak_dbfs,
    MAP_VERSION, MEASURE_VERSION, RULES_VERSION) with the map's, and checks that every cache copy and preview
    exists; all equal means nothing is done and nothing is called. A changed folder re-measures only new and
    changed files (the others keep their numbers and their model answer); an overrides or settings change redoes
    the pools, the map, the report and the previews from the cached numbers in about a second. Options: --check
    (exit 0 current, 1 rebuild needed, also while a file waits for the model), --force (measure everything
    again), --reclassify (ask the model again), --no-model (unclear files listed as "not classified yet" and
    asked at the next run with the model), --dir (another pack folder; tests).
188. **Outputs and who reads them:** styles/sfx/sfx-map.json (tracked: files[] with every measurement,
    classification, fit, model answer, exclusion, ban and pins; pools; excluded; waiting; unclassified;
    overrides; settings; counts), SFX-MAP.md (tracked), overrides.txt (created once with its header, never
    rewritten, tracked), previews/ and .cache/ (ignored). The banner's "sfx map: N files" counts files[]. The
    preflight gains a warn-level file check for the map (the runner continues and S11 flags a reel without a
    map, spec S11); a hard check would stop every sandbox test whose repo copy has no styles/sfx. S11 (M11) runs
    build-sfx-map at its start the way S5 runs index-hooks (the contract in pipeline/stages/11-sfx/CONTRACT.md);
    run.sh does not, so a runner start never calls a model.
189. **Previews (spec 2.6 item 8):** every pool's sounds from the cache copies, trimmed to the audible part (20 ms
    kept at each end) and spaced 1 s apart (sfx.build.preview_gap_s), stereo when any sound is stereo, as one
    48 kHz 16-bit WAV per cue type, with a .txt listing each sound, when it starts, its fit, gain and origin.
    Regenerated whenever missing (they are not in git), removed when a pool empties.
190. **test-m8.sh (no real model call):** section 1 builds a synthetic pack with ffmpeg lavfi in the sandbox (4
    clicks, a fast and a slow noise whoosh, a clipped sine, a silent file, a decaying ding, a low boom, a tremolo
    typing bed, two unclear tones, a text file named .mp3) with the fake claude answering from fixtures served by
    "# Stage: build-sfx-map" (the second fixture answers the id the first skipped): measurements and fields,
    classes, exclusions, the cache copies at -12 dBFS, the pools, the previews, the no-op rebuild, ban and pin
    through rebuilds, an unknown override line, a new and a removed file, --check, the failed call and
    --no-model. Section 2 checks the committed map of styles/sfx/: coverage, fields, no pool over 8, every cue
    type 3 or more or named in build/HUMAN_TODO.md, previews, and a rebuild with the fake claude in error mode
    that must make no call and leave the map as it is. The real indexer ran once in the build; its answers live
    in the committed map.
191. **Earlier milestones touched by M8:** config.json (M1: sfx.build and the preflight entry), the banner
    assertions in test-m1 and test-m2 (M2: the repo's map exists now, so `sfx map: N files` is accepted beside
    `not built`), pipeline/stages/11-sfx/CONTRACT.md (M2: the map's contract for M11).

## M9 Motion library (2026-11-01)

### tokens.json
192. **tokens.json is derived by script, not by a model.** PLAN.md M9 planned the structured tables by script and the
    rest by the checks model; pipeline/lib/tokens.py reads everything with explicit rules (one regex per field, over
    the markdown with its wrapped lines joined) and `verify` proves that every number and hex in tokens.json appears
    in style.md or tweaks.md (exempt: the source hashes, the date, the font metrics measured from the font files, the
    builder's version numbers). A deterministic parser keeps the tokens identical run after run and the test free of
    model calls; when the user rewords a line, the build fails naming the field and the pattern (exit 2) instead of
    guessing. The schema is pipeline/lib/tokens.schema.json (PLAN.md put it under styles/, which is the user's folder;
    only tokens.json goes there). build-tokens also writes motion-lib/assets/tokens.css, the same values as CSS
    custom properties that every component links.
193. **The in-force lines of tweaks.md win, PROPOSED lines are ignored, and an accepted proposal changes the tokens by
    itself:** tokens.py knows the six proposals by their bold titles (Caption position, Right side captions, Hook
    header, Length, Accent-filled cards, 3D) and reads each one's numbers only when its line no longer starts with
    PROPOSED (tokens.json `in_force`). Today captions sit at y 1480 with the safe-zone exception (the Caption box line
    in force); removing the word PROPOSED from the Caption position bullet moves them to y 1332 and drops the
    exception at the next build (test-m9 section 1 proves it).
194. **The 15 open questions of style.md, decided with the rule of item 32** (5 of 7 motion refs; else what both look
    refs agree on; else v02), written in tokens.json `open_questions`:
    1 caption cap center y 1480 (tweaks.md in force; the proposal would make it 1332); 2 caption line at most 620 px
    wide, x 230 to 850 (tweaks.md Right side); 3 scene change B, an animated exit (fade with blur over 4 frames, or a
    fall or a push) then the next scene enters (both look refs; the motion refs split 3, 3, 1); 4 end-card keyword
    typed, 2 frames per letter (both look refs); 5 kicker top y 253 (v02); 6 kicker cap 21 px (v02); 7 dot spacing
    43.5 px (v02: 54 px is in v01, v03, v07 and v08, four videos, under the 5 of 7); 8 lower-right glow warm #F0D9C7
    (v02); 9 no doodles (v02); 10 hero cards straight, only fans, stacks and the end card tilt (v02); 11 headline word
    by word, 3 frames per word, plain fade (both look refs); 12 caption words a plain fade over 4 frames (both look
    refs); 13 honesty labels kept as a small light chip (item 33); 14 no second color (v02); 15 true peak -1.5 dBTP
    (BUILD_SPEC.md S8 and S11). HUMAN_TODO asks the user to accept or change them.
195. **Where the style gives a range, the tokens keep the range and the components use one value from it:** the chip
    pop overshoot 2 percent of "1 to 3", the badge overshoot 16 percent and the tile 13 of "13 to 16", the mascot
    delay 4 frames of "4 to 7", the end-card stagger 6 of "5 to 6", the caption box rise 9 px of "9 to 12", the chunk
    fade-out 2 frames of "2 to 3", the count-up 27.5 frames (the median). frame-match accepts the range where the
    style states one.
196. **The script's beat types are mapped to the library's components by judgment** (tokens.py BEAT_TYPES, tokens.json
    `beat_map`), because style.md's beat map names beats by content (proof / number, the tool, how it works, data,
    options) and script.json by function (hook, stake, number, tool, step, comparison, proof, mechanism,
    before-after, pain-payoff, payoff, ask). `any` lists what every beat may use (the canvas, the captions, the mascot,
    the moves). S9's validator (M10) reads this map; the catalog's beat_types are its inverse.

### The library
197. **Every component is a HyperFrames scene file mounted as a sub-composition** (motion-lib/compositions/<id>.html:
    the variables declared on the file's `<html data-composition-variables>`, everything else inside `<template>`,
    the root `<div id="root" data-composition-id="<id>">`, a paused GSAP timeline registered inline). Two findings
    from the runtime (hyperframe.runtime.iife.js) shape the files: the declared defaults are read from the file's
    document element, so the declaration must sit on `<html>`, not on the root div; and the per-mount
    `getVariables()` and `__timelines` registry exist only inside the inline scene script (a scoped window), so the
    shared library assets/paper-cards.js takes the raw variables as an argument and never registers a timeline. One
    file can be mounted many times with different `data-variable-values`; the runtime maps the registered key to
    the host. An apostrophe inside the single-quoted declaration cuts the attribute short (found with "card's title");
    catalog.py refuses one.
198. **Flat layering, not nested scenes.** Every component is a full-frame 1080x1920 transparent layer that places its
    element with x, y and w props; a reel's index.html mounts the paper canvas once, then one host per component
    instance with absolute data-start and data-duration, z-index for the stacking, the caption line once over the
    body beats, and the voice as `<audio id="vo">`. Scenes are a grouping in the plan (data-scene on the hosts).
    HyperFrames reads one level of nesting for its timeline tools and forbids transforms on a host (.clip) from the
    root timeline, so a scene's exit cannot be animated from outside: every component takes `exit` (fade-blur, fall,
    push, cut) and `exit_at` props instead, and the plan's transitions become those props on the leaving scene's
    components (golden.py apply_transitions).
199. **The shared code:** assets/paper-cards.css (the fonts as @font-face over the OFL files in assets/fonts, the card,
    chips, pills, badges, type classes, the caption boxes, the logo rules) and assets/paper-cards.js (PC: the moves
    enter, pop, flyIn, exit, countUp, typeInto, strike, the mascot's pixel art, the honesty chip, a seeded PRNG, the
    event registry). Fonts: Inter Tight (grotesk, 800), Instrument Serif Italic (the headline phrase and the stat
    unit), Space Grotesk (kicker, chrome), JetBrains Mono (code), Caveat (handwritten), downloaded once from the
    google/fonts repository with their OFL texts. GSAP 3.15.0 and Three.js r159 (three.min.js, the last UMD build)
    are vendored under assets/vendor from the pinned npm packages (package.json; `bash pipeline/bin/setup-node`
    refreshes them). The linked stylesheets are not scoped per composition (only `<style>` blocks are), so
    tokens.css's `:root` variables reach every mount; a scene root may only be styled by `#root` (lint
    subcomposition_root_styled_by_class), so each file styles its own root.
200. **The 27 components:** the 24 items of vocabulary.md (card 1, stat-number 2, end-card 3, mascot 4, dark-chip 5,
    light-chip 6, caption-line 7, pop 8, check-badge 9, window-card 10, terminal-card 11, chart-card 12, thumb-grid
    13, logo-tile 14, strike-through 15, fly-in 16, chat-card 17, progress-bar 18, camera-move 19, headline 20,
    exit-move 21, handwritten-callout 22, speech-bubble 23, table-card 24), plus paper-canvas (the background,
    data-no-timeline), dm-card (the CTA's DM notification card of tweaks.md Branding: a surface card with the round
    avatar-dark.png at 112 px or more, the sender and one message line) and hero-3d (Three.js through the hf-seek
    protocol). The move items (1, 8, 16, 21) exist both as shared PC functions used by every component and as their
    own demo compositions, so frame-match can measure each move alone and the gallery can show it.
201. **Logos are image files with their aspect ratio locked:** every logo spot (logo-tile's image and second_image,
    end-card's lockup, dm-card's avatar, headline's kicker_mark, table-card's logos_json) takes a path and renders an
    `<img>` with object-fit contain inside a box whose size the component sets; nothing redraws, recolors or
    stretches it; the tile around a logo keeps the style's shadow, the image gets none. The plan writes paths as
    brand/<path under library/brand> (checked against brand.json) or research/<file>; golden.py copies them under the
    project's assets/ and rewrites the props. The DM avatar sits in a 120 px circle (its bolt 586 of 1024 px tall
    keeps over 64 px), the lockup defaults to 360 px wide (300 minimum).
202. **The hook breath and the first frame:** the headline shows the accent mark (the brand slot) at frame 0 so frame 0
    is never empty paper, the kicker words fade in one by one from 0.05 s, the headline words land on their spoken
    times (words_json from words.json) and the set piece (hero-3d or another hero) starts 60 ms before the breath so
    its landing sits inside it.
203. **Captions as one component for the whole body:** caption-line takes every chunk with its words' times (chunks_json,
    local seconds) and lays each chunk out at its final width, so a word appears in its own place when spoken; the
    chunk ends a frame before the next chunk's first word whatever the plan says; a chunk wider than 620 px is scaled
    down and reported (caption_overflow event) rather than overflowing the zone. The chunker
    pipeline/lib/motion/captions.py (1 to 4 words, a break at a sentence end, a clause end after two words, a pause
    of 150 ms or more, the word limit; emphasis words from script.json, at most 3 per chunk) made the golden's chunks
    and is 9b's baseline.
204. **Sound events are declared per component in catalog.json** (META in pipeline/lib/motion/catalog.py: event name,
    frame offset from the component's start or a formula over its props, duration where it has one, the cue type it
    takes in S11 or null for a visual change with no sound of its own) and registered at runtime by the moves
    (window.__pcEvents with local seconds; the harness reads them). M10's events.py computes the absolute times from
    the plan and the catalog.
205. **The hf-seek clock is the root's time.** Inside a mounted scene the Three.js listener receives the root time, not
    the clip's local time, so hero-3d takes a clip_start prop (its data-start) and golden.py sets it; without it a
    3D clip mounted later in the reel would show its end state at its start.

### frame-match (DECISIONS.md 29, made precise)
206. **Measured in a Playwright harness, not through HyperFrames' render.** pipeline/lib/motion/harness.py builds a
    standalone page per component (the file's own template content, GSAP, a shim for window.__timelines and
    getVariables, the paper canvas behind) and seeks the GSAP timeline frame by frame while dispatching hf-seek the
    way the runtime does, reading opacity, position, size, scale and text of the tracked elements every frame. The
    DOM numbers are exact where PNG analysis would guess; the real runtime is exercised by `npx hyperframes check`,
    the snapshots and the golden render. One Chromium per run (hardware ANGLE, from motion-lib/webgl.json).
207. **Durations are measured by fitting, not by a threshold:** an expo-out tween is within a pixel long before it ends,
    so the matcher fits the element's curve against the move's ease (expo.out, power3.out, power2.out; ease-in for
    exits) over durations around the expected one and takes the best; the fit's residual must stay within 10 percent
    of the distance. Opacity frames are the first frame at 0.99 or more; a pop's frames end at the first frame back at
    scale 1 within 0.0002 (GSAP lands exactly), a count-up's at the first frame showing the final text, typing by the
    frames per character between the first change and the last. Tolerances: 1 frame, 10 percent, the style's ranges
    where it states one (expectations.py).
208. **The reference correlation compares shapes.** The 30 fps strips (styles/paper-cards/analysis/<vXX>/extra/s30_*.png,
    cells of equal size in rows of 8 under a 16 px label band) show other things moving too, so strips.py measures
    the change curve inside the region that changes most at the peak frame, finds the move window by walking back
    from the peak while the change stays over a fifth of it, resamples both windows to 12 points and takes the
    Pearson correlation; a component passes with r of 0.5 or more on its best strip (none assigned: the numbers alone
    decide). On this PC the 25 components with a strip correlate at 0.57 to 0.99 (frame-match.md); the strips are
    not in git, so on another machine the numbers alone decide.
209. **Pass and fail:** a component passes when every check passes, the best strip correlates and its page logs no
    error; `--apply` moves a failing file to motion-lib/candidates/ (a passing candidate comes back) and writes the
    result into catalog.json. All 27 pass today, so candidates/ holds only .gitkeep; the catalog check and the
    gallery regenerate the showreel index.html from catalog.json so a move never leaves a dangling mount.

### Gallery, WebGL, golden
210. **The gallery is static HTML** (motion-lib/gallery/index.html, built by pipeline/bin/gallery): one 540x960 still
    per component (taken in the harness at a telling moment, tracked in git for the visual director), what it does,
    its props, sound events, beat types and frame-match result, and a Play button that loads gallery/play/<id>.html,
    the harness page plus a looping clock (eyes only; renders never use it). The showreel motion-lib/index.html is
    generated from the catalog's demo props (every component once, in a row over the canvas) and is what
    `npx hyperframes check` and `snapshot` run on.
211. **WebGL on this PC: both paths work.** pipeline/bin/webgl-test (motion/webgl.py) found hardware ANGLE through D3D11
    on the AMD Radeon integrated GPU (WebGL 2) and SwiftShader (Vulkan, software) both drawing the hero-3d canvas
    in the harness, and HyperFrames rendering the 3D composition with `--browser-gpu` and with `--no-browser-gpu`.
    motion-lib/webgl.json records harness_gpu hardware and render_flag --browser-gpu; frame-match and the gallery
    read the first, S10 (M10) the second. `check` and `snapshot` run in the system Chrome, but `render` captures
    with chrome-headless-shell, which HyperFrames downloads into ~/.cache/hyperframes on its first run (about 150 MB,
    slow on this connection); a render killed during that download leaves .chrome.install.lock behind and every
    later render waits on it, so setup-node runs `browser ensure` itself and clears a stale lock first. Should neither work on another machine, webgl is false there and the
    component shows its 2D card (data-webgl=0) for S10 to flag NEEDS REVIEW.
212. **The golden reel is compiled from a plan, not hand-coded** (pipeline/lib/motion/golden.py): the merged plan of
    pipeline/stages/09-plan/schema.json (scenes with component instances and props, captions, cards, labels,
    transitions, branding) becomes the project golden/test-idea/project/ (the library's compositions and assets
    copied in, one host per instance, the captions once, the voice), checked with `npx hyperframes check --json`,
    rendered with the frozen vo.wav, probed with ffprobe (1080x1920, 30 fps, the voice's length within 0.2 s, an audio
    stream) and summarized in contact-sheet.png (one still per scene plus the breath) and README.md. The plan itself
    is written by goldenplan.py from the frozen script.json and words.json with a hand-made design per beat (DESIGN:
    the component, its props, the spoken word it lands on), so the design is by hand and the timings follow the
    voice. S10 can start from the same compiler. The project's fonts, vendor files and voice copy are ignored by git
    (copies of motion-lib and the fixture); golden.mp4 and the per-run reports too.
213. **The golden's branding follows tweaks.md:** the solution is external (the frontend-design plugin) with no logo
    asset, so the hook's kicker mark is the neutral accent dot and no FlashFX asset appears before the CTA; the CTA
    scene mounts the end card with lockup-gradient-on-light.png (300 px, under the mascot row at y 1170) and the DM
    card with avatar-dark.png landing on the word TELLS at y 1305, kept inside x 110 to 850 so no text enters the
    right rail of the lower half; golden.py's plan check enforces the CTA's avatar and lockup and rejects a brand/
    asset outside the CTA unless the plan says the solution is FlashFX.
214. **Earlier milestones touched by M9:** .gitignore (M0: the harness, render and golden copies), config.json (M1: a
    warn-level preflight entry for styles/paper-cards/tokens.json, hard from M10 on when the visual stages need it,
    so no sandbox test of M2 or M3 stops on a missing file), package.json created at the root with the pins
    (hyperframes 0.8.226, gsap 3.15.0, three 0.159.0; `bash pipeline/bin/setup-node` installs them, refreshes the
    vendored copies, checks Chrome and ffmpeg through `hyperframes doctor` and installs the HyperFrames skill pack
    for the M10 builder sessions).

## M10 Visual stages (2026-11-01)

### The three passes of S9
215. **The model designs, the code composes and decides** (the pattern of M4 to M7). The visual director answers each
    pass with a structured object (pipeline/stages/09?-*/model.schema.json): 9a one scene per beat with the
    components, their props and where each one starts (`at`: scene, breath, word:<spoken word>, ms:<offset>;
    `word_props` for timing props such as strike_at or ticks_at that land on a word); 9b the caption word groups, the
    card texts it changes and the labels; 9c a transition type per scene pair. pipeline/lib/visual/plan9.py resolves
    every time from words.json (so every start is a word boundary by construction), fills the defaults (the headline's
    words_json from the beat's words, hero-3d starting visual.breath_set_piece_lead_ms 60 ms before the breath so its
    landing sits inside it), applies the branding, derives the cards and labels, gives the transitions the style's
    durations and validates. The model never writes a millisecond, an instance id or a brand path.
216. **One retry with the exact problems in the same session, then the review path.** pipeline/lib/visual.sh
    visual_pass_run (the shared body of the three stages) calls the director, composes, and on problems resumes the
    session with write_retry_prompt's list; a second failure is stage_fail (a code error for BUILD_SPEC.md 4.2, as S9
    says: "An invalid pass gets one retry with the validator errors, then the review path"). The rejected
    composition stays in plan.candidate.json for the reviewer.
217. **The validator is 19 named rules** (pipeline/lib/visual/plan_validate.py: schema, components, times,
    first_change, breath, max_gap, distinct, repeat, beat_map, three_d, set_pieces, zones, captions, cards, assets,
    honesty, branding, transitions, hook2), every threshold read from tokens.json, catalog.json, brand.json or config
    visual.* (min_distinct_components 5, max_same_in_a_row 2, title_max_words 6, body_max_words 14,
    snap_tolerance_ms 34, zone_tolerance_px 24, max_cut_share 0.34), reported as `rule=<name>: <message>` lines so a
    test can assert the rule and the director's retry prompt can quote it; warnings never fail. 9a checks the scene
    rules, 9b the caption, card and honesty rules, 9c and S10 everything. The fixtures of PLAN.md M10 are
    pipeline/tests/fixtures/plans/good.json (the golden plan) and bad-<rule>.json written by make-bad.py, one per rule.
218. **Zones at plan level are approximate footprints** (visual/common.py footprint: a box per component instance and
    its text boxes, from the props and the style's font metrics); the exact pixel checks are S12's (M11). A hero
    ending under tokens.json zones.hero.bottom_max is a warning, under zones.safe_bottom an error (the CTA's DM card
    excepted: M9 placed it at y 1305 inside the caption band's exception); text reaching the right rail of the lower
    half is estimated from the text boxes with visual.zone_tolerance_px.
219. **Caption chunks never wider than the line.** The style caps the centered caption line at 620 px (tokens.json
    zones.caption.max_width); at the caption size (Inter Tight 800, 67 px, measured with PIL from the library's own
    font file: visual.common.text_width) most 4-word chunks are wider (the golden's chunker had 16 of 33 over the
    limit and the caption-line scaled them down, the gap M9 noted). motion/captions.chunk_words now breaks by width
    (max_width, width_fn), goldenplan.py uses it (the golden has 42 chunks), the 9b prompt tells the director the
    limit in characters, and compose_text splits an overwide chunk the director sends instead of rejecting it (the
    rule is mechanical; a note says so). The emphasis cap is tokens.json limits.caption.emphasis_per_chunk.
220. **The branding is applied by code** (plan9.apply_branding, BUILD_SPEC.md S9 Branding, tweaks.md): the ask scene
    always gets the end-card with brand.json's default lockup for light surfaces (lockup_w at least
    tokens.json branding.lockup_min_width) and the dm-card with branding.cta's avatar (mark/avatar-dark.png) and
    sender, both added with a note when the director left them out (the DM card landing on the keyword's word); the
    brand slot token "@brand-slot" in a prop resolves to the FlashFX bolt (solution flashfx: brand.json defaults.mark),
    the tool's logo (solution.json logo, else a research asset whose name or description says logo or icon) or ""
    (the component's neutral icon); a brand/ asset outside the CTA is removed for a non-FlashFX solution and noted. A
    run without 02-expansion/solution.json counts as not FlashFX (S2 writes it from M12 on). The surface under each
    logo spot is fixed per component and prop (visual.common LOGO_SURFACES: light everywhere but a dark window card)
    and the validator requires the asset's use_on to match it or be both.
221. **The beat map gained window-card for comparison and before-after beats** (pipeline/lib/tokens.py BEAT_TYPES,
    tokens.json rebuilt with --force, catalog.json rewritten): the golden's comparison beat shows the SKILL.md
    screenshot in a window card, which the M9 map forbade; a comparison or a before-and-after often is a real
    screenshot. The push transition lasts push_out_frames plus push_gap_frames (8 frames, 267 ms: the 6-frame push
    and the 2 empty frames of v03) rather than the golden's 200 ms; the golden plan was aligned and re-rendered.
222. **The prompts inline digests, not raw files** (plan9.run_digest into <stage>/digest/): timeline.md (every beat's
    window, display and card text, emphasis and the words with their start ms, the breath, hook 2's words),
    catalog.md (every approved component: what it does, its beats, props with types, defaults, options and IMAGE
    marks, its sound events and still), golden.md (the example reel scene by scene), assets.md (the screenshots with
    what they show), solution.md (the solution and the branding it implies, with the exact paths), scenes.md (the 9a
    instances with their text props, for 9b), chunks.md (the baseline chunks, for 9b), transitions.md (the scene list
    with the style's rules, for 9c); style.md, tweaks.md and tokens.json are inlined whole. The director has Read and
    Glob (config visual.director_tools) so it can look at the stills, the contact sheet and the screenshots. A 9a
    prompt is about 70 KB.
223. **Hook 2's headline is the director's** (9a's answer field hook2: the kicker and the display line split in 1 to 3
    lines, the serif phrase between asterisks; the hook2 rule requires its words to be the display line's). S10 builds
    the alternate clip from the hook scene's components (project.hook2_plan): the headline with hook 2's lines and
    words_hook2.json's times, every other component keeping its distance from the last spoken word, the clip
    min(visual.hook2_max_s 3.5 s, last word plus visual.hook2_hold_ms 800 ms): 3.19 s on the test idea.
224. **Structured output takes free-form objects:** the 9a schema's `props` is an open object; a probe call with the
    haiku model through `--json-schema` returned the nested answer intact, so the design did not need flattened props.

### S10
225. **The project is compiled by code, the builder model is the repair step.** motion/golden.py build_project (M9's
    plan-to-project compiler, now with an optional voice, a folder name, a meta id and a title) turns the merged plan
    into 10-build/project/ in a second; the builder model (config builder, or builder_escalation when the plan has
    visual.three_d_heavy_objects 3D objects or more or state.json rounds.review is 2 or more, M11's counter) is called
    only when `npx hyperframes check --json` reports errors, with Read, Glob, Grep, Edit, Write and `npx hyperframes`
    in the project folder as its working directory (so it cannot touch the library, the pipeline or the user's
    folders), up to visual.build_fix_rounds (2) rounds, then a code error. On the test idea the check passes at once
    and no builder call is made. Candidates (motion-lib/candidates/) are not written by S10 in this version: the
    catalog requires a META entry in pipeline/lib/motion/catalog.py for every component file, so a model-written
    candidate would break the library's checks and the gallery; the director's wishlist (a component it wanted and
    the library lacks) becomes a NEEDS REVIEW flag and the reel uses library components (HUMAN_TODO).
226. **events.json is read from the runtime, not computed from the catalog's formulas** (DECISIONS.md 204 planned the
    formulas). The components register what they do and when on their mount (paper-cards.js PC.event into
    window.__pcEvents, local seconds); pipeline/lib/visual/events.py mounts every instance of the built project with
    its resolved props in the Playwright harness (motion/harness.py, the project folder as its library so the
    screenshots and logos load; hero-3d with clip_start 0 because the harness seeks local times) and reads the
    events; absolute ms = the host's data-start plus the local time. Every event that starts a visible change is
    verified: a seek one frame before and one frame after must change the element's state (opacity by more than
    0.01, since a cubic ease-in moves 0.016 in its first of 4 frames; position by 0.5 px; scale, rotation or text; a
    canvas by its pixels, hero-3d draws from the hf-seek time; typing also at 2 frames after, because the first
    letter appears on the second frame at 2 frames per character; a landing, a peak or an end of a move is the
    moment a change stops and is not verified). PC.exit registers an exit under its move's name (the extra `type` key
    of PC.event wins), so fade-blur, fall, push and cut events are normalized to "exit" with transition_type kept.
    The scene changes come from the plan's transitions, at the next scene's start with transition_ms and the type
    (verified when the leaving components' exits were). `npx hyperframes timeline --json` cross-checks that every
    host starts where the plan says. On the test idea 108 events, 10 scene changes, 69 of 69 verified.
227. **The draft is rendered at the composition's size and scaled down** (project.render_scaled): the HyperFrames CLI
    accepts resolution presets only, so `render --quality draft` produces 1080x1920 and ffmpeg scales to 540x960
    (lanczos, libx264 veryfast, crf visual.draft_crf 20, yuv420p, -an); the full-size file is deleted. The project has
    no audio element (the spec's silent draft; S13 adds the mix), and S10 checks the probe: 540x960, 30 fps, no audio
    stream, the plan's length within 0.2 s. On this PC the 41 s reel renders in about 60 s, the hook 2 clip in 20 s.
228. **WebGL follows motion-lib/webgl.json:** render_flag (--browser-gpu here) goes to every render; webgl false
    turns every hero-3d instance into a popping card with its label (project.replace_3d) and flags NEEDS REVIEW.
229. **The preflight gained the brand kit and the visual files** (config preflight.require, pipeline/lib/preflight.sh):
    a new check type `brand` (library/brand/brand.json under the repo parses, lists assets, every file exists with
    use_on, width and height), styles/paper-cards/tokens.json now hard (M9 kept it a warning), motion-lib/catalog.json
    and node_modules/hyperframes/package.json hard. The test sandboxes copy those four into every --with-pipeline
    sandbox (pipeline/tests/lib.sh), so the M2 to M7 tests still pass their preflight; --with-visual (M10's test)
    adds the library's compositions, assets and stills, the brand kit, the golden plan and contact sheet, and points
    REELS_NODE_PREFIX at the real repo's node_modules (golden.npx_cmd and events.timeline_check read it).
230. **The stage scripts relay the Python's lines like S8** (10-build/run.sh: @@ACTIVITY, @@SAY, @@FLAG, @@ERROR), and
    the three pass stages print `activity: <text>` into their logs beside set_activity, so the tests can assert the
    spec's activities ("planning animations", "validating plan", "planning text", "planning transitions", "building
    visuals", "rendering draft").
231. **The merged plan lives in two places:** 09c-transitions/merged.json (what 9c validated) and 10-build/plan.json
    (the plan as compiled, with the transitions as exit props and any 3D replacement). S10 merges the three pass
    files itself (plan_merge.merge_run), so a pass re-run by the review loop (M11) is picked up without 9c running
    again; 9c writes merged.json for inspection. The pass schemas (09a/09b/09c schema.json) are generated from
    pipeline/stages/09-plan/schema.json by pass-schemas.py so the parts stay one definition (the test checks they are
    current).
232. **Earlier milestones touched by M10:** motion/golden.py (build_project's optional voice, folder, meta id, title,
    the npx prefix), motion/captions.py (the width limit), motion/goldenplan.py (the width-aware chunks, push 267 ms),
    pipeline/lib/tokens.py BEAT_TYPES and the rebuilt tokens.json, tokens.css and catalog.json, motion/harness.py
    (the measured element's tag), motion-lib/compositions/headline.html (ids on the word spans, so the word events
    can be verified), golden/test-idea (plan and render regenerated, M9), the dummies, schemas and contracts of
    09a-animations, 09b-text, 09c-transitions and 10-build (M2), config.json (M1: visual, timeouts plan_seconds,
    build_seconds, check_seconds, events_seconds, render_draft_seconds, the preflight entries), pipeline/lib/preflight.sh
    (M1), pipeline/tests/lib.sh (M1). No stage of M4 to M8 changed.
233. **Windows and bash notes found in M10:** a heredoc fed to `python -` inside `$( ... )` must not also redirect
    stdin from /dev/null (the first brand check did, and Python printed its banner as the "error"); a `/tmp/...` path
    typed inside a Python heredoc is C:/tmp for Windows Python while the same path as a command-line argument is
    converted by Git Bash, so scratch paths go through `cygpath -m` and in as arguments; a Bash tool command that
    chains two quoted heredocs can fail to parse, so the longer patches went into a script file (build/M10/patch-events.py).

## M11 Sound effects pass and review loop (2026-11-01)

### S11, the sound pass
234. **Code only, in three layers (pipeline/lib/sfx/ behind pipeline/bin/mix-sfx and 11-sfx/run.sh):** assign.py turns
    10-build/events.json into cue candidates with the spec's rules and accepts them by priority (mandatory, scene
    changes, hero and number, ui, attention) and time, so the density trimming keeps the spec's order; pick.py rotates
    inside the map's pools; place.py sets where each file starts and how much of it plays; level.py sets the gains;
    render_stem.py mixes in numpy; verify.py measures the rendered stem; mixsfx.py orchestrates, corrects and writes
    cues.json, sound-map.txt, the stem, the mix and draft_mixed.mp4. The stage script relays "@@" lines like S8 and S10
    and refreshes the memory map first (bash pipeline/bin/build-sfx-map, a no-op when nothing changed; its indexer
    call failing is a code error; REELS_SFX_NO_BUILD=1 skips it in tests).
235. **Two readings of "sounds" in the density rule, recorded here because the spec's 4 per 10 s would otherwise drop
    every signature sound of this reel:** a typing bed is a continuous sound, not a hit: it respects the 250 ms
    spacing against other onsets but does not count toward the 4 hits per 10 s; and a series of the same mandatory cue
    on one component within sfx.series_gap_ms (2 s: a checklist's ticks 667 ms apart) counts once and plays one file
    (the first member's). Without these the three checklist ticks ate the window and the terminal's typing bed and
    two scene changes were dropped. A hero that enters on the scene change itself would always lose to the whoosh
    (the spacing rule), so its pop moves to its landing (the card's land event); on the test idea the transitions and
    the mandatory cues still fill the budget and no hero pop survives: 17 sounds from 40 candidates (9 mandatory, 8
    transitions), 23 dropped with their reasons in cues.json.
236. **Calm beats for the slow whoosh:** config sfx.calm_beats = stake and pain-payoff (the spec's "stake, pain, story";
    the pipeline has no story beat type). A cut (0 ms) is still a scene change and gets a fast whoosh.
237. **Placement from the map's own measurements:** a whoosh (transition_slow, transition_fast, attention, hook_hit) is
    placed so the map's peak_s lands on the event, everything else so onset_s lands on it; both were measured on the
    cache copy's timeline (DECISIONS.md 186), so no file is re-analyzed at pick time. A file whose anchor comes later
    than the event allows starts inside the file (offset_ms). A sound plays to its audible end (end_s plus 60 ms), a
    typing bed to its segment's end (a shorter file plays once, never looped), and a tail that would run into the next
    sound is cut sfx.tail_guard_ms (50) before that sound's audible start, with a 30 ms fade; the guard gives the next
    onset a clean lead-in (the first version cut at the onset itself and the previous file's jangling tail was
    measured as the onset).
238. **The 8 dB rule against a local reference with a floor:** the voice's sample peak within sfx.voice_window_ms (600)
    of the event, never taken lower than the reel's overall voice peak minus sfx.voice_floor_under_peak_db (12). The
    floor keeps the hook_hit (it lands in the breath, a second of silence) and any sound in a pause from being pushed
    into inaudibility; with it every sound still sits at least 8 dB under the loudest voice frame near it. The gain is
    computed from the played segment's own peak (a typing bed cut from the middle of a file peaks lower than the file).
    Mono stem and mix: one voice, one channel, the phone speaker the reels play on; a stereo file is averaged.
239. **Verification on what was rendered, with definitions that survive real files:** the stem's 5 ms RMS envelope (the
    map's own measure). A whoosh is in sync when the event falls inside the loudest stretch of its span (the frames
    within 1 dB of the maximum): the jet whooshes have a plateau of 200 ms and the loudest frame moved by a grid
    alignment, which made the first version oscillate by plus and minus 212 ms between passes. A non-whoosh's onset is
    the first frame of its window (40 ms before to 150 ms after the event) within 30 dB of the sound's expected peak, or,
    when something already sounds at the window's start (a bed, a tail), the strongest rise of 6 dB or more over the
    20 ms before it. Unplanned sound: any stretch above -55 dBFS that no planned span (plus 40 ms) covers. The
    corrections of a failed pass: a measured offset moves the file by the opposite amount, a sound over its voice cap
    loses the excess plus 0.5 dB, a true peak over the ceiling lowers every sound, a loud mix lowers the stem; the mix
    itself is touched last (volume plus alimiter with latency compensation) and only when the stem alone cannot fix the
    loudness. Every sound is measured on an envelope aligned to its own first played sample (the map measured the
    file from its first sample on the same 5 ms grid, so an untouched placement reads the frames the map read) and a
    whoosh's peak is searched only within sfx.peak_search_ms (500) of its event: the first version read the reel's grid
    over the whole span, where a grid shift and a neighbor's tail moved the loudest frame and a 2.8 s swoosh with an
    0.8 s swell was "corrected" by 112 and then 888 ms until the stage failed (the cap test's round 4). A correction
    never moves a sound by more than sfx.max_shift_ms (150); a sound that misses by more, or misses again after a shift,
    swaps to the next unused file of its pool (placed and levelled again, the others keep their corrections) and, when
    that fails too, is left out with a NEEDS REVIEW flag: a sound the renderer cannot verify is a file problem, not a
    code error for the reviewer. Up to sfx.verify_passes (5) passes, then exit 3 and the review path. On the test idea
    one correction (the cash register's soft onset measured 35 ms late) and everything within 10 ms; in the cap test's
    fifth round a typing bed that read 75 and then 140 ms late was swapped for the pool's other file and passed.
240. **Rotation and memory:** the pool order is best fit first (pinned first of all), the start offset is seeded per
    reel (the idea id; plus the review round when the edit review asked for other sounds), never the same file twice
    in a row for a cue type, the files used for the same cue in the last sfx.recent_reels (2) reels avoided while the
    pool has others (logs/sfx-usage.json keeps the last 20 reels, this run's entry replaced on a re-run). A series plays
    one file (235). The pools overlap (a ding sits in success and in notification), so a file already chosen for
    another cue type of the reel is avoided while the pool has others, the one-off cue types choosing first: the
    first real edit review caught the DM notification sharing its file with three success ticks.
241. **The hook 2 clip gets its own sounds** (S13 muxes "its own voice and sounds"): the hook 2 project's events are
    read with M10's events reader (no screen verification), the same rules apply with words_hook2.json and vo_hook2.wav,
    the outputs are cues.json's hook2 block, sfx_stem_hook2.wav and mix_hook2.wav. A hook 2 project without its
    compositions (the frozen fixtures keep only index.html) is skipped with a note, never a failed stage.
242. **The edit review's [sfx] notes change the next pass** (assign.apply_feedback): another seed always; "clutter, busy,
    too many, noisy" lowers max_per_10s by one, drops the attention whooshes and every sound by 3 dB; "loud, cover,
    mask, drown" lowers every sound by 4 dB; "quiet, barely" raises them 3 dB (the voice rule still caps); a named
    family (whoosh, click, ding, pop, typing) avoids the files of the previous pass. The applied changes are listed in
    cues.json feedback_applied. Without a reaction a deterministic S11 would re-run identically five times.
243. **Voice only when the map is missing or empty:** mix.wav is vo.wav, the stem silent, draft_mixed.mp4 still made,
    cues.json has voice_only true and a verification that passes with nothing to verify, and the run is flagged NEEDS
    REVIEW naming bash pipeline/bin/build-sfx-map (spec S11).

### S12, the review loop
244. **The mechanical checks run in M9's Playwright harness, not in Node puppeteer** (DECISIONS.md 39 planned
    puppeteer): the built composition's hosts are read from 10-build/project/index.html (so a planted fault in the
    project is caught, not what the plan says) and mounted one by one with their props, the paper canvas behind, the
    same mount S10 verified the events in; no second browser toolchain, and the per-host page gives exact DOM numbers
    at the composition's own 1080x1920 (the draft's half resolution only scales the video checks). The positions are
    canvas coordinates, so overlaps and the right rail are judged across hosts at the same time.
245. **Check times:** every beat settled (its start plus review.settle_ms 600, or its middle when shorter) and its middle,
    every emphasis hit plus 150 ms (the box has faded in), every instance's landing plus 100 ms, the built CTA (its scene's
    end minus 300 ms): 75 times on the test idea. Not the beat ends: the leaving elements are mid-fall there. Elements
    under 0.5 effective opacity are not judged; contrast only at full opacity (a word mid-fade reads as a smear).
246. **Text leaves and backgrounds from pixels:** a text leaf is an element with its own text node; its glyph box is a
    Range over its content. The background behind it is the median of the screenshot pixels around and between the
    glyphs (the box grown by 5 px, the pixels near the text's own color left out), which reads a caption word on its
    accent box, a chip's text on its fill, a kicker on the paper, with no model of the component's CSS. Overlaps skip
    an element and its own ancestor (a chip's accent word inside its text) and inset each box by a sixth of its height
    (adjacent headline lines are 113 px apart with 122 px line boxes).
247. **Contrast: 4.5:1, and review.contrast_display_min (2.7) for the style's display colors** (text in the accent family,
    or text on an accent or success fill): the look's own kicker and serif phrase on paper measure 2.8 to 3.0 (M9's
    HUMAN_TODO foresaw this; HyperFrames' own check warns at the same places). The exemption is by color, so body
    text in ink never gets it.
248. **Zones with two exceptions:** the caption line's words must sit in the caption band (x 230 to 850, within 180 px
    above and 80 px below tokens.json zones.caption.center_y), the tweaks.md exception; the CTA's DM card's texts may
    end inside the same band (DECISIONS.md 218 placed the card at y 1305). The right rail (the right 230 px of the lower
    half) takes no text and no logo. Fonts: the first family of the computed font must be one of tokens.json's five;
    sizes at or over review.min_font_px (24, the library's smallest reading text is 26 and the honesty chips carry
    data-layout-ignore); a caption word under 90 percent of the caption size means the component scaled a chunk down.
249. **Emphasis within 80 ms from the component's own events:** the caption line registers every word with its box
    (PC.event caption_word, em); each plan emphasis hit matches the nearest boxed word of the same text, the error must
    be within review.emphasis_tolerance_ms (80) and the boxed word must be visible at the check time; a hit in the hook
    or the ask (no captions there) passes with a note.
250. **Branding measured on the drawn image:** an img whose src is under assets/brand/ is a logo; brand.json gives its
    type, use_on, content box and bolt height. object-fit contain locks the aspect ratio (else the box ratio must match
    the file's within 2 percent); the drawn box inside the img box gives the lockup's width (300 or more), the bolt's
    height (64 or more), the avatar's size (112 or more); the surface under it is the median of the pixels around the
    box (light at luminance 0.5 or more) and must match use_on; its readable contrast is the better of the PNG's dark
    and bright parts (the 5th and 95th percentile luminance of its opaque pixels) against the surface, 3:1 or more (a
    black lockup on ink fails both the variant and this); clear space is a quarter of the bolt's height around the
    content box, free of other elements' text and images. The CTA must show a lockup and the DM avatar; a logo outside
    the CTA is a fault unless the solution is flashfx.
251. **The style check reuses tools/analyze_refs.py** on draft_mixed.mp4 (into 12-review/analysis/) and compares the
    hero zone's (middle band's) gap median and gap maximum with the references' range plus or minus 20 percent (the
    nine summary.json files of styles/paper-cards/analysis; tokens.json pacing when the folder is missing: it is not in
    git). The palette rule counts the 1 fps frames' non-image pixels within delta E 5 (CIE76) of the token colors plus
    the gradients the look is made of (paper to the two glows and the corner, the card shadow to paper and surface,
    white), the research screenshots and the logos masked with the boxes the mechanical pass measured at those
    seconds; 98.6 percent on the test idea against the 90 required. The accent share uses the measure of
    analysis/accent_share.txt (hue 8 to 30, saturation over 0.55, value over 0.7), logos excluded, under tokens.json
    limits.accent_share_max_pct in every frame (2.9 percent at most here). The mixed draft's loudness is measured with
    loudnorm, the true peak with review.aac_peak_tolerance_db (0.5) of room for the AAC encode.
252. **The audio check** reads S11's verification and transcribes the mixed draft's audio (ffmpeg to 16 kHz, the same
    whisper worker and interpreter resolution as S8, REELS_WHISPER_WORKER first) against the words S8 aligned
    (words.json), with the voiceover's word error rate; under review.wer_max_pct (5). 0.0 percent on the test idea with
    the real faster-whisper.
253. **The edit review is one fresh qa call per round** with Read and Glob (it reads the images): the contact sheet, the
    hook's 10 fps filmstrip and one per transition (pipeline/lib/review/filmstrip.py, 1 s of lead and 0.7 s after each
    scene change), the second full frame of each look reference plus a third of v02, the scene table with the sounds
    of each scene beside it and sound-map.txt whole, the requirements (the viewer's problem and the share line from
    expansion.json, the keyword and the ask from script.json, the solution), what the code already verified, the earlier
    rounds. Its structured answer: the eight scores, branding_natural with a note, tagged issues, a summary
    (12-review/model.schema.json). An ad-feeling branding becomes an [animation] issue.
254. **The verdict and the routing (route.py):** pass only when the three code checks pass and every score is at least
    4. Otherwise every issue (the code's and, when the scores fail, the editor's) goes to the step its tag names and the
    earliest owner reopens with every stage after it and 12-review itself through reopen.txt (state.py now lets a stage
    name itself). A [voice] issue routes only when it names a word in quotes: the voice is deterministic, so S8 can
    respell a named word (voiceover.apply_review_feedback reads 12-review/feedback.json) but cannot re-read an opinion;
    other [voice] issues become NEEDS REVIEW flags. A failing round whose issues route nowhere exports with a flag. The
    editor's issues from a passing round are kept as notes only.
255. **Rounds and models:** state.json rounds.review counts the failed rounds; "reviewing: edit review (round n/5)" and
    "fixing [tag] issues (round n plus 1, opus or fable)" follow caps.review_rounds_opus (3) and review_rounds_fable
    (2): the visual passes call models.visual_director_escalation (fable, new in config.json) once rounds.review reaches
    3, S10's builder keeps M10's rule (builder_escalation at rounds.review 2, DECISIONS.md 225). The round after the fifth
    failure exports with a NEEDS REVIEW flag carrying the scores and the open issues (the captions file shows it through
    the flags). The issue counters: a first failed round opens one issue, a later pass fixes it.
256. **What a re-run pass learns:** 12-review/feedback.json (the issues by stage, the scores, the summary, the reopen
    list); the three director prompts gained a {{REVIEW}} section (python pipeline/lib/review feedback --stage) that
    quotes the issues routed to that pass, or says the pass runs again because an earlier one changed; S11 reacts as in
    242; S8 respells quoted words. S10 learns nothing new: it compiles what the passes changed.
257. **A result cache for the unchanged parts:** the mechanical checks are keyed by index.html, plan.json and the
    project's compositions and assets (names, sizes, dates); the style check's visual parts by draft.mp4 and the image
    boxes, its loudness measured again every round (the mix changes with every sound pass). An [sfx]-only fix round
    therefore costs the sound pass, the transcription and the editor, not two minutes of identical screenshots and
    frames (12-review/cache/, --no-cache to measure again).

### Found on the way, earlier milestones touched
258. **The caption line scaled every chunk to 60 percent** (motion-lib/compositions/caption-line.html compared the chunk's
    1080 px block's scrollWidth with the 620 px limit, so every chunk hit the 0.6 floor; the golden reel and the M10
    draft show 40 px captions where 67 px were specified). S12's mechanical check found it on its first run (every
    caption word "scaled to 40 px"). The width is now a Range over the chunk's words. The frozen draft, hook 2 clip and
    contact sheet of the test idea were rendered again, and so was the golden reel (M9's test runs render-golden; its
    contact sheet, the gallery's players, still and frame-match report changed with it).
259. **Earlier milestones touched by M11:** motion-lib/compositions/caption-line.html (M9, 258), pipeline/lib/state.py
    (M2: a stage may reopen itself), pipeline/lib/visual.sh and the three director prompts (M10: {{REVIEW}}, the
    escalated director), pipeline/lib/voiceover.py (M7: apply_review_feedback), config.json (M1: sfx.*, review.*,
    timeouts sfx_seconds, mechanical_seconds, style_seconds, edit_review_seconds, models.visual_director_escalation;
    rewritten by json.dumps, so its hand alignment is gone), pipeline/tests/lib.sh (M1: --with-review), the 11-sfx dummy
    (M2: the new schema), pipeline/tests/fixtures/runs/test-idea/10-build (M10: the drafts and the contact sheet
    rendered again). The frozen project folders are rebuilt from the plans by pipeline/tests/materialize-project.py
    (the fixtures keep only index.html and instances.json), which also renders the drafts when the mp4 files are missing.
260. **Windows and tool notes found in M11:** a long `python - <<'EOF'` heredoc in a Bash tool call can fail to parse
    before anything runs (two of them did, with nothing applied), so the patches to earlier files went into
    build/M11/patch-1.py and patch-2.py; a Windows Python calling bare `bash` reaches the WSL launcher ("Class not
    registered"), so a patch script must not check bash syntax itself; ffmpeg 9's alimiter takes latency=1 so a limited
    mix does not shift in time.

## M12 Final render, caption, export, end to end (S13, S14)

### The problem-first solution (retrofitted into S1 to S4 and S7)
261. **One module owns the solution:** pipeline/lib/solution.py holds the types (flashfx, external, method), the keyword
    rule, the SOLUTION block's line, the history type, the balance of the recent exported reels, the usable lines of
    voice.md "Proof I can use" (a line with [FILL IN is not proof) and the FlashFX rules as code (a FlashFX mention, a
    "made/rendered/built in FlashFX" phrase, a short list of explicit sales phrases). S2, S3, S4, S7, S14, export.py
    and history.sh call it, so the rules cannot drift between stages.
262. **S1 solution candidates:** research's model schema requires solution_candidates (type external or method, name,
    url, why, sources). An external candidate without a URL that research verified is dropped by research.py: S2 needs
    the link for the LINK deliverable and the SOLUTION block. facts.md lists the candidates under their own heading.
263. **S2 decides, the code corrects:** the model answers solution_decision {type, name, url, reason}; expansion.py
    normalizes it (an unknown type becomes method, an external one without a URL found in facts.md becomes method
    with a note, a flashfx one gets the name FlashFX and https://flashfx.app) and sets the keyword from the type,
    whatever the model wrote: FLASH for flashfx, LINK for external (deliverable: the tool's link), the deliverable
    that fits for a method (deliverables.txt or a new one, as before). The prompt carries account.md's content
    strategy, the candidates, the proof lines and the balance of the last 10 exported reels from history.txt.
    02-expansion/solution.json {type, name, url, reason, keyword, deliverable, deliverable_link, written_by, round,
    checked} is what every later stage reads; a run without it counts as not FlashFX and its history type is "-".
264. **S3 honesty H:** the gate model scores H pass or fail with evidence and a fix hint; gate.py forces a fail when the
    solution is flashfx and "Proof I can use" has no usable line (every FlashFX claim must come from it, spec S2).
    H failing is never a drop by itself: the decision is angle (S4) like a failing P, S or C, inside caps.angle_rounds;
    only a reel still failing after the last round is dropped with "still failing after 2 angle rounds". The score
    text gained " H ok" or " H fail" (for example `P3 S2 C3 F ok H fail`), so history lines of dropped ideas carry it.
265. **S4 decides again:** when H failed, the angle prompt gets the gate's H evidence and fix and must answer a new
    solution_decision under the S2 rules; S4 rewrites solution.json (written_by 04-angle, round n) and the keyword
    that follows it. The fake fixture proves the path: a forced FlashFX solution on the web design idea fails H, S4
    picks the external skill, the gate passes on round 2 (test-m12 section 3).
266. **S7 solution rules:** the writer's prompt carries the rules for the reel's type. A FlashFX mention in a
    non-FlashFX script is a scripted hard failure (any spoken or display line, any card); ad language and "made in
    FlashFX" are judged by the checks model as part of check "solution" (hard), with the scripted phrase list as a
    floor. The S7 plan line ends with "; solution <type>".
267. **History lines:** `date | idea | solution | exported N` (and dropped, blocked), the type read from solution.json at
    the moment the line is written, "-" before S2. The dummy S2 writes an external solution, so the dummy runs of
    test-m2 and test-m3 show "external"; their assertions were updated.

### S13 Final render
268. **Video by HyperFrames, audio by ffmpeg:** HyperFrames renders 10-build/project at 1080x1920, 30 fps, without audio
    (video.mp4); ffmpeg muxes 11-sfx/mix.wav as AAC 48 kHz mono, 160 kbps, with -c:v copy. HyperFrames' own audio path
    duplicated the mono voice to two channels and measured about 3 LU louder than the mix on the golden reel, and the
    mix is the file S11 verified and S12 heard. A missing mix falls back to vo.wav with a flag.
269. **Checks and one post-pass:** ffprobe (size, rate, h264 High, yuv420p, AAC, 48 kHz, audio present, duration equal
    to vo.wav within render.duration_tolerance_s) and loudnorm (voice.loudness_lufs plus or minus 1 LU, true peak at
    most voice.true_peak_dbtp plus 0.5 dB of room for the AAC encode). A failing check gets one ffmpeg pass that fixes
    only what differs (re-encode the video for a wrong profile, pixel format, size or rate; mux again; trim; a gain
    plus alimiter pass on the mix); still failing is a code error (exit 3, the fix loop). The hook 2 clip takes the
    same path with mix_hook2.wav, must be 3.5 s or shorter with audio, and its loudness is a soft check (a flag).

### S14 Caption and export
270. **Hook 1 is the first line, not the model's:** the caption model (config models.script, no tools) writes only the
    body, the ask line, 3 to 5 hashtags and search terms; caption.py prepends hook 1 word for word (125 characters or
    fewer) and checks: one ask, "Comment KEYWORD" once, no second ask, no link, hashtags one word each and not generic,
    none in the body (a hex color like #D97757 is not a tag), body length, the solution rules of 261. humanize.py then
    cleans it and the vendor caption.py lints the whole caption: no FAIL allowed, the WARNs recorded. One retry in the
    same session with the exact problems; the second answer is written anyway with a NEEDS REVIEW flag.
271. **The export stays the runner's:** S14 writes export.json (caption, hashtags, keyword, deliverable, solution, hooks,
    needs_review from state.json flags, the cited facts with URL and date, files); pipeline/lib/export.py renders
    Ncaptions.txt from it with the new SOLUTION block (`flashfx`, `external: name link`, `method: name`), numbers,
    moves in one step, then the runner removes the idea and writes the history line with the solution type.
272. **Earlier milestones touched by M12:** research.py, expansion.py, gate.py and the S1 to S4 prompts, schemas and
    run.sh files (M4), script_checks.py and the S7 prompts, schemas and run.sh (M6), the S5 run.sh (M5: the brief's
    header names the solution), history.sh, runner.sh and export.py (M2), the 02-expansion and 14-export dummies and
    the 13 and 14 schemas (M2), config.json (render.*, caption.*, timeouts render_final_seconds, render_hook2_seconds,
    mux_seconds, caption_seconds), the fake fixtures of M4 (the decision and H fields) and the frozen test idea
    (02-expansion/solution.json, 03-gate H fields), and the assertions of test-m2, test-m3, test-m4 and test-m6 that
    read the history line, the gate's score text, the keyword or the S7 plan line (build/M12/patch-tests.py).
273. **Found while testing M12:** the hook 2 clip's mix (2.68 s, the voice) is shorter than its composition (3.19 s, the
    voice plus the tail), and `-shortest` cut the clip to the audio, so the duration check failed three times and the
    idea was blocked; the mux now pads the audio with silence (apad) so the video's length wins. The activity
    "exporting #N" of spec section 7 was set only after the export, so no line ever showed it; the runner now sets it
    before the export (the number predicted from exports/, the one export.py assigns with one runner) and the STEP line
    reads `writing caption done (12s) -> exporting #1`. test-m2's dummy run calls the real reviewer when a dummy fails:
    the 03-gate dummy lacked the new H field, and the runner's own fixer repaired it and committed
    `autofix(03-gate): ...` (b7ea7e3) with a line in known-issues.md; test-m3 now counts only the 10-build lines its
    sections add, since the sandbox copies the repo's known-issues.md.
274. **M11's style check hung in every second review round** (found by the real run of test-m12 section 4): S12 runs
    tools/analyze_refs.py into 12-review/analysis/ every round, and the analyzer's ffmpeg calls have no -y, so a still
    left from round 1 made ffmpeg wait for "Overwrite? [y/N]" on the inherited stdin until timeouts.style_seconds
    (1200 s) ran out; the runner then retried the "temporary" timeout three times, an hour lost and the review cycle
    next. pipeline/lib/review/style_check.py now removes the previous v01/ folder first and runs the analyzer with no
    stdin (tools/analyze_refs.py, the user's tool, is unchanged). M11's tests never ran a second real style check in the
    same run folder. The live test run was rescued by hand (the same fix copied into its sandbox, the stale stills
    removed, the waiting ffmpeg killed); test-m12 section 1 now runs the analyzer twice into one folder.
275. **A model at its own limit falls back to opus:** when Fable's weekly allowance runs out, the CLI answers "You've
    reached your Fable limit. Switch to another model ..." (api error 429, model_requires_usage_credits) with no reset
    time. The classifier (M3) calls that a transient rate limit (three retries, 21 minutes) and then a code error (a
    plain-text copy of the message is a code error at once), so every escalated call (builder_escalation, reviewer_escalation, visual_director_escalation from review
    round 4) would have gone to the review and fix loop and blocked the reel; and it is not a usage limit to wait out
    either (the others still answer, and the reset may be days away). ai.sh now retries such a call once with config
    models.limit_fallback (default opus, its effort kept) in the same session, with a WARN line; the build runner
    does the same for its batches. Found on 2026-11-02 while Fable was at its limit and the real M12 run was heading
    for round 4; the live run got the same ai.sh.

## M13 Hardening (2026-11-02)

276. **Fault injection lives in ai.sh** (`REELS_FAULT`, never set in normal use). `limit:<stage>[@n]` replaces the next
    call of that stage with a result shaped like the CLI's own ("You've hit your session limit · resets 3:48pm
    (Europe/Rome)", is_error, the same session id), so the real classifier, the LIMIT line, limits.log, the wait, the
    RESUME line and the retry in the same session all run unchanged; the reset is REELS_FAULT_MINUTES (default 3, at
    least 2, since the message has minutes only) ahead and REELS_FAULT_WAIT=fast fast-forwards that one wait.
    `kill:<stage>[@n]` kills the runner (its pid file) and then the stage with SIGKILL, as a crash or a closed window
    would. `@n` is the n-th run folder by creation time (the second idea of a sandbox), and each fault fires once:
    logs/.faults/<kind>-<stage>[@n] remembers it, so the restarted runner keeps the same REELS_FAULT without a second
    kill. The test injects both into the second idea at its first S2 call (the limit: S2 resumes session A, so "the
    same session continues" is visible in the call log) and its first S3 call (the kill): both come before the gate
    can drop the idea, so a dropped second idea cannot skip them.
277. **logs/runner.log rotates at 50 MB** (config logs.rotate_mb, logs.rotate_keep 3): checked when the runner starts
    and at most once a minute in runner_tick (REELS_LOG_ROTATE_BYTES and REELS_LOG_ROTATE_EVERY in tests); the file
    moves to runner.log.1 (older ones shift, the oldest goes) and the new file opens with an INFO line naming the old
    one (INFO never replaces status.txt). A stage's say lines append to whatever runner.log is at that moment, so
    nothing is lost across a rotation; logcheck.py reads runner.log.N ... runner.log.1 runner.log as one timeline.
278. **status.txt is written aside and renamed** (say in log.sh). Measured on this PC with a reader polling the file
    while 1500 lines were written: the direct `>` write let the reader see an empty file; the rename never shows
    empty or half-written content, but Git Bash's rename leaves the name missing for a moment (about 1 read in 100
    during a burst of writes), so readers try again: runner-status, the doctor and the test's sampler. A refused
    rename (another program holding the file) falls back to the direct write.
279. **pipeline/lib/logcheck.py is the judge of the status lines** (the test and the doctor use it). Every line:
    `[HH:MM] TAG  details`, a known tag padded to 6, no CR, no ANSI code, no em dash. The story, session by session
    from each banner: every idea STARTs, moves by STEP lines whose "-> next" is the next STEP's activity, has its GATE
    line before it is exported, ends with DONE, DROP or BLOCK (or, with --allow-crash, the session ends inside it and
    the next session STARTs it again "resumed at" the same stage), NEXT names the next idea and position, every LIMIT
    has its RESUME before the stage ends, the heartbeat has the idea's position and text, a minute within one of the
    idea's age, the FIXED count and an activity from the table of spec section 7 (so has every STEP; the base text
    without its parenthetical detail is allowed, as the runner announces a stage before the stage refines it), no
    idea is silent longer than the heartbeat plus 2 minutes (a hang), the exports are numbered without gaps, the last
    session ends with the summary whose counts match its own lines, no STOP. Times are minute stamps, so every time
    comparison allows one minute. The dummy gate prints no GATE line (only the real gate does); rather than change the
    dummy (test-m2, m3 and m12 assert the dummy runs' exact event sequences), the checker takes --no-gate-line.
280. **build-voice-profile --force keeps the user's parts** (spec 2.3): the existing file is passed as --keep and
    voiceprofile.py merge_keep puts back account.md's Brand and Content strategy and voice.md's How I promote word for
    word (in their place, or after the section that preceded them), any section the user added, any section filled by
    hand while the rebuild only has placeholders for it (a whole section when it has fewer placeholders than the
    rebuild's, else field by field: `- **Name:** Gabriele` replaces `- **Name:** [FILL IN]`), the measured pace line
    and the excerpts when the rebuild measured nothing, and the FlashFX spelling line in its own section after the line
    it followed. With a memo, the memo's draft wins for every field it filled. The previous file is copied to
    logs/voice-profile/<name>.before-<date>.md first, and the script names what it kept. A second --force changes
    nothing. The account.md template's placeholder "Brand mark" section became the "Brand" section of the brand kit
    (library/brand/, 2.7), the one the user's file already had.
281. **pipeline/bin/doctor is read-only and quick** (about 30 s, 5 s with --quick, which skips the voice check):
    versions (and the Node packages against package.json's pins), disk against runner.min_free_gb with the size of
    runs/, exports/ and logs/, the voice interpreters (setup-venv --check), the freshness of the sfx map, tokens.json
    and the hooks index (each tool's own check; hooks.py's own hash), the runner (alive, status.txt checked by
    logcheck.py with its age, a warning when a live runner's status is older than 12 minutes, runner.log and its
    rotated files, the last session's story with --live), and the queue and logs (ideas, history counts, blocked.txt,
    STOPPED.md, limits.log, known-issues.md). OK, WARN or FAIL per line; exit 1 only on a FAIL (a missing tool, a wrong
    package, too little disk, a broken status line, STOPPED.md).
282. **The M13 run is driven by pipeline/tests/m13-run.sh, not by test-m13.sh itself**: bash reads a script as it runs,
    so a test script edited during a run of several hours breaks (it happened to test-m12 in M12). The driver is small
    and stable; test-m13.sh section 3 can check a finished driver folder (M13_REAL_DIR). The real run is started
    detached with PowerShell's Start-Process, because the Claude Code tool stops its own background commands after 2
    hours. The test accepts any of exported, dropped or blocked per idea (spec: "every idea ends exported, dropped or
    blocked with a reason"), and requires the exports numbered from 1 without gaps.
283. **Found by the real M13 run: S8 blocked a reel for saying "Claude" right.** faster-whisper's small model does not
    know the name and writes "clod" or "clawed" for af_bella's correct "Claude" (BUILD_SPEC.md S8 compares every line's
    transcription with its text); auto_respell has no rule for a plain capitalized word, so the line went to S7's
    rewrite, and the script model respelled the name ("You're briefing Clawed Code wrong") to steer the voice; the voice
    then said "Claude", whisper heard "claude", the text said "Clawed", and the idea was blocked at WER 12.5%. Measured
    on this PC (pipeline/lib/tts workers, af_bella, small.en): respellings ("Clawd", "Klawd") change nothing, Kokoro's
    inline phonemes help in some sentences only, while faster-whisper's `hotwords` with the reel's names gives "Claude"
    in every sentence tried, from the unchanged voice. Two fixes: (1) voiceover.hotwords() collects the reel's names
    (a capital that is not just a sentence's first letter, or a sentence-initial word capitalized twice, plus the keys
    of pronunciations.txt) and S8 and S12's audio check pass them to whisper_worker.py (job "hotwords"); the hint
    biases the spelling of what the voice said, it does not create sounds, so a word the voice really garbles still
    fails. (2) S7's one-line rewrite refuses a respelling (script_checks.py respellings(): a new word with the same
    consonant skeleton as a name or long word it replaced, "Clawed" for "Claude"), and its prompt forbids it, because
    the spoken track is also what the captions show and what the voice check compares with.
284. **More found by the real M13 run, and the final pass over the status lines.** (1) S8 blocked the ffmpeg idea
    for a correct "one thirty": whisper writes "130", and the normalizer read that as "one hundred thirty";
    voiceover.py now also accepts the paired reading of a 3 or 4 digit number (pair_words: "one thirty", "eleven
    forty five") and a clock time ("1:30") when the reference says it that way, as it already did for years. (2) S8's
    activity was "fixing pronunciation" without the line when several lines were respelled at once; it now names the
    line being generated ("fixing pronunciation (line b4)", spec section 7). (3) Two activities the spec's table does
    not name are kept and allowed by logcheck.py: S12's "reviewing: audio check" (M11's third code check) and S8's
    "normalizing loudness". (4) The second idea was blocked at S7 because a claim still said more than facts.md backs
    after 3 rounds: the spec's rule for a hard failure, not a defect. Every other line of the run matched sections 6
    and 7 (the banner, START with "resumed at", STEP chains, GATE with H, LIMIT, RESUME, BLOCK, NEXT, the heartbeat
    with its counters, IDLE and the summary). The fixes went into the live sandbox of the rerun as well; the first
    run's log keeps its pre-fix line, so test-m13 section 3 is passed by a second run with every fix in.
285. **The runner's own fixer found a visual-stage bug during the M13 rerun, and the issue counters include the review.**
    In the rerun of the /init idea, 09c failed twice on a zones error ("text reaches x 938 in the lower half"): 09b
    had lengthened a card text into the right rail, and 09b's checks never ran the zones rule. The runner's review
    and fix loop (4.2) fixed it in the sandbox (autofix 97bd3f2: zones in plan_validate.py's CAPTION_RULES; 54dcb04
    after the escalation: the transitions pass runs `visual check-text` and runs 09b again first when 09b's plan fails
    09b's current checks, since the runner restarts only the failed stage), and the reel then exported. Both are ported
    to the repo unchanged (test-m10's fake sections pass). The heartbeat's "issues: f fixed, o open" (spec section 7:
    "errors and failed reviews") counts S12's review too: round 1 failing opens one issue and a later round passing
    fixes it, in state.json, read by the runner when the stage ends; logcheck.py follows the same rule, and the DONE
    line's "N issues fixed" includes a recovered review.
286. **S7's share-identity check matched exact words** (found by the second real M13 run): the stake must name the
    share identity with at least two of its words, and "Long recording. Timestamps known." failed against "if you cut
    clips from long recordings" because "recording" is not "recordings"; the third round's rewrite had changed the
    plural, so a reel whose stake clearly names the viewer was blocked as a hard failure after 3 rounds.
    script_checks.py now compares light word stems (word_stem: plural, possessive, -ing and -ed removed, a doubled
    final consonant undone), so recording, recordings and record match, as do clip, clips and clipping. The second
    real run's other blocks follow the spec: a line the voice still garbled after its one rewrite ("Heads up" heard
    as "headset", 25 percent), and the first run's facts failure.
287. **The ffmpeg rerun (build/M13/rerun3) found three more S8 false failures, all transcription spellings of words
    the voice said right**: whisper wrote the spoken "ten thirty" as "10.30" (a clock time with a dot), the spoken
    "docs" as "docks", and the spelled-out "eff eff em" as "FFM" (and, in the second run, "C L I" as "CL"). The
    comparison now also accepts, when the reference says it that way: a dotted clock time ("10.30") and a version read
    as one number after the point ("3.12" for "three point twelve"); an all-capitals acronym for the letters or the
    letter names the script spells ("CLI" for "c l i", "FFM" for "eff eff em"); and common homophones mapped to one
    form on both sides (docs and docks, cache and cash, site, sight and cite, to, too and two, for and four, and a few
    more in VARIANTS, now applied to number words too); a number followed by a comma ("10.30,") is read as a number.
    Genuine mishearings still fail ("Heads up" as "headset", "Claude" as "cloud"). Replayed on the blocked ffmpeg run
    in its sandbox (Kokoro is deterministic), S8 passed: 1 of 12 lines misheard on the first pass ("asked5", a word and
    a digit glued together), fixed by its rewrite. Not changed: whisper gluing a digit to a word; the rewrite handles it.

## M14 Motion grammar and energy meter (2026-11-07)

### The energy meter (E0)
288. **The meter is pipeline/lib/review/energy.py, run as `python pipeline/lib/review energy <video> [--plan merged.json]`.**
    ffmpeg decodes the video at 30 fps into 108x192 grayscale frames (the area filter: every source pixel counts), and
    every frame gets the mean absolute change against the previous one (0 to 255): frozen under 0.05, subtle under 0.6,
    medium under 4, big from 4. The moving share counts the medium and big frames; the middle band does the same on
    rows 64 to 127 (y 640 to 1280 at 1080x1920); the pixels changing are the mean share of pixels that change by more
    than 8; a still stretch is a run of frames below medium (frozen or subtle) lasting 1 s or more, the still share is
    the time inside such runs and the longest still is the longest run. "Still" means below medium, not frozen: with
    that reading the M13 reel (build/M13/rerun/1.mp4) measures 15.9, 15.1, 1.21, 31.9 percent and 2.8 s against the
    spec's 16, 15, 1.2, 29 and 2.8 (with "frozen" it would measure 0 percent and 0.67 s, which no reel would ever
    fail). With a plan the scenes are measured one by one on their frame ranges, with the same targets, and the
    report lists the failing scenes (M16's review routes them to 9a). The whole measurement is numpy on raw frames:
    about 1 s per 10 s of video.
289. **Calibration and targets.** `energy calibrate --refs styles/paper-cards/refs --out styles/paper-cards/analysis/energy.json`
    measures the nine references (nicknamed as analysis/index.md does) and keeps every number and the medians per
    group. The look medians on this PC: moving share 58.55 percent, middle band 65.55, pixels changing 4.66, still
    stretches 13.25 percent, longest still 1.95 s (the motion refs: 34.5, 38.1, 2.69, 29.4 and 1.7). The targets: the
    three lower bounds at 70 percent of the look median (41, 46, 3.3; the spec's 42 came from a slightly different
    measurement of the same videos), the two upper bounds at the look median rounded up to the next 5 percent and
    0.5 s (15 percent and 2 s: "70 percent of the median" cannot apply to a bound that must not be exceeded, and the
    spec's numbers are exactly the references' own level rounded up). tokens.py derives tokens.json `energy` from
    energy.json when it exists next to the style (its medians' hash is a third source of tokens.json, so a new
    calibration rebuilds the tokens), else from the spec's paper-cards numbers; an `- **Energy:** moving 45, middle 50,
    pixels 3.5, still 12, longest 1.5` line in tweaks.md overrides any subset. The energy CLI reads the repo's
    tokens.json by default, so every caller judges against the calibrated targets. analysis/ is not in git: another
    machine gets the spec's numbers until it calibrates.
290. **tokens.json `motion.grammar` holds the Motion and energy rules as values** (pipeline/lib/tokens.py GRAMMAR: the
    main animation's combined properties, the inertia, the three hold levels, the exit, the edge and ambient layers,
    the camera and depth step, the mascot idle, E3's caption fonts and ratios and E4's budget for M15, E8's
    composition numbers for M16, and the text zones derived from the zones: the caption band, the hook header, the end
    card's text). tokens.css exposes them as `--m-*` custom properties (and the zones as `--m-zone-<name>: x y w h`),
    which pc-motion.js reads at mount. `verify` exempts motion.grammar and energy: their numbers come from BUILD_SPEC.md
    section 5 and from the calibration, not from style.md or tweaks.md. TOKENS_VERSION is 2, so every tokens.json is
    rebuilt once.

### pc-motion.js, the shared grammar (E1, E2, E6)
291. **HyperFrames seeks GSAP timelines with events suppressed.** Its runtime drives every sub-composition timeline with
    `totalTime(t, true)` (the second argument suppresses callbacks), and a Node check with the vendored GSAP 3.15
    confirmed that `onUpdate` never fires under it, while a tween on an accessor property runs its setter. M9's
    count-up, typing and end-card wobble were onUpdate-driven; the golden render of M9 shows their final states, so
    some capture path did fire them, but nothing in the library relies on callbacks any more: pc-motion.js tweens
    real properties (position, scale, rotation, opacity) or an object whose property setter renders text
    (PCM.driven, PCM.countUp, PCM.typeInto), and a wobble is a pair of yoyo tweens. Every frame is the same whichever
    way the timeline is seeked.
292. **One life per element (PCM.life).** The four phases of E1 are GSAP tweens laid on the component's timeline:
    the main animation (the style's measured enter: rise 38 px over 8 frames expo.out with opacity over 5; the pop
    with its overshoot; the fly-in; a fade; a slide), the combined properties of E2 on top of it (a zoom from 0.85, or
    0.92 for small things, or 1.15 from a close start, over 18 frames (0.6 s) power3.inOut, and a parallax rotateY or
    rotateX from 12 degrees to 1 starting 3 frames later), then the inertia and the hold as one tween per property whose ease
    is the closed form d(t) = A (1 - (1 - min(t, D) / D)^3) + v t (PCM.glide: a cubic decelerating tail of amplitude A
    over D = 3 s on top of the hold's constant speed v, so the speed never reaches zero), then the exit. The inertia
    continues the main move's direction: a risen card keeps rising 12 px, a zoomed one keeps growing to 1.03, a turned
    one settles through 0 to minus 1 degree. The hold levels are calm, normal and lively (2, 4, 8 px per second; 0.2,
    0.4, 0.6 degrees per second; 0.2, 0.35, 0.5 percent per second), a `hold` prop on every element component, normal
    by default, and a hold kind per element (drift, rotate, scale or all). The hold ends at the element's exit (every
    exit target is absolute, computed from the hold's end, so the result does not depend on the order frames are
    rendered in) or at a 90 s horizon when the clip ends without one. Children of a holding element (rows, bars,
    caption words, the headline's words) get their own main animation and no hold of their own: the group moves as
    one, as E1 asks.
293. **Each element carries its own perspective** (GSAP transformPerspective 1400 px, the vanishing point at its center)
    instead of one camera on the root. A rotated element then projects symmetrically around its center, so its
    measured center is exact: frame-match fits the main animation on the element's center (cy, cx) and the review's
    pixel checks see no asymmetric growth. E6's depth is per element too: PCM.depth puts a card's image, title and
    body (a chart's title and bars, a table's head and rows, a chat's reply and bar, the DM card's avatar and text)
    at translateZ steps of 24 px under preserve-3d, and the hold's slow rotation is the camera. Elements with
    overflow hidden or a filter (window cards, terminals, the exits' blur) stay flat: the browser flattens them.
294. **Per component.** The headline's blocks hold by rotation and scale only (a drift would carry the kicker above the
    safe top) and move from frame 0; caption chunks drift upward at the calm speed while on screen (E3's two modes
    come in M15); logo tiles turn only 6 degrees and the lockup and the DM avatar only drift (BRAND.md: a logo is
    never turned or distorted); the end card keeps its v02 wobble as yoyo tweens on its 2D rotation while its life
    drives the rest; the camera move's stage drifts its content before the move and holds from where the move ended
    (PCM.camera, PCM.life's `from` state); the mascot idles on its inner svg (a bob, a scaleY breath, the prop group
    `.pc-prop` wiggling, the eyes `.pc-eye` blinking every 2.6 to 3.8 s, seeded) on top of the wrapper's life, in the
    card, window card, fly-in, end card and mascot components; hero-3d's shadow breathes with a scale hold and its
    object spins and bobs from the hf-seek time as before. The three remaining state changes (a struck text dimming,
    a send button recoloring, a screenshot panning inside its window) are PCM.dim, PCM.recolor and PCM.pan, so no
    composition file holds a tween, an ease or an onUpdate of its own (test-m14 greps for them).

### The canvas (E5, E7) and icon-3d (E6)
295. **paper-canvas has a timeline now** (window.__timelines["paper-canvas"]; its host lost data-no-timeline in golden.py
    and the showreel, and carries `seed` and `duration` as variables: the seed from the idea id, the duration the
    reel's length plus 1 s). PCM.canvas builds the edge filler (6 elements, 3 per side: soft surface cards, thumbnail
    frames, dark chips without text, glow shapes and accent stars, 30 to 70 percent outside the frame with the share
    kept 5 points inside that range so the sway never leaves it, the inside part never over 180 px, in three y bands
    that avoid the hook header and are shrunk by the 36 px sway) and the ambient layer (16 stars, dots and small
    clouds in the top and bottom bands and the side margins, never overlapping each other), both as sine sways whose
    period follows from the amplitude and the speed cap (PCM.periodFor: the edge layer at most 20 px per second, the
    ambient at most 10) and a twinkle on the opacity. The placement avoids the text zones of tokens.json with a 10 to
    14 px pad; the layers carry data-layout-ignore, sit under every component (the canvas is z 0) and the review's
    mechanical checks never look at the canvas host (the M14 line of S12). The harness's background copy of the
    canvas stays the static one (its scripts are stripped), so a component measured alone sees no layers.
296. **icon-3d** builds a low-poly Three.js icon in code: a small SVG path parser (M L H V C Q Z, absolute and relative)
    turns one of six paths (bolt, star, play, check, cursor, heart) into a THREE.Shape extruded with a bevel and flat
    shading, or a primitive (a rounded slab from absarc, a torus, an icosahedron), in one palette color, lit like
    hero-3d, turning at `spin` degrees per second with a bob, drawn from the hf-seek time. Without WebGL, or with
    `mode: css`, the CSS-extruded fallback: the same SVG in 8 to 16 depth layers (translateZ, the back layers darker)
    under a preserve-3d stage that PCM.life pops in, PCM.spin turns and PCM.sway bobs; the root reports data-webgl 1
    or 0. The catalog marks it kind 3d with `fallback: css`, so S10 never replaces it with a card; it is allowed in the
    hook and the ask beats only, because tweaks.md's 3D line keeps 3D objects to the hook and the end card (E6's icon
    at the center of any scene needs that line relaxed: HUMAN_TODO). golden.py, events.py, mechanical.py and the plan
    validator treat it as hero-3d (clip_start, the label).

### frame-match, the gallery, the golden
297. **frame-match measures every component for 4.33 s** (130 frames, the move's own frames for the strip correlation)
    and adds the life checks of E1: no visible tracked element stands still for 0.5 s (in every 15-frame window it
    moves 0.9 px, or turns 0.09 degrees, or scales 0.09 percent, or fades, or changes its text: the calm hold over half
    a second less a rounding margin; a canvas is judged on its pixels), the main element's inertia ends 2 to 4 s after
    its landing (the first 10 frames whose motion stays within 15 percent plus 0.02 px of the hold speed, the hold
    speed being the mean motion of the last 15 frames), and the component's own frames measured by review/energy.py
    (108x192, the same thresholds) for the gallery's energy line and catalog.json's `energy`. The fits of M9 read
    their end value just after the expected landing instead of the last frame (the element keeps moving), positions
    are centers, and the scale comes from the length of the transform's x basis vector (m11, m12, m13: a 2D
    hypot(a, b) read a rotated element as smaller). The harness pages take a tag so two harnesses never share a page
    file (a probe next to frame-match corrupted both).
298. **Earlier milestones touched:** M9 (test-m9 section 1 re-proposes the six version 2 lines in its sandbox copy of
    tweaks.md, because the user accepted them on 2026-11-07 and the scenario asserts the proposed state; harness.py's
    tag and 3D-aware measures; golden.py's canvas host and the pc-motion.js copy; gallery.py's showreel host and
    energy line; catalog.py's META), M10 (project.py's replace_3d skips a css fallback; visual/common.py's enter_frames
    and footprint, plan_validate.py and events.py know icon-3d; the frozen fixtures' index.html canvas hosts), M11
    (mechanical.py's clip_start for icon-3d), M1 (config: nothing). The frozen test projects rebuild from the plans
    with the new library, so M10 to M13's fake tests exercise it.
299. **What the golden reel measures after the rewrite (the same plan, the new library):** moving share 13.0 to 27.6
    percent (doubled, as the acceptance test asks; 28.1 before the hold learned to fit the room, decision 304), middle
    band 12.0 to 29.8, pixels changing 1.0 to 1.59, still stretches 49.5 to 30.0 percent, longest still 2.8 to 2.43 s
    (build/M14/golden-energy-before.json against golden/test-idea/energy.json); frozen frames fell from 25 to 4
    percent. The gain came from three things in this
    order: the window cards' screenshots scrolling inside their frames (30 px per second through the page's own height
    by object-position: the two window scenes went from 10 and 32 percent moving to over 80 and 60), the longer
    combined entrances (the zoom and parallax over 18 frames instead of a bare 8-frame rise) and the inertia's first
    second. The holds
    themselves (2 to 8 px per second, a tenth of a degree per frame) are subtle at 108x192 by the spec's own numbers:
    they end the frozen frames and the still stretches, not the moving share. The golden still misses every target
    (41, 46, 3.3, 15, 2): that is M15's kinetic captions and M16's content motion, camera and layered scenes, as the
    spec plans. The render takes 2 to 3 minutes on this PC (90 s before: the 3D parallax, the canvas layers and the scrolling screenshots cost the rest).
300. **Found on the way:** the Bash tool truncates a command near 8 KB, so every multi-file change of this milestone
    is a patch script under build/M14/tmp/ run by python; two harnesses writing the same page file corrupt each other
    (the tag); a zero-duration GSAP tween at position 0 is not rendered when the timeline is seeked to exactly 0
    (the caption chunk's initial state is set at once, outside the timeline); a zero-height plane inside a rotated
    3D card projects a few px tall, so a growing bar starts at a hair and its first frame is read against its own
    baseline; a fit that reads frames after the landing is biased toward a shorter move once the inertia exists.
301. **Found by the M11 rerun: the caption line still sat at y 1480.** The user accepted the "Caption position" proposal on
    2026-11-07 (tokens.json zones.caption.center_y 1332, tokens.css --caption-y, the review's band around 1332), but
    caption-line's `y` prop defaulted to 1480 and the compiler never passes one, so every reel's captions would have
    failed S12's zone check from that day on. The default is now 0, meaning the style's position from tokens.css
    (--caption-y); a plan may still give a y. The frozen M10 and M11 fixtures rebuild with it, the golden was rendered
    once more (its energy numbers moved by a tenth of a point), and the gallery still shows the words in the band.
302. **Also found by the M11 rerun: the CTA's DM card ended below the safe bottom.** With the old caption box at y 1480
    the review and the validator let the DM card and the end card sit in the caption band (DECISIONS.md 218, 248); the
    accepted caption position (1332) drops that exception, so a DM card at y 1305 (172 px tall) ran to 1477 against
    the safe bottom of 1440. The director's default (plan9.apply_branding), the golden plan, the validator fixtures and
    the frozen run now put the DM card at y 1266 and the end card's lockup at lockup_y 1146 (the lockup keeps its clear
    space above the card, the card ends at 1438), and the validator's CTA exemption applies only while the caption band
    lies below the safe bottom (tokens.json zones.caption.safe_zone_exception). The golden plan therefore differs from
    M9's by these two numbers; the M14 test still renders it without regenerating it ("the same plan") and compares it
    with its own hash. The window card's scrolling screenshot moved from a transform to its object-position at the
    same time: the image box never leaves the window, so the review's off-canvas rule stays quiet.
303. **Also found by the M11 rerun: the review judged elements mid-entrance.** With E2 every entering element starts
    at scale 0.85 (0.92 small, 1.15 close) and rotated 12 degrees, and the review's font rule multiplied a text's font
    size by a 2D reading of its transform (hypot(a, b), which is cos 12 degrees under a rotateY), so a sample inside the
    first frames of a DM card read its 28 px labels as 23 px. Three changes. The grammar marks every element's main
    animation window on the element itself (`data-pcm-main="from,to"` in local seconds, from the start to the end of
    the zoom and the lagging rotation: 21 frames) and its exit window (`data-pcm-exit`), both set once when the
    timeline is built (PCM.mark). The review reads the scale as the length of the transformed basis vectors (the 3D
    matrix's first two columns: a rotation is not a scale) and does not judge a text or an image while it, or one of
    its ancestors, is inside such a window: arriving and leaving elements are transients by design (E1 phases 1 and 4),
    judged at the next sample of their life; mechanical.json counts them (counts.transient). The "landed" sample time
    of decision 245 moves to after the combined animation (the component's start plus the grammar's main frames plus
    the rotation lag plus 100 ms, or its landing plus 100 ms when its life is shorter), so the zone and overlap checks
    read the element at rest rather than at 0.98 scale and 5 degrees. Once landed the grammar only grows an element
    (the inertia's scale 0.04 and the hold's creep go up), so a text never reads smaller than its designed size after
    its entrance: the 24 px floor stays a rule about the design. test-m14 section 3 checks the three states on the DM
    card. An element whose whole life is shorter than that window (a chip on a scene's last word, 630 ms in the test
    idea) would never be judged, so it is judged once, at the last sample of its life that is not an exit (check_times
    adds one 50 ms before its end, where the zoom and the rotation are nearly settled), for its geometry and with its
    designed size; the M11 test's planted chip above the safe top found this.
304. **Also found by the M11 rerun: the hold fits the room.** The CTA's DM card drops in and lands with its bottom 2 px
    above the safe bottom (decision 302); E1's inertia (16 px, downward: the drop's direction) and the normal hold's
    drift (4 px per second) then carried its message to y 1449 by the end of the ask beat, below the safe bottom of
    1440. E1 offers the hold as a drift, a rotation or a creep, so near a safe edge the element turns and creeps
    instead of drifting: PCM.life reads the element's rest box (layout offsets up to #stage, which no tween changes),
    the room from it to the safe edges in the move's direction (the safe top and bottom, the side margins, the right
    rail in the lower half, as `--m-safe-*` in tokens.css from tokens.json zones) and fits the planned travel into it:
    the inertia plus the drift over the element's life, which is its `until` or `exit_at` when known and else the
    grammar's room_life_s (8 s, tokens.json motion.grammar.hold; the components do not know the host's duration). The
    drift slows first, then the inertia shrinks; the rotation and the creep keep the element alive (frame-match's
    static rule). A component may opt out with `room: false`. The DM card at the CTA's y therefore moves 2 px down and
    grows; at y 700 it drifts as before (test-m14 section 3 checks both). The scale creep still moves a wide card's
    edges a few px outward over a long hold; the review's samples watch for it, and M16's energy loop can tune the
    hold levels and the room per scene with the real lives.
