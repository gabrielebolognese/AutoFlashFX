# SFX map: styles/sfx

Built 2026-11-01 15:24 by pipeline/bin/build-sfx-map (map version 1). 106 audio files: 93 mapped (49 in at least one pool), 13 excluded, 12 waiting for your approval, 0 not classified yet. 79 classified by name rules, 27 by the indexer model (haiku) from their names and measurements, no model call in this build.

## How to use it

- Listen: `styles/sfx/previews/<cue type>.wav` plays that pool's sounds 1 second apart, best fit first, in the order of `previews/<cue type>.txt`.
- Ban or pin: a line in `styles/sfx/overrides.txt` (`ban: <path>` or `pin: <cue type>: <path>`), then `bash pipeline/bin/build-sfx-map`. A pin goes first in its pool and approves a file from the waiting list.
- The map rebuilds itself when the folder changes (new, removed or edited files) or overrides.txt changes; an unchanged folder is not re-measured and makes no model call. The sound stage (S11) runs the script before picking sounds.
- Levels: every file has a gain that brings its sample peak to -12 dBFS; the normalized 48 kHz copies live in `styles/sfx/.cache/` (the originals are never modified).

## Pools

### transition_slow (8 sounds)

slow whoosh, for slower transitions (400 ms or longer, or into calm beats).

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Free Woosh/ESE - FIGHT PACK - WHOOSH - SlowMo 03.wav | 2.33 s | 0.32 s | 1.00 | -5.6 dB | rules, slow whoosh |
| 2 | Free Woosh/ESE - FIGHT PACK - WHOOSH - SlowMo 04.wav | 2.18 s | 0.25 s | 1.00 | -4.5 dB | rules, slow whoosh |
| 3 | Free Woosh/ESE - FIGHT PACK - WHOOSH - SlowMo 06.wav | 2.16 s | 0.30 s | 1.00 | -6.0 dB | rules, slow whoosh |
| 4 | SlowWoosh.mp3 | 1.27 s | 0.50 s | 1.00 | -1.7 dB | rules, slow whoosh |
| 5 | Swoosh/SFX- Swoosh01.mp3 | 1.03 s | 0.22 s | 1.00 | -6.0 dB | rules, slow whoosh |
| 6 | Swoosh/SFX- Swoosh03.mp3 | 2.27 s | 0.81 s | 1.00 | -6.0 dB | rules, slow whoosh |
| 7 | Swoosh/SFX- Swoosh09.mp3 | 2.29 s | 0.58 s | 1.00 | -7.0 dB | rules, slow whoosh |
| 8 | Swoosh/SFX- Swoosh10.mp3 | 1.12 s | 0.34 s | 1.00 | -9.4 dB | rules, slow whoosh |

### transition_fast (8 sounds)

fast whoosh, for quick scene swaps.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | rapid woosh.wav | 0.29 s | 0.06 s | 1.00 | -7.4 dB | rules, fast whoosh |
| 2 | Swoosh/SFX- Swoosh05.mp3 | 0.34 s | 0.12 s | 1.00 | -9.2 dB | rules, fast whoosh |
| 3 | Swoosh/SFX- Swoosh15.mp3 | 0.41 s | 0.04 s | 1.00 | -6.7 dB | rules, fast whoosh |
| 4 | Swoosh/SFX- Swoosh16.mp3 | 0.28 s | 0.06 s | 1.00 | -7.3 dB | rules, fast whoosh |
| 5 | Swoosh/SFX- Swoosh18.mp3 | 0.10 s | 0.02 s | 1.00 | -6.8 dB | rules, fast whoosh |
| 6 | Swoosh/SFX- Swoosh19.mp3 | 0.28 s | 0.03 s | 1.00 | -6.5 dB | rules, fast whoosh |
| 7 | Transition Sound Effects/Whip Low Sound Effect ( By Ashish Editz )_01.mp3 | 0.23 s | 0.08 s | 1.00 | -11.5 dB | rules, fast whoosh |
| 8 | Transition Sound Effects/Whip Sound Effect ( By Ashish Editz )_01.mp3 | 0.12 s | 0.06 s | 1.00 | -11.9 dB | rules, fast whoosh |

### attention (8 sounds)

