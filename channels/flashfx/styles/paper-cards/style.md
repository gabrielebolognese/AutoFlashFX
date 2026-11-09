# Look: paper-cards (version 2)

Look references: `refs/look/` v01 `igexport-De2Ap1yEUJ2.mp4` (42.1s) and v02 `igexport-De5Ur0HNvIt.mp4` (49.6s), both 720x1280, 30fps.
Motion references: `refs/motion/` v03 to v09 (list in `analysis/index.md`). Version 1 was built from v04, now a motion reference;
it is kept in `analysis/style_v1.md`.
All pixel values are at 1080x1920. The source of every number is in `analysis/sources.md`. tweaks.md overrides this file.

## In one line
Explainer reels on warm, softly lit paper: rounded warm-white cards with soft drop shadows fly in and settle, a heavy-grotesk
headline with one orange serif-italic phrase opens the video, captions are bare black words with orange boxes on the key words,
and a small pixel mascot rides every scene.

## Canvas (1080x1920, 30fps)
- Background: `paper`, two large radial glows and a dot grid. Never a flat color, photo or illustration behind everything.
  - Warm glow, top left: `glow-warm` at its strongest near the corner, still tinted at x 540 and y 600, plain paper by about
    x 810 and y 960.
  - Second glow, lower right: in both look refs, color differs. Open question 8.
  - Bottom corners darker than the center: #E8DFD2 (v01), #E4D7C9 to #E6D9CD (v02).
  - Dot grid: `dot`, dots about 5 to 6 px. Spacing: Open question 7 (54px in v01, 43.5px in v02).
- Zones (y):
  - hook header (first scene only): kicker top 171 (v01) or 253 (v02), Open question 5; headline lines 113px apart.
  - hero group: one centered group, top edge between y 180 and 363, bottom edge at or above y 1176.
  - captions: cap center y 1480 (tweaks.md, Caption box). The look refs put it at y 1327 (v01) and 1337 (v02): Open question 1.
- Side margins: at least 60px (tweaks.md). Look refs: cards 63 to 150px from the edges, end card 105px.
- Right side: no text in the right 230px of the lower half (tweaks.md), so a centered caption line is at most 620px wide
  (x 230 to 850). Open question 2.

