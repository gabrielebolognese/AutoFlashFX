# 09a-animations: Visual plan, animations pass (S9a)

Built in M10 (the folder, schema skeleton and dummy date from M2). Spec: BUILD_SPEC.md section 5, S9 9a; the
decisions in DECISIONS.md 215 to 232.

## Purpose
One scene per script beat with its components from the motion library (never anything else), their props, the
spoken word each one lands on, the hook's set piece inside the breath, emphasis hits, honesty labels, and the
branding that follows the reel's solution. A fresh visual_director session designs; pipeline/lib/visual/plan9.py
composes and pipeline/lib/visual/plan_validate.py checks.

## Inputs
- 07-script/script.json, 08-voiceover/words.json (and words_hook2.json for hook 2's headline)
- 02-expansion/solution.json when it exists (a run without it counts as not FlashFX), 01-research/assets.json and
  assets/ (the screenshots the plan may show as research/<file>)
- styles/paper-cards/{style.md,tweaks.md,vocabulary.md,tokens.json}, motion-lib/catalog.json (with the stills),
  golden/test-idea/{plan.json,contact-sheet.png}, library/brand/brand.json
- the prompt digests the stage writes into 09a-animations/digest/ (timeline.md, catalog.md, golden.md, assets.md,
  solution.md)

## Outputs (in runs/<id>/09a-animations/)
- plan.json is the primary output: the stage is done when it validates against schema.json (generated from
  pipeline/stages/09-plan/schema.json by pass-schemas.py) and the runner has written .done. An answer the
  composer or the validator rejects gets one retry in the same session with the exact errors; after that the
  stage fails (exit 1: the review and fix path).
- plan.json: pass animations, plan_version, idea_id, duration_ms (the voice's length), solution, branding
  (cta_scene, dm_avatar, lockup, brand_slot, flashfx_allowed_outside_cta), scenes[] (id, beat, beat_type, start_ms,
  end_ms snapped to words.json, set_piece, hook_set_piece, honesty_label, emphasis_hits, components[] with id,
  component, start_ms, end_ms, props, role, at, land_ms, assets), hook2 (kicker, lines), wishlist, notes.
- plan.candidate.json when an answer was rejected (what the model answered, composed), prompt.md, prompt-retry.md,
  calls/ with the raw answers, digest/.
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).

## Invariants (pipeline/lib/visual/plan_validate.py, parts scenes)
- components only from motion-lib/catalog.json (approved), with declared props; one scene per beat in order; scene
  windows are the beats' windows of words.json; every component start is a word boundary (or the breath lead)
- the first visual change within tokens.json pacing.first_change_max_frames; a visual change lands inside the
  hook breath; no gap over pacing.gap_max_s; at least config visual.min_distinct_components distinct components;
  never the same hero component more than visual.max_same_in_a_row scenes in a row; each beat type uses only
  tokens.json beat_map components; 3D only in the hook and the end card, at most 2 objects; 1 to 2 set pieces
- zones: side margins, the hero zone's top, nothing under the safe bottom but the CTA's DM card, no text in the
  right 230 px of the lower half
- the Motion and energy rules E8 (M16; config visual.energy_rules error | warn | off; the numbers in tokens.json
  motion.grammar.composition): hero_motion (a content component of at least 120000 px2 inside the hero band y 640 to 1280 for 70
  percent of every scene), hero_fill (the scene's content spans 70 percent of the width), layers (2 or more elements together for
  60 percent of the scene, a fan, grid or swatch row counts as two), camera (a camera-move, a screenshot-zoom with focus points or a
  3D object in at least floor(scenes / 3) scenes), hook_frame0 (a hook element starts within 4 frames: the pipeline moves a late hero
  to the scene's start itself), empty_paper (no stretch over 1 s without content in the hero band), list_entry (no more than 2
  cards of one kind one after another in one spot), and the warning real_motion (recordings exist and no video-card plays one)
- real assets only for real claims: research/<file> exists (a recording is research/<file>.mp4 in the video prop of a video-card); a stat-number's value is in the script or numbers.json;
  mock UI carries honesty mock
- branding (tweaks.md): the CTA always has the dm-card with brand/mark/avatar-dark.png and the end-card with a
  lockup from brand.json (300 px or more); no brand/ asset outside the CTA unless the solution is FlashFX; every
  logo path is in brand.json with a use_on matching its surface; the brand slot is the bolt (FlashFX), the tool's
  logo (research) or the neutral icon

## Exit codes
0 done, 10 drop, 20 block, anything else a code error (BUILD_SPEC.md 4.2).

## Model and session
Fresh visual_director session per pass (config models.visual_director, opus, for the first plan; models.visual_director_fix, sonnet, when the pass runs again after a failed review round; models.visual_director_escalation from caps.review_rounds_opus failed rounds on: opus, fable only on an idea marked [important]; DECISIONS.md 334 and 335), tools config visual.director_tools
(Read, Glob: it may look at the stills, the contact sheet and the screenshots), timeout timeouts.plan_seconds.

## dummy.sh
`bash pipeline/stages/09a-animations/dummy.sh <run_dir>` writes a small valid plan (no model, no library needed) and
honors the planted REELS_DUMMY_* lists (pipeline/lib/dummy.sh).
