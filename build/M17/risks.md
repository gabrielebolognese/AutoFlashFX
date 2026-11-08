# Risks of the moves (M17)

Written by `python pipeline/tests/risk-scan.py`. BLOCKER: the moves must not start while it is true. NOTE: to know, or covered by the move's own checks.

## BLOCKERs (1)

- **BLOCKER Uncommitted changes outside build/ and pipeline/tests/**: 2: M motion-lib/gallery/frame-match.json; M motion-lib/gallery/frame-match.md. M18 refuses to start while git has uncommitted changes outside its own files; it first commits the two runner-written files as a snapshot, and test output such as motion-lib/gallery/frame-match.json must be committed or restored by the build before then (M17 does not touch motion-lib).

## NOTEs (18)

- **NOTE No video runner is alive**: not running (no .locks/runner/pid). It must stay stopped from M18 on until the migration is verified (build/HUMAN_TODO.md).
- **NOTE No unfinished runs**: runs/ has 0 run folder(s) and none is unfinished (runs/ does not exist yet).
- **NOTE No exports yet**: exports/ is absent or empty: the manifest has no M19 line today. M19 writes the manifest again first, so exports made before then are renamed (the rules and the fixture test cover them).
- **NOTE No runs/ folder**: runs/ does not exist: the manifest has no run lines and no run rewrites today; the rules (and test-m17's fixture folder, which has runs and exports) cover them.
- **NOTE Runner-written tracked files**: library/.hooks.stats.json, library/hooks.suggested.txt change on every real run: M18 commits them as they are (chore: snapshot runner-written files before the move) before migrating.
- **NOTE Other local branches**: important-ideas. The branch important-ideas (the user's model change: Sonnet as the main model, fable only for [important] ideas) waits to be merged into main at the M18 pause; merge it before M18 starts, on a clean tree, then renumber DECISIONS 323 to 325 if the numbers are taken. It adds pipeline/tests/test-models.sh, which run-fake.sh picks up once the file exists.
- **NOTE Processes that may hold files open**: running now: chrome.exe x16, claude.exe x4, node.exe x9, python.exe x5. A process with a file open in a moved folder (a render, a browser harness, an editor) makes a rename fail; migrate-channels retries as the runner's moves do and undoes itself when a rename still fails. Close editors and browsers that have motion-lib/, styles/ or golden/ open.
- **NOTE OneDrive syncs this folder**: the path is under OneDrive. 0 file(s) are online-only (not on this disk): none. OneDrive may hold a handle on a file it is uploading, so a rename can fail for a moment; the migration retries, and the whole move is one rename per folder. Files that are online-only are downloaded by a copy but not by a rename.
- **NOTE Old paths inside ignored data**: 226 occurrences in 8 (bucket, form) groups: golden json-backslash 2; library relative 2; logs mixed 7; logs relative 48; motion-lib json-backslash 55; motion-lib mixed 91; motion-lib relative 6; styles relative 15. Run files, captions files and history lines are rewritten by M18 (14.13); old paths in the ignored caches of motion-lib/.harness and .hyperframes and in golden/*/project/.hyperframes name the folder's own absolute path and are rebuilt by the tools that wrote them (a stale cache is not a correctness problem, a stale <base href> in a harness page is). Details: refindex-data.tsv.
- **NOTE Absolute old paths inside tracked data**: 2 (path, form) group(s), 41 occurrences, for example motion-lib/webgl.json:52: "frame": "C:\\Users\\there\\OneDrive\\Desktop\\instagramReels\\motion-lib\\.harness\\webgl. After the move these name a folder that no longer exists (motion-lib/gallery/play/*.html carry a <base href> to motion-lib/): M18 rewrites them where a test or a tool reads them, or the gallery tool rewrites them (python pipeline/lib/motion gallery), and lists each one in its report.
- **NOTE Size of M18's code work (refindex)**: 2207 occurrences in 245 files. Paths built in code (kind code): 195; export names in code: 11; direct reads of config.json: 29; tests: 882; docs and prompts: 279. Details: refindex.tsv, counts per kind in report.md.
- **NOTE Path lengths**: the longest path now is 143 characters; after the move the new prefix adds 17, so none passes 200 today. Runs and exports added later have longer names (a run folder is <date>_<slug>): checked again when M18 writes the manifest.
- **NOTE Symlinks**: none in the walked folders (node_modules is not walked and is engine)
- **NOTE The manifest places every file**: 6737 files are covered by 11 top lines, 12762 are engine, 19499 in the inventory
- **NOTE Disk space**: 133.0 GB free (M18 needs 2 GB; the moves are renames and add no data; the rehearsal fixture and the test copies take under 1 GB).
- **NOTE .gitignore rules to rewrite**: 34 rule(s) name the old folders and must become channels/*/... rules, committed before the first move (14.3): motion-lib/.harness/; motion-lib/renders/; golden/*/project/renders/; /runs/; /exports/; /logs/; /.locks/; library/voice/*; !library/voice/README.txt; library/.hooks.index.json
- **NOTE The curated hooks file**: pipeline/tests/no_emdash.py skips library/hooks.txt by path (the user's file with its dashes): M18 changes the skip path to channels/*/library/hooks.txt and never edits the hooks file to make a test pass.
- **NOTE The folder voicetests/**: 14 untracked files (the user's voice experiments) stay at the root on purpose: a stays line, not channel data.
