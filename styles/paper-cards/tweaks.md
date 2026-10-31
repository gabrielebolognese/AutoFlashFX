# tweaks.md (look: paper-cards)

Drafted from the look reference. Edit freely: every line in this file overrides the references.

## Which reference wins
- Look (colors, fonts, cards, captions, tracker, layout): `refs/look/` only.
- Motion (timing, easing, transitions, set pieces): `refs/motion/` wins over the look reference.
- If a motion reference uses colors, fonts or layouts that don't match style.md, take only its motion.

## Decisions (where the reference and the pipeline rules disagree)
- **Caption box:** stays at y 1480 like the reference, even though the repo's safe zone stops at y 1440.
  The safe-zone check treats the caption band as an allowed exception.
- **Right side:** cards may span the full width (60px margins) like the reference, but no text in the
  right 230px of the lower half, where Instagram's like, comment and share buttons sit.
- **Length:** list and explainer videos may run 45 to 75s like the reference. Everything else stays 25 to 40s.
- **Brand mark:** Claude's asterisk only when the video is about Claude. Otherwise my own mark,
  or the logo of the product the video is about.
- **3D:** hook and end card only, at most 2 objects on screen.
- **Accent:** under 5% of any frame.

PROPOSED lines below come from version 2 of style.md (look refs v01 and v02, motion refs v03 to v09).
None of them is in force until you remove the word PROPOSED. Evidence for each is in analysis/sources.md.

- PROPOSED **Caption position:** the version 2 look refs have no caption box and put the caption cap center
  at y 1327 (v01) and y 1337 (v02); the lowest emphasis box ends at y 1380. That is inside the safe zone, so
  the y 1480 exception above is no longer needed. Proposal: captions at y 1332 (the median of the two) and
  drop the exception. Until you accept this, style.md follows the Caption box line above.
- PROPOSED **Right side, captions:** both look refs center wide caption chunks (v01's widest, at 0:10.8, runs
  942px from x 75 to x 1016), so words land in the right 230px of the lower half; v01's stat pills also put text
  there (unit word to x 916 at 0:09.8). Proposal: keep the Right side line above and cap a centered caption
  line at 620px (x 230 to 850). At the 67px caption size a 3-word chunk fits (v01 0:06.2 is 368px);
  long 4-word chunks have to split.
- PROPOSED **Hook header:** v01 starts the kicker at y 171, above the safe line at y 230; v02 starts it at
  y 253. Proposal: use v02's y 253 so the kicker and headline stay inside the safe zone.
- PROPOSED **Length:** the look refs run 42.1s (v01) and 49.6s (v02); v01 falls between the two bands of the
  Length line above (over 40s, under 45s). The motion refs run 43.8s to 72.6s. Proposal: list and explainer
  videos 40 to 75s; everything else 25 to 40s.
- PROPOSED **Accent-filled cards:** v01 goes over the 5% accent cap with an accent-filled card (7.0% of the
  frame at 0:24.0) and on its end card (5.2% at 0:35.0). v02 peaks at 4.8%. Proposal: keep the cap and
  limit any accent-filled card, the end-card keyword pill included, to 100,000 px of area (for example
  600 x 165).
- PROPOSED **3D:** the look refs use no 3D objects, but draw flat cards in perspective in most scenes
  (tilts, fly-ins from near the camera). Proposal: the 3D line above applies to 3D objects (models,
  extruded logos); flat cards in CSS perspective are allowed in every scene.

## My additions (fill these in)
- [ ] Fonts: exact names, if different from the suggestions in style.md
- [ ] Sound effects: e.g. soft click on each element enter, whoosh on scene change, or none
- [ ] Music: none (like the reference) or a low bed
- [ ] Moves to copy exactly from the motion refs: file + timestamp + what
- [ ] Things to never do:
