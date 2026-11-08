# M17 Control check: report

No behavior change. Nothing the runner uses was touched: the milestone adds files under `build/M17/` and `pipeline/tests/`, plus the build's
memory files (CLAUDE.md, DECISIONS.md 325 to 332, build/progress.md, build/HUMAN_TODO.md). `git diff --name-only e3e1bef..HEAD` lists nothing else
(test-m17 section 4 checks it). The video runner is not running (no `.locks/`, status.txt 8 hours old); M17 never wrote to it.

## What I need from you before M18 (the build is paused: build/PAUSE holds `M18`)

1. **Keep the video runner stopped.** It is stopped now. M18 refuses to move anything while a runner is alive; from M18 on it starts with
   `bash run.sh --channel flashfx`. Unfinished runs need nothing from you: they move with their channel and resume.
2. **The branch `important-ideas`** (your model change) is not merged. If you want it before the channels move, merge it now on a clean tree
   (`git merge important-ideas`), renumber its DECISIONS.md entries 323 to 325 (M16 and M17 use 323 to 332), run `bash pipeline/tests/test-models.sh`,
   and add `"test-models||all"` to the TESTS list of `pipeline/tests/run-fake.sh`. Otherwise M18 runs without it.
3. Nothing else. (`motion-lib/gallery/frame-match.json` and `.md` are modified and uncommitted: test runs of earlier milestones wrote them. M17 may
   not touch motion-lib, so they are listed as the one BLOCKER of risks.md; M18 commits or restores them before its first move.)

## What I built (all in pipeline/tests/, all `python` 3.13 standard library, LF, no em dash)

| file | what it does |
|---|---|
| `manifestlib.py` | the shared part: the inventory (every file, git state, sums per folder), the engine rules, the old-path forms, the TSV format, the config key destinations |
| `inventory.py` | `build/M17/inventory.md` and `inventory.tsv` (every file with its size and git state; machine state: runner, ideas queued, unfinished runs, exports, disk, OneDrive) |
| `refindex.py` | `refindex.tsv` (every reference M18 and M19 must change: paths, export names, config keys, direct config reads; with kind, rooted, certainty and planned change) and `refindex-data.tsv` (old paths inside data in every form) |
| `make-manifest.py` | `move-manifest.tsv` (every move of M18 and M19 in order, the export renames and rewrites included) and `config-keys.tsv` (every config.json key and its destination) |
| `check-manifest.py` | the checks of the spec (old paths exist, no collisions, new paths inside channels/<id>/ or exports/, every inventory file covered once or engine, files and bytes add up); `--after` checks a migrated folder; drift warns, `--strict` fails |
| `risk-scan.py` | `risks.md` (BLOCKER or NOTE) and `riskiest-moves.md` |
| `run-fake.sh`, `fakeresults.py`, `make-test-copy.sh` | runs every fake-only test in a throwaway copy of the repo, records result, duration and log per test and every failing check; `--compare DIR` applies the baseline rule |
| `m17-baseline.sh` | preflight, `doctor --quick` and the dummy fingerprint (`REELS_DUMMY=all bash run.sh --once`) in a temp copy of the state files |
| `m17-fixture.py`, `m17-simulate.py` | a small folder shaped like the real one (runs, exports, history, old paths in every form) and a naive executor of a manifest on it, to prove the manifest means what `--after` checks |
| `m17-summary.py` | the tables of this report |
| `test-m17.sh` | the acceptance test (4 sections) |

Design notes (DECISIONS.md 325 to 332): the manifest has two extra columns (`scope` top or inner, `sha256`); a folder with tracked and ignored files is one
`git-mv` line (git mv renames the whole directory, ignored files included); `.git`, `node_modules` and `build/` are summary rows in the inventory;
Python caches are left out of every count.

## What moves where (build/M17/move-manifest.tsv: 11 lines, all M18)

| destination | lines | files | size | method |
|---|---|---|---|---|
| channels/flashfx/ideas.txt | 1 | 1 | 139 B | git-mv |
| channels/flashfx/library/ | 1 | 43 | 10.3 MB | git-mv |
| channels/flashfx/styles/ | 1 | 1167 | 392.2 MB | git-mv |
| channels/flashfx/motion-lib/ | 1 | 5409 | 79.6 MB | git-mv |
| channels/flashfx/golden/ | 1 | 82 | 40.4 MB | git-mv |
| channels/flashfx/logs/ (runner.log, status.txt, build-sfx-map/, index-hooks/, voice-profile/) | 5 | 21 | 228.8 KB | fs-mv |
| stays at the root (voicetests/, your voice experiments) | 1 | 14 | 11.1 MB | stays |

