# M8 report: Sound effects memory map

Built 2026-11-01 in one build batch. Spec: BUILD_SPEC.md 2.6 and section 12 (M8); plan: PLAN.md M8; decisions:
DECISIONS.md 178 to 191.

## What was built

- **`bash pipeline/bin/build-sfx-map`** builds the map of styles/sfx/ in four Python steps (pipeline/lib/sfx/sfxmap.py:
  plan, measure, classify-plan, build) with the one indexer call made by bash through ai() between the last two
  (the same split as M7: Python works, bash relays and calls the model). Options: `--check` (is the map current),
  `--force` (measure everything again), `--reclassify` (ask the model again), `--no-model` (unclear files wait for
  the next run with the model), `--quiet`, `--dir DIR` (another pack, used by the test). Exit 0 up to date or
  rebuilt, 1 when the indexer call failed (a code error for the stage that called it), 2 for a missing pack or a
  failed step.
- **Measurements** (measure.py, ffmpeg plus numpy, nothing installed): per file the codec, channels, sample rate and
  bit depth from ffprobe; the first audio stream decoded to 48 kHz float in memory; the sample peak, the full-scale
  runs (clipping), the 5 ms RMS envelope giving the onset, the loudest moment, the attack, the tail to 40 dB under,
  the end, the effective duration and the silence padding at both ends; the noise floor from the lead-in and the
  last 50 ms (unknown when the sound fills the file); the spectral centroid; the integrated LUFS and the true peak
  from one ebur128 pass with 2 s of padding so short sounds measure too. 106 files in 8 to 12 s with 4 threads.
- **Classification** (classify.py): name rules first (digits split from letters, so "Swoosh01" is a swoosh), nine
  categories, each mapped to ranked cue type candidates; whooshes classed fast, medium or slow from the effective
  duration and the attack with thresholds tuned on this pack (DECISIONS.md 181). Files with no rule word, or whose
  measurements contradict the name, go to the indexer model in one batched call (pipeline/stages/_prompts/
  classify-sfx.md with its schema): 0 to 3 cue types best first, tags, a confidence and a note per file, cached in
  the map while the file is unchanged. Confidence under 0.6 means waiting for the user's pin. Files a measurement
  already excludes are never asked about.
- **Normalization and cache:** gain = -12 dBFS minus the sample peak; the 48 kHz 16-bit copy with the file's channel
  count under styles/sfx/.cache/<id>-<slug>.wav, same timeline as the original. The originals never change.
