# M15 Kinetic captions and text discipline: report

Spec: BUILD_SPEC.md section 5, Motion and energy rules E3 (captions) and E4 (text discipline), section 12 (M15), the lines marked (M15)
in S7, S9, S10 and S12. Decisions: DECISIONS.md 306 to 312. Test: `bash pipeline/tests/test-m15.sh` (no model call).

## What was built

- **Two caption components on pc-motion.js**, replacing caption-line:
  - `motion-lib/compositions/caption-word.html` (word mode): one word at a time on its spoken word time, centered at the
    style's caption position; a fade with a small zoom (the combined main animation, shortened for a word that lives a few
    frames), and a rise of 8 to 16 px (or a turn of 2 to 4 degrees) over the word's whole life so it is never static; emphasis
    words in the serif italic at 1.4 times the caption size on the accent box.
  - `motion-lib/compositions/caption-group.html` (group mode): draws a layout it is given: each word on its spoken time with E2's
    combined animation at word scale (a rise, a zoom from 0.85, a parallax rotation), the whole group moving as one block (a rise
    of 20 to 40 px or a parallax turn of 3 to 6 degrees) and leaving together.
  - caption-line.html moved to `motion-lib/retired/`; catalog.json lists caption-word (vocabulary item 7) and caption-group,
    the beat map's "any" list names both, frame-match expectations and the gallery cover them.