a random fast whoosh on a visual change that has no other sound, to keep attention up.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | rapid woosh.wav | 0.29 s | 0.06 s | 1.00 | -7.4 dB | rules, fast whoosh |
| 2 | Swoosh/SFX- Swoosh05.mp3 | 0.34 s | 0.12 s | 1.00 | -9.2 dB | rules, fast whoosh |
| 3 | Swoosh/SFX- Swoosh15.mp3 | 0.41 s | 0.04 s | 1.00 | -6.7 dB | rules, fast whoosh |
| 4 | Swoosh/SFX- Swoosh16.mp3 | 0.28 s | 0.06 s | 1.00 | -7.3 dB | rules, fast whoosh |
| 5 | Swoosh/SFX- Swoosh18.mp3 | 0.10 s | 0.02 s | 1.00 | -6.8 dB | rules, fast whoosh |
| 6 | Swoosh/SFX- Swoosh19.mp3 | 0.28 s | 0.03 s | 1.00 | -6.5 dB | rules, fast whoosh |
| 7 | Transition Sound Effects/Whip Low Sound Effect ( By Ashish Editz )_01.mp3 | 0.23 s | 0.08 s | 1.00 | -11.5 dB | rules, fast whoosh |
| 8 | Transition Sound Effects/Whip Sound Effect ( By Ashish Editz )_01.mp3 | 0.12 s | 0.06 s | 1.00 | -11.9 dB | rules, fast whoosh |

### hero_enter (8 sounds)

soft pop or click, only for hero cards and giant numbers.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Pop/Pop sound effect.mp3 | 0.20 s | 0.01 s | 1.00 | -8.5 dB | rules |
| 2 | Pop/pop-1.mp3 | 0.21 s | 0.03 s | 1.00 | -8.5 dB | rules |
| 3 | Pop/pop-2.mp3 | 0.17 s | 0.01 s | 1.00 | 1.4 dB | rules |
| 4 | Pop/pop-3.mp3 | 0.11 s | 0.01 s | 1.00 | 0.2 dB | rules |
| 5 | Pop/pop-4.mp3 | 0.23 s | 0.02 s | 1.00 | -9.7 dB | rules |
| 6 | Pop/pop-5.mp3 | 0.14 s | 0.01 s | 1.00 | -11.7 dB | rules |
| 7 | Pop/pop-6.mp3 | 0.20 s | 0.01 s | 1.00 | -7.1 dB | rules |
| 8 | Pop/pop.mp3 | 0.18 s | 0.04 s | 0.80 | -4.1 dB | rules |

### ui_click (8 sounds)

a small UI click for chips, toggles and highlights changing state.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Click/Click - Sound Effect (HD).mp3 | 0.17 s | 0.00 s | 1.00 | -9.4 dB | rules |
| 2 | Click/Mouse Click - Sound Effect (HD) (1).mp3 | 0.14 s | 0.03 s | 1.00 | -8.4 dB | rules |
| 3 | mouse-click-290204 (1).mp3 | 0.14 s | 0.03 s | 1.00 | -6.7 dB | rules |
| 4 | Click/sound-2.mp3 | 0.23 s | 0.01 s | 0.80 | -11.5 dB | model 0.80 |
| 5 | Click/sound-1.mp3 | 0.29 s | 0.04 s | 0.64 | -11.5 dB | model 0.80 |
| 6 | Ui Sound/SFX- Ui04.mp3 | 0.13 s | 0.00 s | 0.60 | -4.7 dB | model 0.60 |
| 7 | Ui Sound/SFX- Ui05.mp3 | 0.29 s | 0.01 s | 0.60 | -5.2 dB | model 0.60 |
| 8 | Click/Click (2).wav | 0.12 s | 0.10 s | 0.50 | -9.0 dB | rules |

### stamp (4 sounds)

short thud or hit.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Transition Sound Effects/Whip 2 Sound Effect ( By Ashish Editz )_01.mp3 | 0.12 s | 0.03 s | 0.46 | -12.8 dB | rules, fast whoosh |
| 2 | Vine Boom.mp3 | 1.15 s | 0.42 s | 0.42 | -11.6 dB | rules |
| 3 | Transition Sound Effects/Whip Sound Effect ( By Ashish Editz )_01.mp3 | 0.12 s | 0.06 s | 0.40 | -11.9 dB | rules, fast whoosh |
| 4 | camera-flash-204151.mp3 | 0.87 s | 0.06 s | 0.38 | -11.4 dB | model 0.60 |

### number (8 sounds)

tick or short counter.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Click/Click - Sound Effect (HD).mp3 | 0.17 s | 0.00 s | 0.70 | -9.4 dB | rules |
| 2 | Click/Mouse Click - Sound Effect (HD) (1).mp3 | 0.14 s | 0.03 s | 0.70 | -8.4 dB | rules |
| 3 | mouse-click-290204 (1).mp3 | 0.14 s | 0.03 s | 0.70 | -6.7 dB | rules |
| 4 | Pop/Pop sound effect.mp3 | 0.20 s | 0.01 s | 0.40 | -8.5 dB | rules |
| 5 | Pop/pop-1.mp3 | 0.21 s | 0.03 s | 0.40 | -8.5 dB | rules |
| 6 | Pop/pop-2.mp3 | 0.17 s | 0.01 s | 0.40 | 1.4 dB | rules |
| 7 | Pop/pop-3.mp3 | 0.11 s | 0.01 s | 0.40 | 0.2 dB | rules |
| 8 | Pop/pop-4.mp3 | 0.23 s | 0.02 s | 0.40 | -9.7 dB | rules |

