# 11-sfx: Sound effects (S11)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M11
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S11.

## Purpose
Assign cue types to events.json with the deterministic rules of BUILD_SPEC.md S11 (mandatory cues, slow or fast transitions, hero and ui_click, attention gaps, density and spacing), pick files from the sfx map pools, place and level them, render the stem and the mixed draft, verify accuracy and loudness. No model.

## Inputs
- 10-build/events.json, draft.mp4, 08-voiceover/vo.wav
- styles/sfx/sfx-map.json, config sfx, logs/sfx-usage.json

## Outputs (in runs/<id>/11-sfx/)
- cues.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- cues.json: seed, cues (event, cue_type, file, ms, gain_db), verification
- sfx_stem.wav, draft_mixed.mp4, sound-map.txt (one readable line per sound)
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- every planned sound within 33 ms of its event and no unplanned sound
- the 8 dB rule, -14 LUFS plus or minus 1, true peak at most -1.5 dBTP
- map missing or empty: voice only plus a NEEDS REVIEW flag

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
No model. Script pipeline/bin/mix-sfx.

## The sfx map (M8)
styles/sfx/sfx-map.json is built by `bash pipeline/bin/build-sfx-map` (pipeline/lib/sfx/, BUILD_SPEC.md 2.6): run it
at the start of this stage, like 05-hooks runs index-hooks; it is a no-op when styles/sfx/ and overrides.txt are
unchanged (no measuring, no model call) and exits 1 when its one indexer call fails (a code error for this stage).
Pick from `pools[<cue type>]` (best fit first, pinned files first of all, at most 8): each entry has `path`
(relative to styles/sfx/), `cache` (the normalized 48 kHz 16-bit copy under styles/sfx/.cache/, peak at -12 dBFS,
same timeline as the original), `gain_db` (already applied in the cache copy), `onset_s` and `peak_s` (place a
whoosh by `peak_s`, everything else by `onset_s`), `end_s`, `effective_s`, `pad_start_s` and `pad_end_s`. A pool can
be empty or short (`short_pools`); a missing or empty map means voice only plus a NEEDS REVIEW flag.

## dummy.sh
`bash pipeline/stages/11-sfx/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
