# Style bible: inkhead

Version 1, 2026-11-08. Style id: `inkhead` (my choice). Repo path: `channels/<id>/styles/inkhead/style.md`.

Built from the 6 reference videos, taken apart with ffmpeg and a speech model: shot-change detection on every
frame, contact sheets, half-second strips, color clustering on 240 sampled frames, narration transcripts, pitch
and loudness. Values marked "measured" come from that analysis.
Items marked "(my choice)" were decided by Claude and can be changed.

Sections 1 to 16 are the look contract the pipeline follows. Section 17 is the reference breakdown, section 18
the sound and narration found in the references, section 19 the changes this bible makes to other files, and
section 20 the open items.

---

## 1. The look in one paragraph

Flat 2D vector animation in a low-key night palette. Characters are ink figures: a solid near-black round head
with white eyes, black stick limbs and one flat colored garment. Every scene is lit by one motivated light (a
window, a lamp, the moon, a screen, a fire) with soft glows, haze, floating dust and a vignette. Text is bold,
rounded and uppercase: a short keyword headline at the top, karaoke subtitles in the lower third, gold numerals
on chapter cards and a small stat card for the story's numbers. Hard cuts every few seconds between wide scenes,
reaction close-ups, object and app inserts, and title cards. Everything is drawable as SVG and HTML shapes
animated with GSAP.

---

## 2. Code-drawability

All six references translate to code. Nothing in them is painterly, photographic or 3D: circles, rounded
rectangles, straight strokes, flat fills, 2 to 3 stop gradients, radial glows and simple particles.

| Element | Code approach |
| --- | --- |
| Ink characters | one reusable SVG rig: circle head, stroke limbs, path garment |
| Buildings, rooms, furniture | rectangles and rounded rectangles in 2 to 4 depth layers |
| Glows, light pools | radial gradients (not blur filters) |
| Light beams | gradient polygons with `mix-blend-mode: screen` |
| Haze, vignette | full-frame gradient overlays |
| Depth of field | one pre-blurred background layer at most |
| Kinetic text | letters split into spans, staggered GSAP tweens |
| Counters, stamps, page flips | GSAP number tweens, scale bounces, CSS 3D rotation |
| App screens | HTML components |

Cost hotspots are big blur filters, bloom and particle counts. Section 15 caps them.

---

## 3. Palette

### 3.1 Tokens

| Token | Hex | Use |
| --- | --- | --- |
| ink | #0E0B17 | heads, limbs, hair, deepest shadows (measured on heads) |
| night | #0E1221 | default background, cards, infographic space (measured, 16.6% of all pixels) |
| abyss | #080C17 | vignette edges, darkest backgrounds |
| slate | #2C313F | walls, concrete, ground, metal |
| plum | #221F2B | dusk shadows, interiors at night |
| dusk-brown | #432B27 | building walls at dusk, warm interiors |
| ember | #241715 | warm deep shadows |
| mauve | #4F444C | distant buildings, haze |
| white | #FCFBFB | subtitles (measured) |
| cream | #E9E5E8 | eyes, face lines, light strokes (measured) |
| paper | #F2EFEA | speech bubbles, paper, cards |
| muted-cream | #B9B1A5 | headline default (measured) |
| label-grey | #83807F | small labels, HUD labels (measured) |
| gold | #F6D388 | karaoke highlight, numeral gradient top (measured) |
| gold-deep | #C6A767 | headline emphasis, numeral gradient bottom, money and time values (measured) |
| amber | #EFC175 | lit windows, lamps, fire, warm glows (measured) |
| coral | #E3707B | danger, losses, negative stamps, follow pill |
| alarm-red | #B63D39 | sirens, emergency light, calendar header |
| money-green | #39A448 | money in, gains, positive stamps (measured) |
| mint | #66BA69 | positive UI states |
| cyan | #6AC9D6 | diagrams, screens, data lines (measured) |
| hud-cyan | #79ADCA | physical stats in the HUD (measured) |
| steel | #4186A6 | cold light, night windows, water |
| cold-rim | #BFD7FF | moonlight and screen rim light |
| warm-rim | #F3D9B1 | warm rim light |
| rose | #BB637D | dusk sky band (measured) |
| anomaly | #8062CE | the unexplained, supernatural tint (my choice) |
| gabry-orange | #F2913D | Gabry's garment and lines, reserved (my choice) |

