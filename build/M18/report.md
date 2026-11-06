# M18 Channels: report

FlashFX's data now lives in `channels/flashfx/`, every path to channel data goes through one module, and the runner starts with
`bash run.sh --channel flashfx`. The real migration ran on this folder and verified (7,259 files in the listing, checksums, only renames in git
status, `git check-ignore` at every new path, check-manifest `--after` passes). Nothing of yours was edited, only moved.

## What I built

| piece | files |
|---|---|
| the paths module | `pipeline/lib/paths.sh`, `paths.py` (same answers, compared by a test; refuse another channel's folder or export folder with exit 3; `REELS_PATH_TRACE`) |
| channel.json and the config merge | `pipeline/schemas/channel.schema.json`, `pipeline/lib/config.py` (resolve, validate, overrides, set-channel), `common.sh` (`reels_config_refresh`, `reels_set_channel`), `config.sh` (`cfg` follows edits at once, `cfg_channel_enabled`), `channels/flashfx/channel.json` |
| config.json | style, voice, sfx, lengths and the 14 channel paths moved to channel.json (values unchanged); review safety keys now per channel: `protected_paths` = `channels/*/ideas.txt`, `channels/*/library`, `channels/*/styles`, `exports`; `fixer_paths` = `pipeline`, `channels/{channel}/motion-lib/candidates`; preflight entries use `in_channel` and `{channel}` |
| every path through the module | about 45 `cfg paths.*` places (`chcfg`), the bin tools (`reels_require_channel`), `ideas.py`, `export.py`, `protect.py` (walks every channel), `screenshot.py`, `voiceover.py`, `mixsfx.py`, `motion/common.py`, `visual/common.py`, `caption.py`, `review.sh`, `ai.sh` (protected rules, not globbed), `preflight.sh`, `history.sh`, `status.sh`, `stage.sh`, `visual.sh`, `tools/voice.py` |
| the runner | `run.sh --channel`, `--allow-disabled`, `REELS_CHANNEL`; per-channel locks, logs, history, status (they were already behind `REELS_LOCKS` and `REELS_LOGS`, which now sit in the channel folder); the numbering lock of `exports/` is global until M19 |
| the tools | `add-idea.sh --channel`, `preflight --channel`, `runner-status` (a block per channel, the global locks), `doctor` (the engine once, then every channel, the engine keys a channel overrides) |
| the move | `pipeline/bin/migrate-channels`, `pipeline/lib/migrate.py` (dry run, rehearsal, undo script, state-driven undo, kill recovery, verification), the new `.gitignore` |
| tests | `pipeline/tests/test-m18.sh`, `test-isolation.sh` (part 1), `isolation_scan.py`, `isolation-allowlist.txt`; `run-fake.sh` lists both |
| docs | CLAUDE.md (folder map, channels section, rules), DECISIONS.md 344 to 354, build/progress.md, HUMAN_TODO |

## The real migration (build/M18/)

`dry-run.txt` (the dry run), `move-manifest.tsv` (the manifest written right before the moves; check-manifest passed), `manifest-diff.md` (4 lines with other
counts than the M17 plan: files that tests and runs wrote since), `migration-run.txt`, `migration-log.tsv` (ends `verified`), `undo-migration.sh`,
`before-listing.tsv`. Order: the code, the new `.gitignore` (channels rules plus a block of the legacy root rules, so git status stayed clean and every
file stayed ignored) and `channel.json` were committed; then the 11 manifest lines ran (ideas.txt, library, styles, motion-lib, golden by `git mv`; five
logs items by rename; voicetests stays); then the legacy block was deleted and the renames committed. The runner-written tracked files
(`.hooks.stats.json`, `hooks.suggested.txt`) had no changes, so the snapshot commit was not needed. The uncommitted `frame-match` files (the one BLOCKER of
risks.md) were restored with `git checkout`. After the move: `preflight --channel flashfx` passes (8 tools, 2 packages, 9 files), `doctor --quick` has 0
problems and 0 warnings. The 39 gallery players and `webgl.json` held the repository's old absolute path; I replaced it by text (see HUMAN_TODO).

## Test edits (the allowed kinds: the channel argument, channel paths, the no_emdash skip path)

- `pipeline/tests/lib.sh`: `sandbox_init` builds `channels/flashfx/` (SANDBOX_CH, SANDBOX_CH_M, `REELS_CHANNEL`, a copy of channel.json, the style files, tokens.json,
  sfx-map.json, catalog.json and the brand kit that the preflight reads from the channel now), SANDBOX_WPM pins channel.json, new `resolved_config`.
- Mechanical: `$SANDBOX/`, `$SANDBOX_M/` and `$REPO_DIR/` plus library, styles, motion-lib, golden, runs, logs, ideas.txt, .locks became `.../channels/flashfx/...`
  (391 places: m13-run.sh 7, m1 40, m10 7, m11 13, m12 38, m13 16, m14 8, m15 1, m16 6, m2 62, m3 68, m4 38, m5 46, m6 11, m7 17, m8 4, m9 9).
- By hand: test-m1 and test-m7 `--root` is the channel folder; test-m3 (the protected-file denials name `channels/*/...`, the protect.py keys and git path);
  test-m5 (the set-wpm test copies channel.json); test-m6, m7, m11, m12 (`--config` gets the resolved config); test-m17 section 4 (the check of M17's own
  commits is pinned to e3e1bef..89fda33, and after the move the recorded manifest is checked with M18's `--after`); `no_emdash.py` skips
  `channels/*/library/hooks.txt` (a glob); `manifestlib.py` ENGINE_TOP gained `channels`.

## How to run the test

`bash pipeline/tests/test-m18.sh` (about 25 minutes; `M18_SECTIONS="1 2 6"` for some), `bash pipeline/tests/test-isolation.sh`, and the baseline rule:
`bash pipeline/tests/run-fake.sh --out build/M18/baseline --compare build/M17/baseline` (about 7 hours).

## Test results

RESULTS_PLACEHOLDER

## Known gaps

- Export names and numbering per channel are M19's (`exports/N/` as before); `format.json` and the FlashFX names in shared stages are M20's.
- Part 2 of test-isolation (the canary test) is M19's; `new-channel` is M19's.
- `limits.log` is still per channel (the shared limit file is M19).
- BUILD_SPEC.md and PLAN.md still say `library/`, `styles/` and so on in sections 1 to 13: section 14 says to read them inside `channels/<id>/`.

## HUMAN_TODO items added

Start the runner with `bash run.sh --channel flashfx`; your files moved (nothing edited); the gallery players and webgl.json were repointed by text.
