# Role: indexer
# Stage: build-sfx-map

Classify sound effect files for an Instagram reel pipeline (BUILD_SPEC.md 2.6: the sound effects memory map).
Nobody can listen at runtime: the folder name, the file name and a few measurements are all you have. A script
picks sounds from pools per cue type; your job is to say which cue types each file could serve, best first, and
how sure you are.

## Cue types (what the reel needs)

{{CUE_TYPES}}

Typical lengths of effective sound: ui_click, number and hero_enter well under half a second; stamp, success,
negative and notification under two seconds; transition_fast and attention under a second; transition_slow and
hook_hit up to two and a half seconds; typing a few seconds (it is trimmed to the typing on screen).

## The measurements

duration is the whole file; effective is the sound from its onset to the end of its tail (40 dB under the peak);
attack is the time from the onset to the loudest moment (a click or a hit: near zero; a swell: long); brightness
is the spectral centroid (under 800 Hz dark and bassy, 800 to 3000 Hz mid, over 3000 Hz bright and clicky);
peak and loudness are the original file's levels (every file is normalized later, so level does not matter).
"rule guess" is what a name-based rule concluded, or none.

## How to answer

- cue_types: 0 to 3 cue types this file could serve, best first. Empty when it fits nothing (a drum roll, a
  rewind, a 15 second ambience, a riser with no impact).
- tags: 2 to 6 lowercase words that describe the sound as you infer it (for example "page flip paper", "digital
  beep rising", "cash register coins").
- confidence: how sure you are of the first cue type. 0.9 when the name says what it is ("Ding sound effect" for
  success); 0.6 to 0.8 when the name plus the numbers make it likely; under 0.5 when you are guessing (a generic
  "Ui03" with no other clue). Files under 0.6 stay out of the pools until the owner approves them, so do not
  inflate.
- note: one short line of reasoning, under 20 words, no em dashes.

## The files ({{N}})

{{FILES}}

## Your answer

Only this JSON object: {"files": [{"id": "<id as given>", "cue_types": ["<cue type>", ...], "tags": ["..."],
"confidence": 0.0, "note": "..."}]}, one entry per id, every id exactly once, in the order given.
