# M11 Sound effects pass and review loop (S11, S12): build report (2026-11-01)

## What was built

1. **S11, the sound effects pass** (pipeline/stages/11-sfx/run.sh over the package pipeline/lib/sfx/, run by hand with
   `bash pipeline/bin/mix-sfx <run_dir>`; no model). The events of the built visuals (10-build/events.json) get their cue
   types by the spec's rules (assign.py: hook_hit on the hook's set piece, notification on the DM card, typing, success,
   negative; transition_slow or transition_fast on every scene change by the transition's length and the next beat's
   calm; one hero_enter per scene, at its landing when its enter sits on the scene change; ui_click on chips; attention
   whooshes in silent gaps of over 6 s at random 8 to 12 s intervals, never in the first 2 s or during the ask; at most
   4 hits in any 10 s, never two sounds within 250 ms, nothing on the hook's first word but hook_hit; accepted by priority
   so the trimming keeps the spec's order, every dropped candidate listed with its reason). Files come from the memory
   map's pools in a seeded rotation (pick.py: never the same file twice in a row, the last 2 reels' picks avoided through
   logs/sfx-usage.json, a checklist's ticks share one file). Placement (place.py) puts a whoosh's measured peak on the
   event and every other sound's onset on it, trims typing to its segment and cuts tails 50 ms before the next sound with
   a 30 ms fade; levels (level.py) add the cue type's base gain to the map's normalization and cap every sound 8 dB
   under the voice's peak around the moment. The stem and the mix are rendered in numpy (render_stem.py), then verified
   on the rendered files (verify.py): every sound within 33 ms of its event (the plateau of a whoosh, the onset or the
   strongest rise of the rest), no unplanned sound, the 8 dB rule, -14 LUFS plus or minus 1, true peak at most -1.5 dBTP;
   a failure is corrected (offsets, gains, the stem's level, a limiter on the mix last) and verified again, up to 3
   passes, then the review path. Outputs: cues.json, sfx_stem.wav, mix.wav, draft_mixed.mp4, sound-map.txt, and the hook
   2 clip's cues, stem and mix. No map or an empty one: the voice alone plus a NEEDS REVIEW flag. The stage refreshes
   the map at its start (bash pipeline/bin/build-sfx-map, a no-op when nothing changed).
2. **S12, the review and fix loop** (pipeline/stages/12-review/run.sh over the package pipeline/lib/review/, the editor's
   prompt pipeline/stages/12-review/prompt.md with model.schema.json). One round: the mechanical checks
   (mechanical.py: the built composition's hosts read from 10-build/project/index.html and opened one by one in M9's
   Playwright harness at every beat settled and middle, every emphasis hit, every landing and the built CTA; every
   visible text leaf measured with its glyph box, font, size, color and the pixels behind it; the zones with the caption
   band exception, the right 230 px of the lower half, the fonts and sizes, overlaps and off-canvas, contrast 4.5:1 with
   2.7:1 for the style's accent words, every emphasis within 80 ms of its word from the caption line's own events, and
   the branding rules: the CTA's lockup at 300 px or more and the DM avatar at 112 px or more, no FlashFX logo outside the
   CTA unless the solution is flashfx, every logo a brand.json file drawn with its aspect ratio locked, its variant
   matching the luminance of the surface measured behind it with the logo hidden, readable at 3:1, the bolt at 64 px or
   more, clear space of a quarter of the bolt's height); the style conformance check (style_check.py:
   tools/analyze_refs.py on the mixed draft, the hero zone's gap median and maximum within the references' range plus or
   minus 20 percent, at least 90 percent of the non-image pixels within delta E 5 of a token color, the accent share
   under 5 percent of every frame with the logos excluded, the loudness); the audio checks (audio_check.py: S11's
   verification, the voice transcribed from the mixed draft with faster-whisper and compared with words.json, WER under
   5 percent); the edit review by a fresh qa session (edit.py: the contact sheet, a 10 fps filmstrip of the hook and one
   per transition, three stills of the look references, the scene table with the sounds beside it and sound-map.txt;
   eight scores 1 to 5, whether the branding feels natural, tagged issues); the verdict (route.py: pass when every check
   passes and every score is at least 4; otherwise every issue goes back to the step its tag names, [voice] S8,
   [animation] 9a, [text] 9b, [transition] 9c, [sfx] S11, the earliest owner reopened with every stage after it and the
   review itself; 3 opus rounds then 2 fable rounds, then the export with a NEEDS REVIEW flag that carries the notes; a
   [voice] issue routes only when it names a word in quotes, else it is a flag). The re-run passes read
   12-review/feedback.json: the three director prompts gained a {{REVIEW}} section, S11 picks fewer, softer or other
   sounds, S8 respells a named word. A result cache keeps an [sfx]-only round from repeating the visual checks.
3. **The activities and lines** of the spec: "adding sound effects (17 sounds)", "verifying sound sync and loudness",
   "reviewing: mechanical checks", "reviewing: style check", "reviewing: audio check", "reviewing: edit review (round
   1/5)", "fixing [text] issues (round 2, opus)", "fixing [sfx] issues (round 4, fable)"; the S11 and S12 INFO and WARN
   lines; the FLAG line of a capped review.
