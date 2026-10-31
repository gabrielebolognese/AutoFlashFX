# M1 review 1: Skeleton

Reviewer: fresh session, 2026-10-31. Scope: everything changed since 2207b72 (commits 1de401a, 986f7e7, 000acd5),
read against BUILD_SPEC.md sections 1, 2.1, 3 (preflight), 6, 9, 11 and 12 (M1), PLAN.md (M1) and DECISIONS.md
38 to 51. No earlier review or fix file exists for M1.

## Verdict

APPROVED. The acceptance test passes, every M1 item of section 12 is built, and I found no required fix.

## 1. Acceptance test (run by me)

`bash pipeline/tests/test-m1.sh`: **96 passed, 0 failed**, exit 0, 30 s wall clock, no model calls.
`bash pipeline/tests/run-all.sh`: test-m1.sh 96/96 and test-no-emdash.sh 1/1 ("no_emdash: clean"),
"run-all: 2 test files, all passed", exit 0.

What the output shows:
- Parser fixtures: multi-line ideas joined, CRLF plus BOM normalized with exact texts, Italian accents, emoji and
  typographic quotes intact, notes and stray braces ignored, two blocks on one note line, restarted block and `{}`
  reported, empty and missing files count 0, JSON shape.
- Ids stable across additions, removals, CRLF versus LF and whitespace.
- Remove: exact id, an edited idea removed at similarity 0.9 or more and logged, an unrelated hint leaves the file
  byte for byte untouched (exit 3, logged), notes survive, CRLF stays CRLF.
- Concurrency: 20 add-idea.sh processes plus one removal leave exactly 20 intact ideas, no lock dir, no temp file;
  a 120 s old lock is broken and logged; a live lock makes the writer wait.
- validate-json exit codes 0, 1, 2; run.sh banner fields, NO_COLOR, runner.log and status.txt; ffmpeg hidden from
  PATH gives exit 3, STOPPED.md with the winget fix, the STOP line, no banner; the next start removes STOPPED.md.
- The only stderr noise is the expected "unclosed brace" warnings from the notes.txt fixture in section 3.

Extra checks I ran myself (temporary roots, nothing written to the real repo):
- Stronger interleaving: 3 rounds of 15 background add-idea.sh calls with two removals fired 0.4 s and 0.6 s in
  (the removals landed at queue sizes 3 to 7 and 15 to 16, so they really ran mid-burst): 16 ideas every round,
  no stderr output. The "loses nothing" property holds under real interleaving.
- `bash run.sh` in a sandbox: `READY preflight ok: 7 tools, 1 python packages, 4 files, 173 GB free`, then the
  banner `reels autopilot v0.1.0 (000acd5) | queue: 16 ideas | style: paper-cards | voice: chatterbox (fallback
  kokoro) | sfx map: not built` and the queue.
- A CRLF ideas.txt without a final newline gets the new idea appended with CRLF; a file without a final newline
  gets a newline before the new block; stdin input works; empty stdin exits 1.