- **`pipeline/lib/visual/kinetic.py`**, the deterministic group layout engine: word roles (anchor, secondary, connector), fonts
  (the anchor in the heavy grotesk, the others cycling through the serif italic, Caveat and Space Grotesk: 3 words show 3 fonts),
  the anchor at 3.0 down to 2.0 times the caption size, two words stacked beside it at half its size (their lines as tall as
  the anchor within 2 px), words before the anchor on a row above, the rest on rows below offset to the other side, the block
  leaning to one side of the group caption zone, the right-rail rule per word, splitting a group that does not fit
  (`layout_groups`), keeping clear of graphics on screen (`avoid`), `check_layout` and `check_motion` (what the validator
  reads), `group_runs` (a beat's words into groups of 2 to 6), `python pipeline/lib/visual kinetic "the quick brown fox" --anchor 0
  --png out.png`. tokens.json gained `motion.grammar.captions.group_zone` (the hero zone between the margins) and the caption
  words' limits.
- **S7**: every beat carries `importance` (hook, key-claim, number, payoff, pre-ask, normal): the model may propose it, the
  code fixes the structural ones (`script_checks.derive_importance`); schema, prompt and contract updated.
- **S9a, S9b**: the 9b answer may say `mode` (word or group) and `anchor` per chunk; `plan9.finalize_captions` applies the choice
  rule (word mode under any text, groups where the hero zone holds no text and the beat is important or has no graphic), re-cuts
  the pipeline's own groups, lays every group out with kinetic.py and sets every entry's motion; the digest lists each scene's
  importance, text and graphics and the pipeline's own choice; the 9a and 9b prompts state E3 and E4. The plan schema's caption
  entries gained mode, importance, anchor, layout and motion (the 9b pass schema is regenerated).
- **Plan validator** (visual/plan_validate.py): `caption_modes` (word mode under any text, no group over text or a graphic, the
  layout's fonts, sizes, zone, rail, asymmetry, every caption moving, one mode at a time), `text_budget` (100 characters of
  non-caption text at any moment, the CTA aside), `text_size` (no graphic text under the caption size: an error for a size the plan
  chooses, a warning for the sizes the library bakes in).
- **S12 mechanical** (review/mechanical.py, common.py): a group word is judged in the group caption zone; `caption_mode` (a
  group on screen with other text), `text_budget` (rendered characters), `caption_static` (two samples inside a word's or group's
  life), the baked text sizes as `warnings`; check times for every group; the emphasis check finds a phrase by its first word,
  a word of a group, and a short word-mode word (DECISIONS.md 312).
- **Golden plan**: its number and payoff beats lost their cards and chips so that the voice's important lines run as caption
  groups; the other beats stay word mode. golden/test-idea/plan.json and project/ were regenerated.
- **Earlier milestones touched** (M15 depends on them): M6 (script_checks.py, the S7 schemas and prompts), M9 (tokens.py,
  catalog.py, expectations.py, golden.py, goldenplan.py, captions.py; test-m9's golden caption check), M10 (plan9, plan_validate,
  common; the frozen run's four plan files lost the terminal card's `font_px: 28`, which E4 rejects, and its project
  index.html and instances.json were regenerated), M11 (mechanical.py, review/common.py; test-m11 asserts caption-word.html).

## Files

New: pipeline/lib/visual/kinetic.py, motion-lib/compositions/caption-word.html, caption-group.html, motion-lib/retired/caption-line.html
(moved), pipeline/tests/test-m15.sh, m15-mkrun.py, m15-frames.py. Changed: pipeline/lib/{tokens.py, script_checks.py},
pipeline/lib/visual/{common.py, plan9.py, plan_validate.py, __main__.py}, pipeline/lib/motion/{captions.py, catalog.py,
expectations.py, golden.py, goldenplan.py}, pipeline/lib/review/{mechanical.py, common.py}, pipeline/stages/{07-script, 09-plan,
09a-animations, 09b-text, 12-review} (schemas, prompts, contracts), styles/paper-cards/tokens.json and motion-lib/assets/tokens.css
(regenerated), motion-lib/{catalog.json, index.html, gallery/}, golden/test-idea/, pipeline/tests/{test-m9.sh, test-m11.sh,
fixtures/runs/test-idea/...}, CLAUDE.md, DECISIONS.md, build/progress.md, build/HUMAN_TODO.md.

## How to run the test

`bash pipeline/tests/test-m15.sh` (no model call, about 15 to 20 minutes); `M15_SECTIONS="1 2" bash pipeline/tests/test-m15.sh`
is the quick part (about 2 minutes).

1. kinetic.py: "the quick brown fox" as spec E3 (three fonts, "quick" and "brown" at half the anchor's size, their combined height
   within 2 px of the anchor's, top aligned, asymmetric, inside the zone, clear of the rail), six long words fit or split, 300
   generated lists sound with no word under the caption size, group_runs, the motions, seven planted layout faults.
2. The plan rules: the golden plan passes; planted faults (120 characters, a 40 px label, a group over text, a group over a
   graphic, a static word, a static group, two fonts, a word under the caption size, no layout, overlapping modes) are caught; the
   9b choice rule on the frozen words with the golden scenes; a director's group over text refused and one in a free beat kept
   with its anchor; the digest; S7's importance; the schemas.
3. The golden reel: word mode in normal talk, groups on the number and payoff beats, none under text, and every caption word and
   group moving on every frame it is on screen (the compositions seeked frame by frame in the browser harness: about 1400
   element frames, none static); a planted static caption fails that check.
4. S12's mechanical checks on the compiled golden project: clean; planted copies are caught and tagged [text] (a group on screen
   with a chip's text, 142 characters, a static word, a static group).
5. The library: catalog, frame-match of the two components, `npx hyperframes lint` and `check` on motion-lib/.
6. No em dash.

## Test results

(see the end of this file: filled in when the runs finished)

## Known gaps

- E4's minimum text size (67 px) is a warning for the library's baked sizes (cards 44 px, chips 28 to 30, terminal lines 30):
  the library was built to the style's own sizes and cannot meet it without a redesign; the switch is `visual.text_size_baked` and
  `review.text_size_baked` (DECISIONS.md 308, HUMAN_TODO).
- Real reels will show caption groups rarely until the director leaves hero zones without text (the 9a prompt now asks for it;
  M16 builds the rest of the director's prompts and the energy loop).
- The look of the groups (their size is capped at 3 times the caption size, so a group fills about half of the hero zone's
  width) and the rise and turn amounts were not judged by eye on a finished reel.
- S12 samples a word's motion only when it lives 0.6 s or more (shorter words cannot stand still for E1's 0.5 s; the plan
  validator refuses a zero motion); the frame-by-frame check of test-m15 covers every word.

## HUMAN_TODO items added

- M15: the library's baked text sizes against E4's minimum (decide, then switch the config keys).
- M15: look at the kinetic captions on the rebuilt golden reel.
- M15: real reels show groups rarely until M16's director prompts land.
