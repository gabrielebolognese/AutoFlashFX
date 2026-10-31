# vocabulary.md (look: paper-cards, version 2)

The components and moves a developer has to build, ranked by how many of the 9 references use them.
Colors are tokens from style.md. Sizes in px at 1080x1920, durations in frames at 30 fps. Examples are nickname + timestamp
(frame numbers where the notes give them). Measurements behind every number: `analysis/vXX/measurements.md`.
Where a component appears in the version 1 family only (v04, v06, v09), it says so: build its motion, not its look.

## 1. Card enter (all 9)
- Does: brings a scene card, panel, chip or list row into place. The default move for anything new.
- Parameters: element, rise distance (default 38).
- Motion: opacity 0 to 1 over 5 frames; y +38 to 0 over 8 frames; ease-out (expo or cubic); no overshoot, no scale.
  Per video: rise 20 to 72, position 6 to 10 frames.
- Examples: v06 1.10s (f33 to f41, opacity 5 frames, rise 66); v09 25.43s (f763 to f771, rise 24).

## 2. Stat number with count-up (all 9)
- Does: shows a number that proves the point and counts up to it.
- Parameters: value, unit word, icon (optional), sub-label (optional), container: `pill` (white, fully round, 168 tall, icon,
  number, unit in `accent`) or `chip` (141 tall, number plus serif-italic unit in #B36241, sub-label pill under it).
- Type: number heavy grotesk, digit height 64.5 (font about 90), `ink`.
- Motion: container enters (1); number counts from 0 with ease-out (cubic or quart), median 27.5 frames (19 to 36); a second
  stat starts about 1s after the first (v01 0:09.5).
- Examples: v01 0:07.5 to 0:11.5 (two pills); v08 8.40s (f252 to f277, easeOutCubic, 25.5 frames).

## 3. Keyword end card (all 9)
- Does: the CTA. Asks the viewer to comment a keyword.
- Parameters: verb line ("Comment"), keyword, handwritten line (2 lines), mascot row (5 mascots, each with a prop).
- Look: `surface` card 858 wide, 400 to 419 tall, x 105 to 963, top y 324 to 363, tilted (v01 -1.7 degrees), radius 30, card
  shadow; verb in heavy grotesk cap 67.5 to 72; keyword pill `accent`, white caps in quotes, cap 70.5; handwritten line in `script`,
  lines 69 to 70.5 apart; mascots about 171 apart at y 1044 to 1142.
- Motion: elements fade in over 6 frames (3 to 7), 5 to 6 frames apart, top to bottom; keyword typed 2 frames per letter (both
  look refs) or popped (Open question 4); the card wobbles slightly every frame (v02); mascots walk in from the left, then spread
  out (v02) or hop in alternation (v01). Holds 6.6 to 7.2s.
- Examples: v02 42.95s (letters at +4, +6, +8 ... +19); v01 0:34.9 to 0:42.1.

## 4. Mascot (7: v01, v02, v03, v05, v07, v08, v09)
- Does: the recurring character. Rides the main element of each scene and celebrates on the end card.
- Parameters: prop (clapperboard, star, film strip, play icon, grid icon), corner (top right or bottom right).
- Look: pixel art, body `mascot`, about 85 x 58.
- Motion: enters 4 to 7 frames after its card lands, over 3 to 4 frames (fade, or rise from below the element: v02 f11 to f15).
  End-card options measured: hop 72 up and back over 11 frames, 5 up and 6 down (v09 f1566 to f1577); rise 482 to 594 over 10
  frames with a vertical stretch of 1.18 to 1.24 settling to 1 (v07 f1242, v08 f1172); squash hop, height 1, 0.82, 1.05, 1 and
  width 1, 1.13, 0.97, 1 over 10 frames (v07 f1254); walk along a chart to the newest point, 12 to 16 frames (v03 f1319).
- Examples: v01 0:00.53 (pop onto the card corner); v02 0:11.0 (bottom-right corner).

## 5. Dark chip or tag (7: v01, v02, v04, v05, v07, v08, v09)
- Does: a short fact or label attached to a card (time span, file name, "render local", "same skill every time").
- Parameters: text, accent word, small icon.
- Look: `ink-chip`, rounded, white text with one `accent` word, 55 tall (v02).
- Motion: pops in 2 to 3 frames (v01 corner chip, 0:05.65); v09 tag 2 frames, pill 4 frames, 4 frames apart.
- Examples: v01 0:05.7 ("In 2 days" chip on the card corner); v02 0:30.5 (chip under the editor window).

## 6. Light pill or chip (7: v01, v02, v03, v04, v06, v08, v09)
- Does: a label inside or above a card ("video AI", eyebrow labels, state labels).
- Parameters: text.
- Look: `surface`, rounded, `ink` text, 67 tall (v02).
- Motion: fade in over 3 to 4 frames with a small drift (v03 label pill, f1273 to f1276).
- Examples: v02 0:10.6 (label on a media card, struck through at 0:11.1).

## 7. Caption line (bare words: 5 of 9, v01, v02, v03, v07, v08)
- Does: the spoken words, one chunk at a time.
- Parameters: chunk text (1 to 4 words), emphasis words.
- Look and layout: style.md, Captions.
- Motion: word fades in over 4 frames when spoken (3 in the look refs); emphasis box fades in with its word over 4 frames, rising
  9 to 12 (v03 f221 to f224, rise 12; v07 f142 to f145, rise 9); old chunk out over 2 to 3 frames, next word on the following frame.
- Examples: v01 0:05.58 ("two" box, 2 to 3 frames); v03 f244 to f247 (chunk swap).

## 8. Pop (6: v03, v04, v05, v06, v07, v08)
- Does: brings small things in with a little spring: badges, logo tiles, keyword pills, small chips.
- Parameters: overshoot (icons and badges 13 to 16%, pills and cards 1 to 3%), duration 3 to 15 frames.
- Motion: scale from about 0.5 to peak, then back to 1 (back-out); opacity reaches 1 in the first 4 to 5 frames.
- Examples: v08 f124 to f138 (logo tile 0.55, 1.13 at f131, 1.0); v03 f1394 to f1406 (check badge 0.2, 1.16, 1.0).

## 9. Check badge and checklist ticks (6: v01, v03, v04, v06, v07, v08)
- Does: marks done or yes.
- Look: `success` circle, white check, white ring.
- Motion: badge pops (8), 3 frames in v01 right after a progress bar fills; checklist ticks 1 to 3 frames each, 4 to 6 frames apart
  (v06 f1969, f1973, f1977; v07 f1072, f1078, f1083).
- Examples: v01 0:33.52; v03 f1394.

## 10. Window card (5: v01, v02, v05, v07, v08)
- Does: shows the tool or a site.
- Parameters: title or site icon, content (screenshot, illustration, UI mock).
- Look: card (radius 30, card shadow) with a `surface-chrome` title bar and 3 traffic-light dots.
- Motion: card enter (1), or fly-in (16).
- Examples: v01 0:00.13 (hook card from below); v07 12.13s (rises 870 over 16 frames).

## 11. Terminal or code card that types (5: v01, v02, v05, v08, v09)
- Does: shows the prompt or the code being written.
- Parameters: title, lines.
- Look: dark window card, colored mono text.
- Motion: lines appear one by one (v01 0:18.5 to 0:20.5, not counted at 30 fps); chat typing runs about 1.15 frames per character
  (v07 f132 to f155); a rewrite types 1.7 to 2.6 characters per frame (v04 f982 to f1006).
- Examples: v01 0:18.5; v02 0:06.5 to 0:09.5.

## 12. Chart card (5: v03, v04, v05, v06, v07)
- Does: data: bars, a line, a gauge.
- Parameters: values, labels, highlight bar in `accent`.
- Motion: bars grow over 8 to 12 frames, ease-out (v04 8 frames, v06 easeOutCubic 12), 1.5 to 2 frames apart, left to right; the
  value fades in over 2 frames as its bar ends (v06 f1457); gauge arc grows with its number over 23 frames, ease-out (v04 f680 to
  f703); a "you" bar can accelerate instead, 32 frames ease-in (v07 f20 to f52).
- Examples: v06 48.30s (f1449 to f1460); v04 f1432 to f1443.

## 13. Thumbnail grid, fan or deck (5: v01, v02, v04, v05, v06)
- Does: shows many examples at once.
- Parameters: thumbnails, rows and columns, small count chips (dark pill with a play glyph and a number).
- Motion: grid build 3 to 4 frames per card (fade while rising), 1 frame apart inside a row, the second row 7 frames after the
  first (v02 0:34.62 to 0:35.08); deck deal about 1 frame per card over 31 frames, ease-out (v04 f424 to f455); spaced pops every
  10.5 frames (v05 f11, f22, f32 ...).
- Examples: v02 0:34.6; v04 f424.

## 14. Logo tile or logo badge (5: v01, v02, v05, v06, v08)
- Does: names the tool or brand.
- Look: `surface` rounded square (v02) or circle badge (v01), logo in `accent`. tweaks.md Brand mark decides which logo.
- Motion: pop 3 to 4 frames (v02 f1 to f4) or with 13% overshoot over 14 frames (v08); a second tile slides in from the left over
  9 frames with a 6px overshoot (v08 f141 to f150).
- Examples: v02 0:00.03; v01 0:11.5.

## 15. Strike-through (5: v02, v04, v06, v07, v09)
- Does: "not X", before and after.
- Motion: a line drawn across over 3 to 4 frames (v04 f367 to f369); an X as two strokes of 6 frames each, ease-out, 6 frames
  apart (v06 f1872 to f1886); a replacement types in after it (v04).
- Examples: v02 0:11.1 (label struck); v06 62.40s.

## 16. Fly-in from a parked spot (4: v01, v03, v07, v08)
- Does: a big entrance for a hero card or window.
- Parameters: start (below the frame, half off the bottom, or off the left or right edge), start tilt 2.4 to 3.9 degrees.
- Motion: travels 414 to 930 over 11 to 16 frames, expo-out (each frame's step is 0.64 to 0.69 times the previous one), tilt
  eases to 0 to 1.4 degrees, no overshoot.
- Examples: v08 f8 to f21 (930, tilt 3.9 to 1.4); v03 f1433 to f1445 (414 from the right, 12 frames).

## 17. Chat card (4: v01, v06, v07, v08)
- Does: shows a prompt being sent.
- Look: `surface` card with an input bar and an `accent` send button.
- Motion: text types (11); the send button turns from gray to `accent` over 2 frames, 3 frames after the last character (v06 f2133).
- Examples: v01 0:13.5 and 0:31.5; v06 70.9s.

## 18. Progress or meter bar (4: v01, v02, v03, v09)
- Does: shows something finishing or a usage value.
- Motion: the bar fills over 6 frames, then a check badge pops (v01 0:33.35 to 0:33.58).
- Examples: v01 0:33.4; v02 0:13.5.

## 19. Camera pull-back or zoom (4: v02, v04, v05, v06)
- Does: reveals context (the reel inside an editor) or dives into one card.
- Motion: pull-back of the whole scene into an app window, 8 frames ease-out (v02 f828 to f835), or 16 frames ease-in-out (v05
  f524 to f539); grid-to-hero zoom 20 frames ease-in-out (v05 f132 to f152); zoom that ends in a cut, 12 frames ease-in (v05 f1124
  to f1137); long pull-back over a field of cards, about 11x over 108 frames, ease-in-out (v06 f417 to f525). The caption layer
  does not move (v02).
- Examples: v02 27.58s; v05 f524.

## 20. Headline reveal (5: v01, v02, v03, v07, v08)
- Does: builds the hook headline.
- Motion: word by word, 3 to 4 frames per word (v01, v02, v03, v05), or line by line through a mask (v07, v08). Open question 11.
- Examples: v02 0:00.7 to 0:01.5; v07 f2 to f16.

## 21. Exit fall or push (3: v03, v07, v08)
- Does: clears a scene with motion instead of a cut (Open question 3).
- Motion: fall off the bottom over 10 frames, ease-in (distance grows with the square of time), tilting 1.5 to 2 degrees, while the
  title rises 96 and fades (v07 f111 to f121); push 6 frames out to the left, ease-in, then 2 empty frames (v03 f1425 to f1431).
- Examples: v08 f318 to f328 (scatter); v07 f767 to f776.

## 22. Handwritten callout (3: v02, v07, v08)
- Does: a hand-drawn aside with an arrow pointing at something.
- Look: `script` color, handwritten face.
- Motion: not measured.
- Examples: v02 0:07.5; v08 32.0s.

## 23. Speech bubble and confetti on the end card (2: v07, v08)
- Motion: bubble scales from about 0.5 to 1 over 7 frames with a 40 to 42 overshoot in y, settling by 9 more frames; keyword pill
  pops 7 frames with 1.4 to 3% overshoot; confetti drifts (not measured).
- Examples: v07 f1251; v08 f1180.

## 24. Table card (2: v02, v04)
- Look: `surface` card, logo row with a small pill, label and value rows with hairline dividers, values right-aligned, good
  values in `success`.
- Motion: card enter, 7 frames, rise 28 (v04 f195 to f202).
- Examples: v02 0:41.5.

## One-offs (1 video each; build only if the script needs it)
- **Data sweep** (v03 f990 to f1104): a front of paths sweeps right at a constant 4.9 per frame for 114 frames (linear) while a
  clock pill steps one value per frame.
- **Stamp slam** (v04 f1767 to f1770, version 1 family): 3 to 4 frames, scale about 1.26 to 1.12 to 1, opacity 0.2 to 1, rotation
  8.3 degrees, ease-in, no bounce.
- **Stone card** (v06 f859 to f874): fill white to #878177 over 12 frames (ease-in), crack lines from frame 4, tilt to -3 degrees
  over the last 5 frames.
- **Sticker pop-off** (v09 f91 to f96): scale 1.0, 1.06, 1.13, 1.05, 0.60, 0 over 5 frames, one sticker every 4 to 10 frames.
- **Doodles** (v01, every scene): Open question 9.
- **Sticky note to attachment** (v01 0:13.5 to 0:14.5), **layer stack** (v01 0:23.7 to 0:25.5), **3D timeline wall** (v01 0:26.3 to
  0:29.2), **depth stack** (v02 0:18.5): seen on sheets, not measured at 30 fps.
- **Progress tracker** (v04, v06, v09): version 1 family only. Not part of the version 2 look.
