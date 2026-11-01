# M8 review 1: Sound effects memory map

Verdict: APPROVED

## Acceptance test

`bash pipeline/tests/test-m8.sh`: 164 passed, 0 failed, exit 0 (about 90 s, no model call; full log in
build/M8/review-1-test.log).

- Section 1, the synthetic ffmpeg pack: the 0.3 s noise swoosh comes out fast and the 1.6 s swell slow, the clipped
  pop is excluded with its reason, the fake .mp3 is a decode error, a ban drops the file and survives another
  rebuild, a pin puts the file first, an unchanged folder is not measured again and makes no model call, and a
  failed indexer call exits 1.
- Section 2, the committed map of styles/sfx/: all 106 files are either mapped (93) or excluded with a reason (13),
  every measured field is present, no pool has more than 8 files, typing and negative are short and named in
  build/HUMAN_TODO.md, the previews and their .txt listings exist for all 12 cue types, and a rebuild is a no-op.
- `bash pipeline/bin/build-sfx-map --check` on its own: up to date, rc 0.

## Required fixes

None.

## What later milestones need from M8 (checked)

- M11: `pipeline/bin/build-sfx-map` (a no-op when nothing changed, exit 1 when the indexer call fails),
  `styles/sfx/sfx-map.json` with `pools`, `short_pools`, `cache`, `gain_db`, `onset_s` and `peak_s`, and the
  contract in pipeline/stages/11-sfx/CONTRACT.md. All present.
- config.json: `sfx.build` is in place, and the map is a warn-level preflight entry, so the runner keeps going
  without it.
- Earlier features: M8 changed only the banner regex in test-m1.sh and test-m2.sh (it now also accepts
  "sfx map: N files"). That is consistent with the banner now reporting the map, and no other earlier code changed.

## Suggestions (not blocking)

1. PLAN.md asks for a "base gain per cue type" in config `sfx`. M8 normalizes every file to a -12 dBFS peak and
   leaves the per-cue level to S11 (`min_db_under_voice`). If M11 wants per-cue offsets, add them there.
2. Every pool comes from name rules plus measurements, and nobody has listened to it yet. The HUMAN_TODO entry to
   listen to the previews covers this. Until the user pins files, M11 should expect short pools (typing,
   negative) and plan to rotate within them.
3. The folder hash uses paths, sizes and dates. A file replaced with the same size and timestamp (rare) would not
   be measured again. `--force` covers this; mentioning it in SFX-MAP.md's usage notes would help.