## Color (measured)
| token | hex | use |
|---|---|---|
| paper | `#F5EEE3` | background base (v01 #F6F0E6, v02 #F4EBE0) |
| glow-warm | `#ECD2BE` | top-left glow at its strongest sampled point (v01 #EBCBB5, v02 #EDD8C6) |
| dot | `#D2CABE` | dot grid (v01 #D5CFC4, v02 #CFC4B8) |
| surface | `#FFFAF7` | cards, pills, light chips, end card |
| surface-chrome | `#F9F4EF` | window title bars (v01); media frames are `#FFF8F1` (v02) |
| ink | `#100904` | captions, headline, numbers |
| ink-chip | `#1C110F` | dark chips and tags (v01 #1C110F, v02 #1B110F) |
| accent | `#DC6532` | caption emphasis boxes, kicker, keyword pill, play and send buttons, progress bars, logo marks (v01 #DE6531, v02 #DB6534) |
| accent-deep | `#C9623C` | serif-italic headline phrase (v01 #C96139, v02 #C9643F) |
| script | `#B04924` | handwritten line (both) |
| success | `#289C5C` | check badges, positive values (v01 #1F9B56, v02 #329D61) |
| mascot | `#D67354` | mascot body (v01 #D77454, v02 #D57253) |

The UI accent covers a median 0.8 to 1.3% of a frame (p90 4.7 to 4.8%). Media inside cards (illustrations, screenshots) brings
its own colors and does not count as UI.

## Shapes
- **Card:** `surface`, corner radius 30px, no outline (only a 1 to 3px faint darker edge, #D7C5BA to #E4D5C9), soft drop
  shadow: about 3px above, 36 to 42px at the sides, 52.5 to 73.5px below (median 66), darkest right under the bottom edge
  (#B2A994 to #B59986 on paper). Starting point in CSS: `box-shadow: 0 31px 35px` in a warm brown, tuned until the pixel under
  the bottom edge matches.
- **Window card:** a card with a `surface-chrome` title bar: 3 traffic-light dots plus a small title or site icon. Dark variant
  (terminal, code): near-black body with colored mono text (fill not sampled).
- **Media card:** the image inside a 7.5px `#FFF8F1` frame, radius 30px, same shadow (v02).
- **Stat container:** white pill, fully round, 168px tall, icon plus number plus unit word (v01); or a rounded chip 141px tall,
  number plus serif-italic unit (#B36241) with a small sub-label pill under it (v02).
- **Dark chip:** `ink-chip`, rounded, small white text with one accent word, 55px tall (v02).
- **Light chip:** `surface`, rounded, ink text, 67px tall (v02).
- **Emphasis box:** `accent` fill, near-white text, corner radius 12px (v01). Sizes under Captions.
- **Keyword pill:** `accent`, fully round, white caps in quotes. v01 runs a subtle vertical gradient #EB773B (top) to #DF6532
  (bottom); v02 measures #E36E37.
- **Check badge:** `success` circle, white check, white ring.
- **Logo tile:** `surface` rounded square (v02) or circle badge (v01) with the topic logo in `accent`.
- **Tilt:** the end card is rotated (v01 -1.7 degrees, rising to the right; v02 tilts and wobbles). Hero cards: Open question 10.
- **3D:** the look refs have no 3D objects; cards move in perspective (fly-ins from near the camera, tilts). tweaks.md 3D line
  applies.

## Typography (sizes at 1080 wide)
| role | font class | suggestion | size | case |
|---|---|---|---|---|
| caption | heavy grotesk 800 | Inter Tight ExtraBold or Plus Jakarta Sans ExtraBold | cap 48px, font about 67px | Sentence case, as spoken |
| hook headline | heavy grotesk 800 to 900 | same | cap 70.5 to 76.5px (median 73.5), font about 102px, lines 113px apart | Sentence case, tight tracking |
| headline phrase | serif italic, regular weight | Instrument Serif Italic | sits on the headline lines | as spoken, `accent-deep` |
| kicker | grotesk 600 to 700, wide tracking | Space Grotesk SemiBold | cap 21px (v02) or 27px (v01): Open question 6 | ALL CAPS, `accent`, after a small accent mark |
| stat number | heavy grotesk | same as caption | digit height 64.5px, font about 90px | digits with commas |
| end card "Comment" | heavy grotesk | same as caption | cap 67.5 to 72px (median 69.75), font about 97px | Title case |
| end card keyword | heavy grotesk | same as caption | cap 70.5px, font about 98px | ALL CAPS in quotes, white on `accent` |
| mono (timers, filenames, code, chip text) | monospace | JetBrains Mono | not measured | as typed |
| handwritten | script | Caveat | lines 69 to 70.5px apart, font about 58px (estimate) | lower case, `script` |

The suggestions are close matches, not identifications. Caption, headline and numbers use the same face.

## Captions
- No box and no panel: bare `ink` words, Sentence case, punctuation kept.
- Position: one line, centered, cap center y 1480 (tweaks.md), at most 620px wide (tweaks.md, Right side).
- 1 to 4 words per chunk. The chunk is laid out at its final width and centered, and each word appears in its own place when
  it is spoken. Words are never shown before they are spoken.
- Word enter: opacity 0 to 1 over 4 frames. Blur and rise: Open question 12.
- Emphasis: 1 to 3 key words per chunk sit on an `accent` box (sometimes the whole chunk). Each word's box fades in with the word
  over 4 frames, rising 9 to 12px. Boxes of adjacent words touch and read as one bar.
- Box: 76.5 to 81px tall (median 78.75), 13.5px above the cap height, 15 to 19.5px below the baseline, radius 12px, 9px gap to the
  previous word; text near-white (#FCF7F5 to #FFF5F3).
- Replace: the old chunk fades out over 2 to 3 frames; the next chunk's first word starts on the following frame. No overlap.
- No captions while the hook headline is on screen and none on the end card: the headline carries the words there.

## Hook and end card
Added in version 2 because both look refs build them the same way.
- **Hook:** frame 0 is empty paper with the accent mark where the kicker will start. The hero element enters within the first
  4 frames (v01 card from below at frame 4, v02 icon pop frames 1 to 4). Kicker words fade in one per spoken word, then the
  headline builds word by word over 2 to 3 lines with one phrase (1 to 2 words) in the serif italic. The hook scene runs 4.4s
  (v02) to 5.4s (v01).
- **End card:** a `surface` card 858px wide, 400 to 419px tall, x 105 to 963, top edge at y 324 (v02) to 363 (v01), tilted.
  "Comment" on top, the keyword pill under it, a two-line handwritten line under the card, then a row of 5 mascots with props
  about 171px apart (y 1044 to 1142). Both look refs type the keyword into the pill letter by letter (Open question 4). The end card holds
  6.6s (v02) to 7.2s (v01) to the end. No loop back to frame 0.

## Mascot (the recurring element; there is no tracker)
- Pixel-art creature, body `mascot`, about 85 x 58px, carrying one prop that matches the scene (clapperboard, star,
  film strip, play icon, grid icon).
- One per scene, perched on a corner of the main element (top right or bottom right) and overlapping its edge.
- Enters 4 to 7 frames after its card lands, fading or rising in over 3 to 4 frames.
- Also in 5 of 7 motion refs (v03, v05, v07, v08, v09).
- Brand mark: tweaks.md. In the look refs the topic logo sits in the kicker mark, on logo tiles and on badges.

## Pacing (timing from the motion refs v03 to v09)
- Visual changes in the hero zone (middle screen band): median 6.4 per 10s, median gap 0.9s, p90 3.55s, longest 6.5s.
  Look refs: 5.5 per 10s, median gap 1.03s (v01) and 1.3s (v02).
- Scenes: mean scene length per motion ref 2.2 to 5.9s, median 3.9s. Look refs run longer scenes (median 4.8s v01, 5.25s v02).
- Inside a scene, elements build one at a time; v03, v06, v08 and v09 land each element on the word that names it.
- Length: look refs 42.1s and 49.6s, motion refs 43.8 to 72.6s. tweaks.md Length line applies.
- Voice speed: not checked.

## Motion (from the motion refs; a rule needs 5 of the 7)
- **Enter** (scene card, panel, chip, list row): opacity 0 to 1 over 5 frames and y +38px to 0 over 8 frames, ease-out
  (expo or cubic), no overshoot, no scale. All 7 motion refs. Rise per video 20 to 72px.
- **Exit:** a cut, or a move faster than the enter that accelerates (ease-in), 3 to 10 frames. Which one: Open question 3.
- **Scene change:** Open question 3 (cut, animated exit, or camera move).
- **Pop** (badge, logo tile, keyword pill, small chip): scale up from about 0.5 with a back-out overshoot, 3 to 15 frames;
  icons and badges overshoot 13 to 16%, pills and cards 1 to 3%. 6 of 7 (v03 to v08).
- **Count-up:** numbers count from 0 with ease-out (cubic or quart), median 27.5 frames (19 to 36). Ease-out in 5 of the 6 measured (v05 eases in and out).
- **Caption chunk replace:** 2 to 3 frames out, the next word on the following frame, no overlap. 6 of 7.
- **Caption word enter:** 4 frames (v03, v07, v08, the motion refs with bare captions).
- **End card build:** elements fade in over 6 frames (3 to 7), top to bottom, 5 to 6 frames apart. All 7. The mascot moves on
  the end card (rise, hop, walk-in or pop) in 5 of 7 and in both look refs.
- **Typing** (keyword, prompt, code): 2 frames per letter for keywords (v02, v06; v03 2 to 3, v04 1.5).
- **Set pieces:** one or two per reel. Each one appears in fewer than 5 refs, so their specs live in `vocabulary.md`: fly-in from
  a spot parked off frame, camera pull-back or zoom, grid build with a 1 to 2 frame stagger, strike-through drawn over 3 to 6
  frames, data sweep, stamp, card turning to stone, sticker pop-off.

## Beat map
| beat | component | videos (of 9) |
|---|---|---|
| hook (0 to 5s) | kicker plus headline with a serif-italic phrase, over one hero card or icon pair | v01, v02, v03, v07, v08 (5) |
| proof / number | stat container or giant number, counting up | all 9 |
| CTA | end card: "Comment" plus keyword, mascot or mascot row | all 9 |
| any scene | mascot with a prop | v01, v02, v03, v05, v07, v08, v09 (7) |
| fact / label | dark chip or tag | v01, v02, v04, v05, v07, v08, v09 (7) |
| state | light pill or chip | v01, v02, v03, v04, v06, v08, v09 (7) |
| done / yes | check badge or checklist ticks | v01, v03, v04, v06, v07, v08 (6) |
| the tool | window card (browser or app) | v01, v02, v05, v07, v08 (5) |
| how it works | terminal or code card that types | v01, v02, v05, v08, v09 (5) |
| data | chart card (bars, line, gauge) | v03, v04, v05, v06, v07 (5) |
| options / examples | grid, fan or deck of thumbnail cards | v01, v02, v04, v05, v06 (5) |
| tool identity | logo tile or logo badge | v01, v02, v05, v06, v08 (5) |
| "not X" / before and after | strike-through (line or X) | v02, v04, v06, v07, v09 (5) |
| the prompt | chat card with an input bar or bubbles, typing | v01, v06, v07, v08 (4) |
| progress | progress or meter bar | v01, v02, v03, v09 (4) |
| aside | handwritten callout with an arrow | v02, v07, v08 (3) |
| comparison | table card | v02, v04 (2) |
| version 1 only | progress tracker | v04, v06, v09 (3) |
| one-offs | stamp (v04), stone card (v06), sticker pop-off (v09), doodles (v01), speech bubble and confetti on the end card (v07, v08) | 1 or 2 each |

## Honesty labels
- None in the look refs: no ILLUSTRATIVE-style tags on stat pills, meters, grids or mock screens (v01 0:07.5 to 0:12.5, v02
  0:13.5 and 0:34.0 to 0:40.0 checked).
- The version 1 family labels every mock or sourced card (v04, v06, v09); v05 uses disclosure lines; v03 shows source headers.
  Open question 13.

## Sound (measured, all 9 videos)
- Voice only: no music bed detected in any reference. True silence 3.6 to 16.7% of the track (median 12.9%; look refs 12.9% and
  14.6%).
- Loudness: -14.1 to -14.4 LUFS integrated (median -14.2). True peak -2.4 to +0.2 dBTP (median -0.7; look refs -1.0 and -0.7).
- Sound effects: not checked. Decide by ear and write it in tweaks.md.

## Never
- Ink (black) outlines on cards, hard offset shadows, square card corners.
- A box or panel behind the caption line, ALL CAPS captions, caption words shown before they are spoken.
- A progress tracker or any bar fixed to the top of the frame.
- A photo or illustration as the background: media sits inside cards, the background is always paper.
- A second UI accent hue. Green is only for success states. (Blue: Open question 14.)
- Accent-filled areas over 5% of a frame (tweaks.md).
- 3D objects outside the hook and the end card (tweaks.md).

## Open questions
Decide these first:
1. **Caption position.** tweaks.md keeps captions at y 1480 (a version 1 decision for a boxed caption). Both look refs put the
   unboxed caption at y 1327 (v01) and 1337 (v02), inside the safe zone. Options: keep y 1480, or move to y 1332 and drop the
   safe-zone exception (PROPOSED in tweaks.md).
2. **Caption width vs the right 230px.** Both look refs center wide chunks; v01's widest is 942px (0:10.8, x 75 to 1016). Options: cap
   the line at 620px (follows tweaks.md: a 3-word chunk like v01's "In two days," is 368px and fits; long 4-word chunks
   must split), or allow wider lines like the refs.
3. **Scene change.** The motion refs split three ways:
   (A) hard cut, then the new scene's elements enter: v04, v06, v09.
   (B) animated exit, then enter: v03 (push: 6 frames out ease-in, 2 empty frames, 12 frames in expo-out; or a 20-frame
   shrink-and-crossfade), v07 (falls over 10 frames, ease-in, tilting about 2 degrees; the next card rises at once), v08 (gravity
   fall over 10 frames). The look refs do this too (v01, v02: fade with blur over 2 to 4 frames, then fly-ins).
   (C) camera moves as transitions: v05 (pull-back 16 frames and zoom 20 frames, both ease-in-out; pan 5 frames ease-out).
   Every video in the version 2 look family (v01, v02, v03, v07, v08) uses B; the version 1 family uses A.
4. **End-card keyword.** Typed into the pill letter by letter (v01, v02, v03, v04, v06) or popped in as a finished pill (v07,
   v08; v09 fades it in, v05 fades the whole card).

Smaller:
5. **Hook header top.** Kicker at y 171 (v01, above the safe line at 230) or y 253 (v02). PROPOSED in tweaks.md: 253.
6. **Kicker size.** Cap 27px (v01) or 21px (v02).
7. **Dot grid spacing.** 54px (v01; also v03, v07, v08) or 43.5px (v02).
8. **Lower-right glow.** Cool #D4D9DB (v01) or warm #F0D9C7 (v02).
9. **Doodles.** v01 scatters small stickers in every scene (purple dot #9A7ADF, blue dot #68AAE0, pink star #F28EB1, orange star
   #DD652A, dashed-outline clouds, all with a white outline). v02 has none.
10. **Hero card tilt.** v01 tilts hero cards in perspective; v02 keeps them straight and tilts only fans, the depth stack and the
    end card.
11. **Headline build.** Word by word as spoken (v01, v02, v03, v05; 3 to 4 frames per word, v03 and v05 rising 9 to 10.5px) or
    line by line through a mask (v07: 10 frames, 90px rise, lines 5 frames apart; v08: 5 to 7 frames, 53px rise).
12. **Caption word style.** Plain fade (v01, v02, v07) or blur-to-sharp with a 7.5 to 10.5px rise (v03, v08).
13. **Honesty labels.** The look refs have none. Version 1 required them, and v04, v06 and v09 label every mock or sourced card
    ("illustrative", "real", source and date). Keep them or drop them.
14. **Second color for comments.** v01 colors the comment icon and count blue (#4485D2). Only v01 does this.
15. **True peak.** The references range from -2.4 to +0.2 dBTP, and v07 clips. Pick a ceiling.