The rest of the folder is engine and stays: 12,762 files (pipeline, tools, build, node_modules, config.json, run.sh, the docs). 6,737 files are
covered by the 11 lines; the inventory has 19,499 files and 1.1 GB (check-manifest passes: every file covered once or engine, the sums add up).

**There is no `runs/`, no `exports/` and no `.locks/` in the folder today**, so the manifest has no run line, no export rename and no rewrite line yet.
The rules for them (runs move with the channel and get their old paths rewritten, exports/N becomes exports/flashfx-N with renamed files and
rewritten HOOKS, RUN and EDITOR lines, the history's "exported N" becomes "exported flashfx-N") are proved on the fixture folder by test-m17 and
`check-manifest.py --after`. M18 and M19 write the manifest again right before they move, so whatever the runner makes in between is covered by the same rules.

## The 10 riskiest moves (riskiest-moves.md has the reasons)

1. `styles` (392 MB, 1,160 ignored files: reference videos, analysis frames, the sound pack's audio): git cannot restore them, only the undo script.
2. `motion-lib` (5,409 files, 5,256 ignored: renders, harness caches): the most files; absolute old paths inside it (see below).
3. `golden` (40 MB, golden.mp4 and project caches ignored).
4. `library` (curated by you: hooks, profile, voice recordings and engine.txt are ignored files; never to be lost or edited).
5. to 9. the five items of `logs/` (a log the runner appends to: only with the runner stopped).
10. `ideas.txt` (your queue).
Beyond the moves, the riskiest edits are the rewrites of old paths in run folders, captions files and history lines, and moving the config keys into
channel.json (config-keys.tsv: 231 keys: 42 move to channel.json in M18 (the sections style, voice, sfx, lengths and 14 paths), 82 to format.json in M20 (7 sections), 107 stay engine, the four review safety keys among them).

## BLOCKERs and NOTEs (risks.md: 1 BLOCKER, 18 NOTEs)

- BLOCKER: uncommitted changes outside build/ and pipeline/tests/: `motion-lib/gallery/frame-match.json` and `.md` (written by earlier tests). M18 resolves
  it first (commit or restore). No video runner is alive, no unfinished run, no symlink, no online-only OneDrive file, no path over 200 characters
  (the longest is 143, the new prefix adds 17), 149 GB free, and the manifest places every file.
- NOTEs worth reading: old paths inside data (refindex-data.tsv): 39 tracked `motion-lib/gallery/play/*.html` carry a `<base href="file:///C:/Users/there/.../motion-lib/">`,
  `motion-lib/webgl.json` holds a backslash path, and the ignored harness and `.hyperframes` caches of motion-lib and golden hold the same absolute paths; they are
  tool output that is rebuilt (gallery, harness) and M18 lists each one it rewrites or regenerates. OneDrive syncs this folder (renames may fail for a moment:
  the migration retries). The tracked runner-written files (`library/.hooks.stats.json`, `hooks.suggested.txt`) are committed as a snapshot by M18 first.
  The `.gitignore` has 34 rules that name the old folders and become `channels/*/...` rules before the first move.

## M18's size (refindex.tsv: 2,207 occurrences in 245 files; 26 are not under the root and need nothing)

| subject | code | comment | prompt | doc | test | fixture | data | config |
|---|---|---|---|---|---|---|---|---|
| path (library/, styles/, motion-lib/, golden/, ideas.txt, runs/, logs/, .locks/, exports/) | 195 | 258 | 30 | 167 | 783 | 49 | 123 | 35 |
| export name (N.mp4, Ncaptions.txt, Nhook2.mp4, exports/N, "exported N") | 11 | 17 | 0 | 20 | 51 | 0 | 0 | 0 |
| config key that moves | 221 | 73 | 1 | 56 | 34 | 0 | 0 | 0 |
| direct read of config.json | 29 | 9 | 2 | 3 | 14 | 0 | 0 | 0 |

Paths built in code are the work: 195 occurrences, most in `pipeline/stages/05-hooks/run.sh` (28), `pipeline/lib/runner.sh` (27), `voiceover.py` (20), `sfx/mixsfx.py` (19),
`build-runner.sh` (16), `bin/build-sfx-map`, `bin/build-voice-profile` (15 each). 42 occurrences are the folder's own absolute path (`certainty absolute`),
41 of them in tracked data. 104 config-key rows are candidates (a section access such as `cfg["review"]`, which may be an unrelated dict).

## The baseline (build/M17/baseline/)

`bash pipeline/tests/run-fake.sh` ran 18 test files (plus test-m17 at the end) in a throwaway copy of the repo (about 7 hours here: the machine has 2 GB of free memory and every test renders or
runs the dummy pipeline; durations are recorded, never compared). Results (results.tsv, failures.tsv, logs/<test>.log):

| test | sections | status | passed | failed |
|---|---|---|---|---|
| test-no-emdash | all | pass | 1 | 0 |
| test-limits | all | pass | 94 | 0 |
| test-m1 | all | pass | 96 | 0 |
| test-m2 | all | **known failure** | 192 | 15 |
| test-m3 | 1 2 3 5 to 10 | **known failure** | 372 | 2 |
| test-m4 | 1 2 | pass | 202 | 0 |
| test-m5 | 1 2 | pass | 196 | 0 |
| test-m6 | 1 2 | **known failure** | 146 | 1 |
| test-m7 | 1 2 | **known failure** | 115 | 1 |
| test-m8 | 1 2 | pass | 164 | 0 |
| test-m9 | all | pass | 80 | 0 |
| test-m10 | 1 2 | pass | 134 | 0 |
| test-m11 | 1 2 3 | pass | 227 | 0 |
| test-m12 | 1 2 3 5 | pass | 180 | 0 |
| test-m13 | 1 2 4 | pass | 100 | 0 |
| test-m14 | all | pass | 74 | 0 |
| test-m15 | all | pass | 127 | 0 |
| test-m16 | 1 2 3 4 5 7 | pass | 166 | 0 |
| test-m17 | 1 2 3 4 | pass | 80 | 0 |

Known failures (recorded, not fixed, as the spec says):
- test-m2 (15 checks): the two-idea dummy run takes more than the test's 300 s on this machine (exit 124), so the second export and the checks after it fail. The
  same 192 passed and 15 failed were recorded in M16 (DECISIONS.md 324).
- test-m3 (2 checks): `limit date` and `limit epoch` (the LIMIT line's target time and the fast-forward line), clock dependent.
- test-m6 (1 check): `setup: the beat map comes from style.md and the excerpts from voice.md`: your filled voice.md (as in M15's report).
- test-m7 (1 check): the S8 setup line: library/voice/engine.txt names the turbo engine, so the line says something else.
- test-m17 itself is the last row of results.tsv (`run-fake.sh --append --only test-m17`, in the copy): pass, 80 checks.

Also recorded: `preflight.txt` (ok: 8 tools, 2 python packages, 9 files), `doctor-quick.txt` (0 problems, 0 warnings), and the dummy fingerprint of
`REELS_DUMMY=all bash run.sh --once` in a temp copy: `fingerprint-run.txt` (106 entries: the run folder's tree, `<ts>` for its date and time),
`fingerprint-exports.txt` (`1/`, `1/1.mp4`, `1/1captions.txt`, `1/1hook2.mp4`), `fingerprint-state.txt` (the root's other entries: logs, .locks), `dummy-run.txt`.
The baseline rule from here on: no test that passed in the baseline fails; `bash pipeline/tests/run-fake.sh --compare build/M17/baseline` applies it
(per test file and per failing check; a known failure that now passes is fine).

## How to run the tests

- `bash pipeline/tests/test-m17.sh` (about 5 minutes; `M17_SECTIONS="1 2"` is the quick part): 1 the manifest rules on the fixture, 2 check-manifest's planted
  faults and `--after` on a migrated fixture, 3 refindex on the fixture and determinism (make-manifest and refindex run twice on the fixture and on the real folder),
  4 the recorded artifacts, the baseline machinery, `git diff` against MS_START_SHA, no em dash.
- `python pipeline/tests/check-manifest.py` passes (11 lines cover 6,737 files; 12,762 engine files).
- Regenerate: `python pipeline/tests/inventory.py; python pipeline/tests/make-manifest.py; python pipeline/tests/refindex.py; python pipeline/tests/risk-scan.py`.
- `bash pipeline/tests/run-fake.sh` (the baseline again, about 7 hours), `bash pipeline/tests/m17-baseline.sh` (about 6 minutes).

## Known gaps

- The real folder has no runs/ and exports/, so the run and export lines are proved on a fixture, not on real data.
- `test-m17` joined the baseline after the commit that holds it (it needs its own artifacts to exist); the baseline of the other 18 test files ran before it was written.
- The refindex classifies by file place and by line shape: a docstring with a path is a comment, a dict access called "review" is a candidate. M18 reads
  the candidates.
- A background command of the build tool is stopped after 2 hours here, but the test chain it started kept running to the end (nothing was lost).

## HUMAN_TODO items added

- M17: the pause list (merge `important-ideas` if you want it, the uncommitted frame-match files, keep the runner stopped): build/HUMAN_TODO.md.
