# Inventory of the folder (M17)

Written by `python pipeline/tests/inventory.py`. inventory.tsv has one row per file (path, kind, size, files, git state, top-level item).
`.git`, `node_modules` and `build` are one summary row each (kind tree); `__pycache__` folders and `.pyc` files are left out.

Total: **19499 files, 1.1 GB** (7246 rows in inventory.tsv). Git state of the walked files: tracked 747, untracked (not ignored) 1, ignored 6495.

## State of the machine

- Video runner: not running (no .locks/runner/pid)
- logs/status.txt (874 minutes old): `[04:19] READY  preflight ok: 8 tools, 2 python packages, 9 files, 155 GB free`
- Ideas queued in ideas.txt: 1
- Runs: 0 finished, 0 unfinished, 0 with an unreadable state.json
- Exports present: none (no exports/ folder or it is empty)
- Free disk: 133.0 GB
- Synced by OneDrive: YES (the folder path contains OneDrive; the environment names a OneDrive folder (C:\Users\there\OneDrive)); 0 files are online-only (not on this disk)

## Top-level items

| item | kind | files | size | tracked | untracked | ignored |
|---|---|---|---|---|---|---|
| .git/ | folder | 3334 | 52.4 MB | 0 | 0 | 0 (+3334 in a summary row) |
| .gitattributes | file | 1 | 174 B | 1 | 0 | 0 |
| .gitignore | file | 1 | 1.4 KB | 1 | 0 | 0 |
| BUILD_SPEC.md | file | 1 | 169.6 KB | 1 | 0 | 0 |
| CHANNELS.md | file | 1 | 87.5 KB | 1 | 0 | 0 |
| CLAUDE.md | file | 1 | 28.0 KB | 1 | 0 | 0 |
| DECISIONS.md | file | 1 | 271.1 KB | 1 | 0 | 0 |
| PLAN.md | file | 1 | 79.6 KB | 1 | 0 | 0 |
| README.md | file | 1 | 15 B | 1 | 0 | 0 |
| build/ | folder | 2334 | 389.0 MB | 0 | 0 | 0 (+2334 in a summary row) |
| build-runner.sh | file | 1 | 52.3 KB | 1 | 0 | 0 |
| config.json | file | 1 | 14.8 KB | 1 | 0 | 0 |
| golden/ | folder | 82 | 40.4 MB | 55 | 0 | 27 |
| ideas.txt | file | 1 | 139 B | 1 | 0 | 0 |
| library/ | folder | 43 | 10.3 MB | 35 | 0 | 8 |
| logs/ | folder | 21 | 228.8 KB | 0 | 0 | 21 |
| motion-lib/ | folder | 5409 | 79.6 MB | 153 | 0 | 5256 |
| node_modules/ | folder | 6588 | 139.9 MB | 0 | 0 | 0 (+6588 in a summary row) |
| package-lock.json | file | 1 | 61.7 KB | 1 | 0 | 0 |
| package.json | file | 1 | 678 B | 1 | 0 | 0 |
| pipeline/ | folder | 490 | 25.6 MB | 480 | 1 | 9 |
| requirements.txt | file | 1 | 127 B | 1 | 0 | 0 |
| run.sh | file | 1 | 1.9 KB | 1 | 0 | 0 |
| styles/ | folder | 1167 | 392.2 MB | 7 | 0 | 1160 |
| tools/ | folder | 2 | 30.1 KB | 2 | 0 | 0 |
| voicetests/ | folder | 14 | 11.1 MB | 0 | 0 | 14 |

## The big data folders, summed

| folder | files | size | tracked | untracked | ignored |
|---|---|---|---|---|---|
| runs/ | 0 | 0 B | 0 | 0 | 0 |
| exports/ | 0 | 0 B | 0 | 0 | 0 |
| logs/ | 21 | 228.8 KB | 0 | 0 | 21 |
| library/voice/ | 7 | 8.3 MB | 1 | 0 | 6 |
| styles/*/refs/ | 9 | 33.2 MB | 0 | 0 | 9 |
| styles/*/analysis/ | 915 | 250.9 MB | 0 | 0 | 915 |
| styles/sfx/ audio | 224 | 107.9 MB | 0 | 0 | 224 |
| render outputs | 6 | 33.9 MB | 0 | 0 | 6 |
| motion-lib/.harness and .hyperframes (caches) | 5254 | 64.7 MB | 0 | 0 | 5254 |

Per styles/sfx, library/voice, styles/*/refs and styles/*/analysis folder:

| folder | files | size |
|---|---|---|
| golden/ | 82 | 40.4 MB |
| library/voice/ | 7 | 8.3 MB |
| styles/paper-cards/analysis/ | 915 | 250.9 MB |
| styles/paper-cards/refs/ | 9 | 33.2 MB |
| styles/sfx/ | 239 | 108.1 MB |

## What the walk found

- Symlinks: 0
- Paths longer than 200 characters (absolute): 0
- Unreadable files: 0

