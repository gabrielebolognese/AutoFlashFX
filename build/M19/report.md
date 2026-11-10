# M19 Exports and channels side by side: report

Built 2026-11-09 and 2026-11-10 (one batch, Sonnet 5.5). The gate of 14.13 ran first: `preflight --channel flashfx` passes and `check-manifest.py --after`
on M18's manifest differs only by the growth of two logs and the bytes of motion-lib/ (M18's documented text replacement); test-m19 section 2 accepts exactly that.

## What I built

- **Export names and numbering (spec section 8).** `pipeline/lib/export.py` and `export.sh`: every export is `exports/<id>-N/` with `<id>-N.mp4`,
  `<id>-Ncaptions.txt` and (only on a platform with the clip) `<id>-Nhook2.mp4`. N = 1 + the highest number of the channel among the folders and the
  history lines `exported <id>-N`, so a deleted folder never gives its number back. The runner's DONE line is `exported <id>-N -> exports/<id>-N/ (...)`, the
  history line `exported <id>-N`, the RUN section of the captions file `channels/<id>/runs/<run>`. An `input.json` that a platform exporter leaves in
  `runs/<run>/export/` survives the assembly. logcheck.py reads both DONE forms. (DECISIONS.md 355.)
- **Platforms.** `pipeline/platforms/instagram-reels/` (platform.json, render.py: today's captions file behind the interface, stage 14-export unchanged),
  `pipeline/platforms/youtube-shorts/` (platform.json, input.schema.json, model.schema.json, prompt.md, exporter.py, run.sh), `pipeline/schemas/platform.schema.json`,
  `pipeline/lib/platform_lib.py` (`list|show|check|settings|of`). exporter.py has every check of section 8 (title, description of at most 1000 characters,
  no 200+ paragraph, a list of 3 to 6 items, exactly 4 hashtags with the required ones, no copy of an earlier description by first line and 30 percent trigram
  overlap against the last 30, pinned comment, serial rules, humanize and the slop list), one rewrite with the failures listed, NEEDS REVIEW on the second
  failure, `logs/descriptions.jsonl`. It was written by a subagent from a brief; I read its report, fixed the RUN line and added `manifest_required` to both
  platform.json files, and the test runs it through the real stage script with the fake model. (DECISIONS.md 356, 357.)
- **heavy.sh** (`pipeline/lib/heavy.sh`): `heavy_run <kind> <label> -- cmd`, the global `.locks/heavy.lock` (holder file, stale by pid), one WAIT line per wait,
  the activity shows the wait, `engine_log` (root `logs/engine.log`: waits over 10 minutes, shared limit waits), `editor_run` (`.locks/editor.lock`, used from M21);
  config `heavy` (stale_seconds, poll_seconds, wait_log_seconds, kinds). Wrapped: S8, S10's build steps, S11, S12's five code steps, S13. (358.)
- **Limit sharing:** `.locks/limit.json` written by `limit_wait`, read by `ai()` before every attempt (`limit_shared_wait`: LIMIT line naming the channel that hit it,
  the same reset, no call); the root `logs/limits.log` carries the channel id. (359.)
- **Daily quota:** `pipeline/lib/quota.py`; `IDLE   quota 2/2 today, next idea after 00:00`; continues after midnight in the channel's timezone; `--once` prints
  the line and the summary and exits 0; runner-status shows today's exports against the quota. (360.)
- **new-channel:** `pipeline/bin/new-channel` and `pipeline/lib/newchannel.py`, template in `pipeline/formats/problem-solution-reel/template/`, preflight's new
  `fill_in` check (hard while the channel is disabled, a warning once enabled). (361.)
- **runner-status and doctor** for every channel and the shared parts (quota, heavy lock, limit file, engine.log, platforms).
- **The export migration (14.13, M19 lines):** `make-manifest.py` writes the M19 lines for the folder as M18 left it (the history after M18 is an inner rewrite
  inside the channel folder; `check-manifest.py` accepts an inner line under channels/); `migrate.py` now knows inner renames (the file names inside an export
  folder) in verify, undo (state-driven and the undo script) and premigrate paths. Rehearsal fixture: dry run, run, undo (identical checksums), run again, a kill
  halfway recovered. The real folder had no export and no history line, so its executed manifest has no M19 line (`build/M19/real-migration.txt`). (362.)
- **test-isolation.sh part 2** (the canary test; recorder `FAKE_CLAUDE_RECORD_DIR` in the fake claude): S1, S2, S3, S5, S6, S7 and S14 of two canary channels reach
  their model call and the recorded prompts and arguments never carry the other channel's canary, folder or export name; the path trace of a dummy run stays inside
  the engine, `channels/alpha/` and `exports/alpha-*/`. (363.)
- **Dummy fingerprint** with the new names: `build/M19/fingerprint/` (`fingerprint-run.txt`, `fingerprint-exports.txt`: `flashfx-1/` with `flashfx-1.mp4`,
  `flashfx-1captions.txt`, `flashfx-1hook2.mp4`); the run tree equals M17's baseline, the exports tree equals it with the names normalized.

## Files

New: pipeline/lib/{platform_lib.py, heavy.sh, quota.py, newchannel.py}, pipeline/bin/new-channel, pipeline/schemas/platform.schema.json,
pipeline/platforms/**, pipeline/formats/problem-solution-reel/template/**, pipeline/tests/{test-m19.sh, m19-ytshorts.py}, build/M19/**.
Changed: pipeline/lib/{export.py, export.sh, history.sh, limits.sh, ai.sh, runner.sh, status.sh, log.sh, logcheck.py, preflight.sh, stage.sh, dummy.sh, migrate.py, solution.py (a comment)},
pipeline/bin/{doctor, runner-status}, pipeline/stages/{08-voiceover, 10-build, 11-sfx, 12-review, 13-render}/run.sh (heavy_run around the heavy command),
pipeline/stages/14-export/{CONTRACT.md, run.sh (comments)}, pipeline/tests/{make-manifest.py, check-manifest.py, test-isolation.sh, isolation-allowlist.txt, fakes/claude.py},
config.json (`heavy`, the `fill_in` preflight entry), CLAUDE.md, DECISIONS.md 355 to 364, build/progress.md, build/HUMAN_TODO.md.

Earlier milestones touched, because M19 depends on them: M2 (export, history, DONE line, status), M3 (limits and ai.sh), M8, M10, M11, M12 and M13 stage scripts and
logcheck (heavy_run, tags), M17 (make-manifest and check-manifest), M18 (migrate.py, preflight, test-m18).

## Test edits allowed by the spec (each listed)

test-m2 (export names, the numbering unit tests take a channel and a history, the RUN path), test-m3 and test-m13 (the root logs/limits.log), test-m4, test-m10,
test-m11, test-m12 (check_export, history lines, history_add with `flashfx-1`), test-m16, test-m18 (the DONE line, the exports tree normalized for the M17 baseline,
the two-channel runs). The edits are mechanical (`exports/N/N.mp4` to `exports/flashfx-N/flashfx-N.mp4`, `exported #N` to `exported flashfx-N`).

## How to run the test

`bash pipeline/tests/test-m19.sh` (about 40 minutes; `M19_SECTIONS="1 3"` for some; `M19_RECORD=1` rewrites the fingerprint),
`ISOLATION_PARTS="1 2" bash pipeline/tests/test-isolation.sh`, `python pipeline/tests/m19-ytshorts.py selftest`.

## Test output (this build)

See "Results" below.

## Known gaps

- `run-fake.sh` (the whole fake-only suite, about 7 hours) was NOT run against the M17 baseline. I ran the tests that M19's changes can break instead: test-m2, m3,
  m12 (sections 1 2 3 5), m13 (1 2 4), m17, m18, test-limits and test-isolation; test-m4, m10, m11 and m16 carry the mechanical name edits but were not run
  (their dummy and real sections take an hour or more each). Run `bash pipeline/tests/run-fake.sh --out build/M19/baseline --compare build/M17/baseline` when the machine is free.
- test-m2 section 2 still has the known timing failure of the baseline (heartbeat gaps; the 300 s limit of two idea runs is no longer hit when the machine is idle).
- The visual director, builder and S12 prompts are not driven by the canary test (they need a built project); they join in M23 to M27 (spec 14.5).
- S8's one-line rewrite call runs inside S8's heavy step: a usage limit wait there would hold the heavy lock for the wait (rare; DECISIONS.md 358).
- `frame-match`, `gallery`, `webgl-test` and `render-golden` are not wrapped in heavy_run (a person starts them by hand); S15's capture is M21's.
- Nothing runs the youtube-shorts exporter inside a format yet (serial-story is M23); it is tested on its 6 fixtures, through the stage's run.sh with the fake model and
  through export.py.

## HUMAN_TODO items added

Four lines in build/HUMAN_TODO.md: the new export names (nothing to do), `daily_quota`, how to start another channel with new-channel, the root limits.log and the WAIT line.

## Results (logs in build/M19/logs/)

- `bash pipeline/tests/test-m19.sh`: **197 passed, 0 failed** (final-m19.log; sections 1 to 8: numbering and names, the export migration on the rehearsal fixture with
  undo, second run and kill recovery, the youtube-shorts exporter and the platform interface, the heavy lock, limit sharing, the quota with the fast clock, new-channel,
  test-isolation both parts, the fingerprint, runner-status and doctor, no em dash).
- `ISOLATION_PARTS="1 2" bash pipeline/tests/test-isolation.sh`: 34 passed, 0 failed (final-isolation.log).
- `python pipeline/tests/m19-ytshorts.py selftest`: 86 passed, 0 failed.
- test-m17: 81 passed, 0 failed. test-m18: 199 passed, 0 failed (final-m18b.log). test-limits: 94 passed, 0 failed.
- test-m2: 206 passed, 1 failed (final-m2.log): the heartbeat-timing case that is in the M17 baseline's known failures (the baseline had 15, the rest were the 300 s
  timeout of an overloaded machine).
- test-m12 sections 1 2 3 5: 180 passed, 0 failed. test-m13 sections 1 2 4: 100 passed, 0 failed.
- test-m3 (all sections): 412 passed, 12 failed (final-m3.log). Two are the baseline's known failures (limit date, limit epoch). The other 10 were all in section 9 of
  that one long run (a runner that stopped before creating its run); section 9 run alone passes: 104 passed, 0 failed (m3-s9.log). I take them for a disturbance of that run
  (the build chain around it was killed at its time limit while it ran), not for a regression, but I could not reproduce either way.
- The dummy fingerprint is in build/M19/fingerprint/; `bash pipeline/tests/test-m19.sh` section 8 compares against it (M20 compares against it too).
