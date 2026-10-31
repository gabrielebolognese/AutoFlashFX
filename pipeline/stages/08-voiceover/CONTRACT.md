# 08-voiceover: Voiceover (S8)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M7
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S8.

## Purpose
Generate the voice beat by beat with the configured engine (clone from reference.wav when it can), hook with higher energy, fixed gaps, silences trimmed; align with faster-whisper into words.json; check speakability by word error rate; normalize loudness; also hook 2's voice. No model calls.

## Inputs
- 07-script/script.json (spoken track), 06-judge/judge.json (hook 2)
- config tts and voice, library/voice/reference.wav, library/profile/pronunciations.txt

## Outputs (in runs/<id>/08-voiceover/)
- words.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- vo.wav, vo_hook2.wav (48 kHz, -14 LUFS integrated, true peak at most -1.5 dBTP)
- words.json, words_hook2.json: engine, duration_ms, words (word, start_ms, end_ms, beat)
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- WER over 3% on a line: new seed up to 3 times, then the whole voiceover with the fallback engine (never two voices in one reel), then one line rewrite through S7, then a flag
- a line more than 15% over its estimate is flagged
- timestamps monotonic, every beat covered

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
No model. Engines in .venv-tts (Python 3.11).

## dummy.sh
`bash pipeline/stages/08-voiceover/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
