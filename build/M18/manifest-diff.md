# Manifest difference: M17 plan to the manifest written right before the moves

Plan: `build/M17/move-manifest.tsv`. Executed: `build/M18/move-manifest.tsv`.

0 line(s) of M18 only in the plan, 0 only now, 4 with other counts.

## Same line, other counts

- `library`: plan 43 files 10757022 bytes, now 43 files 10755778 bytes
- `styles`: plan 1167 files 411262003 bytes, now 1167 files 414231425 bytes
- `motion-lib`: plan 5409 files 83493465 bytes, now 5409 files 83493617 bytes
- `logs/index-hooks`: plan 9 files 38458 bytes, now 13 files 38753 bytes

## Why

The video runner, the tests and the build itself keep writing files (runs, logs, caches) between the plan and the move, and the fresh manifest covers whatever is there. The rules are the same (BUILD_SPEC.md 14.13).
