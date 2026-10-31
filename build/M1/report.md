# M1 report: Skeleton

Built 2026-10-31 from BUILD_SPEC.md section 12 (M1) and PLAN.md (M1). Acceptance test green: 96 checks in about
35 seconds, no model calls.

## What this batch built
- **Folders and git.** library/profile/, library/voice/ (ignored except its README.txt), motion-lib/ with
  candidates/ and gallery/, golden/, pipeline/{lib,stages,bin,vendor,knowledge,tests}/ (.gitkeep where empty).
  hooks.txt moved to library/hooks.txt with `git mv`, content untouched. runs/, exports/, logs/ and .locks/ are
  created by run.sh at startup.
- **config.json.** Every key of spec section 9: models with an effort level per role, tts (primary chatterbox,
  fallback kokoro, gaps, whisper model, engine parameters), voice, sfx (map path, base gain per cue type, density
  and spacing rules), lengths, caps, runner (poll, heartbeat, limit margin, timezone, sleep scale, lock timeouts,
  minimum free disk), paths, and `preflight.require`, the table the startup checks read.
- **ideas.txt** with the spec's test idea, and **library/profile/deliverables.txt** and **pronunciations.txt**
  with header comments explaining their formats (no entries yet: HUMAN_TODO).
- **The idea queue** (pipeline/lib/ideas.py, wrapped by pipeline/lib/ideas.sh): the braces parser (multi-line
  ideas, CRLF, BOM, UTF-8, text outside braces ignored, a restarted block on a forgotten closing brace), the id
  (12 hex characters of the sha1 of the normalized text), `list`, `first`, `count`, `id`, `append` and `remove`
  with the 0.9 similarity fallback for an idea edited meanwhile (left alone and logged otherwise). Every write
  takes the `.locks/ideas` mkdir lock (60 s stale timeout, stale locks removed and logged) and rewrites the file
  atomically (temp file plus replace, retried for OneDrive). A CRLF file is written back as CRLF.
- **pipeline/bin/add-idea.sh**: appends every braced block from its arguments or stdin (text without braces is
  wrapped), prints one confirmation line with the queue size, and records each addition in logs/.new-ideas so the
  M2 runner can print its NEW line.
- **Preflight** (pipeline/lib/preflight.sh, pipeline/bin/preflight): table-driven checks for commands (with
  minimum versions for python and node), Python packages, style files, library/hooks.txt, free disk space and the
  gh login (warning only). A hard failure writes logs/STOPPED.md with the diagnosis and the exact fix, prints a
  STOP line and exits 3. A successful start removes a leftover STOPPED.md.
- **run.sh**: creates the state folders, runs the preflight, prints the banner (version and commit, queue size,
  style, voice engine and fallback, sfx map file count or "not built"), lists the queue, then exits saying the loop
  arrives in M2. `--once` is parsed; unknown options exit 1.
- **Shared libraries**: pipeline/lib/common.sh (roots exported in C:/ form, PYTHONUTF8, LANG), log.sh (`say`,
  the status line format of spec section 6, colors on a terminal, runner.log append, status.txt overwrite),
  config.sh (`cfg`, `cfg_rows`).
- **Tools**: pipeline/bin/validate-json (jsonschema), pipeline/bin/setup-python, requirements.txt.
- **Tests**: pipeline/tests/lib.sh (sandboxed REELS_ROOT, asserts, fast_mode), test-m1.sh, test-no-emdash.sh with
  no_emdash.py, run-all.sh, and the parser fixtures in pipeline/tests/fixtures/ideas/.

Two Windows facts shaped the code and are recorded in DECISIONS.md 38 to 40: Git Bash converts POSIX paths in
arguments but not in environment variables (so roots are exported through `cygpath -m`), and Windows Python
writes CRLF to pipes (so every helper reconfigures stdout to LF).

## Files
- New: config.json, ideas.txt, requirements.txt, run.sh, library/profile/deliverables.txt,
  library/profile/pronunciations.txt, library/voice/README.txt, pipeline/lib/{common.sh, log.sh, config.sh,
  ideas.py, ideas.sh, preflight.sh}, pipeline/bin/{add-idea.sh, validate-json, preflight, setup-python},
  pipeline/tests/{lib.sh, run-all.sh, test-m1.sh, test-no-emdash.sh, no_emdash.py},
  pipeline/tests/fixtures/ideas/{multiline, crlf, italian, notes, inline, restart, empty}.txt, .gitkeep files in
  golden/, motion-lib/candidates/, motion-lib/gallery/, pipeline/stages/, pipeline/vendor/, pipeline/knowledge/.
