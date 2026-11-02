# M13 Hardening: review 1

Verdict: APPROVED

## What was checked

- PLAN.md M13 (scope and acceptance test), build/M13/report.md, the commits dad04f0..f3a6816, and the diffs of the
  shared code M13 touched: pipeline/lib/log.sh (say() with the status rename, reels_log_rotate), status.sh (the
  rotation check in runner_tick), runner.sh (the rotation at startup), ai.sh (ai_fault returns at once when
  REELS_FAULT is unset, so normal runs make the same call as before).
- The acceptance test `bash pipeline/tests/test-m13.sh`, run this way:
  - `M13_SECTIONS="1 2 4"` (fake-only: units, three ideas with the fake claude including the simulated limit, the
    kill, the restart and the story, no em dash): **100 passed, 0 failed** (build/M13/review1-test-s124.log).
  - `M13_REAL_DIR=build/M13/real2 M13_SECTIONS=3` (section 3's checks over the real three-idea run the build made:
    LIMIT with its reset time, limits.log target, RESUME in the same session, the resume after the kill at the same
    stage, the heartbeat counters, exports without gaps, history, 503 status samples all valid, IDLE, the stop line,
    the summary, no em dash): **33 passed, 0 failed** (build/M13/review1-test-s3.log).
  - I did not start a new multi-hour real run: the real run is on record and its checks pass again.

## Required fixes

None.

## Suggestions

1. The real2 run predates decisions 286 and 287 (the S7 stem check, S8's spelling tolerances). The single-idea reruns
   cover them only up to S8 for the ffmpeg idea. One more real three-idea run (`bash pipeline/tests/m13-run.sh real
   build/M13/real3`, detached) would show the export count rising with these fixes in place.
2. The 50 MB rotation is only tested with a 6 KB limit. That is fine, but `stat -c %s` runs once a minute for as long
   as the runner lives. That costs little, and nothing else needs to change.
3. In say(), a failed rename falls back to a direct write, which can briefly leave status.txt empty again (the case
   the rename was added to avoid). That only happens when another program holds the file open, so it is acceptable.
   A log line on the fallback would make it visible.
4. The report's known gap still applies: whisper mishears lowercase command names ("init"), and the hotwords only
   cover capitalized names. This is worth a look in M14 or later if real ideas keep getting blocked at S8.
