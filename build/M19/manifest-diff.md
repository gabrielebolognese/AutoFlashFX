# Manifest difference: M17 plan to the manifest written right before the moves

Plan: `build/M17/move-manifest.tsv`. Executed: `build/M19/move-manifest.tsv`.

0 line(s) of M19 only in the plan, 0 only now, 0 with other counts.

## Why

The video runner, the tests and the build itself keep writing files (runs, logs, caches) between the plan and the move, and the fresh manifest covers whatever is there. The rules are the same (BUILD_SPEC.md 14.13).