### 3.2 Rules (checkable on sampled frames)

- Dark dominance: at least 65% of pixels below luminance 60/255. Measured in the references: 79%.
  Isolation: at least 75%. Entrepreneur: at least 55%.
- Accents: saturated bright pixels (saturation above 0.45, top channel above 140) stay under 6% of the frame.
  Measured: 2.0%.
- Brights: pixels above luminance 200 stay under 8%, except one allowed flash (section 12). Measured: 3.5%.
- One motivated main light per scene. Rim light color follows it (warm-rim or cold-rim).
- Gabry-orange belongs to Gabry: no other character, garment or important prop uses it, and no color within
  a hue distance of 20 degrees of it covers more than 2% of the frame. Fire and lamps use amber, never orange.
- Meaning of colors: green = money in or good; coral and alarm-red = money out, loss or danger; gold = numbers,
  time, emphasis; cyan = screens and data; steel and cold-rim = cold, night, isolation; anomaly = something that
  should not exist.

### 3.3 Universe palettes

| | Isolation | Entrepreneur |
| --- | --- | --- |
| Base | night, abyss, slate | dusk-brown, plum, ember, night |
| Lights | moon (cold-rim), flashlight (amber), screens (cyan), emergency (alarm-red), fire (amber) | lit windows (amber), desk lamps, monitor glow (cyan), sunsets (gold to rose) |
| Atmosphere | snow, fog, dust, rain, darkness at the edges | dusk haze, warm dust in window beams |
| Vignette | 50 to 60% | 35 to 45% |
| Typical accents | steel, cyan, alarm-red, anomaly | gold, money-green, coral |

---

## 4. Characters (everyone)

### 4.1 Construction (unit H = head diameter)

| Part | Rule |
| --- | --- |
| Head | circle, ink fill; hair is an ink shape merged into the head, hats are colored shapes |
| Eyes | 2 white ovals, 0.22H wide by 0.26H tall, centers 0.18H left and right of center, 0.05H above center |
| Pupils | ink circles 0.11H, pointing where the character looks |
| Mouth, brows | cream strokes 0.05H wide with round caps; brows only in medium shots and close-ups |
| Torso | rounded trapezoid garment, 0.75H wide at the shoulders, 1.5H tall (coats and dresses to 2.2H) |
| Garment shading | flat color plus one shade 18% darker on the side away from the light |
| Arms | ink strokes 0.11H wide, 1.4H long, round ends as hands; sleeves cover the upper 60% in the garment color |
| Legs | ink strokes 0.14H wide, 2.1H long; feet are ink ovals 0.3H long |
| Height | adult 4.6H, teen 4.2H, kid 3.4H, elderly 4.3H with a 5 degree forward lean |
| Rim light | 2 px stroke (at medium-shot scale) on the light-facing edge of head and body, warm-rim or cold-rim, 70% opacity |
| Ground shadow | ink ellipse under the feet, 25% opacity, soft edge |

Measured on the references: adults stand 4.5 to 5 head heights tall; faces are cream lines on ink.

### 4.2 Expressions (shared set)

neutral, joy (eyes as upward arcs, wide open smile), alarmed (eyes bigger, pupils small, small round mouth),
worried (inner brows up, small frown), determined (brows down, flat mouth), smug (half-closed eyes, side smile),
exhausted (half-closed eyes, flat brows, mouth down), devastated (inner brows up, deep frown, optional
steel-colored tear).

### 4.3 Motion

- Walk: 2-pose leg swing, 0.5 s per step, head bob 0.03H. Elderly: 0.7 s per step.
- Idle: torso breathing (scale 1.000 to 1.015, 3 s period); blink every 3 to 5 s (eyes scaleY to 0.1 for 0.12 s).
- Reactions: a pose change in 0.15 s with a small overshoot; big reactions read best on a phone.
- Holding objects: the hand closes into a mitten shape around the object.