- **Quality filter** (pools.py): clipped (10 or more runs of 3 full-scale samples), high noise floor (within 30 dB of
  the peak, files of 0.5 s or longer), silent, undecodable, far too long (over 5 s of sound, typing excepted, or over
  twice a cue type's window), and "no cue type fits" from the model. Every exclusion carries its reason.
- **Pools:** fit = category fit x duration window fit x attack fit x quality x confidence; each pool keeps the files
  with fit 0.25 or more, best first, pinned first, at most 8; fewer than 3 is short.
- **overrides.txt** (overrides.py): `ban: <path>` and `pin: <cue type>: <path>`, created once with a header that
  explains them and never rewritten; a pin goes first, approves a waiting file and overrides every exclusion but a
  decode error; unknown lines are reported, never fatal.
- **Previews** (previews.py): styles/sfx/previews/<cue type>.wav, the pool's sounds trimmed to their audible part and
  spaced 1 s apart, with a .txt listing each sound and when it starts.
- **Outputs** (writemap.py): styles/sfx/sfx-map.json (every measurement, classification, fit, model answer,
  exclusion, ban and pin per file; the pools; excluded; waiting; unclassified; overrides; settings; counts) and
  SFX-MAP.md (how to use it, the pools as tables, short pools, the waiting list with the model's guesses, excluded
  files with reasons, overrides in force, counts per category, the thresholds).
- **Rebuilds:** the plan compares the folder hash (paths, sizes, dates), the hash of overrides.txt's effective lines
  and the settings hash (config sfx.build, the map, measurement and rules versions); unchanged means nothing is
  done and no model is called. A changed folder measures only the new and changed files; an overrides or settings
  change redoes pools, map, report and previews from the cached numbers in about a second. Missing cache copies or
  previews are regenerated.
- **config.json:** `sfx.build` (pool_size 5 to 8, min_pool 3, min_confidence 0.6, min_fit 0.25, preview_gap_s 1, the
  whoosh thresholds, the quality thresholds, the duration window per cue type) and a warn-level preflight entry for
  the map (the runner continues; S11 flags a reel without a map, as the spec's S11 says).
- **The map of this pack:** 106 audio files, 93 mapped, 13 excluded (4 clipped masters, 6 far too long, 2 risers and
  the drum roll that fit nothing, the noisy 16 s rewind), 12 waiting for a pin, 27 classified by one haiku call
  (about 20 s), 59 by rules. Pools: transition_slow 8, transition_fast 8, attention 8, hero_enter 8, ui_click 8,
  number 8, hook_hit 8, stamp 4, notification 4, success 3, typing 2 (short), negative 2 (short).

## Files

- New: pipeline/bin/build-sfx-map; pipeline/lib/sfx/{common.py, measure.py, classify.py, overrides.py, pools.py,
  previews.py, writemap.py, sfxmap.py, map.schema.json}; pipeline/stages/_prompts/classify-sfx.md and
  classify-sfx.schema.json; styles/sfx/sfx-map.json, styles/sfx/SFX-MAP.md, styles/sfx/overrides.txt (tracked);
  styles/sfx/previews/ and styles/sfx/.cache/ (ignored); pipeline/tests/test-m8.sh; build/M8/report.md.
- Changed: config.json (sfx.build, the preflight entry), pipeline/stages/11-sfx/CONTRACT.md (the map's contract for
  M11), pipeline/tests/test-m1.sh and test-m2.sh (the banner accepts "sfx map: N files"), DECISIONS.md,
  build/progress.md, build/HUMAN_TODO.md, CLAUDE.md.

## How to run the test

```
bash pipeline/tests/test-m8.sh                   # everything, about 90 seconds, no model call
M8_SECTIONS="1" bash pipeline/tests/test-m8.sh   # the synthetic pack only (or "2": the committed map only)
bash pipeline/bin/build-sfx-map --check          # is the committed map current for styles/sfx/ on this PC
bash pipeline/bin/build-sfx-map                  # rebuild (a no-op when nothing changed)
```

## Test output, in short

`bash pipeline/tests/test-m8.sh`: `test-m8.sh: 164 passed, 0 failed` in 1 min 22 s.

- Section 1 (a synthetic pack of 13 ffmpeg-generated sounds plus a text file named .mp3, the fake claude answering
  from fixtures): every file measured on the first build; one batched indexer call plus one more for the id the
  first answer skipped; the 0.3 s noise swoosh is fast, the 1.6 s swell slow; the clipped sine, the silent file and
  the text file excluded with their reasons; the cache copy is 48 kHz with the file's channel count and peaks at
  -12.0 dBFS; gain_db equals -12 minus the peak; the pools hold the clicks, the ding, the model's tone, the boom
  (stamp and hook_hit) and the typing bed; the low-confidence tone waits; previews with their listings; a rebuild
  of the unchanged pack says "up to date", measures nothing, calls nothing and leaves the map byte for byte; a ban
  drops the click and holds through a plain and a forced rebuild (the model's answers survive --force); pins go
  first and approve the waiting file; an unknown line is reported; a new file is measured alone and a removed file
  leaves the map with its cache copy pruned; --check exits 1 after a change and 0 after the rebuild; a failed
  indexer call exits 1; --no-model builds with the file "not classified yet" and the next run with the model asks
  only about it.
- Section 2 (the committed map of styles/sfx/): the 106 files on disk are exactly the map's files, each mapped or
  excluded with a reason; every measured field present; no pool over 8; the two short cue types are named in
  build/HUMAN_TODO.md; previews present with the right counts; `bash pipeline/bin/build-sfx-map` with the fake
  claude in error mode exits 0, makes no call and leaves the committed map as it is; no em dash anywhere.

Regression after the changes to earlier milestones: `bash pipeline/tests/test-m1.sh` 96 passed, 0 failed;
`bash pipeline/tests/test-m2.sh` (the banner assertion) 220 passed, 0 failed; `bash pipeline/tests/test-no-emdash.sh`
1 passed, 0 failed.

## Earlier milestones touched

config.json (M1: `sfx.build` and the preflight entry), the banner assertions of test-m1 and test-m2 (M2: the repo
now carries the map, so the banner reads "sfx map: 106 files" when the real run.sh starts in a sandbox), the 11-sfx
contract (M2). Nothing else was changed.

## Known gaps

- Nobody has heard the picks. The whooshes, clicks and pops rest on name rules plus measurements, the 27 loose files
  on the indexer model's reading of names and numbers. The previews and overrides.txt exist for the user's ears
  (HUMAN_TODO).
- Two pools are short (typing 2, negative 2): the pack has no more such sounds. 12 files wait for a pin, mostly the
  generic "Ui Sound/SFX- Ui02..Ui10" blips the model could not place with confidence.
- Clipping is a heuristic on decoded mp3: a hot bass-heavy master and real clipping look alike (two "SFX- Swoosh"
  files at 0.0 dBFS with 19 full-scale runs went out with the two Air files at 21 and 46). A pin brings any of them
  back.
- The noise floor is unknown for files whose sound fills the file (no lead-in, no quiet end); those are never
  excluded for noise. The LUFS of sounds shorter than 400 ms is low by construction (the gating block includes
  silence); levels use the sample peak as the spec says.
- "Far too long" caps effective sound at 5 s (twice the longest window) for everything but files named as typing.
  Long files with another name are excluded even if the model would have found a use.
- The map's model answers are cached by path, size and date: renaming a file re-asks it (one small call).
- A pack with hundreds of unclear files may leave a few ids unanswered after the two calls of one run; they are
  asked again at the next run (by design, as index-hooks does).
- aif, aiff, ogg and flac are accepted but this pack has only wav and mp3, so those decoders ran only in theory.
- run.sh does not rebuild the map at startup (a start never calls a model); S11 runs `build-sfx-map` at its start
  (M11), and the user runs it after adding sounds. The preflight only warns when the map is missing.
- The cache copies keep the original channel count (stereo for most of this pack); S11 decides whether its stem is
  stereo or downmixed (the map carries `channels` per file).

## HUMAN_TODO items added

- M8: listen to styles/sfx/previews/<cue type>.wav and ban or pin through styles/sfx/overrides.txt.
- M8: typing and negative are short (2 sounds each); drop more such files into styles/sfx/ and rebuild.
- M8: 12 files wait for a pin (the model's confidence was under 0.6); pinning the good ones improves success,
  notification and number.
- M8: 13 files are excluded with a reason in SFX-MAP.md; a pin overrides every reason but a decode error.