4. **The test** pipeline/tests/test-m11.sh with the fake editor's answers (pipeline/tests/fixtures/fake/m11,
   m11-text, m11-sfx), pipeline/tests/materialize-project.py (the frozen project folders rebuilt from the plans, the
   drafts rendered when the mp4 files are missing) and `sandbox_init --with-review`.

## Files

- pipeline/lib/sfx/{assign,pick,place,level,render_stem,verify,audioio,mixsfx}.py, pipeline/bin/mix-sfx
- pipeline/stages/11-sfx/{run.sh,schema.json,CONTRACT.md,dummy.sh}
- pipeline/lib/review/{__init__,__main__,common,mechanical,style_check,audio_check,filmstrip,edit,route}.py
- pipeline/stages/12-review/{run.sh,prompt.md,model.schema.json,schema.json,CONTRACT.md}
- pipeline/tests/test-m11.sh, pipeline/tests/materialize-project.py, pipeline/tests/fixtures/fake/{m11,m11-text,m11-sfx}/,
  pipeline/tests/fixtures/runs/test-idea/10-build/{draft.mp4,hook2.mp4} (rendered again, not in git) and contact-sheet.png
- Earlier milestones touched (M11 depends on them): motion-lib/compositions/caption-line.html (M9: every caption chunk
  was scaled to 60 percent, found by the new mechanical check; the fix is one width measurement) and card.html (a logo in
  a card's image slot keeps its aspect ratio), golden/test-idea/project/compositions (the same two files),
  pipeline/lib/state.py (M2: a stage may reopen itself), pipeline/lib/visual.sh and the 09a/09b/09c prompts (M10: the
  review notes, the escalated director), pipeline/lib/voiceover.py (M7: the review's quoted words respelled),
  config.json (M1: sfx.*, review.*, four timeouts, models.visual_director_escalation; rewritten by json.dumps),
  pipeline/tests/lib.sh (M1: --with-review)
- DECISIONS.md 234 to 260; build/progress.md; build/HUMAN_TODO.md; CLAUDE.md; build/M11/patch-1.py, patch-2.py,
  patch-3.py, patch-claude-md.py (the patches to earlier files, kept as a record)

## How to run the test

`bash pipeline/tests/test-m11.sh` (30 to 45 minutes; section 4 calls the real qa editor once and the real faster-whisper).
`M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh` runs the fake-only sections. `M11_FREEZE=1` makes section 4 copy
the real 11-sfx and 12-review JSON outputs into pipeline/tests/fixtures/runs/test-idea/ (the inputs of M12).

## Test output (summary)

```
== 1. units ==   89 PASS, about 8 minutes
   (S11 on the frozen build: 17 sounds from 40 candidates (9 mandatory, 8 transitions), 23 dropped with their reasons;
   every mandatory cue present; spacing, density, first-word and ask rules; every file from its pool; the rotation;
   every sound within 10 ms of its event on the rendered stem after one correction, no unplanned sound; the closest
   sound 7.2 dB under the voice cap; the mix -14.35 LUFS, -1.6 dBTP; one sound-map.txt line per cue; the usage log;
   the hook 2 clip's hook_hit. The detector catches a sound 80 ms off and a planted 250 ms burst. An [sfx] note changes
   the seed, lowers the density to 3 per 10 s and every sound by 7 dB. No map: voice only plus the FLAG line. The
   mechanical checks pass on the clean draft (397 text boxes at 75 times, 25 of 25 emphasis hits within 80 ms, the
   lockup 300 px on a light surface, the avatar 120 px with its bolt at 69 px); the style check passes (hero-zone gap
   median 1.03 s in the references' 0.26 to 1.56 s, palette 98.6 percent within delta E 5, accent 2.9 percent at most,
   loudness); the audio check passes (fake whisper, WER 0). The planted copy fails on every planted fault: brand_outside,
   brand_variant and brand_contrast (the black lockup on the dark window), brand_stretched, brand_small, brand_cta,
   right_rail, zone. The routing units: pass, [text] to 09b with the reopen list and the activity, a failing code check
   routes by its tag, a [voice] note without a quoted word becomes a flag, a quoted word reopens S8, fable after the
   opus rounds, the cap, an ad-feeling branding as [animation], the notes a re-run pass gets. The dummies validate.)
== 2. S11 and S12 through the runner with the fake editor ==   110 PASS, about 11 minutes
   (the pass: the run resumes at S11, 17 sounds, S12 round 1 of 5, the three code checks ok, the round passes with the
   editor's scores, one model call, the activities, review.json, the filmstrips, the prompt with the sound map, the
   contact sheet, the hook strip and the reference stills, the export. The planted [text] issue: round 1 fails naming
   09b-text, S12 hands over to 9b, the text pass runs again with the review's notes (the prompt quotes the issue, the
   transitions pass gets the context note), then 9c, the build, the sounds, round 2 passes, the export with one issue
   fixed; four model calls; every reopened stage counted once, 09a untouched; rounds.review 1; the second draft and the
   second sound pass.)
== 3. the cap ==   28 PASS, about 5 minutes
   (rounds 1 to 4 fail and go back to S11, round 5 ends the loop, the FLAG line with the scores and the open [sfx]
   issue, the export; five editor calls; the activities "fixing [sfx] issues (round 2, opus)" to "(round 5, fable)";
   rounds.review 5, S11 and S12 reopened four times, the build never; the sound pass applied the editor's note; the
   unchanged composition's checks came from the cache; the export's NEEDS REVIEW block carries the notes.)
== 4. the real editor and the real transcription ==   26 PASS, about 5 minutes, 1 model call
   (S11 plus S12 in 257 s; the editor answered: scores stop 3, hierarchy 3, look 4, variety 3, sync 4, sound 4,
   generic 3, requirements 3, 16 tagged issues, verdict fix; the mechanical checks pass on the frozen draft, the
   branding checks included; the style check passes; the voice is intelligible in the mix with the real faster-whisper
   (WER 0.0 percent); the 11-sfx and 12-review outputs frozen under pipeline/tests/fixtures/runs/test-idea/)
== 5. no em dash in the files M11 wrote ==   1 PASS
test-m11.sh: 254 passed, 0 failed (the sections run separately, about 30 minutes in all)
```

After M11 the other milestones' tests were re-run where their code changed: test-m1.sh 96 passed, test-m2.sh 220 passed,
test-m7.sh's fake sections 116 passed, test-m9.sh 80 passed (it rendered the golden reel again with the fixed caption
line), test-m10.sh's fake sections 134 passed, and the repository-wide em dash scan passes.

## Known gaps

- The spec's density rule is read with two refinements (DECISIONS.md 235): typing beds do not count as hits and a
  checklist's ticks count once; with the literal reading the test idea lost its typing bed and two scene changes to
  three dings. On this reel the transitions and the mandatory cues fill the 4-per-10-s budget, so no hero pop survives.
- Nobody has heard the result: the picks come from the map's measurements and names; the levels from the spec's rule.
  The HUMAN_TODO asks for one listen with sound-map.txt open before the first real export.
- The verification's "no unplanned sound" is span-based: a stray sound inside the quiet tail of a planned whoosh would
  not be told apart. The renderer never produces one; the rule guards against placement bugs, not against the files.
- The mechanical checks judge each host in its own mount (the same mount S10 verified the events in): a text whose
  background is another host's element (none in this style: chips and cards carry their own fill, captions sit on the
  paper) would be measured against the paper.