### success (3 sounds)

positive UI ding (checkmarks).

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Ding sound effect.mp3 | 1.34 s | 0.07 s | 1.00 | -5.0 dB | rules |
| 2 | cash-register-kaching-sound-effect-125042.mp3 | 1.20 s | 0.50 s | 0.60 | -7.6 dB | model 0.60 |
| 3 | discord-notification.mp3 | 0.21 s | 0.13 s | 0.40 | -11.1 dB | rules |

### typing (2 sounds) (SHORT: fewer than 3)

keyboard or UI typing (comment fields, terminals), trimmed to the typing duration.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Click/Writing on keyboard Sound Effect.mp3 | 6.55 s | 6.43 s | 1.00 | -11.6 dB | rules |
| 2 | keyboard-typing-5997.mp3 | 15.53 s | 7.99 s | 1.00 | -4.3 dB | rules |

### negative (2 sounds) (SHORT: fewer than 3)

soft error or scratch (strike-throughs).

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | erro.mp3 | 0.79 s | 0.04 s | 1.00 | -11.2 dB | rules |
| 2 | censor-beep-88052.mp3 | 0.50 s | 0.36 s | 0.60 | -9.1 dB | model 0.60 |

### hook_hit (8 sounds)

impact with a whoosh, for the hook's set piece.

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | Vine Boom.mp3 | 1.15 s | 0.42 s | 0.90 | -11.6 dB | rules |
| 2 | Swoosh/SFX- Swoosh02.mp3 | 0.64 s | 0.16 s | 0.50 | -5.2 dB | rules, medium whoosh |
| 3 | Swoosh/SFX- Swoosh04.mp3 | 0.54 s | 0.12 s | 0.50 | -6.0 dB | rules, medium whoosh |
| 4 | Swoosh/SFX- Swoosh13.mp3 | 0.79 s | 0.06 s | 0.50 | -6.6 dB | rules, medium whoosh |
| 5 | Transition Sound Effects/Swoosh 6 Sound Effect ( By Ashish Editz )_01.mp3 | 0.59 s | 0.18 s | 0.47 | -13.5 dB | rules, medium whoosh |
| 6 | jet woosh.wav | 2.66 s | 0.19 s | 0.47 | -11.8 dB | rules, slow whoosh |
| 7 | Transition Sound Effects/Deep Whoosh Sound Effect ( By Ashish Editz )_01.mp3 | 0.54 s | 0.18 s | 0.43 | -12.4 dB | rules, medium whoosh |
| 8 | Free Woosh/ESE - FIGHT PACK - WHOOSH - SlowMo 05.wav | 3.19 s | 0.10 s | 0.36 | -5.2 dB | rules, slow whoosh |

### notification (4 sounds)