### 4.4 Side characters

- Garments from this set, never orange: rose #D9839F, sky #7FB2E5, mustard #E2B93B, umber #8A6A4F,
  lavender #A58AD6, olive #8A9450, ash #9A9AA3, teal #3FAF9F, wine #8E3B58, cream coat #D8CDB8.
- Identity comes from hair silhouettes (bun, ponytail, bob, curls, buzz, long), hats (beanie, cap, fedora, hard
  hat), glasses, beards (an ink chin extension) and garment color.
- Age: white or grey hair shapes, glasses, a cane, a lean; kids at 3.2 to 3.6H.
- Crowds: up to 12 animated figures; more becomes a static silhouette layer or a row of round heads in the
  foreground (the audience device from the references).

### 4.5 The unexplained (Isolation)

- Threats are shown through absence and silhouette: a shape darker than the night (#05060B), sometimes with two
  small pale eye points, partly hidden, never in full detail.
- Prefer evidence over creatures: footprints, a wrong reflection, a door open that was shut, a shadow with no owner.
- Anomaly purple tints things that should not exist (a light, a sign, a mark).
- No blood, wounds or bodies on screen.

---

## 5. Gabry (model sheet proposal, pending open item 1)

The face is ink for every character, so Gabry is recognized by silhouette, color and outfit, never by facial
detail. A cartoon version of Gabriele in this style means his hair silhouette; everything else stays as below.

| Part | Rule |
| --- | --- |
| Hair | a forward-swept quiff: one wave rising 0.35H above the crown, swept toward screen right in the default three-quarter view, 3 soft points; ink like the head (my choice; replaced by Gabriele's own silhouette if open item 1 says so) |
| Signature color | gabry-orange #F2913D, shade #C76F28 (my choice) |
| Default outfit | orange hoodie: hood band behind the neck, 2 cream drawstrings 0.25H long, sleeves orange over the upper 60% of the arms |
| Legs, shoes | ink, like everyone |
| Accessories | none by default; glasses only in old age or when a story needs them |
| Height | 4.6H as an adult |

Fixed in every story: the quiff silhouette, orange as the dominant garment color, the ink face system, the voice.

Era and job outfits keep orange as the main garment: an orange parka in the Arctic, an orange work jacket at a
weather station, an orange shirt with a dark tie in 1994, an orange vest in 1926 Chicago, an orange suit jacket
as a CEO.

Age variants:

| Age | Height | Changes |
| --- | --- | --- |
| kid (6 to 10) | 3.4H | quiff 0.25H, hoodie a little oversized |
| teen (13 to 17) | 4.2H | default outfit |
| adult (18 to 40) | 4.6H | default |
| 50s | 4.6H | one grey (#9A9AA3) streak at the front of the quiff |
| 80 | 4.3H | quiff white (#EDEAE4) and lower (0.2H), round glasses, cane, 5 degree lean, slower walk |

On screen (my choice): Gabry appears in at least 40% of shots and at least once every 15 s. When the shot is his
point of view (his phone, his hands), his orange sleeve is visible.

---

## 6. Environments

### 6.1 Construction

- 2 to 4 depth layers: sky or back wall, far silhouettes (lighter and hazier), mid set, foreground.
- Buildings: flat rectangles with window grids; dark windows in the wall color 25% darker; 10 to 25% of windows
  lit in amber with a soft halo.
- Skies: night (night to abyss with a moon glow), dusk (plum to rose to amber at the horizon), day through windows
  (pale steel-blue).
- Interiors: a flat back wall, one window or lamp as the main light, simple furniture silhouettes, dust in the
  light beam.
- Ground: a flat band with a vertical gradient; feet sit on it with a ground shadow.

### 6.2 Isolation sets

bunker (slate concrete, hatch and ladder, shelves of cans, a radio with a red LED, one bare bulb cone), cabin
(dark wood planks, fireplace glow in amber, window onto snowy pines), night forest (layered pine silhouettes,
snow particles, moon), research or weather station (pale walls, monitors in cyan, a printer), ship deck at sea
(fog, horizon line, running lights), empty city street (dark windows, one lit window), underground stairs,
lighthouse lamp room.

### 6.3 Entrepreneur sets

bedroom desk at night (monitor glow, extension cord, cables), family kitchen (warm lamp, table), dusk street
with storefronts, bank or office interior (window onto the skyline), diner, bakery, warehouse.
Era overlays: 1920s (warmer, gas lamps, candlestick phones, ledger books), 1990s (beige CRT monitor, landline,
fax, pager, paper flyers), today (smartphone, laptop).

### 6.4 Data space

The references' infographic look, kept for story facts only (a ledger, a distance, a temperature, a countdown):
night background, a 40 px grid of 1 px lines at 6% opacity, vignette, faint particles, cyan line art, gold
numbers. At most 2 data shots per part, and never a lecture.

---

## 7. Light and depth

- Every scene has one main light, shown or implied, and the rim light follows it.
- Glows: radial gradients 2 to 4 times the size of the light, 35 to 60% opacity.
- Light beams: gradient polygons, `screen` blend, 15 to 30% opacity, drifting by at most 2 degrees.
- Haze: a vertical gradient toward the horizon or the light, 10 to 25% opacity.
- Vignette: per universe (section 3.3).
- Depth of field: in close-ups and inserts, the background layer is blurred (one pre-blurred layer, 4 to 8 px).
- Particles: dust in beams (2 to 4 px cream dots, slow drift), snow, rain streaks, embers, banknotes.

---

## 8. Camera

- Measured: many shots are locked off; on clean long shots the frame often pushes in by 2 to 6% over 4 to 9 s.
- Default: a locked frame with a slow push-in of 2 to 5% over the shot.
- Static holds: UI inserts, title cards, data shots.
- Pans: only to follow movement or to reveal something in the same space.
- Punch-in: scale 1.00 to 1.12 in 0.2 s on a reveal word (my choice).
- Shake: 4 to 10 px, 0.15 to 0.4 s, decaying, on knocks, impacts and stamps (my choice).
- No camera rotation beyond 3 degrees, no handheld drift (none in the references).

Shot sizes (vertical frame):

| Shot | Rule |
| --- | --- |
| wide | characters 18 to 30% of frame height, environment readable |
| medium | characters 45 to 65% of frame height |
| close-up | the head fills 40 to 60% of frame width, rim light on, background blurred |
| insert | the object or screen fills 55 to 75% of frame width |

---

## 9. Pacing and shot grammar

Measured: in the vertical reference, a detected change every 3.1 s on average; sampled every half second, a new
visual beat (a cut, a stamp, a counter, a new object) about every 2 s. The horizontal references change every
3.7 to 6.4 s. This section replaces the "visual change every 3 to 5 s" line in scenarios.md (section 19).

- A new visual beat every 2 to 4 s. No unchanged frame longer than 4 s, except up to 2 tension holds of at most
  6 s per part.
- Hard cuts: on average every 3 to 4 s, so 25 to 40 cuts in a 90 to 120 s part. Entrepreneur runs faster
  (every 2.5 to 3.5 s); Isolation slower on dread (every 4 to 5 s) and sudden on shocks.
- Shot mix per part: scene shots (wide and medium) 40 to 55%, inserts 20 to 35%, reaction close-ups 10 to 20%,
  cards (title and data) at most 12%.
- At least 2 close-ups of Gabry per part.
- Sync: cuts and element changes land on word boundaries. The key word of a sentence triggers its visual
  (the counter rolls on the number, the stamp lands on "paid", the cut to the door lands on "knock").
- The shock or reveal of a part lands as a cut or a punch-in on its key word, followed by a beat of stillness.

---

## 10. Text system

### 10.1 Fonts (my choice; the build vendors them from Google Fonts)

| Font | Use |
| --- | --- |
| Nunito 800 and 900 | all overlay text: headline, subtitles, cards, HUD, stamps, pills, bubbles |
| Inter 600 and 700 | text inside the world: apps, screens, documents, signs |
| IBM Plex Mono 500 | printouts, terminals, radio transcripts, camera timestamps, receipts |

Overlay text is always uppercase. Text inside the world may use normal case.

### 10.2 Vertical layout map (1080 x 1920)

```
y   0% to   7%   platform top bar: no text
y   9% to  17%   HEADLINE, centered, max width 84%
y  18% to  27%   HUD card or part badge, left side (x 6% to 44%)
y  20% to  64%   main stage: faces and key action (subject center near 44%)
y  64% to  73%   SUBTITLES, baseline at 70%, centered, max width 72%
y  74% to 100%   platform bottom zone (title, channel, sound): no text, no faces, no key action
x  86% to 100%,  y 38% to 86%: action buttons: no text, no faces
```

The engine's YouTube Shorts safe zones override these numbers when they differ.
The vertical reference places subtitles at 78% of height, inside the bottom zone; this bible moves them up.

### 10.3 Headline (top)

- Nunito 800, 46 px, letter spacing 0.04em, muted-cream; emphasis word in gold-deep or a meaning color
  (green, coral). Soft glow: text shadow 0 0 18 px in its own color at 35%.
- 1 or 2 lines, at most 5 words. A second line may be 1.3 times larger (reference: "EVERY / SINGLE DAY").
- Content: the beat's key fact (a time, a place, a number, an object) or 2 to 5 words of the current sentence.
  Never information from a later beat.
- In: letters drop in from 0.3em above, staggered 25 ms, `back.out(1.6)`, done within 0.45 s.
- Out: cut with the shot, or fade in 0.15 s.
- Glitch variant: letters swap and scramble for broken signals, corrupted messages, other languages.

### 10.4 Subtitles (lower third)

- Nunito 900, 66 px, white, 6 px outline in #16121A, shadow 0 4 px 10 px at 55% black.
- Karaoke: the word being spoken is gold; the highlight moves word by word on the voice's word timestamps.
- Chunks of 1 to 4 words on one line. Break at sentence ends and commas when possible (the reference uses fixed
  4-word windows that cross sentences; my choice is to respect sentences).
- Chunks switch instantly, no fades.
- Numbers appear the way they are spoken ("TWO HUNDRED TWELVE DOLLARS"), as in the reference, so the highlight
  stays in sync. Digits live in the headline, the HUD and the cards.
- When the background behind the subtitles is brighter than luminance 128, a soft dark gradient band (40%) sits
  behind them.

### 10.5 Dialogue

- Gabry's lines: subtitle text in gabry-orange with the spoken word in white. When Gabry is on screen and the
  line is 6 words or fewer, a speech bubble appears by his head as well.
- Other characters' lines (read by the narrator): white subtitles inside quotes; a speech bubble from that
  character when on screen.
- Speech bubble: paper pill, Nunito 900 34 px in #1A1620, tail toward the speaker, pops in from scale 0.6 to 1.0
  in 0.18 s, lasts as long as the line.

### 10.6 Title cards (time jumps)

- Night background, faint particles, vignette.
- Label: Nunito 800, 30 px, letter spacing 0.3em, cream at 85% ("DAY", "WEEK", "AGE", "MARCH").
- Numeral: Nunito 900, 240 px, gradient gold to gold-deep, glow 0 0 30 px gold at 30%.
- Divider: 280 px by 2 px, cream at 35%, 40 px under the numeral.
- 1.0 to 1.6 s. The numeral pops (scale 0.85 to 1.0 in 0.3 s) or counts up from the previous value.
- Used only for time jumps: "DAY 43", "WEEK 2", "AGE 80", "MARCH 1994", "11:46 PM".

### 10.7 HUD card (the story's numbers)

- Top left (x 6%, y 19%), 380 px wide, padding 22 px, radius 18 px, night fill at 78%, border 1.5 px in
  muted-cream at 35%.
- 1 to 3 rows. Label: Nunito 800, 24 px, letter spacing 0.18em, label-grey. Value: Nunito 900, 58 px, right
  aligned: gold-deep for money and time, hud-cyan for physical stats.
- On change: the value counts to the new number in 0.6 s and flashes money-green on a gain or coral on a loss
  for 0.4 s.
- Shown when a tracked number first matters, then on every change.
- Values must equal the story's `bible.md` (ledger or inventory) at that moment: a review check.
- Entrepreneur rows: CASH, DEBT, ORDERS, DAY. Isolation rows: DAY, FOOD, WATER, BATTERY, TEMP, DISTANCE.

### 10.8 Stamps, strikes, pills, badges, labels

- Stamp: outlined box (6 px), Nunito 900, 72 px, rotated minus 8 degrees, coral for bad (DECLINED, OVERDUE,
  SOLD OUT), money-green for good (PAID, APPROVED); lands from scale 1.6 to 1.0 in 0.18 s with a 6 px shake.
- Strike: a coral 6 px line drawn across the old value, then the new value appears.
- Pill: fully rounded, night fill at 70%, 2 px stroke in an accent with a soft glow, Nunito 800, 26 px.
- Floating badge: a pill above a character's head carrying a number tied to them (a price, a debt, days left).
- Diagram labels: Nunito 800, 22 px, letter spacing 0.08em, cream.

### 10.9 Limits

- At most 3 text blocks at once: headline, subtitles, plus one of HUD, bubble or card text.
- No overlay text smaller than 22 px.

---

## 11. In-world UI library

All apps, brands and logos are invented and generic: never a real one, never a real brand's look.

- Phone: rounded rectangle at 9 by 19.5, corner radius 12% of its width, ink bezel 3%, screen #10141F; held by
  an ink hand from the lower right, with Gabry's orange sleeve when it is his phone; 55 to 70% of frame width.
  Lock screen shows the story's time; notification banners slide in from the top.
- Apps: bank (balance large, green or coral; transaction list), messages (others' bubbles in grey, Gabry's in
  orange), email (sender, bold subject, preview), map (dark land #1B2130, roads #3A4256, water #1D3B57, route in
  cyan, pin in coral), store dashboard (orders, revenue in gold, small cyan line chart), ads dashboard (spent,
  clicks, orders), calendar (alarm-red header band, large ink numeral on paper, page flips), weather, dating or
  social apps when a story needs them.
- Camera feed: frame with a red REC dot and a mono timestamp, light scanlines at 4% opacity.
- Paper: invoice and receipt (paper fill, mono text, bold total), printer strip (mono, perforation dots), letters
  and notes, ID badge, newspaper (invented masthead), contract (lines and a signature line).
- Devices: radio (box, dial, speaker grille, LED), 1920s candlestick phone and cash register, 1990s CRT monitor,
  landline, fax and pager, today's laptop.

---

## 12. Effects

| Effect | Parameters | When |
| --- | --- | --- |
| counter roll | number tween 0.6 to 1.5 s | money, days, distances |
| page flip | CSS 3D rotation, 0.25 s per page | calendars, documents, time passing |
| flicker | light drops to 30 to 50% for 2 to 5 frames, at most 3 bursts per shot | Isolation tension |
| emergency light | alarm-red radial pulse, 1.5 s period | alarms, sirens |
| screen glow | cyan wash plus cold rim on the face | phones, monitors |
| ghost echo | 2 to 4 copies at 15 to 35% opacity, offset in time | loops, memories, deja vu |
| rewind | horizontal streak lines, slight desaturation, reversed motion, mono timer | time effects |
| static | low-opacity noise layer, at most 10% | radio, camera feeds |
| letterbox | black bars at 5% top and bottom | one cinematic sequence per part at most |
| flash | white, at most 3 frames, at most 1 per part | a shock reveal |
| money rain | green rectangles falling and tumbling | windfalls |
| glitch text | letters swap and scramble | broken signals, corrupted messages |

---

## 13. Transitions

- Measured: 95% of the 501 detected changes happen within a single frame. Hard cuts are the default.
- Allowed specials, at most 2 per part: match cut (same shape in the same place), whip pan (0.2 s horizontal
  blur), page flip, rewind streaks, a cut to black for 2 to 6 frames before a shock (Isolation), a 0.3 s dissolve
  for memories and dreams only.
- Never: wipes, spins, zoom transitions, decorative glitch transitions.

---

## 14. Opening and end

- Frame 0 is already the scene, with the headline on screen. Narration starts by 0.5 s (measured in the
  references). No logo, no intro card.
- Part 2 onward: a "PART 2" pill (gold stroke) at the HUD position for the first 2.5 s, during the recap.
- End card, non-final parts (my choice): right after the cliffhanger line, 1.5 s. The last frame dims to 40% and
  blurs; centered, "END OF PART 1" in cream small caps, "PART 2" as a gold title-card numeral, and a coral
  "FOLLOW" pill under it (as in the vertical reference). No voice over it.
- Final part: after the last line, a 1.0 s fade to black, then "THE END" (Nunito 900, 140 px, gold) for 1.5 s.

---

## 15. Render budget

- At most 2 full-frame blur filters per shot; glows are gradients.
- At most 80 particles per shot; at most 12 animated characters.
- Backgrounds use at most 4 depth layers.
- Animate transforms and opacity; never animate filter values.
- Recurring elements come from shared components: the character rig, the UI library, the text system.
- Output 1080 x 1920. The references run at 24 fps; the platform config sets the render rate.

---

## 16. Avoid

- Real brands, logos, app interfaces, landmarks presented as real institutions, real people.
- Photoreal textures, painterly brushes, 3D renders, AI-generated images.
- Gradients with more than 3 stops; drop shadows on everything; glossy or neon overload.
- Overlay text in lowercase, under weight 800, or inside the platform zones.
- Characters under 15% of frame height in story shots (the horizontal references' wide shots are too small for a
  phone).
- Orange on anyone but Gabry; fire or lamps in Gabry's orange.
- Explainer asides (study citations, science diagrams) that do not move the story.
- Blood, wounds, bodies on screen.
- More than 1 flash per part; any strobe.
- Emoji, stickers, meme images.

---

## 17. References

Folder on Gabriele's PC: pending (open item 2). Files, as uploaded:

1. **What_if_you_woke_up_in_the_year_3026...mp4** (Nora frozen in 2026): 16:9, 9:59, 2.65 changes per 10 s.
   - Take: cryo and sci-fi lab interiors (steel cylinders, blue light, haze), scrambled glitch text, the "DAY 20"
     title card and the "you've been asleep" counter card, wireframe globe and dot maps, space shots.
   - Not: the cryonics science asides, the embryo diagram.
2. **What_if_you_could_see_everyones_IQ...mp4**: 16:9, 7:42, 2.53 changes per 10 s.
   - Take: dusk city streets full of characters, floating number badges above heads, invented phone apps
     (search, a dating app), the classroom set, night-room lighting with a window beam.
   - Not: statistics lectures (bell curves, score charts), a real court building.
3. **You_wake_up_and_there_s_1000000_in_your_account...mp4**: the only vertical Short, 1:00, 3.02 changes per 10 s.
   This is the layout model.
   - Take: headline at the top, karaoke subtitles with gold word highlights, DAY, WEEK, MONTH and YEAR title cards,
     counter rolls, stamps and strikes, calendar page flips, the bank app, the phone held from the lower right,
     joyful face close-up, money rain, the "PART 2" plus "FOLLOW" end card.
   - Not: subtitles at 78% of height (inside YouTube's bottom zone), fixed 4-word subtitle windows across
     sentences, the spoken "Follow for part 2", the announced cliffhanger ("a problem nobody warns you about").
4. **What_if_you_woke_up_tomorrow_as_a_perfect_10-10...mp4**: 16:9, 7:24, 1.71 changes per 10 s.
   - Take: everyday social scenes (street, office, kitchen, park bench), framed portraits and polaroids, outlined
     pill lists, app grids, candidate-card UI with bars, sunsets with sun glow, window light beams.
   - Not: face-rating themes, study citations.
5. **What_if_you_could_rewind_time_by_exactly_10_seconds...mp4**: 16:9, 7:23, 1.67 changes per 10 s.
   - Take: the rewind effect (streaks, reversed motion, timer), ghost copies for repeated moments, big face
     close-ups with rim light and changing expressions, the stage with curtain, spotlight and audience heads,
     crossed-out labels.
   - Not: "science agrees" boxes, node diagrams about research.
6. **What_if_you_aged_backwards...mp4** (Sam born at 80): 16:9, 6:10, 1.54 changes per 10 s.
   - Take: the stat card (AGE and BODY) that becomes the HUD, aging cues (white hair, glasses, cane, lean), the
     hospital room with a heart monitor, bookshelf and candle interiors, the memory wall of photos, the START to END
     road timeline, letterboxed moments, framed memory scenes.
   - Not: biology diagrams (cells, jellyfish, lab mice).

All six share one production system: the same character design, palette, type, mix and loudness. They read as
one channel, and this bible keeps that consistency.

---

## 18. Sound and narration in the references (measured)

| Video | Narration pace | Mean sentence | Short sentences (4 words or fewer) | Narrator pitch (median) |
| --- | --- | --- | --- | --- |
| 1 (year 3026) | 2.35 words/s | 7.1 words | 38% | 121 Hz |
| 2 (IQ) | 2.36 words/s | 6.9 words | 37% | 129 Hz |
| 3 (million, Short) | 2.35 words/s | 6.7 words | 48% | 138 Hz |
| 4 (perfect 10) | 2.62 words/s | 9.8 words | 20% | 137 Hz |
| 5 (rewind) | 2.67 words/s | 7.6 words | 25% | 136 Hz |
| 6 (aged backwards) | 2.37 words/s | 5.7 words | 50% | 132 Hz |

Measured on the first 150 s of each long video and the whole Short.

- Pace: 2.45 words per second on average. At that pace, 90 to 120 s holds 220 to 295 words.
- Sentences: mean 7.2 words, median 6, 90% at 14 words or fewer.
- Voice: one adult male narrator, the same pitch range in all six (median 121 to 138 Hz).
- Point of view: second person, present tense, even with a named protagonist ("Your name is Nora.",
  "Your name is Sam.").
- Structure: time markers as sentences ("Day 1.", "Week 1.", "Age 5."), concrete numbers, the narrator reads all
  dialogue.
- Mix: a continuous bed, never silent; in the pauses it sits about 18 to 20 LU under the voice. Every video is
  mastered to the same integrated loudness, -17.1 LUFS.
- What the bed is (music, ambience) and how sound effects are used cannot be measured from the files: open item 3.

---

## 19. Changes this bible makes to other files

To apply when the profile is finalized:

1. `scenarios.md` 7.10 and the storytelling pacing line: "a visual change every 3 to 5 s" becomes section 9 of
   this bible (a new beat every 2 to 4 s, a cut every 3 to 4 s on average).
2. `voice.md`, numbers: subtitles show numbers as spoken words; digits appear in the headline, HUD and cards.
3. `voice.md`, sentences: average sentence 9 words or fewer (was 12) and at least 25% of sentences at 4 words or
   fewer, closer to the references (7.2 average). The 22-word maximum stays.
4. `storytelling.md` and `scenarios.md`: the word window becomes 220 to 295 words per part (2.45 words per second
   measured in the references), until Kokoro's own pace is measured.
5. Engine requirements: word-level timestamps from the voiceover (for karaoke subtitles and word-synced cuts), and
   vendored fonts (Nunito, Inter, IBM Plex Mono).
6. `channel.json`: `config.style` = `inkhead`; `sources.refs` = the folder with these six videos.

---

## 20. Open items

1. Gabry's hair silhouette: the proposed quiff, or Gabriele's own (from photos). The rest of section 5 holds
   either way. Also confirm the signature orange.
2. The Windows path of the folder with the six reference videos.
3. One line on the references' sound: what the bed is (music, ambience), whether you like it, and how sound
   effects are used.
4. Spoken call to action: the vertical reference says "Follow for part 2" after the cliffhanger. Current choice:
   on screen only, so the cliffhanger is the last thing heard. Keep it, or add the spoken line?