- The style check's cadence compares the middle screen band with the references' summary.json files; the analysis
  folder is not in git, so another machine falls back to tokens.json's pacing numbers with wider bounds.
- The editor cannot watch the video: it judges stills and filmstrips, as the spec says. Its taste is the prompt's; the
  first real round scored the test idea (section 4) and the loop around it is exercised with fake verdicts.
- The S10 builder escalates at 2 failed review rounds (M10's reading) while the director escalates at 3 (the spec's
  S12 caps); both are config.
- A [voice] issue only reaches S8 when it names a word in quotes; S8 respells it with the voiceover's auto_respell,
  which may or may not change what the voice does with it.
- The real editor's call in section 4 is the only real-model exercise of the prompt; the fix rounds with real director
  calls (a real [text] issue flowing into a real 9b re-plan) are exercised with the fake director's fixtures only.

## HUMAN_TODO items added

- Listen to one mixed draft with sound-map.txt open before the first real export; the levers (overrides.txt, config
  sfx.base_gain_db).
- The caption line's 60 percent bug and bash pipeline/bin/render-golden to refresh the golden reel's captions.
- What the editor does, where its notes are, and the levers (the prompt's How to judge section, config review.*).
- The sound map's refresh at the start of every sound stage (one indexer call when new unclear files appear).

## Earlier milestones touched

M9 (caption-line.html, card.html and their copies in the golden project), M10 (visual.sh, the three director prompts),
M7 (voiceover.py), M2 (state.py, the 11-sfx dummy), M1 (config.json, tests/lib.sh), the M10 fixtures (the drafts and the
contact sheet rendered again after the caption fix). No stage of M3 to M6 and M8 changed.