- Moved: hooks.txt to library/hooks.txt (unchanged).
- Changed: .gitignore (library/voice/* with README.txt re-included), .gitattributes (the CRLF fixture is `-text`),
  CLAUDE.md (build status, braces rule now live, runner note, Windows path note), DECISIONS.md (M1 section, items
  38 to 51, including a dated correction to item 36), build/progress.md, build/HUMAN_TODO.md.

## How to run the test
```
bash pipeline/tests/test-m1.sh          # the M1 acceptance test (about 35 s)
bash pipeline/tests/run-all.sh          # every test that exists, plus the em dash scan
```
KEEP_SANDBOX=1 keeps the temporary root for inspection. The tests never touch the real ideas.txt, runs/, exports/
or logs/.

## Test output summary
`test-m1.sh: 96 passed, 0 failed` (34 s), `test-no-emdash.sh: 1 passed`, `run-all: 2 test files, all passed`.
- Parser fixtures: multi-line ideas joined to one line, CRLF plus BOM normalized with the exact texts, Italian
  accents, an emoji and typographic quotes intact, notes and a stray `}` ignored, two blocks inside one note
  line, a restarted block and `{}` reported on stderr, empty and missing files count 0, JSON output shape.
- Ids: 12 hex characters, unchanged when other ideas are added or removed, identical for CRLF and LF versions and
  across whitespace differences.
- Remove: the exact id; an idea edited meanwhile (similarity 0.98) removed and logged; an unrelated hint leaves
  the file byte for byte untouched with exit 3 and a log line; notes survive; a CRLF file stays CRLF.
- add-idea.sh: two blocks in one argument, text without braces, stdin, a multi-line idea, UTF-8 accents, the
  logs/.new-ideas record, blank input and `{}` refused.
- Concurrency: 20 add-idea.sh processes against one removal leave exactly 20 intact ideas, no lock directory, no
  temp file, no timeout; a 120 s old lock is broken in 1 s and logged; a fresh lock makes a writer wait until it
  is released.
- validate-json: valid, invalid (exit 1 with the path and message), unreadable (exit 2).
- run.sh: exit 0, READY and START lines with every banner field, the queue listed, no escape codes under
  NO_COLOR, runner.log and status.txt written, state folders created; with ffmpeg hidden from PATH: exit 3,
  STOPPED.md naming ffmpeg and the winget fix, the STOP line in the terminal and in status.txt, no banner; the
  next good start removes STOPPED.md and says so.

## Known gaps
- run.sh has no processing loop yet (M2). The NEW line consumer of logs/.new-ideas is also M2.
- preflight.require lists M1's dependencies only; M7 adds the TTS venv and the voice reference or kokoro fallback,
  M8 the sfx map, M9 tokens.json and the node modules (DECISIONS.md 23).
- library/profile/account.md and voice.md arrive in M5; deliverables.txt and pronunciations.txt hold only their
  header comments until the user fills them.
- The stale lock breaker has a microsecond race between its second mtime check and the rmdir (DECISIONS.md 43);
  accepted on a single-user machine.
- An untracked `build-runner.new.sh` appeared in the root at 13:23, after this batch started. It is not part of
  M1 and was left uncommitted.
- Earlier milestones touched: only the M0 documents, by appending (DECISIONS.md M1 section with the correction to
  item 36, CLAUDE.md status and rules, .gitignore and .gitattributes as described above).

## HUMAN_TODO items added
- M1: fill library/profile/deliverables.txt and library/profile/pronunciations.txt (formats in the headers).
- M1: add ideas with `bash pipeline/bin/add-idea.sh "{...}"` or by pasting braces into Claude Code; hand edits
  are fine while the runner is stopped.

## Commits
- 1de401a feat(M1): skeleton: config, ideas queue with lock, add-idea.sh, preflight, run.sh banner, tests
- 986f7e7 docs(M1): decisions 38 to 51, progress, human todo, CLAUDE.md build status
- docs(M1): report (this file, committed after it was written)
