# 11-sfx: Sound effects (S11)

Built in M11 (the folder set, the first schema and dummy.sh came from M2). Spec: BUILD_SPEC.md section 5, S11;
DECISIONS.md M11.

## Purpose
Attach sounds to the events of the built visuals (not to the plan, so the timing is exact): cue types by the
deterministic rules of S11 (mandatory cues, slow or fast transitions, one hero sound per scene, ui clicks, attention
whooshes in silent gaps, the density and spacing rules, nothing on the hook's first word but hook_hit), files from the
memory map's pools in rotation, placement by peak (whooshes) or onset (the rest), levels under the voice, the stem and
the mix rendered, verified and corrected. No model. Code: pipeline/lib/sfx/{assign,pick,place,level,render_stem,
verify,audioio,mixsfx}.py behind pipeline/bin/mix-sfx.

## Inputs
- 10-build/events.json (every event in absolute ms, with the catalog's cue suggestions), 10-build/plan.json (the
  compiled plan: the hook's set piece, the scenes' beat types), 10-build/draft.mp4 (the silent 540x960 draft)
- 08-voiceover/vo.wav (48 kHz mono, -14 LUFS), 08-voiceover/words.json (the first word, the ask beat)
- for the hook 2 clip: 10-build/hook2/ (its project and plan.json), 08-voiceover/vo_hook2.wav and words_hook2.json
- styles/sfx/sfx-map.json and the cache copies styles/sfx/.cache/ (REELS_SFX_DIR points at another pack folder in
  tests), config sfx.* (base gains, density, spacing, the voice rule, the attention interval, the slow transition
  threshold, the sync tolerance, calm_beats, verify_passes), logs/sfx-usage.json (the last reels' picks)
- 12-review/feedback.json when the edit review routed [sfx] issues here (the next round picks other files and, when the
  review found the sounds cluttering or loud, fewer and softer ones)

## Outputs (in runs/<id>/11-sfx/)
- cues.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done. Fields: seed, counts, cues[] (id, cue_type, group, ms, the event it sits on, file, placement:
  reel_start_ms, offset_ms, play_ms, fade_out_ms, trim; levels: base_gain_db, voice_ref_dbfs, gain_db, peak_dbfs,
  capped_by_voice), dropped[] (every candidate the rules removed, with the reason), verification (pass, passes,
  accuracy, voice_rule, loudness, corrections), files, hook2 (the same for the alternate clip, or why it was skipped).
- sfx_stem.wav (the sounds alone, 48 kHz mono), mix.wav (voice plus sounds, the audio S13 muxes), draft_mixed.mp4
  (draft.mp4 with the mix, for S12), sound-map.txt (one readable line per sound: time, cue type, file, the visual
  event, the gain and trims)
- sfx_stem_hook2.wav, mix_hook2.wav, sound-map-hook2.txt for the hook 2 clip (when 10-build/hook2 exists)
- logs/sfx-usage.json gains this reel's picks per cue type (the last 20 reels are kept)
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).

## Invariants
- every planned sound within config sfx.sync_tolerance_ms (33 ms) of its event (the peak for whooshes, the onset for
  the rest) on the rendered stem, and no sound the plan does not list
- every sound's peak at least sfx.min_db_under_voice (8 dB) under the voice's peak around that moment (the voice's
  overall peak minus 12 dB when the voice is quiet there)
- the mix at voice.loudness_lufs plus or minus 1 LU, true peak at most voice.true_peak_dbtp
- at most sfx.max_per_10s sounds in any 10 s, never two within sfx.min_spacing_ms, nothing on the hook's first word
  but hook_hit, no attention whoosh in the first 2 s or during the ask
- the map missing or empty: the voice alone (mix.wav is vo.wav, the stem silent) plus a NEEDS REVIEW flag

## Exit codes
0 done, anything else a code error for the review and fix loop (BUILD_SPEC.md 4.2): a missing input, a failing tool, the
verification still failing after sfx.verify_passes correction passes, build-sfx-map's indexer call failing.

## Model and session
No model. The map's rebuild at the start (bash pipeline/bin/build-sfx-map) makes the indexer call of BUILD_SPEC.md 2.6
only when new unclear files appeared in styles/sfx/.

## dummy.sh
`bash pipeline/stages/11-sfx/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