message sound (the CTA's DM card).

| # | file | sound | attack | fit | gain | from |
|---|------|-------|--------|-----|------|------|
| 1 | discord-notification.mp3 | 0.21 s | 0.13 s | 1.00 | -11.1 dB | rules |
| 2 | Ding sound effect.mp3 | 1.34 s | 0.07 s | 0.50 | -5.0 dB | rules |
| 3 | cash-register-kaching-sound-effect-125042.mp3 | 1.20 s | 0.50 s | 0.48 | -7.6 dB | model 0.60 |
| 4 | censor-beep-88052.mp3 | 0.50 s | 0.36 s | 0.48 | -9.1 dB | model 0.60 |

## Short pools

These cue types have fewer than 3 sounds: typing, negative. Add files to styles/sfx/ (a sorted subfolder or a descriptive name), or pin a waiting file in overrides.txt.

## Waiting for your approval (low confidence)

The indexer model could not tell from the name and the measurements (confidence under 0.6). They stay out of the pools until you pin them: `pin: <cue type>: <path>` in overrides.txt.

- Beep roser.wav: maybe notification, hero_enter (confidence 0.45; Bright beep, but the slow 0.43 s attack is unlike a click; guessing.)
- PlageFlip3.mp3: maybe transition_slow (confidence 0.55; Page flip with 0.66 s swell over 2.6 s; plausible slow transition.)
- Transition Sound Effects/Magic Spell Sound Effect ( By Ashish Editz )_01.mp3: maybe transition_slow (confidence 0.50; Magic spell name, 0.5 s attack, 3.5 s long; loosely a slow swoosh.)
- Ui Sound/SFX- Ui02.mp3: maybe ui_click, success (confidence 0.55; Short bright UI tone with 0.41 s tail; click or small ding.)
- Ui Sound/SFX- Ui03.mp3: maybe notification, ui_click (confidence 0.50; Generic UI name; 1.3 s bright tone suggests message sound.)
- Ui Sound/SFX- Ui06.mp3: maybe success, notification (confidence 0.50; 1.3 s bright tone with tail; ding or message sound, generic name.)
- Ui Sound/SFX- Ui07.mp3: maybe ui_click, hero_enter (confidence 0.50; Generic UI name; 0.23 s attack makes it a soft pop at best.)
- Ui Sound/SFX- Ui08.mp3: maybe ui_click (confidence 0.55; Short bright click with near-zero attack; generic name.)
- Ui Sound/SFX- Ui09.mp3: maybe ui_click, success (confidence 0.45; Generic UI name; 0.77 s bright tone with slight swell.)
- Ui Sound/SFX- Ui10.mp3: maybe ui_click, success (confidence 0.50; Generic UI name; 0.6 s bright tone, short tail.)
- finger-snap-reverb-423222.mp3: maybe ui_click, stamp (confidence 0.50; Snap with 0.12 s effective sound; long reverb tail is mostly silence.)
- pop-91931.mp3: maybe hero_enter, transition_slow (confidence 0.50; Named pop, but 2 s attack and 3 s length fit a slow swell better.)

## Excluded files

- PageFlips.mp3: far too long for any cue type (effective sound 6.0 s)
- PlaneWoosh.wav: far too long for any cue type (effective sound 10.7 s)
- Riser.wav: no cue type fits (model: Riser with no impact at the end; fits nothing per the brief.)
- SFX Swoos.MP3: far too long for any cue type (effective sound 48.2 s)
- Swoosh/SFX- Swoosh06.mp3: clipped (19 runs of full-scale samples)
- Swoosh/SFX- Swoosh07.mp3: clipped (19 runs of full-scale samples)
- Transition Sound Effects/Air Blow Sound Effect ( By Ashish Editz )_01.mp3: clipped (46 runs of full-scale samples)
- Transition Sound Effects/Air Swoosh Sound Effect ( By Ashish Editz )_01.mp3: clipped (21 runs of full-scale samples)
- Transition Sound Effects/Fast Swoosh Sound Effect ( By Ashish Editz )_01.mp3: far too long for any cue type (effective sound 5.0 s)
- Transition Sound Effects/Fast Whoosh Sound Effect ( By Ashish Editz ).mp3: far too long for any cue type (effective sound 5.8 s)
- drum-roll-please-6386.mp3: far too long for any cue type (effective sound 6.1 s)
- plane riser.wav: no cue type fits (model: Riser with no impact; fits nothing per the brief.)
- rewind-2-63931.mp3: high noise floor (22 dB under the peak)

## Overrides in force (styles/sfx/overrides.txt)

None.

## Counts per category

- click: 7
- impact: 1
- negative: 1
- notification: 1
- other: 26
- pop: 9
- success: 1
- typing: 2
- whoosh fast: 17
- whoosh medium: 12
- whoosh slow: 29

## Thresholds (config.json sfx, DECISIONS.md M8)

- whoosh speed: fast when the effective sound is 0.35 s or shorter, or 0.6 s or shorter with an attack of 0.08 s or shorter; slow when it is 0.8 s or longer with an attack of 0.2 s or longer, or 1.5 s or longer; medium otherwise. Effective sound = onset (30 dB under the loudest 5 ms frame) to the end of the tail (40 dB under).
- quality: clipped at 10 or more runs of 3 full-scale samples; high noise floor when the 5th percentile of the 20 ms frame RMS is within 30 dB of the peak (files of 0.5 s or longer); far too long over 5 s of effective sound (typing excepted) or over 2 times a cue type's window.
- pools: fit at least 0.25, at most 8 sounds, short under 3; model answers under confidence 0.6 wait for a pin.
- duration windows (seconds of effective sound): transition_slow 0.4 to 2.5; transition_fast 0.08 to 0.8; attention 0.08 to 0.7; hero_enter 0.03 to 0.7; ui_click 0.01 to 0.4; stamp 0.05 to 1; number 0.01 to 0.35; success 0.1 to 1.8; typing 0.4 to 30; negative 0.08 to 1.8; hook_hit 0.2 to 2.5; notification 0.15 to 2.5