- After the tests the real repo has no logs/, runs/ or exports/ and `git status` shows only the untracked
  build-runner.new.sh (not M1's, correctly left alone).

## 2. Spec compliance

- Section 12 M1 "Builds": folders (with .gitkeep), git, config.json, preflight, ideas.txt parsing, the lock,
  add-idea.sh, the test idea (exact text from 2.1). All present.
- Section 12 M1 "Test": parser fixtures (multi-line, CRLF, Italian accents, text outside braces) and concurrent
  additions during a deletion. Both covered and passing.
- 2.1: braces across lines, notes ignored, first idea, append at end, CRLF and UTF-8, `.locks/ideas` mkdir lock
  with 60 s stale timeout, temp file plus atomic replace, hash of normalized text, 0.9 similarity fallback with
  "leave alone and log" otherwise. The braces rule is in CLAUDE.md.
- Section 1 git: runs/, exports/, logs/, styles/*/refs/, styles/*/analysis/, sfx audio and .cache/, library/voice/
  (README.txt re-included), .env all ignored (checked with git check-ignore); .gitattributes forces LF.
- Section 3 preflight: claude, ffmpeg, ffprobe, python (min 3.11), node (min 22), gh, git, jsonschema, style
  files, hooks.txt, disk; STOPPED.md with the exact fix and exit 3. The voice reference, tokens.json and sfx map
  checks are deferred to M7, M8 and M9 (DECISIONS.md 23, report "Known gaps"); acceptable since those files do not
  exist yet.
- Section 6: `[HH:MM] TAG  details` with the tag padded to 6, ANSI colors only on a terminal without NO_COLOR,
  runner.log append and status.txt overwrite.
- Section 9: every key present (models with effort, tts, voice, sfx numbers 4, 250, 8, 8 to 12, 400, 33; lengths
  25 to 40 and 45 to 75; caps; runner 120, 300, 120, Europe/Rome; style; paths). Model assignments match the spec.
- Section 11: CLAUDE.md has the build status, how to start, the braces rule, logs, curated folders.

## 3. Robustness

- Windows Git Bash: roots exported through `cygpath -m`, ideas.py also accepts /c/... paths, every Python helper
  reconfigures stdout to LF and UTF-8, PYTHONUTF8 and LANG set, `python` (never python3) everywhere, OneDrive
  replace retries. GNU `date`/`touch -d` only in tests. No hardcoded secrets. No em dash in any tracked or new file.
- Errors: lock timeout exit 4, file errors exit 2, unknown run.sh options exit 1, malformed braces warn on stderr.

## 4. Earlier milestones

M0 has no test command (build/progress.md). M0 documents were only appended to (DECISIONS.md M1 section with a
dated correction to item 36, CLAUDE.md status), nothing broken.

## Required fixes

None.

## Repeated from earlier review

None (this is the first M1 review).

## Optional suggestions (never a reason to reject)

1. **CLAUDE.md lines 55 to 56: the `\n` in the snippet became a real line break.** The file reads
   `sys.stdout.reconfigure(newline="` then a new line, then `")`. A session that copies it gets a broken string
   literal. Write it as `newline="\n"` (escaped) so the snippet is copyable; verify with
   `grep -n 'newline="\\n"' CLAUDE.md`. Worth doing in the M2 batch since CLAUDE.md is loaded into every session.
2. **add-idea.sh silently truncates unbraced text that contains `}`.** `bash pipeline/bin/add-idea.sh "foo } bar"`
   stores `{foo}` and prints "added 1 idea", losing " bar". The wrapper builds `{foo } bar}`, which parses as the
   block "foo" plus a note. Rare (the braces rule always passes braces), but it is silent data loss. Either refuse
   text that has a `}` without a `{` with a clear message, or replace the stray brace before wrapping. Verify:
   the command above either exits 1 with a message or stores the whole text.
3. **test-m1.sh section 5:** the removal starts right after the 20 background processes are spawned, so it may run
   before most of them start. It still proves the invariant, but a short `sleep 0.3` before the removal (and a
   second removal a bit later) would guarantee real interleaving, as in my extra check above.
4. **run.sh banner:** if `ideas_count` fails (unreadable ideas.txt), `queue` is empty and `[ "$queue" -gt 0 ]`
   prints a bash error. A `${queue:-0}` guard, or a STOP line, would be cleaner. M2 replaces this body anyway.
5. **Banner voice field:** it shows the configured primary (chatterbox) even though reference.wav is missing and
   the spec (2.5) says the kokoro stock voice is used until it exists. M7 should print the effective engine.
6. **Deferred preflight items:** make sure M7 (TTS venv, voice reference or kokoro), M8 (sfx map) and M9
   (tokens.json, node modules) append their entries to `preflight.require`, as DECISIONS.md 23 promises.
